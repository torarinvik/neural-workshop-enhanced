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


#: The rate the older frame tasks run at unless a driver opts in to
#: one step a shown frame.
USUAL_SLOWEST_HZ = 10.0
#: The slice a tick is cut into when one tick carries a whole frame: a
#: power of two, so the slices of half a second sum to it exactly and
#: the frame clock lands on each frame's start.
FRAME_SUBSTEP = 1.0 / 128


class SlowFrames:
    """For the frame tasks written before :class:`FrameRung`: they may
    also be driven at one step a shown frame, as an opt-in.

    At ten steps a second and above nothing changes: the task keeps its
    own longest tick and slice, and runs as it always has. At exactly
    ``FRAME_HZ`` the task built for the run is let take a whole frame in
    one tick, cut in slices that sum exactly, so that every step lands
    on the start of a frame, and a press, which these tasks take at
    once, comes at the same point of the trial as it would at ten steps
    a second. Other rates below ten are refused, as before: their ticks
    would not sum to the frames exactly.
    """

    slowest_frame_hz = FRAME_HZ

    def __init__(self, *args, frame_hz: float = 60.0, **kwargs) -> None:
        hz = float(frame_hz)
        if hz < USUAL_SLOWEST_HZ and hz != FRAME_HZ:
            raise ValueError('frame_hz must be at least %g, or exactly %g '
                             'for one step a frame'
                             % (USUAL_SLOWEST_HZ, FRAME_HZ))
        super().__init__(*args, frame_hz=frame_hz, **kwargs)

    def apply_dials(self, task) -> None:
        super().apply_dials(task)
        if self._hz < USUAL_SLOWEST_HZ:
            task.LONGEST_TICK = 1.0 / self._hz
            task.SUBSTEP = FRAME_SUBSTEP
