# -*- coding: utf-8 -*-
"""Accelerated kernels for Neural Workshop.

Every hot loop exists twice: once in ``native/bwcore.c`` and once in
:mod:`bwaccel.fallback`, with the same contract. If the compiled
extension is importable this module dispatches to it; otherwise the game
runs unaided on the Python versions. ``backend()`` says which is live,
and the test suite checks the two against each other.

Modules
-------
``fallback``    the pure-Python implementations
``board``       position ids and the geometry of the board
``scheduling``  milliseconds, ticks, and the phases of a trial
``arithmetic``  exact Decimal arithmetic for arithmetic n-back
``pixels``      reading the public feedback band out of a frame

The board, scheduling, arithmetic and pixel helpers are re-exported here,
so ``bwaccel.grid_layout`` and friends keep working as before.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .arithmetic import ARITHMETIC_OPS, apply_arithmetic, score_arithmetic
from .board import (active_position_ids, grid_cell_count, grid_center_out_ids,
                    grid_center_out_ids_3d, grid_layout, grid_layout_3d,
                    position_col_row, position_col_row_depth)
from .fallback import (_aggregate_day_scores_py, _analyze_session_py,
                       _compute_bt_sequence_py, _is_nback_match_py,
                       _mean_tail_py, _parse_stats_text_py,
                       _rounded_rect_vertices_py, _sample_unique_py,
                       _variable_nback_list_py)
from .pixels import (count_closed_column_runs, count_feedback_label_runs_py,
                     count_feedback_pixels_py, default_band)
from .scheduling import (clamp_trial_interval_ms, interval_adjust_step,
                         ms_to_ticks, plan_trial_phases)

try:
    import bwcore as _native  # type: ignore
    USING_NATIVE = True
except ImportError:
    _native = None
    USING_NATIVE = False

__all__ = [
    'USING_NATIVE', 'backend', 'banner', 'seed',
    'compute_bt_sequence', 'analyze_session', 'aggregate_day_scores',
    'rounded_rect_vertices', 'variable_nback_list', 'sample_unique',
    'parse_stats_text', 'is_nback_match', 'mean_tail',
    'apply_arithmetic', 'score_arithmetic', 'ARITHMETIC_OPS',
    'grid_layout', 'grid_layout_3d', 'grid_cell_count', 'position_col_row',
    'position_col_row_depth', 'grid_center_out_ids', 'grid_center_out_ids_3d',
    'active_position_ids',
    'ms_to_ticks', 'clamp_trial_interval_ms', 'plan_trial_phases',
    'interval_adjust_step',
    'count_feedback_pixels', 'count_feedback_label_runs',
    'count_closed_column_runs', 'default_band', 'maybe_hint_compile',
]


def backend() -> str:
    """``'C'`` when the compiled extension is in use, else ``'Python'``."""
    return 'C' if (USING_NATIVE and _native is not None) else 'Python'


def banner() -> str:
    """Short UI/console tag, e.g. ``native: C``."""
    return 'native: %s' % backend()


def seed(n: Optional[int] = None) -> None:
    """Seed the RNGs. ``None`` uses entropy; ``0`` is a real seed."""
    target = _native if USING_NATIVE else random
    if n is None:
        target.seed()
    else:
        target.seed(int(n))


# --- kernels with a C counterpart -----------------------------------------

def compute_bt_sequence(num_trials: int, nback: int, n_pos: int = 6,
                        n_audio: int = 6, n_both: int = 2,
                        pos_choices: int = 8,
                        audio_choices: int = 8) -> List[List[int]]:
    """A dual sequence with exactly the requested number of matches."""
    args = (num_trials, nback, n_pos, n_audio, n_both, pos_choices,
            audio_choices)
    if USING_NATIVE:
        return _native.compute_bt_sequence(*args)
    return _compute_bt_sequence_py(*args)


def analyze_session(nback: int, crab: bool = False,
                    jaeggi_scoring: bool = False,
                    variable_list: Optional[Sequence[int]] = None,
                    modalities: Optional[Sequence[str]] = None,
                    session: Optional[Dict[str, Any]] = None
                    ) -> Dict[str, Optional[Tuple[int, int]]]:
    """Rights and wrongs per modality for a finished session."""
    args = (nback, crab, jaeggi_scoring, variable_list, modalities, session)
    if USING_NATIVE:
        return _native.analyze_session(*args)
    return _analyze_session_py(*args)


def aggregate_day_scores(style: Any, entries: Sequence[Sequence[float]],
                         advance: float = 80.0,
                         fallback: float = 50.0) -> Tuple[float, float]:
    """Collapse one day's sessions into a (mean, max) score pair."""
    if USING_NATIVE:
        return _native.aggregate_day_scores(style, entries, advance, fallback)
    return _aggregate_day_scores_py(style, entries, advance, fallback)


def rounded_rect_vertices(lx: int, rx: int, by: int, ty: int,
                          cr: int) -> List[int]:
    """A 40-vertex rounded rectangle as a flat ``[x, y, ...]`` list."""
    if USING_NATIVE:
        return _native.rounded_rect_vertices(lx, rx, by, ty, cr)
    return _rounded_rect_vertices_py(lx, rx, by, ty, cr)


def variable_nback_list(count: int, back: int) -> List[int]:
    """Per-trial n-back levels for variable n-back mode."""
    if USING_NATIVE:
        return _native.variable_nback_list(count, back)
    return _variable_nback_list_py(count, back)


def sample_unique(lo: int, hi: int, k: int) -> List[int]:
    """*k* distinct integers drawn from ``[lo, hi]``."""
    if USING_NATIVE:
        return _native.sample_unique(lo, hi, k)
    return _sample_unique_py(lo, hi, k)


def parse_stats_text(text: str) -> List[Dict[str, Any]]:
    """Parse a stats file into one dict per recorded session."""
    if USING_NATIVE:
        return _native.parse_stats_text(text)
    return _parse_stats_text_py(text)


def is_nback_match(current: Any, history: Sequence[Any],
                   nback_trial: int) -> Optional[bool]:
    """Whether *current* matches ``history[nback_trial]``.

    ``None`` when that trial is out of range — the comparison cannot be
    made, which is not the same as "no match".
    """
    if USING_NATIVE:
        return _native.is_nback_match(current, history, nback_trial)
    return _is_nback_match_py(current, history, nback_trial)


def mean_tail(seq: Sequence[float], tail: int = 0) -> float:
    """Mean of the last *tail* items; ``0`` means the whole sequence."""
    if USING_NATIVE:
        return _native.mean_tail(seq, tail)
    return _mean_tail_py(seq, tail)


def count_feedback_pixels(rgba: Sequence[int], width: int, height: int,
                          y0: Optional[int] = None,
                          y1: Optional[int] = None) -> Tuple[int, int, int]:
    """Count feedback-palette pixels in the public band of a frame."""
    width, height = int(width), int(height)
    lo, hi = default_band(height)
    lo = max(0, int(y0) if y0 is not None else lo)
    hi = min(height, int(y1) if y1 is not None else hi)
    if USING_NATIVE and hasattr(_native, 'count_feedback_pixels'):
        return _native.count_feedback_pixels(bytes(rgba), width, height, lo, hi)
    return count_feedback_pixels_py(rgba, width, height, lo, hi)


def count_feedback_label_runs(rgba: Sequence[int], width: int, height: int,
                              y0: Optional[int] = None,
                              y1: Optional[int] = None
                              ) -> Tuple[int, int, int]:
    """Count feedback *labels* in the public band of a frame."""
    width, height = int(width), int(height)
    lo, hi = default_band(height)
    lo = max(0, int(y0) if y0 is not None else lo)
    hi = min(height, int(y1) if y1 is not None else hi)
    if USING_NATIVE and hasattr(_native, 'count_feedback_label_runs'):
        return _native.count_feedback_label_runs(bytes(rgba), width, height,
                                                 lo, hi)
    return count_feedback_label_runs_py(rgba, width, height, lo, hi)


def maybe_hint_compile() -> None:
    """Print a one-line hint when the C module is absent."""
    if USING_NATIVE or os.environ.get('BW_SILENT_FALLBACK'):
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print('bwaccel: C extension not found, using Python fallback. '
          'Build it with:  %s "%s" build_ext --inplace'
          % (sys.executable, os.path.join(root, 'setup.py')),
          file=sys.stderr)
