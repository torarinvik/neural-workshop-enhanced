# -*- coding: utf-8 -*-
"""The stepped agent boundary for Sign Painter.

Nineteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-17 pick red, green, blue and yellow; port 18 dips the brush.
With the button down the brush paints the next point of the next
stroke when it is on it; straying from the stroke smudges. The order
is written on the screen. The agent hears the brush, a smudge, a dry
brush and each finished stroke.

Clocked: the board swings and the paint dries whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SignPainterEnv(TaskEnv):
    """Deterministic, stepped view of one Sign Painter run."""

    task_class = ('neural_workshop.ui.signpainter', 'SignPainter')
    ports = 19
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_sign_painter_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> SignPainterEnv:
    """A production environment: the task's own defaults."""
    return SignPainterEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_sign_painter_outcome = SignPainterEnv.verifier()

__all__ = ['SignPainterEnv', 'make_sign_painter_env',
           'verify_sign_painter_outcome']
