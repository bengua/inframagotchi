"""Tests for the thread-safe HealthState cache."""

from __future__ import annotations

from unittest import TestCase

from probes.state import HealthState


class HealthStateTests(TestCase):
    def test_empty_state_is_neutral(self) -> None:
        self.assertEqual(HealthState().aggregate(), 100)

    def test_aggregate_uses_weakest_non_none_value(self) -> None:
        state = HealthState()
        state.set("a", 1.0)
        state.set("b", None)
        state.set("c", 0.25)
        self.assertEqual(state.aggregate(), 25)

    def test_all_none_is_neutral(self) -> None:
        state = HealthState()
        state.set("a", None)
        state.set("b", None)
        self.assertEqual(state.aggregate(), 100)

    def test_values_are_clamped(self) -> None:
        state = HealthState()
        state.set("low", -0.5)
        state.set("high", 1.5)
        self.assertEqual(state.aggregate(), 0)

    def test_snapshot_returns_latest_values(self) -> None:
        state = HealthState()
        state.set("a", 0.5)
        snap = state.snapshot()
        self.assertIn("a", snap)
        self.assertEqual(snap["a"]["value"], 0.5)
        self.assertIsInstance(snap["a"]["last_updated"], float)
