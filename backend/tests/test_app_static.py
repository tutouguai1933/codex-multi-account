"""这个文件验证后端可以托管前端构建产物。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from codex_multi_account.app import create_app
from codex_multi_account.config import AppSettings


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


def test_backend_serves_frontend_index_when_dist_exists(tmp_path) -> None:
    """存在前端构建目录时，根路径应返回首页。"""

    dist_dir = tmp_path / "web" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>frontend-shell</body></html>", encoding="utf-8")
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "frontend-shell" in response.text


def test_backend_serves_static_asset_when_dist_exists(tmp_path) -> None:
    """存在前端构建目录时，也应能返回静态资源文件。"""

    dist_dir = tmp_path / "web" / "dist" / "assets"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "web" / "dist" / "index.html").write_text("<html><body>frontend-shell</body></html>", encoding="utf-8")
    (dist_dir / "app.js").write_text("console.log('hello');", encoding="utf-8")
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text
