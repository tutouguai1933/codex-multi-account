"""这个文件验证 Codex CLI 适配器的快照和切换行为。"""

from __future__ import annotations

import json
from datetime import datetime

from codex_multi_account.adapters.codex_cli import CodexCliAdapter
from conftest import make_jwt


def test_codex_adapter_reads_auth_json(tmp_path) -> None:
    """应能从 auth.json 读取当前登录态。"""

    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    codex_home.mkdir(parents=True)
    payload = {
        "auth_mode": "chatgpt",
        "last_refresh": 123,
        "OPENAI_API_KEY": None,
        "tokens": {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "id_token": make_jwt("codex@example.com", "acct-codex", "user-codex"),
            "account_id": "acct-codex",
        },
    }
    (codex_home / "auth.json").write_text(json.dumps(payload), encoding="utf-8")
    adapter = CodexCliAdapter(codex_home=codex_home, state_dir=state_dir)
    snapshot = adapter.read_runtime_snapshot()
    assert snapshot.auth_mode == "chatgpt"
    assert snapshot.active_email == "codex@example.com"


def test_codex_adapter_switch_rewrites_auth_atomically(tmp_path) -> None:
    """切换快照时应更新 auth.json。"""

    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    codex_home.mkdir(parents=True)
    payload = {
        "auth_mode": "chatgpt",
        "tokens": {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "id_token": make_jwt("codex@example.com", "acct-codex", "user-codex"),
            "account_id": "acct-codex",
        },
    }
    (codex_home / "auth.json").write_text(json.dumps(payload), encoding="utf-8")
    adapter = CodexCliAdapter(codex_home=codex_home, state_dir=state_dir)
    binding = adapter.capture_current("account1")
    assert binding.snapshot_id == "account1"
    result = adapter.activate_snapshot("account1")
    current = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))
    assert result.active_account_id == "acct-codex"
    assert current["tokens"]["account_id"] == "acct-codex"


def test_codex_adapter_delete_snapshot_removes_local_copy_only(tmp_path) -> None:
    """删除快照不应删除当前 auth.json。"""

    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    codex_home.mkdir(parents=True)
    payload = {
        "auth_mode": "chatgpt",
        "tokens": {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "id_token": make_jwt("codex@example.com", "acct-codex", "user-codex"),
            "account_id": "acct-codex",
        },
    }
    (codex_home / "auth.json").write_text(json.dumps(payload), encoding="utf-8")
    adapter = CodexCliAdapter(codex_home=codex_home, state_dir=state_dir)
    adapter.capture_current("account1")
    adapter.delete_snapshot("account1")
    assert not (adapter.snapshot_dir / "account1.json").exists()
    assert (codex_home / "auth.json").exists()


def test_codex_adapter_normalizes_old_oauth_payloads(tmp_path) -> None:
    """旧的 oauth 快照写回时，应自动转成当前 Codex CLI 识别的 chatgpt 结构。"""

    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    codex_home.mkdir(parents=True)
    adapter = CodexCliAdapter(codex_home=codex_home, state_dir=state_dir)

    adapter.write_snapshot_payload(
        "legacy",
        {
            "auth_mode": "oauth",
            "tokens": {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": make_jwt("legacy@example.com", "acct-legacy", "user-legacy"),
                "account_id": "acct-legacy",
            },
        },
    )
    result = adapter.activate_snapshot("legacy")
    current = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))

    assert result.auth_mode == "chatgpt"
    assert current["auth_mode"] == "chatgpt"
    assert current["OPENAI_API_KEY"] is None
    assert current["tokens"]["account_id"] == "acct-legacy"


def test_codex_adapter_normalizes_last_refresh_to_rfc3339_string(tmp_path) -> None:
    """写回 auth.json 时应把 last_refresh 规整成 Codex CLI 可接受的 RFC3339 字符串。"""

    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    codex_home.mkdir(parents=True)
    adapter = CodexCliAdapter(codex_home=codex_home, state_dir=state_dir)

    adapter.write_snapshot_payload(
        "legacy",
        {
            "auth_mode": "oauth",
            "last_refresh": 1775113886,
            "tokens": {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": make_jwt("legacy@example.com", "acct-legacy", "user-legacy"),
                "account_id": "acct-legacy",
            },
        },
    )
    adapter.activate_snapshot("legacy")
    current = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))

    assert isinstance(current["last_refresh"], str)
    assert current["last_refresh"].endswith("Z")
    assert datetime.fromisoformat(current["last_refresh"].replace("Z", "+00:00"))


def test_codex_adapter_can_activate_api_key_snapshot(tmp_path) -> None:
    """API Key 快照切换时应只补 openai_base_url，不改 provider 身份。"""

    codex_home = tmp_path / ".codex"
    state_dir = tmp_path / "data"
    codex_home.mkdir(parents=True)
    (codex_home / "config.toml").write_text(
        'model = "gpt-5.4"\nmodel_reasoning_effort = "high"\n',
        encoding="utf-8",
    )
    adapter = CodexCliAdapter(codex_home=codex_home, state_dir=state_dir)

    adapter.write_api_snapshot(
        "api-main",
        {
            "base_url": "https://www.ananapi.com/",
            "api_key": "sk-demo",
        },
    )
    snapshot = adapter.activate_snapshot("api-main")
    current_auth = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))
    current_config = (codex_home / "config.toml").read_text(encoding="utf-8")

    assert snapshot.account_kind == "api"
    assert snapshot.provider_name == "openai"
    assert current_auth["auth_mode"] == "apikey"
    assert current_auth["OPENAI_API_KEY"] == "sk-demo"
    assert "tokens" not in current_auth
    assert 'openai_base_url = "https://www.ananapi.com"' in current_config
    assert 'model = "gpt-5.4"' in current_config
    assert 'model_reasoning_effort = "high"' in current_config
    assert 'model_provider =' not in current_config
    assert "[model_providers" not in current_config
