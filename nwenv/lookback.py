# -*- coding: utf-8 -*-
"""The stepped agent boundary for the looking-back tasks: the answer
is in a frame no longer showing.

Clocked: the frames go by, and the time to answer runs, whether or not
the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any

from .taskenv import TaskEnv


class _Rung(TaskEnv):
    """What every wrapper here shares."""

    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class ShapeBackEnv(_Rung):
    """Shape Back: Three ports, one a card, from the left. Presses
    before the question is put are ignored."""

    task_class = ('neural_workshop.ui.lookback', 'ShapeBack')
    ports = 3


class HiddenCueEnv(_Rung):
    """Hidden Cue: Four ports, one a square, in reading order.
    Presses before the question is put are ignored."""

    task_class = ('neural_workshop.ui.lookback', 'HiddenCue')
    ports = 4


class SoundBackEnv(_Rung):
    """Sound Back: Three ports: 0 low, 1 middle, 2 high. The tones
    reach the agent only as sound. Presses before the question is
    put are ignored."""

    task_class = ('neural_workshop.ui.lookback', 'SoundBack')
    ports = 3


verify_shape_back_outcome = ShapeBackEnv.verifier()
verify_hidden_cue_outcome = HiddenCueEnv.verifier()
verify_sound_back_outcome = SoundBackEnv.verifier()

__all__ = ['ShapeBackEnv', 'HiddenCueEnv', 'SoundBackEnv']
