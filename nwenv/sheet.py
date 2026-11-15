# -*- coding: utf-8 -*-
"""The stepped agent boundary for Spreadsheet.

Fifteen ports, Browser's: ports 0-11 move the drawn pointer (up, down,
left, right, by 80, 20 or 5 units of a 1000 by 640 screen), port 12
clicks, ports 13 and 14 scroll the rows. Every click counts against
par, keypad presses included; moving and scrolling are free. Green
means the number submitted was right, in no more clicks than par.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

CLICK, SCROLL_UP, SCROLL_DOWN = 12, 13, 14


class SpreadsheetEnv(TaskEnv):
    """Deterministic, stepped view of one Spreadsheet run."""

    task_class = ('neural_workshop.ui.sheet', 'Spreadsheet')
    ports = 15
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_spreadsheet_env(seed: int = 0, shm_name: Optional[str] = None
                         ) -> SpreadsheetEnv:
    """A production environment: the task's own defaults."""
    return SpreadsheetEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_spreadsheet_outcome = SpreadsheetEnv.verifier()

__all__ = ['CLICK', 'SCROLL_DOWN', 'SCROLL_UP', 'SpreadsheetEnv',
           'make_spreadsheet_env', 'verify_spreadsheet_outcome']
