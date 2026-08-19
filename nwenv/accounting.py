# -*- coding: utf-8 -*-
"""Counters for how a run actually went.

Useful for spotting the failure modes a stepped environment is prone to:
frames published but never observed (dropped), frames observed twice
(duplicate), and trials that produced no verifiable outcome at all.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Set, Tuple


class Accounting:
    """Per-run counters, reset whenever the environment resets."""

    def __init__(self) -> None:
        self.logical_trials: int = 0
        self.significant_frames: int = 0
        self.authenticated_outcomes: Set[Tuple[Any, ...]] = set()
        self.dropped_frames: int = 0
        self.duplicate_frames: int = 0
        self.action_to_outcome_ns: List[int] = []
        self.t0: float = time.monotonic()
        self.reset()

    def reset(self) -> None:
        self.logical_trials = 0
        self.significant_frames = 0
        self.authenticated_outcomes = set()
        self.dropped_frames = 0
        self.duplicate_frames = 0
        self.action_to_outcome_ns = []
        self.t0 = time.monotonic()

    def snapshot(self) -> Dict[str, Any]:
        """A plain-dict view, safe to log or serialise."""
        wall = time.monotonic() - self.t0
        return {
            'logical_trials': self.logical_trials,
            'significant_frames': self.significant_frames,
            'unique_public_outcome_bits': len(self.authenticated_outcomes),
            'dropped_frames': self.dropped_frames,
            'duplicate_frames': self.duplicate_frames,
            'action_to_outcome_latency_ms': [
                ns / 1e6 for ns in self.action_to_outcome_ns],
            'wall_time_s': wall,
            'trials_per_s': (self.logical_trials / wall) if wall > 0 else 0.0,
        }


def format_accounting(acc: Any) -> str:
    """One-line summary of an :class:`Accounting` or its snapshot."""
    s = acc.snapshot() if hasattr(acc, 'snapshot') else acc
    latencies = s['action_to_outcome_latency_ms']
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
    return (
        'logical_trials=%i significant_frames=%i unique_public_outcome_bits=%i '
        'dropped_frames=%i duplicate_frames=%i '
        'action_to_outcome_latency_ms_avg=%.2f wall_time_s=%.3f trials/s=%.1f'
        % (s['logical_trials'], s['significant_frames'],
           s['unique_public_outcome_bits'], s['dropped_frames'],
           s['duplicate_frames'], avg_latency, s['wall_time_s'],
           s['trials_per_s']))
