# -*- coding: utf-8 -*-
"""Converting durations into scheduler ticks, and planning a trial.

Everything the game times is expressed in milliseconds, but the
scheduler only wakes up once per tick. These helpers keep the two in
agreement so that ``ticks * tick_ms`` really is the interval the player
asked for.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Dict

#: A trial always gets at least this many ticks.
_MIN_TRIAL_TICKS = 3


def ms_to_ticks(ms: float, tick_ms: int = 100) -> int:
    """Convert a duration in milliseconds to a tick count (at least 1)."""
    tick_ms = max(1, int(tick_ms))
    try:
        ms = float(ms)
    except (TypeError, ValueError):
        ms = tick_ms
    return max(1, int(round(ms / tick_ms)))


def clamp_trial_interval_ms(ms: int, tick_ms: int = 100, min_ticks: int = 3,
                            max_ms: int = 60000) -> int:
    """Snap a trial interval to the clock grid and to sane bounds."""
    tick_ms = max(1, int(tick_ms))
    min_ticks = max(2, int(min_ticks))
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        ms = tick_ms * min_ticks
    lo = tick_ms * min_ticks
    hi = max(lo, int(max_ms))
    ms = max(lo, min(hi, ms))
    # Snap to the scheduler quantum, so ticks * tick_ms == interval.
    return ms_to_ticks(ms, tick_ms) * tick_ms


def plan_trial_phases(trial_ms: int, stim_ms: int, feedback_ms: int,
                      tick_ms: int = 1) -> Dict[str, int]:
    """Split a trial into stimulus, blank and feedback ticks.

    The three never overlap and always sum to the trial. If the wanted
    stimulus and feedback together exceed the trial, both are scaled
    down proportionally, each keeping at least one tick, and the blank
    disappears.
    """
    tick_ms = max(1, int(tick_ms))
    total = max(_MIN_TRIAL_TICKS, ms_to_ticks(trial_ms, tick_ms))
    stim_want = max(1, ms_to_ticks(stim_ms, tick_ms))
    fb_want = max(1, ms_to_ticks(feedback_ms, tick_ms))

    if stim_want + fb_want > total:
        stim = int(round(total * (stim_want / float(stim_want + fb_want))))
        stim = max(1, min(stim, total - 1))
        feedback = total - stim
        blank = 0
    else:
        stim = stim_want
        feedback = fb_want
        blank = total - stim - feedback

    return {
        'total_ticks': total,
        'stimulus_ticks': int(stim),
        'blank_ticks': int(blank),
        'feedback_ticks': int(feedback),
        'stimulus_ms': int(stim) * tick_ms,
        'blank_ms': int(blank) * tick_ms,
        'feedback_ms': int(feedback) * tick_ms,
    }


def interval_adjust_step(ms: int) -> int:
    """F5/F6 step size: fine at high speed, coarse for long trials."""
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        ms = 100
    for threshold, step in ((20, 1), (100, 5), (500, 10), (2000, 50)):
        if ms <= threshold:
            return step
    return 100
