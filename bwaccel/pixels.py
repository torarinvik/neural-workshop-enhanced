# -*- coding: utf-8 -*-
"""Reading the public feedback band out of a rendered frame.

The agent environment is only allowed to see pixels, so the outcome of a
trial has to be recovered from the colours of the feedback labels along
the bottom of the screen: green is correct, red incorrect, blue "oops".

Counting *labels* rather than pixels makes the result invariant to
wording, font and resolution, which is what the public outcome relies on.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

#: Column classes.
_EMPTY, _POSITIVE, _NEGATIVE, _OOPS = 0, 1, 2, 3

#: A channel must be this bright, and the others this dim, to count.
_BRIGHT = 180
_DIM = 140

#: A column needs at least this many matching pixels to be classified.
_MIN_COLUMN_PIXELS = 2


def default_band(height: int) -> Tuple[int, int]:
    """The bottom quarter of the frame, where feedback labels live."""
    return int(height * 0.75), height


def _resolve_band(height: int, y0: Optional[int],
                  y1: Optional[int]) -> Tuple[int, int]:
    lo, hi = default_band(height)
    if y0 is not None:
        lo = int(y0)
    if y1 is not None:
        hi = int(y1)
    return max(0, lo), min(height, hi)


def _classify(r: int, g: int, b: int) -> int:
    """Which feedback colour, if any, a pixel is."""
    if g >= _BRIGHT and r <= _DIM and b <= _DIM:
        return _POSITIVE
    if r >= _BRIGHT and g <= _DIM and b <= _DIM:
        return _NEGATIVE
    if b >= _BRIGHT and r <= _DIM and g <= _DIM:
        return _OOPS
    return _EMPTY


def count_feedback_pixels_py(rgba: Sequence[int], width: int, height: int,
                             y0: Optional[int] = None,
                             y1: Optional[int] = None) -> Tuple[int, int, int]:
    """Count feedback-palette pixels in the band of a top-down RGBA buffer."""
    width, height = int(width), int(height)
    y0, y1 = _resolve_band(height, y0, y1)
    counts = [0, 0, 0, 0]
    row_bytes = width * 4
    for y in range(y0, y1):
        base = y * row_bytes
        for x in range(width):
            off = base + x * 4
            counts[_classify(rgba[off], rgba[off + 1], rgba[off + 2])] += 1
    return (counts[_POSITIVE], counts[_NEGATIVE], counts[_OOPS])


def _classify_columns(rgba: Sequence[int], width: int, y0: int,
                      y1: int) -> List[int]:
    """One class per column: the feedback colour that dominates it."""
    row_bytes = width * 4
    classes: List[int] = []
    for x in range(width):
        counts = [0, 0, 0, 0]
        for y in range(y0, y1):
            off = y * row_bytes + x * 4
            counts[_classify(rgba[off], rgba[off + 1], rgba[off + 2])] += 1
        pos, neg, oops = counts[_POSITIVE], counts[_NEGATIVE], counts[_OOPS]
        if pos >= _MIN_COLUMN_PIXELS and pos >= neg and pos >= oops:
            classes.append(_POSITIVE)
        elif neg >= _MIN_COLUMN_PIXELS and neg >= oops:
            classes.append(_NEGATIVE)
        elif oops >= _MIN_COLUMN_PIXELS:
            classes.append(_OOPS)
        else:
            classes.append(_EMPTY)
    return classes


def count_closed_column_runs(classes: Sequence[int],
                             width: int) -> Tuple[int, int, int]:
    """Merge column runs of one class across small gaps, and count them.

    The gap threshold closes the spaces between glyphs and words inside
    one caption without joining two separate captions.
    """
    gap_thresh = max(8, int(width) // 40)
    runs = [0, 0, 0, 0]
    x = 0
    n = len(classes)
    while x < n:
        cls = classes[x]
        if cls == _EMPTY:
            x += 1
            continue
        x += 1
        while True:
            while x < n and classes[x] == cls:
                x += 1
            z = x
            while z < n and classes[z] == _EMPTY:
                z += 1
            if z < n and classes[z] == cls and (z - x) < gap_thresh:
                x = z
                continue
            break
        runs[cls] += 1
    return (runs[_POSITIVE], runs[_NEGATIVE], runs[_OOPS])


def count_feedback_label_runs_py(rgba: Sequence[int], width: int, height: int,
                                 y0: Optional[int] = None,
                                 y1: Optional[int] = None
                                 ) -> Tuple[int, int, int]:
    """Count feedback *labels* in the public pixel band.

    Each surviving column run is one label; the caller turns the counts
    into a scalar as ``(n_pos - n_neg) / (n_pos + n_neg)``.
    """
    width, height = int(width), int(height)
    y0, y1 = _resolve_band(height, y0, y1)
    return count_closed_column_runs(_classify_columns(rgba, width, y0, y1),
                                    width)
