"""这个文件负责读写 Codex CLI 认证文件，并维护本项目自己的快照目录。"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codex_multi_account.adapters.openclaw import decode_jwt_payload
from codex_multi_account.models.account import RuntimeSnapshot, SnapshotBinding


def atomic_write_json(path: Path, data: dict[str, Any], mode: int | None = None) -> None:
    """安全写入 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        temp_name = handle.name
    temp_path = Path(temp_name)
    try:
        if mode is not None:
            os.chmod(temp_path, mode)
        os.replace(temp_path, path)
        if mode is not None:
            os.chmod(path, mode)
    finally:
        if temp_path.exists():
            temp_path.unlink()


class CodexCliAdapter:
    """负责 Codex CLI 活跃登录态和快照切换。"""

    def __init__(self, codex_home: Path, state_dir: Path) -> None:
        self.codex_home = codex_home
        self.state_dir = state_dir
        self.snapshot_dir = state_dir / "snapshots" / "codex"

    @property
    def auth_path(self) -> Path:
        """返回当前活跃 auth.json 路径。"""

        return self.codex_home / "auth.json"

    def _extract_token_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """优先从 id_token 里提取身份字段，缺失时回退到 access_token。"""

        tokens = payload.get("tokens") or {}
        id_payload = decode_jwt_payload(tokens.get("id_token"))
        if id_payload:
            return id_payload
        return decode_jwt_payload(tokens.get("access_token"))

    def _normalize_last_refresh(self, value: object) -> str:
        """把 last_refresh 规整成 Codex CLI 接受的 RFC3339 字符串。"""

        if isinstance(value, str) and value:
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return value
            except ValueError:
                pass
        if isinstance(value, (int, float)):
            moment = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            moment = datetime.now(timezone.utc)
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")

    def _normalize_auth_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """把旧导出格式整理成当前 Codex CLI 可接受的 auth.json 结构。"""

        tokens = payload.get("tokens") or {}
        tokens = tokens if isinstance(tokens, dict) else {}
        normalized = dict(payload)
        normalized["auth_mode"] = "chatgpt"
        normalized["OPENAI_API_KEY"] = normalized.get("OPENAI_API_KEY")
        normalized["tokens"] = {
            "id_token": tokens.get("id_token"),
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "account_id": tokens.get("account_id"),
        }
        if normalized.get("OPENAI_API_KEY", None) is not None:
            normalized["OPENAI_API_KEY"] = None
        normalized["last_refresh"] = self._normalize_last_refresh(normalized.get("last_refresh"))
        return normalized

    def _to_runtime_snapshot(self, payload: dict[str, Any]) -> RuntimeSnapshot:
        """把 auth.json 转成统一快照。"""

        normalized = self._normalize_auth_payload(payload)
        tokens = normalized.get("tokens") or {}
        id_payload = self._extract_token_payload(normalized)
        auth_payload = id_payload.get("https://api.openai.com/auth") or {}
        email = id_payload.get("email") or (id_payload.get("https://api.openai.com/profile") or {}).get("email")
        return RuntimeSnapshot(
            target="codex",
            active_email=email,
            active_account_id=tokens.get("account_id") or auth_payload.get("chatgpt_account_id"),
            user_id=normalized.get("user_id") or auth_payload.get("user_id") or auth_payload.get("chatgpt_user_id"),
            plan_type=normalized.get("plan_type") or auth_payload.get("chatgpt_plan_type"),
            expires=id_payload.get("exp"),
            auth_mode=normalized.get("auth_mode"),
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
            raw_profile=normalized,
            has_binding=bool(payload),
        )

    def build_auth_payload(self, exported: dict[str, Any]) -> dict[str, Any]:
        """把 cockpit-tools 的导出条目转回可写入 auth.json 的结构。"""

        tokens = exported.get("tokens") or {}
        return self._normalize_auth_payload(
            {
                "auth_mode": exported.get("auth_mode") or "chatgpt",
                "OPENAI_API_KEY": None,
                "last_refresh": exported.get("usage_updated_at"),
                "user_id": exported.get("user_id"),
                "plan_type": exported.get("plan_type"),
                "account_id": exported.get("account_id"),
                "account_name": exported.get("account_name"),
                "account_structure": exported.get("account_structure"),
                "organization_id": exported.get("organization_id"),
                "email": exported.get("email"),
                "tokens": {
                    "id_token": tokens.get("id_token"),
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token"),
                    "account_id": exported.get("account_id"),
                },
            }
        )

    def write_snapshot_payload(self, snapshot_id: str, payload: dict[str, Any]) -> RuntimeSnapshot:
        """把给定 payload 保存成 Codex 快照。"""

        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{snapshot_id}.json"
        normalized = self._normalize_auth_payload(payload)
        atomic_write_json(path, normalized, mode=0o600)
        return self._to_runtime_snapshot(normalized)

    def read_runtime_snapshot(self) -> RuntimeSnapshot:
        """读取当前活跃的 Codex CLI 登录态。"""

        if not self.auth_path.exists():
            return RuntimeSnapshot(target="codex", raw_profile={}, has_binding=False)
        payload = json.loads(self.auth_path.read_text(encoding="utf-8"))
        return self._to_runtime_snapshot(payload)

    def read_snapshot(self, snapshot_id: str) -> RuntimeSnapshot:
        """读取某个已保存的快照。"""

        path = self.snapshot_dir / f"{snapshot_id}.json"
        if not path.exists():
            return RuntimeSnapshot(target="codex", raw_profile={}, has_binding=False)
        return self._to_runtime_snapshot(json.loads(path.read_text(encoding="utf-8")))

    def capture_current(self, snapshot_id: str) -> SnapshotBinding:
        """把当前活跃登录态保存为快照。"""

        snapshot = self.read_runtime_snapshot()
        if not snapshot.has_binding:
            raise ValueError("当前没有可导入的 Codex 登录态")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{snapshot_id}.json"
        atomic_write_json(path, snapshot.raw_profile, mode=0o600)
        return SnapshotBinding(
            snapshot_id=snapshot_id,
            path=str(path),
            target="codex",
            email=snapshot.active_email,
        )

    def activate_snapshot(self, snapshot_id: str) -> RuntimeSnapshot:
        """把快照切回当前 auth.json。"""

        path = self.snapshot_dir / f"{snapshot_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        normalized = self._normalize_auth_payload(payload)
        atomic_write_json(self.auth_path, normalized, mode=0o600)
        return self._to_runtime_snapshot(normalized)

    def delete_snapshot(self, snapshot_id: str) -> None:
        """删除本地保存的快照。"""

        path = self.snapshot_dir / f"{snapshot_id}.json"
        if path.exists():
            path.unlink()
