"""Smoke tests for the optional Qt backend (the ``qt`` extra).

They run headless with ``QT_QPA_PLATFORM=offscreen`` and are skipped when
PyQt6 is not installed, so the core suite stays runnable without Qt.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

# Qt WebEngine must be imported before any QApplication exists, so try it at
# module load; the test below skips if it is not installed.
try:
    from PyQt6 import QtWebEngineWidgets
except ImportError:
    QtWebEngineWidgets = None


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_offscreen_window_has_the_requested_geometry(qapp) -> None:
    # Same size as the standard inframagotchi window built by app._window_kwargs.
    window = QtWidgets.QWidget()
    window.setWindowTitle("inframagotchi")
    window.resize(480, 600)
    window.show()
    qapp.processEvents()
    assert window.windowTitle() == "inframagotchi"
    assert (window.width(), window.height()) == (480, 600)
    window.close()


def test_qt_webengine_is_importable() -> None:
    # pywebview's Qt backend renders the pet through Qt WebEngine.
    if QtWebEngineWidgets is None:
        pytest.skip("PyQt6-WebEngine is not installed")
    assert hasattr(QtWebEngineWidgets, "QWebEngineView")
