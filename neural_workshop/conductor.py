# -*- coding: utf-8 -*-
"""Conductor: beat time for the orchestra and bring the players in.

An orchestra pit seen from the podium, its sections sitting where they
sit: strings to the left, woodwind in the middle, brass to the right,
drums at the back. The drummer gives the pulse. On every beat, beat:
flick the pointer downwards. The score along the top says what else is
wanted and when -- "Beat 5: bring in the brass" (click that section, on
that beat), "Beat 9: louder" (Up arrow, on that beat), "Beat 12:
softer" (Down arrow), "Beat 14: cut the strings" (click them again).
A section that has been brought in plays; one that has not is silent.

The ladder:

* rungs 1-3: eight slow beats, one cue, the beat number shown, three
  slips forgiven;
* rungs 4-6: twelve beats, two cues, louder and softer;
* rungs 7-9: the beat number is shown only on the first of each four;
  cuts as well as entries;
* rungs 10-12: quicker; stray beats now count as slips;
* rungs 13-15: no beat numbers after the first four;
* rungs 16-19: the tempo bends -- follow the drummer;
* from rung 20: longer pieces, more cues, a quicker pulse, a narrower
  moment and fewer slips forgiven.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec
from .i18n import _

LOUDER, SOFTER = H.KEYS, H.KEYS + 1
PORTS = H.KEYS + 2
EVENTS = tuple(range(PORTS))
SECTIONS = (_('strings'), _('woodwind'), _('brass'), _('drums'))
SEATS: Tuple[Vec, ...] = ((-4.5, 0.0, -5.0), (0.0, 0.0, -7.0),
                          (4.5, 0.0, -5.0), (0.0, 0.8, -10.0))
VIEW = H.lens((0.0, 4.5, 3.0), (0.0, 0.5, -7.0), 600.0, 500.0, 250.0)
NEAR = 70.0                    # how near a section the click has to be
FLICK = 40.0                   # how far down a beat has to go
DRUM, STRINGS, WIND, BRASS, SLIP, DONE = range(6)
PATCHES = ('wood', 'organ', 'flute', 'brass', 'growl', 'bell')
SCALE = (0, 4, 7, 12, 7, 4, 0, -5)


class Grade(NamedTuple):
    rung: int
    beats: int
    cues: int
    period: float              # seconds a beat
    moment: float              # how near the beat, either side
    kinds: Tuple[str, ...]
    numbers: str               # 'all', 'bars' or 'start'
    strict: bool
    bend: float                # how much the tempo wanders
    slips: int                 # forgiven


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        beats=8 if r < 4 else 12 if r < 10 else 16 if r < 20
        else 20 + 2 * (top // 2),
        cues=1 if r < 4 else 2 if r < 7 else 3 if r < 13 else 4 if r < 20
        else 5 + top // 3,
        period=(1.0 if r < 4 else 0.85 if r < 10 else 0.7 if r < 16
                else 0.62 if r < 20 else max(0.42, 0.6 - 0.006 * top)),
        moment=(0.3 if r < 4 else 0.24 if r < 10 else 0.19 if r < 20
                else max(0.1, 0.18 - 0.003 * top)),
        kinds=(('enter',) if r < 4 else ('enter', 'loud', 'soft') if r < 7
               else ('enter', 'cut', 'loud', 'soft')),
        numbers='all' if r < 7 else 'bars' if r < 13 else 'start',
        strict=r >= 10,
        bend=0.0 if r < 16 else 0.18 if r < 20 else min(0.3, 0.2
                                                        + 0.005 * top),
        slips=3 if r < 7 else 2 if r < 13 else 1 if r < 20 else 0)


class Cue(NamedTuple):
    beat: int                  # counted from 1
    kind: str
    section: int
    text: str


class Piece(NamedTuple):
    level: Grade
    times: Tuple[float, ...]   # when each beat falls
    cues: Tuple[Cue, ...]
    key: int
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Piece]:
    t, times = 2.0, []
    wave = draw.uniform(0, 6.28)
    for k in range(level.beats):
        times.append(t)
        t += level.period * (1.0 + level.bend * math.sin(wave + k * 0.45))
    beats = sorted(draw.sample(range(3, level.beats + 1), level.cues))
    playing = [True, False, False, True]
    cues: List[Cue] = []
    for beat in beats:
        kinds = [k for k in level.kinds
                 if (k != 'enter' or not all(playing)) and
                 (k != 'cut' or sum(playing) > 1)]
        kind = draw.choice(kinds)
        section = -1
        if kind == 'enter':
            section = draw.choice([s for s in range(4) if not playing[s]])
            playing[section] = True
            text = _('Beat %d: bring in the %s.') % (beat, SECTIONS[section])
        elif kind == 'cut':
            section = draw.choice([s for s in range(4) if playing[s]])
            playing[section] = False
            text = _('Beat %d: cut the %s.') % (beat, SECTIONS[section])
        else:
            text = (_('Beat %d: louder.') if kind == 'loud'
                    else _('Beat %d: softer.')) % beat
        cues.append(Cue(beat, kind, section, text))
    return Piece(level, tuple(times), tuple(cues), draw.randrange(12),
                 draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Piece:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


def spot(section: int) -> Tuple[float, float]:
    q = VIEW.see(SEATS[section])
    return q[0], q[1] + 30.0


class Run(H.HandRun):
    def __init__(self, piece: Piece) -> None:
        super().__init__(piece.times[-1] + 1.5)
        self.piece, self.level = piece, piece.level
        self.playing = [True, False, False, True]
        self.loud = 1                  # 0 soft, 1, 2 loud
        self.beaten = [False] * len(piece.times)
        self.done = [False] * len(piece.cues)
        self.slips = 0
        self.fall = 0.0                # how far down this flick has come
        self.last_y = self.hand.y
        self.next = 0                  # the next beat to sound
        self.judged = 0                # beats whose moment has passed
        self.flash = -1.0

    def near_beat(self) -> Optional[int]:
        """The beat whose moment this is."""
        for k, t in enumerate(self.piece.times):
            if abs(self.t - t) <= self.level.moment:
                return k
        return None

    def cue_at(self, k: int) -> Optional[int]:
        for j, cue in enumerate(self.piece.cues):
            if cue.beat == k + 1:
                return j
        return None

    def shown_beat(self) -> str:
        """The beat number as the screen shows it, or nothing."""
        k = self.next
        if k < 1:
            return ''
        how = self.level.numbers
        if how == 'all' or how == 'bars' and (k - 1) % 4 == 0 or \
                how == 'start' and k <= 4:
            return '%d' % k
        return ''

    def _slip(self) -> None:
        self.slips += 1
        self.note(0.15, 110.0, SLIP, 0.4)
        if self.slips > self.level.slips:
            self.result = (False, _('The orchestra fell apart'))

    def _mark(self, did: str, section: int = -1) -> None:
        """A beat, a click or a key at this moment."""
        k = self.near_beat()
        if k is None:
            if did != 'beat' or self.level.strict:
                self._slip()
            return
        j = self.cue_at(k)
        cue = self.piece.cues[j] if j is not None else None
        if did == 'beat':
            self.beaten[k] = True
            return
        if cue is None or self.done[j] or (
                did in ('loud', 'soft') and cue.kind != did) or (
                did == 'click' and (cue.kind not in ('enter', 'cut') or
                                    cue.section != section)):
            return self._slip()
        self.done[j] = True
        self.beaten[k] = True
        self.flash = self.t
        if cue.kind == 'enter':
            self.playing[section] = True
        elif cue.kind == 'cut':
            self.playing[section] = False
        else:
            self.loud = max(0, min(2, self.loud + (1 if did == 'loud'
                                                   else -1)))

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        for s in range(4):
            x, y = spot(s)
            if math.hypot(self.hand.x - x, self.hand.y - y) <= NEAR:
                return self._mark('click', s)

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if self.result is None:
            self._mark('loud' if port == LOUDER else 'soft')

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        level, piece = self.level, self.piece
        dy = self.hand.y - self.last_y
        self.last_y = self.hand.y
        if dy < 0:
            before = self.fall
            self.fall -= dy
            if before < FLICK <= self.fall:
                self._mark('beat')
        elif dy > 0:
            self.fall = 0.0
        while self.next < len(piece.times) and \
                piece.times[self.next] <= self.t:
            k = self.next
            self.next += 1
            gain = (0.25, 0.4, 0.6)[self.loud]
            self.note(0.08, 150.0 if k % 4 else 110.0, DRUM,
                      0.5 if self.playing[3] else 0.25)
            base = 220.0 * 2 ** ((piece.key + SCALE[k % 8]) / 12.0)
            for s, (voice, mult, pan) in enumerate(((STRINGS, 1.0, -0.6),
                                                    (WIND, 2.0, 0.0),
                                                    (BRASS, 0.5, 0.6))):
                if self.playing[s]:
                    self.note(level.period * 0.9, base * mult, voice, gain,
                              pan=pan)
        while self.judged < len(piece.times) and \
                piece.times[self.judged] + level.moment < self.t:
            k = self.judged
            self.judged += 1
            j = self.cue_at(k)
            if j is not None and not self.done[j]:
                self._slip()
            elif not self.beaten[k]:
                self._slip()
            if self.result is not None:
                return
        if self.t >= self.end:
            self.note(0.5, 660.0, DONE, 0.5)
            self.result = (True, _('Bravo'))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Beat every beat and do every cue on its beat: one port a step."""
    if run.result is not None:
        return []
    hand, piece = run.hand, run.piece
    if hand.down:
        return [H.RELEASE]
    k = next((b for b in range(len(piece.times)) if not run.beaten[b] and
              piece.times[b] + run.level.moment * 0.5 > run.t), None)
    if k is None:
        return []
    now = run.t >= piece.times[k] - 0.02
    j = run.cue_at(k)
    cue = piece.cues[j] if j is not None and not run.done[j] else None
    if cue is not None and cue.kind in ('enter', 'cut'):
        x, y = spot(cue.section)
        move = H.toward(hand, x, y, tol=10.0)
        if move is not None:
            return [move]
        return [H.PRESS] if now else []
    if cue is not None:
        return [LOUDER if cue.kind == 'loud' else SOFTER] if now else []
    if not now:
        if hand.y < 400.0 or run.fall > 0:
            return [0]                          # lift the baton
        return []
    return [1 * 3]                              # and bring it down


def play(piece: Piece, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(piece), pilot, EVENTS, act, dt)
