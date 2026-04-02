"""这个文件提供账号池相关接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from codex_multi_account.api.serializers import public_account_dict
from codex_multi_account.services.account_pool import AccountPoolService
from codex_multi_account.services.login_session import LoginSessionInputError, LoginSessionManager
from codex_multi_account.services.probe_service import ProbeService
from codex_multi_account.services.switch_service import AccountUnavailableError, SwitchService


class SwitchRequest(BaseModel):
    """描述切换请求。"""

    target: Literal["openclaw", "codex", "both"]


class ImportRequest(BaseModel):
    """描述导入请求。"""

    label: str | None = None


class LoginInputRequest(BaseModel):
    """描述网页登录页提交的授权信息。"""

    value: str


class CodexBatchImportRequest(BaseModel):
    """描述批量导入的 Codex JSON。"""

    items: list[dict[str, object]]


def build_accounts_router(
    account_pool: AccountPoolService,
    probe_service: ProbeService,
    switch_service: SwitchService,
    login_manager: LoginSessionManager,
) -> APIRouter:
    """构建账号相关路由。"""

    router = APIRouter(prefix="/api/accounts", tags=["accounts"])

    @router.get("")
    def list_accounts() -> dict[str, list[dict[str, object]]]:
        return {
            "accounts": [public_account_dict(item) for item in account_pool.list_accounts()]
        }

    @router.post("/import/openclaw-current")
    def import_openclaw_current(payload: ImportRequest) -> dict[str, object]:
        return public_account_dict(account_pool.import_openclaw_current(payload.label))

    @router.post("/import/codex-current")
    def import_codex_current(payload: ImportRequest) -> dict[str, object]:
        return public_account_dict(account_pool.import_codex_current(payload.label))

    @router.post("/import/codex-batch")
    def import_codex_batch(payload: CodexBatchImportRequest) -> dict[str, object]:
        accounts = account_pool.import_codex_batch(payload.items)
        return {
            "importedCount": len(accounts),
            "accounts": [public_account_dict(item) for item in accounts],
        }

    @router.get("/export/codex-batch")
    def export_codex_batch() -> dict[str, object]:
        return {"items": account_pool.export_codex_batch()}

    @router.post("/login/openclaw")
    def login_openclaw() -> dict[str, object]:
        return login_manager.start("openclaw").to_dict()

    @router.post("/login/codex")
    def login_codex() -> dict[str, object]:
        return login_manager.start("codex").to_dict()

    @router.get("/logins")
    def list_login_states() -> dict[str, object]:
        return {
            "targets": {
                key: value.to_dict()
                for key, value in login_manager.snapshot_all().items()
            }
        }

    @router.post("/login/{target}/cancel")
    def cancel_login(target: Literal["openclaw", "codex"]) -> dict[str, object]:
        return login_manager.cancel(target).to_dict()

    @router.post("/login/{target}/input")
    def submit_login_input(
        target: Literal["openclaw", "codex"],
        payload: LoginInputRequest,
    ) -> dict[str, object]:
        try:
            return login_manager.submit_input(target, payload.value).to_dict()
        except LoginSessionInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/{account_id}")
    def get_account(account_id: str) -> dict[str, object]:
        account = account_pool.get_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account-not-found")
        return public_account_dict(account)

    @router.post("/{account_id}/probe")
    def probe_account(account_id: str) -> dict[str, object]:
        return public_account_dict(probe_service.probe_account(account_id))

    @router.post("/{account_id}/switch")
    def switch_account(account_id: str, payload: SwitchRequest) -> dict[str, object]:
        try:
            return switch_service.switch_target(account_id, payload.target)
        except (KeyError, AccountUnavailableError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/{account_id}/disable")
    def disable_account(account_id: str) -> dict[str, object]:
        return public_account_dict(account_pool.disable_account(account_id))

    @router.post("/{account_id}/enable")
    def enable_account(account_id: str) -> dict[str, object]:
        return public_account_dict(account_pool.enable_account(account_id))

    @router.delete("/{account_id}")
    def delete_account(account_id: str) -> dict[str, str]:
        account_pool.delete_account(account_id)
        return {"status": "deleted"}

    return router
