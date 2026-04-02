"""这个文件提供调度设置接口。"""

from __future__ import annotations

from fastapi import APIRouter

from codex_multi_account.models.settings import SchedulerSettings
from codex_multi_account.storage.json_store import JsonStore


def build_settings_router(settings_store: JsonStore) -> APIRouter:
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

    return router

