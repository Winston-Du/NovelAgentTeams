"""Integration test fixtures.

This conftest.py applies to all tests in tests/integration/ and forces a short
HTTP timeout (5 seconds) so that tests performing real network calls (e.g.
``tests/integration/test_api_integration.py``) cannot hang indefinitely when
the target service is slow, unresponsive, or returns unexpected data.

Background
----------
The ``requests`` library delegates to ``urllib3`` which manages its own
connection pool and timeout configuration.  Setting
``socket.setdefaulttimeout()`` alone is **not sufficient** because
``urllib3`` opens sockets with explicit timeouts that override the socket
default.  We therefore monkeypatch ``requests.sessions.Session.request``
to inject a default ``timeout`` argument into every call when the caller
has not supplied one.  This is the same trick used by popular projects
such as ``pytest-httpserver`` and works regardless of the underlying
connection pool state.
"""

from typing import Any, Generator

import pytest
import requests

# Hard ceiling for any single HTTP request originating from a test in
# this directory.  Picked to be long enough for slow CI machines but
# short enough to keep the suite under a few minutes when the backend
# is unavailable.
DEFAULT_HTTP_TIMEOUT = 5

_original_session_request = requests.sessions.Session.request


def _patched_session_request(
    self: requests.sessions.Session,
    method: str,
    url: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Inject a default ``timeout`` argument when none was provided."""
    kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT)
    return _original_session_request(self, method, url, *args, **kwargs)


@pytest.fixture(autouse=True)
def _enforce_http_timeout() -> Generator[None, None, None]:
    """Force every integration test to use a 5-second HTTP timeout.

    The fixture installs the patched ``Session.request`` on entry and
    restores the original on exit so it does not leak across test files
    or affect production code.
    """
    requests.sessions.Session.request = _patched_session_request
    try:
        yield
    finally:
        requests.sessions.Session.request = _original_session_request
