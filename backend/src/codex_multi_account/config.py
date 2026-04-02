"""这个文件负责集中管理服务路径与运行配置，供适配器、服务层和 API 共用。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    """描述应用运行时用到的路径与外部配置。"""

    project_root: Path
    data_dir: Path
    openclaw_home: Path
    codex_home: Path
    primary_agent: str
    usage_url: str
    fallback_model: str


def _resolve_project_root(project_root: Path | None = None) -> Path:
    """尽量把传入目录解析成项目根目录。"""

    root = (project_root or Path.cwd()).resolve()
    if (root / "web").exists() and (root / "backend").exists():
        return root
    if root.name == "backend" and (root.parent / "web").exists():
        return root.parent
    return root


def default_app_settings(project_root: Path | None = None) -> AppSettings:
    """生成默认配置，允许测试时覆盖项目根目录。"""

    root = _resolve_project_root(project_root)
    return AppSettings(
        project_root=root,
        data_dir=Path(os.environ.get("CMA_DATA_DIR", str(root / "data"))).expanduser(),
        openclaw_home=Path(
            os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw"))
        ).expanduser(),
        codex_home=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser(),
        primary_agent=os.environ.get("OPENCLAW_PRIMARY_AGENT", "taizi"),
        usage_url=os.environ.get(
            "OPENCLAW_CODEX_USAGE_URL",
            "https://chatgpt.com/backend-api/wham/usage",
        ),
        fallback_model=os.environ.get("OPENCLAW_FALLBACK_MODEL", "bailian/qwen3.5-plus"),
    )
