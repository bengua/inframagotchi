"""Safeguards of the test suite.

The current directory is global process state: several tests `os.chdir`
into a temporary directory that is then deleted, without ever coming
back. The process then stays in a directory that no longer exists, and ALL
the following tests inherit that state.

For a long time this broke nothing because no test launched a subprocess.
The first one that did — a route that ran a helper script — saw
the child interpreter die at startup on « OSError: failed to make path
absolute », return a silent code 1, and so a 503 where 200 was expected. The
test passed alone and failed in the suite: the signature of a pollution.

Restoring the cwd around every test makes this class of failure impossible,
rather than fixing one call at a time while waiting for the next.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _restore_current_directory():
    start = os.getcwd()
    yield
    try:
        os.chdir(start)
    except OSError:
        # The starting directory itself has disappeared: fall back to the
        # root rather than leave the process in the void.
        os.chdir("/")
