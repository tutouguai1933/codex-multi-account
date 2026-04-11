"""这个文件集中处理第三方 API 账号的指纹、配置清洗和公共字段转换。"""

from __future__ import annotations

from hashlib import md5

from codex_multi_account.models.account import ApiProfile


MANAGED_CODEX_CONFIG_KEYS = {
    "openai_base_url",
    "chatgpt_base_url",
}

LEGACY_CODEX_CONFIG_KEYS = {
    "model_provider",
}


def normalize_base_url(value: str) -> str:
    """规整 provider base_url，避免同义 URL 重复建号。"""

    return value.strip().rstrip("/")


def api_profile_fingerprint(
    provider_name: str,
    base_url: str,
    api_key: str,
    model: str,
) -> str:
    """根据关键字段生成稳定指纹。"""

    basis = "|".join(
        [
            provider_name.strip().lower(),
            normalize_base_url(base_url).lower(),
            api_key.strip(),
            model.strip(),
        ]
    )
    return f"api_{md5(basis.encode('utf-8')).hexdigest()[:16]}"


def ensure_api_profile_fingerprint(profile: ApiProfile) -> ApiProfile:
    """补齐 API 账号指纹。"""

    if profile.fingerprint:
        return profile
    return profile.model_copy(
        update={
            "fingerprint": api_profile_fingerprint(
                profile.provider_name,
                profile.base_url,
                profile.api_key,
                profile.model,
            )
        }
    )
