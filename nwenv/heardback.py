# -*- coding: utf-8 -*-
"""The stepped agent boundary for the heard-back tasks: tones a frame
at a time, reaching the agent only as sound.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.heardback'


class ChangedNoteEnv(FrameRung):
    """Changed Note: Four ports, one a place in the four tones, first
    to fourth. The tones reach the agent only as sound. Presses before
    the question is put are ignored."""

    task_class = (UI, 'ChangedNote')
    ports = 4


class ChangedChimeEnv(FrameRung):
    """Changed Chime: Four ports, one a place in the four tones, fourth
    to first. The tones reach the agent only as sound. Presses before
    the question is put are ignored."""

    task_class = (UI, 'ChangedChime')
    ports = 4


class MarkedToneEnv(FrameRung):
    """Marked Tone: Four ports, one a pitch, lowest to highest. The
    tones reach the agent only as sound. Presses before the question
    is put are ignored."""

    task_class = (UI, 'MarkedTone')
    ports = 4


class OtherVoiceEnv(FrameRung):
    """Other Voice: Four ports, one a pitch, highest to lowest. The
    tones reach the agent only as sound. Presses before the question
    is put are ignored."""

    task_class = (UI, 'OtherVoice')
    ports = 4


ENVS = (ChangedNoteEnv, ChangedChimeEnv, MarkedToneEnv, OtherVoiceEnv)

verify_changed_note_outcome = ChangedNoteEnv.verifier()
verify_changed_chime_outcome = ChangedChimeEnv.verifier()
verify_marked_tone_outcome = MarkedToneEnv.verifier()
verify_other_voice_outcome = OtherVoiceEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
