"""Tests for safe TCP port conflict handling."""

import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from novels_project.utils.port_utils import PortProcess, ensure_port_free


@pytest.fixture
def current_user() -> str:
    """Return the current OS username used by port_utils."""
    from novels_project.utils import port_utils

    return port_utils._get_current_username()


def test_ensure_port_free_returns_true_when_port_is_free():
    with patch("novels_project.utils.port_utils._list_processes_using_port", return_value=[]):
        assert ensure_port_free(8000) is True


def test_ensure_port_free_does_not_kill_by_default(current_user):
    occupied = [PortProcess(pid=123, user=current_user, command="nginx")]

    with patch("novels_project.utils.port_utils._list_processes_using_port", return_value=occupied), \
         patch("novels_project.utils.port_utils.os.kill") as kill_mock:
        assert ensure_port_free(8000) is False
        kill_mock.assert_not_called()


def test_ensure_port_free_does_not_kill_other_user_processes(current_user):
    other_user = "root" if current_user != "root" else "daemon"
    occupied = [PortProcess(pid=456, user=other_user, command="uvicorn novels_project.api.server:app")]

    with patch("novels_project.utils.port_utils._list_processes_using_port", return_value=occupied), \
         patch("novels_project.utils.port_utils.os.kill") as kill_mock:
        assert ensure_port_free(8000, allow_kill=True) is False
        kill_mock.assert_not_called()


def test_ensure_port_free_does_not_kill_non_app_processes(current_user):
    occupied = [PortProcess(pid=789, user=current_user, command="nginx")]

    with patch("novels_project.utils.port_utils._list_processes_using_port", return_value=occupied), \
         patch("novels_project.utils.port_utils.os.kill") as kill_mock:
        assert ensure_port_free(8000, allow_kill=True) is False
        kill_mock.assert_not_called()


def test_ensure_port_free_kills_current_user_app_process(current_user):
    occupied = [PortProcess(pid=1001, user=current_user, command="python")]

    with patch("novels_project.utils.port_utils._list_processes_using_port", return_value=occupied), \
         patch("novels_project.utils.port_utils._get_process_command", return_value="python -m novels_project.api.server:app"), \
         patch("novels_project.utils.port_utils._terminate_process", return_value=True) as terminate_mock:
        assert ensure_port_free(8000, allow_kill=True) is True
        terminate_mock.assert_called_once_with(occupied[0])


def test_ensure_port_free_respects_confirm_kill(current_user):
    occupied = [PortProcess(pid=1002, user=current_user, command="python")]

    with patch("novels_project.utils.port_utils._list_processes_using_port", return_value=occupied), \
         patch("novels_project.utils.port_utils._get_process_command", return_value="python -m novels_project.api.server:app"), \
         patch("novels_project.utils.port_utils._terminate_process") as terminate_mock:
        assert ensure_port_free(8000, allow_kill=True, confirm_kill=lambda _: False) is False
        terminate_mock.assert_not_called()


def test_terminate_process_escalates_to_sigkill_after_sigterm_fails():
    process = PortProcess(pid=2001, user="tester", command="python")
    # Process stays alive for all 10 SIGTERM wait iterations, then dies after SIGKILL
    running = [True] * 11  # 10 wait checks + 1 final check after SIGKILL
    running[-1] = False  # dead after SIGKILL

    def kill_side_effect(pid, sig):
        assert pid == process.pid
        if sig == signal.SIGTERM:
            return None
        if sig == signal.SIGKILL:
            return None
        raise AssertionError(f"unexpected signal: {sig}")

    def is_running_side_effect(pid):
        assert pid == process.pid
        return running.pop(0)

    with patch("novels_project.utils.port_utils.os.kill", side_effect=kill_side_effect), \
         patch("novels_project.utils.port_utils._process_is_running", side_effect=is_running_side_effect):
        from novels_project.utils import port_utils

        assert port_utils._terminate_process(process) is True
        calls = port_utils.os.kill.call_args_list
        assert calls[0].args == (process.pid, signal.SIGTERM)
        assert calls[1].args == (process.pid, signal.SIGKILL)


def test_parse_lsof_output():
    output = """COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
python   1234 winston   10u  IPv4 12345      0t0  TCP *:8000 (LISTEN)
nginx    5678 nobody     6u  IPv4 67890      0t0  TCP *:8000 (LISTEN)
"""
    from novels_project.utils import port_utils

    processes = port_utils._parse_lsof_output(output)

    assert processes == [
        PortProcess(pid=1234, user="winston", command="python"),
        PortProcess(pid=5678, user="nobody", command="nginx"),
    ]


def test_subprocess_called_process_error_means_port_is_free():
    with patch("novels_project.utils.port_utils.subprocess.check_output", side_effect=subprocess.CalledProcessError(1, ["lsof"])):
        from novels_project.utils import port_utils

        assert port_utils._list_processes_using_port(8000) == []
