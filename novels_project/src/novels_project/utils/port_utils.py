"""Utility helpers for detecting and clearing TCP port conflicts.

Typical usage before starting a local service (e.g. the FastAPI dev server on
port 8000)::

    from novels_project.utils.port_utils import ensure_port_free
    if ensure_port_free(8000):
        print("Killed existing process on port 8000")
    # now start the service …

The implementation uses ``lsof`` which is available on macOS and Linux.  If no
process is found the function returns ``False`` and does nothing.
"""

import os
import signal
import subprocess
from typing import List

def _list_pids_using_port(port: int) -> List[int]:
    """Return a list of PIDs that are listening on *port*.

    The function runs ``lsof -i :<port>`` and parses the output.  If the port is
    not in use, an empty list is returned.
    """
    try:
        output = subprocess.check_output(["lsof", "-i", f":{port}"], text=True)
    except subprocess.CalledProcessError:
        # ``lsof`` exits with non‑zero when no matches are found.
        return []
    lines = output.strip().splitlines()
    # Skip the header line (e.g. "COMMAND   PID USER   FD ...")
    pids: List[int] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            try:
                pids.append(int(parts[1]))
            except ValueError:
                continue
    return pids

def ensure_port_free(port: int) -> bool:
    """Detect a process occupying *port* and kill it.

    Returns ``True`` if a process was found and terminated, ``False`` otherwise.
    The function uses ``SIGKILL`` (``kill -9``) to guarantee termination.
    """
    pids = _list_pids_using_port(port)
    if not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            # Process already exited between detection and kill.
            continue
    return True
