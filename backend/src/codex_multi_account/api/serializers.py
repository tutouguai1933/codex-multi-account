"""这个文件负责把账号模型转成适合前端展示的安全结构。"""

from __future__ import annotations

from codex_multi_account.models.account import AccountRecord


def _pick_string(source: dict[str, object], key: str) -> str | None:
    """从字典里读取字符串字段。"""

    value = source.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _public_metadata(account: AccountRecord) -> dict[str, object]:
    """只保留前端展示需要的元数据。"""

    metadata = account.metadata if isinstance(account.metadata, dict) else {}
    identity = metadata.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    exported = metadata.get("codex_export")
    exported = exported if isinstance(exported, dict) else {}
    api_profile = account.api_profile.model_dump(mode="json") if account.api_profile else None
    return {
        "identity": {
            "account_id": _pick_string(identity, "account_id"),
            "user_id": _pick_string(identity, "user_id"),
            "plan_type": _pick_string(identity, "plan_type"),
            "auth_mode": _pick_string(identity, "auth_mode"),
            "account_kind": _pick_string(identity, "account_kind"),
            "provider_name": _pick_string(identity, "provider_name"),
            "base_url": _pick_string(identity, "base_url"),
            "api_fingerprint": _pick_string(identity, "api_fingerprint"),
        },
        "codex_export": {
            "id": _pick_string(exported, "id"),
            "email": _pick_string(exported, "email"),
            "auth_mode": _pick_string(exported, "auth_mode"),
            "user_id": _pick_string(exported, "user_id"),
            "plan_type": _pick_string(exported, "plan_type"),
            "account_id": _pick_string(exported, "account_id"),
            "organization_id": exported.get("organization_id"),
            "account_name": _pick_string(exported, "account_name"),
            "account_structure": _pick_string(exported, "account_structure"),
            "usage_updated_at": exported.get("usage_updated_at"),
            "tags": exported.get("tags"),
            "created_at": exported.get("created_at"),
            "last_used": exported.get("last_used"),
        },
        "api_profile": None
        if api_profile is None
        else {
            "provider_name": api_profile.get("provider_name"),
            "base_url": api_profile.get("base_url"),
            "wire_api": api_profile.get("wire_api"),
            "requires_openai_auth": api_profile.get("requires_openai_auth"),
            "model": api_profile.get("model"),
            "review_model": api_profile.get("review_model"),
            "model_reasoning_effort": api_profile.get("model_reasoning_effort"),
            "disable_response_storage": api_profile.get("disable_response_storage"),
            "network_access": api_profile.get("network_access"),
            "windows_wsl_setup_acknowledged": api_profile.get("windows_wsl_setup_acknowledged"),
            "model_context_window": api_profile.get("model_context_window"),
            "model_auto_compact_token_limit": api_profile.get("model_auto_compact_token_limit"),
            "fingerprint": api_profile.get("fingerprint"),
            "has_api_key": bool(api_profile.get("api_key")),
        },
    }


def public_account_dict(account: AccountRecord) -> dict[str, object]:
    """返回安全的账号展示结构。"""

    payload = account.model_dump(mode="json")
    if account.api_profile is not None:
        payload["api_profile"] = {
            "provider_name": account.api_profile.provider_name,
            "base_url": account.api_profile.base_url,
            "wire_api": account.api_profile.wire_api,
            "requires_openai_auth": account.api_profile.requires_openai_auth,
            "model": account.api_profile.model,
            "review_model": account.api_profile.review_model,
            "model_reasoning_effort": account.api_profile.model_reasoning_effort,
            "disable_response_storage": account.api_profile.disable_response_storage,
            "network_access": account.api_profile.network_access,
            "windows_wsl_setup_acknowledged": account.api_profile.windows_wsl_setup_acknowledged,
            "model_context_window": account.api_profile.model_context_window,
            "model_auto_compact_token_limit": account.api_profile.model_auto_compact_token_limit,
            "fingerprint": account.api_profile.fingerprint,
            "has_api_key": True,
        }
    payload["metadata"] = _public_metadata(account)
    return payload
