# -*- coding: utf-8 -*-
"""The stepped agent boundary for Desktop.

Seventeen ports. Twelve move the drawn pointer: up, down, left, right,
each by a long, a medium or a short step (80, 20 and 5 units of a
1000 by 640 screen). Moving is free. Then click; press and release,
which between them drag -- a title bar to move a window, a corner to
resize it, an icon to move a file -- or, let go where they were
pressed, click; Done; and the right button, which opens a menu of
what can be done to the icon or folder under the pointer. A
click costs a point and so does a drag. Every point the reference
presses or lets go is on the pointer's grid, so anything the reference
can reach the agent can reach.

This is the one task whose ports carry no meaning of their own. A port
does not mean "set the volume"; it means "move left a little", and
what a click does depends entirely on what the screen shows under the
pointer -- which window is on top, which tab is open, whether a menu
or a list is in the way. Operating that is the skill being trained.

Green means every setting on the card held when Done was pressed and
the clicks came in at or under par: what a plain reference took on the
identical desktop, scaled by the rung, below it past rung twenty.

Turn-based, so it takes the think clock: pointer moves are free in
clicks but not in thinking time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: Moves are ports 0-11: direction * 3 + step. Then these.
CLICK, PRESS, RELEASE, DONE, RIGHT = 12, 13, 14, 15, 16


class DesktopEnv(TaskEnv):
    """Deterministic, stepped view of one Desktop run."""

    task_class = ('neural_workshop.ui.desktop', 'Desktop')
    ports = 17
    clocked = False
    action = 'steer'
    open_phase = ('working',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_desktop_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> DesktopEnv:
    """A production environment: the task's own defaults."""
    return DesktopEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_desktop_outcome = DesktopEnv.verifier()

__all__ = ['CLICK', 'DONE', 'DesktopEnv', 'PRESS', 'RELEASE', 'RIGHT',
           'make_desktop_env',
           'verify_desktop_outcome']
