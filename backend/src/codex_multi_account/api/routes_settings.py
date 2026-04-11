"""这个文件提供调度设置接口。"""

from __future__ import annotations

from fastapi import APIRouter

from codex_multi_account.adapters.codex_cli import CodexCliAdapter
from codex_multi_account.models.settings import (
    CodexQuickSettings,
    CodexRuntimeFiles,
    CodexRuntimeSaveRequest,
    SchedulerSettings,
)
from codex_multi_account.storage.json_store import JsonStore


def build_settings_router(settings_store: JsonStore, codex: CodexCliAdapter) -> APIRouter:
    """构建设置路由。"""

    router = APIRouter(prefix="/api/settings", tags=["settings"])

    @router.get("")
    def get_settings() -> dict[str, object]:
        payload = settings_store.read(default=SchedulerSettings().model_dump(mode="json"))
        return SchedulerSettings.model_validate(payload).model_dump(mode="json")

    @router.put("")
    def save_settings(payload: SchedulerSettings) -> dict[str, object]:
        settings_store.write(payload.model_dump(mode="json"))
        return payload.model_dump(mode="json")

    @router.get("/codex-runtime")
    def get_codex_runtime() -> dict[str, object]:
        return CodexRuntimeFiles.model_validate(codex.read_runtime_files()).model_dump(mode="json")

    @router.put("/codex-runtime")
    def save_codex_runtime(payload: CodexRuntimeSaveRequest) -> dict[str, object]:
        return CodexRuntimeFiles.model_validate(
            codex.save_runtime_files(payload.config_text, payload.auth_text)
        ).model_dump(mode="json")

    @router.put("/codex-runtime/quick")
    def save_codex_runtime_quick(payload: CodexQuickSettings) -> dict[str, object]:
        return CodexRuntimeFiles.model_validate(
            codex.save_quick_settings(payload.model_dump(mode="json"))
        ).model_dump(mode="json")

    return router
