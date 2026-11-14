# -*- coding: utf-8 -*-
"""What Happens Next: the start of a clip, and which ending is its own.

The first part of a short clip plays on a loop. Below it, a few short
stretches of video play side by side, and one of them is what really
came next. The rest are decoys, and the ladder is the decoys:

* rung 1: the true continuation against a stretch of some other clip --
  a different room, different people, nearly free;
* from rung 4 the true continuation **played backwards**: the same
  people, the same place, the same frames, and only the direction of
  time to tell them apart -- a ball falling up, a diver leaving the
  water;
* from rung 8 a stretch from **later** in the same clip, the last
  stretch of the opening played again, and one from the middle of the
  opening: right scene, wrong moment;
* from rung 12 the continuation **skipping ahead** by half its own
  length, which joins on almost as well as the truth;
* from rung 16 no other clips at all: every option is from the same
  clip, so nothing but what happens next can tell them apart;
* and the number of options grows from two to six;
* past rung 20 the opening shown gets shorter, down to a quarter of
  it, so there is less run-up to read the action from.

A choice is right or wrong, so there is no par: green means the true
continuation was picked. Guessing is right one time in the number of
options, which the ladder takes from a half to a sixth.

Nothing here touches pyglet or ffmpeg: a clip is a list of frames, and
the decoys are slices of lists. :mod:`neural_workshop.ui.whatnext`
decodes and plays them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

from .videoclips import STILL, difference

MOST_CHOICES = 6

KINDS = ('other', 'reversed', 'later', 'replay', 'earlier', 'skipped')


class Grade(NamedTuple):
    rung: int
    choices: int
    kinds: Tuple[str, ...]
    #: Share of the opening shown, counted back from where it ends.
    context: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = ['other']
    if r >= 4:
        kinds.append('reversed')
    if r >= 8:
        kinds += ['later', 'replay', 'earlier']
    if r >= 12:
        kinds.append('skipped')
    if r >= 16:
        kinds.remove('other')
    return Grade(r, min(MOST_CHOICES, 2 + (r - 1) // 3), tuple(kinds),
                 1.0 if r <= 20 else max(0.25, 1.0 - 0.075 * (r - 20)))


Frames = List[bytes]


class Puzzle(NamedTuple):
    opening: Frames
    options: Tuple[Frames, ...]
    answer: int
    #: What each option is: 'truth' or a kind of decoy.
    kinds: Tuple[str, ...]


def spans(length: int) -> Tuple[int, int]:
    """Where the opening ends and how long a continuation runs."""
    cut = int(length * 0.4)
    piece = max(4, min(int(length * 0.15), 20))
    return cut, piece


def unlike(one: Frames, two: Frames, floor: float = STILL) -> bool:
    """Whether two stretches can be told apart by looking."""
    middle = min(len(one), len(two)) // 2
    return max(difference(one[0], two[0]),
               difference(one[middle], two[middle]),
               difference(one[-1], two[-1])) >= floor


def decoy(kind: str, frames: Frames, other: Optional[Frames]
          ) -> Optional[Frames]:
    cut, piece = spans(len(frames))
    truth = frames[cut:cut + piece]
    if kind == 'reversed':
        return truth[::-1]
    if kind == 'replay':
        return frames[cut - piece:cut] if cut >= piece else None
    if kind == 'earlier':
        start = cut // 2 - piece // 2
        return frames[start:start + piece] if start >= 0 else None
    if kind == 'later':
        start = cut + 2 * piece
        return frames[start:start + piece] \
            if start + piece <= len(frames) else None
    if kind == 'skipped':
        start = cut + piece // 2
        return frames[start:start + piece] \
            if start + piece <= len(frames) else None
    if kind == 'other' and other:
        ocut, _opiece = spans(len(other))
        stretch = other[ocut:ocut + piece]
        return stretch if len(stretch) == piece else None
    return None


def plan(level: Grade, rng: random.Random) -> List[str]:
    """The decoys a puzzle asks for, in a preferred order. The same-clip
    kinds are used once each; other clips fill the rest when allowed."""
    same = [k for k in level.kinds if k != 'other']
    rng.shuffle(same)
    wanted = level.choices - 1
    if 'other' in level.kinds:
        # Below rung 16 at least one decoy is another clip, and the
        # rest mix.
        picks = ['other'] + same
        picks = picks[:wanted]
        while len(picks) < wanted:
            picks.append('other')
        return picks
    return same


def build(frames: Frames, others: Sequence[Frames], level: Grade,
          rng: random.Random) -> Optional[Puzzle]:
    """A puzzle from a clip, or None when this clip will not make one:
    too short, too still, or too few decoys that can be told apart."""
    cut, piece = spans(len(frames))
    if cut + piece > len(frames) or cut < piece:
        return None
    truth = frames[cut:cut + piece]
    picked: List[Tuple[str, Frames]] = []
    spare = list(others)
    order = plan(level, rng)
    # Kinds that cannot be made from this clip are swapped for any other
    # allowed kind that can, so the count of options holds.
    fallback = [k for k in ('reversed', 'replay', 'later', 'earlier',
                            'skipped')
                if k in level.kinds] + (['other'] * 6
                                        if 'other' in level.kinds else [])
    for kind in order + fallback:
        if len(picked) == level.choices - 1:
            break
        if kind != 'other' and any(k == kind for k, _f in picked):
            continue
        other = spare.pop(0) if kind == 'other' and spare else None
        stretch = decoy(kind, frames, other)
        if stretch is None or not unlike(stretch, truth):
            continue
        if any(not unlike(stretch, f) for _k, f in picked):
            continue
        picked.append((kind, stretch))
    if len(picked) < level.choices - 1:
        return None
    answer = rng.randrange(level.choices)
    options = [f for _k, f in picked]
    kinds = [k for k, _f in picked]
    options.insert(answer, truth)
    kinds.insert(answer, 'truth')
    shown = max(piece, int(cut * level.context))
    return Puzzle(frames[cut - shown:cut], tuple(options), answer,
                  tuple(kinds))


def describe(kind: str) -> str:
    from .i18n import _
    return {'truth': _('what happened'), 'other': _('another clip'),
            'reversed': _('played backwards'), 'later': _('later on'),
            'replay': _('the opening again'),
            'earlier': _('from the opening'),
            'skipped': _('skipped ahead')}.get(kind, kind)
