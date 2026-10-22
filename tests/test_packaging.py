"""Tests that the installed package ships the web pages.

Without the ``web`` package in the distribution the installed entry point has
no ``index.html`` to serve and answers 404 on every page. The packaging must
therefore declare ``web`` as a package and carry all of its data files.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _toml() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


class WebPackagingTests(TestCase):
    def test_web_is_declared_as_a_package(self) -> None:
        # ``web`` must sit beside ``probes`` so its files land in the wheel.
        packages = _toml()["tool"]["setuptools"]["packages"]
        self.assertIn("web", packages)

    def test_web_package_data_covers_all_files(self) -> None:
        # Every web file (index.html and the avatars pages) must be bundled.
        package_data = _toml()["tool"]["setuptools"]["package-data"]
        self.assertIn("**/*", package_data.get("web", []))

    def test_web_is_importable_package(self) -> None:
        # A bare __init__.py makes ``web`` a regular package, not a namespace
        # one, so package-data resolution is deterministic.
        self.assertTrue((ROOT / "web" / "__init__.py").is_file())
