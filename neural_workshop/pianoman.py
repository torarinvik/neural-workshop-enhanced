# -*- coding: utf-8 -*-
"""Piano Man: hear a melody, then play it back.

A short melody is played. Then the keyboard is yours: play the same
notes in the same order. One wrong key ends the trial.

Every melody is in a real scale -- pentatonic, major, minor, blues, a
mode -- and moves as tunes move, mostly by step with the odd leap, home
on its keynote when it is long enough to have a home. So what there is
to learn is how tunes go, not a string of unrelated pitches.

Nobody is asked for perfect pitch: one key is always marked. Low down
it is the first note of the melody, so the rest is a matter of how far
up or down each note goes from the last; high up it is the scale's
keynote, and the first note has to be found from that.

The ladder:

* rungs 1-3: two notes; each key lights as its note plays; C major
  pentatonic; the keys of the scale are tinted;
* rungs 4-6: three notes; nothing lights, the first key is marked;
  major scales too;
* rungs 7-9: four notes, in any key; minor scales; small leaps;
* rungs 10-12: five notes on two octaves; no tinted keys; uneven
  rhythm;
* rungs 13-15: six notes; blues and modes; other instruments; one
  hearing more, not two;
* from rung 16: the keynote is marked, not the first note; a note
  more every two rungs, to twenty-four; faster; no second hearing
  from rung 22.

For the agent boundary: port k presses key k, counted from the left
(black keys in their places); the last port asks to hear it again.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import showing
from .i18n import _

LOW = 60                       # the leftmost key: middle C
MOST_KEYS = 25
LISTEN = MOST_KEYS             # the port that asks to hear it again
PORTS = MOST_KEYS + 1
EVENTS = frozenset(range(PORTS))
SCALES = {
    'major pentatonic': (0, 2, 4, 7, 9),
    'major': (0, 2, 4, 5, 7, 9, 11),
    'minor': (0, 2, 3, 5, 7, 8, 10),
    'minor pentatonic': (0, 3, 5, 7, 10),
    'blues': (0, 3, 5, 6, 7, 10),
    'dorian': (0, 2, 3, 5, 7, 9, 10),
    'mixolydian': (0, 2, 4, 5, 7, 9, 10),
    'harmonic minor': (0, 2, 3, 5, 7, 8, 11),
}
NAMES = ('C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B')
BLACK = (1, 3, 6, 8, 10)


class Grade(NamedTuple):
    rung: int
    notes: int
    scales: Tuple[str, ...]
    keys: int            # on the keyboard
    any_key: bool        # the scale may start on any note
    lights: bool         # each key lights as its note plays
    mark: str            # 'first' note or the scale's 'keynote'
    tinted: bool         # the scale's keys are tinted
    leap: int            # how many scale steps a note may move
    uneven: bool         # rhythm
    beat: float          # seconds
    listens: int         # times it may be heard again
    patches: Tuple[str, ...]


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    penta = ('major pentatonic',)
    plain = penta + ('major',)
    minor = plain + ('minor', 'minor pentatonic')
    every = tuple(SCALES)
    piano = ('pluck',)
    others = ('pluck', 'bell', 'glass', 'organ', 'flute', 'clarinet')
    if r < 4:
        return Grade(r, 2, penta, 13, False, True, 'first', True, 1, False,
                     0.6, 2, piano)
    if r < 7:
        return Grade(r, 3, plain, 13, False, False, 'first', True, 1, False,
                     0.6, 2, piano)
    if r < 10:
        return Grade(r, 4, minor, 13, True, False, 'first', True, 2, False,
                     0.55, 2, piano)
    if r < 13:
        return Grade(r, 5, minor, 25, True, False, 'first', False, 2, True,
                     0.5, 2, piano)
    if r < 16:
        return Grade(r, 6, every, 25, True, False, 'first', False, 3, True,
                     0.45, 1, others)
    return Grade(r, min(24, 7 + (r - 16) // 2), every, 25, True, False,
                 'keynote', False, 4, True, max(0.28, 0.42 - 0.01 * (r - 16)),
                 1 if r < 22 else 0, others)


class Puzzle(NamedTuple):
    level: Grade
    scale: str
    keynote: int                 # 0 for C ... 11 for B
    melody: Tuple[int, ...]      # keys, from the left
    onsets: Tuple[float, ...]    # seconds from the melody's start
    lengths: Tuple[float, ...]
    mark: int                    # the key that is marked
    patch: str
    seed: int
    question: str


def freq(key: int) -> float:
    return 440.0 * 2.0 ** ((LOW + key - 69) / 12.0)


def in_scale(p: Puzzle, key: int) -> bool:
    return (LOW + key - p.keynote) % 12 in SCALES[p.scale]


def name(key: int) -> str:
    return NAMES[(LOW + key) % 12]


def is_black(key: int) -> bool:
    return (LOW + key) % 12 in BLACK


def solve(p: Puzzle) -> List[int]:
    return list(p.melody)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    scale = draw.choice(level.scales)
    keynote = draw.randrange(12) if level.any_key else 0
    steps = SCALES[scale]
    pool = [k for k in range(level.keys) if (LOW + k - keynote) % 12 in steps]
    homes = [i for i, k in enumerate(pool) if (LOW + k - keynote) % 12 == 0]
    middle = min(homes, key=lambda i: abs(pool[i] - level.keys // 2))
    n = level.notes
    for _attempt in range(500):
        # A marked first note may be any of the scale's; unmarked, the
        # melody leans on the keynote.
        at = middle if level.mark != 'first' and draw.random() < 0.4 \
            else draw.randrange(len(pool))
        line = [at]
        while len(line) < n:
            # Mostly by step; a leap now and then; seldom the same note.
            reach = 1 if draw.random() < 0.65 else level.leap
            move = draw.randint(-reach, reach)
            if move == 0 and (level.leap < 2 or draw.random() < 0.7):
                continue
            nxt = line[-1] + move
            if not 0 <= nxt < len(pool):
                continue
            if len(line) >= 3 and nxt == line[-2] and line[-1] == line[-3]:
                continue             # not a trill
            line.append(nxt)
        if n >= 5:
            # Home on the keynote, by a step if one will do it.
            home = min(homes, key=lambda i: abs(i - line[-2]))
            if home == line[-2] or abs(home - line[-2]) > max(2, level.leap):
                continue
            line[-1] = home
        if len(set(line)) < min(n, 3 if n > 2 else 2):
            continue
        break
    else:
        raise RuntimeError('no melody for rung %d' % rung)
    beats = [draw.choice((0.5, 0.5, 1.0, 1.0, 1.5)) if level.uneven else 1.0
             for _k in range(n)]
    beats[-1] = max(beats[-1], 1.5)
    onsets, t = [], 0.0
    for b in beats:
        onsets.append(t)
        t += b * level.beat
    melody = tuple(pool[i] for i in line)
    mark = melody[0] if level.mark == 'first' else pool[middle]
    return Puzzle(level, scale, keynote, melody, tuple(onsets),
                  tuple(b * level.beat for b in beats), mark,
                  draw.choice(level.patches), seed,
                  _('Listen, then play it back'))


def patches(p: Puzzle) -> tuple:
    return (showing.patch(p.patch, p.seed),)


class Run:
    """One trial: the melody plays, then the keys are counted."""

    LEAD = 0.7           # seconds before the melody starts

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.t = 0.0
        self.notes: List = []        # everything that sounds, in order
        self.starts: List[float] = []
        self.played: List[int] = []
        self.pressed_at = -9.0
        self.listens = puzzle.level.listens
        self.result: Optional[Tuple[bool, str]] = None
        self.ready = 0.0             # when the keys start to count
        self.deadline = 0.0
        self._sound(self.LEAD)

    def _sound(self, at: float) -> None:
        p = self.puzzle
        self.starts.append(at)
        for key, on, length in zip(p.melody, p.onsets, p.lengths):
            self.notes.append(showing.note(at + on, max(0.18, length * 0.9),
                                           freq(key), 0.0, 0.7))
        self.ready = at + p.onsets[-1] + p.lengths[-1]
        self.deadline = self.ready + 6.0 + 2.5 * len(p.melody)

    @property
    def playing(self) -> bool:
        """Whether the melody is still being played to the listener."""
        return self.t < self.ready

    def lit(self) -> Optional[int]:
        """The key the melody is on now, where the keys light."""
        if not self.puzzle.level.lights or not self.playing:
            return None
        p = self.puzzle
        since = self.t - self.starts[-1]
        for key, on, length in zip(p.melody, p.onsets, p.lengths):
            if on <= since < on + length * 0.9:
                return key
        return None

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.deadline:
            self.result = (False, _('Too slow'))

    def press(self, key: int) -> None:
        p = self.puzzle
        if self.result is not None or self.playing \
                or not 0 <= key < p.level.keys:
            return
        self.notes.append(showing.note(self.t, 0.35, freq(key), 0.0, 0.7))
        self.pressed_at = self.t
        self.played.append(key)
        want = p.melody[len(self.played) - 1]
        if key != want:
            self.result = (False, _('No: note %d was %s')
                           % (len(self.played), name(want)))
        elif len(self.played) == len(p.melody):
            self.result = (True, _('Right: all %d notes') % len(p.melody))

    def listen(self) -> None:
        if self.result is None and not self.playing and not self.played \
                and self.listens > 0:
            self.listens -= 1
            self._sound(self.t + 0.3)


def act(run: Run, port: int) -> None:
    if port == LISTEN:
        run.listen()
    else:
        run.press(port)


def autopilot(run: Run) -> List[int]:
    """Plays it back: the next note, once the melody is over."""
    if run.result is not None or run.playing:
        return []
    return [run.puzzle.melody[len(run.played)]]
