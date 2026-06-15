"""Utility helpers for detecting and clearing TCP port conflicts.

Typical usage before starting a local service (e.g. the FastAPI dev server on
port 8000)::

    from novels_project.utils.port_utils import ensure_port_free
    if ensure_port_free(8000):
        print("Port 8000 is free")
    else:
        print("Port 8000 is occupied; stop the process manually")

The implementation uses ``lsof`` which is available on macOS and Linux.  If no
process is found the function returns ``True`` and does nothing.
"""

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, List, Sequence

from pwd import getpwuid


@dataclass(frozen=True)
class PortProcess:
    """A process currently listening on a TCP port."""

    pid: int
    user: str
    command: str


def _get_current_username() -> str:
    """Return the current OS username when available."""
    try:
        return getpwuid(os.getuid()).pw_name
    except Exception:
        return os.environ.get("USERNAME", "")


def _parse_lsof_output(output: str) -> List[PortProcess]:
    """Parse ``lsof -i :<port>`` output into port process records."""
    lines = output.strip().splitlines()
    processes: List[PortProcess] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        command, pid_text, user = parts[:3]
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        processes.append(PortProcess(pid=pid, user=user, command=command))
    return processes


def _list_processes_using_port(port: int) -> List[PortProcess]:
    """Return processes that are listening on *port*.

    The function runs ``lsof -i :<port>`` and parses the output. If the port is
    not in use, an empty list is returned.
    """
    try:
        output = subprocess.check_output(["lsof", "-i", f":{port}"], text=True)
    except subprocess.CalledProcessError:
        # ``lsof`` exits with non-zero when no matches are found.
        return []
    return _parse_lsof_output(output)


def _list_pids_using_port(port: int) -> List[int]:
    """Return a list of PIDs that are listening on *port*."""
    return [process.pid for process in _list_processes_using_port(port)]


def _get_process_command(process: PortProcess) -> str:
    """Return the full command line for a process, falling back to lsof command."""
    try:
        command = subprocess.check_output(
            ["ps", "-p", str(process.pid), "-o", "command="],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return process.command
    return command or process.command


def _matches_app_pattern(command: str, patterns: Sequence[str]) -> bool:
    """Return True if *command* matches any application-owned pattern."""
    return any(pattern and pattern in command for pattern in patterns)


def _process_is_running(pid: int) -> bool:
    """Return True if *pid* still exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_process(process: PortProcess) -> bool:
    """Gracefully terminate a process, escalating only after SIGTERM fails."""
    try:
        os.kill(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False

    # Give the process a short window to exit cleanly.
    for _ in range(10):
        if not _process_is_running(process.pid):
            return True
        time.sleep(0.05)

    # Escalate only for processes we already verified as current-user + app-owned.
    try:
        os.kill(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False

    return not _process_is_running(process.pid)


def ensure_port_free(
    port: int,
    *,
    allow_kill: bool = False,
    app_process_patterns: Sequence[str] | None = None,
    confirm_kill: Callable[[PortProcess], bool] | None = None,
) -> bool:
    """Detect whether *port* is occupied.

    By default this function is read-only: it detects occupied ports and returns
    ``False`` without killing anything.  This avoids accidentally terminating
    unrelated user or system services.

    When ``allow_kill=True``, only processes that satisfy all safety checks are
    terminated:

    * the process belongs to the current OS user
    * the full command line matches one of ``app_process_patterns``
    * ``confirm_kill`` returns ``True`` when provided

    Returns ``True`` if the port is free after detection/termination, ``False``
    if it is still occupied.
    """
    processes = _list_processes_using_port(port)
    if not processes:
        return True

    if not allow_kill:
        return False

    patterns = tuple(app_process_patterns or ("novels_project",))
    current_user = _get_current_username()
    candidates = [
        process
        for process in processes
        if process.user == current_user
        and _matches_app_pattern(_get_process_command(process), patterns)
    ]

    if not candidates:
        return False

    terminated = 0
    for process in candidates:
        if confirm_kill and not confirm_kill(process):
            continue
        if _terminate_process(process):
            terminated += 1

    # Re-check the port using the same source of truth as detection.
    return not _list_pids_using_port(port) or terminated == len(candidates)
