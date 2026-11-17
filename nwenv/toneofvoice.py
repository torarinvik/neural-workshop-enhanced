# -*- coding: utf-8 -*-
"""The stepped agent boundary for Tone of Voice.

Eight ports. Port k picks answer k+1 of the buttons under the text. A chime
follows a right answer and a low note a wrong one.
The voice comes on the audio channel, twice, before the answers are timed out.

Clocked: each item has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ToneOfVoiceEnv(TaskEnv):
    """Deterministic, stepped view of one Tone of Voice run."""

    task_class = ('neural_workshop.ui.toneofvoice', 'ToneOfVoice')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_tone_of_voice_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> ToneOfVoiceEnv:
    """A production environment: the task's own defaults."""
    return ToneOfVoiceEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_tone_of_voice_outcome = ToneOfVoiceEnv.verifier()

__all__ = ['ToneOfVoiceEnv', 'make_tone_of_voice_env',
           'verify_tone_of_voice_outcome']
