"""这个文件提供简单的 JSON 原子读写，供账号池和设置共用。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonStore:
    """负责把小体量 JSON 文档安全写到磁盘。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """读取 JSON，不存在时返回默认值。"""

        if not self.path.exists():
            return dict(default or {})
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, data: dict[str, Any]) -> None:
        """使用原子替换写入 JSON。"""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False
        ) as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            temp_name = handle.name
        temp_path = Path(temp_name)
        try:
            os.replace(temp_path, self.path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

