# -*- coding: utf-8 -*-
"""Privileged inspection, for tests and debugging only.

Nothing here is part of the learner-facing contract. The probe reads
game state directly, which is exactly what the public environment must
never do, so it lives behind a separate class that has to be asked for
explicitly and gated on ``NW_DIAGNOSTICS=1``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import brainworkshop as bw

from .env import NeuralWorkshopEnv


class TestProbe:
    """Direct view of the game state. Tests only."""

    def phase(self) -> Optional[str]:
        return bw.mode.phase

    def stim(self) -> Dict[str, int]:
        return dict(bw.mode.current_stim)

    def show_missed(self) -> bool:
        return bool(bw.mode.show_missed)

    def session_done(self) -> bool:
        return bool(bw.mode.session_done or bw.mode.phase == 'done')

    def captured_audio(self) -> List[Dict[str, Any]]:
        return list(bw.audio_capture)

    def score_snapshot(self) -> Dict[str, Any]:
        return {
            'trial_number': bw.mode.trial_number,
            'inputs': dict(bw.mode.inputs),
            'started': bool(bw.mode.started),
        }


class DiagnosticEnv(NeuralWorkshopEnv):
    """Environment with a probe attached. Never used in production."""

    def __init__(self, seed: Optional[int] = None,
                 shm_name: Optional[str] = None,
                 game_mode: Optional[int] = None,
                 num_trials: Optional[int] = None,
                 n_back: Optional[int] = None,
                 grid_size: Optional[int] = None,
                 active_cells: Optional[int] = None,
                 mute_music: bool = True, mute_applause: bool = True,
                 visible: bool = False) -> None:
        os.environ['NW_DIAGNOSTICS'] = '1'
        super().__init__(
            seed=seed, shm_name=shm_name, diagnostics=True,
            game_mode=game_mode, num_trials=num_trials, n_back=n_back,
            grid_size=grid_size, active_cells=active_cells,
            mute_music=mute_music, mute_applause=mute_applause,
            visible=visible)
        self.probe = TestProbe()
