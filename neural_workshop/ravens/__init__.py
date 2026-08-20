# -*- coding: utf-8 -*-
"""Raven's-style matrix puzzles, generated on the fly.

A three-by-three grid of drawings follows one or more rules; the
bottom-right cell is missing and the player picks it from eight
choices. The rules are geometric — a shape repeats, turns, shrinks,
changes shading, multiplies, or two cells combine — so the puzzle
needs no language and can be generated rather than drawn by hand.

The rules, the routes through the grid and the strategies for
building wrong answers follow the Sandia Generated Matrix Tool, a Java
research tool by Zachary Benz and Kevin Dixon, released by Sandia
Corporation in 2010 under a three-clause BSD licence. This is a
rewrite rather than a translation, and it departs from the original
where the original was wrong; ``Readme.md`` lists where and why.

Layout of the package:

``geometry``
    Points, outlines, and the transform every shape is drawn through.
``surfaces``
    The six shapes and five fills, and when two of them look alike.
``transforms``
    The routes a rule walks through the grid.
``rules``
    What changes from cell to cell along a route.
``matrix``
    Layers, the finished grid, and the wrong answers.

None of it imports pyglet, so a puzzle can be generated and checked
without a window. The drawing lives in :mod:`neural_workshop.ui.ravens`.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .matrix import Puzzle, generate
from .surfaces import Surface

__all__ = ['Puzzle', 'Surface', 'generate']
