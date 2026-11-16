# -*- coding: utf-8 -*-
"""The Missing Word: put back the words that fell out, take out the
words that crept in.

A short passage of real text (Simple English Wikipedia, see
:mod:`neural_workshop.passages`), one sentence a line, has lost some of
its words:

    the rotation venus is slow

and, from rung 7, gained some it never had:

    a venusian day is longer than the a year

Under each line, between every two words, is a caret: a place a word
could go. Click a caret to see four words that could go there and click
one to put it in. Click a word to strike it out. Done (Enter) hands
the passage in; it passes when it reads exactly as it was written.
Reset (R) puts the passage back as dealt. The first and the last word
of a line are never missing, and no two missing words were next to each
other.

**What makes the gap the gap.** A word is only taken out where the
two words it leaves side by side are a pair that appears nowhere in the
54,000 sentences the task reads, and a word is only put in where it
makes such a pair on both sides. Every caret offers four words, drawn
the same way whether a word is missing there or not, so the offer says
nothing about where the gaps are.

The ladder:

* rungs 1-3: one sentence, one or two missing words;
* rungs 4-9: two sentences;
* rungs 7+: words that do not belong as well;
* rungs 10+: three sentences, and longer passages from rung 16;
* rungs 13+: the other words on offer are as common as the right one;
* rungs 19+: no count of the mistakes on the screen;
* above that the mistakes keep coming, one more every few rungs, until
  a quarter of the words are wrong, and then the clock shortens without
  end.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import hand as H
from . import passages as PS
from . import proofreader as PR
from . import sentences as S
from .i18n import _

DONE_KEY = H.KEYS              # 14: hand the passage in
RESET = H.KEYS + 1             # 15: put it back as dealt
PORTS = H.KEYS + 2
EVENTS = tuple(range(PORTS))
TICK, PICK, STRIKE, DONE, MISS = range(5)
PATCHES = ('wood', 'bell', 'wood', 'bell', 'growl')

KINDS = ('missing', 'extra')
FROM = {'missing': 1, 'extra': 7}
STRIKE_OUT = 'strike out'      # the one choice a clicked word offers

# Where things are: the lines and tiles of The Proofreader, a caret
# below each gap.
row_y, widths, centres, option_x = PR.row_y, PR.widths, PR.centres, \
    PR.option_x
TILE_H, GAP = PR.TILE_H, PR.GAP
CARET_DY = 30.0                # the caret sits this far below the line
CARET_R = 12.0
OPT_Y, OPT_W = PR.OPT_Y, PR.OPT_W
DONE_AT, RESET_AT = PR.DONE_AT, PR.RESET_AT
BUTTON_W, BUTTON_H = PR.BUTTON_W, PR.BUTTON_H


class Grade(NamedTuple):
    rung: int
    sentences: int
    kinds: Tuple[str, ...]
    errors: int
    hint: bool
    close: bool                # the other words as common as the right one
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    n = 1 if r < 4 else 2 if r < 10 else 3 if r < 16 else \
        min(6, 4 + (r - 16) // 6)
    kinds = tuple(k for k in KINDS if r >= FROM[k])
    errors = 1 + (r - 1) // 3 if r <= 30 else 10 + (r - 30) // 4
    cap = max(1, 9 * n // 4)
    errors = min(errors, cap)
    seconds = 40.0 + 20.0 * errors + 5.0 * n
    over = max(0, r - 25)
    if over and errors >= cap:
        seconds *= max(0.25, 1.0 - 0.02 * over)
    return Grade(r, n, kinds, errors, r < 19, r >= 13, round(seconds, 1))


class Tok(NamedTuple):
    id: int
    text: str


class Machine(NamedTuple):
    level: Grade
    original: Tuple[Tuple[str, ...], ...]
    rows: Tuple[Tuple[Tok, ...], ...]          # as dealt
    damage: Tuple[Tuple[str, int, int], ...]   # (kind, sentence, index)
    seed: int                                  # for the words on offer
    seconds: float


# --- words as they come ---------------------------------------------------

@functools.lru_cache(maxsize=1)
def _tokens() -> Tuple[str, ...]:
    """Every inside word of every sentence read: a word drawn from here
    is drawn as often as English uses it."""
    out = []
    for sent in S.bank()[:20000]:
        out.extend(w for w in sent.words[1:-1] if w.isalpha())
    return tuple(out)


def common_word(draw: random.Random) -> str:
    return draw.choice(_tokens())


def _unsaid(a: str, b: str) -> bool:
    return not PR.said(a, b)


# --- a passage, damaged ---------------------------------------------------

def _source(level: Grade, draw: random.Random):
    if level.sentences == 1:
        pool = S.choose((6, 12), S.TOP_RANK)
        if not pool:
            return None
        return PR._norm((draw.choice(pool).words,))
    bank = [p for p in PS.bank() if len(p) == level.sentences
            and all(5 <= len(s) <= 15 for s in p)]
    if not bank:
        return None
    return PR._norm(draw.choice(bank))


def build(level: Grade, draw: random.Random) -> Optional[Machine]:
    original = _source(level, draw)
    if original is None:
        return None
    rows: List[List[Tok]] = [[Tok(si * 100 + i, w) for i, w in enumerate(s)]
                             for si, s in enumerate(original)]
    gone = [set() for _s in original]      # original indices taken out
    damage: List[Tuple[str, int, int]] = []
    extra_id = 9000
    for _t in range(level.errors * 8):
        if len(damage) >= level.errors:
            break
        kind = draw.choice(level.kinds)
        si = draw.randrange(len(original))
        row = rows[si]
        if kind == 'missing':
            spots = [k for k in range(1, len(row) - 1)
                     if row[k].id < 9000 and not PR.name(row[k].text)
                     and row[k - 1].id < 9000 and row[k + 1].id < 9000]
            draw.shuffle(spots)
            for k in spots:
                i = row[k].id % 100
                if i - 1 in gone[si] or i + 1 in gone[si]:
                    continue
                if not _unsaid(row[k - 1].text, row[k + 1].text):
                    continue
                gone[si].add(i)
                del row[k]
                damage.append(('missing', si, i))
                break
        else:
            spots = list(range(1, len(row)))
            draw.shuffle(spots)
            for k in spots:
                if row[k - 1].id >= 9000 or row[k].id != row[k - 1].id + 1:
                    continue                   # only where nothing is gone
                c = common_word(draw)
                if c in (row[k - 1].text, row[k].text):
                    continue
                if _unsaid(row[k - 1].text, c) and _unsaid(c, row[k].text):
                    row.insert(k, Tok(extra_id, c))
                    extra_id += 1
                    damage.append(('extra', si, k))
                    break
    if len(damage) < level.errors:
        return None
    return Machine(level, original, tuple(tuple(r) for r in rows),
                   tuple(damage), draw.getrandbits(30), level.seconds)


def texts(rows) -> List[List[str]]:
    return [[t.text for t in row] for row in rows]


def truth_between(machine: Machine, a: Tok, b: Tok) -> Optional[str]:
    """The word written between *a* and *b*, if one is missing there."""
    if a.id >= 9000 or b.id >= 9000 or a.id // 100 != b.id // 100:
        return None
    si, i, j = a.id // 100, a.id % 100, b.id % 100
    if j == i + 2:
        return machine.original[si][i + 1]
    return None


def offer(machine: Machine, a: Tok, b: Tok) -> Tuple[str, ...]:
    """The four words a caret between *a* and *b* offers: the missing
    word if there is one, else a word drawn as a missing one would be,
    and three others beside it."""
    draw = random.Random(hash((machine.seed, a.id, b.id)))
    truth = truth_between(machine, a, b) or common_word(draw)
    pool: List[str] = []
    fs = [f for f in PR.forms(truth) if f != truth]
    draw.shuffle(fs)
    pool += fs[:1]
    pool += PR._near_words(truth, machine.level.close, draw, 3)
    opts = [truth] + [p for p in pool if p != truth][:3]
    draw.shuffle(opts)
    return tuple(opts)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Machine:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=200)


def carets(row) -> List[float]:
    """Where the caret between word k and k+1 of a line is."""
    cs = centres(row)
    ws, _k = widths(row)
    return [(cs[k] + ws[k] / 2 + cs[k + 1] - ws[k + 1] / 2) / 2
            for k in range(len(row) - 1)]


# --- a run ----------------------------------------------------------------

class Run(H.HandRun):
    def __init__(self, machine: Machine) -> None:
        super().__init__(machine.seconds)
        self.machine, self.level = machine, machine.level
        self.rows: List[List[Tok]] = [list(r) for r in machine.rows]
        self.chosen = None             # ('word', r, i) / ('gap', r, k)
        self.made = 20000              # ids for words the player puts in

    def n(self) -> int:
        return len(self.rows)

    def options(self) -> Tuple[str, ...]:
        c = self.chosen
        if c is None:
            return ()
        if c[0] == 'word':
            return (STRIKE_OUT,)
        row = self.rows[c[1]]
        return offer(self.machine, row[c[2]], row[c[2] + 1])

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        x, y = self.hand.x, self.hand.y
        if abs(y - DONE_AT[1]) <= BUTTON_H / 2:
            if abs(x - DONE_AT[0]) <= BUTTON_W / 2:
                return self.done()
            if abs(x - RESET_AT[0]) <= BUTTON_W / 2:
                return self.reset()
        opts = self.options()
        if opts and abs(y - OPT_Y) <= TILE_H / 2 + 4:
            for k, o in enumerate(opts):
                if abs(x - option_x(k, len(opts))) <= OPT_W / 2:
                    return self._pick(o)
        self.chosen = None
        n = self.n()
        for r, row in enumerate(self.rows):
            ry = row_y(r, n)
            if abs(y - (ry - CARET_DY)) <= CARET_R:
                for k, cx in enumerate(carets(row)):
                    if abs(x - cx) <= CARET_R:
                        self.chosen = ('gap', r, k)
                        self.note(0.05, 520.0, TICK, 0.2)
                        return
            if abs(y - ry) <= TILE_H / 2:
                ws, _k = widths(row)
                for i, cx in enumerate(centres(row)):
                    if abs(x - cx) <= ws[i] / 2:
                        self.chosen = ('word', r, i)
                        self.note(0.05, 700.0, TICK, 0.2)
                        return

    def _pick(self, o: str) -> None:
        c, self.chosen = self.chosen, None
        row = self.rows[c[1]]
        if c[0] == 'word':
            if len(row) > 1:
                del row[c[2]]
            self.note(0.08, 300.0, STRIKE, 0.3)
        else:
            row.insert(c[2] + 1, Tok(self.made, o))
            self.made += 1
            self.note(0.08, 660.0, PICK, 0.3)

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if self.result is not None:
            return
        if port == DONE_KEY:
            self.done()
        elif port == RESET:
            self.reset()

    def reset(self) -> None:
        self.rows = [list(r) for r in self.machine.rows]
        self.chosen = None
        self.note(0.1, 200.0, STRIKE, 0.3)

    def done(self) -> None:
        if self.result is not None:
            return
        if texts(self.rows) == [list(s) for s in self.machine.original]:
            self.note(0.6, 880.0, DONE, 0.5)
            self.result = (True, _('Mended'))
        else:
            self.note(0.5, 90.0, MISS, 0.5)
            self.result = (False, _('Not as it was written'))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.end:
            self.result = (False, _('Out of time'))


act = H.act


# --- the reference player ---------------------------------------------------

def autopilot(run: Run) -> List[int]:
    """Knows the passage: strikes what does not belong, puts back what
    is missing, then hands it in."""
    if run.result is not None:
        return []
    if run.hand.down:
        return [H.RELEASE]
    mc, n = run.machine, run.n()
    for r, row in enumerate(run.rows):
        truth = mc.original[r]
        # the first word that is not as written
        k = next((k for k in range(len(row))
                  if k >= len(truth) or row[k].text != truth[k]), None)
        if k is None:
            if len(row) == len(truth):
                continue
            k = len(row)
        word_ok = k < len(row) and row[k].id < 9000
        # A word there that the original has later: something is
        # missing before it. Anything else does not belong.
        if k < len(row) and not word_ok:
            if run.chosen == ('word', r, k):
                return _click(run, option_x(0, 1), OPT_Y)
            return _click(run, centres(row)[k], row_y(r, n))
        want = truth[k]
        if run.chosen == ('gap', r, k - 1):
            opts = run.options()
            return _click(run, option_x(opts.index(want), len(opts)), OPT_Y)
        return _click(run, carets(row)[k - 1], row_y(r, n) - CARET_DY)
    return _click(run, DONE_AT[0], DONE_AT[1])


def _click(run: Run, x: float, y: float) -> List[int]:
    move = H.toward(run.hand, x, y, tol=3.0)
    if move is not None:
        return [move]
    return [H.PRESS]


def play(machine: Machine, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(machine), pilot, EVENTS, act, dt)
