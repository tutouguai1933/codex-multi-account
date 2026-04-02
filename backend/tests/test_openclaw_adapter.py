"""这个文件验证 OpenClaw 适配器的读取、快照和切换行为。"""

from __future__ import annotations

import json

from codex_multi_account.adapters.openclaw import OpenClawAdapter
from conftest import make_jwt


def write_json(path, data) -> None:
    """写测试 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_openclaw_adapter_reads_live_default_profile(tmp_path) -> None:
    """读取默认 profile 时应拿到真实邮箱。"""

    openclaw_home = tmp_path / ".openclaw"
    state_dir = tmp_path / "data"
    adapter = OpenClawAdapter(openclaw_home=openclaw_home, state_dir=state_dir, primary_agent="main")
    profile = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": make_jwt("beta@example.com", "acct-beta", "user-beta"),
        "refresh": "refresh-beta",
        "accountId": "acct-beta",
        "expires": 2_000_000_000,
    }
    write_json(
        openclaw_home / "agents" / "main" / "agent" / "auth-profiles.json",
        {"version": 1, "profiles": {"openai-codex:default": profile}},
    )
    snapshot = adapter.read_runtime_snapshot()
    assert snapshot.active_email == "beta@example.com"
    assert snapshot.active_account_id == "acct-beta"


def test_openclaw_switch_preserves_usage_metadata_and_order(tmp_path) -> None:
    """切换快照时应保留元数据并更新配置顺序。"""

    openclaw_home = tmp_path / ".openclaw"
    state_dir = tmp_path / "data"
    adapter = OpenClawAdapter(openclaw_home=openclaw_home, state_dir=state_dir, primary_agent="main")
    alpha = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": make_jwt("alpha@example.com", "acct-alpha", "user-alpha"),
        "refresh": "refresh-alpha",
        "accountId": "acct-alpha",
        "expires": 2_000_000_000,
    }
    beta = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": make_jwt("beta@example.com", "acct-beta", "user-beta"),
        "refresh": "refresh-beta",
        "accountId": "acct-beta",
        "expires": 2_000_000_000,
    }
    write_json(
        openclaw_home / "openclaw.json",
        {
            "auth": {"profiles": {}, "order": {"openai-codex": ["openai-codex:default"]}},
            "agents": {"list": [{"id": "main"}, {"id": "worker"}]},
        },
    )
    store = {
        "version": 1,
        "profiles": {
            "openai-codex:default": beta,
            "openai-codex:beta@example.com": beta,
        },
        "usageStats": {"openai-codex:default": {"lastUsed": 1}},
        "lastGood": {"openai-codex": "openai-codex:beta@example.com"},
    }
    write_json(openclaw_home / "agents" / "main" / "agent" / "auth-profiles.json", store)
    write_json(openclaw_home / "agents" / "worker" / "agent" / "auth-profiles.json", store)
    adapter.snapshot_dir.mkdir(parents=True, exist_ok=True)
    write_json(adapter.snapshot_dir / "account1.json", alpha)

    adapter.activate_snapshot("account1")

    main_store = json.loads(
        (openclaw_home / "agents" / "main" / "agent" / "auth-profiles.json").read_text(encoding="utf-8")
    )
    config = json.loads((openclaw_home / "openclaw.json").read_text(encoding="utf-8"))
    assert main_store["profiles"]["openai-codex:default"]["accountId"] == "acct-alpha"
    assert main_store["usageStats"] == {"openai-codex:default": {"lastUsed": 1}}
    assert config["auth"]["order"]["openai-codex"][:2] == [
        "openai-codex:default",
        "openai-codex:alpha@example.com",
    ]

