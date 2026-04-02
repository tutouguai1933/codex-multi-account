"""这个文件负责追加 JSONL 事件日志，方便界面展示最近动作。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EventLog:
    """负责写入和读取事件流。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, payload: dict[str, Any]) -> None:
        """把事件追加到 JSONL 文件。"""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """按时间倒序读取最近事件。"""

        if not self.path.exists():
            return []
        rows = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        rows.reverse()
        return rows[:limit]

