"""这个文件验证账号探测和用量解析的关键边界。"""

from __future__ import annotations

from dataclasses import dataclass

from codex_multi_account.config import AppSettings
from codex_multi_account.models.account import (
    AccountBindings,
    AccountQuota,
    AccountRecord,
    AccountStatus,
    RuntimeSnapshot,
    TargetBinding,
)
from codex_multi_account.services.probe_service import ProbeService, parse_usage_payload


@dataclass
class FakeSnapshotReader:
    """按快照 id 返回固定运行时快照。"""

    snapshots: dict[str, RuntimeSnapshot]

    def read_snapshot(self, snapshot_id: str) -> RuntimeSnapshot:
        """读取指定快照。"""

        return self.snapshots[snapshot_id]


class FakeAccountPool:
    """用最小能力模拟账号池。"""

    def __init__(self, account: AccountRecord, snapshots: dict[str, RuntimeSnapshot]) -> None:
        self.account = account
        self.openclaw = FakeSnapshotReader(snapshots)
        self.codex = FakeSnapshotReader(snapshots)

    def require_account(self, account_id: str) -> AccountRecord:
        """返回唯一账号。"""

        assert account_id == self.account.id
        return self.account

    def update_account(self, account: AccountRecord) -> AccountRecord:
        """记录更新后的账号。"""

        self.account = account
        return account

    def list_accounts(self) -> list[AccountRecord]:
        """返回唯一账号。"""

        return [self.account]


def build_settings(tmp_path) -> AppSettings:
    """构造测试设置。"""

    return AppSettings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        openclaw_home=tmp_path / ".openclaw",
        codex_home=tmp_path / ".codex",
        primary_agent="main",
        usage_url="http://127.0.0.1:9/usage",
        fallback_model="bailian/qwen3.5-plus",
    )


def test_parse_usage_payload_classifies_windows_by_duration() -> None:
    """不应盲信 primary/secondary 命名顺序。"""

    payload = {
        "rate_limit": {
            "primary_window": {
                "used_percent": 80,
                "limit_window_seconds": 604800,
                "reset_at": 200,
            },
            "secondary_window": {
                "used_percent": 30,
                "limit_window_seconds": 18000,
                "reset_at": 100,
            },
        }
    }

    parsed = parse_usage_payload(payload)

    assert parsed["five_hour_used_pct"] == 30.0
    assert parsed["weekly_used_pct"] == 80.0
    assert parsed["reset_at_five_hour"] == 100
    assert parsed["reset_at_weekly"] == 200


def test_probe_account_uses_other_binding_when_first_binding_is_stale(tmp_path) -> None:
    """同一个账号的一侧快照失效时，应尝试另一侧绑定。"""

    account = AccountRecord(
        id="acct_1",
        label="acct_1",
        bindings=AccountBindings(
            openclaw=TargetBinding(snapshot_id="oc"),
            codex=TargetBinding(snapshot_id="cx"),
        ),
        status=AccountStatus(health="quota-unknown", reason="not-probed"),
        quota=AccountQuota(five_hour_used_pct=91.0, weekly_used_pct=92.0),
    )
    pool = FakeAccountPool(
        account,
        snapshots={
            "oc": RuntimeSnapshot(target="openclaw", access_token="openclaw-token", has_binding=True),
            "cx": RuntimeSnapshot(target="codex", access_token="codex-token", has_binding=True),
        },
    )
    service = ProbeService(build_settings(tmp_path), pool)  # type: ignore[arg-type]

    def fake_fetch_usage(token: str, account_id: str | None) -> dict[str, object]:
        if token == "openclaw-token":
            return {"health": "auth-invalid", "reason": "http-401"}
        return {
            "health": "healthy",
            "reason": "live-usage-api",
            "five_hour_used_pct": 35.0,
            "weekly_used_pct": 40.0,
            "reset_at_five_hour": 101,
            "reset_at_weekly": 202,
        }

    service._fetch_usage = fake_fetch_usage  # type: ignore[method-assign]

    result = service.probe_account("acct_1")

    assert result.status.health == "healthy"
    assert result.status.reason == "live-usage-api"
    assert result.quota.five_hour_used_pct == 35.0
    assert result.quota.weekly_used_pct == 40.0


def test_probe_account_for_api_key_only_checks_connectivity(tmp_path) -> None:
    """第三方 API 账号不探额度，只看连通性。"""

    account = AccountRecord(
        id="acct_api",
        label="ananapi",
        kind="api",
        api_profile={
            "provider_name": "OpenAI",
            "base_url": "https://www.ananapi.com/",
            "wire_api": "responses",
            "requires_openai_auth": True,
            "api_key": "sk-demo",
            "model": "gpt-5.4",
        },
        status=AccountStatus(health="quota-unknown", reason="not-probed"),
    )
    pool = FakeAccountPool(account, {})
    service = ProbeService(build_settings(tmp_path), pool)  # type: ignore[arg-type]
    service._probe_api_profile = lambda current: {  # type: ignore[method-assign]
        "health": "healthy",
        "reason": "api-connect-ok",
    }

    result = service.probe_account("acct_api")

    assert result.status.health == "healthy"
    assert result.status.reason == "api-connect-ok"
    assert result.quota.five_hour_used_pct is None
