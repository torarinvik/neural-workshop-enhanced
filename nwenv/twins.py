# -*- coding: utf-8 -*-
"""The stepped agent boundary for the twin tasks: four rules, each in two looks.

Turn-based, so these take the think clock: nothing moves until a port
is pressed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any

from .taskenv import TaskEnv


class _Rung(TaskEnv):
    """What every wrapper here shares."""

    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class MatchShapesEnv(_Rung):
    """Match Shapes: Two ports: 0 same, 1 different."""

    task_class = ('neural_workshop.ui.twins', 'MatchShapes')
    ports = 2


class MatchTilesEnv(_Rung):
    """Match Tiles: Two ports: 0 different, 1 same."""

    task_class = ('neural_workshop.ui.twins', 'MatchTiles')
    ports = 2


class OddShapeEnv(_Rung):
    """Odd Shape: Twelve ports, one an item, from the left; a rung
    with fewer items leaves the rest doing nothing."""

    task_class = ('neural_workshop.ui.twins', 'OddShape')
    ports = 12


class OddStripeEnv(_Rung):
    """Odd Stripe: Twelve ports, one an item, counted back round the
    ring; a rung with fewer items leaves the rest doing nothing."""

    task_class = ('neural_workshop.ui.twins', 'OddStripe')
    ports = 12


class NextShapeEnv(_Rung):
    """Next Shape: Three ports, one a card, from the left."""

    task_class = ('neural_workshop.ui.twins', 'NextShape')
    ports = 3


class NextTileEnv(_Rung):
    """Next Tile: Three ports, one a card, from the bottom."""

    task_class = ('neural_workshop.ui.twins', 'NextTile')
    ports = 3


class InTheLoopEnv(_Rung):
    """In the Loop: Two ports: 0 inside, 1 outside."""

    task_class = ('neural_workshop.ui.twins', 'InTheLoop')
    ports = 2


class InThePenEnv(_Rung):
    """In the Pen: Two ports: 0 outside, 1 inside."""

    task_class = ('neural_workshop.ui.twins', 'InThePen')
    ports = 2


verify_match_shapes_outcome = MatchShapesEnv.verifier()
verify_match_tiles_outcome = MatchTilesEnv.verifier()
verify_odd_shape_outcome = OddShapeEnv.verifier()
verify_odd_stripe_outcome = OddStripeEnv.verifier()
verify_next_shape_outcome = NextShapeEnv.verifier()
verify_next_tile_outcome = NextTileEnv.verifier()
verify_in_the_loop_outcome = InTheLoopEnv.verifier()
verify_in_the_pen_outcome = InThePenEnv.verifier()

__all__ = ['MatchShapesEnv', 'MatchTilesEnv', 'OddShapeEnv', 'OddStripeEnv', 'NextShapeEnv', 'NextTileEnv', 'InTheLoopEnv', 'InThePenEnv']
