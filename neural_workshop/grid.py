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


def current_grid_3d() -> bool:
    """Whether the board is rendered as a 3D transparent cube."""
    try:
        return bool(state.cfg.GRID_3D)
    except Exception:
        return False


def current_3d_cube_count() -> int:
    """Number of four-faced cubes composing one 3D position pattern."""
    try:
        return max(1, min(6, int(state.cfg.GRID_3D_CUBES)))
    except Exception:
        return 1


def decode_3d_pattern(position: int, count: int | None = None) -> List[int]:
    """Decode a 1-based pattern id into one highlighted face per cube."""
    count = current_3d_cube_count() if count is None else max(1, int(count))
    value = max(0, int(position) - 1)
    faces = []
    for _ in range(count):
        faces.append(value % 4)
        value //= 4
    return faces


def current_cell_count() -> int:
    """How many cells the board has."""
    if current_grid_3d():
        return 4 ** current_3d_cube_count()
    dim = 3 if current_grid_3d() else 2
    return bwaccel.grid_cell_count(
        current_grid_size(), current_include_center(), dim=dim)


_PERSPECTIVE_BACK_SCALE = 0.18


def current_cell_px() -> float:
    """Side length of one cell, in pixels."""
    n = current_grid_size()
    if current_grid_3d():
        return state.field.size / float(n)
    return state.field.size / float(n)


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
    if current_grid_3d():
        return list(range(1, current_cell_count() + 1))
    dim = 3 if current_grid_3d() else 2
    return bwaccel.active_position_ids(
        current_grid_size(), current_include_center(),
        current_active_cell_limit(), dim=dim)


def position_3d_node_px(i: float, j: float, k: float, n: int) -> Tuple[int, int]:
    """Project a 3D grid node into a room viewed along the depth axis."""
    depth = max(0.0, min(1.0, k / float(n)))
    scale = _PERSPECTIVE_BACK_SCALE + (
        1.0 - _PERSPECTIVE_BACK_SCALE) * depth
    x = int(round(state.field.center_x
                  + (i / float(n) - 0.5) * state.field.size * scale))
    y = int(round(state.field.center_y
                  + (j / float(n) - 0.5) * state.field.size * scale))
    return x, y


def position_pixel_center(position: int) -> Tuple[int, int]:
    """Pixel centre of a stimulus. ``position <= 0`` is the field centre."""
    if current_grid_3d():
        return int(state.field.center_x), int(state.field.center_y)
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
