"""这个文件提供手动触发调度和刷新接口。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from codex_multi_account.scheduler.engine import SchedulerEngine
from codex_multi_account.scheduler.runner import SchedulerRunner


def build_scheduler_router(scheduler: SchedulerEngine, scheduler_runner: SchedulerRunner) -> APIRouter:
    """构建调度路由。"""

    router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

    @router.get("/status")
    def scheduler_status() -> dict[str, object]:
        return scheduler_runner.snapshot().to_dict()

    @router.post("/run")
    async def run_scheduler() -> dict[str, object]:
        try:
            result = await scheduler_runner.run_now(source="manual")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"调度失败：{exc}") from exc
        return {
            "assignments": result.assignments,
            "actions": result.actions,
            "reason": result.reason,
            "forcedImmediate": result.forced_immediate,
            "events": [item.model_dump(mode="json") for item in result.events],
        }

    @router.post("/refresh")
    def refresh_only(background_tasks: BackgroundTasks = None) -> dict[str, str]:
        if background_tasks is None:
            scheduler.probe_service.probe_all()
            return {"status": "refreshed"}
        background_tasks.add_task(scheduler.probe_service.probe_all)
        return {"status": "refresh-started"}

    return router
