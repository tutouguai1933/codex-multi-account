"""这个文件验证后台自动刷新循环和状态记录。"""

from __future__ import annotations

import asyncio

from codex_multi_account.models.settings import SchedulerSettings
from codex_multi_account.scheduler.runner import SchedulerRunner
from codex_multi_account.storage.json_store import JsonStore


class FakeEngine:
    """用内存对象模拟调度执行结果。"""

    def __init__(self) -> None:
        self.calls = 0
        self.force_flags: list[bool] = []

    def run_once(self, force_rebalance: bool = False):
        """记录被调用次数并返回简化结果。"""

        self.calls += 1
        self.force_flags.append(force_rebalance)
        return {"reason": "auto-run", "assignments": {"openclaw": "acct_1", "codex": "acct_2"}}


class FailingEngine:
    """模拟会持续报错的调度器。"""

    def __init__(self) -> None:
        self.calls = 0

    def run_once(self, force_rebalance: bool = False):
        """每次执行都抛出错误。"""

        self.calls += 1
        raise RuntimeError("probe failed")


def test_scheduler_runner_runs_immediately_when_auto_refresh_enabled(tmp_path) -> None:
    """启用自动刷新后，启动时应立刻跑一次并记录状态。"""

    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(
        SchedulerSettings(auto_refresh_enabled=True, refresh_interval_seconds=3600).model_dump(mode="json")
    )
    engine = FakeEngine()
    runner = SchedulerRunner(settings_store=settings_store, engine=engine)

    async def scenario() -> None:
        await runner.start()
        await asyncio.sleep(0.05)
        snapshot = runner.snapshot()
        await runner.stop()
        assert engine.calls >= 1
        assert snapshot.enabled is True
        assert snapshot.running is True
        assert snapshot.last_reason == "auto-run"
        assert snapshot.last_run_at is not None

    asyncio.run(scenario())


def test_scheduler_runner_stays_idle_when_auto_refresh_disabled(tmp_path) -> None:
    """关闭自动刷新后，后台循环不应执行调度。"""

    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(
        SchedulerSettings(auto_refresh_enabled=False, refresh_interval_seconds=1).model_dump(mode="json")
    )
    engine = FakeEngine()
    runner = SchedulerRunner(settings_store=settings_store, engine=engine)

    async def scenario() -> None:
        await runner.start()
        await asyncio.sleep(0.05)
        snapshot = runner.snapshot()
        await runner.stop()
        assert engine.calls == 0
        assert snapshot.enabled is False
        assert snapshot.running is True
        assert snapshot.last_run_at is None

    asyncio.run(scenario())


def test_scheduler_runner_keeps_loop_alive_after_failure(tmp_path) -> None:
    """自动调度报错后，后台循环不应直接退出。"""

    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(
        SchedulerSettings(auto_refresh_enabled=True, refresh_interval_seconds=600).model_dump(mode="json")
    )
    engine = FailingEngine()
    runner = SchedulerRunner(settings_store=settings_store, engine=engine)

    async def scenario() -> None:
        await runner.start()
        await asyncio.sleep(0.05)
        snapshot = runner.snapshot()
        await runner.stop()
        assert engine.calls >= 1
        assert snapshot.running is True
        assert snapshot.enabled is True
        assert snapshot.last_error == "probe failed"

    asyncio.run(scenario())


def test_scheduler_runner_marks_manual_runs_as_force_rebalance(tmp_path) -> None:
    """手动立即调度时，应要求调度器重新计算最优分配。"""

    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(
        SchedulerSettings(auto_refresh_enabled=False, refresh_interval_seconds=600).model_dump(mode="json")
    )
    engine = FakeEngine()
    runner = SchedulerRunner(settings_store=settings_store, engine=engine)

    async def scenario() -> None:
        await runner.run_now(source="manual")
        assert engine.calls == 1
        assert engine.force_flags == [True]

    asyncio.run(scenario())
