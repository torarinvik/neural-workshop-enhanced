# -*- coding: utf-8 -*-
"""Raven's-style matrix puzzles, generated on the fly.

Nine panels in a three-by-three grid. The figures in them follow rules
that run along the rows; the last panel is missing and the player picks
it from eight candidates.

The pieces:

``geometry``
    Points, outlines, and cutting an outline into triangles to fill.
``palette``
    The fills — greys, and a colour set chosen to survive colour
    blindness.
``figures``
    The figures themselves: regular polygons at graded sizes.
``layouts``
    Where figures sit inside a panel, and how a panel splits into
    components that carry rules of their own.
``rules``
    What an attribute does across a row: hold, step, distribute three,
    or add up.
``matrix``
    Dealing rules to attributes, running them out into nine panels, and
    building the eight answers.

None of it imports pyglet, so a puzzle can be generated and checked
without a window. The drawing lives in :mod:`neural_workshop.ui.ravens`.

The rules, the layouts and the way wrong answers are built follow the
conventions of Raven's Progressive Matrices. An earlier version of
this engine was a port of the Sandia Generated Matrix Tool, a Java
research tool by Zachary Benz and Kevin Dixon released by Sandia
Corporation in 2010 under a three-clause BSD licence; what survives
from it is the colour work and the near-miss strategy. ``Readme.md``
says what was rebuilt and why.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .matrix import LADDER, Puzzle, generate

__all__ = ['LADDER', 'Puzzle', 'generate']
