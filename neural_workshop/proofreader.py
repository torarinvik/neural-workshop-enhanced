# -*- coding: utf-8 -*-
"""The Proofreader: put a damaged passage of English right.

A short passage of real text (Simple English Wikipedia, see
:mod:`neural_workshop.passages`) has been damaged, and the task is to
mend it. The damage comes in six kinds, each a different piece of
knowing English:

==============  ========================================================
``swap``        two neighbouring words change places: *the dog big*
``scramble``    a word's letters are shuffled: *the big gdo*
``order``       the sentences of the passage are out of order
``intruder``    a word is swapped for another word: *the big tea barked*
``agree``       a word takes the wrong form: *the dogs barks*,
                *she have*, *an dog*
``move``        a word is moved far from its place in the sentence
==============  ========================================================

**Mending.** Every word is a tile. Drag a tile along its line to move
it; drag a sentence by its handle (the number on the left) up or down
to move the sentence. Click a word to see the forms it could take and
click one to put it in. Done (Enter) hands the passage in; it passes
when it reads exactly as it was written. Reset (R) puts the damage
back.

**What makes a fix the fix.** Real text has many readings, so the
damage is only dealt where it makes something English does not say:
every pair of words a swap, a move, an intruder or a wrong form puts
side by side is a pair that appears nowhere in the 54,000 sentences
the task reads. A scrambled word is not another word. Nothing about
the screen says which words are damaged, and the sounds are the same
for a right fix and a wrong one: the only feedback is the verdict.

The ladder:

* rungs 1-3: one sentence, one or two words swapped; scrambled words
  from rung 2;
* rungs 4-9: two sentences, and from rung 4 out of order;
* rungs 7+: a word swapped for another word;
* rungs 10+: three sentences, and words in the wrong form;
* rungs 13+: a word moved anywhere in its sentence;
* rungs 16+: longer passages, letters shuffled from end to end;
* rungs 19+: no count of the mistakes on the screen, and intruders as
  common as the words they replace;
* above that the mistakes keep coming, one more every few rungs, until
  a third of the words are wrong, and then the clock shortens without
  end.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import hand as H
from . import passages as PS
from . import sentences as S
from .i18n import _

DONE_KEY = H.KEYS              # 14: hand the passage in
RESET = H.KEYS + 1             # 15: put the damage back
PORTS = H.KEYS + 2
EVENTS = tuple(range(PORTS))
TICK, LIFT, DROP, PICK, DONE, MISS = range(6)
PATCHES = ('wood', 'wood', 'wood', 'bell', 'bell', 'growl')

KINDS = ('swap', 'scramble', 'order', 'intruder', 'agree', 'move')
FROM = {'swap': 1, 'scramble': 2, 'order': 4, 'intruder': 7,
        'agree': 10, 'move': 13}

# Where things are on the 1000 by 640 screen (y up).
ROW_TOP = 540.0
TEXT_X = (96.0, 980.0)
HANDLE_X = 54.0
CHAR, PAD, GAP, TILE_H = 12.0, 14.0, 8.0, 34.0   # CHAR: a 15 pt letter
OPT_Y = 112.0
OPT_W = 150.0
DONE_AT = (900.0, 44.0)
RESET_AT = (760.0, 44.0)
BUTTON_W, BUTTON_H = 120.0, 40.0
CLICK = 8.0                    # moved less than this: a click, not a drag


class Grade(NamedTuple):
    rung: int
    sentences: int
    kinds: Tuple[str, ...]
    errors: int                # word-level mistakes
    hint: bool                 # the count of mistakes shown
    whole: bool                # scrambles move every letter
    close: bool                # intruders as common as what they replace
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    n = 1 if r < 4 else 2 if r < 10 else 3 if r < 16 else \
        min(6, 4 + (r - 16) // 6)
    kinds = tuple(k for k in KINDS if r >= FROM[k] and
                  (k != 'order' or n > 1))
    errors = 1 + (r - 1) // 3 if r <= 30 else 10 + (r - 30) // 4
    words = 9 * n
    errors = min(errors, max(1, words // 3))
    seconds = 45.0 + 18.0 * errors + 5.0 * n
    over = max(0, r - 25)
    if over and errors >= words // 3:
        seconds *= max(0.25, 1.0 - 0.02 * over)
    return Grade(r, n, kinds, errors, r < 19, r >= 16, r >= 19,
                 round(seconds, 1))


# --- what English allows ---------------------------------------------------

def _lower(w: str) -> str:
    return w.lower()


@functools.lru_cache(maxsize=1)
def pairs() -> frozenset:
    """Every pair of neighbouring words the task has read, lowercased."""
    seen = set()
    for sent in S.bank():
        ws = sent.words
        seen.update(hash((a, b)) for a, b in zip(ws, ws[1:]))
    for passage in PS.bank():
        for ws in passage:
            low = [w.lower() for w in ws]
            seen.update(hash((a, b)) for a, b in zip(low, low[1:]))
    return frozenset(seen)


def said(a: str, b: str) -> bool:
    return hash((a.lower(), b.lower())) in pairs()


#: Small closed sets whose members are easily mixed up.
CLOSED = (('a', 'an', 'the'), ('is', 'are', 'was', 'were', 'be', 'been'),
          ('has', 'have', 'had'), ('do', 'does', 'did'),
          ('this', 'these', 'that', 'those'), ('much', 'many'),
          ('it', 'its'), ('there', 'their'), ('than', 'then'),
          ('to', 'too'))


@functools.lru_cache(maxsize=1)
def families() -> Dict[str, Tuple[str, ...]]:
    """Each word and the other forms of it: walk, walks, walked, ..."""
    known = set(S.vocabulary(S.TOP_RANK))
    out: Dict[str, set] = {}
    for w in S.vocabulary(25000):
        if len(w) < 3:
            continue
        forms = {w}
        for f in (w + 's', w + 'es', w + 'ed', w + 'd', w + 'ing',
                  w[:-1] + 'ing' if w.endswith('e') else '',
                  w[:-1] + 'ies' if w.endswith('y') else '',
                  w[:-1] + 'ied' if w.endswith('y') else ''):
            if f and f in known:
                forms.add(f)
        if len(forms) > 1:
            for f in forms:
                out.setdefault(f, set()).update(forms)
    for group in CLOSED:
        for f in group:
            out.setdefault(f, set()).update(group)
    return {w: tuple(sorted(fs)) for w, fs in out.items()}


def forms(w: str) -> Tuple[str, ...]:
    return families().get(w.lower(), ())


@functools.lru_cache(maxsize=1)
def _ranked() -> Tuple[str, ...]:
    return S.vocabulary(S.TOP_RANK)


@functools.lru_cache(maxsize=1)
def _rank_of() -> Dict[str, int]:
    return {w: k for k, w in enumerate(_ranked())}


def name(w: str) -> bool:
    """A capitalised word: a name, never damaged."""
    return w[:1].isupper()


# --- a passage, damaged --------------------------------------------------

class Tok(NamedTuple):
    id: int
    text: str


class Machine(NamedTuple):
    level: Grade
    original: Tuple[Tuple[str, ...], ...]      # as written
    rows: Tuple[Tuple[Tok, ...], ...]          # as dealt, in dealt order
    origin: Dict[int, Tuple[int, int]]         # token id -> (sentence, i)
    row_of: Tuple[int, ...]                    # dealt row -> sentence
    options: Dict[int, Tuple[str, ...]]        # token id -> forms to pick
    damage: Tuple[Tuple[str, int, int], ...]   # (kind, sentence, i)
    seconds: float


def _norm(passage) -> Tuple[Tuple[str, ...], ...]:
    """First words lowercased unless they are names."""
    out = []
    known = _rank_of()
    for ws in passage:
        ws = list(ws)
        if ws and (len(ws[0]) == 1 or ws[0][1:].islower()) and \
                ws[0].lower() in known:
            ws[0] = ws[0].lower()
        out.append(tuple(ws))
    return tuple(out)


def _fresh(sent: Sequence[str], i: int, w: str) -> bool:
    """Whether word *w* at *i* makes a pair with each neighbour that the
    corpus never has."""
    left = sent[i - 1] if i > 0 else None
    right = sent[i + 1] if i + 1 < len(sent) else None
    return all(n is None or not said(*p) for n, p in (
        (left, (left or '', w)), (right, (w, right or ''))))


def _scramble(w: str, whole: bool, draw: random.Random) -> Optional[str]:
    known = _rank_of()
    for _t in range(20):
        if whole:
            cs = list(w)
            draw.shuffle(cs)
            s = ''.join(cs)
        else:
            mid = list(w[1:-1])
            draw.shuffle(mid)
            s = w[0] + ''.join(mid) + w[-1]
        if s != w and s not in known:
            return s
    return None


def _near_words(w: str, close: bool, draw: random.Random, n: int) -> List[str]:
    """Words of about *w*'s commonness, not forms of it."""
    ranked, rank = _ranked(), _rank_of()
    at = rank.get(w.lower(), len(ranked) // 2)
    span = 300 if close else 6000
    lo, hi = max(0, at - span), min(len(ranked) - 1, at + span)
    out: List[str] = []
    own = set(forms(w)) | {w.lower()}
    for _t in range(200):
        c = ranked[draw.randint(lo, hi)]
        if c not in own and c not in out and c.isalpha() and len(c) > 1:
            out.append(c)
            if len(out) >= n:
                break
    return out


def _damage_sentence(sent: List[str], kind: str, level: Grade,
                     draw: random.Random, used: set
                     ) -> Optional[Tuple[List[str], Tuple[str, int]]]:
    """*sent* with one more mistake of *kind*, and where it went."""
    n = len(sent)
    spots = [i for i in range(n) if i not in used and not name(sent[i])]
    draw.shuffle(spots)
    for i in spots:
        w = sent[i]
        if kind == 'swap':
            j = i + 1
            if j >= n or j in used or name(sent[j]) or sent[i] == sent[j]:
                continue
            out = sent[:]
            out[i], out[j] = out[j], out[i]
            if said(out[i], out[j]):
                continue
            used.update((i, j))
            return out, (kind, i)
        if kind == 'scramble':
            if len(w) < 4:
                continue
            s = _scramble(w, level.whole, draw)
            if s is None:
                continue
            out = sent[:]
            out[i] = s
            used.add(i)
            return out, (kind, i)
        if kind == 'intruder':
            if len(w) < 3:
                continue
            for c in _near_words(w, level.close, draw, 12):
                if _fresh(sent, i, c):
                    out = sent[:]
                    out[i] = c
                    used.add(i)
                    return out, (kind, i)
        if kind == 'agree':
            fs = [f for f in forms(w) if f != w]
            draw.shuffle(fs)
            for f in fs:
                if _fresh(sent, i, f):
                    out = sent[:]
                    out[i] = f
                    used.add(i)
                    return out, (kind, i)
        if kind == 'move':
            for j in draw.sample(range(n), n):
                if abs(j - i) < 2 or j in used:
                    continue
                out = sent[:]
                out.insert(j, out.pop(i))
                if not _fresh(out, j, w):
                    continue
                used.update(range(min(i, j), max(i, j) + 1))
                return out, (kind, i)
    return None


def _options(text: str, truth: str, kind: Optional[str], close: bool,
             draw: random.Random) -> Tuple[str, ...]:
    """The forms offered for a word: always the right one, never only
    it, and drawn the same way whether the word is damaged or not."""
    pool: List[str] = []
    fs = [f for f in forms(truth) if f != truth]
    draw.shuffle(fs)
    pool += fs[:2]
    pool += _near_words(truth, close, draw, 4 - len(pool))
    opts = [truth] + [p for p in pool if p != text and p != truth][:3]
    draw.shuffle(opts)
    return tuple(opts[:4])


def build(level: Grade, draw: random.Random) -> Optional[Machine]:
    if level.sentences == 1:
        pool = S.choose((6, 12), S.TOP_RANK)
        if not pool:
            return None
        original = _norm((draw.choice(pool).words,))
    else:
        bank = [p for p in PS.bank() if len(p) == level.sentences
                and all(5 <= len(s) <= 15 for s in p)]
        if not bank:
            bank = [p[:level.sentences] for p in PS.bank()
                    if len(p) >= level.sentences]
        if not bank:
            return None
        original = _norm(draw.choice(bank))
    words = sum(len(s) for s in original)
    kinds = [k for k in level.kinds if k != 'order']
    damaged = [list(s) for s in original]
    used = [set() for _s in original]
    damage: List[Tuple[str, int, int]] = []
    # Each token keeps its identity through the damage.
    ids = [[(si * 100 + i) for i in range(len(s))]
           for si, s in enumerate(original)]
    errors = min(level.errors, max(1, words // 3))
    for _e in range(errors * 4):
        if len(damage) >= errors:
            break
        kind = draw.choice(kinds)
        si = draw.randrange(len(original))
        got = _damage_sentence(damaged[si], kind, level, draw, used[si])
        if got is None:
            continue
        before = damaged[si]
        damaged[si], (k, i) = got
        if kind in ('swap', 'move'):
            # follow the tokens: the same reordering applied to ids
            order = _follow(before, damaged[si])
            if order is None:
                return None
            ids[si] = [ids[si][k_] for k_ in order]
        damage.append((kind, si, i))
    if len(damage) < errors:
        return None
    row_of = list(range(len(original)))
    if 'order' in level.kinds:
        while row_of == sorted(row_of):
            draw.shuffle(row_of)
        damage.append(('order', -1, -1))
    rows, origin, options = [], {}, {}
    for si in row_of:
        row = []
        for k, (tid, text) in enumerate(zip(ids[si], damaged[si])):
            row.append(Tok(tid, text))
        rows.append(tuple(row))
    for si, s in enumerate(original):
        for i, w in enumerate(s):
            origin[si * 100 + i] = (si, i)
    hurt = {(si, i): kind for kind, si, i in damage if si >= 0}
    for row in rows:
        for t in row:
            si, i = origin[t.id]
            truth = original[si][i]
            if name(truth):
                continue
            options[t.id] = _options(t.text, truth, hurt.get((si, i)),
                                     level.close, draw)
    m = Machine(level, original, tuple(rows), origin, tuple(row_of),
                options, tuple(damage), level.seconds)
    if texts(m.rows) == [list(s) for s in original]:
        return None
    return m


def _follow(before: List[str], after: List[str]) -> Optional[List[int]]:
    """Which index of *before* each word of *after* came from (a move
    or a swap: same words, new order)."""
    left = list(range(len(before)))
    out = []
    for w in after:
        k = next((k for k in left if before[k] == w), None)
        if k is None:
            return None
        left.remove(k)
        out.append(k)
    return out


def texts(rows) -> List[List[str]]:
    return [[t.text for t in row] for row in rows]


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Machine:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=200)


# --- where things are ---------------------------------------------------

def row_y(k: int, n: int) -> float:
    step = min(78.0, 400.0 / max(1, n - 1)) if n > 1 else 0.0
    return ROW_TOP - k * step


def widths(row) -> Tuple[List[float], float]:
    """Each tile's width in a line, and the scale the line is drawn at:
    wide enough for the word as shown, the last one's full stop too."""
    ws = [(len(t.text) + (i == len(row) - 1)) * CHAR + PAD
          for i, t in enumerate(row)]
    total = sum(ws) + GAP * max(0, len(ws) - 1)
    room = TEXT_X[1] - TEXT_X[0]
    k = min(1.0, room / total) if total else 1.0
    return [w * k for w in ws], k


def centres(row) -> List[float]:
    ws, k = widths(row)
    out, x = [], TEXT_X[0]
    for w in ws:
        out.append(x + w / 2)
        x += w + GAP * k
    return out


def option_x(k: int, n: int) -> float:
    return 500.0 + (k - (n - 1) / 2.0) * (OPT_W + 14.0)


# --- a run ----------------------------------------------------------------

class Run(H.HandRun):
    def __init__(self, machine: Machine) -> None:
        super().__init__(machine.seconds)
        self.machine, self.level = machine, machine.level
        self.rows: List[List[Tok]] = [list(r) for r in machine.rows]
        self.selected: Optional[int] = None    # a token id
        self.carry = None                      # ('row', k) / ('tok', r, i)
        self.start = (0.0, 0.0)
        self.moves = 0

    def n(self) -> int:
        return len(self.rows)

    def find(self, tid: int) -> Optional[Tuple[int, int]]:
        for r, row in enumerate(self.rows):
            for i, t in enumerate(row):
                if t.id == tid:
                    return r, i
        return None

    def row_at(self, y: float) -> Optional[int]:
        for r in range(self.n()):
            if abs(y - row_y(r, self.n())) <= TILE_H / 2 + 6:
                return r
        return None

    def tok_at(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        r = self.row_at(y)
        if r is None:
            return None
        ws, _k = widths(self.rows[r])
        for i, c in enumerate(centres(self.rows[r])):
            if abs(x - c) <= ws[i] / 2 + GAP / 2:
                return r, i
        return None

    def options(self) -> Tuple[str, ...]:
        if self.selected is None:
            return ()
        return self.machine.options.get(self.selected, ())

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        x, y = self.hand.x, self.hand.y
        self.start = (x, y)
        if abs(y - DONE_AT[1]) <= BUTTON_H / 2:
            if abs(x - DONE_AT[0]) <= BUTTON_W / 2:
                return self.done()
            if abs(x - RESET_AT[0]) <= BUTTON_W / 2:
                return self.reset()
        opts = self.options()
        if opts and abs(y - OPT_Y) <= TILE_H / 2 + 4:
            for k, o in enumerate(opts):
                if abs(x - option_x(k, len(opts))) <= OPT_W / 2:
                    at = self.find(self.selected)
                    if at is not None:
                        r, i = at
                        self.rows[r][i] = Tok(self.selected, o)
                        self.moves += 1
                    self.selected = None
                    self.note(0.08, 660.0, PICK, 0.3)
                    return
        self.selected = None
        r = self.row_at(y)
        if r is not None and abs(x - HANDLE_X) <= 30:
            self.carry = ('row', r)
            self.note(0.05, 300.0, LIFT, 0.3)
            return
        at = self.tok_at(x, y)
        if at is not None:
            self.carry = ('tok',) + at
            self.note(0.05, 500.0, LIFT, 0.25)

    def release(self) -> None:
        if not self.hand.down:
            return
        self.hand.down = False
        carry, self.carry = self.carry, None
        if carry is None or self.result is not None:
            return
        x, y = self.hand.x, self.hand.y
        moved = abs(x - self.start[0]) + abs(y - self.start[1])
        if carry[0] == 'row':
            if moved < CLICK:
                return
            n = self.n()
            to = min(range(n), key=lambda k: abs(y - row_y(k, n)))
            if to != carry[1]:
                self.rows.insert(to, self.rows.pop(carry[1]))
                self.moves += 1
            self.note(0.06, 260.0, DROP, 0.35)
            return
        _t, r, i = carry
        if moved < CLICK:                      # a click: the forms
            tid = self.rows[r][i].id
            if tid in self.machine.options:
                self.selected = tid
            self.note(0.05, 700.0, TICK, 0.2)
            return
        if self.row_at(y) != r:
            return                             # only along its own line
        cs = centres(self.rows[r])
        to = sum(1 for k, c in enumerate(cs) if k != i and c < x)
        tok = self.rows[r].pop(i)
        self.rows[r].insert(to, tok)
        self.moves += 1
        self.note(0.06, 420.0, DROP, 0.3, pan=(x - 500) / 500)

    def key(self, port: int) -> None:
        if self.result is not None:
            return
        if port == DONE_KEY:
            self.done()
        elif port == RESET:
            self.reset()

    def reset(self) -> None:
        self.rows = [list(r) for r in self.machine.rows]
        self.selected = None
        self.note(0.1, 200.0, DROP, 0.3)

    def mistakes(self) -> int:
        """How many words are not as written (sentences out of order
        count each of their words)."""
        want = self.machine.original
        got = texts(self.rows)
        bad = 0
        for k, row in enumerate(got):
            truth = want[k] if k < len(want) else ()
            bad += sum(1 for a, b in zip(row, truth) if a != b)
            bad += abs(len(row) - len(truth))
        return bad

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
    """Knows the passage: puts the sentences in order, the words right,
    then the words in order, then hands it in."""
    if run.result is not None:
        return []
    hand, mc = run.hand, run.machine
    if hand.down and run.carry is None:
        return [H.RELEASE]
    n = run.n()
    if run.carry is not None:                  # finish the drag under way
        goal = run._goal
        move = H.toward(hand, goal[0], goal[1], tol=3.0)
        return [move] if move is not None else [H.RELEASE]
    # 1. the sentences in order
    for p in range(n):
        sp = mc.origin[run.rows[p][0].id][0] if run.rows[p] else p
        if sp != p:
            src = next(r for r in range(n)
                       if mc.origin[run.rows[r][0].id][0] == p)
            return _drag(run, (HANDLE_X, row_y(src, n)),
                         (HANDLE_X, row_y(p, n)))
    # 2. every word its right form
    for r, row in enumerate(run.rows):
        for i, t in enumerate(row):
            si, wi = mc.origin[t.id]
            truth = mc.original[si][wi]
            if t.text != truth:
                if run.selected == t.id:
                    opts = run.options()
                    k = opts.index(truth)
                    return _click(run, option_x(k, len(opts)), OPT_Y)
                return _click(run, centres(row)[i], row_y(r, n))
    # 3. the words in order
    for r, row in enumerate(run.rows):
        for i in range(len(row)):
            si, wi = mc.origin[row[i].id]
            if wi != i:
                j = next(j for j, t in enumerate(row)
                         if mc.origin[t.id][1] == i)
                cs = centres(row)
                others = [c for k, c in enumerate(cs) if k != j]
                if i == 0:
                    x = others[0] - 20.0
                elif i >= len(others):
                    x = others[-1] + 20.0
                else:
                    x = (others[i - 1] + others[i]) / 2
                return _drag(run, (cs[j], row_y(r, n)), (x, row_y(r, n)))
    return _click(run, DONE_AT[0], DONE_AT[1])


def _click(run: Run, x: float, y: float) -> List[int]:
    move = H.toward(run.hand, x, y, tol=3.0)
    if move is not None:
        return [move]
    if run.hand.down:
        return [H.RELEASE]
    run._goal = (x, y)                         # let go where it was pressed
    return [H.PRESS]


def _drag(run: Run, a, b) -> List[int]:
    move = H.toward(run.hand, a[0], a[1], tol=3.0)
    if move is not None:
        return [move]
    run._goal = b
    return [H.PRESS]


def play(machine: Machine, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(machine), pilot, EVENTS, act, dt)
