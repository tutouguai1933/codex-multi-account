"""这个文件验证总览接口会带出调度状态。"""

from __future__ import annotations

from codex_multi_account.app import create_app
from codex_multi_account.api.routes_accounts import ImportRequest, SwitchRequest
from codex_multi_account.config import AppSettings
from conftest import make_jwt


def write_json(path, data) -> None:
    """写测试 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def seed_openclaw(settings: AppSettings) -> None:
    """写入一个 OpenClaw 登录态。"""

    profile = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": make_jwt("api@example.com", "acct-api", "user-api"),
        "refresh": "refresh-api",
        "accountId": "acct-api",
    }
    write_json(
        settings.openclaw_home / "agents" / "main" / "agent" / "auth-profiles.json",
        {"version": 1, "profiles": {"openai-codex:default": profile}},
    )


def route_endpoint(app, path: str, method: str = "GET"):
    """按路径和方法取出路由函数。"""

    for route in app.router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"未找到路由: {method} {path}")


def test_overview_route_returns_scheduler_status(tmp_path) -> None:
    """总览接口应带出自动刷新状态。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    payload = route_endpoint(app, "/api/overview")()

    assert payload["status"] == "ok"
    assert "scheduler" in payload
    assert payload["scheduler"]["running"] is False
    assert payload["scheduler"]["enabled"] is True


def test_overview_route_marks_unassigned_when_no_target_is_assigned(tmp_path) -> None:
    """没有任何分配时，不应误报成共用中。"""

    app = create_app(build_settings(tmp_path))

    payload = route_endpoint(app, "/api/overview")()

    assert payload["summary"]["allocationMode"] == "unassigned"


def test_overview_route_includes_accounts_for_dashboard_cards(tmp_path) -> None:
    """总览接口应直接带出账号列表，且不要把 token 返回到前端。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="overview-card")
    )

    payload = route_endpoint(app, "/api/overview")()

    assert len(payload["accounts"]) == 1
    assert payload["accounts"][0]["email"] == "api@example.com"
    assert payload["accounts"][0]["metadata"]["identity"]["account_id"] == "acct-api"
    assert "tokens" not in payload["accounts"][0]["metadata"]["codex_export"]


def test_overview_route_prefers_live_runtime_over_stale_assignment(tmp_path) -> None:
    """总览应按当前真实运行态显示，而不是只看账号池里旧分配。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    codex_payload = {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {
            "access_token": make_jwt("live@example.com", "acct-live", "user-live"),
            "refresh_token": "refresh-live",
            "id_token": make_jwt("live@example.com", "acct-live", "user-live"),
            "account_id": "acct-live",
        },
    }
    write_json(settings.codex_home / "auth.json", codex_payload)
    app = create_app(settings)

    openclaw_account = route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="openclaw-live")
    )
    codex_account = route_endpoint(app, "/api/accounts/import/codex-current", "POST")(
        payload=ImportRequest(label="codex-live")
    )

    route_endpoint(app, "/api/accounts/{account_id}/switch", "POST")(
        account_id=openclaw_account["id"],
        payload=SwitchRequest(target="openclaw"),
    )

    payload = route_endpoint(app, "/api/overview")()

    assert payload["summary"]["openclawAccountEmail"] == "api@example.com"
    assert payload["summary"]["codexAccountEmail"] == "live@example.com"
    assert payload["summary"]["codexAccountId"] == codex_account["id"]
