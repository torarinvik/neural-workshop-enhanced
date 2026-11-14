# -*- coding: utf-8 -*-
"""The stepped agent boundary for Browser.

Fifteen ports, Desktop's pointer and two more. Ports 0-11 move the
drawn pointer: up, down, left, right, each by a long, a medium or a
short step (80, 20 and 5 units of a 1000 by 640 window). Port 12
clicks whatever is under the pointer -- a link, a button, Back, Home,
the cart -- or nothing. Ports 13 and 14 scroll the page up and down.
Moving and scrolling are free; every click counts against par.

Green means the cart at checkout held exactly what the shopping list
asked for, in no more clicks than par: the fewest that could do it plus
a share, shrinking with the rung, of what a thorough shopper spends
opening everything.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

CLICK, SCROLL_UP, SCROLL_DOWN = 12, 13, 14


class BrowserEnv(TaskEnv):
    """Deterministic, stepped view of one Browser run."""

    task_class = ('neural_workshop.ui.browser', 'Browser')
    ports = 15
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_browser_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> BrowserEnv:
    """A production environment: the task's own defaults."""
    return BrowserEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_browser_outcome = BrowserEnv.verifier()

__all__ = ['BrowserEnv', 'CLICK', 'SCROLL_DOWN', 'SCROLL_UP',
           'make_browser_env', 'verify_browser_outcome']
