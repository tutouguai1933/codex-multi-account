# Codex Multi Account Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web service and browser UI that manages a shared account pool for OpenClaw and Codex CLI, with status detection, manual switching, scheduled refresh, and auto-switching that prefers account separation across the two clients.

**Architecture:** Keep all runtime mutation and scheduling logic in a Python backend so the proven OpenClaw script can be refactored into reusable modules. Expose a local HTTP API consumed by a React UI that focuses on dashboard, account pool operations, settings, and event visibility.

**Tech Stack:** Python 3 + FastAPI + Uvicorn + Pydantic, React + TypeScript + Vite, pytest

---

## Scope

- Create a new project in `/home/djy/codex-multi-account`
- Reuse and refactor the proven OpenClaw multi-account logic
- Add first-class Codex CLI snapshot and switching support
- Provide a local API and browser UI
- Ship v1 with import, login trigger, probe, switch, disable, delete, scheduled refresh, and auto-switch

## Out Of Scope

- Desktop packaging
- Remote deployment
- Multi-user auth
- Sync across machines
- Mobile layout polish beyond basic responsive support

## Proposed File Structure

- Create: `/home/djy/codex-multi-account/backend/pyproject.toml`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/__init__.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/app.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/config.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/models/account.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/models/settings.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/storage/json_store.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/storage/event_log.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/adapters/openclaw.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/adapters/codex_cli.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/services/account_pool.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/services/probe_service.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/services/switch_service.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/scheduler/engine.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_overview.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_accounts.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_settings.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_events.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_openclaw_adapter.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_codex_cli_adapter.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_scheduler_engine.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_api_accounts.py`
- Create: `/home/djy/codex-multi-account/web/package.json`
- Create: `/home/djy/codex-multi-account/web/src/main.tsx`
- Create: `/home/djy/codex-multi-account/web/src/app/App.tsx`
- Create: `/home/djy/codex-multi-account/web/src/pages/DashboardPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/pages/AccountsPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/pages/SettingsPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/pages/EventsPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/AccountTable.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/StatusCard.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/QuotaBar.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/EventList.tsx`
- Create: `/home/djy/codex-multi-account/web/src/lib/api.ts`
- Create: `/home/djy/codex-multi-account/web/src/lib/types.ts`
- Create: `/home/djy/codex-multi-account/web/src/styles.css`
- Create: `/home/djy/codex-multi-account/docs/runbook.md`
- Create: `/home/djy/codex-multi-account/data/.gitkeep`

### Task 1: Scaffold backend package

**Files:**
- Create: `/home/djy/codex-multi-account/backend/pyproject.toml`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/__init__.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/app.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/config.py`

- [ ] **Step 1: Write the failing backend smoke test**

```python
from fastapi.testclient import TestClient

from codex_multi_account.app import create_app


def test_health_route_returns_ok():
    client = TestClient(create_app())
    response = client.get("/api/overview")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_api_accounts.py -k health_route_returns_ok -v`
Expected: FAIL because package or app factory does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="codex-multi-account")

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_api_accounts.py -k health_route_returns_ok -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/src/codex_multi_account backend/tests/test_api_accounts.py
git commit -m "feat: scaffold backend service"
```

### Task 2: Extract OpenClaw adapter from the proven script

**Files:**
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/adapters/openclaw.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_openclaw_adapter.py`
- Reference: `/home/djy/.openclaw/workspace-taizi/skills/openclaw-openai-multi-account/scripts/openclaw-openai-accounts.py`

- [ ] **Step 1: Write the failing adapter test for active profile detection**

```python
def test_openclaw_adapter_reads_live_default_profile(tmp_path):
    adapter = OpenClawAdapter(openclaw_home=tmp_path)
    adapter.write_fixture_default_profile(email="beta@example.com")
    snapshot = adapter.read_runtime_snapshot()
    assert snapshot.active_email == "beta@example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_openclaw_adapter.py -k live_default_profile -v`
Expected: FAIL because `OpenClawAdapter` is missing

- [ ] **Step 3: Implement minimal adapter methods**

```python
class OpenClawAdapter:
    def __init__(self, openclaw_home: Path) -> None:
        self.openclaw_home = openclaw_home

    def read_runtime_snapshot(self) -> RuntimeSnapshot:
        # Read ~/.openclaw/openclaw.json and auth-profiles.json,
        # resolve openai-codex:default, and normalize active email/account info.
        auth_store = self._load_primary_auth_store()
        profile = auth_store["profiles"]["openai-codex:default"]
        identity = self._identity_from_profile(profile)
        return RuntimeSnapshot(
            target="openclaw",
            active_email=identity.email,
            active_account_id=identity.account_id,
            raw_profile=profile,
        )
```

- [ ] **Step 4: Port regression coverage from the existing script**

```python
def test_openclaw_switch_preserves_usage_metadata():
    before = adapter.read_auth_store("main")
    adapter.activate_snapshot("account1")
    after = adapter.read_auth_store("main")
    assert after["usageStats"] == before["usageStats"]


def test_openclaw_reconciles_aliases_and_order():
    adapter.reconcile_saved_accounts()
    config = adapter.read_openclaw_config()
    assert config["auth"]["order"]["openai-codex"][0] == "openai-codex:default"
```

- [ ] **Step 5: Run adapter tests**

Run: `python3 -m pytest backend/tests/test_openclaw_adapter.py -v`
Expected: PASS with coverage for detection, reconcile, snapshot, switch

- [ ] **Step 6: Commit**

```bash
git add backend/src/codex_multi_account/adapters/openclaw.py backend/tests/test_openclaw_adapter.py
git commit -m "feat: extract openclaw runtime adapter"
```

### Task 3: Add Codex CLI snapshot, import, and switch adapter

**Files:**
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/adapters/codex_cli.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_codex_cli_adapter.py`

- [ ] **Step 1: Write the failing test for reading the active Codex auth**

```python
def test_codex_adapter_reads_auth_json(tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text('{"auth_mode":"oauth","tokens":{"id_token":"abc"}}')
    adapter = CodexCliAdapter(codex_home=tmp_path / ".codex")
    snapshot = adapter.read_runtime_snapshot()
    assert snapshot.auth_mode == "oauth"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_codex_cli_adapter.py -k reads_auth_json -v`
Expected: FAIL because `CodexCliAdapter` is missing

- [ ] **Step 3: Implement import/snapshot/switch methods**

```python
class CodexCliAdapter:
    def read_runtime_snapshot(self) -> RuntimeSnapshot:
        payload = json.loads((self.codex_home / "auth.json").read_text())
        return RuntimeSnapshot(
            target="codex",
            auth_mode=payload.get("auth_mode"),
            raw_profile=payload,
        )

    def capture_current(self, snapshot_id: str) -> SnapshotRecord:
        payload = json.loads((self.codex_home / "auth.json").read_text())
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.json"
        snapshot_path.write_text(json.dumps(payload, indent=2))
        return SnapshotRecord(snapshot_id=snapshot_id, path=snapshot_path)

    def activate_snapshot(self, snapshot_id: str) -> RuntimeSnapshot:
        payload = json.loads((self.snapshot_dir / f"{snapshot_id}.json").read_text())
        self._atomic_write_auth(payload)
        return RuntimeSnapshot(target="codex", auth_mode=payload.get("auth_mode"), raw_profile=payload)
```

- [ ] **Step 4: Add tests for safe write and delete**

```python
def test_codex_adapter_switch_rewrites_auth_atomically():
    adapter.capture_current("account1")
    adapter.activate_snapshot("account1")
    assert json.loads((adapter.codex_home / "auth.json").read_text())["auth_mode"] == "oauth"


def test_codex_adapter_delete_snapshot_removes_local_copy_only():
    adapter.capture_current("account1")
    adapter.delete_snapshot("account1")
    assert not (adapter.snapshot_dir / "account1.json").exists()
    assert (adapter.codex_home / "auth.json").exists()
```

- [ ] **Step 5: Run Codex adapter tests**

Run: `python3 -m pytest backend/tests/test_codex_cli_adapter.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/codex_multi_account/adapters/codex_cli.py backend/tests/test_codex_cli_adapter.py
git commit -m "feat: add codex cli adapter"
```

### Task 4: Define shared models and JSON storage

**Files:**
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/models/account.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/models/settings.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/storage/json_store.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/storage/event_log.py`

- [ ] **Step 1: Write the failing test for persisting account pool records**

```python
def test_json_store_round_trips_accounts(tmp_path):
    store = JsonStore(tmp_path / "accounts.json")
    store.write({"accounts": [{"id": "acct_1", "label": "work"}]})
    assert store.read()["accounts"][0]["id"] == "acct_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_api_accounts.py -k round_trips_accounts -v`
Expected: FAIL because `JsonStore` is missing

- [ ] **Step 3: Implement storage and core models**

```python
class AccountRecord(BaseModel):
    id: str
    label: str
    email: str | None = None
    bindings: Bindings
    status: AccountStatus
    quota: AccountQuota
```

- [ ] **Step 4: Add event append coverage**

```python
def test_event_log_appends_jsonl_records(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    log.append({"type": "switch", "target": "openclaw"})
    assert tmp_path.joinpath("events.jsonl").read_text().strip().startswith("{")
```

- [ ] **Step 5: Run model/storage tests**

Run: `python3 -m pytest backend/tests/test_api_accounts.py -k "round_trips_accounts or event_log_appends" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/codex_multi_account/models backend/src/codex_multi_account/storage backend/tests/test_api_accounts.py
git commit -m "feat: add shared models and json storage"
```

### Task 5: Implement account pool service

**Files:**
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/services/account_pool.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/adapters/openclaw.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/adapters/codex_cli.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_account_pool.py`

- [ ] **Step 1: Write the failing tests for import and delete**

```python
def test_account_pool_imports_current_openclaw_runtime():
    record = service.import_openclaw_current(label="work-main")
    assert record.bindings.openclaw.snapshot_id is not None


def test_account_pool_deletes_snapshot_bindings():
    service.delete_account("acct_1")
    assert service.get_account("acct_1") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_account_pool.py -v`
Expected: FAIL because `AccountPoolService` is missing

- [ ] **Step 3: Implement the service**

```python
class AccountPoolService:
    def import_openclaw_current(self, label: str | None = None) -> AccountRecord:
        snapshot = self.openclaw.capture_current(label or "openclaw-current")
        return self._upsert_binding(snapshot=snapshot, target="openclaw", label=label)

    def import_codex_current(self, label: str | None = None) -> AccountRecord:
        snapshot = self.codex.capture_current(label or "codex-current")
        return self._upsert_binding(snapshot=snapshot, target="codex", label=label)

    def delete_account(self, account_id: str) -> None:
        account = self.require_account(account_id)
        self._delete_bound_snapshots(account)
        self.store.remove(account_id)
```

- [ ] **Step 4: Add disable/enable behavior coverage**

```python
def test_account_pool_can_disable_and_enable_account():
    service.disable_account("acct_1")
    assert service.require_account("acct_1").status.manual_disabled is True
```

- [ ] **Step 5: Run account pool tests**

Run: `python3 -m pytest backend/tests/test_account_pool.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/codex_multi_account/services/account_pool.py backend/tests/test_account_pool.py
git commit -m "feat: add unified account pool"
```

### Task 6: Implement probe and switch services

**Files:**
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/services/probe_service.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/services/switch_service.py`
- Modify: `/home/djy/codex-multi-account/backend/tests/test_openclaw_adapter.py`
- Modify: `/home/djy/codex-multi-account/backend/tests/test_codex_cli_adapter.py`

- [ ] **Step 1: Write the failing tests for targeted switching**

```python
def test_switch_service_can_assign_openclaw_only():
    result = service.switch_target("acct_1", "openclaw")
    assert result["target"] == "openclaw"


def test_switch_service_can_assign_codex_only():
    result = service.switch_target("acct_1", "codex")
    assert result["target"] == "codex"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_openclaw_adapter.py backend/tests/test_codex_cli_adapter.py -k assign -v`
Expected: FAIL because switch orchestration is missing

- [ ] **Step 3: Implement probe and targeted switch logic**

```python
class SwitchService:
    def switch_target(self, account_id: str, target: Literal["openclaw", "codex", "both"]) -> dict[str, Any]:
        account = self.account_pool.require_account(account_id)
        if target in {"openclaw", "both"}:
            self.openclaw.activate_snapshot(account.bindings.openclaw.snapshot_id)
        if target in {"codex", "both"}:
            self.codex.activate_snapshot(account.bindings.codex.snapshot_id)
        return {"accountId": account_id, "target": target, "status": "ok"}
```

- [ ] **Step 4: Add deletion guard coverage**

```python
def test_switch_service_refuses_deleted_or_disabled_accounts():
    service.disable_account("acct_1")
    with pytest.raises(AccountUnavailableError):
        service.switch_target("acct_1", "both")
```

- [ ] **Step 5: Run service tests**

Run: `python3 -m pytest backend/tests/test_openclaw_adapter.py backend/tests/test_codex_cli_adapter.py backend/tests/test_account_pool.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/codex_multi_account/services/probe_service.py backend/src/codex_multi_account/services/switch_service.py backend/tests
git commit -m "feat: add probe and switch services"
```

### Task 7: Implement scheduler with separation-first policy

**Files:**
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/scheduler/engine.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_scheduler_engine.py`

- [ ] **Step 1: Write the failing scheduler tests**

```python
def test_scheduler_prefers_different_accounts_for_openclaw_and_codex():
    result = engine.run_once()
    assert result.assignments["openclaw"] != result.assignments["codex"]


def test_scheduler_allows_same_account_when_no_other_candidate_exists():
    result = engine.run_once()
    assert result.reason == "same-account-fallback"


def test_scheduler_blocks_soft_switch_when_openclaw_sessions_are_active():
    result = engine.run_once()
    assert result.actions["openclaw"] == "blocked-active-session"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_scheduler_engine.py -v`
Expected: FAIL because scheduler engine does not exist

- [ ] **Step 3: Implement ranking and execution**

```python
class SchedulerEngine:
    def run_once(self) -> SchedulerResult:
        # 1. refresh health/quota
        # 2. rank candidates per target
        # 3. prefer separation
        # 4. allow same-account fallback
        # 5. log reasons
        openclaw_choice = self._pick_target("openclaw")
        codex_choice = self._pick_target("codex", avoid_account_id=openclaw_choice.account_id)
        if codex_choice is None:
            codex_choice = self._pick_target("codex")
        return self._apply_choices(openclaw_choice, codex_choice)
```

- [ ] **Step 4: Add cooldown and hard-threshold coverage**

```python
def test_scheduler_forces_immediate_switch_at_hard_threshold():
    result = engine.run_once()
    assert result.forced_immediate is True


def test_scheduler_logs_block_reason_when_switch_is_skipped():
    result = engine.run_once()
    assert "blocked" in result.events[-1].reason
```

- [ ] **Step 5: Run scheduler tests**

Run: `python3 -m pytest backend/tests/test_scheduler_engine.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/codex_multi_account/scheduler/engine.py backend/tests/test_scheduler_engine.py
git commit -m "feat: add separation-first scheduler"
```

### Task 8: Add API routes for overview, accounts, settings, and events

**Files:**
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_overview.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_accounts.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_settings.py`
- Create: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_events.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/app.py`
- Create: `/home/djy/codex-multi-account/backend/tests/test_api_accounts.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_accounts_route_lists_unified_accounts():
    response = client.get("/api/accounts")
    assert response.status_code == 200


def test_switch_route_accepts_target_parameter():
    response = client.post("/api/accounts/acct_1/switch", json={"target": "openclaw"})
    assert response.status_code == 200


def test_delete_route_removes_account():
    response = client.delete("/api/accounts/acct_1")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_api_accounts.py -v`
Expected: FAIL because routes are missing

- [ ] **Step 3: Implement routes**

```python
router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("")
def list_accounts() -> dict[str, list[dict[str, Any]]]:
    return {"accounts": [account.model_dump(mode="json") for account in account_pool.list_accounts()]}


@router.post("/{account_id}/switch")
def switch_account(account_id: str, payload: SwitchRequest) -> dict[str, Any]:
    return switch_service.switch_target(account_id=account_id, target=payload.target)
```

- [ ] **Step 4: Add validation tests for disable/enable/probe**

```python
def test_probe_route_returns_health_payload():
    response = client.post("/api/accounts/acct_1/probe")
    assert response.json()["status"]["health"] in {"healthy", "quota-unknown"}


def test_disable_route_marks_account_unavailable():
    response = client.post("/api/accounts/acct_1/disable")
    assert response.status_code == 200
```

- [ ] **Step 5: Run backend API suite**

Run: `python3 -m pytest backend/tests -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/codex_multi_account/api backend/src/codex_multi_account/app.py backend/tests/test_api_accounts.py
git commit -m "feat: add backend api routes"
```

### Task 9: Scaffold frontend app and dashboard shell

**Files:**
- Create: `/home/djy/codex-multi-account/web/package.json`
- Create: `/home/djy/codex-multi-account/web/src/main.tsx`
- Create: `/home/djy/codex-multi-account/web/src/app/App.tsx`
- Create: `/home/djy/codex-multi-account/web/src/pages/DashboardPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/StatusCard.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/QuotaBar.tsx`
- Create: `/home/djy/codex-multi-account/web/src/lib/api.ts`
- Create: `/home/djy/codex-multi-account/web/src/lib/types.ts`
- Create: `/home/djy/codex-multi-account/web/src/styles.css`

- [ ] **Step 1: Write the failing UI smoke test or lintable render target**

```tsx
it("renders dashboard heading", () => {
  render(<DashboardPage />);
  expect(screen.getByText("Account Control Plane")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test or build to verify it fails**

Run: `pnpm --dir web test`
Expected: FAIL because frontend app is missing

- [ ] **Step 3: Implement dashboard shell**

```tsx
export function DashboardPage() {
  return (
    <section>
      <h1>Account Control Plane</h1>
      <div className="status-grid">{/* OpenClaw / Codex cards */}</div>
    </section>
  );
}
```

- [ ] **Step 4: Run frontend build**

Run: `pnpm --dir web build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/src
git commit -m "feat: scaffold frontend dashboard"
```

### Task 10: Build accounts page, settings page, and events page

**Files:**
- Create: `/home/djy/codex-multi-account/web/src/pages/AccountsPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/pages/SettingsPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/pages/EventsPage.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/AccountTable.tsx`
- Create: `/home/djy/codex-multi-account/web/src/components/EventList.tsx`
- Modify: `/home/djy/codex-multi-account/web/src/app/App.tsx`

- [ ] **Step 1: Write the failing UI test for account actions**

```tsx
it("shows switch, probe, disable, and delete actions for each account row", () => {
  render(<AccountsPage />);
  expect(screen.getByRole("button", { name: /switch openclaw/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir web test`
Expected: FAIL because accounts page and table are missing

- [ ] **Step 3: Implement pages and components**

```tsx
export function AccountTable({ accounts }: { accounts: AccountRecord[] }) {
  return <table>{/* rows with status, quota, actions */}</table>;
}
```

- [ ] **Step 4: Wire settings and events**

```tsx
export function SettingsPage() {
  return <form>{/* thresholds, refresh interval, fallback */}</form>;
}
```

- [ ] **Step 5: Run frontend build**

Run: `pnpm --dir web build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat: add accounts settings and events pages"
```

### Task 11: Connect frontend actions to backend API

**Files:**
- Modify: `/home/djy/codex-multi-account/web/src/lib/api.ts`
- Modify: `/home/djy/codex-multi-account/web/src/pages/DashboardPage.tsx`
- Modify: `/home/djy/codex-multi-account/web/src/pages/AccountsPage.tsx`
- Modify: `/home/djy/codex-multi-account/web/src/pages/SettingsPage.tsx`
- Modify: `/home/djy/codex-multi-account/web/src/pages/EventsPage.tsx`

- [ ] **Step 1: Write the failing integration-oriented UI test**

```tsx
it("loads overview and renders current OpenClaw and Codex assignments", async () => {
  server.use(http.get("/api/overview", () => HttpResponse.json(mockOverview)));
  render(<DashboardPage />);
  expect(await screen.findByText("OpenClaw")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir web test`
Expected: FAIL because API layer is not wired

- [ ] **Step 3: Implement client calls and page loading states**

```tsx
export async function getOverview(): Promise<OverviewResponse> {
  const response = await fetch("/api/overview");
  return response.json();
}
```

- [ ] **Step 4: Add mutation flows**

```tsx
await switchAccount(accountId, { target: "openclaw" });
await probeAccount(accountId);
await deleteAccount(accountId);
```

- [ ] **Step 5: Run frontend build and tests**

Run: `pnpm --dir web test && pnpm --dir web build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat: wire frontend to backend api"
```

### Task 12: Add scheduler loop, runbook, and end-to-end verification

**Files:**
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/app.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/scheduler/engine.py`
- Create: `/home/djy/codex-multi-account/docs/runbook.md`

- [ ] **Step 1: Write the failing test for scheduled refresh bootstrapping**

```python
def test_app_starts_scheduler_when_enabled():
    app = create_app()
    assert app.state.scheduler is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_api_accounts.py -k scheduler -v`
Expected: FAIL because startup wiring is missing

- [ ] **Step 3: Implement startup wiring and operator docs**

```python
@app.on_event("startup")
async def startup() -> None:
    app.state.scheduler = SchedulerEngine(
        settings_store=settings_store,
        account_pool=account_pool,
        switch_service=switch_service,
        probe_service=probe_service,
        event_log=event_log,
    )
```

- [ ] **Step 4: Run full verification**

Run: `python3 -m pytest backend/tests -v`
Expected: PASS

Run: `pnpm --dir web build`
Expected: PASS

Run: `python3 -m uvicorn codex_multi_account.app:create_app --factory --host 127.0.0.1 --port 8080`
Expected: local service starts without traceback

- [ ] **Step 5: Commit**

```bash
git add backend/src/codex_multi_account/app.py backend/src/codex_multi_account/scheduler/engine.py docs/runbook.md
git commit -m "feat: add scheduler startup and runbook"
```

## Validation Commands

These are the commands expected during implementation. Commands that require dependency installation must be user-run first because the current repo rules forbid automatic install/restore/update steps.

- User-run before implementation:

```bash
python3 -m pip install -e backend
```

Expected: backend package and test dependencies become available

- User-run before frontend work:

```bash
pnpm --dir web install
```

Expected: frontend dependencies are installed

- Backend tests:

```bash
python3 -m pytest backend/tests -v
```

Expected: all backend tests pass

- Frontend tests:

```bash
pnpm --dir web test
```

Expected: frontend tests pass

- Frontend build:

```bash
pnpm --dir web build
```

Expected: production bundle builds without errors

- Local backend smoke run:

```bash
python3 -m uvicorn codex_multi_account.app:create_app --factory --host 127.0.0.1 --port 8080
```

Expected: service starts and `/api/overview` returns JSON

## Self-Review

- Spec coverage: plan covers unified pool, OpenClaw reuse, Codex adapter, API, UI, scheduler, settings, events, and validation.
- Placeholder scan: no `TODO` or `TBD` placeholders remain in tasks.
- Type consistency: backend package root is consistently `codex_multi_account`, scheduler target names are consistently `openclaw`, `codex`, `both`.
