"""这个文件验证登录会话状态管理。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codex_multi_account.models.account import AccountRecord
from codex_multi_account.services.login_session import LoginSessionManager
from codex_multi_account.storage.json_store import JsonStore


@dataclass
class FakeProcess:
    """模拟可轮询状态的子进程。"""

    pid: int
    exit_code: int | None = None
    submitted_inputs: list[str] | None = None

    def poll(self) -> int | None:
        """返回当前退出码。"""

        return self.exit_code

    def terminate(self) -> None:
        """模拟终止进程。"""

        self.exit_code = -15

    def send_line(self, value: str) -> None:
        """记录页面提交给登录进程的输入。"""

        if self.submitted_inputs is None:
            self.submitted_inputs = []
        self.submitted_inputs.append(value)


def make_account(account_id: str, label: str) -> AccountRecord:
    """构造最小账号对象。"""

    return AccountRecord(id=account_id, label=label)


def make_manager(tmp_path: Path, starter, importers=None) -> LoginSessionManager:
    """创建带持久化存储的登录管理器。"""

    return LoginSessionManager(
        importers=importers
        or {
            "openclaw": lambda: make_account("acct_1", "openclaw-main"),
            "codex": lambda: make_account("acct_2", "codex-main"),
        },
        store=JsonStore(tmp_path / "login_sessions.json"),
        process_starter=starter,
    )


def test_login_session_reports_running_after_start(tmp_path) -> None:
    """启动登录后应记录运行中状态。"""

    processes: list[FakeProcess] = []

    def starter(command: list[str]) -> FakeProcess:
        process = FakeProcess(pid=1234, exit_code=None)
        processes.append(process)
        return process

    manager = make_manager(tmp_path, starter)

    payload = manager.start("openclaw")

    assert payload.status == "running"
    assert payload.pid == 1234
    assert payload.target == "openclaw"


def test_login_session_auto_imports_after_success_exit(tmp_path) -> None:
    """登录命令成功结束后应自动收编当前登录态。"""

    process = FakeProcess(pid=1234, exit_code=None)

    def starter(command: list[str]) -> FakeProcess:
        return process

    manager = make_manager(tmp_path, starter)
    manager.start("openclaw")
    process.exit_code = 0

    payload = manager.snapshot("openclaw")

    assert payload.status == "imported"
    assert payload.imported_account_id == "acct_1"
    assert payload.imported_label == "openclaw-main"


def test_login_session_marks_failed_exit_code(tmp_path) -> None:
    """登录命令失败退出时应留下失败状态。"""

    process = FakeProcess(pid=1234, exit_code=None)

    def starter(command: list[str]) -> FakeProcess:
        return process

    manager = make_manager(tmp_path, starter)
    manager.start("codex")
    process.exit_code = 1

    payload = manager.snapshot("codex")

    assert payload.status == "failed"
    assert payload.exit_code == 1


def test_login_session_returns_existing_running_process_without_restart(tmp_path) -> None:
    """已有运行中的登录任务时，不应重复拉起第二个进程。"""

    started_commands: list[list[str]] = []

    def starter(command: list[str]) -> FakeProcess:
        started_commands.append(command)
        return FakeProcess(pid=1000 + len(started_commands), exit_code=None)

    manager = make_manager(tmp_path, starter)

    first = manager.start("codex")
    second = manager.start("codex")

    assert first.pid == second.pid
    assert len(started_commands) == 1


def test_login_session_persists_last_state_and_restores_after_restart(tmp_path) -> None:
    """服务重启后，应能看到上次登录状态而不是完全丢失。"""

    process = FakeProcess(pid=1234, exit_code=None)

    def starter(command: list[str]) -> FakeProcess:
        return process

    manager = make_manager(tmp_path, starter)
    manager.start("openclaw")

    restored = make_manager(tmp_path, starter=lambda command: FakeProcess(pid=9999))
    payload = restored.snapshot("openclaw")

    assert payload.status == "interrupted"
    assert payload.pid == 1234


def test_login_session_extracts_auth_url_from_output(tmp_path) -> None:
    """输出里出现授权地址时，应暴露给页面。"""

    manager = make_manager(tmp_path, starter=lambda command: FakeProcess(pid=1234, exit_code=None))
    manager.start("openclaw")

    manager.record_output(
        "openclaw",
        "Open: https://auth.openai.com/oauth/authorize?response_type=code",
    )
    payload = manager.snapshot("openclaw")

    assert payload.auth_url == "https://auth.openai.com/oauth/authorize?response_type=code"
    assert payload.output_lines[-1].startswith("Open:")


def test_login_session_marks_awaiting_input_after_prompt(tmp_path) -> None:
    """输出里出现粘贴提示后，应告诉页面可以提交授权信息。"""

    manager = make_manager(tmp_path, starter=lambda command: FakeProcess(pid=1234, exit_code=None))
    manager.start("openclaw")

    manager.record_output(
        "openclaw",
        "Paste the authorization code (or full redirect URL):",
    )
    payload = manager.snapshot("openclaw")

    assert payload.awaiting_input is True
    assert "粘贴" in payload.note


def test_login_session_can_submit_input_to_running_process(tmp_path) -> None:
    """页面提交的授权信息应送进正在运行的登录进程。"""

    process = FakeProcess(pid=1234, exit_code=None)

    def starter(command: list[str]) -> FakeProcess:
        return process

    manager = make_manager(tmp_path, starter)
    manager.start("openclaw")
    manager.record_output(
        "openclaw",
        "Paste the authorization code (or full redirect URL):",
    )

    payload = manager.submit_input("openclaw", "https://auth.openai.com/callback?code=abc")

    assert process.submitted_inputs == ["https://auth.openai.com/callback?code=abc"]
    assert payload.awaiting_input is False
    assert "已提交" in payload.note


def test_login_session_redacts_callback_code_from_output(tmp_path) -> None:
    """进程回显回调地址时，不应把授权码原样写进状态。"""

    manager = make_manager(tmp_path, starter=lambda command: FakeProcess(pid=1234, exit_code=None))
    manager.start("openclaw")

    manager.record_output(
        "openclaw",
        "…https://localhost:1455/auth/callback?code=secret-code&state=demo",
    )
    payload = manager.snapshot("openclaw")

    assert "secret-code" not in payload.output_lines[-1]
    assert payload.output_lines[-1] == "已收到回调地址（已隐藏敏感参数）"


def test_login_session_masks_callback_code_in_output(tmp_path) -> None:
    """如果 CLI 回显回调地址，页面和持久化状态不应保留敏感 code。"""

    manager = make_manager(tmp_path, starter=lambda command: FakeProcess(pid=1234, exit_code=None))
    manager.start("openclaw")

    manager.record_output(
        "openclaw",
        "…https://example.com/auth/callback?code=secret-token",
    )
    payload = manager.snapshot("openclaw")

    assert payload.output_lines[-1] == "已收到回调地址（已隐藏敏感参数）"


def test_login_session_can_be_cancelled(tmp_path) -> None:
    """运行中的登录任务应支持取消。"""

    process = FakeProcess(pid=1234, exit_code=None)

    def starter(command: list[str]) -> FakeProcess:
        return process

    manager = make_manager(tmp_path, starter)
    manager.start("codex")
    manager.record_output("codex", "Open: https://auth.openai.com/oauth/authorize?response_type=code")
    manager.record_output("codex", "Paste the authorization code (or full redirect URL):")
    payload = manager.cancel("codex")

    assert payload.status == "cancelled"
    assert payload.exit_code == -15
    assert payload.pid is None
    assert payload.auth_url is None
    assert payload.output_lines == []
