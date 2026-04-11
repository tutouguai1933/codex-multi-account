"""这个文件提供首页总览接口。"""

from __future__ import annotations

from fastapi import APIRouter

from codex_multi_account.api.serializers import public_account_dict
from codex_multi_account.scheduler.runner import SchedulerRunner
from codex_multi_account.services.account_pool import AccountPoolService
from codex_multi_account.storage.event_log import EventLog


def build_overview_router(
    account_pool: AccountPoolService,
    event_log: EventLog,
    scheduler_runner: SchedulerRunner,
) -> APIRouter:
    """构建总览路由。"""

    router = APIRouter(tags=["overview"])

    def display_name(account, runtime_email: str | None) -> str | None:
        """给总览面板返回可展示的当前账号名称。"""

        if account is None:
            return runtime_email
        return account.email or account.label or runtime_email

    @router.get("/api/overview")
    def overview() -> dict[str, object]:
        accounts = account_pool.list_accounts()
        openclaw_runtime = account_pool.openclaw.read_runtime_snapshot()
        codex_runtime = account_pool.codex.read_runtime_snapshot()
        current_openclaw = (
            account_pool.resolve_account_for_runtime(openclaw_runtime)
            if openclaw_runtime.has_binding
            else None
        )
        current_codex = (
            account_pool.resolve_account_for_runtime(codex_runtime)
            if codex_runtime.has_binding
            else None
        )
        if current_openclaw is None and current_codex is None:
            allocation_mode = "unassigned"
        elif current_openclaw is None or current_codex is None:
            allocation_mode = "partial"
        elif current_openclaw.id != current_codex.id:
            allocation_mode = "separated"
        else:
            allocation_mode = "shared"
        public_accounts: list[dict[str, object]] = []
        for item in accounts:
            payload = public_account_dict(item)
            payload["assignment"] = {
                "openclaw": bool(current_openclaw and item.id == current_openclaw.id),
                "codex": bool(current_codex and item.id == current_codex.id),
            }
            public_accounts.append(payload)
        return {
            "status": "ok",
            "summary": {
                "totalAccounts": len(accounts),
                "openclawAccountId": current_openclaw.id if current_openclaw else None,
                "codexAccountId": current_codex.id if current_codex else None,
                "openclawAccountEmail": display_name(current_openclaw, openclaw_runtime.active_email),
                "codexAccountEmail": display_name(current_codex, codex_runtime.active_email),
                "allocationMode": allocation_mode,
                "separated": bool(
                    current_openclaw and current_codex and current_openclaw.id != current_codex.id
                ),
            },
            "scheduler": scheduler_runner.snapshot().to_dict(),
            "accounts": public_accounts,
            "recentEvents": event_log.list_recent(limit=5),
        }

    return router
