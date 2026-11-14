# -*- coding: utf-8 -*-
"""Notebook: more to remember than a head can hold, and a few lines to
write on.

A round is a stream of cards. A fact card gives a code -- *Gate Maple:
382* -- and some cards later a question card asks for it, with a few
codes to choose from. Beside the cards is a notebook of a few lines. On
any fact card the player can write the card onto a line (overwriting
whatever was there) before moving on, and the notebook stays in view, so
a code written down is a code that can be read back when it is asked.

What the task measures is whether the notebook gets used well: what is
worth a line, which line to give up, and when. The ladder:

* more facts, and longer between a fact and its question;
* from rung 6 cards marked *not needed*, never asked about, which waste
  a line if written down;
* from rung 8 updates -- *Gate Maple is now 517* -- after which the old
  code is wrong, and is among the choices;
* up to rung 15 the notebook has a line for everything that has to be
  remembered at once; from rung 16 it has fewer, losing one every second
  rung, so the rest has to be held in the head -- by rung 30 nearly all
  of it.

A round passes when every question is answered right. There is no par.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

MOST_LINES = 8
MOST_CHOICES = 4

THINGS = ('Gate', 'Locker', 'Room', 'Bus', 'Safe', 'Desk', 'Bay', 'Door')
NAMES = ('Maple', 'Ivy', 'Cedar', 'Birch', 'Fern', 'Hazel', 'Rowan',
         'Willow', 'Aspen', 'Holly', 'Juniper', 'Laurel', 'Myrtle', 'Olive',
         'Pine', 'Sage', 'Thorn', 'Elm', 'Alder', 'Larch')


class Grade(NamedTuple):
    rung: int
    facts: int
    #: The most facts waiting to be asked at any one time.
    hold: int
    #: Cards at least between a fact and its question.
    gap: int
    choices: int
    noise: int
    updates: int
    lines: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    hold = min(MOST_LINES, 1 + (r - 1) // 2)
    facts = min(16, r + (r - 1) // 3)
    if r < 6:
        lines = hold + 1
    elif r <= 15:
        lines = hold
    else:
        lines = max(1, hold - (r - 14) // 2)
    return Grade(
        rung=r,
        facts=facts,
        hold=hold,
        gap=min(8, (r - 1) // 2),
        choices=2 if r < 3 else MOST_CHOICES,
        noise=0 if r < 6 else 1 + (r - 6) // 4,
        updates=0 if r < 8 else min(5, 1 + (r - 8) // 3),
        lines=lines,
    )


class Card(NamedTuple):
    #: 'fact', 'update', 'noise' or 'question'.
    kind: str
    key: str
    code: int
    #: For a question: the codes offered, and which one is right.
    offered: Tuple[int, ...] = ()
    answer: int = -1

    def words(self) -> str:
        if self.kind == 'fact':
            return '%s: %d' % (self.key, self.code)
        if self.kind == 'update':
            return _('%s is now %d') % (self.key, self.code)
        if self.kind == 'noise':
            return _('%s: %d   (not needed)') % (self.key, self.code)
        return _('%s?') % self.key

    def note(self) -> str:
        """What writing this card down puts on a line."""
        return '%s %d' % (self.key, self.code)


class Deal(NamedTuple):
    seed: int
    level: Grade
    cards: Tuple[Card, ...]

    @property
    def questions(self) -> int:
        return sum(1 for c in self.cards if c.kind == 'question')


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    names = [(t, n) for t in THINGS for n in NAMES]
    draw.shuffle(names)
    keys = ['%s %s' % pair for pair in names[:level.facts + level.noise]]
    needed, noise = keys[:level.facts], keys[level.facts:]
    codes: Dict[str, List[int]] = {}
    used = set()

    def fresh() -> int:
        while True:
            code = draw.randint(100, 999)
            if code not in used:
                used.add(code)
                return code

    updated = set(draw.sample(needed, min(level.updates, len(needed))))
    cards: List[Card] = []
    waiting: List[Tuple[str, int]] = []     # (key, index of its fact)
    to_show = list(needed)
    noise_at = set(draw.sample(range(level.facts + level.noise),
                               level.noise))
    pending_updates = set()
    while to_show or waiting:
        ready = [(k, at) for k, at in waiting
                 if len(cards) - at > level.gap and k not in pending_updates]
        due_update = [k for k in pending_updates]
        can_show = to_show and len(waiting) < level.hold
        roll = draw.random()
        if due_update and roll < 0.35:
            key = draw.choice(due_update)
            pending_updates.discard(key)
            code = fresh()
            codes[key].append(code)
            cards.append(Card('update', key, code))
            # The question waits a full gap after the update too.
            waiting = [(k, len(cards) - 1 if k == key else at)
                       for k, at in waiting]
            continue
        if noise and len(cards) in noise_at:
            key = noise.pop()
            cards.append(Card('noise', key, fresh()))
            continue
        if can_show and (not ready or roll < 0.55):
            key = to_show.pop()
            code = fresh()
            codes[key] = [code]
            cards.append(Card('fact', key, code))
            waiting.append((key, len(cards) - 1))
            if key in updated:
                pending_updates.add(key)
            continue
        if ready:
            key, _at = ready[0] if roll < 0.5 else draw.choice(ready)
            waiting = [(k, at) for k, at in waiting if k != key]
            cards.append(_question(key, codes, used, level, draw))
            continue
        if due_update:
            continue                # an update must come first
        # Nothing is ready and nothing new may be shown: a noise card,
        # or a filler fact no one will be asked about, passes the time.
        if noise:
            key = noise.pop()
        else:
            key = 'Spare %s' % draw.choice(NAMES)
        cards.append(Card('noise', key, fresh()))
    return Deal(seed, level, tuple(cards))


def _question(key: str, codes: Dict[str, List[int]], used, level: Grade,
              draw: random.Random) -> Card:
    right = codes[key][-1]
    decoys = [c for c in codes[key][:-1]]                  # stale codes
    others = [c for k, cs in codes.items() if k != key for c in cs]
    draw.shuffle(others)
    decoys += others
    offered = [right]
    for code in decoys:
        if len(offered) == level.choices:
            break
        if code not in offered:
            offered.append(code)
    while len(offered) < level.choices:
        code = draw.randint(100, 999)
        if code not in offered:
            offered.append(code)
    draw.shuffle(offered)
    return Card('question', key, right, tuple(offered), offered.index(right))


class Round:
    """Play through a deal: the notebook, and the answers given."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.at = 0
        self.lines: List[str] = [''] * dealt.level.lines
        self.answers: List[bool] = []

    @property
    def card(self) -> Optional[Card]:
        return self.deal.cards[self.at] if self.at < len(self.deal.cards) \
            else None

    @property
    def over(self) -> bool:
        return self.at >= len(self.deal.cards)

    @property
    def right(self) -> int:
        return sum(self.answers)

    def write(self, line: int) -> bool:
        card = self.card
        if card is None or card.kind == 'question' \
                or not 0 <= line < len(self.lines):
            return False
        self.lines[line] = card.note()
        return True

    def next(self) -> bool:
        card = self.card
        if card is None or card.kind == 'question':
            return False
        self.at += 1
        return True

    def answer(self, choice: int) -> Optional[bool]:
        card = self.card
        if card is None or card.kind != 'question' \
                or not 0 <= choice < len(card.offered):
            return None
        right = choice == card.answer
        self.answers.append(right)
        self.at += 1
        return right


def reference_move(play: Round, memory: Dict[str, int]) -> Tuple[str, int]:
    """A careful notebook keeper: ('write', line), ('next', 0) or
    ('answer', choice).

    It writes down every needed fact and update -- over the line already
    holding that key, else an empty line, else the line of a key already
    asked about, else the oldest line -- answers from the notebook when
    the key is on it, and from *memory* (what it was told and did not
    write down, which stands for a head) when it is not and
    ``memory['head']`` allows it.
    """
    card = play.card
    if card.kind == 'question':
        for line in play.lines:
            if line.rsplit(' ', 1)[0] == card.key:
                code = int(line.rsplit(' ', 1)[1])
                if code in card.offered:
                    return ('answer', card.offered.index(code))
        if card.key in memory:
            return ('answer', card.offered.index(memory[card.key]))
        return ('answer', 0)
    if card.kind == 'noise' or memory.get('_wrote') == play.at:
        return ('next', 0)
    memory['_wrote'] = play.at
    asked = {c.key for c in play.deal.cards[:play.at]
             if c.kind == 'question'}
    keyed = [i for i, line in enumerate(play.lines)
             if line.rsplit(' ', 1)[0] == card.key]
    empty = [i for i, line in enumerate(play.lines) if not line]
    stale = [i for i, line in enumerate(play.lines)
             if line.rsplit(' ', 1)[0] in asked]
    for choice in (keyed, empty, stale):
        if choice:
            return ('write', choice[0])
    if memory.get('head'):
        memory[card.key] = card.code
        return ('next', 0)
    return ('write', play.at % len(play.lines))


def act(play: Round, move: Tuple[str, int]) -> None:
    kind, at = move
    if kind == 'write':
        play.write(at)
    elif kind == 'next':
        play.next()
    else:
        play.answer(at)


def peak(dealt: Deal) -> int:
    """The most needed facts waiting to be asked at any one moment."""
    waiting, most = set(), 0
    for card in dealt.cards:
        if card.kind == 'fact':
            waiting.add(card.key)
        elif card.kind == 'question':
            waiting.discard(card.key)
        most = max(most, len(waiting))
    return most
