# -*- coding: utf-8 -*-
"""The shared engine of the Emotion tasks: a round of questions about
how someone feels.

Each task deals a :class:`Round` of :class:`Item`\\ s. An item shows
something -- a face, a comment, a dialogue, a story -- and asks one or
more :class:`Step`\\ s, each a choice among at most eight answers: which
emotion it is, then perhaps the second strongest, or why, or how
strongly each of four emotions is felt. An item is right when every
step is right (or, for intensities, when the steps together are close
enough). After each item the right answer is shown for a moment, with
a chime for right and a low note for wrong. The round passes when
enough items are right.

The answers are on buttons under the item; click one, or press its
number. Each item has its own time.

For the agent boundary: ports 0-7 pick the answer of that number.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, NamedTuple, Optional, Sequence, Tuple

from . import hand as H
from .i18n import _

PORTS = 8
EVENTS = tuple(range(PORTS))
TICK, RIGHT, WRONG, DONE, MISS = range(5)
PATCHES = ('wood', 'bell', 'growl', 'bell', 'growl')
SHOW = 1.4                     # seconds the right answer stays up

# The answer buttons on the 1000 by 640 screen.
OPT_Y = (112.0, 56.0)          # two rows
OPT_H = 44.0
#: Wide answers: a stack of full-width rows, the first centred here.
WIDE_Y, WIDE_H, WIDE_GAP = 236.0, 34.0, 40.0
#: Over wide answers, the question sits here and the text box ends above.
WIDE_ASK_Y, WIDE_BOX = 278.0, (60.0, 300.0, 880.0, 262.0)


class Step(NamedTuple):
    ask: str                       # the question, e.g. "Which emotion?"
    options: Tuple[str, ...]
    answer: int
    value: Tuple[float, ...] = ()  # for intensities: what each option is
    wide: bool = False             # long answers: one full-width row each


class Item(NamedTuple):
    prompt: str                    # text shown (may be empty for a face)
    steps: Tuple[Step, ...]
    seconds: float
    face: object = None            # a face to show (see emotiondata)
    flash: float = 0.0             # seconds the face shows, 0 for always
    crop: str = ''                 # '', 'eyes' or 'mouth'
    truth: str = ''                # said after the answer
    tolerance: float = -1.0        # >= 0: intensity steps, summed error
    title: str = ''                # a heading over the prompt


class Round(NamedTuple):
    level: object
    items: Tuple[Item, ...]
    need: int


def option_rect(k: int, n: int, wide: bool = False
                ) -> Tuple[float, float, float, float]:
    """(x, y, w, h) of answer button *k* of *n*: one row up to four, two
    rows above that; or, for *wide* answers, one full-width row each."""
    if wide:
        return 60.0, WIDE_Y - k * WIDE_GAP - WIDE_H / 2, 880.0, WIDE_H
    per = n if n <= 4 else math.ceil(n / 2)
    row, col = divmod(k, per)
    if n <= 4:
        y = OPT_Y[0] - 28
    else:
        y = OPT_Y[row]
    w = min(220.0, (960.0 - 12.0 * (per - 1)) / per)
    total = per * w + 12.0 * (per - 1)
    x = 500.0 - total / 2 + col * (w + 12.0)
    return x, y - OPT_H / 2, w, OPT_H


def judge(item: Item, picks: Sequence[int]) -> bool:
    if item.tolerance >= 0:
        err = sum(abs(s.value[p] - s.value[s.answer])
                  for s, p in zip(item.steps, picks))
        return err <= item.tolerance + 1e-9
    return all(p == s.answer for s, p in zip(item.steps, picks))


class Run(H.HandRun):
    def __init__(self, rnd: Round) -> None:
        super().__init__(sum(i.seconds for i in rnd.items) +
                         SHOW * len(rnd.items) + 2.0)
        self.round, self.level = rnd, rnd.level
        self.hand.to(500.0, 20.0)          # out of the way, under the buttons
        self.k = 0                     # the item asked
        self.picks: List[int] = []     # answers given to its steps
        self.marks: List[bool] = []    # each item done: right or not
        self.since = 0.0               # when the item (or showing) began
        self.showing = False
        self.last: Optional[Tuple[bool, Tuple[int, ...]]] = None

    def item(self) -> Optional[Item]:
        return self.round.items[self.k] if self.k < len(self.round.items) \
            else None

    def step_now(self) -> Optional[Step]:
        it = self.item()
        if it is None or self.showing or len(self.picks) >= len(it.steps):
            return None
        return it.steps[len(self.picks)]

    def face_visible(self) -> bool:
        it = self.item()
        return it is not None and (it.flash <= 0 or self.showing or
                                   self.t - self.since < it.flash)

    def choose(self, k: int) -> None:
        if self.result is not None:
            return
        st = self.step_now()
        if st is None or not 0 <= k < len(st.options):
            return
        self.picks.append(k)
        self.note(0.05, 600.0 + 40 * k, TICK, 0.2)
        if len(self.picks) == len(self.item().steps):
            self._grade(judge(self.item(), self.picks))

    def click(self) -> None:
        st = self.step_now()
        if st is None:
            return
        x, y = self.hand.x, self.hand.y
        for k in range(len(st.options)):
            bx, by, bw, bh = option_rect(k, len(st.options), st.wide)
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return self.choose(k)

    def _grade(self, right: bool) -> None:
        self.marks.append(right)
        self.last = (right, tuple(self.picks))
        self.showing = True
        self.since = self.t
        if right:
            self.note(0.3, 880.0, RIGHT, 0.4)
        else:
            self.note(0.35, 180.0, WRONG, 0.4)
        n, need = len(self.round.items), self.round.need
        wrong = self.marks.count(False)
        if wrong > n - need:
            self.result = (False, _('%d of %d right, %d needed') % (
                self.marks.count(True), n, need))
            self.note(0.5, 90.0, MISS, 0.5)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        it = self.item()
        if it is None:
            return
        if self.showing:
            if self.t - self.since >= SHOW:
                self.showing = False
                self.k += 1
                self.picks = []
                self.since = self.t
                if self.k >= len(self.round.items):
                    self._finish()
            return
        if self.t - self.since >= it.seconds:
            while len(self.picks) < len(it.steps):
                self.picks.append(-1)
            self._grade(False)

    def _finish(self) -> None:
        right = self.marks.count(True)
        n, need = len(self.round.items), self.round.need
        if right >= need:
            self.result = (True, _('%d of %d right') % (right, n))
            self.note(0.6, 1320.0, DONE, 0.5)
        else:
            self.result = (False, _('%d of %d right, %d needed') % (
                right, n, need))
            self.note(0.5, 90.0, MISS, 0.5)


def act(run: Run, port: int) -> None:
    if 0 <= port < PORTS:
        run.choose(port)
    elif port == H.PRESS:
        run.click()


# --- players -------------------------------------------------------------------

def autopilot(run: Run) -> List[int]:
    """Knows every answer."""
    st = run.step_now()
    if st is None or run.result is not None:
        return []
    return [st.answer]


def always(k: int):
    def pilot(run: Run) -> List[int]:
        st = run.step_now()
        if st is None or run.result is not None:
            return []
        return [min(k, len(st.options) - 1)]
    return pilot


def at_random(seed: int):
    import random
    draw = random.Random(seed)

    def pilot(run: Run) -> List[int]:
        st = run.step_now()
        if st is None or run.result is not None:
            return []
        return [draw.randrange(len(st.options))]
    return pilot


def play(rnd: Round, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    return H.play(Run(rnd), pilot, EVENTS, act, dt)


def need_mixed(chances: Sequence[float], ceiling: float = 0.03) -> int:
    """The fewest right answers out of ``len(chances)`` items, item *i*
    guessed right with ``chances[i]``, that guessing reaches no more
    than *ceiling* of the time."""
    dist = [1.0]
    for c in chances:
        nxt = [0.0] * (len(dist) + 1)
        for j, p in enumerate(dist):
            nxt[j] += p * (1 - c)
            nxt[j + 1] += p * c
        dist = nxt
    tail = 0.0
    for need in range(len(dist) - 1, -1, -1):
        if tail + dist[need] > ceiling:
            return need + 1
        tail += dist[need]
    return 0


def need_for(n: int, chance: float, ceiling: float = 0.03) -> int:
    """The fewest right answers out of *n* that guessing at *chance*
    reaches no more than *ceiling* of the time."""
    from math import comb
    for need in range(n + 1):
        p = sum(comb(n, j) * chance ** j * (1 - chance) ** (n - j)
                for j in range(need, n + 1))
        if p <= ceiling:
            return need
    return n
