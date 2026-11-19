# -*- coding: utf-8 -*-
"""The stepped agent boundary for the now-and-earlier tasks: things
show twice, and the answer is what differs the second time.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.nowthen'


class WhichMovedEnv(FrameRung):
    """Which Moved?: Four ports, one a card, left to right. Presses
    before the question is put are ignored."""

    task_class = (UI, 'WhichMoved')
    ports = 4


class MovedBeadEnv(FrameRung):
    """Moved Bead: Four ports, one a card, top to bottom. Presses
    before the question is put are ignored."""

    task_class = (UI, 'MovedBead')
    ports = 4


class WhichIsNewEnv(FrameRung):
    """Which Is New?: Four ports, one a card, left to right. Presses
    before the question is put are ignored."""

    task_class = (UI, 'WhichIsNew')
    ports = 4


class NewBeadEnv(FrameRung):
    """New Bead: Four ports, one a card, top to bottom. Presses before
    the question is put are ignored."""

    task_class = (UI, 'NewBead')
    ports = 4


class WhichIsGoneEnv(FrameRung):
    """Which Is Gone?: Four ports, one a card, left to right. Presses
    before the question is put are ignored."""

    task_class = (UI, 'WhichIsGone')
    ports = 4


class GoneBeadEnv(FrameRung):
    """Gone Bead: Four ports, one a card, top to bottom. Presses before
    the question is put are ignored."""

    task_class = (UI, 'GoneBead')
    ports = 4


class TradedPlacesEnv(FrameRung):
    """Traded Places: Five ports, one a place in the row, left to
    right. Presses before the question is put are ignored."""

    task_class = (UI, 'TradedPlaces')
    ports = 5


class TradedBeadsEnv(FrameRung):
    """Traded Beads: Five ports, one a place on the arc, right to left.
    Presses before the question is put are ignored."""

    task_class = (UI, 'TradedBeads')
    ports = 5


ENVS = (WhichMovedEnv, MovedBeadEnv, WhichIsNewEnv, NewBeadEnv,
        WhichIsGoneEnv, GoneBeadEnv, TradedPlacesEnv, TradedBeadsEnv)

verify_which_moved_outcome = WhichMovedEnv.verifier()
verify_moved_bead_outcome = MovedBeadEnv.verifier()
verify_which_is_new_outcome = WhichIsNewEnv.verifier()
verify_new_bead_outcome = NewBeadEnv.verifier()
verify_which_is_gone_outcome = WhichIsGoneEnv.verifier()
verify_gone_bead_outcome = GoneBeadEnv.verifier()
verify_traded_places_outcome = TradedPlacesEnv.verifier()
verify_traded_beads_outcome = TradedBeadsEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
