"""这个文件验证统一账号池的导入、删除和启停行为。"""

from __future__ import annotations

import json

from codex_multi_account.adapters.codex_cli import CodexCliAdapter
from codex_multi_account.adapters.openclaw import OpenClawAdapter
from codex_multi_account.services.account_pool import AccountPoolService
from codex_multi_account.storage.json_store import JsonStore
from conftest import make_jwt


def write_json(path, data) -> None:
    """写测试 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_account_pool_imports_current_openclaw_runtime(tmp_path) -> None:
    """导入当前 OpenClaw 登录态后应生成账号。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    profile = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": make_jwt("work@example.com", "acct-work", "user-work"),
        "refresh": "refresh-work",
        "accountId": "acct-work",
    }
    write_json(
        openclaw_home / "agents" / "main" / "agent" / "auth-profiles.json",
        {"version": 1, "profiles": {"openai-codex:default": profile}},
    )
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )
    account = service.import_openclaw_current(label="work-main")
    assert account.email == "work@example.com"
    assert account.bindings.openclaw.snapshot_id == "work-main"


def test_account_pool_deletes_snapshot_bindings(tmp_path) -> None:
    """删除账号应移除快照和账号记录。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    profile = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": make_jwt("work@example.com", "acct-work", "user-work"),
        "refresh": "refresh-work",
        "accountId": "acct-work",
    }
    write_json(
        openclaw_home / "agents" / "main" / "agent" / "auth-profiles.json",
        {"version": 1, "profiles": {"openai-codex:default": profile}},
    )
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )
    account = service.import_openclaw_current(label="work-main")
    service.delete_account(account.id)
    assert service.get_account(account.id) is None
    assert not (state_dir / "snapshots" / "openclaw" / "work-main.json").exists()


def test_account_pool_can_disable_and_enable_account(tmp_path) -> None:
    """账号应能被禁用和重新启用。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    profile = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": make_jwt("work@example.com", "acct-work", "user-work"),
        "refresh": "refresh-work",
        "accountId": "acct-work",
    }
    write_json(
        openclaw_home / "agents" / "main" / "agent" / "auth-profiles.json",
        {"version": 1, "profiles": {"openai-codex:default": profile}},
    )
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )
    account = service.import_openclaw_current(label="work-main")
    disabled = service.disable_account(account.id)
    enabled = service.enable_account(account.id)
    assert disabled.status.manual_disabled is True
    assert enabled.status.manual_disabled is False


def test_account_pool_imports_codex_batch_into_both_targets(tmp_path) -> None:
    """批量导入 Codex JSON 后，应同时生成 Codex 和 OpenClaw 绑定。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )

    imported = service.import_codex_batch(
        [
            {
                "id": "codex_demo_1",
                "email": "demo@example.com",
                "auth_mode": "oauth",
                "user_id": "user-demo",
                "plan_type": "team",
                "account_id": "acct-demo",
                "tokens": {
                    "id_token": make_jwt("demo@example.com", "acct-demo", "user-demo"),
                    "access_token": make_jwt("demo@example.com", "acct-demo", "user-demo"),
                    "refresh_token": "refresh-demo",
                },
                "quota": {
                    "hourly_percentage": 88,
                    "weekly_percentage": 77,
                },
                "usage_updated_at": 100,
                "created_at": 90,
                "last_used": 95,
            }
        ]
    )

    assert len(imported) == 1
    account = imported[0]
    assert account.email == "demo@example.com"
    assert account.bindings.codex.snapshot_id is not None
    assert account.bindings.openclaw.snapshot_id is not None
    codex_snapshot = service.codex.read_snapshot(account.bindings.codex.snapshot_id or "")
    openclaw_snapshot = service.openclaw.read_snapshot(account.bindings.openclaw.snapshot_id or "")
    assert codex_snapshot.active_email == "demo@example.com"
    assert openclaw_snapshot.active_email == "demo@example.com"
    assert account.metadata["codex_export"]["account_id"] == "acct-demo"
    snapshot_payload = json.loads(
        (
            state_dir
            / "snapshots"
            / "codex"
            / f"{account.bindings.codex.snapshot_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert snapshot_payload["auth_mode"] == "chatgpt"
    assert snapshot_payload["OPENAI_API_KEY"] is None


def test_account_pool_does_not_merge_same_email_with_different_account_id(tmp_path) -> None:
    """同邮箱不同 workspace/account_id 的条目不应误合并。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )

    imported = service.import_codex_batch(
        [
            {
                "id": "codex_demo_1",
                "email": "same@example.com",
                "auth_mode": "oauth",
                "user_id": "user-a",
                "plan_type": "team",
                "account_id": "acct-a",
                "tokens": {
                    "id_token": make_jwt("same@example.com", "acct-a", "user-a"),
                    "access_token": make_jwt("same@example.com", "acct-a", "user-a"),
                    "refresh_token": "refresh-a",
                },
            },
            {
                "id": "codex_demo_2",
                "email": "same@example.com",
                "auth_mode": "oauth",
                "user_id": "user-b",
                "plan_type": "team",
                "account_id": "acct-b",
                "tokens": {
                    "id_token": make_jwt("same@example.com", "acct-b", "user-b"),
                    "access_token": make_jwt("same@example.com", "acct-b", "user-b"),
                    "refresh_token": "refresh-b",
                },
            },
        ]
    )

    assert len(imported) == 2
    assert len(service.list_accounts()) == 2


def test_account_pool_exports_cockpit_compatible_codex_json(tmp_path) -> None:
    """导出结果应兼容 cockpit-tools 的关键字段。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )
    imported = service.import_codex_batch(
        [
            {
                "id": "codex_demo_1",
                "email": "export@example.com",
                "auth_mode": "oauth",
                "user_id": "user-export",
                "plan_type": "team",
                "account_id": "acct-export",
                "account_name": "Workspace",
                "account_structure": "workspace",
                "tokens": {
                    "id_token": make_jwt("export@example.com", "acct-export", "user-export"),
                    "access_token": make_jwt("export@example.com", "acct-export", "user-export"),
                    "refresh_token": "refresh-export",
                },
                "quota": {
                    "hourly_percentage": 71,
                    "weekly_percentage": 50,
                },
                "usage_updated_at": 101,
                "created_at": 91,
                "last_used": 96,
            }
        ]
    )
    account = imported[0]
    account.quota.five_hour_used_pct = 29.0
    account.quota.weekly_used_pct = 50.0
    account.quota.reset_at_five_hour = 300
    account.quota.reset_at_weekly = 600
    service.update_account(account)

    exported = service.export_codex_batch()

    assert len(exported) == 1
    item = exported[0]
    assert item["email"] == "export@example.com"
    assert item["account_id"] == "acct-export"


def test_account_pool_create_api_account_uses_base_url_as_label(tmp_path) -> None:
    """第三方 API 账号默认应直接用基础地址做名称。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )

    account = service.create_api_account(
        {
            "base_url": "https://www.ananapi.com/",
            "api_key": "sk-demo",
        }
    )

    assert account.label == "https://www.ananapi.com"
    assert account.api_profile is not None
    assert account.api_profile.provider_name == "openai"


def test_account_pool_can_create_unified_api_account(tmp_path) -> None:
    """第三方 API 账号应作为统一账号进入两侧绑定。"""

    openclaw_home = tmp_path / ".openclaw"
    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    service = AccountPoolService(
        JsonStore(state_dir / "accounts.json"),
        OpenClawAdapter(openclaw_home, state_dir, "main"),
        CodexCliAdapter(codex_home, state_dir),
    )

    account = service.create_api_account(
        {
            "label": "ananapi",
            "provider_name": "OpenAI",
            "base_url": "https://www.ananapi.com/",
            "wire_api": "responses",
            "requires_openai_auth": True,
            "api_key": "sk-demo",
            "model": "gpt-5.4",
            "review_model": "gpt-5.4",
            "model_reasoning_effort": "xhigh",
            "disable_response_storage": True,
            "network_access": "enabled",
            "windows_wsl_setup_acknowledged": True,
            "model_context_window": 1_000_000,
            "model_auto_compact_token_limit": 900_000,
        }
    )

    assert account.kind == "api"
    assert account.api_profile is not None
    assert account.bindings.codex.snapshot_id is not None
    assert account.bindings.openclaw.snapshot_id is not None
    assert account.api_profile.fingerprint is not None
    codex_snapshot = service.codex.read_snapshot(account.bindings.codex.snapshot_id or "")
    openclaw_snapshot = service.openclaw.read_snapshot(account.bindings.openclaw.snapshot_id or "")
    assert codex_snapshot.auth_mode == "apikey"
    assert codex_snapshot.active_account_id == account.api_profile.fingerprint
    assert openclaw_snapshot.auth_mode == "apikey"
    assert openclaw_snapshot.active_account_id == account.api_profile.fingerprint
