# -*- coding: utf-8 -*-
"""Morning Round: deliver the papers, by rules that change on the way.

A bicycle rides up a street of houses, left and right. Each house shows
what it is: the colour of its door, its number, a pointed or a flat
roof, a dog in the yard or not, the mailbox flag up or down, the lights
on or off, a cat on the step. A paper thrown to the left or the right
flies across the lawn and lands where the bicycle has got to by then;
it is delivered to the house it lands at.

Which houses take a paper is a **rule**, written in the rulebook in the
corner. Getting the riding right is the easy part. The street is cut
into blocks by crossroads, and the rule may change at a crossroads:

* rung 1: subscribers have a star sign in the window;
* rungs 2-4: one rule for the whole street, written in the rulebook:
  one feature ("blue door"), then two ("dog and not flag up");
* rungs 5-6: two rules, A and B; a sign at each crossroads says which
  is in force from there;
* rungs 7+: no signs. The rulebook lists the rules and says which one
  the round starts with; at any crossroads the rule may silently change
  to another one in the list (as often as not it does). What the houses
  say is all there is to go by: a subscriber thanks you for a paper
  (a chime), a house that wanted none shouts, and a subscriber passed
  without one complains (a horn). A house passed in silence wanted
  none. The new rule has to be worked out from that, on the move;
* rungs 9+: three rules, and house numbers (even, divisible by three)
  and the side of the street in the rules;
* rungs 10+: rules that look elsewhere: at the house across the
  street, every second house of a kind, a door the colour of the last
  one on its side;
* rungs 11+: the rulebook is shown at the depot and then put away;
* rungs 12+: the block's landmark (a church on the corner) in the
  rules, four blocks;
* above that the rules grow without end: more of them, more parts to
  each, more blocks, a faster bicycle and less time at the depot.

A round passes when the street is done with no more mistakes (a paper
to the wrong house, a subscriber missed) than the round allows -- one
or two, and two more for every crossroads where the rule might change
unseen -- and without three falls. Things in the road (cones, bins,
parked cars, from rung 8 cyclists coming the other way) knock the rider
off the bicycle.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import hand as H
from .i18n import _

LEFT, RIGHT, FASTER, SLOWER, THROW_L, THROW_R = range(6)
PORTS = 6
EVENTS = (THROW_L, THROW_R)
CHIME, SHOUT, HORN, THUD, CRASH, WHOOSH, BELL = range(7)
PATCHES = ('bell', 'growl', 'wood', 'wood', 'growl', 'wood', 'bell')

# The street on the 1000 by 640 screen; distance along the street is d.
RIDER_Y = 140.0                # where the bicycle is drawn
AHEAD = 500.0                  # how far up the street is in view
LEFT_FRONT, RIGHT_FRONT = 470.0, 730.0     # where the lawns meet the walk
LEFT_HOUSE, RIGHT_HOUSE = (330.0, 470.0), (730.0, 870.0)
ROAD = (490.0, 710.0)
LANE = (508.0, 692.0)          # where the bicycle can be
SPACING = 150.0                # house to house on one side
HOUSE_LEN = 104.0              # a house's frontage
STAGGER = SPACING / 2          # the right side is half a house on
CROSSING = 170.0               # a crossroads between blocks
FIRST = 330.0                  # the first house after the depot
PAPER_V = 640.0                # sideways speed of a thrown paper
COOLDOWN = 0.15
RIDER_R = 13.0
STEER_V = 230.0
ACCEL = 160.0
FALL = 1.4                     # seconds on the ground

DOORS = ('red', 'blue', 'green', 'yellow')
LANDMARKS = ('church', 'shop', 'park', 'school')
BASIC = ('blue', 'red', 'green', 'yellow', 'pointed', 'dog', 'flag',
         'lights', 'cat')
NUMBERS = ('left', 'even', 'three')
WORDS = {'sign': 'star in the window', 'blue': 'blue door',
         'red': 'red door', 'green': 'green door', 'yellow': 'yellow door',
         'pointed': 'pointed roof', 'dog': 'dog', 'flag': 'flag up',
         'lights': 'lights on', 'cat': 'cat', 'left': 'left side',
         'even': 'even number', 'three': 'number divisible by 3',
         'church': 'church block'}


class Grade(NamedTuple):
    rung: int
    mode: str                  # 'marked', 'told', 'sign' or 'hidden'
    deck: int                  # rules in the rulebook
    atoms: int                 # parts to each rule
    pool: Tuple[str, ...]      # the features rules may use
    state: bool                # rules that look at other houses
    blocks: int
    houses: int                # houses a side, each block
    speed: float               # how fast the bicycle starts, px/s
    clutter: float             # things in the road, per house
    movers: bool               # cyclists coming the other way
    memorise: bool             # the rulebook is put away after the depot
    brief: float               # seconds at the depot
    slack: int                 # mistakes a round allows


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    mode = 'marked' if r == 1 else 'told' if r < 5 else \
        'sign' if r < 7 else 'hidden'
    deck = 1 if r < 5 else 2 if r < 9 else 3 if r < 13 else \
        min(6, 3 + (r - 12) // 4)
    atoms = 1 if r < 4 else 2 if r < 13 else min(9, 2 + (r - 11) // 4)
    pool = BASIC + (NUMBERS if r >= 9 else ()) + \
        (('church',) if r >= 12 else ())
    blocks = 1 if r < 5 else 2 if r < 6 else 3 if r < 12 else \
        min(8, 4 + (r - 12) // 4)
    houses = 6 if r < 13 else 5
    speed = (100.0, 115.0, 125.0, 135.0)[r - 1] if r < 5 else \
        min(520.0, 140.0 + 9.0 * (r - 5))
    clutter = 0.0 if r < 3 else min(0.9, 0.15 + 0.04 * (r - 3))
    memorise = r >= 11
    brief = 2.0 if not memorise else max(3.0, 14.0 - 0.25 * (r - 11))
    hidden_turns = blocks - 1 if mode == 'hidden' else 0
    slack = (2 if r < 3 else 1) + 2 * hidden_turns
    return Grade(r, mode, deck, atoms, pool, r >= 10, blocks, houses,
                 speed, clutter, r >= 8, memorise, brief, slack)


class House(NamedTuple):
    i: int                     # in street order
    side: int                  # -1 left, +1 right
    k: int                     # index along its side
    d: float
    block: int
    door: str
    number: int
    pointed: bool
    dog: bool
    flag: bool
    lights: bool
    cat: bool
    sign: bool


class Thing(NamedTuple):
    d: float                   # where it is at t = 0 (moving ones move down)
    x: float
    r: float
    kind: str                  # 'cone', 'bin', 'car', 'cyclist'
    v: float                   # speed toward the rider (0 for still)


class Street(NamedTuple):
    level: Grade
    houses: Tuple[House, ...]
    blocks: Tuple[Tuple[float, float], ...]    # (start d, end d)
    landmarks: Tuple[str, ...]
    deck: Tuple[object, ...]                   # the rules, A, B, ...
    active: Tuple[int, ...]                    # rule in force, each block
    want: Tuple[bool, ...]                     # each house: a paper?
    things: Tuple[Thing, ...]
    papers: int
    length: float                              # where the street ends
    seconds: float


# --- rules ----------------------------------------------------------------

def _atom_vector(name: str, houses, landmarks) -> List[bool]:
    out = []
    for h in houses:
        if name in DOORS:
            v = h.door == name
        elif name == 'church':
            v = landmarks[h.block] == 'church'
        elif name == 'left':
            v = h.side < 0
        elif name == 'even':
            v = h.number % 2 == 0
        elif name == 'three':
            v = h.number % 3 == 0
        else:
            v = bool(getattr(h, name))
        out.append(v)
    return out


_MEMO: Dict[object, List[bool]] = {}
_OWNER: list = [None]


def truth(rule, houses: Sequence[House], landmarks) -> List[bool]:
    """Which houses *rule* gives a paper to (remembered for the street
    last asked about)."""
    if _OWNER[0] is not houses:
        _OWNER[0] = houses
        _MEMO.clear()
    got = _MEMO.get(rule)
    if got is None:
        got = _MEMO[rule] = _truth(rule, houses, landmarks)
    return got


def _truth(rule, houses: Sequence[House], landmarks) -> List[bool]:
    op = rule[0]
    if op == 'atom':
        return _atom_vector(rule[1], houses, landmarks)
    if op == 'not':
        return [not v for v in truth(rule[1], houses, landmarks)]
    if op in ('and', 'or'):
        a = truth(rule[1], houses, landmarks)
        b = truth(rule[2], houses, landmarks)
        return [(x and y) if op == 'and' else (x or y)
                for x, y in zip(a, b)]
    if op == 'opp':
        v = truth(rule[1], houses, landmarks)
        at = {(h.side, h.k): h.i for h in houses}
        return [v[at[(-h.side, h.k)]] if (-h.side, h.k) in at else False
                for h in houses]
    if op == 'alt':
        v = truth(rule[1], houses, landmarks)
        seen: Dict[int, int] = {}
        out = []
        for h in houses:
            if v[h.i]:
                n = seen.get(h.block, 0)
                seen[h.block] = n + 1
                out.append(n % 2 == 0)
            else:
                out.append(False)
        return out
    if op == 'same':
        last: Dict[int, str] = {}
        out = []
        for h in houses:
            out.append(last.get(h.side) == h.door)
            last[h.side] = h.door
        return out
    raise ValueError(op)


def say(rule, top: bool = True) -> str:
    """The rule in the rulebook's words."""
    op = rule[0]
    if op == 'atom':
        return WORDS[rule[1]]
    if op == 'not':
        inner = rule[1]
        if inner[0] == 'atom' and inner[1] in ('dog', 'cat'):
            return 'no ' + WORDS[inner[1]]
        return 'not ' + say(inner, False)
    if op in ('and', 'or'):
        text = '%s %s %s' % (say(rule[1], False), op, say(rule[2], False))
        return text if top else '(' + text + ')'
    if op == 'opp':
        return 'across from: ' + say(rule[1], False)
    if op == 'alt':
        return 'every 2nd: ' + say(rule[1], False)
    if op == 'same':
        return 'door as the last on its side'
    raise ValueError(op)


def size(rule) -> int:
    op = rule[0]
    if op in ('atom', 'same'):
        return 1
    if op in ('not', 'opp', 'alt'):
        return size(rule[1])
    return size(rule[1]) + size(rule[2])


def meaningful(rule, houses, landmarks) -> bool:
    """Whether every part of *rule* changes what it says somewhere on
    this street: no "blue door or blue door", no part that never
    matters."""
    op = rule[0]
    if op in ('atom', 'same'):
        v = truth(rule, houses, landmarks)
        return any(v) and not all(v)
    if op in ('not', 'opp', 'alt'):
        if op == 'not' and rule[1][0] == 'not':
            return False
        return meaningful(rule[1], houses, landmarks) and \
            truth(rule, houses, landmarks) != \
            truth(rule[1], houses, landmarks)
    whole = truth(rule, houses, landmarks)
    return all(meaningful(c, houses, landmarks) and
               truth(c, houses, landmarks) != whole for c in rule[1:])


def make_rule(n: int, level: Grade, draw: random.Random):
    """A rule with *n* parts from the rung's features."""
    if n <= 1:
        if level.state and draw.random() < 0.12:
            node = ('same',)
        else:
            node = ('atom', draw.choice(level.pool))
            if level.rung >= 3 and draw.random() < 0.3:
                node = ('not', node)
    else:
        a = draw.randint(1, n - 1)
        node = (draw.choice(('and', 'or')), make_rule(a, level, draw),
                make_rule(n - a, level, draw))
    if level.state and node[0] != 'same' and draw.random() < 0.2:
        node = (draw.choice(('opp', 'alt')), node)
    return node


# --- the street -------------------------------------------------------------

def _houses(level: Grade, draw: random.Random):
    houses, blocks = [], []
    d = FIRST
    start_l = draw.randrange(1, 40) * 2 - 1
    start_r = start_l + 1 + 2 * draw.randrange(0, 3)
    kl = kr = 0
    for b in range(level.blocks):
        b0 = d - SPACING / 2
        for j in range(level.houses):
            for side, off in ((-1, 0.0), (1, STAGGER)):
                k = kl if side < 0 else kr
                number = (start_l + 2 * k) if side < 0 else (start_r + 2 * k)
                houses.append(dict(side=side, k=k, d=d + j * SPACING + off,
                                   block=b, door=draw.choice(DOORS),
                                   number=number,
                                   pointed=draw.random() < 0.5,
                                   dog=draw.random() < 0.4,
                                   flag=draw.random() < 0.5,
                                   lights=draw.random() < 0.5,
                                   cat=draw.random() < 0.4))
                if side < 0:
                    kl += 1
                else:
                    kr += 1
        d += level.houses * SPACING
        blocks.append((b0, d - SPACING / 2 + STAGGER))
        d += CROSSING
    houses.sort(key=lambda h: h['d'])
    return [House(i=i, sign=False, **h) for i, h in enumerate(houses)], \
        blocks, d - CROSSING + 200.0


def _things(level: Grade, length: float, draw: random.Random):
    out = []
    if level.clutter <= 0:
        return out
    n = int(level.clutter * length / SPACING)
    d = FIRST + 120.0
    for _k in range(n):
        d += draw.uniform(170.0, 320.0)
        if d > length - 150:
            break
        if level.movers and draw.random() < 0.3:
            out.append(Thing(d + level.speed * 2.5, draw.uniform(*LANE), 14.0,
                             'cyclist', draw.uniform(40.0, 90.0)))
            continue
        kind = draw.choice(('cone', 'bin', 'car'))
        if kind == 'car':
            x = draw.choice((ROAD[0] + 26.0, ROAD[1] - 26.0))
            out.append(Thing(d, x, 26.0, 'car', 0.0))
        else:
            out.append(Thing(d, draw.uniform(LANE[0] + 20, LANE[1] - 20),
                             12.0, kind, 0.0))
    return out


def build(level: Grade, draw: random.Random) -> Optional[Street]:
    houses, blocks, length = _houses(level, draw)
    landmarks = tuple(draw.choice(LANDMARKS) for _b in blocks)
    if level.mode == 'marked':
        houses = [h._replace(sign=draw.random() < 0.5) for h in houses]
        deck = [('atom', 'sign')]
    else:
        deck, seen = [], []
        for _t in range(60):
            if len(deck) >= level.deck:
                break
            n = draw.randint(max(1, level.atoms - 1), level.atoms)
            rule = make_rule(n, level, draw)
            v = truth(rule, houses, landmarks)
            if not 0.25 <= sum(v) / len(v) <= 0.7 or v in seen or \
                    not meaningful(rule, houses, landmarks):
                continue
            deck.append(rule)
            seen.append(v)
        if len(deck) < level.deck:
            return None
    vectors = [truth(r, houses, landmarks) for r in deck]
    # Which rule is in force in each block.
    active = [0]
    for _b in range(1, level.blocks):
        if level.deck > 1 and (level.mode == 'sign' or draw.random() < 0.5):
            active.append(draw.choice([k for k in range(level.deck)
                                       if k != active[-1]]))
        else:
            active.append(active[-1])
    if level.mode in ('sign', 'hidden') and level.blocks > 1 and \
            len(set(active)) < 2:
        active[-1] = (active[0] + 1) % level.deck
    want = [vectors[active[h.block]][h.i] for h in houses]
    n = len(houses)
    slack = level.slack
    # Every block has papers to give and houses to pass, and every two
    # rules tell themselves apart inside every block.
    for b in range(level.blocks):
        here = [h.i for h in houses if h.block == b]
        got = sum(want[i] for i in here)
        if got < 2 or got > len(here) - 2:
            return None
        for a in range(len(deck)):
            for c in range(a + 1, len(deck)):
                if sum(vectors[a][i] != vectors[c][i] for i in here) < 2:
                    return None
    # The shortcuts lose: every house, none, the first rule throughout.
    subs = sum(want)
    if n - subs <= slack + 1 or subs <= slack + 1:
        return None
    if level.mode in ('sign', 'hidden'):
        fixed = sum(vectors[active[0]][i] != want[i] for i in range(n))
        if fixed <= slack + 1:
            return None
    things = _things(level, length, draw)
    papers = subs + max(3, n // 5)
    seconds = level.brief + length / (0.55 * level.speed) + 10.0
    return Street(level, tuple(houses), tuple(blocks), landmarks,
                  tuple(deck), tuple(active), tuple(want), tuple(things),
                  papers, length, round(seconds, 1))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Street:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=300)


# --- a ride ---------------------------------------------------------------------

class Paper(NamedTuple):
    x: float
    d: float
    side: int
    v: float                   # forward speed it carries


class Run(H.HandRun):
    def __init__(self, street: Street) -> None:
        super().__init__(street.seconds)
        self.street, self.level = street, street.level
        self.s = 0.0                           # how far up the street
        self.x = (LANE[0] + LANE[1]) / 2
        self.v = street.level.speed
        self.papers = street.papers
        self.flying: List[Paper] = []
        self.got: Dict[int, str] = {}          # house -> 'ok', 'wrong', 'missed'
        self.known: Dict[int, bool] = {}       # house -> wanted a paper
        self.passed = 0                        # houses passed, in order
        self.falls = 0
        self.down_until = -1.0
        self.hit: set = set()                  # things already fallen over
        self.last_throw = -9.0
        self.mistakes = 0

    # what the screen and the player can see
    def riding(self) -> bool:
        return self.t >= self.level.brief

    def rulebook_open(self) -> bool:
        return not self.level.memorise or not self.riding()

    def block_at(self, d: float) -> int:
        for b, (lo, hi) in enumerate(self.street.blocks):
            if d < hi + CROSSING / 2:
                return b
        return len(self.street.blocks) - 1

    def thing_d(self, th: Thing, t: Optional[float] = None) -> float:
        t = self.t if t is None else t
        return th.d - th.v * max(0.0, t - self.level.brief)

    def throw(self, side: int) -> None:
        if not self.riding() or self.result is not None or \
                self.t < self.down_until or self.papers <= 0 or \
                self.t - self.last_throw < COOLDOWN:
            return
        self.papers -= 1
        self.last_throw = self.t
        self.flying.append(Paper(self.x, self.s, side, self.v))
        self.note(0.05, 900.0, WHOOSH, 0.15, pan=0.6 * side)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.end:
            self.result = (False, _('Out of time: the round was not done'))
            return
        if not self.riding():
            return
        down = self.t < self.down_until
        if not down:
            if control == LEFT:
                self.x -= STEER_V * dt
            elif control == RIGHT:
                self.x += STEER_V * dt
            elif control == FASTER:
                self.v += ACCEL * dt
            elif control == SLOWER:
                self.v -= ACCEL * dt
            self.x = max(LANE[0], min(LANE[1], self.x))
            lo, hi = 0.6 * self.level.speed, 1.6 * self.level.speed
            self.v = max(lo, min(hi, self.v))
            self.s += self.v * dt
        self._fly(dt)
        self._crash()
        self._pass()
        if self.result is None and self.s >= self.street.length and \
                not self.flying:
            self._finish()

    def _fly(self, dt: float) -> None:
        keep = []
        for p in self.flying:
            x = p.x + p.side * PAPER_V * dt
            d = p.d + p.v * dt
            front = LEFT_FRONT if p.side < 0 else RIGHT_FRONT
            if (x - front) * p.side >= 0:
                self._land(p.side, d)
            else:
                keep.append(Paper(x, d, p.side, p.v))
        self.flying = keep

    def _land(self, side: int, d: float) -> None:
        pan = 0.7 * side
        for h in self.street.houses:
            if h.side == side and abs(d - h.d) <= HOUSE_LEN / 2:
                if h.i in self.got:
                    self.note(0.06, 160.0, THUD, 0.2, pan=pan)
                    return
                if self.street.want[h.i]:
                    self.got[h.i] = 'ok'
                    self.note(0.35, 990.0, CHIME, 0.45, pan=pan)
                else:
                    self.got[h.i] = 'wrong'
                    self.note(0.4, 150.0, SHOUT, 0.5, pan=pan)
                    self._mistake()
                self.known[h.i] = self.street.want[h.i]
                return
        self.note(0.06, 160.0, THUD, 0.2, pan=pan)

    def _pass(self) -> None:
        houses = self.street.houses
        while self.passed < len(houses) and \
                self.s > houses[self.passed].d + HOUSE_LEN:
            h = houses[self.passed]
            self.passed += 1
            if h.i in self.got:
                continue
            self.known[h.i] = self.street.want[h.i]
            if self.street.want[h.i]:
                self.got[h.i] = 'missed'
                self.note(0.45, 300.0, HORN, 0.45, pan=0.7 * h.side)
                self._mistake()

    def _mistake(self) -> None:
        self.mistakes += 1
        if self.mistakes > self.level.slack and self.result is None:
            self.result = (False, _('Too many complaints: %d') %
                           self.mistakes)

    def _crash(self) -> None:
        if self.t < self.down_until:
            return
        for k, th in enumerate(self.street.things):
            if k in self.hit:
                continue
            dd = self.thing_d(th) - self.s
            if abs(dd) < th.r + RIDER_R and abs(th.x - self.x) < th.r + \
                    RIDER_R:
                self.hit.add(k)
                self.falls += 1
                self.down_until = self.t + FALL
                self.note(0.5, 110.0, CRASH, 0.6)
                if self.falls >= 3:
                    self.result = (False, _('Three falls: the round is off'))
                return

    def _finish(self) -> None:
        houses = self.street.houses
        self.passed = len(houses)
        for h in houses:
            if h.i not in self.got and self.street.want[h.i]:
                self.got[h.i] = 'missed'
                self._mistake()
        if self.result is None:
            self.result = (True, _('Round done: %d mistake(s)') %
                           self.mistakes)
            self.note(0.6, 1320.0, BELL, 0.5)


def act(run: Run, port: int) -> None:
    if port == THROW_L:
        run.throw(-1)
    elif port == THROW_R:
        run.throw(1)


# --- the players --------------------------------------------------------------

def flight(run: Run, side: int) -> float:
    front = LEFT_FRONT if side < 0 else RIGHT_FRONT
    return abs(front - run.x) / PAPER_V


def _lane(run: Run) -> Optional[int]:
    """A steering port that keeps the bicycle clear of the road ahead."""
    look = 2.2 * run.v
    best, best_x = None, run.x
    choices = [LANE[0] + 8 + k * (LANE[1] - LANE[0] - 16) / 8
               for k in range(9)]

    def danger(x):
        worst = 0.0
        for k, th in enumerate(run.street.things):
            if k in run.hit:
                continue
            gap = run.thing_d(th) - run.s
            if gap < -th.r - RIDER_R or gap > look + th.v * 2.2:
                continue
            ahead_t = max(0.0, gap) / max(1.0, run.v + th.v)
            if ahead_t > 2.2:
                continue
            clear = abs(th.x - x) - th.r - RIDER_R
            if clear < 14:
                worst = max(worst, (14 - clear) * (3.0 - ahead_t))
        return worst
    here = danger(run.x)
    if here <= 0:
        return None
    for x in sorted(choices, key=lambda c: abs(c - run.x)):
        dg = danger(x)
        if best is None or dg < best - 1e-6:
            best, best_x = dg, x
    if abs(best_x - run.x) < 3:
        return None
    return LEFT if best_x < run.x else RIGHT


def _thrower(decide):
    """A player that rides like the reference and throws to the houses
    *decide(run, house)* says."""
    def pilot(run: Run) -> List[int]:
        if run.result is not None or not run.riding():
            return []
        if run.t >= run.down_until:
            for h in run.street.houses[run.passed:run.passed + 6]:
                if h.i in run.got or getattr(run, '_aimed', {}).get(h.i):
                    continue
                land = run.s + run.v * flight(run, h.side)
                if land < h.d - 14:
                    continue
                if land > h.d + HOUSE_LEN / 2 - 12:
                    continue
                if not decide(run, h):
                    continue
                if run.t - run.last_throw < COOLDOWN:
                    break
                run.__dict__.setdefault('_aimed', {})[h.i] = True
                return [THROW_L if h.side < 0 else THROW_R]
        steer = _lane(run)
        return [steer] if steer is not None else []
    return pilot


def _vectors(run: Run) -> List[List[bool]]:
    if '_vectors' not in run.__dict__:
        st = run.street
        run._vectors = [list(truth(r, st.houses, st.landmarks))
                        for r in st.deck]
    return run._vectors


def believed(run: Run, b: int) -> Dict[int, float]:
    """The rules that could be in force in block *b*, weighed: what the
    houses of the block have said, and how likely a change was."""
    st = run.street
    level = st.level
    if level.mode in ('marked', 'told', 'sign') or b == 0:
        return {st.active[b]: 1.0}
    memo = run.__dict__.setdefault('_beliefs', {})
    key = (b, len(run.known))
    if key in memo:
        return memo[key]
    vectors = _vectors(run)
    prev = believed(run, b - 1)
    stay = 0.5
    out: Dict[int, float] = {}
    for k in range(len(st.deck)):
        p = sum(w * (stay if j == k else (1 - stay) / (len(st.deck) - 1))
                for j, w in prev.items())
        for i, wanted in run.known.items():
            if st.houses[i].block == b and vectors[k][i] != wanted:
                p = 0.0
                break
        if p > 0:
            out[k] = p
    total = sum(out.values()) or 1.0
    memo[key] = {k: p / total for k, p in out.items()}
    return memo[key]


def _reference_decide(run: Run, h: House) -> bool:
    st = run.street
    vectors = _vectors(run)
    weights = believed(run, h.block)
    yes = sum(w for k, w in weights.items() if vectors[k][h.i])
    return yes > 0.5


autopilot = _thrower(_reference_decide)
every_house = _thrower(lambda run, h: True)


def first_rule(run: Run, h: House) -> bool:
    st = run.street
    if '_first' not in run.__dict__:
        run._first = truth(st.deck[st.active[0]], st.houses, st.landmarks)
    return run._first[h.i]


stubborn = _thrower(first_rule)


def play(street: Street, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(street)
    while run.result is None:
        ports = pilot(run)
        port = ports[0] if ports else None
        if port is not None and port in EVENTS:
            act(run, port)
            port = None
        run.step(dt, port)
    return run.result
