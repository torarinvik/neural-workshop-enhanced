# -*- coding: utf-8 -*-
"""What the stepped boundaries of the frame-by-frame families share.

Clocked: the frames go by, and the time to answer runs, whether or not
the agent acts. These tasks are safe to drive as slowly as one step a
shown frame (``frame_hz=2``): their frames are half a second long, and
their screens let a single tick carry the run a whole frame on, so a
trial driven that way is judged as it is at ten steps a second.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .taskenv import TaskEnv

#: One step a shown frame.
FRAME_HZ = 2.0


class FrameRung(TaskEnv):
    """A graded clocked task that may be stepped a frame at a time."""

    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}
    slowest_frame_hz = FRAME_HZ
