"""Tests for the chain-run health probe."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase

from probes.chain import make_chain


def _write(path, state: str, mtime: float) -> None:
    Path(path).write_text(json.dumps({"state": state}))
    os.utime(path, (mtime, mtime))


class ChainProbeTests(TestCase):
    def _run(self, directory, params=None) -> float | None:
        _, probe = make_chain(params if params is not None else {"dir": str(directory)})
        return probe()

    def test_missing_directory_returns_none(self):
        self.assertIsNone(self._run("/nonexistent/records"))

    def test_default_directory_used_in_name(self):
        name, _ = make_chain({})
        self.assertEqual(name, "chain:runs/records")

    def test_all_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = time.time()
            _write(os.path.join(tmp, "a.json"), "ok", base + 1)
            _write(os.path.join(tmp, "b.json"), "ok", base + 2)
            self.assertEqual(self._run(tmp), 1.0)

    def test_fraction_of_good_states(self):
        # 2 good, 1 failed, 1 needs_human → 2/4 = 0.5
        with tempfile.TemporaryDirectory() as tmp:
            base = time.time()
            _write(os.path.join(tmp, "a.json"), "ok", base + 1)
            _write(os.path.join(tmp, "b.json"), "done", base + 2)
            _write(os.path.join(tmp, "c.json"), "failed", base + 3)
            _write(os.path.join(tmp, "d.json"), "needs_human", base + 4)
            self.assertEqual(self._run(tmp), 0.5)

    def test_only_most_recent_eight_counted(self):
        # 9 files, only the 8 newest are counted; the oldest is failed.
        # Newest 8 are all good → 1.0 even though the 9th (oldest) is failed.
        with tempfile.TemporaryDirectory() as tmp:
            base = time.time()
            _write(os.path.join(tmp, "old.json"), "failed", base)
            for i in range(8):
                _write(os.path.join(tmp, f"new{i}.json"), "ok", base + i + 1)
            self.assertEqual(self._run(tmp), 1.0)

    def test_empty_directory_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self._run(tmp))

    def test_non_json_files_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = time.time()
            _write(os.path.join(tmp, "a.json"), "ok", base + 1)
            with open(os.path.join(tmp, "b.txt"), "w") as fh:
                fh.write("not json")
            self.assertEqual(self._run(tmp), 1.0)

    def test_malformed_record_treated_as_bad_but_no_exception(self):
        # A non-dict JSON record makes .get raise → caught → None (no crash).
        with tempfile.TemporaryDirectory() as tmp:
            base = time.time()
            _write(os.path.join(tmp, "a.json"), "ok", base + 1)
            with open(os.path.join(tmp, "bad.json"), "w") as fh:
                fh.write("[1, 2, 3]")
            self.assertIsNone(self._run(tmp))

    def test_unreadable_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.json"), "w") as fh:
                fh.write("not valid json")
            self.assertIsNone(self._run(tmp))
