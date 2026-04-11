"""这个文件定义调度与页面会用到的设置模型。"""

from __future__ import annotations

from pydantic import BaseModel


class SchedulerThresholds(BaseModel):
    """描述软阈值和硬阈值。"""

    five_hour_switch_at: float = 80.0
    hard_five_hour_switch_at: float = 90.0
    weekly_switch_at: float = 90.0
    hard_weekly_switch_at: float = 95.0


class SchedulerSettings(BaseModel):
    """描述自动调度开关与策略。"""

    auto_refresh_enabled: bool = True
    refresh_interval_seconds: int = 600
    inactive_minutes: float = 3.0
    prefer_separation: bool = True
    thresholds: SchedulerThresholds = SchedulerThresholds()


class CodexQuickSettings(BaseModel):
    """描述配置页里常用的 Codex 基础字段。"""

    openai_base_url: str | None = None
    model: str | None = None
    review_model: str | None = None
    model_reasoning_effort: str | None = None
    fast_mode_enabled: bool | None = None
    model_context_window: int | None = None
    model_auto_compact_token_limit: int | None = None


class CodexRuntimeFiles(BaseModel):
    """描述 Codex 配置页要展示的原文和快捷字段。"""

    config_text: str
    auth_text: str
    quick_settings: CodexQuickSettings


class CodexRuntimeSaveRequest(BaseModel):
    """描述原文保存请求。"""

    config_text: str
    auth_text: str
