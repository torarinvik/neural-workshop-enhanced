# -*- coding: utf-8 -*-
"""Pure-Python implementations of every accelerated kernel.

These define the contract: the C extension in ``native/bwcore.c`` must
produce the same results, and the test suite checks both against each
other. When the extension is missing these run the game unaided.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _nonmatch_choice(prev: int, hi: int) -> int:
    """A value in [1, hi] that is deliberately not *prev*."""
    v = random.randint(1, hi)
    if v == prev:
        v = 1 if v == hi else v + 1
    return v


def _compute_bt_sequence_py(num_trials: int, nback: int, n_pos: int = 6,
                            n_audio: int = 6, n_both: int = 2,
                            pos_choices: int = 8,
                            audio_choices: int = 8) -> List[List[int]]:
    """Construct a sequence with exact match counts in O(T)."""
    T = num_trials - nback
    if num_trials < 1 or nback < 1 or T < 1:
        raise ValueError('num_trials must be > nback and both must be positive')
    if n_both < 0 or n_pos < n_both or n_audio < n_both:
        raise ValueError('cannot realize requested match counts')
    if pos_choices < 2 or audio_choices < 2:
        raise ValueError('pos_choices and audio_choices must be >= 2')
    n_pos_only = n_pos - n_both
    n_aud_only = n_audio - n_both
    n_neither = T - n_pos_only - n_aud_only - n_both
    if n_neither < 0:
        raise ValueError('cannot realize requested match counts with this trial/n-back')

    kind = ([3] * n_both +
            [1] * n_pos_only +
            [2] * n_aud_only +
            [0] * n_neither)
    random.shuffle(kind)

    pos = [random.randint(1, pos_choices) for _ in range(nback)]
    audio = [random.randint(1, audio_choices) for _ in range(nback)]

    for k in kind:
        if k & 1:
            pos.append(pos[-nback])
        else:
            pos.append(_nonmatch_choice(pos[-nback], pos_choices))
        if k & 2:
            audio.append(audio[-nback])
        else:
            audio.append(_nonmatch_choice(audio[-nback], audio_choices))
    return [pos, audio]


def _crab_back(x: int, nback: int) -> int:
    """Crab-back reverses each run of N, so the lag varies by trial."""
    return 1 + 2 * (x % nback)


def _resolve_back(x: int, nback: int, crab: bool,
                  variable_list: Optional[Sequence[int]]) -> int:
    """How many trials back trial *x* should be compared against."""
    back = _crab_back(x, nback) if crab else nback
    if variable_list is not None:
        idx = x - back
        if 0 <= idx < len(variable_list):
            back = variable_list[idx]
    return max(1, back)


def _score_direct(data: Sequence[Any], inp: Optional[Sequence[Any]],
                  nback: int, crab: bool, jaeggi: bool,
                  variable_list: Optional[Sequence[int]]) -> Tuple[int, int]:
    """Rights and wrongs for one stimulus stream matched against itself."""
    rights = wrongs = 0
    n = len(data)
    for x in range(nback, n):
        back = _resolve_back(x, nback, crab, variable_list)
        if back > x:
            continue
        match = data[x] == data[x - back]
        inpv = bool(inp[x]) if inp is not None and x < len(inp) else False
        rights += int(match and inpv)
        wrongs += int(match ^ inpv)
        if jaeggi:
            rights += int((not match) and (not inpv))
    return rights, wrongs


def _analyze_session_py(
        nback: int, crab: bool = False, jaeggi_scoring: bool = False,
        variable_list: Optional[Sequence[int]] = None,
        modalities: Optional[Sequence[str]] = None,
        session: Optional[Dict[str, Any]] = None
) -> Dict[str, Optional[Tuple[int, int]]]:
    """Rights and wrongs per modality for a finished session."""
    if modalities is None or session is None:
        raise TypeError('modalities and session are required')
    out = {}
    for mod in modalities:
        if mod == 'arithmetic':
            out[mod] = None
            continue
        if mod in ('visvis', 'visaudio', 'audiovis'):
            now_key = 'vis' if mod.startswith('vis') else 'audio'
            then_key = 'vis' if mod.endswith('vis') else 'audio'
            now = session.get(now_key)
            then = session.get(then_key)
            inp = session.get(mod + '_input')
            if now is None or then is None:
                continue
            n = min(len(now), len(then))
            rights = wrongs = 0
            for x in range(nback, n):
                back = _resolve_back(x, nback, crab, variable_list)
                if back > x:
                    continue
                match = now[x] == then[x - back]
                inpv = bool(inp[x]) if inp is not None and x < len(inp) else False
                rights += int(match and inpv)
                wrongs += int(match ^ inpv)
                if jaeggi_scoring:
                    rights += int((not match) and (not inpv))
            out[mod] = (rights, wrongs)
        else:
            data = session.get(mod)
            inp = session.get(mod + '_input')
            if data is None:
                continue
            out[mod] = _score_direct(data, inp, nback, crab, jaeggi_scoring, variable_list)
    return out


_STYLE = {
    'N': 0, '%': 1, 'N.%': 2, 'N+2*%-1': 3, 'N+10/3+4/3': 4,
}


def _aggregate_day_scores_py(style: Any, entries: Sequence[Sequence[float]],
                             advance: float = 80.0,
                             fallback: float = 50.0) -> Tuple[float, float]:
    """Collapse one day's sessions into a (mean, max) score pair."""
    if not isinstance(style, int):
        style = _STYLE[style]
    if style == 4:
        den = advance - fallback or 1.0
        m = 1.0 / den
        b = -m * fallback
    scores = []
    for entry in entries:
        nback, percent = entry[0], entry[1]
        if style == 0:
            score = float(nback)
        elif style == 1:
            score = 0.01 * percent
        elif style == 2:
            score = nback + 0.01 * percent
        elif style == 3:
            score = nback - 1 + 2 * 0.01 * percent
        else:
            score = nback + b + m * percent
        scores.append(score)
    if not scores:
        return (0.0, 0.0)
    return (sum(scores) / float(len(scores)), max(scores))


def _rounded_rect_vertices_py(lx: int, rx: int, by: int, ty: int,
                              cr: int) -> List[int]:
    """A 40-vertex rounded rectangle as a flat [x, y, ...] list."""
    # Python 3: ranges must be materialised before concatenation.
    sweep_up = list(range(0, 91, 10))
    sweep_dn = list(range(90, -1, -10))
    x = ([lx + int(cr * (1 - math.cos(math.radians(i)))) for i in sweep_up] +
         [rx - int(cr * (1 - math.sin(math.radians(i)))) for i in sweep_up] +
         [rx - int(cr * (1 - math.sin(math.radians(i)))) for i in sweep_dn] +
         [lx + int(cr * (1 - math.cos(math.radians(i)))) for i in sweep_dn])
    y = ([by + int(cr * (1 - math.sin(math.radians(i)))) for i in sweep_up + sweep_dn] +
         [ty - int(cr * (1 - math.sin(math.radians(i)))) for i in sweep_up + sweep_dn])
    xy = []
    for a, b in zip(x, y):
        xy.extend((a, b))
    return xy


def _variable_nback_list_py(count: int, back: int) -> List[int]:
    """Per-trial n-back levels for variable n-back mode."""
    # Beta(back/2, 1) == U^(2/back)
    inv = 2.0 / float(back)
    out = []
    for _ in range(count):
        u = random.random()
        if u <= 0.0:
            u = 1e-12
        v = int(u ** inv * back + 1)
        if v < 1:
            v = 1
        if v > back:
            v = back
        out.append(v)
    return out


def _sample_unique_py(lo: int, hi: int, k: int) -> List[int]:
    """*k* distinct integers drawn from [lo, hi]."""
    return random.sample(range(lo, hi + 1), k)


def _parse_stats_text_py(text: str) -> List[Dict[str, Any]]:
    """Parse a stats file into one dict per recorded session."""
    records = []
    for line in text.splitlines():
        if not line or line[0] not in '0123456789':
            continue
        if len(line) < 19:
            continue
        try:
            y = int(line[0:4]); mo = int(line[5:7]); d = int(line[8:10])
            H = int(line[11:13]); M = int(line[14:16]); S = int(line[17:19])
        except ValueError:
            continue
        sep = '\t' if '\t' in line else ','
        cols = line.split(sep)
        if len(cols) < 9:
            continue

        def _ival(idx: int, default: int = 0) -> int:
            if idx >= len(cols):
                return default
            try:
                return int(cols[idx])
            except (TypeError, ValueError):
                return default

        cats = [_ival(9 + i, 0) for i in range(16)]
        sesstime = 0
        if len(cols) > 25:
            try:
                sesstime = int(round(float(cols[25])))
            except (TypeError, ValueError):
                sesstime = 0
        records.append({
            'year': y, 'month': mo, 'day': d,
            'hour': H, 'minute': M, 'second': S,
            'percent': _ival(2), 'mode': _ival(3), 'nback': _ival(4),
            'ticks': _ival(5), 'trials': _ival(6),
            'manual': _ival(7), 'session': _ival(8),
            'sesstime': sesstime, 'cats': cats,
        })
    return records


def _is_nback_match_py(current: Any, history: Sequence[Any],
                       nback_trial: int) -> Optional[bool]:
    """Whether *current* matches history[nback_trial]; None if out of range."""
    if nback_trial < 0 or nback_trial >= len(history):
        return None
    return current == history[nback_trial]


def _mean_tail_py(seq: Sequence[float], tail: int = 0) -> float:
    """Mean of the last *tail* items; 0 means the whole sequence."""
    if not seq:
        return 0.0
    chunk = seq[-tail:] if tail > 0 else seq
    if not chunk:
        return 0.0
    return sum(chunk) / float(len(chunk))


