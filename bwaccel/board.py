# -*- coding: utf-8 -*-
"""The geometry of the position board.

A board is ``n`` x ``n`` cells, each with a 1-based position id. The
classic 3x3 board keeps its historic id-to-cell mapping so that old stats
files still describe the same cells; every other size is numbered in
reading order. On an odd board the centre cell is skipped unless
``include_center`` asks for it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

#: Historic id -> (col, row) for the original 3x3 board.
_CLASSIC_3X3: Dict[int, Tuple[int, int]] = {
    0: (1, 1),
    1: (2, 1), 2: (0, 1), 3: (1, 2),
    4: (2, 2), 5: (0, 2), 6: (1, 0),
    7: (2, 0), 8: (0, 0),
    9: (1, 1),
}


def grid_layout(n: int, include_center: bool = False
                ) -> List[Tuple[int, int, int]]:
    """``[(position_id, col, row), ...]`` for an n x n board."""
    n = max(2, int(n))
    include_center = bool(include_center)
    if n == 3:
        ids = list(range(1, 9))
        if include_center:
            ids.append(9)
        return [(pid, _CLASSIC_3X3[pid][0], _CLASSIC_3X3[pid][1])
                for pid in ids]

    skip_center = (n % 2 == 1) and not include_center
    cells: List[Tuple[int, int, int]] = []
    pid = 1
    for row in range(n):
        for col in range(n):
            if skip_center and col == n // 2 and row == n // 2:
                continue
            cells.append((pid, col, row))
            pid += 1
    return cells


def grid_cell_count(n: int, include_center: bool = False) -> int:
    """How many usable cells an n x n board has."""
    return len(grid_layout(n, include_center))


def position_col_row(position: Optional[int], n: int,
                     include_center: bool = False
                     ) -> Optional[Tuple[int, int]]:
    """Map a 1-based position id to (col, row).

    Returns ``None`` for an unknown id, and for ``position <= 0``, which
    means "the centre of the field, no cell".
    """
    n = max(2, int(n))
    if position is None or int(position) <= 0:
        return None
    position = int(position)
    if n == 3:
        return _CLASSIC_3X3.get(position)
    for pid, col, row in grid_layout(n, include_center):
        if pid == position:
            return (col, row)
    return None


def grid_center_out_ids(n: int, include_center: bool = False) -> List[int]:
    """Position ids ordered from the board centre outwards.

    This is the curriculum order: a capped board uses the first N of
    these, so difficulty grows by spreading outwards.
    """
    n = max(2, int(n))
    if n == 3 and not include_center:
        return [1, 2, 3, 6, 4, 5, 7, 8]
    cx = cy = (n - 1) / 2.0
    cells = sorted(grid_layout(n, include_center),
                   key=lambda c: ((c[1] - cx) ** 2 + (c[2] - cy) ** 2,
                                  -c[2], c[1]))
    return [c[0] for c in cells]


def active_position_ids(n: int, include_center: bool = False,
                        limit: int = 0) -> List[int]:
    """Ids that may be sampled. ``limit <= 0`` means the whole board."""
    all_ids = [pid for pid, _col, _row in grid_layout(n, include_center)]
    try:
        limit = int(limit or 0)
    except (TypeError, ValueError):
        limit = 0
    if limit <= 0 or limit >= len(all_ids):
        return all_ids
    order = grid_center_out_ids(n, include_center)
    return order[:max(2, min(limit, len(order)))]
