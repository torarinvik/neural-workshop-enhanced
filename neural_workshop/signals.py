# -*- coding: utf-8 -*-
"""Signals: a partner, a row of things, and a code nobody explains.

Every exchange shows a few objects -- each a colour and a shape -- and a
partner across the table. When the partner speaks, it marks one object
in its mind and sends a signal: one or two glyphs from an alphabet of
eight abstract marks. The player picks the object it meant. When the
player speaks, an object is outlined, the player sends glyphs, and the
partner picks. Either way the answer is shown afterwards. Which glyph
means which colour or shape is the partner's own convention and is never
said: it has to be worked out from what happens, and then used.

A game is a run of exchanges with one partner; a new game is a new
partner with a new code. The ladder:

* rung 1: only listening, glyphs that name colours, objects of
  different colours -- read the code;
* from rung 4 only speaking -- find which of eight glyphs makes the
  partner pick the colour wanted;
* from rung 8 listening and speaking by turns, and glyphs for shapes as
  well as colours: say whatever picks the outlined object out from the
  others;
* from rung 12 two glyphs a signal, and objects that only colour and
  shape *together* tell apart;
* from rung 16 the partner **changes** its code partway through, without
  a word: two glyphs swap meanings, three from rung 20;
* past rung 20 fewer exchanges to learn in, and more objects.

A game passes when it makes at least par: what a reference learner made
on the identical game -- it keeps counts of which glyph went with which
colour or shape, forgets slowly where codes can change, and tries
glyphs it has not tried when it has nothing better -- with ground given
below rung twenty and asked for past it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .i18n import _

GLYPHS = 8
COLOURS = ('red', 'blue', 'green', 'yellow')
SHAPES = ('circle', 'square', 'triangle', 'star')
#: A value is ('colour', i) or ('shape', i); the alphabet names all eight.
VALUES = tuple([('colour', i) for i in range(4)]
               + [('shape', i) for i in range(4)])
MOST_OBJECTS = 8


class Grade(NamedTuple):
    rung: int
    objects: int
    exchanges: int
    #: 'listen', 'speak' or 'both'.
    roles: str
    #: Which attributes glyphs name in this game, and how many a signal is.
    shapes: bool
    length: int
    #: Glyph meanings swapped partway (0: none).
    swaps: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        roles = 'listen'
    elif r < 8:
        roles = 'speak'
    else:
        roles = 'both'
    if r < 8:
        objects = min(4, 2 + (r - 1) % 4 // 1 if r < 4 else 2 + (r - 4))
    elif r < 12:
        objects = min(5, 3 + (r - 8) // 2)
    else:
        objects = min(MOST_OBJECTS, 4 + (r - 12) // 3)
    return Grade(
        rung=r,
        objects=max(2, objects),
        exchanges=16 if r <= 20 else max(8, 16 - (r - 20)),
        roles=roles,
        shapes=r >= 8,
        length=2 if r >= 12 else 1,
        swaps=0 if r < 16 else (2 if r < 20 else 3),
    )


Thing = Tuple[int, int]          # (colour, shape)


class Exchange(NamedTuple):
    role: str                    # who speaks: 'partner' or 'player'
    objects: Tuple[Thing, ...]
    target: int
    #: Fixes the partner's choice among equally good readings.
    coin: int


class Deal(NamedTuple):
    seed: int
    level: Grade
    #: meaning[g] is the value glyph g names, before the change.
    meaning: Tuple[Tuple[str, int], ...]
    exchanges: Tuple[Exchange, ...]
    #: From this exchange on the code is ``changed``.
    change_at: int
    changed: Tuple[Tuple[str, int], ...]

    def code(self, at: int) -> Tuple[Tuple[str, int], ...]:
        return self.changed if at >= self.change_at else self.meaning


def value_of(thing: Thing, value: Tuple[str, int]) -> bool:
    kind, index = value
    return thing[0] == index if kind == 'colour' else thing[1] == index


def _scene(level: Grade, draw: random.Random) -> Optional[Tuple[
        Tuple[Thing, ...], int]]:
    n = level.objects
    if not level.shapes:
        colours = draw.sample(range(4), min(n, 4))
        things = [(c, draw.randrange(4)) for c in colours]
        return tuple(things), draw.randrange(len(things))
    for _attempt in range(200):
        things = []
        while len(things) < n:
            thing = (draw.randrange(4), draw.randrange(4))
            if thing not in things:
                things.append(thing)
        target = draw.randrange(n)
        mine = things[target]
        colour_unique = sum(t[0] == mine[0] for t in things) == 1
        shape_unique = sum(t[1] == mine[1] for t in things) == 1
        if level.length == 1 and (colour_unique or shape_unique):
            return tuple(things), target
        if level.length == 2 and not colour_unique and not shape_unique:
            return tuple(things), target
    return None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    # Below rung 8 only colours are named: four glyphs mean nothing.
    meaning = list(VALUES) if level.shapes else \
        [v for v in VALUES if v[0] == 'colour'] + [None] * 4
    draw.shuffle(meaning)
    exchanges = []
    while len(exchanges) < level.exchanges:
        scene = _scene(level, draw)
        if scene is None:
            continue
        things, target = scene
        if level.roles == 'listen':
            role = 'partner'
        elif level.roles == 'speak':
            role = 'player'
        else:
            role = 'partner' if len(exchanges) % 2 == 0 else 'player'
        exchanges.append(Exchange(role, things, target,
                                  draw.randrange(1 << 16)))
    changed = list(meaning)
    change_at = level.exchanges
    if level.swaps:
        change_at = level.exchanges // 2 + draw.randint(-2, 1)
        used = [g for g, v in enumerate(meaning) if v is not None]
        moved = draw.sample(used, level.swaps)
        values = [changed[g] for g in moved]
        values = values[1:] + values[:1]
        for g, v in zip(moved, values):
            changed[g] = v
    return Deal(seed, level, tuple(meaning), tuple(exchanges), change_at,
                tuple(changed))


# --- the partner ---------------------------------------------------------

def partner_says(dealt: Deal, at: int) -> Tuple[int, ...]:
    """The glyphs the partner sends for exchange *at*'s target."""
    ex = dealt.exchanges[at]
    code = dealt.code(at)
    mine = ex.objects[ex.target]
    glyph = {v: g for g, v in enumerate(code)}
    if dealt.level.length == 2:
        return (glyph[('colour', mine[0])], glyph[('shape', mine[1])])
    if not dealt.level.shapes:
        return (glyph[('colour', mine[0])],)
    if sum(t[0] == mine[0] for t in ex.objects) == 1:
        return (glyph[('colour', mine[0])],)
    return (glyph[('shape', mine[1])],)


def partner_picks(dealt: Deal, at: int, signal: Sequence[int]) -> int:
    """The object the partner takes a player's signal to mean: those that
    fit every glyph it understands, or all of them if none fits, one
    fixed by the exchange's coin."""
    ex = dealt.exchanges[at]
    code = dealt.code(at)
    fits = [i for i, thing in enumerate(ex.objects)
            if all(code[g] is None or value_of(thing, code[g])
                   for g in signal)]
    if all(code[g] is None for g in signal):
        fits = []
    pool = fits or list(range(len(ex.objects)))
    return pool[ex.coin % len(pool)]


# --- a game --------------------------------------------------------------

class Game:
    """A game in play: where it is, what has been said and picked."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.at = 0
        self.wins: List[bool] = []
        #: Glyphs the player has put in so far, speaking.
        self.drafted: List[int] = []
        #: What happened, exchange by exchange: (exchange, signal,
        #: picked, right).
        self.history: List[Tuple[Exchange, Tuple[int, ...], int,
                                 bool]] = []

    @property
    def over(self) -> bool:
        return self.at >= len(self.deal.exchanges)

    @property
    def exchange(self) -> Optional[Exchange]:
        return None if self.over else self.deal.exchanges[self.at]

    def heard(self) -> Tuple[int, ...]:
        """The partner's signal, when it is the partner's turn."""
        ex = self.exchange
        if ex is None or ex.role != 'partner':
            return ()
        return partner_says(self.deal, self.at)

    def pick(self, index: int) -> Optional[bool]:
        ex = self.exchange
        if ex is None or ex.role != 'partner' \
                or not 0 <= index < len(ex.objects):
            return None
        return self._close(self.heard(), index)

    def say(self, glyph: int) -> Optional[bool]:
        ex = self.exchange
        if ex is None or ex.role != 'player' or not 0 <= glyph < GLYPHS:
            return None
        self.drafted.append(glyph)
        if len(self.drafted) < self.deal.level.length:
            return None
        signal = tuple(self.drafted)
        return self._close(signal, partner_picks(self.deal, self.at,
                                                 signal))

    def _close(self, signal: Tuple[int, ...], picked: int) -> bool:
        ex = self.exchange
        right = picked == ex.target
        self.history.append((ex, signal, picked, right))
        self.wins.append(right)
        self.drafted = []
        self.at += 1
        return right

    @property
    def score(self) -> int:
        return sum(self.wins)


# --- the reference -------------------------------------------------------

class Learner:
    """A belief, per glyph, over what it means -- each colour, each shape,
    or nothing -- updated by how likely each exchange's outcome was under
    every meaning, and let drift back towards not knowing where a code
    can change."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        level = dealt.level
        self.options: List[Optional[Tuple[str, int]]] = \
            [v for v in VALUES if level.shapes or v[0] == 'colour']
        if not level.shapes:
            self.options.append(None)
        self.belief = [[1.0 / len(self.options)] * len(self.options)
                       for _g in range(GLYPHS)]
        self.drift = 0.15 if level.swaps else 0.0

    def _normal(self, row: List[float]) -> None:
        total = sum(row) or 1.0
        for i in range(len(row)):
            row[i] = row[i] / total
            if self.drift:
                row[i] = (1 - self.drift) * row[i] + \
                    self.drift / len(row)

    def _chance(self, thing_has, objects, picked, meaning) -> float:
        """How likely the partner's pick was if a glyph meant *meaning*."""
        n = len(objects)
        if meaning is None:
            return 1.0 / n
        fits = [i for i, t in enumerate(objects) if value_of(t, meaning)]
        if not fits:
            return 1.0 / n
        return 1.0 / len(fits) if picked in fits else 0.02

    def saw(self, exchange: Exchange, signal: Sequence[int],
            picked: int) -> None:
        level = self.deal.level
        for place, g in enumerate(signal):
            row = self.belief[g]
            for i, meaning in enumerate(self.options):
                if exchange.role == 'partner':
                    mine = exchange.objects[exchange.target]
                    fit = meaning is not None and value_of(mine, meaning)
                    if level.length == 2 and meaning is not None and \
                            meaning[0] != ('colour', 'shape')[place]:
                        fit = False
                    row[i] *= 1.0 if fit else 0.02
                else:
                    row[i] *= self._chance(None, exchange.objects, picked,
                                           meaning)
            self._normal(row)

    def _reads(self, g: int, thing: Thing) -> float:
        """How likely glyph *g* describes *thing*."""
        return sum(p * (1.0 if m is None or value_of(thing, m) else 0.0)
                   for p, m in zip(self.belief[g], self.options))

    def listen(self, exchange: Exchange, signal: Sequence[int]) -> int:
        def fit(i):
            score = 1.0
            for g in signal:
                score *= self._reads(g, exchange.objects[i])
            return score
        return max(range(len(exchange.objects)), key=lambda i: (fit(i), -i))

    def _lands(self, g: int, exchange: Exchange) -> float:
        """How likely the partner picks the target if *g* is sent alone."""
        return sum(p * self._chance(None, exchange.objects, exchange.target,
                                    m)
                   for p, m in zip(self.belief[g], self.options))

    def speak(self, exchange: Exchange) -> Tuple[int, ...]:
        mine = exchange.objects[exchange.target]
        if self.deal.level.length == 1:
            return (max(range(GLYPHS),
                        key=lambda g: (self._lands(g, exchange), -g)),)
        signal: List[int] = []
        for kind, index in (('colour', mine[0]), ('shape', mine[1])):
            v = self.options.index((kind, index))
            pool = [g for g in range(GLYPHS) if g not in signal]
            signal.append(max(pool, key=lambda g: (self.belief[g][v], -g)))
        return tuple(signal)


def reference_game(dealt: Deal) -> Game:
    game, learner = Game(dealt), Learner(dealt)
    while not game.over:
        ex = game.exchange
        if ex.role == 'partner':
            game.pick(learner.listen(ex, game.heard()))
        else:
            for g in learner.speak(ex):
                game.say(g)
        learner.saw(*game.history[-1][:3])
    return game


def guessing(dealt: Deal, tries: int = 4) -> float:
    total = 0
    for seed in range(tries):
        draw = random.Random(seed)
        game = Game(dealt)
        while not game.over:
            ex = game.exchange
            if ex.role == 'partner':
                game.pick(draw.randrange(len(ex.objects)))
            else:
                game.say(draw.randrange(GLYPHS))
        total += game.score
    return total / float(tries)


def par(dealt: Deal) -> float:
    from .ui.rungtask import ladder_par
    ref = reference_game(dealt).score
    # The ceiling past twenty is halfway from the reference to a perfect
    # game: a perfect game would have to know a code it is still
    # learning.
    return ladder_par(dealt.level.rung, ref, guessing(dealt),
                      (ref + len(dealt.exchanges)) / 2.0)


def colour_word(i: int) -> str:
    return {0: _('red'), 1: _('blue'), 2: _('green'), 3: _('yellow')}[i]


def shape_word(i: int) -> str:
    return {0: _('circle'), 1: _('square'), 2: _('triangle'),
            3: _('star')}[i]
