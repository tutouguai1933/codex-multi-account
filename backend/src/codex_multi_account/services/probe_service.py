"""这个文件负责状态检测与额度探测。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from codex_multi_account.config import AppSettings
from codex_multi_account.models.account import AccountRecord
from codex_multi_account.services.account_pool import AccountPoolService

FIVE_HOUR_WINDOW_SECONDS = 5 * 60 * 60
WEEKLY_WINDOW_SECONDS = 7 * 24 * 60 * 60
WEEKLY_RESET_GAP_SECONDS = 4 * 24 * 60 * 60


def clamp_percent(value: Any) -> float | None:
    """把接口返回的百分比规整到 0-100。"""

    try:
        number = float(value)
    except Exception:
        return None
    if number < 0:
        return 0.0
    if number > 100:
        return 100.0
    return round(number, 1)


def classify_usage_http_error(status: int, body_text: str = "") -> dict[str, Any]:
    """把 usage 接口的 HTTP 错误转成统一健康状态。"""

    lowered = body_text.lower()
    if status in {401, 403}:
        if "workspace" in lowered or "not enabled" in lowered or "plan" in lowered:
            return {"health": "plan-unavailable", "reason": f"http-{status}-workspace-or-plan"}
        return {"health": "auth-invalid", "reason": f"http-{status}-token-invalid"}
    if status == 404:
        return {"health": "plan-unavailable", "reason": "http-404"}
    if status == 429:
        return {"health": "quota-unknown", "reason": "http-429-rate-limited"}
    return {"health": "quota-unknown", "reason": f"http-{status}"}


def _normalize_window(window: Any, fallback_seconds: int) -> dict[str, float | int | None] | None:
    """把窗口对象规整成便于排序的结构。"""

    if not isinstance(window, dict):
        return None
    raw_seconds = window.get("limit_window_seconds")
    try:
        seconds = int(float(raw_seconds)) if raw_seconds is not None else fallback_seconds
    except Exception:
        seconds = fallback_seconds
    if seconds <= 0:
        seconds = fallback_seconds
    reset_at = window.get("reset_at")
    try:
        normalized_reset_at = int(float(reset_at)) if reset_at is not None else None
    except Exception:
        normalized_reset_at = None
    return {
        "used_percent": clamp_percent(window.get("used_percent")),
        "limit_window_seconds": seconds,
        "reset_at": normalized_reset_at,
    }


def _pick_five_hour_window(
    windows: list[dict[str, float | int | None]],
) -> dict[str, float | int | None] | None:
    """挑出最像短时额度窗口的那一个。"""

    if not windows:
        return None
    return min(
        windows,
        key=lambda item: (
            abs(int(item["limit_window_seconds"] or FIVE_HOUR_WINDOW_SECONDS) - FIVE_HOUR_WINDOW_SECONDS),
            int(item["limit_window_seconds"] or FIVE_HOUR_WINDOW_SECONDS),
        ),
    )


def _pick_weekly_window(
    windows: list[dict[str, float | int | None]],
    five_hour_window: dict[str, float | int | None] | None,
) -> dict[str, float | int | None] | None:
    """挑出最像周额度窗口的那一个。"""

    if not windows:
        return None
    candidates = sorted(
        windows,
        key=lambda item: int(item["limit_window_seconds"] or 0),
        reverse=True,
    )
    for candidate in candidates:
        seconds = int(candidate["limit_window_seconds"] or 0)
        if seconds >= WEEKLY_WINDOW_SECONDS:
            return candidate
    if five_hour_window is not None:
        primary_reset = five_hour_window.get("reset_at")
        for candidate in candidates:
            secondary_reset = candidate.get("reset_at")
            if primary_reset is None or secondary_reset is None:
                continue
            if int(secondary_reset) - int(primary_reset) >= WEEKLY_RESET_GAP_SECONDS:
                return candidate
    for candidate in candidates:
        if five_hour_window is None or candidate is not five_hour_window:
            return candidate
    return candidates[0]


def parse_usage_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """从 usage 接口结果里尽量稳健地解析 5 小时和周额度。"""

    rate_limit = payload.get("rate_limit") or {}
    windows = [
        item
        for item in (
            _normalize_window(rate_limit.get("primary_window"), FIVE_HOUR_WINDOW_SECONDS),
            _normalize_window(rate_limit.get("secondary_window"), WEEKLY_WINDOW_SECONDS),
        )
        if item is not None
    ]
    five_hour_window = _pick_five_hour_window(windows)
    weekly_window = _pick_weekly_window(windows, five_hour_window)
    return {
        "five_hour_used_pct": None if five_hour_window is None else five_hour_window.get("used_percent"),
        "weekly_used_pct": None if weekly_window is None else weekly_window.get("used_percent"),
        "reset_at_five_hour": None if five_hour_window is None else five_hour_window.get("reset_at"),
        "reset_at_weekly": None if weekly_window is None else weekly_window.get("reset_at"),
    }


class ProbeService:
    """根据快照内容更新账号状态和额度。"""

    def __init__(self, settings: AppSettings, account_pool: AccountPoolService) -> None:
        self.settings = settings
        self.account_pool = account_pool

    def _fetch_usage(self, token: str, account_id: str | None) -> dict[str, Any] | None:
        """调用 usage API，失败时返回空。"""

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "codex-multi-account",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id
        request = urllib.request.Request(self.settings.usage_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            return classify_usage_http_error(exc.code, body_text)
        except Exception as exc:  # pragma: no cover - 网络异常路径不稳定
            return {"health": "quota-unknown", "reason": f"usage-fetch-error:{type(exc).__name__}"}

        parsed = parse_usage_payload(payload)
        if all(parsed[key] is None for key in ("five_hour_used_pct", "weekly_used_pct")):
            return {"health": "quota-unknown", "reason": "usage-api-empty", **parsed}
        return {"health": "healthy", "reason": "live-usage-api", **parsed}

    def _clear_quota(self, account: AccountRecord) -> None:
        """清空旧额度，避免页面继续展示过期数据。"""

        account.quota.five_hour_used_pct = None
        account.quota.weekly_used_pct = None
        account.quota.reset_at_five_hour = None
        account.quota.reset_at_weekly = None

    def _pick_best_quota_result(self, results: list[dict[str, Any]]) -> dict[str, Any] | None:
        """从多侧绑定的检测结果里选出最可信的一份共享状态。"""

        if not results:
            return None
        priorities = {
            "healthy": 0,
            "quota-unknown": 1,
            "plan-unavailable": 2,
            "auth-invalid": 3,
        }
        return min(results, key=lambda item: priorities.get(str(item.get("health")), 99))

    def probe_account(self, account_id: str) -> AccountRecord:
        """探测单个账号并更新账号池。"""

        account = self.account_pool.require_account(account_id)
        snapshots = []
        if account.bindings.openclaw.snapshot_id:
            snapshots.append(self.account_pool.openclaw.read_snapshot(account.bindings.openclaw.snapshot_id))
        if account.bindings.codex.snapshot_id:
            snapshots.append(self.account_pool.codex.read_snapshot(account.bindings.codex.snapshot_id))
        valid_snapshots = [snapshot for snapshot in snapshots if snapshot.has_binding]
        if not valid_snapshots:
            account.status.health = "missing-binding"
            account.status.reason = "no-snapshot"
            self._clear_quota(account)
            return self.account_pool.update_account(account)
        if account.status.manual_disabled:
            account.status.health = "manual-disabled"
            account.status.reason = "disabled-by-user"
            self._clear_quota(account)
            return self.account_pool.update_account(account)
        quota_results = []
        for snapshot in valid_snapshots:
            if not snapshot.access_token:
                continue
            result = self._fetch_usage(snapshot.access_token, snapshot.active_account_id)
            if result:
                quota_results.append(result)
        quota = self._pick_best_quota_result(quota_results)
        if quota is None:
            account.status.health = "healthy"
            account.status.reason = "local-auth-present"
        else:
            account.status.health = quota["health"]
            account.status.reason = quota["reason"]
            account.quota.five_hour_used_pct = quota.get("five_hour_used_pct")
            account.quota.weekly_used_pct = quota.get("weekly_used_pct")
            account.quota.reset_at_five_hour = quota.get("reset_at_five_hour")
            account.quota.reset_at_weekly = quota.get("reset_at_weekly")
        account.timestamps.last_detected_at = int(time.time())
        return self.account_pool.update_account(account)

    def probe_all(self) -> list[AccountRecord]:
        """探测全部账号。"""

        results = []
        for account in self.account_pool.list_accounts():
            results.append(self.probe_account(account.id))
        return results
