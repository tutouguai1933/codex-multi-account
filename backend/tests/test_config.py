"""这个文件验证默认配置的路径解析。"""

from __future__ import annotations

from codex_multi_account.config import default_app_settings


def test_default_app_settings_resolves_repo_root_from_backend_dir(tmp_path, monkeypatch) -> None:
    """从 backend 目录启动时，也应识别整个项目根目录。"""

    backend_dir = tmp_path / "backend"
    web_dir = tmp_path / "web"
    backend_dir.mkdir(parents=True, exist_ok=True)
    web_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(backend_dir)

    settings = default_app_settings()

    assert settings.project_root == tmp_path
    assert settings.data_dir == tmp_path / "data"
