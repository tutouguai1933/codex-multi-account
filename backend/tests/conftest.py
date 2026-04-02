"""这个文件负责测试共用的导入路径和 JWT 夹具。"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def make_jwt(email: str, account_id: str, user_id: str, plan: str = "team") -> str:
    """构造一个足够测试用的 JWT。"""

    def encode_segment(payload: dict[str, object]) -> str:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    header = {"alg": "none", "typ": "JWT"}
    body = {
        "email": email,
        "https://api.openai.com/profile": {"email": email, "email_verified": True},
        "https://api.openai.com/auth": {
            "chatgpt_account_id": account_id,
            "user_id": user_id,
            "chatgpt_plan_type": plan,
        },
    }
    return f"{encode_segment(header)}.{encode_segment(body)}.sig"

