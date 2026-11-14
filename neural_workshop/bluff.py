# -*- coding: utf-8 -*-
"""Bluff: a small poker game against an opponent with habits -- and later
one that learns yours.

Each hand both players put in one chip and get one card from a short deck
of numbered cards; the higher card wins a showdown. The player to act
first checks or bets one chip. Facing a check, the other checks (a
showdown for the two chips in) or bets. Facing a bet, a player folds
(the bettor takes what is in) or calls (a showdown for two chips each).
Who acts first alternates.

What is learned is the opponent, from what it does and from the cards it
shows when a hand goes to a showdown:

* rungs 1-2 a **calling station**: it calls anything, so bet the good
  cards and never bluff;
* rungs 3-4 a **rock**: it folds all but the best, so bluff it;
* rungs 5-6 a **maniac**: it bets nearly every hand, so call it down;
* rungs 7-13 one of those -- or, from 10, a sound player -- unannounced:
  find out which;
* rungs 14-17 an **adaptive** player that watches what you do: bluff
  often and it calls more, fold too much and it bluffs more;
* from rung 18 the opponent **changes** at a hand nobody announces.

Bigger decks come in at rungs 7, 14 and 18 (five, seven, nine cards),
so a card's worth is less obvious.

Every card and every coin the opponent tosses to mix its play is dealt up
front, by hand number, so the reference plays exactly the hands the
player plays. A round is scored not by the chips, which the cards move,
but by what each hand's choices were worth: the chips they win on
average over every card the opponent could have held, against what the
opponent really does at that moment (at a spot the hand never reached,
the player is taken to bet or call with the better half of the deck).
Chips are shown as well. Par is what the reference's choices were worth
on the identical deal, less an allowance below rung twenty and more
after.

The reference keeps, for the opponent, how often it bets and calls with
low, middle and high cards -- counted from showdowns, forgetting slowly
in case it changes -- and plays the best reply to that, looking ahead
through its own later choice in the hand.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: Kinds of opponent.
STATION, ROCK, MANIAC, SOUND, ADAPTIVE = ('station', 'rock', 'maniac',
                                          'sound', 'adaptive')
#: The player's two choices: check or fold, bet or call.
PASSIVE, AGGRESSIVE = 0, 1


class Grade(NamedTuple):
    rung: int
    cards: int
    hands: int
    #: Opponent kinds a round may deal, and whether it changes mid-round.
    kinds: Tuple[str, ...]
    changes: bool
    #: Allowance, as a share of the reference's edge over sound play
    #: (positive), or chips a hand demanded on top of it (negative).
    allow: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r <= 2:
        kinds: Tuple[str, ...] = (STATION,)
    elif r <= 4:
        kinds = (ROCK,)
    elif r <= 6:
        kinds = (MANIAC,)
    elif r <= 9:
        kinds = (STATION, ROCK, MANIAC)
    elif r <= 13:
        kinds = (STATION, ROCK, MANIAC, SOUND)
    elif r <= 17:
        kinds = (ADAPTIVE,)
    else:
        kinds = (STATION, ROCK, MANIAC, ADAPTIVE)
    return Grade(
        rung=r,
        cards=3 if r < 7 else (5 if r < 14 else (7 if r < 18 else 9)),
        hands=20 + r,
        kinds=kinds,
        changes=r >= 18,
        allow=((21 - r) / 20.0 if r <= 20 else -0.03 * (r - 20)),
    )


# --- the opponents -----------------------------------------------------------

def strength(card: int, cards: int) -> float:
    """0 for the lowest card, 1 for the highest."""
    return card / float(cards - 1)


class Habits:
    """What an opponent tends to do, and for the adaptive one, what it
    has noticed about the player."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        #: The adaptive opponent's notes: the player's bets, bluffs among
        #: them that were seen, folds to bets, and bets faced.
        self.bets = self.bluffs = self.shown = 0
        self.folds = self.faced = 0

    def aggression(self, s: float, spot: str) -> float:
        """Chance of betting (spot '' or 'c') or calling ('b', 'cb')
        with a card of strength *s*."""
        kind = self.kind
        opening = spot in ('', 'c')
        if kind == STATION:
            return (1.0 if s > 0.8 else 0.0) if opening else 1.0
        if kind == ROCK:
            return (1.0 if s > 0.85 else 0.0) if opening else \
                (1.0 if s > 0.8 else 0.0)
        if kind == MANIAC:
            return 0.9 if opening else (1.0 if s > 0.3 else 0.2)
        # Sound play: bet the top, bluff some of the bottom, call the
        # middle sometimes.
        bluff, call_from = 0.33, 0.45
        if kind == ADAPTIVE:
            if self.shown >= 2:
                rate = self.bluffs / float(self.shown)
                # A player who bluffs a lot gets called a lot.
                call_from = 0.2 if rate > 0.3 else (0.7 if rate < 0.1
                                                    else 0.45)
            if self.faced >= 3 and self.folds / float(self.faced) > 0.5:
                bluff = 0.8
        if opening:
            if s > 0.74:
                return 1.0
            return bluff if s < 0.26 else 0.0
        if s >= call_from + 0.2:
            return 1.0
        return 0.35 if s >= call_from else 0.0

    def notice(self, player_card: Optional[int], cards: int,
               player_bet: bool, player_folded_to_bet: Optional[bool]
               ) -> None:
        """The adaptive opponent's notebook, after a hand."""
        if self.kind != ADAPTIVE:
            return
        if player_bet:
            self.bets += 1
            if player_card is not None:
                self.shown += 1
                if strength(player_card, cards) < 0.5:
                    self.bluffs += 1
        if player_folded_to_bet is not None:
            self.faced += 1
            self.folds += 1 if player_folded_to_bet else 0


# --- a deal --------------------------------------------------------------------

class Hand(NamedTuple):
    player: int
    opponent: int
    #: Whether the player acts first.
    player_first: bool
    #: The opponent's coins for its (up to two) choices in the hand.
    coins: Tuple[float, float]


class Deal(NamedTuple):
    level: Grade
    hands: Tuple[Hand, ...]
    #: The opponent's kind from each hand on: ((hand, kind), ...).
    kinds: Tuple[Tuple[int, str], ...]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if rng is None:
        rng = random.Random(seed)
    level = grade(rung)
    hands = []
    for index in range(level.hands):
        mine, theirs = rng.sample(range(level.cards), 2)
        hands.append(Hand(mine, theirs, index % 2 == 0,
                          (rng.random(), rng.random())))
    first = rng.choice(level.kinds)
    kinds = [(0, first)]
    if level.changes:
        later = rng.choice([k for k in level.kinds if k != first])
        kinds.append((rng.randint(level.hands // 3,
                                  2 * level.hands // 3), later))
    return Deal(level, tuple(hands), tuple(kinds))


def kind_at(dealt: Deal, hand: int) -> str:
    found = dealt.kinds[0][1]
    for start, kind in dealt.kinds:
        if hand >= start:
            found = kind
    return found


# --- playing -------------------------------------------------------------------

class Record(NamedTuple):
    """A hand as it went: the actions in order ('c', 'b', 'f', 'k' for
    check, bet, fold, call), who won what, and the opponent's card if it
    was shown."""
    player_first: bool
    actions: str
    player_card: int
    shown: Optional[int]
    won: int


class Match:
    """A round: hands played one after another."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        self.records: List[Record] = []
        #: What each hand's choices were worth on average.
        self.worths: List[float] = []
        self.habits: Dict[str, Habits] = {}
        self.actions = ''
        self._coin = 0
        self._start_hand()

    # --- whose turn ---------------------------------------------------------

    @property
    def index(self) -> int:
        return len(self.records)

    @property
    def over(self) -> bool:
        return self.index >= len(self.deal.hands)

    @property
    def hand(self) -> Optional[Hand]:
        return None if self.over else self.deal.hands[self.index]

    @property
    def chips(self) -> int:
        return sum(r.won for r in self.records)

    @property
    def value(self) -> float:
        return sum(self.worths)

    def _worth(self, actions: str) -> float:
        """The hand's worth: the player's choices as made, the
        opponent's card and coins averaged out."""
        hand = self.hand
        habits = self._opponent()
        cards = self.level.cards
        mine = hand.player
        taken = {actions[:i]: actions[i] for i in range(len(actions))
                 if (i % 2 == 0) == hand.player_first}

        def go(spot: str, theirs: int) -> float:
            done = _payoff(spot, hand.player_first, mine, theirs)
            if done is not None:
                return done
            nxt = ('b', 'c') if spot in ('', 'c') else ('k', 'f')
            if (len(spot) % 2 == 0) == hand.player_first:
                if spot in taken:
                    return go(spot + taken[spot], theirs)
                good = strength(mine, cards) >= 0.5
                return go(spot + nxt[0 if good else 1], theirs)
            p = habits.aggression(strength(theirs, cards), spot)
            return (p * go(spot + nxt[0], theirs)
                    + (1 - p) * go(spot + nxt[1], theirs))

        others = [c for c in range(cards) if c != mine]
        return sum(go('', t) for t in others) / len(others)

    def _opponent(self) -> Habits:
        kind = kind_at(self.deal, self.index)
        if kind not in self.habits:
            self.habits[kind] = Habits(kind)
        return self.habits[kind]

    def player_to_act(self) -> bool:
        hand = self.hand
        if hand is None:
            return False
        acts = len(self.actions)
        first_player = hand.player_first
        return (acts % 2 == 0) == first_player

    @property
    def spot(self) -> str:
        return self.actions

    # --- moves -----------------------------------------------------------------

    def _start_hand(self) -> None:
        self.actions = ''
        self._coin = 0
        if not self.over and not self.player_to_act():
            self._opponent_moves()

    def act(self, choice: int) -> bool:
        """The player checks/folds (0) or bets/calls (1)."""
        if self.over or not self.player_to_act():
            return False
        self._take(choice)
        if not self._finished():
            self._opponent_moves()
        return True

    def _take(self, aggressive: int) -> None:
        spot = self.actions
        if spot in ('', 'c'):
            self.actions += 'b' if aggressive else 'c'
        else:
            self.actions += 'k' if aggressive else 'f'

    def _opponent_moves(self) -> None:
        hand = self.hand
        s = strength(hand.opponent, self.level.cards)
        p = self._opponent().aggression(s, self.actions)
        coin = hand.coins[min(self._coin, 1)]
        self._coin += 1
        self._take(1 if coin < p else 0)
        self._finished()

    def _finished(self) -> bool:
        a = self.actions
        if a not in ('cc', 'bk', 'cbk', 'bf', 'cbf'):
            return False
        hand = self.hand
        player_first = hand.player_first
        if a.endswith('f'):
            # The one who bet takes the antes: first actor bet in 'bf'.
            bettor_first = a == 'bf'
            player_bet = bettor_first == player_first
            won = 1 if player_bet else -1
            shown = None
        else:
            stake = 1 if a == 'cc' else 2
            won = stake if hand.player > hand.opponent else -stake
            shown = hand.opponent
        self.worths.append(self._worth(a))
        # What the player did, for the adaptive opponent.
        mine = [a[i] for i in range(len(a))
                if (i % 2 == 0) == player_first]
        theirs = [a[i] for i in range(len(a))
                  if (i % 2 == 0) != player_first]
        player_bet = 'b' in mine
        faced = 'b' in theirs
        folded = ('f' in mine) if faced else None
        self._opponent().notice(hand.player if shown is not None else None,
                                self.level.cards, player_bet, folded)
        self.records.append(Record(player_first, a, hand.player, shown, won))
        self._start_hand()
        return True


# --- the reference -------------------------------------------------------------

BUCKETS = 3


def bucket(card: int, cards: int) -> int:
    return min(BUCKETS - 1, int(strength(card, cards) * BUCKETS))


class Model:
    """What the reference believes the opponent does: for each spot kind
    (opening, facing a bet) and each card bucket, a Beta belief about
    being aggressive. Old evidence fades a little."""

    KEEP = 0.97

    def __init__(self, cards: int) -> None:
        self.cards = cards
        # Prior: sound play.
        sound = Habits(SOUND)
        self.yes: Dict[Tuple[str, int], float] = {}
        self.no: Dict[Tuple[str, int], float] = {}
        for spot in ('open', 'face'):
            for b in range(BUCKETS):
                s = (b + 0.5) / BUCKETS
                p = sound.aggression(s, '' if spot == 'open' else 'b')
                self.yes[(spot, b)] = 1.0 * p + 0.3
                self.no[(spot, b)] = 1.0 * (1 - p) + 0.3

    def saw(self, record: Record) -> None:
        for key in self.yes:
            self.yes[key] = 0.3 + (self.yes[key] - 0.3) * self.KEEP
            self.no[key] = 0.3 + (self.no[key] - 0.3) * self.KEEP
        if record.shown is None:
            # A fold: the opponent's card is unseen, but a fold to a bet
            # says its card was weak enough to fold; count it, lightly,
            # against every bucket that facing a bet.
            a = record.actions
            folder_first = a == 'cbf'
            if (folder_first == record.player_first):
                return      # the player folded
            for b in range(BUCKETS):
                self.no[('face', b)] += 0.3 * (BUCKETS - b) / BUCKETS
            return
        b = bucket(record.shown, self.cards)
        a = record.actions
        for i, act in enumerate(a):
            theirs = (i % 2 == 0) != record.player_first
            if not theirs:
                continue
            spot = 'open' if act in 'cb' else 'face'
            if act in 'bk':
                self.yes[(spot, b)] += 1
            else:
                self.no[(spot, b)] += 1

    def p(self, spot: str, b: int) -> float:
        key = ('open' if spot in ('', 'c') else 'face', b)
        return self.yes[key] / (self.yes[key] + self.no[key])


def _payoff(actions: str, player_first: bool, mine: int, theirs: int
            ) -> Optional[int]:
    if actions not in ('cc', 'bk', 'cbk', 'bf', 'cbf'):
        return None
    if actions.endswith('f'):
        bettor_first = actions == 'bf'
        return 1 if bettor_first == player_first else -1
    stake = 1 if actions == 'cc' else 2
    return stake if mine > theirs else -stake


def best_choice(model: Model, actions: str, player_first: bool, mine: int,
                cards: int) -> int:
    """AGGRESSIVE or PASSIVE: whichever is worth more on average over
    the opponent's possible cards, weighted by how likely each is to
    have played as it did."""
    nxt = ('b', 'c') if actions in ('', 'c') else ('k', 'f')
    weights = []
    for theirs in range(cards):
        if theirs == mine:
            continue
        w = 1.0
        for i, act in enumerate(actions):
            if (i % 2 == 0) == player_first:
                continue
            p = model.p(actions[:i], bucket(theirs, cards))
            w *= p if act in 'bk' else (1 - p)
        weights.append((theirs, w))
    norm = sum(w for _t, w in weights) or 1.0
    worth = []
    for n in nxt:
        total = 0.0
        for theirs, w in weights:
            total += w * _after(model, actions + n, player_first, mine,
                                theirs, cards)
        worth.append(total / norm)
    return AGGRESSIVE if worth[0] >= worth[1] - 1e-9 else PASSIVE


def _after(model, actions, player_first, mine, theirs, cards):
    done = _payoff(actions, player_first, mine, theirs)
    if done is not None:
        return done
    players_turn = (len(actions) % 2 == 0) == player_first
    nxt = ('b', 'c') if actions in ('', 'c') else ('k', 'f')
    if players_turn:
        # The player's own later choice, made without seeing the card.
        return _pick_later(model, actions, player_first, mine, theirs,
                           cards)
    p = model.p(actions, bucket(theirs, cards))
    return (p * _after(model, actions + nxt[0], player_first, mine, theirs,
                       cards)
            + (1 - p) * _after(model, actions + nxt[1], player_first, mine,
                               theirs, cards))


def _pick_later(model, actions, player_first, mine, theirs, cards):
    choice = best_choice(model, actions, player_first, mine, cards)
    nxt = ('b', 'c') if actions in ('', 'c') else ('k', 'f')
    return _after(model, actions + nxt[0 if choice else 1], player_first,
                  mine, theirs, cards)


def reference_move(model: Model, match: Match) -> int:
    hand = match.hand
    return best_choice(model, match.actions, hand.player_first, hand.player,
                       match.level.cards)


def play_with(dealt: Deal, chooser) -> Match:
    """A whole round with *chooser(match, model)* making the player's
    choices; the model is kept up to date for it."""
    match = Match(dealt)
    model = Model(dealt.level.cards)
    seen = 0
    while not match.over:
        while seen < len(match.records):
            model.saw(match.records[seen])
            seen += 1
        if match.over:
            break
        match.act(chooser(match, model))
    return match


def reference_round(dealt: Deal) -> Match:
    return play_with(dealt, lambda match, model: reference_move(model,
                                                                match))


def sound_round(dealt: Deal) -> Match:
    """A player who plays soundly and never adapts: the baseline."""
    sound = Habits(SOUND)

    def choose(match, _model):
        hand = match.hand
        s = strength(hand.player, dealt.level.cards)
        p = sound.aggression(s, match.actions)
        coin = (hand.coins[0] + 0.5) % 1.0     # its own coin, not theirs
        return AGGRESSIVE if coin < p else PASSIVE
    return play_with(dealt, choose)


def par(dealt: Deal) -> float:
    """The least a round's choices must be worth to pass: part of the
    way from sound play to the reference below rung twenty, and past it
    more than the reference, by a share of a chip a hand."""
    level = dealt.level
    ref = reference_round(dealt).value
    if level.allow >= 0:
        base = sound_round(dealt).value
        return ref - level.allow * max(0.0, ref - base)
    return ref - level.allow * level.hands


__all__ = ['ADAPTIVE', 'AGGRESSIVE', 'Deal', 'Grade', 'Habits', 'Hand',
           'MANIAC', 'Match', 'Model', 'PASSIVE', 'ROCK', 'Record',
           'SOUND', 'STATION', 'best_choice', 'deal', 'grade', 'kind_at',
           'par', 'play_with', 'reference_move', 'reference_round',
           'sound_round', 'strength']
