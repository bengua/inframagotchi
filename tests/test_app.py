"""Tests for the app entry point window options (no pywebview required)."""

from __future__ import annotations

import sys
import types
import unittest.mock as mock
from unittest import TestCase

if "webview" not in sys.modules:
    # app.py imports webview at module level; provide a stub when the real
    # pywebview is unavailable so the suite stays runnable in a bare env.
    sys.modules["webview"] = types.ModuleType("webview")

from app import PET_SIZE_DEFAULT, _window_kwargs


class WindowKwargsTests(TestCase):
    def test_standard_window_is_unchanged(self) -> None:
        # Without --pet the window must stay the opaque 480x600 one.
        kwargs = _window_kwargs("http://host:8080/", pet=False, pet_size=PET_SIZE_DEFAULT)
        self.assertEqual(
            kwargs,
            {
                "url": "http://host:8080/",
                "width": 480,
                "height": 600,
                "background_color": "#0a0a0e",
                "resizable": True,
            },
        )
        # No pet-only keys leak into the standard window.
        self.assertNotIn("frameless", kwargs)
        self.assertNotIn("transparent", kwargs)
        self.assertNotIn("on_top", kwargs)
        self.assertNotIn("easy_drag", kwargs)

    def test_pet_window_is_square_frameless_transparent_on_top(self) -> None:
        kwargs = _window_kwargs("http://host:8080/", pet=True, pet_size=PET_SIZE_DEFAULT)
        self.assertEqual(kwargs["width"], 240)
        self.assertEqual(kwargs["height"], 240)
        self.assertTrue(kwargs["frameless"])
        self.assertTrue(kwargs["transparent"])
        self.assertTrue(kwargs["on_top"])
        self.assertTrue(kwargs["easy_drag"])
        self.assertFalse(kwargs["resizable"])
        # Transparent background, not the opaque #0a0a0e.
        self.assertNotIn("background_color", kwargs)

    def test_pet_size_overrides_square_side(self) -> None:
        kwargs = _window_kwargs("http://host:8080/", pet=True, pet_size=320)
        self.assertEqual(kwargs["width"], 320)
        self.assertEqual(kwargs["height"], 320)

    def test_main_connect_pet_opens_pet_window(self) -> None:
        # Exercise main() client mode end-to-end with a mocked webview.
        with mock.patch.object(sys, "argv", ["app.py", "--connect", "http://u", "--pet"]):
            import app as app_module

            with mock.patch.object(app_module, "webview") as wv:
                app_module.main()
        wv.create_window.assert_called_once_with(
            "inframagotchi",
            url="http://u",
            width=240,
            height=240,
            frameless=True,
            transparent=True,
            on_top=True,
            easy_drag=True,
            resizable=False,
        )
        wv.start.assert_called_once_with()

    def test_main_connect_without_pet_keeps_standard_window(self) -> None:
        with mock.patch.object(sys, "argv", ["app.py", "--connect", "http://u"]):
            import app as app_module

            with mock.patch.object(app_module, "webview") as wv:
                app_module.main()
        wv.create_window.assert_called_once_with(
            "inframagotchi",
            url="http://u",
            width=480,
            height=600,
            background_color="#0a0a0e",
            resizable=True,
        )
        wv.start.assert_called_once_with()
