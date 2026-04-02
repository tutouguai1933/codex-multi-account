"""这个文件验证主要 API 路由逻辑是否可用。"""

from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from codex_multi_account.app import create_app
from codex_multi_account.api.routes_accounts import (
    CodexBatchImportRequest,
    ImportRequest,
    LoginInputRequest,
    SwitchRequest,
    build_accounts_router,
)
from codex_multi_account.config import AppSettings
from codex_multi_account.services.login_session import LoginSessionManager
from codex_multi_account.storage.json_store import JsonStore
from conftest import make_jwt
from test_login_session import FakeProcess, make_account


def write_json(path, data) -> None:
    """写测试 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def router_endpoint(router, path: str, method: str = "GET"):
    """按路径和方法取出单个路由对象里的函数。"""

    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"未找到路由: {method} {path}")


def test_health_route_returns_ok(tmp_path) -> None:
    """总览接口应返回 200。"""

    app = create_app(build_settings(tmp_path))
    payload = route_endpoint(app, "/api/overview")()
    assert payload["status"] == "ok"


def test_accounts_route_lists_unified_accounts(tmp_path) -> None:
    """导入后应能列出账号。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="api-main")
    )
    response = route_endpoint(app, "/api/accounts", "GET")()
    assert len(response["accounts"]) == 1


def test_switch_route_accepts_target_parameter(tmp_path) -> None:
    """切换接口应接受 target 参数。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    imported = route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="api-main")
    )
    response = route_endpoint(app, "/api/accounts/{account_id}/switch", "POST")(
        account_id=imported["id"],
        payload=SwitchRequest(target="openclaw"),
    )
    assert response["target"] == "openclaw"


def test_switch_route_updates_codex_runtime_and_overview(tmp_path) -> None:
    """切 Codex 后，真实运行态和总览当前账号都应变化。"""

    settings = build_settings(tmp_path)
    app = create_app(settings)
    sample = {
        "id": "codex_demo_1",
        "email": "switch@example.com",
        "auth_mode": "chatgpt",
        "user_id": "user-switch",
        "plan_type": "team",
        "account_id": "acct-switch",
        "tokens": {
            "id_token": make_jwt("switch@example.com", "acct-switch", "user-switch"),
            "access_token": make_jwt("switch@example.com", "acct-switch", "user-switch"),
            "refresh_token": "refresh-switch",
        },
    }

    imported = route_endpoint(app, "/api/accounts/import/codex-batch", "POST")(
        payload=CodexBatchImportRequest(items=[sample])
    )
    route_endpoint(app, "/api/accounts/{account_id}/switch", "POST")(
        account_id=imported["accounts"][0]["id"],
        payload=SwitchRequest(target="codex"),
    )

    runtime = json.loads((settings.codex_home / "auth.json").read_text(encoding="utf-8"))
    overview = route_endpoint(app, "/api/overview")()

    assert runtime["auth_mode"] == "chatgpt"
    assert runtime["tokens"]["account_id"] == "acct-switch"
    assert overview["summary"]["codexAccountEmail"] == "switch@example.com"


def test_delete_route_removes_account(tmp_path) -> None:
    """删除接口应能移除账号。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    imported = route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="api-main")
    )
    deleted = route_endpoint(app, "/api/accounts/{account_id}", "DELETE")(account_id=imported["id"])
    listed = route_endpoint(app, "/api/accounts", "GET")()
    assert deleted["status"] == "deleted"
    assert listed["accounts"] == []


def test_probe_route_returns_health_payload(tmp_path) -> None:
    """探测接口应返回健康状态字段。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    imported = route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="api-main")
    )
    response = route_endpoint(app, "/api/accounts/{account_id}/probe", "POST")(account_id=imported["id"])
    assert response["status"]["health"] in {"healthy", "quota-unknown", "auth-invalid"}


def test_scheduler_run_route_returns_summary(tmp_path) -> None:
    """手动调度接口应返回调度摘要。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="api-main")
    )
    response = asyncio.run(route_endpoint(app, "/api/scheduler/run", "POST")())
    assert "assignments" in response


def test_scheduler_refresh_route_returns_status(tmp_path) -> None:
    """一键检测全部额度接口应返回成功状态。"""

    settings = build_settings(tmp_path)
    seed_openclaw(settings)
    app = create_app(settings)
    route_endpoint(app, "/api/accounts/import/openclaw-current", "POST")(
        payload=ImportRequest(label="api-main")
    )

    response = route_endpoint(app, "/api/scheduler/refresh", "POST")()

    assert response["status"] == "refreshed"


def test_login_status_route_returns_target_states(tmp_path) -> None:
    """登录状态接口应返回两个目标的状态。"""

    app = create_app(build_settings(tmp_path))

    response = route_endpoint(app, "/api/accounts/logins", "GET")()

    assert set(response["targets"].keys()) == {"openclaw", "codex"}
    assert response["targets"]["openclaw"]["status"] == "idle"


def test_login_status_route_is_not_shadowed_by_account_detail_route(tmp_path) -> None:
    """真实 HTTP 路由下，/logins 不应被 account_id 动态路由覆盖。"""

    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.get("/api/accounts/logins")

    assert response.status_code == 200
    assert response.json()["targets"]["codex"]["status"] == "idle"


def test_login_input_route_submits_value_to_running_session(tmp_path) -> None:
    """登录输入接口应把页面值送进当前会话。"""

    process = FakeProcess(pid=1234, exit_code=None)
    manager = LoginSessionManager(
        importers={
            "openclaw": lambda: make_account("acct_1", "openclaw-main"),
            "codex": lambda: make_account("acct_2", "codex-main"),
        },
        store=JsonStore(tmp_path / "login_sessions.json"),
        process_starter=lambda command: process,
    )
    manager.start("openclaw")
    manager.record_output("openclaw", "Paste the authorization code (or full redirect URL):")
    router = build_accounts_router(
        account_pool=object(),  # type: ignore[arg-type]
        probe_service=object(),  # type: ignore[arg-type]
        switch_service=object(),  # type: ignore[arg-type]
        login_manager=manager,
    )

    response = router_endpoint(router, "/api/accounts/login/{target}/input", "POST")(
        target="openclaw",
        payload=LoginInputRequest(value="https://auth.openai.com/callback?code=abc"),
    )

    assert response["awaiting_input"] is False
    assert process.submitted_inputs == ["https://auth.openai.com/callback?code=abc"]


def test_batch_import_and_export_routes_work(tmp_path) -> None:
    """批量导入和导出接口应兼容 Codex JSON。"""

    app = create_app(build_settings(tmp_path))
    sample = {
        "id": "codex_demo_1",
        "email": "batch@example.com",
        "auth_mode": "oauth",
        "user_id": "user-batch",
        "plan_type": "team",
        "account_id": "acct-batch",
        "tokens": {
            "id_token": make_jwt("batch@example.com", "acct-batch", "user-batch"),
            "access_token": make_jwt("batch@example.com", "acct-batch", "user-batch"),
            "refresh_token": "refresh-batch",
        },
        "quota": {
            "hourly_percentage": 100,
            "weekly_percentage": 90,
        },
    }

    imported = route_endpoint(app, "/api/accounts/import/codex-batch", "POST")(
        payload=CodexBatchImportRequest(items=[sample])
    )
    exported = route_endpoint(app, "/api/accounts/export/codex-batch", "GET")()

    assert imported["importedCount"] == 1
    assert imported["accounts"][0]["bindings"]["openclaw"]["snapshot_id"] is not None
    assert exported["items"][0]["email"] == "batch@example.com"


def test_account_routes_do_not_expose_token_metadata(tmp_path) -> None:
    """账号接口返回前端时，不应把 token 明文带出去。"""

    app = create_app(build_settings(tmp_path))
    sample = {
        "id": "codex_demo_safe",
        "email": "safe@example.com",
        "auth_mode": "oauth",
        "user_id": "user-safe",
        "plan_type": "team",
        "account_id": "acct-safe",
        "account_name": "Safe Workspace",
        "tokens": {
            "id_token": make_jwt("safe@example.com", "acct-safe", "user-safe"),
            "access_token": make_jwt("safe@example.com", "acct-safe", "user-safe"),
            "refresh_token": "refresh-safe",
        },
    }

    imported = route_endpoint(app, "/api/accounts/import/codex-batch", "POST")(
        payload=CodexBatchImportRequest(items=[sample])
    )

    account = imported["accounts"][0]

    assert account["metadata"]["codex_export"]["account_name"] == "Safe Workspace"
    assert "tokens" not in account["metadata"]["codex_export"]
