"""这个文件负责让调度器在后台按设置周期运行，并记录最近状态。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any

from codex_multi_account.models.settings import SchedulerSettings
from codex_multi_account.storage.json_store import JsonStore


@dataclass(slots=True)
class SchedulerStatus:
    """描述后台调度器的当前状态。"""

    running: bool
    enabled: bool
    refresh_interval_seconds: int
    last_run_at: int | None = None
    last_reason: str | None = None
    last_error: str | None = None
    last_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转成可返回给接口的字典。"""

        return asdict(self)


class SchedulerRunner:
    """负责启动、停止和周期执行调度。"""

    def __init__(self, settings_store: JsonStore, engine: Any) -> None:
        self.settings_store = settings_store
        self.engine = engine
        settings = self._read_settings()
        self._status = SchedulerStatus(
            running=False,
            enabled=settings.auto_refresh_enabled,
            refresh_interval_seconds=settings.refresh_interval_seconds,
        )
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._run_lock = asyncio.Lock()

    def _read_settings(self) -> SchedulerSettings:
        """读取最新调度设置。"""

        payload = self.settings_store.read(default=SchedulerSettings().model_dump(mode="json"))
        return SchedulerSettings.model_validate(payload)

    async def start(self) -> None:
        """启动后台循环。"""

        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._status.running = True
        self._task = asyncio.create_task(self._run_loop(), name="codex-multi-account-scheduler")

    async def stop(self) -> None:
        """停止后台循环。"""

        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._status.running = False

    async def run_now(self, source: str = "manual") -> Any:
        """立即执行一次调度，并刷新最近状态。"""

        async with self._run_lock:
            force_rebalance = source == "manual"
            try:
                result = await asyncio.to_thread(self.engine.run_once, force_rebalance)
            except Exception as exc:
                self._status.last_run_at = int(time.time())
                self._status.last_error = str(exc)
                self._status.last_source = source
                raise
            self._status.last_run_at = int(time.time())
            self._status.last_reason = getattr(result, "reason", None)
            if self._status.last_reason is None and isinstance(result, dict):
                self._status.last_reason = result.get("reason")
            self._status.last_error = None
            self._status.last_source = source
            return result

    def snapshot(self) -> SchedulerStatus:
        """返回最新状态快照。"""

        settings = self._read_settings()
        self._status.enabled = settings.auto_refresh_enabled
        self._status.refresh_interval_seconds = settings.refresh_interval_seconds
        self._status.running = self._task is not None and not self._task.done()
        return SchedulerStatus(**self._status.to_dict())

    async def _run_loop(self) -> None:
        """按设置循环执行自动调度。"""

        next_run_at = 0.0
        while not self._stop_event.is_set():
            settings = self._read_settings()
            self._status.enabled = settings.auto_refresh_enabled
            self._status.refresh_interval_seconds = settings.refresh_interval_seconds

            if settings.auto_refresh_enabled and time.time() >= next_run_at:
                try:
                    await self.run_now(source="auto")
                except Exception:
                    next_run_at = time.time() + max(settings.refresh_interval_seconds, 1)
                    continue
                next_run_at = time.time() + max(settings.refresh_interval_seconds, 1)
                continue

            if not settings.auto_refresh_enabled:
                next_run_at = 0.0

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
