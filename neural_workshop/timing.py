# -*- coding: utf-8 -*-
"""Trial timing: ticks, milliseconds and the phases inside one trial.

A trial is divided into a stimulus phase, a blank phase and a feedback
phase. The tick is the scheduler's quantum; everything else is expressed
in milliseconds and converted here so that config, CLI overrides and the
agent environment all agree on the same clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Dict

import bwaccel

from . import state


def tick_duration_ms() -> int:
    """Length of one scheduler tick, in milliseconds."""
    try:
        return max(1, int(state.cfg.TICK_DURATION_MS))
    except Exception:
        return 100


def trial_interval_ms() -> int:
    """Length of one trial, in milliseconds.

    An explicit ``TRIAL_INTERVAL_MS`` wins; otherwise the interval is
    derived from the mode's tick budget.
    """
    try:
        ms = int(state.cfg.TRIAL_INTERVAL_MS or 0)
    except Exception:
        ms = 0
    if ms > 0:
        return bwaccel.clamp_trial_interval_ms(ms, tick_duration_ms())
    return int(state.mode.ticks_per_trial) * tick_duration_ms()


def set_trial_interval_ms(ms: int) -> int:
    """Set the trial length and re-derive the mode's tick budget."""
    ms = bwaccel.clamp_trial_interval_ms(ms, tick_duration_ms())
    state.cfg.TRIAL_INTERVAL_MS = ms
    state.mode.ticks_per_trial = bwaccel.ms_to_ticks(ms, tick_duration_ms())
    return ms


def apply_trial_interval_override() -> None:
    """Re-apply ``TRIAL_INTERVAL_MS`` after something changed the mode."""
    try:
        ms = int(state.cfg.TRIAL_INTERVAL_MS or 0)
    except Exception:
        ms = 0
    if ms > 0:
        set_trial_interval_ms(ms)


def plan_current_trial_phases() -> Dict[str, int]:
    """Tick counts for the stimulus / blank / feedback phases of a trial."""
    return bwaccel.plan_trial_phases(
        trial_interval_ms(),
        state.cfg.STIMULUS_DURATION_MS,
        state.cfg.FEEDBACK_DURATION_MS,
        tick_duration_ms())


def feedback_tick() -> int:
    """Tick index, from trial start, where feedback begins.

    Self-paced mode jumps straight here once the player has answered.
    """
    plan = plan_current_trial_phases()
    return plan['stimulus_ticks'] + plan['blank_ticks'] + 1
