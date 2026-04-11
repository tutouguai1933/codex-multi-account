"""这个文件验证调度设置和 Codex 文件编辑接口。"""

from __future__ import annotations

import json

from codex_multi_account.app import create_app
from codex_multi_account.config import AppSettings
from conftest import make_jwt


def build_settings(tmp_path) -> AppSettings:
    """构造测试环境设置。"""

    return AppSettings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        openclaw_home=tmp_path / ".openclaw",
        codex_home=tmp_path / ".codex",
        primary_agent="main",
        usage_url="http://127.0.0.1:9/usage",
        fallback_model="bailian/qwen3.5-plus",
    )


def route_endpoint(app, path: str, method: str = "GET"):
    """按路径和方法取出路由函数。"""

    for route in app.router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"未找到路由: {method} {path}")


def test_codex_runtime_route_returns_raw_files_and_quick_settings(tmp_path) -> None:
    """应能读取 Codex 的 config/auth 原文和基础快捷字段。"""

    settings = build_settings(tmp_path)
    settings.codex_home.mkdir(parents=True)
    (settings.codex_home / "config.toml").write_text(
        'model = "gpt-5.4"\nreview_model = "gpt-5.4"\nmodel_reasoning_effort = "xhigh"\nmodel_context_window = 1000000\nmodel_auto_compact_token_limit = 900000\nopenai_base_url = "https://www.ananapi.com"\nservice_tier = "fast"\n[features]\nfast_mode = true\n',
        encoding="utf-8",
    )
    (settings.codex_home / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "apikey",
                "OPENAI_API_KEY": "sk-demo",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    app = create_app(settings)

    payload = route_endpoint(app, "/api/settings/codex-runtime", "GET")()

    assert 'model = "gpt-5.4"' in payload["config_text"]
    assert '"OPENAI_API_KEY": "sk-demo"' in payload["auth_text"]
    assert payload["quick_settings"]["model"] == "gpt-5.4"
    assert payload["quick_settings"]["openai_base_url"] == "https://www.ananapi.com"
    assert payload["quick_settings"]["fast_mode_enabled"] is True


def test_codex_runtime_save_route_persists_raw_files(tmp_path) -> None:
    """保存原文后，应立刻写回 config.toml 和 auth.json。"""

    settings = build_settings(tmp_path)
    settings.codex_home.mkdir(parents=True)
    (settings.codex_home / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")
    (settings.codex_home / "auth.json").write_text(
        json.dumps({"auth_mode": "chatgpt", "tokens": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    app = create_app(settings)

    payload = route_endpoint(app, "/api/settings/codex-runtime", "PUT")(
        payload=type(
            "Payload",
            (),
            {
                "config_text": 'model = "gpt-5.4"\nreview_model = "gpt-5.4"\n',
                "auth_text": json.dumps(
                    {
                        "auth_mode": "apikey",
                        "OPENAI_API_KEY": "sk-updated",
                        "tokens": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        )()
    )

    assert 'review_model = "gpt-5.4"' in payload["config_text"]
    assert '"OPENAI_API_KEY": "sk-updated"' in payload["auth_text"]
    assert 'review_model = "gpt-5.4"' in (settings.codex_home / "config.toml").read_text(encoding="utf-8")
    assert '"OPENAI_API_KEY": "sk-updated"' in (settings.codex_home / "auth.json").read_text(encoding="utf-8")
    assert '"tokens"' not in payload["auth_text"]
    assert '"tokens"' not in (settings.codex_home / "auth.json").read_text(encoding="utf-8")


def test_codex_runtime_quick_route_updates_config_text(tmp_path) -> None:
    """快捷字段保存后，应立刻反映到返回的 config 原文中。"""

    settings = build_settings(tmp_path)
    settings.codex_home.mkdir(parents=True)
    (settings.codex_home / "config.toml").write_text(
        'model = "gpt-5.4"\nreview_model = "gpt-5.4"\nmodel_reasoning_effort = "xhigh"\n',
        encoding="utf-8",
    )
    (settings.codex_home / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "id_token": make_jwt("settings@example.com", "acct-settings", "user-settings"),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    app = create_app(settings)

    payload = route_endpoint(app, "/api/settings/codex-runtime/quick", "PUT")(
        payload=type(
            "Payload",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "model": "gpt-5.4",
                    "review_model": "gpt-5.4",
                    "model_reasoning_effort": "high",
                    "fast_mode_enabled": True,
                    "model_context_window": 1_000_000,
                    "model_auto_compact_token_limit": 900_000,
                }
            },
        )()
    )

    assert 'model_reasoning_effort = "high"' in payload["config_text"]
    assert "model_context_window = 1000000" in payload["config_text"]
    assert "model_auto_compact_token_limit = 900000" in payload["config_text"]
    assert 'service_tier = "fast"' in payload["config_text"]
    assert "[features]" in payload["config_text"]
    assert "fast_mode = true" in payload["config_text"]
