"""这个文件负责读写 Codex CLI 认证文件，并维护本项目自己的快照目录。"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # pragma: no cover - 兼容 Python 3.10 / 3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from codex_multi_account.adapters.openclaw import decode_jwt_payload
from codex_multi_account.models.account import ApiProfile, RuntimeSnapshot, SnapshotBinding
from codex_multi_account.utils.api_profiles import (
    LEGACY_CODEX_CONFIG_KEYS,
    MANAGED_CODEX_CONFIG_KEYS,
    ensure_api_profile_fingerprint,
    normalize_base_url,
)


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


def atomic_write_text(path: Path, content: str, mode: int | None = None) -> None:
    """安全写入文本文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
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
        self.backup_dir = state_dir / "runtime_backups"

    @property
    def auth_path(self) -> Path:
        """返回当前活跃 auth.json 路径。"""

        return self.codex_home / "auth.json"

    @property
    def config_path(self) -> Path:
        """返回当前活跃 config.toml 路径。"""

        return self.codex_home / "config.toml"

    @property
    def config_backup_path(self) -> Path:
        """返回 Codex 配置备份路径。"""

        return self.backup_dir / "codex-config.toml"

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

        if str(payload.get("auth_mode") or "") == "apikey":
            normalized = dict(payload)
            normalized["auth_mode"] = "apikey"
            normalized.pop("tokens", None)
            normalized["OPENAI_API_KEY"] = str(payload.get("OPENAI_API_KEY") or "")
            normalized["last_refresh"] = self._normalize_last_refresh(normalized.get("last_refresh"))
            return normalized
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
        if normalized.get("auth_mode") == "apikey":
            config = self.read_config()
            provider_name = "openai"
            base_url = self._resolve_codex_api_base_url(config)
            model = config.get("model")
            fingerprint = payload.get("api_profile_fingerprint")
            if not isinstance(fingerprint, str) or not fingerprint:
                profile = ApiProfile(
                    provider_name=provider_name,
                    base_url=base_url,
                    api_key=str(normalized.get("OPENAI_API_KEY") or ""),
                    model=str(model or "gpt-5.4"),
                )
                profile = ensure_api_profile_fingerprint(profile)
                fingerprint = profile.fingerprint
            return RuntimeSnapshot(
                target="codex",
                account_kind="api",
                active_account_id=fingerprint,
                auth_mode="apikey",
                provider_name=provider_name,
                base_url=base_url,
                api_key_fingerprint=fingerprint,
                active_model=str(model or ""),
                raw_profile=normalized,
                has_binding=bool(normalized.get("OPENAI_API_KEY")),
            )
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

    def read_config(self) -> dict[str, Any]:
        """读取当前 Codex CLI 配置。"""

        if not self.config_path.exists():
            return {}
        return tomllib.loads(self.config_path.read_text(encoding="utf-8"))

    def read_runtime_files(self) -> dict[str, Any]:
        """读取配置页需要的 Codex 原文和快捷字段。"""

        config_text = (
            self.config_path.read_text(encoding="utf-8")
            if self.config_path.exists()
            else ""
        )
        auth_text = (
            self.auth_path.read_text(encoding="utf-8")
            if self.auth_path.exists()
            else "{\n  \"auth_mode\": \"chatgpt\",\n  \"tokens\": {}\n}\n"
        )
        config = self.read_config()
        return {
            "config_text": config_text,
            "auth_text": auth_text,
            "quick_settings": {
                "openai_base_url": self._resolve_codex_api_base_url(config) or None,
                "model": str(config.get("model") or "") or None,
                "review_model": str(config.get("review_model") or "") or None,
                "model_reasoning_effort": str(config.get("model_reasoning_effort") or "") or None,
                "fast_mode_enabled": self._is_fast_mode_enabled(config),
                "model_context_window": int(config["model_context_window"])
                if isinstance(config.get("model_context_window"), int)
                else None,
                "model_auto_compact_token_limit": int(config["model_auto_compact_token_limit"])
                if isinstance(config.get("model_auto_compact_token_limit"), int)
                else None,
            },
        }

    def _dump_scalar(self, value: object) -> str:
        """把标量值转成 TOML 文本。"""

        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        return json.dumps("" if value is None else str(value), ensure_ascii=False)

    def _dump_toml_section(self, prefix: list[str], payload: dict[str, Any], lines: list[str]) -> None:
        """递归写出 TOML 字典。"""

        scalar_items: list[tuple[str, object]] = []
        child_items: list[tuple[str, dict[str, Any]]] = []
        for key, value in payload.items():
            if isinstance(value, dict):
                child_items.append((key, value))
            else:
                scalar_items.append((key, value))
        if prefix:
            section = ".".join(
                [json.dumps(item, ensure_ascii=False) if ("/" in item or "." in item) else item for item in prefix]
            )
            lines.append(f"[{section}]")
        for key, value in scalar_items:
            lines.append(f"{key} = {self._dump_scalar(value)}")
        if prefix and (scalar_items or child_items):
            lines.append("")
        for key, value in child_items:
            self._dump_toml_section([*prefix, key], value, lines)

    def write_config(self, payload: dict[str, Any]) -> None:
        """把配置字典写回 config.toml。"""

        lines: list[str] = []
        self._dump_toml_section([], payload, lines)
        content = "\n".join(line for line in lines if line is not None).strip() + "\n"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(content, encoding="utf-8")

    def save_runtime_files(self, config_text: str, auth_text: str) -> dict[str, Any]:
        """保存配置页里编辑后的 config/auth 原文。"""

        normalized_config = config_text if config_text.endswith("\n") else f"{config_text}\n"
        parsed_auth = json.loads(auth_text)
        if not isinstance(parsed_auth, dict):
            raise ValueError("auth.json 顶层必须是 JSON 对象")
        if str(parsed_auth.get("auth_mode") or "") == "apikey":
            parsed_auth = self._normalize_auth_payload(parsed_auth)
        normalized_auth = json.dumps(parsed_auth, ensure_ascii=False, indent=2) + "\n"
        tomllib.loads(normalized_config)
        atomic_write_text(self.config_path, normalized_config)
        atomic_write_text(self.auth_path, normalized_auth, mode=0o600)
        return self.read_runtime_files()

    def save_quick_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        """按快捷字段更新 config.toml，并返回最新原文。"""

        config = self.read_config()
        for key in [
            "model",
            "review_model",
            "model_reasoning_effort",
            "model_context_window",
            "model_auto_compact_token_limit",
        ]:
            value = payload.get(key)
            if value is not None:
                config[key] = value
        openai_base_url = payload.get("openai_base_url")
        if isinstance(openai_base_url, str):
            normalized = normalize_base_url(openai_base_url)
            if normalized:
                config["openai_base_url"] = normalized
            else:
                config.pop("openai_base_url", None)
        fast_mode_enabled = payload.get("fast_mode_enabled")
        if isinstance(fast_mode_enabled, bool):
            config["service_tier"] = "fast" if fast_mode_enabled else "flex"
            features = config.get("features")
            if not isinstance(features, dict):
                features = {}
            features["fast_mode"] = fast_mode_enabled
            config["features"] = features
        self.write_config(config)
        return self.read_runtime_files()

    def backup_config_if_needed(self) -> None:
        """首次进入 API 模式前备份当前 config.toml。"""

        if not self.config_path.exists():
            return
        current = self.read_config()
        if self._is_managed_api_config(current):
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.config_backup_path.write_text(self.config_path.read_text(encoding="utf-8"), encoding="utf-8")

    def restore_default_config(self) -> None:
        """退出 API 模式时恢复之前的 config.toml。"""

        if self.config_backup_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                self.config_backup_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.config_backup_path.unlink()
            return
        self.clear_api_provider_config()

    def _merge_api_profile_into_config(self, profile: ApiProfile) -> dict[str, Any]:
        """把第三方 API 基础地址写进当前 Codex 配置，并保留无关设置。"""

        profile = ensure_api_profile_fingerprint(profile)
        config = self.read_config()
        for key in MANAGED_CODEX_CONFIG_KEYS | LEGACY_CODEX_CONFIG_KEYS:
            config.pop(key, None)
        config["openai_base_url"] = normalize_base_url(profile.base_url)
        providers = config.get("model_providers")
        if isinstance(providers, dict):
            for key in list(providers.keys()):
                current = providers.get(key)
                if isinstance(current, dict) and "base_url" in current and "wire_api" in current:
                    providers.pop(key, None)
        providers = config.setdefault("model_providers", {})
        if not isinstance(providers, dict) or not providers:
            config.pop("model_providers", None)
        return config

    def clear_api_provider_config(self) -> None:
        """从 config.toml 中移除本项目托管的第三方 API 配置。"""

        config = self.read_config()
        changed = False
        for key in MANAGED_CODEX_CONFIG_KEYS | LEGACY_CODEX_CONFIG_KEYS:
            if key in config:
                config.pop(key, None)
                changed = True
        providers = config.get("model_providers")
        if isinstance(providers, dict):
            for key in list(providers.keys()):
                current_provider = providers.get(key)
                if isinstance(current_provider, dict) and "base_url" in current_provider and "wire_api" in current_provider:
                    providers.pop(key, None)
                    changed = True
            if not providers:
                config.pop("model_providers", None)
                changed = True
        if changed:
            self.write_config(config)

    def _resolve_codex_api_base_url(self, config: dict[str, Any]) -> str:
        """读取当前 Codex 配置中的 API 基础地址，兼容旧格式。"""

        base_url = config.get("openai_base_url")
        if isinstance(base_url, str) and base_url.strip():
            return normalize_base_url(base_url)
        provider_name = str(config.get("model_provider") or "")
        providers = config.get("model_providers")
        if isinstance(providers, dict) and provider_name:
            provider = providers.get(provider_name)
            if isinstance(provider, dict):
                legacy_base_url = provider.get("base_url")
                if isinstance(legacy_base_url, str) and legacy_base_url.strip():
                    return normalize_base_url(legacy_base_url)
        return ""

    def _is_fast_mode_enabled(self, config: dict[str, Any]) -> bool:
        """判断当前配置是否启用了 Fast 模式。"""

        features = config.get("features")
        if isinstance(features, dict) and features.get("fast_mode") is False:
            return False
        return str(config.get("service_tier") or "").strip().lower() == "fast"

    def _is_managed_api_config(self, config: dict[str, Any]) -> bool:
        """判断当前配置是否已经是本项目写入的 API 模式。"""

        if isinstance(config.get("openai_base_url"), str) and str(config.get("openai_base_url")).strip():
            return True
        provider_name = str(config.get("model_provider") or "")
        providers = config.get("model_providers")
        if isinstance(providers, dict) and provider_name:
            provider = providers.get(provider_name)
            if isinstance(provider, dict) and "base_url" in provider and "wire_api" in provider:
                return True
        return False

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

    def write_api_snapshot(self, snapshot_id: str, profile: ApiProfile | dict[str, Any]) -> RuntimeSnapshot:
        """把第三方 API 账号保存成可切换快照。"""

        if not isinstance(profile, ApiProfile):
            profile = ApiProfile.model_validate(profile)
        profile = ensure_api_profile_fingerprint(profile)
        payload = {
            "auth_mode": "apikey",
            "OPENAI_API_KEY": profile.api_key,
            "last_refresh": self._normalize_last_refresh(None),
            "api_profile_fingerprint": profile.fingerprint,
            "api_profile": profile.model_dump(mode="json"),
        }
        return self.write_snapshot_payload(snapshot_id, payload)

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
        profile_payload = payload.get("api_profile") if isinstance(payload, dict) else None
        if normalized.get("auth_mode") == "apikey":
            if not isinstance(profile_payload, dict):
                raise ValueError("API 账号快照缺少 provider 配置")
            profile = ensure_api_profile_fingerprint(ApiProfile.model_validate(profile_payload))
            self.backup_config_if_needed()
            self.write_config(self._merge_api_profile_into_config(profile))
        else:
            self.restore_default_config()
        atomic_write_json(self.auth_path, normalized, mode=0o600)
        return self._to_runtime_snapshot(normalized)

    def delete_snapshot(self, snapshot_id: str) -> None:
        """删除本地保存的快照。"""

        path = self.snapshot_dir / f"{snapshot_id}.json"
        if path.exists():
            path.unlink()
