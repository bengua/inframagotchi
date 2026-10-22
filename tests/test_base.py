"""Tests for the base probe contract and scoring helpers."""

from __future__ import annotations

from unittest import TestCase

from probes.base import linear_score, safe_call


class LinearScoreTests(TestCase):
    def test_lower_is_good(self) -> None:
        # load: 1.0 at warn=2.0, 0.0 at critical=4.0
        self.assertAlmostEqual(linear_score(1.0, 2.0, 4.0), 1.0)
        self.assertAlmostEqual(linear_score(2.0, 2.0, 4.0), 1.0)
        self.assertAlmostEqual(linear_score(3.0, 2.0, 4.0), 0.5)
        self.assertAlmostEqual(linear_score(4.0, 2.0, 4.0), 0.0)
        self.assertAlmostEqual(linear_score(5.0, 2.0, 4.0), 0.0)

    def test_higher_is_good(self) -> None:
        # free fraction: 1.0 at warn=0.5, 0.0 at critical=0.1
        self.assertAlmostEqual(linear_score(0.6, 0.5, 0.1), 1.0)
        self.assertAlmostEqual(linear_score(0.5, 0.5, 0.1), 1.0)
        self.assertAlmostEqual(linear_score(0.3, 0.5, 0.1), 0.5)
        self.assertAlmostEqual(linear_score(0.1, 0.5, 0.1), 0.0)
        self.assertAlmostEqual(linear_score(0.0, 0.5, 0.1), 0.0)

    def test_equal_good_bad(self) -> None:
        self.assertAlmostEqual(linear_score(5.0, 5.0, 5.0), 1.0)
        self.assertAlmostEqual(linear_score(4.9, 5.0, 5.0), 0.0)


class SafeCallTests(TestCase):
    def test_returns_none_for_none(self) -> None:
        self.assertIsNone(safe_call(lambda: None))

    def test_clamps_high_and_low(self) -> None:
        self.assertAlmostEqual(safe_call(lambda: 1.5), 1.0)
        self.assertAlmostEqual(safe_call(lambda: -0.5), 0.0)
        self.assertAlmostEqual(safe_call(lambda: 0.5), 0.5)

    def test_catches_exception(self) -> None:
        self.assertIsNone(safe_call(lambda: (_ for _ in ()).throw(RuntimeError("boom"))))
