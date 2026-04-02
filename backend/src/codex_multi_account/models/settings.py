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

