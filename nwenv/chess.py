# -*- coding: utf-8 -*-
"""Stepped boundary for Chess: Winning Move."""
from __future__ import annotations

from typing import Any

from .taskenv import TaskEnv


class ChessEnv(TaskEnv):
    """Choose one source/destination pair from the visible chessboard."""

    task_class = ('neural_workshop.ui.chess', 'Chess')
    ports = 64 * 64
    clocked = False
    open_phase = ('solving',)
    settled_phase = ('solved', 'missed')
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        task.answer(port // 64, port % 64)


verify_chess_outcome = ChessEnv.verifier()

__all__ = ['ChessEnv', 'verify_chess_outcome']
