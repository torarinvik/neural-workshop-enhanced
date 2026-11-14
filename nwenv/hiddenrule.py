# -*- coding: utf-8 -*-
"""The stepped agent boundary for Hidden Rule.

Ten ports. The first six each step one property of the object being
built to its next value -- colour, shape, size, count, fill, bar -- and
cost nothing; a property not in play on the rung does nothing. Then
Test, which puts the object under the lamp for a point; Exam; and Lit
and Dark, which answer the exam's questions. Steered rather than a port
per object because the top rungs have three hundred and eighty-four.

Green means the round cost no more than par: what a Bayesian reference
experimenter paid on the identical deal -- the same lies on the same
numbered test, the same exam in the same order -- scaled by the rung,
which past rung twenty asks for less than it paid.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: Step a property: ports 0-5. Then these.
TEST, EXAM, LIT, DARK = 6, 7, 8, 9


class HiddenRuleEnv(TaskEnv):
    """Deterministic, stepped view of one Hidden Rule run."""

    task_class = ('neural_workshop.ui.hiddenrule', 'HiddenRule')
    ports = 10
    clocked = False
    action = 'steer'
    open_phase = ('testing', 'examining')
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_hidden_rule_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> HiddenRuleEnv:
    """A production environment: the task's own defaults."""
    return HiddenRuleEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_hidden_rule_outcome = HiddenRuleEnv.verifier()

__all__ = ['DARK', 'EXAM', 'HiddenRuleEnv', 'LIT', 'TEST',
           'make_hidden_rule_env', 'verify_hidden_rule_outcome']
