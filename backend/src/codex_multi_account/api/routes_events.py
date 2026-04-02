"""这个文件提供事件日志查询接口。"""

from __future__ import annotations

from fastapi import APIRouter

from codex_multi_account.storage.event_log import EventLog


def build_events_router(event_log: EventLog) -> APIRouter:
    """构建事件日志路由。"""

    router = APIRouter(prefix="/api/events", tags=["events"])

    @router.get("")
    def list_events(limit: int = 50) -> dict[str, object]:
        return {"events": event_log.list_recent(limit=limit)}

    return router

