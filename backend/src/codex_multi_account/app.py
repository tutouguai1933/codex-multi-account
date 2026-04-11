"""这个文件组装 FastAPI 应用，把存储、适配器、服务和路由连起来。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from codex_multi_account.adapters.codex_cli import CodexCliAdapter
from codex_multi_account.adapters.openclaw import OpenClawAdapter
from codex_multi_account.api.routes_accounts import build_accounts_router
from codex_multi_account.api.routes_events import build_events_router
from codex_multi_account.api.routes_overview import build_overview_router
from codex_multi_account.api.routes_scheduler import build_scheduler_router
from codex_multi_account.api.routes_settings import build_settings_router
from codex_multi_account.config import AppSettings, default_app_settings
from codex_multi_account.scheduler.engine import SchedulerEngine
from codex_multi_account.scheduler.runner import SchedulerRunner
from codex_multi_account.services.account_pool import AccountPoolService
from codex_multi_account.services.login_session import LoginSessionManager
from codex_multi_account.services.probe_service import ProbeService
from codex_multi_account.services.switch_service import SwitchService
from codex_multi_account.storage.event_log import EventLog
from codex_multi_account.storage.json_store import JsonStore


def _register_frontend_routes(app: FastAPI, project_root: Path) -> None:
    """在存在前端构建产物时，提供单服务静态托管。"""

    dist_dir = project_root / "web" / "dist"
    index_path = dist_dir / "index.html"
    if not index_path.exists():
        return
    dist_root = dist_dir.resolve()

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def frontend_assets(frontend_path: str) -> FileResponse:
        if not frontend_path or frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not-found")
        candidate = (dist_dir / frontend_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(dist_root):
            return FileResponse(candidate)
        return FileResponse(index_path)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """创建应用实例。"""

    app_settings = settings or default_app_settings()
    app_settings.data_dir.mkdir(parents=True, exist_ok=True)
    accounts_store = JsonStore(app_settings.data_dir / "accounts.json")
    settings_store = JsonStore(app_settings.data_dir / "settings.json")
    login_store = JsonStore(app_settings.data_dir / "login_sessions.json")
    event_log = EventLog(app_settings.data_dir / "events" / "events.jsonl")
    openclaw = OpenClawAdapter(
        openclaw_home=app_settings.openclaw_home,
        state_dir=app_settings.data_dir,
        primary_agent=app_settings.primary_agent,
    )
    codex = CodexCliAdapter(codex_home=app_settings.codex_home, state_dir=app_settings.data_dir)
    account_pool = AccountPoolService(accounts_store, openclaw, codex)
    probe_service = ProbeService(app_settings, account_pool)
    switch_service = SwitchService(account_pool)
    login_manager = LoginSessionManager(
        importers={
            "openclaw": account_pool.import_openclaw_current,
            "codex": account_pool.import_codex_current,
        },
        store=login_store,
    )
    scheduler = SchedulerEngine(
        settings_store=settings_store,
        account_pool=account_pool,
        switch_service=switch_service,
        probe_service=probe_service,
        event_log=event_log,
        openclaw_adapter=openclaw,
    )
    scheduler_runner = SchedulerRunner(settings_store=settings_store, engine=scheduler)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """在应用启动时挂载调度器对象。"""

        app.state.scheduler = scheduler
        app.state.scheduler_runner = scheduler_runner
        await scheduler_runner.start()
        try:
            yield
        finally:
            await scheduler_runner.stop()

    app = FastAPI(title="codex-multi-account", lifespan=lifespan)
    app.include_router(build_overview_router(account_pool, event_log, scheduler_runner))
    app.include_router(build_accounts_router(account_pool, probe_service, switch_service, login_manager))
    app.include_router(build_settings_router(settings_store, codex))
    app.include_router(build_events_router(event_log))
    app.include_router(build_scheduler_router(scheduler, scheduler_runner))
    _register_frontend_routes(app, app_settings.project_root)
    return app
