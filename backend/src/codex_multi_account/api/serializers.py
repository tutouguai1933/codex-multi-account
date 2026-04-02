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
    return {
        "identity": {
            "account_id": _pick_string(identity, "account_id"),
            "user_id": _pick_string(identity, "user_id"),
            "plan_type": _pick_string(identity, "plan_type"),
            "auth_mode": _pick_string(identity, "auth_mode"),
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
    }


def public_account_dict(account: AccountRecord) -> dict[str, object]:
    """返回安全的账号展示结构。"""

    payload = account.model_dump(mode="json")
    payload["metadata"] = _public_metadata(account)
    return payload
