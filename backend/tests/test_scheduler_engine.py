"""这个文件验证调度器的分流和阻塞策略。"""

from __future__ import annotations

from codex_multi_account.models.account import (
    AccountBindings,
    AccountQuota,
    AccountRecord,
    RuntimeSnapshot,
    AccountStatus,
    TargetBinding,
)
from codex_multi_account.models.settings import SchedulerSettings
from codex_multi_account.scheduler.engine import SchedulerEngine
from codex_multi_account.storage.event_log import EventLog
from codex_multi_account.storage.json_store import JsonStore


class FakeAccountPool:
    """用内存列表模拟账号池。"""

    def __init__(self, accounts: list[AccountRecord]) -> None:
        self.accounts = accounts
        self.openclaw = FakeOpenClawAdapter()
        self.codex = FakeCodexAdapter()

    def list_accounts(self) -> list[AccountRecord]:
        return self.accounts

    def assign_target(self, target: str, account_id: str | None) -> None:
        for item in self.accounts:
            if target == "openclaw":
                item.assignment.openclaw = item.id == account_id
            else:
                item.assignment.codex = item.id == account_id

    def resolve_account_for_runtime(self, runtime: RuntimeSnapshot) -> AccountRecord | None:
        for item in self.accounts:
            identity = item.metadata.get("identity") if isinstance(item.metadata, dict) else None
            identity = identity if isinstance(identity, dict) else {}
            same_account_id = bool(runtime.active_account_id) and identity.get("account_id") == runtime.active_account_id
            same_user_id = bool(runtime.user_id) and identity.get("user_id") == runtime.user_id
            same_email = bool(runtime.active_email) and item.email == runtime.active_email
            if same_account_id and same_user_id:
                return item
            if same_account_id and same_email:
                return item
            if (
                runtime.active_account_id is None
                and runtime.user_id is None
                and same_email
            ):
                return item
        return None


class FakeProbeService:
    """测试里直接返回现有账号。"""

    def __init__(self, pool: FakeAccountPool) -> None:
        self.pool = pool

    def probe_all(self) -> list[AccountRecord]:
        return self.pool.list_accounts()


class FakeSwitchService:
    """记录被调度的切换动作。"""

    def __init__(self, pool: FakeAccountPool) -> None:
        self.pool = pool
        self.calls: list[tuple[str, str]] = []

    def switch_target(self, account_id: str, target: str) -> dict[str, str]:
        self.calls.append((account_id, target))
        self.pool.assign_target(target, account_id)
        return {"accountId": account_id, "target": target}


class FakeOpenClawAdapter:
    """测试里只返回活跃会话列表。"""

    def __init__(self, sessions: list[dict[str, object]] | None = None) -> None:
        self.sessions = sessions or []
        self.runtime = RuntimeSnapshot(target="openclaw", raw_profile={}, has_binding=False)

    def list_recent_active_sessions(self, active_minutes: float) -> list[dict[str, object]]:
        return self.sessions

    def read_runtime_snapshot(self) -> RuntimeSnapshot:
        return self.runtime


class FakeCodexAdapter:
    """测试里提供当前 Codex 真实运行态。"""

    def __init__(self) -> None:
        self.runtime = RuntimeSnapshot(target="codex", raw_profile={}, has_binding=False)

    def read_runtime_snapshot(self) -> RuntimeSnapshot:
        return self.runtime


def sync_runtime_from_assignments(pool: FakeAccountPool) -> None:
    """把测试里的 assignment 同步成当前真实运行态。"""

    openclaw_current = next((item for item in pool.accounts if item.assignment.openclaw), None)
    codex_current = next((item for item in pool.accounts if item.assignment.codex), None)
    if openclaw_current is not None:
        pool.openclaw.runtime = RuntimeSnapshot(
            target="openclaw",
            active_email=openclaw_current.email,
            active_account_id=(openclaw_current.metadata.get("identity") or {}).get("account_id")
            if isinstance(openclaw_current.metadata, dict)
            else None,
            user_id=(openclaw_current.metadata.get("identity") or {}).get("user_id")
            if isinstance(openclaw_current.metadata, dict)
            else None,
            has_binding=True,
            raw_profile={},
        )
    if codex_current is not None:
        pool.codex.runtime = RuntimeSnapshot(
            target="codex",
            active_email=codex_current.email,
            active_account_id=(codex_current.metadata.get("identity") or {}).get("account_id")
            if isinstance(codex_current.metadata, dict)
            else None,
            user_id=(codex_current.metadata.get("identity") or {}).get("user_id")
            if isinstance(codex_current.metadata, dict)
            else None,
            has_binding=True,
            raw_profile={},
        )


def make_account(
    account_id: str,
    *,
    openclaw: bool,
    codex: bool,
    five: float,
    weekly: float,
    disabled: bool = False,
    email: str | None = None,
    runtime_account_id: str | None = None,
    user_id: str | None = None,
) -> AccountRecord:
    """构造测试账号。"""

    return AccountRecord(
        id=account_id,
        label=account_id,
        email=email or f"{account_id}@example.com",
        bindings=AccountBindings(
            openclaw=TargetBinding(snapshot_id=f"{account_id}-oc" if openclaw else None, available=openclaw),
            codex=TargetBinding(snapshot_id=f"{account_id}-cx" if codex else None, available=codex),
        ),
        status=AccountStatus(
            health="manual-disabled" if disabled else "healthy",
            reason="test",
            manual_disabled=disabled,
        ),
        quota=AccountQuota(five_hour_used_pct=five, weekly_used_pct=weekly),
        metadata={
            "identity": {
                "account_id": runtime_account_id,
                "user_id": user_id,
            }
        },
    )


def test_scheduler_prefers_different_accounts_for_openclaw_and_codex(tmp_path) -> None:
    """有可选账号时应优先分流。"""

    accounts = [
        make_account("acct_1", openclaw=True, codex=True, five=10.0, weekly=10.0),
        make_account("acct_2", openclaw=True, codex=True, five=11.0, weekly=11.0),
    ]
    pool = FakeAccountPool(accounts)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=FakeSwitchService(pool),  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter(),  # type: ignore[arg-type]
    )
    result = engine.run_once()
    assert result.assignments["openclaw"] != result.assignments["codex"]


def test_scheduler_allows_same_account_when_no_other_candidate_exists(tmp_path) -> None:
    """没有第二个候选账号时允许共用。"""

    accounts = [make_account("acct_1", openclaw=True, codex=True, five=10.0, weekly=10.0)]
    pool = FakeAccountPool(accounts)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=FakeSwitchService(pool),  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter(),  # type: ignore[arg-type]
    )
    result = engine.run_once()
    assert result.reason == "same-account-fallback"


def test_scheduler_blocks_soft_switch_when_openclaw_sessions_are_active(tmp_path) -> None:
    """软阈值下有活跃会话时应阻塞 OpenClaw 切换。"""

    current = make_account("acct_1", openclaw=True, codex=True, five=85.0, weekly=20.0)
    current.assignment.openclaw = True
    other = make_account("acct_2", openclaw=True, codex=True, five=10.0, weekly=10.0)
    pool = FakeAccountPool([current, other])
    sync_runtime_from_assignments(pool)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=FakeSwitchService(pool),  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter([{"key": "session-1"}]),  # type: ignore[arg-type]
    )
    result = engine.run_once()
    assert result.actions["openclaw"] == "blocked-active-session"


def test_scheduler_blocks_weekly_soft_switch_when_openclaw_sessions_are_active(tmp_path) -> None:
    """周额度软阈值命中时，也应尊重活跃会话阻塞。"""

    current = make_account("acct_1", openclaw=True, codex=True, five=20.0, weekly=92.0)
    current.assignment.openclaw = True
    other = make_account("acct_2", openclaw=True, codex=True, five=10.0, weekly=10.0)
    pool = FakeAccountPool([current, other])
    sync_runtime_from_assignments(pool)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=FakeSwitchService(pool),  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter([{"key": "session-1"}]),  # type: ignore[arg-type]
    )
    result = engine.run_once()
    assert result.actions["openclaw"] == "blocked-active-session"


def test_scheduler_marks_keep_when_assignments_are_already_optimal(tmp_path) -> None:
    """当前分配已经符合策略时，不应把动作记成 switched。"""

    openclaw_current = make_account("acct_1", openclaw=True, codex=True, five=10.0, weekly=10.0)
    openclaw_current.assignment.openclaw = True
    codex_current = make_account("acct_2", openclaw=True, codex=True, five=11.0, weekly=11.0)
    codex_current.assignment.codex = True
    pool = FakeAccountPool([openclaw_current, codex_current])
    sync_runtime_from_assignments(pool)
    switch_service = FakeSwitchService(pool)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=switch_service,  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter(),  # type: ignore[arg-type]
    )
    result = engine.run_once()
    assert result.actions == {"openclaw": "keep", "codex": "keep"}
    assert switch_service.calls == []


def test_scheduler_records_event_when_no_openclaw_candidate_exists(tmp_path) -> None:
    """没有 OpenClaw 候选账号时，应留下明确事件。"""

    accounts = [make_account("acct_1", openclaw=False, codex=True, five=10.0, weekly=10.0)]
    pool = FakeAccountPool(accounts)
    event_log = EventLog(tmp_path / "events.jsonl")
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=FakeSwitchService(pool),  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=event_log,
        openclaw_adapter=FakeOpenClawAdapter(),  # type: ignore[arg-type]
    )
    result = engine.run_once()
    events = event_log.list_recent(limit=5)
    assert result.reason == "no-openclaw-candidate"
    assert events[0]["reason"] == "no-openclaw-candidate"


def test_scheduler_prefers_live_runtime_over_stale_assignment_for_openclaw(tmp_path) -> None:
    """OpenClaw 调度应以真实运行态为准，不应被旧 assignment 误导。"""

    stale_assigned = make_account(
        "acct_2",
        openclaw=True,
        codex=True,
        five=73.0,
        weekly=22.0,
        email="d18769999192@gmail.com",
        runtime_account_id="d47bc63d-231c-4a37-98bb-969869cf3d13",
        user_id="user-wuUgYH1qcYgkC4ulzXpdiMH7",
    )
    stale_assigned.assignment.openclaw = True
    live_current = make_account(
        "acct_6",
        openclaw=True,
        codex=True,
        five=0.0,
        weekly=30.0,
        email="d18769999192@gmail.com",
        runtime_account_id="8e091a2a-3fda-4ffa-be7c-4d2b833b8efa",
        user_id="user-wuUgYH1qcYgkC4ulzXpdiMH7",
    )
    codex_current = make_account(
        "acct_4",
        openclaw=True,
        codex=True,
        five=0.0,
        weekly=0.0,
        email="1933208939@qq.com",
        runtime_account_id="d47bc63d-231c-4a37-98bb-969869cf3d13",
        user_id="user-gWokVgpfwUQaXtCG9E7rexQd",
    )
    codex_current.assignment.codex = True

    pool = FakeAccountPool([stale_assigned, live_current, codex_current])
    pool.openclaw = FakeOpenClawAdapter()  # type: ignore[attr-defined]
    pool.codex = FakeCodexAdapter()  # type: ignore[attr-defined]
    pool.openclaw.runtime = RuntimeSnapshot(  # type: ignore[attr-defined]
        target="openclaw",
        active_email="d18769999192@gmail.com",
        active_account_id="8e091a2a-3fda-4ffa-be7c-4d2b833b8efa",
        has_binding=True,
        raw_profile={},
    )
    pool.codex.runtime = RuntimeSnapshot(  # type: ignore[attr-defined]
        target="codex",
        active_email="1933208939@qq.com",
        active_account_id="d47bc63d-231c-4a37-98bb-969869cf3d13",
        has_binding=True,
        raw_profile={},
    )
    switch_service = FakeSwitchService(pool)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=switch_service,  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=pool.openclaw,  # type: ignore[arg-type]
    )

    result = engine.run_once()

    assert result.assignments["openclaw"] == "acct_6"
    assert ("acct_2", "openclaw") not in switch_service.calls


def test_scheduler_force_rebalance_picks_better_openclaw_candidate(tmp_path) -> None:
    """手动立即调度时，应重新挑选更健康的 OpenClaw 账号。"""

    current_openclaw = make_account(
        "acct_2",
        openclaw=True,
        codex=True,
        five=73.0,
        weekly=22.0,
        email="d18769999192@gmail.com",
        runtime_account_id="d47bc63d-231c-4a37-98bb-969869cf3d13",
        user_id="user-wuUgYH1qcYgkC4ulzXpdiMH7",
    )
    current_openclaw.assignment.openclaw = True
    better_candidate = make_account(
        "acct_6",
        openclaw=True,
        codex=True,
        five=0.0,
        weekly=30.0,
        email="d18769999192@gmail.com",
        runtime_account_id="8e091a2a-3fda-4ffa-be7c-4d2b833b8efa",
        user_id="user-wuUgYH1qcYgkC4ulzXpdiMH7",
    )
    current_codex = make_account(
        "acct_4",
        openclaw=True,
        codex=True,
        five=0.0,
        weekly=0.0,
        email="1933208939@qq.com",
        runtime_account_id="d47bc63d-231c-4a37-98bb-969869cf3d13",
        user_id="user-gWokVgpfwUQaXtCG9E7rexQd",
    )
    current_codex.assignment.codex = True

    pool = FakeAccountPool([current_openclaw, better_candidate, current_codex])
    sync_runtime_from_assignments(pool)
    switch_service = FakeSwitchService(pool)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=switch_service,  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=pool.openclaw,  # type: ignore[arg-type]
    )

    result = engine.run_once(force_rebalance=True)

    assert result.assignments["openclaw"] == "acct_6"
    assert ("acct_6", "openclaw") in switch_service.calls


def test_scheduler_keeps_manual_locked_api_target(tmp_path) -> None:
    """当前目标被手动锁到 API 账号时，自动调度不应把它切走。"""

    api_account = make_account("acct_api", openclaw=True, codex=True, five=0.0, weekly=0.0)
    api_account.kind = "api"
    api_account.assignment.codex = True
    api_account.assignment.codex_locked = True
    oauth_account = make_account("acct_oauth", openclaw=True, codex=True, five=10.0, weekly=10.0)
    pool = FakeAccountPool([api_account, oauth_account])
    sync_runtime_from_assignments(pool)
    switch_service = FakeSwitchService(pool)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=switch_service,  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter(),  # type: ignore[arg-type]
    )

    result = engine.run_once()

    assert result.assignments["codex"] == "acct_api"
    assert result.actions["codex"] == "manual-locked"
    assert ("acct_oauth", "codex") not in switch_service.calls
    assert result.forced_immediate is True


def test_scheduler_skips_api_account_when_picking_candidates(tmp_path) -> None:
    """第三方 API 账号不应被自动调度主动选中。"""

    api_account = make_account("acct_api", openclaw=True, codex=True, five=1.0, weekly=1.0)
    api_account.kind = "api"
    normal_account = make_account("acct_2", openclaw=True, codex=True, five=10.0, weekly=10.0)
    pool = FakeAccountPool([api_account, normal_account])
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    switcher = FakeSwitchService(pool)
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=switcher,  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter(),  # type: ignore[arg-type]
    )

    result = engine.run_once()

    assert result.assignments["openclaw"] == "acct_2"
    assert result.assignments["codex"] == "acct_2"


def test_scheduler_keeps_manual_locked_api_target(tmp_path) -> None:
    """某个目标已手动切入 API 账号后，自动调度不应再碰它。"""

    locked_api = make_account("acct_api", openclaw=True, codex=True, five=5.0, weekly=5.0)
    locked_api.kind = "api"
    locked_api.assignment.codex = True
    locked_api.assignment.codex_locked = True
    normal_account = make_account(
        "acct_2",
        openclaw=True,
        codex=True,
        five=10.0,
        weekly=10.0,
        runtime_account_id="acct-normal",
        user_id="user-normal",
    )
    pool = FakeAccountPool([locked_api, normal_account])
    sync_runtime_from_assignments(pool)
    settings_store = JsonStore(tmp_path / "settings.json")
    settings_store.write(SchedulerSettings().model_dump(mode="json"))
    engine = SchedulerEngine(
        settings_store=settings_store,
        account_pool=pool,  # type: ignore[arg-type]
        switch_service=FakeSwitchService(pool),  # type: ignore[arg-type]
        probe_service=FakeProbeService(pool),  # type: ignore[arg-type]
        event_log=EventLog(tmp_path / "events.jsonl"),
        openclaw_adapter=FakeOpenClawAdapter(),  # type: ignore[arg-type]
    )

    result = engine.run_once()

    assert result.actions["codex"] == "manual-locked"
    assert result.assignments["codex"] == "acct_api"
