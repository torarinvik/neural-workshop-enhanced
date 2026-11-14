# -*- coding: utf-8 -*-
"""Gamble: slot machines whose odds are hidden, drift, and sometimes bite.

A row of machines. Each pull of a lever pays what that machine pays on a
win, or nothing; that is all there is to learn from. A round is a fixed
number of pulls. Its score is not the coins, which luck moves, but what
the pulls were worth: each pull counts what that machine paid *on
average* at that moment. So a lucky streak on a bad machine does not
pass a round and an unlucky one on the best machine does not fail it;
the coins are still shown, and where there is a bankroll they are what
runs out. Which machine is best
has to be found by pulling, and every pull spent finding out is a pull
not spent on the best one: explore or exploit.

The ladder takes that apart one piece at a time:

* more machines, closer together, so finding the best costs more;
* from rung 6 the odds **drift**, so what was learned goes stale and the
  best machine has to be looked for again;
* from rung 10 some machines **bite**: they win more often than the
  others and now and then take a large loss, so the one that feels best
  is not the one that pays best;
* from rung 14 the odds **jump**: the machines swap places at a pull
  nobody announces;
* from rung 18 a pull **costs a coin** and the round starts with a small
  bankroll. Run it dry and the round is lost; and when every machine
  loses on average the right play is to walk away, which **Stop** does.

Everything random is dealt up front: each machine's odds at every pull
and the draw each machine would make at every pull. So the reference
meets exactly what the player would have met had it pulled the same
lever at the same pull, and par is fair.

Par is what the reference won on the identical deal, minus an allowance
that is half the gap between knowing everything and pulling at random at
rung one, nothing at rung twenty-one, and below nothing after: past
rung twenty the reference has to be beaten.

The reference is discounted Thompson sampling: a Beta belief about each
machine's win rate and bite rate, old evidence weighed down when the
odds can move, a sample from each belief, the machine whose sample pays
best. It stops when every machine it has tried enough looks like a loser.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

#: The most machines a rung puts out.
MOST_ARMS = 8


class Grade(NamedTuple):
    rung: int
    arms: int
    pulls: int
    #: How far apart the machines' win rates are spread.
    spread: float
    #: How far a win rate wanders per pull, as a standard deviation.
    drift: float
    #: Machines that bite, and the pulls at which the odds jump.
    biters: int
    jumps: int
    #: What a pull costs, and the bankroll a round starts with (0: none).
    price: int
    bankroll: int
    #: Allowance: positive is a share of the reference's edge over
    #: random pulling given away; negative is a share of the gap from the
    #: reference to knowing the odds demanded on top. See :func:`par`.
    allow: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    arms = min(MOST_ARMS, 2 + (r - 1) // 3)
    return Grade(
        rung=r,
        arms=arms,
        pulls=15 + 5 * arms + r // 2,
        spread=max(0.12, 0.6 - 0.035 * (r - 1)),
        drift=0.0 if r < 6 else min(0.06, 0.015 + 0.004 * (r - 6)),
        biters=0 if r < 10 else min(3, 1 + (r - 10) // 4),
        jumps=0 if r < 14 else min(3, 1 + (r - 14) // 5),
        price=0 if r < 18 else 1,
        bankroll=0 if r < 18 else 30,
        allow=(0.5 * (21 - r) / 20.0 if r <= 20
               else -0.02 * (r - 20)),
    )


class Machine(NamedTuple):
    #: What a win pays, and the bite: how often (per pull) and how much.
    pays: int
    bite_rate: float
    bite: int


class Deal(NamedTuple):
    level: Grade
    machines: Tuple[Machine, ...]
    #: odds[t][a]: machine a's win rate at pull t.
    odds: Tuple[Tuple[float, ...], ...]
    #: draws[t][a]: the uniform draw machine a makes at pull t.
    draws: Tuple[Tuple[float, ...], ...]
    #: Pulls at which the odds jump.
    jumps: Tuple[int, ...]
    #: Seeds the reference's own sampling, so par is a number.
    seed: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if rng is None:
        rng = random.Random(seed)
    level = grade(rung)
    arms = level.arms
    centre = rng.uniform(0.35, 0.55)
    rates = [min(0.9, max(0.05, centre + level.spread
                          * (rng.random() - 0.5))) for _a in range(arms)]
    # One machine is clearly best at the start.
    best = rng.randrange(arms)
    rates[best] = min(0.92, max(rates) + level.spread * 0.25)
    # Where pulls cost, a win pays enough that the best machine is
    # worth pulling and the worst are not.
    pays = [1 if level.price == 0 else rng.choice((2, 3, 4))
            for _a in range(arms)]
    if level.price:
        pays[best] = max(3, pays[best])
    machines = [Machine(pays[a], 0.0, 0) for a in range(arms)]
    # A biter wins more often than the best machine and pays for it: its
    # bite is set so that on average it does worse than the best.
    for a in rng.sample([a for a in range(arms) if a != best],
                        min(level.biters, arms - 1)):
        rates[a] = min(0.95, rates[best] + 0.15)
        bite_rate = rng.uniform(0.05, 0.1)
        excess = rates[a] * pays[a] - rates[best] * pays[best]
        bite = int(excess / bite_rate) + rng.randint(3, 6)
        machines[a] = Machine(pays[a], bite_rate, max(4, bite))
    jumps = tuple(sorted(rng.sample(range(level.pulls // 4,
                                          level.pulls - 3),
                                    level.jumps)))
    odds: List[Tuple[float, ...]] = []
    for t in range(level.pulls):
        if t in jumps:
            # The win rates trade places; each machine keeps its payout
            # and its bite.
            rng.shuffle(rates)
        odds.append(tuple(rates))
        if level.drift:
            rates = [min(0.95, max(0.03, p + rng.gauss(0, level.drift)))
                     for p in rates]
    draws = tuple(tuple(rng.random() for _a in range(arms))
                  for _t in range(level.pulls))
    return Deal(level, tuple(machines), tuple(odds), draws, jumps,
                rng.randrange(1 << 30))


def payout(dealt: Deal, t: int, arm: int) -> int:
    """What pulling *arm* at pull *t* pays: the win, nothing, or the
    bite; less the price of the pull."""
    machine = dealt.machines[arm]
    draw = dealt.draws[t][arm]
    if draw < dealt.odds[t][arm]:
        won = machine.pays
    elif draw > 1.0 - machine.bite_rate:
        won = -machine.bite
    else:
        won = 0
    return won - dealt.level.price


def worth(dealt: Deal, t: int, arm: int) -> float:
    """What pulling *arm* at pull *t* pays on average."""
    machine = dealt.machines[arm]
    return (dealt.odds[t][arm] * machine.pays
            - machine.bite_rate * machine.bite - dealt.level.price)


class Round:
    """One round being played."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        #: (machine, what it paid), one per pull made.
        self.history: List[Tuple[int, int]] = []
        self.stopped = False

    @property
    def t(self) -> int:
        return len(self.history)

    @property
    def total(self) -> int:
        return sum(won for _arm, won in self.history)

    @property
    def pulls_left(self) -> int:
        return 0 if self.stopped else self.level.pulls - self.t

    @property
    def value(self) -> float:
        """What the pulls were worth on average: the score."""
        return sum(worth(self.deal, t, arm)
                   for t, (arm, _won) in enumerate(self.history))

    @property
    def bust(self) -> bool:
        return bool(self.level.bankroll) and \
            self.level.bankroll + self.total <= 0

    @property
    def over(self) -> bool:
        return self.pulls_left <= 0 or self.bust

    def pull(self, arm: int) -> Optional[int]:
        if self.over or not 0 <= arm < self.level.arms:
            return None
        won = payout(self.deal, self.t, arm)
        self.history.append((arm, won))
        return won

    def stop(self) -> bool:
        """Walk away with what is won. Only where pulls cost."""
        if self.over or not self.level.price:
            return False
        self.stopped = True
        return True

    def seen(self, arm: int) -> List[int]:
        return [won for a, won in self.history if a == arm]


# --- the reference -----------------------------------------------------------

class Belief:
    """Discounted Beta beliefs about each machine's win and bite rates."""

    def __init__(self, dealt: Deal) -> None:
        level = dealt.level
        self.deal = dealt
        moving = level.drift or level.jumps
        #: How much a pull's evidence still counts one pull later.
        self.keep = 1.0 if not moving else (0.95 if not level.jumps
                                            else 0.9)
        arms = level.arms
        self.wins = [1.0] * arms
        self.losses = [1.0] * arms
        self.bites = [0.2] * arms
        self.calm = [5.0] * arms
        self.bite_size = [0] * arms
        self.pulled = [0] * arms
        #: Undiscounted: wins, and what was given back, per machine.
        self.won = [0] * arms
        self.spent = [0] * arms
        self.coins = 0

    def saw(self, arm: int, won: int) -> None:
        price = self.deal.level.price
        gross = won + price
        for a in range(len(self.wins)):
            self.wins[a] = 1.0 + (self.wins[a] - 1.0) * self.keep
            self.losses[a] = 1.0 + (self.losses[a] - 1.0) * self.keep
        self.pulled[arm] += 1
        self.coins += won
        self.won[arm] += max(0, gross)
        self.spent[arm] += price + max(0, -gross)
        if gross > 0:
            self.wins[arm] += 1
            self.calm[arm] += 1
        elif gross < 0:
            self.losses[arm] += 1
            self.bites[arm] += 1
            self.bite_size[arm] = max(self.bite_size[arm], -gross)
        else:
            self.losses[arm] += 1
            self.calm[arm] += 1

    def mean(self, arm: int) -> float:
        machine = self.deal.machines[arm]
        win = self.wins[arm] / (self.wins[arm] + self.losses[arm])
        bite = self.bites[arm] / (self.bites[arm] + self.calm[arm])
        return (win * machine.pays - bite * self.bite_size[arm]
                - self.deal.level.price)

    def sample(self, arm: int, rng: random.Random) -> float:
        machine = self.deal.machines[arm]
        win = rng.betavariate(self.wins[arm], self.losses[arm])
        bite = rng.betavariate(self.bites[arm], self.calm[arm])
        return (win * machine.pays - bite * self.bite_size[arm]
                - self.deal.level.price)


def reference_move(belief: Belief, rng: random.Random) -> Optional[int]:
    """The machine to pull, or None to stop: where pulls cost, once
    every machine has paid back less than it took over two pulls or
    more, or once the bankroll is nearly gone."""
    arms = len(belief.wins)
    level = belief.deal.level
    if level.price:
        if level.bankroll + belief.coins <= 3 * level.price:
            return None
        if all(belief.pulled[a] >= 2 and belief.won[a] < belief.spent[a]
               for a in range(arms)):
            return None
    samples = [belief.sample(a, rng) for a in range(arms)]
    return max(range(arms), key=lambda a: samples[a])


def reference_round(dealt: Deal) -> Round:
    play = Round(dealt)
    belief = Belief(dealt)
    rng = random.Random(dealt.seed)
    while not play.over:
        arm = reference_move(belief, rng)
        if arm is None:
            play.stop()
            break
        won = play.pull(arm)
        belief.saw(arm, won)
    return play


def knowing(dealt: Deal) -> float:
    """What a player who knew every machine's odds would win on average
    -- stopping for good, where pulls cost, once nothing pays."""
    level = dealt.level
    best = [max(worth(dealt, t, a) for a in range(level.arms))
            for t in range(level.pulls)]
    if not level.price:
        return sum(best)
    # The best place to stop: the most the rest of the round could add.
    total, peak, running = 0.0, 0.0, 0.0
    for value in best:
        running += value
        peak = max(peak, running)
    total = peak
    return total


def guessing(dealt: Deal) -> float:
    """What pulling at random wins on average."""
    level = dealt.level
    return sum(sum(worth(dealt, t, a) for a in range(level.arms))
               / level.arms for t in range(level.pulls))


def par(dealt: Deal) -> float:
    """The least a round's pulls must be worth to pass.

    Up to rung twenty, part of the way from pulling at random to what
    the reference's pulls were worth: half its edge at rung one, all of
    it at rung twenty-one. Past that, part of the way on from the
    reference to knowing every machine's odds."""
    allow = dealt.level.allow
    ref = reference_round(dealt).value
    if allow >= 0:
        guess = guessing(dealt)
        return ref - allow * max(0.0, ref - guess)
    return ref - allow * max(0.0, knowing(dealt) - ref)


__all__ = ['Belief', 'Deal', 'Grade', 'MOST_ARMS', 'Machine', 'Round',
           'deal', 'grade', 'guessing', 'knowing', 'par', 'payout',
           'reference_move', 'reference_round', 'worth']
