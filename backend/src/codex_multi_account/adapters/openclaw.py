"""这个文件负责读写 OpenClaw 运行时文件，并把结果转换成统一快照。"""

from __future__ import annotations

import base64
import json
import os
import tempfile
import time
from hashlib import md5
from pathlib import Path
from typing import Any

from codex_multi_account.models.account import ApiProfile, RuntimeSnapshot, SnapshotBinding
from codex_multi_account.utils.api_profiles import ensure_api_profile_fingerprint, normalize_base_url

CANONICAL_PROFILE = "openai-codex:default"
DEFAULT_OAUTH_MODEL = "openai-codex/gpt-5.4"


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


def decode_jwt_payload(token: str | None) -> dict[str, Any]:
    """解码 JWT 中间段，失败时返回空字典。"""

    if not token:
        return {}
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


class OpenClawAdapter:
    """负责 OpenClaw 登录态的读取、快照和切换。"""

    def __init__(self, openclaw_home: Path, state_dir: Path, primary_agent: str) -> None:
        self.openclaw_home = openclaw_home
        self.state_dir = state_dir
        self.primary_agent = primary_agent
        self.snapshot_dir = state_dir / "snapshots" / "openclaw"
        self.backup_dir = state_dir / "runtime_backups"

    @property
    def config_path(self) -> Path:
        """返回主配置文件路径。"""

        return self.openclaw_home / "openclaw.json"

    def auth_path_for_agent(self, agent_id: str) -> Path:
        """返回某个 agent 的认证文件路径。"""

        return self.openclaw_home / "agents" / agent_id / "agent" / "auth-profiles.json"

    def configured_agents(self) -> list[str]:
        """收集配置中声明的 agent 和磁盘中存在的 agent。"""

        ids: list[str] = []
        if self.config_path.exists():
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            for item in (config.get("agents", {}) or {}).get("list", []):
                agent_id = item.get("id")
                if isinstance(agent_id, str):
                    ids.append(agent_id)
        agents_dir = self.openclaw_home / "agents"
        if agents_dir.exists():
            for entry in agents_dir.iterdir():
                if entry.is_dir() and (entry / "agent").exists():
                    ids.append(entry.name)
        if self.primary_agent not in ids:
            ids.insert(0, self.primary_agent)
        return sorted(set(ids))

    def load_auth_store(self, agent_id: str) -> dict[str, Any]:
        """读取某个 agent 的认证文件。"""

        path = self.auth_path_for_agent(agent_id)
        if not path.exists():
            return {"version": 1, "profiles": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    def read_openclaw_config(self) -> dict[str, Any]:
        """读取 OpenClaw 主配置。"""

        if not self.config_path.exists():
            return {}
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    @property
    def config_backup_path(self) -> Path:
        """返回 OpenClaw 配置备份路径。"""

        return self.backup_dir / "openclaw.json"

    def _backup_config_if_needed(self) -> None:
        """首次进入 API 模式前备份当前 openclaw.json。"""

        if self.config_backup_path.exists() or not self.config_path.exists():
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.config_backup_path.write_text(self.config_path.read_text(encoding="utf-8"), encoding="utf-8")

    def restore_default_config(self) -> None:
        """退出 API 模式时恢复原始 openclaw.json。"""

        if self.config_backup_path.exists():
            self.config_path.write_text(
                self.config_backup_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.config_backup_path.unlink()
            return
        config = self.read_openclaw_config()
        providers = ((config.get("models") or {}).get("providers") or {})
        if isinstance(providers, dict):
            for key in list(providers.keys()):
                if isinstance(key, str) and key.startswith("cma-api-"):
                    providers.pop(key, None)
        agents = config.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        model_cfg = defaults.setdefault("model", {})
        model_cfg["primary"] = DEFAULT_OAUTH_MODEL
        default_models = defaults.setdefault("models", {})
        if isinstance(default_models, dict):
            default_models.setdefault(DEFAULT_OAUTH_MODEL, {})
        atomic_write_json(self.config_path, config)

    def _identity_from_profile(self, profile: dict[str, Any]) -> RuntimeSnapshot:
        """把 profile 解析成统一快照。"""

        if profile.get("type") == "api":
            provider_name = str(profile.get("provider_name") or "openai")
            base_url = str(profile.get("base_url") or "")
            api_key = str(profile.get("api_key") or "")
            model = str(profile.get("model") or "")
            fingerprint = str(profile.get("fingerprint") or "")
            if not fingerprint and api_key:
                fingerprint = f"api_{md5('|'.join([provider_name.lower(), normalize_base_url(base_url).lower(), api_key, model]).encode('utf-8')).hexdigest()[:16]}"
            return RuntimeSnapshot(
                target="openclaw",
                account_kind="api",
                active_account_id=fingerprint or None,
                auth_mode="apikey",
                provider_name=provider_name,
                base_url=base_url,
                api_key_fingerprint=fingerprint or None,
                active_model=model or None,
                raw_profile=profile,
                has_binding=bool(api_key and base_url and model),
            )
        payload = decode_jwt_payload(str(profile.get("access") or ""))
        openai_profile = payload.get("https://api.openai.com/profile") or {}
        auth = payload.get("https://api.openai.com/auth") or {}
        return RuntimeSnapshot(
            target="openclaw",
            active_email=openai_profile.get("email"),
            active_account_id=profile.get("accountId") or auth.get("chatgpt_account_id"),
            user_id=auth.get("user_id"),
            plan_type=auth.get("chatgpt_plan_type"),
            expires=profile.get("expires"),
            access_token=profile.get("access"),
            refresh_token=profile.get("refresh"),
            raw_profile=profile,
            has_binding=bool(profile),
        )

    def read_runtime_snapshot(self) -> RuntimeSnapshot:
        """读取当前主 agent 的活跃 OpenAI Codex 登录态。"""

        config = self.read_openclaw_config()
        defaults = ((config.get("agents") or {}).get("defaults") or {}) if isinstance(config, dict) else {}
        model_cfg = defaults.get("model") or {}
        primary_model = model_cfg.get("primary") if isinstance(model_cfg, dict) else None
        if isinstance(primary_model, str) and "/" in primary_model:
            provider_key, _, model_id = primary_model.partition("/")
            provider = ((config.get("models") or {}).get("providers") or {}).get(provider_key)
            if isinstance(provider, dict) and provider.get("apiKey"):
                profile = {
                    "type": "api",
                    "provider_name": str(provider.get("providerName") or "openai"),
                    "base_url": str(provider.get("baseUrl") or ""),
                    "wire_api": str(provider.get("api") or "openai-responses"),
                    "api_key": str(provider.get("apiKey") or ""),
                    "model": model_id,
                    "review_model": model_id,
                    "fingerprint": str(provider.get("fingerprint") or ""),
                }
                return self._identity_from_profile(profile)
        store = self.load_auth_store(self.primary_agent)
        profiles = store.get("profiles") or {}
        profile = profiles.get(CANONICAL_PROFILE)
        if not isinstance(profile, dict):
            return RuntimeSnapshot(target="openclaw", raw_profile={}, has_binding=False)
        return self._identity_from_profile(profile)

    def read_snapshot(self, snapshot_id: str) -> RuntimeSnapshot:
        """读取已保存的快照。"""

        path = self.snapshot_dir / f"{snapshot_id}.json"
        if not path.exists():
            return RuntimeSnapshot(target="openclaw", raw_profile={}, has_binding=False)
        return self._identity_from_profile(json.loads(path.read_text(encoding="utf-8")))

    def capture_current(self, snapshot_id: str) -> SnapshotBinding:
        """保存当前活跃 profile 到本地快照。"""

        snapshot = self.read_runtime_snapshot()
        if not snapshot.has_binding:
            raise ValueError("当前没有可导入的 OpenClaw 登录态")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{snapshot_id}.json"
        atomic_write_json(path, snapshot.raw_profile, mode=0o600)
        return SnapshotBinding(
            snapshot_id=snapshot_id,
            path=str(path),
            target="openclaw",
            email=snapshot.active_email,
        )

    def write_snapshot_profile(self, snapshot_id: str, profile: dict[str, Any]) -> RuntimeSnapshot:
        """把给定 profile 保存成 OpenClaw 快照。"""

        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{snapshot_id}.json"
        atomic_write_json(path, profile, mode=0o600)
        return self._identity_from_profile(profile)

    def write_api_snapshot(self, snapshot_id: str, profile: ApiProfile | dict[str, Any]) -> RuntimeSnapshot:
        """把第三方 API 配置保存成 OpenClaw 可切换快照。"""

        if not isinstance(profile, ApiProfile):
            profile = ApiProfile.model_validate(profile)
        profile = ensure_api_profile_fingerprint(profile)
        return self.write_snapshot_profile(
            snapshot_id,
            {
                "type": "api",
                "provider_name": profile.provider_name,
                "base_url": normalize_base_url(profile.base_url),
                "wire_api": profile.wire_api,
                "requires_openai_auth": profile.requires_openai_auth,
                "api_key": profile.api_key,
                "model": profile.model,
                "review_model": profile.review_model or profile.model,
                "model_reasoning_effort": profile.model_reasoning_effort,
                "model_context_window": profile.model_context_window,
                "model_auto_compact_token_limit": profile.model_auto_compact_token_limit,
                "fingerprint": profile.fingerprint,
            },
        )

    def delete_snapshot(self, snapshot_id: str) -> None:
        """删除本地快照，不影响当前运行时。"""

        path = self.snapshot_dir / f"{snapshot_id}.json"
        if path.exists():
            path.unlink()

    def _email_profile_id(self, email: str | None) -> str:
        """返回邮箱别名 profile id。"""

        if email:
            return f"openai-codex:{email}"
        return CANONICAL_PROFILE

    def activate_snapshot(self, snapshot_id: str) -> RuntimeSnapshot:
        """把指定快照写回 OpenClaw 运行时。"""

        path = self.snapshot_dir / f"{snapshot_id}.json"
        profile = json.loads(path.read_text(encoding="utf-8"))
        if profile.get("type") == "api":
            return self._activate_api_profile(profile)
        self.restore_default_config()
        runtime = self._identity_from_profile(profile)
        email_profile = self._email_profile_id(runtime.active_email)
        for agent_id in self.configured_agents():
            store = self.load_auth_store(agent_id)
            profiles = store.setdefault("profiles", {})
            profiles[CANONICAL_PROFILE] = profile
            if email_profile != CANONICAL_PROFILE:
                profiles[email_profile] = profile
            atomic_write_json(self.auth_path_for_agent(agent_id), store, mode=0o600)
        config = self.read_openclaw_config()
        auth = config.setdefault("auth", {})
        profiles = auth.setdefault("profiles", {})
        profiles[CANONICAL_PROFILE] = {"provider": "openai-codex", "mode": "oauth"}
        if email_profile != CANONICAL_PROFILE:
            profiles[email_profile] = {
                "provider": "openai-codex",
                "mode": "oauth",
                "email": runtime.active_email,
            }
        order = auth.setdefault("order", {})
        existing = order.get("openai-codex") or []
        order["openai-codex"] = [
            CANONICAL_PROFILE,
            *([email_profile] if email_profile != CANONICAL_PROFILE else []),
            *[item for item in existing if item not in {CANONICAL_PROFILE, email_profile}],
        ]
        agents = config.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        model_cfg = defaults.setdefault("model", {})
        model_cfg["primary"] = DEFAULT_OAUTH_MODEL
        default_models = defaults.setdefault("models", {})
        if isinstance(default_models, dict):
            default_models.setdefault(DEFAULT_OAUTH_MODEL, {})
        atomic_write_json(self.config_path, config)
        return runtime

    def _activate_api_profile(self, profile: dict[str, Any]) -> RuntimeSnapshot:
        """把第三方 API 账号写回 OpenClaw 主配置。"""

        runtime = self._identity_from_profile(profile)
        self._backup_config_if_needed()
        config = self.read_openclaw_config()
        models = config.setdefault("models", {})
        providers = models.setdefault("providers", {})
        provider_key = f"cma-api-{runtime.api_key_fingerprint or runtime.active_account_id or 'default'}"
        model_id = str(profile.get("model") or "gpt-5.4")
        review_model = str(profile.get("review_model") or model_id)
        base_url = normalize_base_url(str(profile.get("base_url") or ""))
        api_name = str(profile.get("provider_name") or "openai")
        provider_payload = {
            "name": api_name,
            "providerName": api_name,
            "baseUrl": base_url,
            "apiKey": str(profile.get("api_key") or ""),
            "api": "openai-responses"
            if str(profile.get("wire_api") or "responses") == "responses"
            else "openai-completions",
            "fingerprint": runtime.api_key_fingerprint,
            "models": [],
        }
        for current_model in [model_id, review_model]:
            if not current_model:
                continue
            provider_payload["models"].append(
                {
                    "id": current_model,
                    "name": current_model,
                    "reasoning": True,
                    "input": ["text", "image"],
                    "cost": {
                        "input": 0,
                        "output": 0,
                        "cacheRead": 0,
                        "cacheWrite": 0,
                    },
                    "contextWindow": int(profile.get("model_context_window") or 1_000_000),
                    "maxTokens": int(profile.get("model_auto_compact_token_limit") or 128_000),
                }
            )
        providers[provider_key] = provider_payload
        agents = config.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        model_cfg = defaults.setdefault("model", {})
        model_cfg["primary"] = f"{provider_key}/{model_id}"
        default_models = defaults.setdefault("models", {})
        if isinstance(default_models, dict):
            default_models[f"{provider_key}/{model_id}"] = {}
            default_models[f"{provider_key}/{review_model}"] = {}
        atomic_write_json(self.config_path, config)
        return runtime

    def list_recent_active_sessions(self, active_minutes: float) -> list[dict[str, Any]]:
        """列出最近活跃的 OpenClaw 会话。"""

        if active_minutes <= 0:
            return []
        now_ms = int(time.time() * 1000)
        threshold_ms = int(active_minutes * 60 * 1000)
        rows: list[dict[str, Any]] = []
        for agent_id in self.configured_agents():
            sessions_path = self.openclaw_home / "agents" / agent_id / "sessions" / "sessions.json"
            if not sessions_path.exists():
                continue
            store = json.loads(sessions_path.read_text(encoding="utf-8"))
            for key, info in store.items():
                if ":cron:" in key or key.startswith("cron:"):
                    continue
                updated_at = int(info.get("updatedAt") or 0)
                age_ms = max(0, now_ms - updated_at)
                if age_ms <= threshold_ms:
                    rows.append({"key": key, "updatedAt": updated_at, "ageMs": age_ms})
        rows.sort(key=lambda item: item["updatedAt"], reverse=True)
        return rows
