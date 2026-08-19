# -*- coding: utf-8 -*-
"""The board the position stimulus appears on.

The board is ``GRID_SIZE`` x ``GRID_SIZE`` cells. Cells are identified by
a 1-based position id; id ``0`` (or less) means "the centre of the field,
no cell", which is where non-positional stimuli are drawn.

An optional ``ACTIVE_POSITION_CELLS`` cap restricts sampling to the first
N cells in centre-out order, for a gentler curriculum on a large board.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Tuple

import bwaccel

from . import state


def current_grid_bounds() -> Tuple[int, int]:
    """The (min, max) grid size the player is allowed to select."""
    try:
        gmin = int(state.cfg.GRID_SIZE_MIN)
    except Exception:
        gmin = 2
    try:
        gmax = int(state.cfg.GRID_SIZE_MAX)
    except Exception:
        gmax = 32
    gmin = max(2, gmin)
    gmax = max(gmin, gmax)
    return gmin, gmax


def current_grid_size() -> int:
    """Side length of the board, clamped to the configured bounds."""
    gmin, gmax = current_grid_bounds()
    try:
        return max(gmin, min(gmax, int(state.cfg.GRID_SIZE)))
    except Exception:
        return 3


def current_include_center() -> bool:
    """Whether the middle cell of an odd-sized board is usable."""
    return bool(state.cfg.GRID_INCLUDE_CENTER)


def current_cell_count() -> int:
    """How many cells the board has."""
    return bwaccel.grid_cell_count(current_grid_size(), current_include_center())


def current_cell_px() -> float:
    """Side length of one cell, in pixels."""
    return state.field.size / float(current_grid_size())


def current_active_cell_limit() -> int:
    """Curriculum cap on sampled cells; ``0`` means the whole board."""
    for key in ('ACTIVE_POSITION_CELLS', 'POSITION_CELL_COUNT'):
        try:
            n = int(state.cfg[key] or 0)
        except Exception:
            n = 0
        if n > 0:
            return n
    return 0


def current_active_position_ids() -> List[int]:
    """Position ids the stimulus generator may draw from."""
    return bwaccel.active_position_ids(
        current_grid_size(), current_include_center(),
        current_active_cell_limit())


def position_pixel_center(position: int) -> Tuple[int, int]:
    """Pixel centre of a stimulus. ``position <= 0`` is the field centre."""
    cell = current_cell_px()
    col_row = bwaccel.position_col_row(
        position, current_grid_size(), current_include_center())
    if col_row is None:
        return int(state.field.center_x), int(state.field.center_y)
    col, row = col_row
    x = int(round(state.field.center_x - state.field.size / 2.0
                  + cell * (col + 0.5)))
    y = int(round(state.field.center_y - state.field.size / 2.0
                  + cell * (row + 0.5)))
    return x, y
