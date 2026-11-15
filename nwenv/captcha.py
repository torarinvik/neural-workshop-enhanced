# -*- coding: utf-8 -*-
"""The stepped agent boundary for Captcha.

Twenty-five ports: 0-22 type the characters of
``neural_workshop.captcha.ALPHABET`` in order, 23 rubs out the last
one, 24 submits. Green means what was typed is exactly the characters
the rule asks for, in reading order.

Turn-based, so it takes the think clock: the picture waits for the agent.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CaptchaEnv(TaskEnv):
    """Deterministic, stepped view of one Captcha run."""

    task_class = ('neural_workshop.ui.captcha', 'Captcha')
    ports = 25
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_captcha_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> CaptchaEnv:
    """A production environment: the task's own defaults."""
    return CaptchaEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_captcha_outcome = CaptchaEnv.verifier()

__all__ = ['CaptchaEnv', 'make_captcha_env',
           'verify_captcha_outcome']
