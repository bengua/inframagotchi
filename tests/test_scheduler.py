"""Tests for the background ProbeScheduler."""

from __future__ import annotations

import time
from unittest import TestCase

from probes.loader import Probe
from probes.scheduler import ProbeScheduler
from probes.state import HealthState


class ProbeSchedulerTests(TestCase):
    def test_runs_probe_immediately_and_updates_state(self) -> None:
        state = HealthState()
        probe = Probe("fast", lambda: 0.5, 0.1)
        sched = ProbeScheduler(state, [probe])
        sched.start()
        time.sleep(0.05)
        try:
            self.assertEqual(state.aggregate(), 50)
        finally:
            sched.stop()

    def test_slow_probe_does_not_block_reader(self) -> None:
        state = HealthState()
        slow_probe = Probe("slow", lambda: (time.sleep(0.3), 0.0)[1], 60.0)
        sched = ProbeScheduler(state, [slow_probe])
        sched.start()
        try:
            time.sleep(0.4)  # let the first slow run finish
            start = time.perf_counter()
            health = state.aggregate()
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, 0.05)
            self.assertEqual(health, 0)
        finally:
            sched.stop()

    def test_thread_count_matches_probe_count(self) -> None:
        state = HealthState()
        probes = [Probe(f"p{i}", lambda: 0.5, 1.0) for i in range(5)]
        sched = ProbeScheduler(state, probes)
        sched.start()
        try:
            self.assertEqual(len(sched._threads), 5)
            time.sleep(0.05)
            alive = [t for t in sched._threads if t.is_alive()]
            self.assertEqual(len(alive), 5)
        finally:
            sched.stop()

    def test_clean_shutdown(self) -> None:
        state = HealthState()
        probe = Probe("p", lambda: 0.5, 0.05)
        sched = ProbeScheduler(state, [probe])
        sched.start()
        time.sleep(0.1)
        sched.stop()
        self.assertTrue(all(not t.is_alive() for t in sched._threads))
