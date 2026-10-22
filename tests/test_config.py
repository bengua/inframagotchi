"""Tests for config discovery and parsing."""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path
from unittest import TestCase

from probes._config import (
    DEFAULT_CONFIG,
    active_config_path,
    active_config_text,
    find_config,
    load_config,
    save_config,
)


class ConfigTests(TestCase):
    def test_load_default_when_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            conf = load_config()
        self.assertEqual(conf, DEFAULT_CONFIG)

    def test_load_from_given_path(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write("""[[probe]]\ntype = "ping"\nhost = "1.1.1.1"\n""")
            path = Path(fh.name)
        try:
            conf = load_config(path)
            self.assertEqual(
                conf,
                {"probe": [{"type": "ping", "host": "1.1.1.1"}]},
            )
        finally:
            path.unlink()

    def test_find_config_env_override(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write("""[[probe]]\ntype = "service"\nunit = "foo"\n""")
            path = Path(fh.name)
        old = os.environ.get("INFRAMAGOTCHI_CONFIG")
        try:
            os.environ["INFRAMAGOTCHI_CONFIG"] = str(path)
            self.assertEqual(find_config(), path)
        finally:
            if old is None:
                os.environ.pop("INFRAMAGOTCHI_CONFIG", None)
            else:
                os.environ["INFRAMAGOTCHI_CONFIG"] = old
            path.unlink()

    def test_find_config_xdg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config" / "inframagotchi"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "inframagotchi.toml"
            config_file.write_text("""[[probe]]\ntype = "backup"\n""")
            old_xdg = os.environ.get("XDG_CONFIG_HOME")
            old_cwd = os.getcwd()
            try:
                os.environ["XDG_CONFIG_HOME"] = str(Path(tmp) / "config")
                os.chdir(tempfile.mkdtemp())
                self.assertEqual(find_config(), config_file)
            finally:
                if old_xdg is None:
                    os.environ.pop("XDG_CONFIG_HOME", None)
                else:
                    os.environ["XDG_CONFIG_HOME"] = old_xdg
                os.chdir(old_cwd)

    def test_invalid_toml_fallback(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write("this is not valid toml = ")
            path = Path(fh.name)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                conf = load_config(path)
                self.assertEqual(conf, DEFAULT_CONFIG)
            self.assertTrue(any("Invalid config" in str(w.message) for w in caught))
        finally:
            path.unlink()

    def test_probe_must_be_table_or_array(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write("""probe = "nope"\n""")
            path = Path(fh.name)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                conf = load_config(path)
                self.assertEqual(conf, DEFAULT_CONFIG)
            self.assertTrue(any("must be a table or array" in str(w.message) for w in caught))
        finally:
            path.unlink()

    def test_load_preserves_avatar_key(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write('{"avatar": "avatars/dog.html", "probe": [{"type": "disk", "path": "/"}]}')
            path = Path(fh.name)
        try:
            conf = load_config(path)
            self.assertEqual(conf.get("avatar"), "avatars/dog.html")
            self.assertEqual(conf["probe"], [{"type": "disk", "path": "/"}])
        finally:
            path.unlink()


class SaveConfigTests(TestCase):
    def test_save_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inframagotchi.json"
            text = '{"probe": [{"type": "disk", "path": "/", "interval": 10}]}'
            result = save_config(text, path)
            self.assertEqual(result, path)
            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_save_updates_active_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inframagotchi.json"
            text = '{"probe": []}'
            save_config(text, path)
            self.assertEqual(active_config_path(), path)
            self.assertEqual(active_config_text(), text)

    def test_save_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inframagotchi.json"
            with self.assertRaises(ValueError) as ctx:
                save_config("this is not json", path)
            self.assertIn("Invalid config", str(ctx.exception))

    def test_save_rejects_bad_probe_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inframagotchi.json"
            with self.assertRaises(ValueError) as ctx:
                save_config('{"probe": "nope"}', path)
            self.assertIn("probe", str(ctx.exception).lower())

    def test_save_rejects_non_string_avatar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inframagotchi.json"
            with self.assertRaises(ValueError) as ctx:
                save_config('{"probe": [], "avatar": 123}', path)
            self.assertIn("avatar", str(ctx.exception).lower())

    def test_save_creates_file_when_none_specified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from probes import _config

            old_path = _config.active_config_path()
            _config._active_path = None
            os.chdir(tmp)
            try:
                text = '{"probe": []}'
                result = save_config(text)
                self.assertEqual(result, Path(tmp) / "inframagotchi.json")
            finally:
                _config._active_path = old_path
