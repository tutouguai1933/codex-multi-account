"""这个文件负责管理登录命令的运行状态，并在完成后尝试自动收编账号。"""

from __future__ import annotations

import os
import pty
import re
import signal
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from codex_multi_account.models.account import AccountRecord
from codex_multi_account.storage.json_store import JsonStore


class PtyLoginProcess:
    """包装带 PTY 的登录进程，供状态管理复用。"""

    def __init__(self, process: subprocess.Popen[str], output_stream: Any, master_fd: int) -> None:
        self._process = process
        self.stdout = output_stream
        self.pid = process.pid
        self._master_fd = master_fd

    def poll(self) -> int | None:
        """返回子进程退出码。"""

        return self._process.poll()

    def terminate(self) -> None:
        """终止子进程。"""

        self._process.terminate()

    def send_line(self, value: str) -> None:
        """向登录进程写入一行输入。"""

        os.write(self._master_fd, f"{value}\n".encode("utf-8"))


class LoginSessionInputError(ValueError):
    """描述登录输入提交失败。"""


@dataclass(slots=True)
class LoginSessionState:
    """描述某个目标当前或最近一次登录状态。"""

    target: str
    status: str = "idle"
    note: str = "未开始"
    pid: int | None = None
    command: list[str] = field(default_factory=list)
    started_at: int | None = None
    finished_at: int | None = None
    exit_code: int | None = None
    imported_account_id: str | None = None
    imported_label: str | None = None
    error: str | None = None
    auth_url: str | None = None
    awaiting_input: bool = False
    output_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转成接口可返回的字典。"""

        return asdict(self)


class LoginSessionManager:
    """管理 OpenClaw 和 Codex 的登录命令状态。"""

    def __init__(
        self,
        importers: dict[str, Callable[[], AccountRecord]],
        store: JsonStore,
        process_starter: Callable[[list[str]], Any] | None = None,
    ) -> None:
        self.importers = importers
        self.store = store
        self.process_starter = process_starter or self._default_process_starter
        self.commands = {
            "openclaw": ["openclaw", "models", "auth", "login", "--provider", "openai-codex"],
            "codex": ["codex", "login"],
        }
        self._lock = threading.Lock()
        self._states = self._load_states()
        self._processes: dict[str, Any | None] = {"openclaw": None, "codex": None}
        self._mark_interrupted_sessions()

    def _default_process_starter(self, command: list[str]) -> Any:
        """默认使用子进程启动登录命令。"""

        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            command,
            start_new_session=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=True,
        )
        os.close(slave_fd)
        output_stream = os.fdopen(master_fd, "r", encoding="utf-8", errors="ignore", buffering=1)
        return PtyLoginProcess(process, output_stream, master_fd)

    def _load_states(self) -> dict[str, LoginSessionState]:
        """从磁盘读取最近一次登录状态。"""

        payload = self.store.read(
            default={
                "targets": {
                    "openclaw": LoginSessionState(target="openclaw").to_dict(),
                    "codex": LoginSessionState(target="codex").to_dict(),
                }
            }
        )
        raw_targets = payload.get("targets", {})
        states = {
            "openclaw": LoginSessionState(**raw_targets.get("openclaw", LoginSessionState(target="openclaw").to_dict())),
            "codex": LoginSessionState(**raw_targets.get("codex", LoginSessionState(target="codex").to_dict())),
        }
        for state in states.values():
            cleaned_lines = [
                normalized
                for normalized in (
                    self._normalize_output_line(item)
                    for item in state.output_lines
                )
                if normalized is not None
            ]
            state.output_lines = cleaned_lines[-20:]
            state.awaiting_input = any(self._line_needs_user_input(item) for item in state.output_lines)
        return states

    def _persist(self) -> None:
        """把当前状态写回磁盘。"""

        self.store.write(
            {
                "targets": {
                    key: value.to_dict()
                    for key, value in self._states.items()
                }
            }
        )

    def _mark_interrupted_sessions(self) -> None:
        """服务重启后，把未完成状态改成可恢复可见的中断状态。"""

        changed = False
        for state in self._states.values():
            if state.status == "running":
                state.status = "interrupted"
                state.note = "服务已重启，上次登录流程被中断，请重新发起"
                state.finished_at = int(time.time())
                state.awaiting_input = False
                changed = True
        if changed:
            self._persist()

    def _append_output(self, target: str, line: str) -> None:
        """追加一行输出并尝试提取授权链接。"""

        sanitized = self._sanitize_sensitive_line(line)
        normalized = self._normalize_output_line(sanitized)
        with self._lock:
            state = self._states[target]
            if state.auth_url is None:
                match = re.search(r"https?://\S+", line)
                if match:
                    state.auth_url = match.group(0).rstrip(")]}>,")
            if self._line_needs_user_input(line):
                state.awaiting_input = True
                state.note = "请把授权码或完整回调地址粘贴到页面里提交"
            if normalized is None:
                self._persist()
                return
            state.output_lines = [*state.output_lines[-19:], normalized]
            self._persist()

    def _line_needs_user_input(self, line: str) -> bool:
        """判断一行输出是否在请求用户粘贴授权信息。"""

        normalized = line.lower()
        return "authorization code" in normalized or "redirect url" in normalized

    def _sanitize_sensitive_line(self, line: str) -> str:
        """隐藏不应该持久化到页面和本地状态里的敏感参数。"""

        lowered = line.lower()
        if "auth.openai.com/oauth/authorize" in lowered:
            return line
        if re.search(r"[?&]code=[^&\s]+", line):
            return "已收到回调地址（已隐藏敏感参数）"
        return line

    def _normalize_output_line(self, line: str) -> str | None:
        """清洗 PTY 输出，只保留页面里值得展示的内容。"""

        without_ansi = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", line)
        cleaned = re.sub(r"[\r\x00-\x08\x0b-\x1f\x7f]", "", without_ansi).strip()
        if not cleaned:
            return None
        if cleaned.startswith("]9;"):
            return None
        if "http" in cleaned or cleaned.startswith("Open:"):
            return cleaned
        semantic = re.sub(r"[│├└┘╭╮╯╰─◇◆◐◑◒◓■…· ]", "", cleaned)
        if len(semantic) < 4:
            return None
        if len(cleaned) < 4:
            return None
        if re.fullmatch(r"[◐◑◒◓■.…\-]+", cleaned):
            return None
        return cleaned

    def _attach_output_reader(self, target: str, process: Any) -> None:
        """后台读取登录命令输出，方便页面展示。"""

        stream = getattr(process, "stdout", None)
        if stream is None:
            return

        def reader() -> None:
            try:
                for raw_line in stream:
                    line = raw_line.strip()
                    if line:
                        self._append_output(target, line)
            except Exception:
                return

        thread = threading.Thread(target=reader, name=f"{target}-login-output", daemon=True)
        thread.start()

    def start(self, target: str) -> LoginSessionState:
        """启动某个目标的登录命令。"""

        current = self.snapshot(target)
        if current.status == "running":
            return current

        command = list(self.commands[target])
        now = int(time.time())
        try:
            process = self.process_starter(command)
        except FileNotFoundError as exc:
            state = LoginSessionState(
                target=target,
                status="unavailable",
                note="未找到登录命令",
                command=command,
                started_at=now,
                finished_at=now,
                error=str(exc),
            )
            self._states[target] = state
            self._processes[target] = None
            self._persist()
            return LoginSessionState(**state.to_dict())

        state = LoginSessionState(
            target=target,
            status="running",
            note="请在页面授权链接或服务终端里完成登录",
            pid=getattr(process, "pid", None),
            command=command,
            started_at=now,
            awaiting_input=False,
        )
        self._states[target] = state
        self._processes[target] = process
        self._persist()
        self._attach_output_reader(target, process)
        return LoginSessionState(**state.to_dict())

    def snapshot(self, target: str) -> LoginSessionState:
        """返回单个目标的最新状态。"""

        self._refresh_target(target)
        return LoginSessionState(**self._states[target].to_dict())

    def snapshot_all(self) -> dict[str, LoginSessionState]:
        """返回全部目标的最新状态。"""

        return {target: self.snapshot(target) for target in self._states}

    def record_output(self, target: str, line: str) -> None:
        """给测试或外部流程追加一行输出。"""

        self._append_output(target, line)

    def submit_input(self, target: str, value: str) -> LoginSessionState:
        """把页面提交的授权信息写回正在运行的登录进程。"""

        payload = value.strip()
        if not payload:
            raise LoginSessionInputError("login-input-empty")

        self._refresh_target(target)
        process = self._processes[target]
        state = self._states[target]
        if process is None or state.status != "running":
            raise LoginSessionInputError("login-not-running")

        sender = getattr(process, "send_line", None)
        if not callable(sender):
            raise LoginSessionInputError("login-input-unsupported")

        sender(payload)
        state.awaiting_input = False
        state.note = "已提交网页里的授权信息，等待登录完成"
        state.output_lines = [*state.output_lines[-19:], "已从页面提交授权信息"]
        self._persist()
        return LoginSessionState(**state.to_dict())

    def cancel(self, target: str) -> LoginSessionState:
        """取消某个目标当前运行中的登录。"""

        process = self._processes[target]
        state = self._states[target]
        if process is None:
            return LoginSessionState(**state.to_dict())

        try:
            pid = getattr(process, "pid", None)
            if pid:
                os.killpg(pid, signal.SIGTERM)
            else:
                process.terminate()
        except Exception:
            process.terminate()
        self._processes[target] = None
        state.status = "cancelled"
        state.note = "登录流程已取消"
        state.pid = None
        state.exit_code = -15
        state.finished_at = int(time.time())
        state.auth_url = None
        state.awaiting_input = False
        state.output_lines = []
        self._persist()
        return LoginSessionState(**state.to_dict())

    def _refresh_target(self, target: str) -> None:
        """刷新某个目标的运行状态。"""

        process = self._processes[target]
        if process is None:
            return

        exit_code = process.poll()
        if exit_code is None:
            self._states[target].status = "running"
            return

        state = self._states[target]
        state.finished_at = int(time.time())
        state.exit_code = exit_code
        state.pid = None
        self._processes[target] = None

        if exit_code != 0:
            state.status = "failed"
            state.note = f"登录命令已退出，退出码 {exit_code}"
            state.awaiting_input = False
            self._persist()
            return

        try:
            account = self.importers[target]()
        except Exception as exc:
            state.status = "completed"
            state.note = "登录命令已完成，请手动导入当前登录态"
            state.error = str(exc)
            state.awaiting_input = False
            self._persist()
            return

        state.status = "imported"
        state.note = f"登录完成，已收编 {account.label}"
        state.imported_account_id = account.id
        state.imported_label = account.label
        state.error = None
        state.awaiting_input = False
        self._persist()
