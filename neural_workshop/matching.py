# -*- coding: utf-8 -*-
"""Deciding whether the current stimulus matches the one N trials back.

This is the scoring rule of the whole game, so it is kept apart from the
widgets that display its verdict.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from decimal import InvalidOperation
from typing import Tuple

import bwaccel

from . import state

#: One of these is returned by :func:`check_match`.
CORRECT = 'correct'
INCORRECT = 'incorrect'
MISSED = 'missed'
UNKNOWN = 'unknown'


def effective_back() -> int:
    """How many trials back the comparison reaches on this trial.

    Crab-back reverses each run of N stimuli, so the distance changes
    from trial to trial rather than staying at N.
    """
    mode = state.mode
    if mode.flags[mode.mode]['crab'] == 1:
        return 1 + 2 * ((mode.trial_number - 1) % mode.back)
    return mode.back


def _nback_trial_index(back: int) -> int:
    """Index into the session history of the trial being compared against."""
    mode = state.mode
    # FIXME: whether crab-back composes with VARIABLE_NBACK is unresolved.
    if state.cfg.VARIABLE_NBACK:
        offset = mode.variable_list[mode.trial_number - back - 1]
        return mode.trial_number - offset - 1
    return mode.trial_number - back - 1


def _current_and_history(input_type: str) -> Tuple[object, str]:
    """The value to compare, and the history key to compare it against.

    The combination modes cross the channels: ``visaudio`` compares the
    current *visual* stimulus against the *audio* history, and so on.
    """
    mode = state.mode
    if input_type in ('visvis', 'visaudio', 'image'):
        current = mode.current_stim['vis']
    elif input_type == 'audiovis':
        current = mode.current_stim['audio']
    else:
        current = mode.current_stim[input_type]

    if input_type in ('visvis', 'audiovis', 'image'):
        return current, 'vis'
    if input_type == 'visaudio':
        return current, 'audio'
    return current, input_type


def _check_arithmetic(nback_trial: int) -> str:
    """Compare the player's typed answer against the correct one."""
    mode = state.mode
    try:
        correct_answer = bwaccel.apply_arithmetic(
            mode.current_operation,
            state.stats.session['numbers'][nback_trial],
            mode.current_stim['number'])
    except (InvalidOperation, ZeroDivisionError, ValueError, TypeError):
        return INCORRECT
    given = state.arithmetic_answer_label.parse_answer()
    return CORRECT if correct_answer == given else INCORRECT


def check_match(input_type: str, check_missed: bool = False) -> str:
    """Verdict for one modality on the current trial.

    With *check_missed*, a true match reports ``'missed'`` instead of
    ``'correct'`` — that is the caller asking "should the player have
    pressed this?", not "did they press it correctly?".
    """
    mode = state.mode
    back = effective_back()
    nback_trial = _nback_trial_index(back)

    if len(state.stats.session['position1']) < mode.back:
        return UNKNOWN

    if input_type == 'arithmetic':
        return _check_arithmetic(nback_trial)

    current, history_key = _current_and_history(input_type)
    matched = bwaccel.is_nback_match(
        current, state.stats.session[history_key], nback_trial)
    if matched is None:
        return INCORRECT
    if matched:
        return MISSED if check_missed else CORRECT
    return INCORRECT
