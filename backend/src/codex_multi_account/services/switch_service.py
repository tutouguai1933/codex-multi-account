"""这个文件负责把账号分配到 OpenClaw、Codex 或同时分配。"""

from __future__ import annotations

from typing import Any, Literal

from codex_multi_account.models.account import AccountRecord
from codex_multi_account.services.account_pool import AccountPoolService


class AccountUnavailableError(RuntimeError):
    """账号不可切换时抛出的异常。"""


class SwitchService:
    """负责把快照切换回运行时。"""

    def __init__(self, account_pool: AccountPoolService) -> None:
        self.account_pool = account_pool

    def _require_switchable(self, account: AccountRecord, target: str) -> str:
        """检查目标是否有对应绑定。"""

        if account.status.manual_disabled:
            raise AccountUnavailableError("账号已被手动禁用")
        binding = account.bindings.openclaw if target == "openclaw" else account.bindings.codex
        if not binding.snapshot_id:
            raise AccountUnavailableError(f"账号缺少 {target} 绑定")
        return binding.snapshot_id

    def switch_target(
        self,
        account_id: str,
        target: Literal["openclaw", "codex", "both"],
    ) -> dict[str, Any]:
        """切换指定目标。"""

        account = self.account_pool.require_account(account_id)
        if target in {"openclaw", "both"}:
            snapshot_id = self._require_switchable(account, "openclaw")
            self.account_pool.openclaw.activate_snapshot(snapshot_id)
            self.account_pool.assign_target_with_lock(
                "openclaw",
                account_id,
                manual_lock=account.kind == "api",
            )
        if target in {"codex", "both"}:
            snapshot_id = self._require_switchable(account, "codex")
            self.account_pool.codex.activate_snapshot(snapshot_id)
            self.account_pool.assign_target_with_lock(
                "codex",
                account_id,
                manual_lock=account.kind == "api",
            )
        return {
            "accountId": account_id,
            "target": target,
            "status": "ok",
        }
