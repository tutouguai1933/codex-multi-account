"""这个文件根据健康度、阈值和分流策略决定自动切换结果。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from codex_multi_account.adapters.openclaw import OpenClawAdapter
from codex_multi_account.models.account import AccountRecord, EventRecord
from codex_multi_account.models.settings import SchedulerSettings
from codex_multi_account.services.account_pool import AccountPoolService
from codex_multi_account.services.probe_service import ProbeService
from codex_multi_account.services.switch_service import SwitchService
from codex_multi_account.storage.event_log import EventLog
from codex_multi_account.storage.json_store import JsonStore


@dataclass(slots=True)
class SchedulerResult:
    """描述一次调度的输出。"""

    assignments: dict[str, str | None]
    actions: dict[str, str]
    reason: str
    forced_immediate: bool = False
    events: list[EventRecord] = field(default_factory=list)


class SchedulerEngine:
    """负责按策略自动分配账号。"""

    def __init__(
        self,
        settings_store: JsonStore,
        account_pool: AccountPoolService,
        switch_service: SwitchService,
        probe_service: ProbeService,
        event_log: EventLog,
        openclaw_adapter: OpenClawAdapter,
    ) -> None:
        self.settings_store = settings_store
        self.account_pool = account_pool
        self.switch_service = switch_service
        self.probe_service = probe_service
        self.event_log = event_log
        self.openclaw_adapter = openclaw_adapter

    def _settings(self) -> SchedulerSettings:
        """读取调度设置。"""

        payload = self.settings_store.read(default=SchedulerSettings().model_dump(mode="json"))
        return SchedulerSettings.model_validate(payload)

    def _is_account_usable(self, account: AccountRecord) -> bool:
        """判断账号是否总体可用。"""

        return account.status.health not in {
            "auth-invalid",
            "plan-unavailable",
            "manual-disabled",
            "missing-binding",
        }

    def _threshold_score(self, account: AccountRecord) -> tuple[float, float]:
        """把额度转成可排序分数，越小越优。"""

        five = account.quota.five_hour_used_pct
        weekly = account.quota.weekly_used_pct
        return (
            float(five) if five is not None else 10_000.0,
            float(weekly) if weekly is not None else 10_000.0,
        )

    def _exceeds_soft_limit(self, account: AccountRecord, settings: SchedulerSettings) -> bool:
        """判断账号是否触发任一软阈值。"""

        five = account.quota.five_hour_used_pct
        weekly = account.quota.weekly_used_pct
        return bool(
            (five is not None and five >= settings.thresholds.five_hour_switch_at)
            or (weekly is not None and weekly >= settings.thresholds.weekly_switch_at)
        )

    def _exceeds_hard_limit(self, account: AccountRecord, settings: SchedulerSettings) -> bool:
        """判断账号是否触发任一硬阈值。"""

        five = account.quota.five_hour_used_pct
        weekly = account.quota.weekly_used_pct
        return bool(
            (five is not None and five >= settings.thresholds.hard_five_hour_switch_at)
            or (weekly is not None and weekly >= settings.thresholds.hard_weekly_switch_at)
        )

    def _pick_for_target(
        self,
        target: str,
        accounts: list[AccountRecord],
        avoid_account_id: str | None = None,
    ) -> AccountRecord | None:
        """按目标选出最优账号。"""

        candidates: list[AccountRecord] = []
        for account in accounts:
            binding = account.bindings.openclaw if target == "openclaw" else account.bindings.codex
            if not binding.snapshot_id:
                continue
            if not self._is_account_usable(account):
                continue
            if avoid_account_id and account.id == avoid_account_id:
                continue
            candidates.append(account)
        if not candidates:
            return None
        candidates.sort(key=self._threshold_score)
        return candidates[0]

    def _event(self, level: str, reason: str, message: str, target: str | None = None, account_id: str | None = None) -> EventRecord:
        """构造并落盘事件。"""

        event = EventRecord(
            type="scheduler",
            level=level,
            reason=reason,
            message=message,
            target=target,
            account_id=account_id,
            created_at=int(time.time()),
        )
        self.event_log.append(event.model_dump(mode="json"))
        return event

    def _select_openclaw_choice(
        self,
        accounts: list[AccountRecord],
        current_openclaw: AccountRecord | None,
        current_codex: AccountRecord | None,
        settings: SchedulerSettings,
        blocked_sessions: list[dict[str, object]],
        force_rebalance: bool = False,
    ) -> tuple[AccountRecord | None, str | None, list[EventRecord]]:
        """为 OpenClaw 选择本轮应使用的账号。"""

        events: list[EventRecord] = []
        avoid_account_id = (
            current_codex.id
            if (
                settings.prefer_separation
                and current_codex
                and (current_openclaw is None or current_codex.id != current_openclaw.id)
            )
            else None
        )
        if current_openclaw and self._is_account_usable(current_openclaw):
            if force_rebalance:
                if blocked_sessions and not self._exceeds_hard_limit(current_openclaw, settings):
                    events.append(
                        self._event(
                            "warning",
                            "blocked-active-session",
                            "OpenClaw 当前仍有活跃会话，暂不执行立即重算。",
                            target="openclaw",
                            account_id=current_openclaw.id,
                        )
                    )
                    return current_openclaw, "blocked-active-session", events
                candidate = self._pick_for_target(
                    "openclaw",
                    accounts,
                    avoid_account_id=avoid_account_id,
                ) or self._pick_for_target("openclaw", accounts)
                return candidate or current_openclaw, None, events
            if self._exceeds_soft_limit(current_openclaw, settings):
                if blocked_sessions and not self._exceeds_hard_limit(current_openclaw, settings):
                    events.append(
                        self._event(
                            "warning",
                            "blocked-active-session",
                            "OpenClaw 当前只达到软阈值，且仍有活跃会话，暂不切换。",
                            target="openclaw",
                            account_id=current_openclaw.id,
                        )
                    )
                    return current_openclaw, "blocked-active-session", events
                candidate = self._pick_for_target(
                    "openclaw",
                    accounts,
                    avoid_account_id=avoid_account_id,
                ) or self._pick_for_target("openclaw", accounts)
                return candidate or current_openclaw, None, events
            return current_openclaw, None, events
        candidate = self._pick_for_target(
            "openclaw",
            accounts,
            avoid_account_id=avoid_account_id,
        ) or self._pick_for_target("openclaw", accounts)
        return candidate, None, events

    def _select_codex_choice(
        self,
        accounts: list[AccountRecord],
        current_codex: AccountRecord | None,
        openclaw_choice: AccountRecord | None,
        settings: SchedulerSettings,
        force_rebalance: bool = False,
    ) -> tuple[AccountRecord | None, str]:
        """为 Codex 选择本轮应使用的账号。"""

        avoid_account_id = openclaw_choice.id if (settings.prefer_separation and openclaw_choice) else None
        if force_rebalance:
            candidate = self._pick_for_target("codex", accounts, avoid_account_id=avoid_account_id)
            if candidate is not None:
                return candidate, "separated-targets"
            fallback = self._pick_for_target("codex", accounts)
            return fallback, "same-account-fallback"
        if current_codex and self._is_account_usable(current_codex):
            if avoid_account_id and current_codex.id != avoid_account_id and not self._exceeds_soft_limit(current_codex, settings):
                return current_codex, "separated-targets"
            if not avoid_account_id and not self._exceeds_soft_limit(current_codex, settings):
                return current_codex, "separated-targets"

        candidate = self._pick_for_target("codex", accounts, avoid_account_id=avoid_account_id)
        if candidate is not None:
            return candidate, "separated-targets"
        fallback = self._pick_for_target("codex", accounts)
        return fallback, "same-account-fallback"

    def run_once(self, force_rebalance: bool = False) -> SchedulerResult:
        """执行一次自动调度。"""

        settings = self._settings()
        accounts = self.probe_service.probe_all()
        openclaw_runtime = self.account_pool.openclaw.read_runtime_snapshot()
        codex_runtime = self.account_pool.codex.read_runtime_snapshot()
        current_openclaw = (
            self.account_pool.resolve_account_for_runtime(openclaw_runtime)
            if openclaw_runtime.has_binding
            else None
        )
        current_codex = (
            self.account_pool.resolve_account_for_runtime(codex_runtime)
            if codex_runtime.has_binding
            else None
        )

        blocked_sessions = self.openclaw_adapter.list_recent_active_sessions(settings.inactive_minutes)
        openclaw_choice, openclaw_reason, events = self._select_openclaw_choice(
            accounts,
            current_openclaw,
            current_codex,
            settings,
            blocked_sessions,
            force_rebalance=force_rebalance,
        )
        if openclaw_reason == "blocked-active-session" and current_openclaw is not None:
            codex_choice, codex_reason = self._select_codex_choice(
                accounts,
                current_codex,
                current_openclaw,
                settings,
                force_rebalance=force_rebalance,
            )
            return SchedulerResult(
                assignments={
                    "openclaw": current_openclaw.id,
                    "codex": codex_choice.id if codex_choice else None,
                },
                actions={
                    "openclaw": "blocked-active-session",
                    "codex": "keep" if current_codex and codex_choice and current_codex.id == codex_choice.id else (codex_reason if codex_choice is None else "switched"),
                },
                reason="blocked-active-session",
                forced_immediate=force_rebalance,
                events=events,
            )

        if openclaw_choice is None:
            codex_choice, codex_reason = self._select_codex_choice(
                accounts,
                current_codex,
                None,
                settings,
                force_rebalance=force_rebalance,
            )
            event = self._event(
                "warning",
                "no-openclaw-candidate",
                "当前没有可用于 OpenClaw 的账号，已保留现有分配。",
                target="openclaw",
            )
            return SchedulerResult(
                assignments={"openclaw": None, "codex": codex_choice.id if codex_choice else None},
                actions={
                    "openclaw": "no-candidate",
                    "codex": "keep" if current_codex and codex_choice and current_codex.id == codex_choice.id else ("none" if codex_choice is None else ("switched" if codex_reason != "same-account-fallback" or current_codex is None or current_codex.id != codex_choice.id else "keep")),
                },
                reason="no-openclaw-candidate",
                forced_immediate=force_rebalance,
                events=[event],
            )

        codex_choice, reason = self._select_codex_choice(
            accounts,
            current_codex,
            openclaw_choice,
            settings,
            force_rebalance=force_rebalance,
        )

        openclaw_action = "keep"
        codex_action = "keep"
        if current_openclaw is None or current_openclaw.id != openclaw_choice.id:
            self.switch_service.switch_target(openclaw_choice.id, "openclaw")
            openclaw_action = "switched"
        if codex_choice and (current_codex is None or current_codex.id != codex_choice.id):
            self.switch_service.switch_target(codex_choice.id, "codex")
            codex_action = "switched"
        elif codex_choice is None:
            codex_action = "none"

        event = self._event(
            "info",
            reason,
            "自动调度已完成账号分配。",
            account_id=openclaw_choice.id,
        )
        return SchedulerResult(
            assignments={
                "openclaw": openclaw_choice.id,
                "codex": codex_choice.id if codex_choice else None,
            },
            actions={"openclaw": openclaw_action, "codex": codex_action},
            reason=reason,
            forced_immediate=force_rebalance,
            events=[*events, event],
        )
