"""这个文件定义账号、快照和事件模型，供适配器、调度器和 API 复用。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeSnapshot(BaseModel):
    """描述某个目标当前活跃登录态的标准化结果。"""

    target: str
    active_email: str | None = None
    active_account_id: str | None = None
    user_id: str | None = None
    plan_type: str | None = None
    expires: int | None = None
    auth_mode: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    raw_profile: dict[str, object] = Field(default_factory=dict)
    has_binding: bool = False


class SnapshotBinding(BaseModel):
    """描述账号池绑定的某个快照。"""

    snapshot_id: str
    path: str
    target: str
    email: str | None = None


class TargetBinding(BaseModel):
    """描述一个目标侧的快照绑定信息。"""

    snapshot_id: str | None = None
    available: bool = False


class AccountBindings(BaseModel):
    """描述账号在 OpenClaw 和 Codex 两侧的绑定情况。"""

    openclaw: TargetBinding = Field(default_factory=TargetBinding)
    codex: TargetBinding = Field(default_factory=TargetBinding)


class AccountStatus(BaseModel):
    """描述账号的整体健康状态。"""

    health: str = "quota-unknown"
    reason: str = "not-probed"
    manual_disabled: bool = False


class AccountQuota(BaseModel):
    """描述额度快照。"""

    five_hour_used_pct: float | None = None
    weekly_used_pct: float | None = None
    reset_at_five_hour: int | None = None
    reset_at_weekly: int | None = None


class AccountAssignments(BaseModel):
    """描述当前哪个目标在使用该账号。"""

    openclaw: bool = False
    codex: bool = False


class AccountTimestamps(BaseModel):
    """描述探测和分配时间。"""

    last_detected_at: int | None = None
    last_assigned_at: int | None = None


class AccountRecord(BaseModel):
    """描述统一账号池中的单个账号。"""

    id: str
    label: str
    email: str | None = None
    tags: list[str] = Field(default_factory=list)
    bindings: AccountBindings = Field(default_factory=AccountBindings)
    status: AccountStatus = Field(default_factory=AccountStatus)
    quota: AccountQuota = Field(default_factory=AccountQuota)
    assignment: AccountAssignments = Field(default_factory=AccountAssignments)
    timestamps: AccountTimestamps = Field(default_factory=AccountTimestamps)
    metadata: dict[str, object] = Field(default_factory=dict)


class EventRecord(BaseModel):
    """描述一条事件日志。"""

    type: str
    level: str
    reason: str
    message: str
    target: str | None = None
    account_id: str | None = None
    created_at: int
