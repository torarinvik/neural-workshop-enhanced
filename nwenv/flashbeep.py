# -*- coding: utf-8 -*-
"""The stepped agent boundary for Flash and Beep.

Four ports: 0 says the flash came first and 1 the beep; where the
flashes are counted, port k answers k+1. The beeps reach the agent
only as sound.

Clocked: the sounds play and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FlashBeepEnv(TaskEnv):
    """Deterministic, stepped view of one Flash and Beep run."""

    task_class = ('neural_workshop.ui.flashbeep', 'FlashBeep')
    ports = 4
    clocked = True
    #: A flash lasts a twentieth of a second: slower frames could miss it.
    slowest_frame_hz = 30.0
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_flash_and_beep_env(seed: int = 0,
                              shm_name: Optional[str] = None) -> FlashBeepEnv:
    """A production environment: the task's own defaults."""
    return FlashBeepEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_flash_and_beep_outcome = FlashBeepEnv.verifier()

__all__ = ['FlashBeepEnv', 'make_flash_and_beep_env',
           'verify_flash_and_beep_outcome']
