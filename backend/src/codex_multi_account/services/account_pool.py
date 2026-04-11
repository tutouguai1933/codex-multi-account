"""这个文件负责统一账号池的增删改查与目标分配。"""

from __future__ import annotations

import json
import re
import time
from hashlib import md5
from typing import Iterable

from codex_multi_account.adapters.codex_cli import CodexCliAdapter
from codex_multi_account.adapters.openclaw import OpenClawAdapter, decode_jwt_payload
from codex_multi_account.models.account import AccountRecord, ApiProfile, RuntimeSnapshot
from codex_multi_account.storage.json_store import JsonStore
from codex_multi_account.utils.api_profiles import ensure_api_profile_fingerprint, normalize_base_url


class AccountPoolService:
    """管理统一账号池。"""

    def __init__(
        self,
        store: JsonStore,
        openclaw: OpenClawAdapter,
        codex: CodexCliAdapter,
    ) -> None:
        self.store = store
        self.openclaw = openclaw
        self.codex = codex

    def list_accounts(self) -> list[AccountRecord]:
        """返回全部账号。"""

        payload = self.store.read(default={"accounts": []})
        return [AccountRecord.model_validate(item) for item in payload.get("accounts", [])]

    def save_accounts(self, accounts: Iterable[AccountRecord]) -> None:
        """覆盖写回账号列表。"""

        self.store.write({"accounts": [item.model_dump(mode="json") for item in accounts]})

    def get_account(self, account_id: str) -> AccountRecord | None:
        """按 id 获取账号。"""

        for item in self.list_accounts():
            if item.id == account_id:
                return item
        return None

    def require_account(self, account_id: str) -> AccountRecord:
        """按 id 获取账号，不存在时抛错。"""

        account = self.get_account(account_id)
        if account is None:
            raise KeyError(f"账号不存在: {account_id}")
        return account

    def resolve_account_for_runtime(self, runtime: RuntimeSnapshot) -> AccountRecord | None:
        """按当前真实运行态找到对应账号。"""

        return self._find_existing(self.list_accounts(), runtime)

    def _next_account_id(self, accounts: list[AccountRecord]) -> str:
        """生成新的账号 id。"""

        numbers = []
        for item in accounts:
            match = re.fullmatch(r"acct_(\d+)", item.id)
            if match:
                numbers.append(int(match.group(1)))
        next_number = max(numbers, default=0) + 1
        return f"acct_{next_number}"

    def _default_label(self, snapshot: RuntimeSnapshot, fallback: str) -> str:
        """生成默认显示名。"""

        if snapshot.active_email:
            return snapshot.active_email.split("@", 1)[0]
        return fallback

    def _find_existing(self, accounts: list[AccountRecord], runtime: RuntimeSnapshot) -> AccountRecord | None:
        """按真实账号特征找现有记录，避免同邮箱不同 workspace 误合并。"""

        if runtime.account_kind == "api" and runtime.api_key_fingerprint:
            for item in accounts:
                if item.kind == "api" and item.api_profile and item.api_profile.fingerprint == runtime.api_key_fingerprint:
                    return item
        for item in accounts:
            metadata = item.metadata.get("identity") if isinstance(item.metadata, dict) else None
            if not isinstance(metadata, dict):
                metadata = {}
            same_account_id = bool(runtime.active_account_id) and metadata.get("account_id") == runtime.active_account_id
            same_user_id = bool(runtime.user_id) and metadata.get("user_id") == runtime.user_id
            same_email = bool(runtime.active_email) and item.email == runtime.active_email
            if same_account_id and same_user_id:
                return item
            if same_account_id and same_email:
                return item
            if runtime.active_account_id is None and runtime.user_id is None and same_email:
                return item
        return None

    def _apply_identity_metadata(self, account: AccountRecord, runtime: RuntimeSnapshot) -> None:
        """把共享账号身份字段落到账号元数据。"""

        identity = account.metadata.setdefault("identity", {})
        if not isinstance(identity, dict):
            identity = {}
            account.metadata["identity"] = identity
        if runtime.active_account_id:
            identity["account_id"] = runtime.active_account_id
        if runtime.user_id:
            identity["user_id"] = runtime.user_id
        if runtime.plan_type:
            identity["plan_type"] = runtime.plan_type
        if runtime.auth_mode:
            identity["auth_mode"] = runtime.auth_mode
        if runtime.account_kind:
            identity["account_kind"] = runtime.account_kind
        if runtime.provider_name:
            identity["provider_name"] = runtime.provider_name
        if runtime.base_url:
            identity["base_url"] = runtime.base_url
        if runtime.api_key_fingerprint:
            identity["api_fingerprint"] = runtime.api_key_fingerprint

    def _merge_runtime(
        self,
        target: str,
        snapshot_id: str,
        runtime: RuntimeSnapshot,
        label: str | None,
    ) -> AccountRecord:
        """把某一侧的运行时导入到账号池。"""

        accounts = self.list_accounts()
        existing = self._find_existing(accounts, runtime)
        if existing is None:
            existing = AccountRecord(
                id=self._next_account_id(accounts),
                label=label or self._default_label(runtime, snapshot_id),
                kind=runtime.account_kind,
                email=runtime.active_email,
            )
            accounts.append(existing)
        existing.kind = runtime.account_kind or existing.kind
        if runtime.active_email and not existing.email:
            existing.email = runtime.active_email
        self._apply_identity_metadata(existing, runtime)
        if target == "openclaw":
            existing.bindings.openclaw.snapshot_id = snapshot_id
            existing.bindings.openclaw.available = True
        else:
            existing.bindings.codex.snapshot_id = snapshot_id
            existing.bindings.codex.available = True
        existing.status.health = "healthy" if runtime.has_binding else "missing-binding"
        existing.status.reason = "imported-current-runtime"
        existing.timestamps.last_detected_at = int(time.time())
        self.save_accounts(accounts)
        return existing

    def _merge_api_account(
        self,
        profile: ApiProfile,
        label: str | None,
        codex_snapshot_id: str,
        openclaw_snapshot_id: str,
    ) -> AccountRecord:
        """把第三方 API 账号写进统一账号池。"""

        profile = ensure_api_profile_fingerprint(profile)
        accounts = self.list_accounts()
        existing = next(
            (
                item
                for item in accounts
                if item.kind == "api"
                and item.api_profile is not None
                and item.api_profile.fingerprint == profile.fingerprint
            ),
            None,
        )
        if existing is None:
            existing = AccountRecord(
                id=self._next_account_id(accounts),
                label=label or normalize_base_url(profile.base_url),
                kind="api",
                email=None,
                api_profile=profile,
            )
            accounts.append(existing)
        existing.kind = "api"
        existing.api_profile = profile
        existing.email = None
        existing.bindings.codex.snapshot_id = codex_snapshot_id
        existing.bindings.codex.available = True
        existing.bindings.openclaw.snapshot_id = openclaw_snapshot_id
        existing.bindings.openclaw.available = True
        existing.status.health = "quota-unknown"
        existing.status.reason = "api-account-added"
        self._apply_identity_metadata(
            existing,
            RuntimeSnapshot(
                target="codex",
                account_kind="api",
                active_account_id=profile.fingerprint,
                auth_mode="apikey",
                provider_name=profile.provider_name,
                base_url=profile.base_url,
                api_key_fingerprint=profile.fingerprint,
                active_model=profile.model,
                has_binding=True,
                raw_profile={},
            ),
        )
        self.save_accounts(accounts)
        return existing

    def _safe_snapshot_id(self, value: str) -> str:
        """把外部 id 转成适合文件名的快照 id。"""

        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
        return cleaned or f"snapshot-{int(time.time())}"

    def _build_openclaw_profile_from_codex_export(self, exported: dict[str, object]) -> dict[str, object]:
        """把 Codex 导出条目转成 OpenClaw profile。"""

        tokens = exported.get("tokens") if isinstance(exported, dict) else {}
        tokens = tokens if isinstance(tokens, dict) else {}
        access_token = tokens.get("access_token")
        access_payload = decode_jwt_payload(str(access_token or ""))
        return {
            "type": "oauth",
            "provider": "openai-codex",
            "access": access_token,
            "refresh": tokens.get("refresh_token"),
            "accountId": exported.get("account_id"),
            "expires": access_payload.get("exp"),
        }

    def _snapshot_base_for_exported_item(self, exported: dict[str, object], runtime: RuntimeSnapshot) -> str:
        """给导入条目生成稳定快照名。"""

        raw_id = exported.get("id")
        if isinstance(raw_id, str) and raw_id:
            return self._safe_snapshot_id(raw_id)
        unique = "|".join(
            [
                str(runtime.active_email or ""),
                str(runtime.active_account_id or ""),
                str(runtime.user_id or ""),
            ]
        )
        return f"codex-{md5(unique.encode('utf-8')).hexdigest()[:16]}"

    def import_codex_batch(self, items: list[dict[str, object]]) -> list[AccountRecord]:
        """批量导入 cockpit-tools 导出的 Codex JSON，并同时补齐两侧快照。"""

        imported_accounts: list[AccountRecord] = []
        for exported in items:
            auth_payload = self.codex.build_auth_payload(exported)
            runtime = self.codex._to_runtime_snapshot(auth_payload)
            snapshot_base = self._snapshot_base_for_exported_item(exported, runtime)
            codex_snapshot_id = self._safe_snapshot_id(f"{snapshot_base}-codex")
            openclaw_snapshot_id = self._safe_snapshot_id(f"{snapshot_base}-openclaw")
            self.codex.write_snapshot_payload(codex_snapshot_id, auth_payload)
            openclaw_profile = self._build_openclaw_profile_from_codex_export(exported)
            self.openclaw.write_snapshot_profile(openclaw_snapshot_id, openclaw_profile)
            account = self._merge_runtime("codex", codex_snapshot_id, runtime, None)
            account.bindings.openclaw.snapshot_id = openclaw_snapshot_id
            account.bindings.openclaw.available = True
            codex_export = dict(exported)
            account.metadata["codex_export"] = codex_export
            if exported.get("tags") is not None and not account.tags:
                tags = exported.get("tags")
                if isinstance(tags, list):
                    account.tags = [str(item) for item in tags]
            quota = exported.get("quota")
            if isinstance(quota, dict):
                hourly = quota.get("hourly_percentage")
                weekly = quota.get("weekly_percentage")
                try:
                    account.quota.five_hour_used_pct = float(100 - float(hourly)) if hourly is not None else account.quota.five_hour_used_pct
                except Exception:
                    pass
                try:
                    account.quota.weekly_used_pct = float(100 - float(weekly)) if weekly is not None else account.quota.weekly_used_pct
                except Exception:
                    pass
                account.quota.reset_at_five_hour = quota.get("hourly_reset_time") if isinstance(quota.get("hourly_reset_time"), int) else account.quota.reset_at_five_hour
                account.quota.reset_at_weekly = quota.get("weekly_reset_time") if isinstance(quota.get("weekly_reset_time"), int) else account.quota.reset_at_weekly
            imported_accounts.append(self.update_account(account))
        return imported_accounts

    def import_token_payload(self, payload: str, label: str | None = None) -> list[AccountRecord]:
        """把粘贴进来的 token JSON 或账号 JSON 导入账号池。"""

        parsed = json.loads(payload)
        if isinstance(parsed, list):
            return self.import_codex_batch(
                [item for item in parsed if isinstance(item, dict)]
            )
        if not isinstance(parsed, dict):
            raise ValueError("导入内容必须是 JSON 对象或数组")
        if "tokens" in parsed:
            codex_snapshot_id = label or self._safe_snapshot_id(f"token-{int(time.time())}-codex")
            runtime = self.codex.write_snapshot_payload(codex_snapshot_id, parsed)
            openclaw_snapshot_id = self._safe_snapshot_id(f"{codex_snapshot_id}-openclaw")
            self.openclaw.write_snapshot_profile(
                openclaw_snapshot_id,
                {
                    "type": "oauth",
                    "provider": "openai-codex",
                    "access": ((parsed.get("tokens") or {}).get("access_token")),
                    "refresh": ((parsed.get("tokens") or {}).get("refresh_token")),
                    "accountId": parsed.get("account_id"),
                    "expires": decode_jwt_payload(str(((parsed.get("tokens") or {}).get("access_token")) or "")).get("exp"),
                },
            )
            account = self._merge_runtime("codex", codex_snapshot_id, runtime, label)
            account.bindings.openclaw.snapshot_id = openclaw_snapshot_id
            account.bindings.openclaw.available = True
            return [self.update_account(account)]
        raise ValueError("暂不支持这种 token JSON，请改用 API Key 或 cockpit 导出格式")

    def create_api_account(self, payload: dict[str, object]) -> AccountRecord:
        """创建一条第三方 API 账号记录。"""

        label = str(payload.get("label") or "").strip() or None
        profile = ensure_api_profile_fingerprint(
            ApiProfile.model_validate(
                {
                    "provider_name": "openai",
                    "base_url": payload.get("base_url"),
                    "api_key": payload.get("api_key"),
                }
            )
        )
        codex_snapshot_id = self._safe_snapshot_id(f"{profile.fingerprint}-codex")
        openclaw_snapshot_id = self._safe_snapshot_id(f"{profile.fingerprint}-openclaw")
        self.codex.write_api_snapshot(codex_snapshot_id, profile)
        self.openclaw.write_api_snapshot(openclaw_snapshot_id, profile)
        return self.update_account(
            self._merge_api_account(profile, label, codex_snapshot_id, openclaw_snapshot_id)
        )

    def _build_export_from_account(self, account: AccountRecord) -> dict[str, object] | None:
        """把统一账号池条目转回 cockpit-tools 兼容结构。"""

        if not account.bindings.codex.snapshot_id:
            return None
        snapshot = self.codex.read_snapshot(account.bindings.codex.snapshot_id)
        payload = snapshot.raw_profile if isinstance(snapshot.raw_profile, dict) else {}
        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            return None
        stored = account.metadata.get("codex_export") if isinstance(account.metadata, dict) else None
        stored = dict(stored) if isinstance(stored, dict) else {}
        identity = account.metadata.get("identity") if isinstance(account.metadata, dict) else None
        identity = identity if isinstance(identity, dict) else {}
        export_id = stored.get("id")
        if not isinstance(export_id, str) or not export_id:
            basis = "|".join([account.id, str(account.email or ""), str(identity.get("account_id") or "")])
            export_id = f"codex_{md5(basis.encode('utf-8')).hexdigest()}"
        quota = dict(stored.get("quota")) if isinstance(stored.get("quota"), dict) else {}
        quota.update(
            {
                "hourly_percentage": None
                if account.quota.five_hour_used_pct is None
                else int(round(100 - account.quota.five_hour_used_pct)),
                "hourly_reset_time": account.quota.reset_at_five_hour,
                "hourly_window_minutes": quota.get("hourly_window_minutes", 300),
                "hourly_window_present": quota.get("hourly_window_present", account.quota.five_hour_used_pct is not None),
                "weekly_percentage": None
                if account.quota.weekly_used_pct is None
                else int(round(100 - account.quota.weekly_used_pct)),
                "weekly_reset_time": account.quota.reset_at_weekly,
                "weekly_window_minutes": quota.get("weekly_window_minutes", 10080),
                "weekly_window_present": quota.get("weekly_window_present", account.quota.weekly_used_pct is not None),
                "raw_data": quota.get("raw_data"),
            }
        )
        return {
            "id": export_id,
            "email": account.email,
            "auth_mode": payload.get("auth_mode") or identity.get("auth_mode") or stored.get("auth_mode") or "oauth",
            "user_id": identity.get("user_id") or stored.get("user_id"),
            "plan_type": identity.get("plan_type") or stored.get("plan_type"),
            "account_id": identity.get("account_id") or stored.get("account_id"),
            "organization_id": stored.get("organization_id"),
            "account_name": stored.get("account_name"),
            "account_structure": stored.get("account_structure"),
            "tokens": {
                "id_token": tokens.get("id_token"),
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
            },
            "quota": quota,
            "usage_updated_at": stored.get("usage_updated_at"),
            "tags": stored.get("tags"),
            "created_at": stored.get("created_at"),
            "last_used": stored.get("last_used"),
        }

    def export_codex_batch(self) -> list[dict[str, object]]:
        """导出 cockpit-tools 兼容的 Codex JSON 列表。"""

        items = []
        for account in self.list_accounts():
            exported = self._build_export_from_account(account)
            if exported is not None:
                items.append(exported)
        return items

    def import_openclaw_current(self, label: str | None = None) -> AccountRecord:
        """导入当前 OpenClaw 登录态。"""

        runtime = self.openclaw.read_runtime_snapshot()
        snapshot_id = label or self._default_label(runtime, "openclaw-current")
        self.openclaw.capture_current(snapshot_id)
        return self._merge_runtime("openclaw", snapshot_id, runtime, label)

    def import_codex_current(self, label: str | None = None) -> AccountRecord:
        """导入当前 Codex 登录态。"""

        runtime = self.codex.read_runtime_snapshot()
        snapshot_id = label or self._default_label(runtime, "codex-current")
        self.codex.capture_current(snapshot_id)
        return self._merge_runtime("codex", snapshot_id, runtime, label)

    def update_account(self, account: AccountRecord) -> AccountRecord:
        """更新单个账号。"""

        accounts = self.list_accounts()
        updated: list[AccountRecord] = []
        replaced = False
        for item in accounts:
            if item.id == account.id:
                updated.append(account)
                replaced = True
            else:
                updated.append(item)
        if not replaced:
            updated.append(account)
        self.save_accounts(updated)
        return account

    def disable_account(self, account_id: str) -> AccountRecord:
        """禁用账号。"""

        account = self.require_account(account_id)
        account.status.manual_disabled = True
        account.status.health = "manual-disabled"
        account.status.reason = "disabled-by-user"
        return self.update_account(account)

    def enable_account(self, account_id: str) -> AccountRecord:
        """启用账号。"""

        account = self.require_account(account_id)
        account.status.manual_disabled = False
        if account.status.health == "manual-disabled":
            account.status.health = "quota-unknown"
            account.status.reason = "enabled-by-user"
        return self.update_account(account)

    def delete_account(self, account_id: str) -> None:
        """删除账号及其本地快照。"""

        account = self.require_account(account_id)
        if account.bindings.openclaw.snapshot_id:
            self.openclaw.delete_snapshot(account.bindings.openclaw.snapshot_id)
        if account.bindings.codex.snapshot_id:
            self.codex.delete_snapshot(account.bindings.codex.snapshot_id)
        remaining = [item for item in self.list_accounts() if item.id != account_id]
        self.save_accounts(remaining)

    def assign_target(self, target: str, account_id: str | None) -> None:
        """把某个目标分配给指定账号。"""

        self.assign_target_with_lock(target, account_id, manual_lock=False)

    def assign_target_with_lock(self, target: str, account_id: str | None, manual_lock: bool) -> None:
        """把目标分配给指定账号，并同步该目标的手动锁定状态。"""

        accounts = self.list_accounts()
        for item in accounts:
            if target == "openclaw":
                item.assignment.openclaw = item.id == account_id
                item.assignment.openclaw_locked = item.id == account_id and manual_lock
            elif target == "codex":
                item.assignment.codex = item.id == account_id
                item.assignment.codex_locked = item.id == account_id and manual_lock
            if item.id == account_id:
                item.timestamps.last_assigned_at = int(time.time())
        self.save_accounts(accounts)
