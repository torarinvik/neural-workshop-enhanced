# -*- coding: utf-8 -*-
"""Sonar: find a hidden target by asking good questions, then commit.

Something is hidden on a grid. A *ping* on a cell costs one point and
reports how far the target is from it, in coarse bands. A *dig* claims
a cell: right, and the round is won; wrong, and it costs a penalty and
tells you only that it was not there. The round's cost is pings plus
penalties, and it is scored against what a strong reference player
paid on the very same deal.

Every move is a decision under uncertainty, and the ladder adds the
decisions one at a time:

* **Which question.** A ping that splits the remaining possibilities
  evenly is worth several that confirm what is already known. This is
  the skill almost nothing else in the workshop rewards: choosing the
  most *informative* action rather than the most rewarding one.
* **When to stop asking.** Digging at seventy per cent sure saves pings
  and risks the penalty; the penalty rises with the rung, so the right
  moment to commit moves.
* **Error correction.** From rung five a reading can be off by one
  band. One ping is no longer proof, and a contradiction between two
  is something to resolve rather than ignore.
* **Waiting has a price.** From rung eight the target drifts a step
  now and then with every action taken. Caution that was free becomes
  costly, and the long-run risk of losing the trail trades against the
  short-run risk of a wrong dig.

**The reference is fair because it plays the identical deal.** Noise
and drift are drawn from streams indexed by how many actions have been
taken, never by which actions, so the reference meets the same lie on
its third ping and the same drift after its fifth action that the
player does. It is a Bayesian player — an exact posterior over cells,
greedy on expected information, and a dig rule that weighs the
penalty against the price of another ping — so it is strong but not
optimal, and a player who plans further ahead can beat it.

Nothing here imports pyglet.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: What a ping costs. Everything else is priced in pings.
PING = 1.0

#: The reference ping chooses among this many cells, the best by
#: posterior mass plus a random spread. Enough to find a good split;
#: few enough that the reference plays a round in well under a second.
CANDIDATES = 36

#: On a drifting target, a ping expected to learn less than drift adds
#: plus this many nats has stopped paying, and the reference digs.
STALLED = 0.02


class Grade(NamedTuple):
    rung: int
    side: int
    #: Cells per band of distance. One is the exact distance.
    width: int
    #: Readings past the last band all read as the last band.
    bands: int
    #: Chance a reading is off by one band.
    noise: float
    #: Chance the target steps to a neighbouring cell per action.
    drift: float
    #: Cost of a wrong dig, in pings.
    penalty: float
    #: How much worse than the reference a round may be and still pass;
    #: negative means it has to do better.
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        side=min(24, 4 + r),
        width=1 if r <= 2 else (2 if r <= 6 else 3),
        bands=64 if r <= 2 else (5 if r <= 6 else 4),
        noise=0.0 if r < 5 else min(0.30, 0.05 * (r - 4)),
        drift=0.0 if r < 8 else min(0.45, 0.06 * (r - 7)),
        penalty=float(min(24, 2 + r)),
        # Generous at the bottom, nought by rung twelve, and from rung
        # twenty below nought: the top of the ladder is out-planning the
        # reference, by more at every rung, which has no ceiling.
        slack=(float(max(0, 4 - r // 3)) if r <= 20
               else -0.5 * (r - 20)),
    )


Cell = Tuple[int, int]


def chebyshev(one: Cell, two: Cell) -> int:
    return max(abs(one[0] - two[0]), abs(one[1] - two[1]))


def band(level: Grade, distance: int) -> int:
    return min(distance // level.width, level.bands - 1)


def likelihood(level: Grade, reading: int, true_band: int) -> float:
    """P(reading | the band it should have read)."""
    if level.noise <= 0:
        return 1.0 if reading == true_band else 0.0
    neighbours = [b for b in (true_band - 1, true_band + 1)
                  if 0 <= b < level.bands]
    if reading == true_band:
        return 1.0 - level.noise if neighbours else 1.0
    if reading in neighbours:
        return level.noise / len(neighbours)
    return 0.0


class Deal(NamedTuple):
    """One round: where the target starts and the dice it will meet.

    ``path[k]`` is where the target is after *k* actions; ``lies[k]`` is
    the noise draw the *k*-th action's reading meets: nought for a true
    reading, -1 or +1 for one band off.
    """

    level: Grade
    path: Tuple[Cell, ...]
    lies: Tuple[int, ...]
    #: Actions allowed before the round is lost.
    budget: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    rng = rng or random.Random(seed)
    level = grade(rung)
    side = level.side
    budget = side * side + 10
    at = (rng.randrange(side), rng.randrange(side))
    path = [at]
    for _step in range(budget + 1):
        if level.drift and rng.random() < level.drift:
            x, y = at
            options = [(x + dx, y + dy) for dx, dy in
                       ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if 0 <= x + dx < side and 0 <= y + dy < side]
            at = rng.choice(options)
        path.append(at)
    lies = tuple((rng.choice((-1, 1)) if rng.random() < level.noise else 0)
                 for _ in range(budget + 1))
    return Deal(level, tuple(path), lies, budget)


class Round:
    """The state of one round, for the player or the reference alike."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        self.actions = 0
        self.pings: List[Tuple[Cell, int]] = []
        self.misses: List[Cell] = []
        #: 'ping' or 'dig' for each action taken, in order.
        self.log: List[str] = []
        self.cost = 0.0
        self.found = False
        self.over = False

    @property
    def target(self) -> Cell:
        return self.deal.path[min(self.actions, len(self.deal.path) - 1)]

    def ping(self, cell: Cell) -> Optional[int]:
        if self.over:
            return None
        true = band(self.level, chebyshev(cell, self.target))
        lie = self.deal.lies[min(self.actions, len(self.deal.lies) - 1)]
        reading = min(self.level.bands - 1, max(0, true + lie))
        self.pings.append((cell, reading))
        self.log.append('ping')
        self.cost += PING
        self._advance()
        return reading

    def dig(self, cell: Cell) -> bool:
        if self.over:
            return False
        if cell == self.target:
            self.found = True
            self.over = True
            return True
        self.misses.append(cell)
        self.log.append('dig')
        self.cost += self.level.penalty
        self._advance()
        return False

    def _advance(self) -> None:
        self.actions += 1
        if self.actions >= self.deal.budget:
            self.over = True


# --- the reference -----------------------------------------------------------

class Belief:
    """An exact posterior over where the target is now."""

    def __init__(self, level: Grade) -> None:
        self.level = level
        side = level.side
        self.cells = [(x, y) for y in range(side) for x in range(side)]
        self.p: Dict[Cell, float] = {c: 1.0 / len(self.cells)
                                     for c in self.cells}

    def _normalise(self) -> None:
        total = sum(self.p.values())
        if total <= 0:
            # Every hypothesis ruled out can only mean a reading was
            # misread as impossible; start again rather than divide by
            # nought.
            self.p = {c: 1.0 / len(self.cells) for c in self.cells}
            return
        self.p = {c: v / total for c, v in self.p.items() if v > 0}

    def drift(self) -> None:
        """The target may have stepped since the last action."""
        q = self.level.drift
        if not q:
            return
        side = self.level.side
        moved: Dict[Cell, float] = {}
        for (x, y), mass in self.p.items():
            moved[(x, y)] = moved.get((x, y), 0.0) + mass * (1 - q)
            options = [(x + dx, y + dy) for dx, dy in
                       ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if 0 <= x + dx < side and 0 <= y + dy < side]
            for other in options:
                moved[other] = moved.get(other, 0.0) + mass * q / len(options)
        self.p = moved

    def heard(self, cell: Cell, reading: int) -> None:
        for where in list(self.p):
            self.p[where] *= likelihood(
                self.level, reading, band(self.level, chebyshev(cell, where)))
        self._normalise()
        self.drift()

    def missed(self, cell: Cell) -> None:
        self.p.pop(cell, None)
        self._normalise()
        self.drift()

    def entropy(self) -> float:
        return -sum(v * math.log(v) for v in self.p.values() if v > 0)

    def spread(self) -> float:
        """Entropy one drift step adds to the posterior as it stands."""
        if not self.level.drift:
            return 0.0
        before = self.entropy()
        saved = self.p
        self.drift()
        after = self.entropy()
        self.p = saved
        return max(0.0, after - before)

    def best(self) -> Tuple[Cell, float]:
        cell = max(self.p, key=lambda c: (self.p[c], c))
        return cell, self.p[cell]

    def expected_entropy(self, probe: Cell) -> float:
        return self.outlook(probe)[0]

    def outlook(self, probe: Cell) -> Tuple[float, float]:
        """What pinging *probe* is expected to leave: the posterior's
        entropy, and how sure of the likeliest cell it will be."""
        bands = self.level.bands
        z = [0.0] * bands
        zlogz = [0.0] * bands
        peak = [0.0] * bands
        for where, mass in self.p.items():
            true = band(self.level, chebyshev(probe, where))
            for reading in (true - 1, true, true + 1):
                if not 0 <= reading < bands:
                    continue
                weight = mass * likelihood(self.level, reading, true)
                if weight > 0:
                    z[reading] += weight
                    zlogz[reading] += weight * math.log(weight)
                    if weight > peak[reading]:
                        peak[reading] = weight
        total = 0.0
        for zr, zl in zip(z, zlogz):
            if zr > 0:
                total += zr * math.log(zr) - zl
        # E[max posterior] = sum over readings of P(r) * max_c P(c|r),
        # and P(r) * P(c|r) is the joint weight, so it is the sum of
        # each reading's largest weight.
        return total, sum(peak)


def reference_move(belief: Belief, rng: random.Random
                   ) -> Tuple[str, Cell]:
    """('dig' or 'ping', cell): the reference's next action.

    It picks the ping that leaves the least expected entropy, and digs
    the likeliest cell instead when the expected penalty of a dig —
    ``1 - sure`` of it — is no more than about a ping. On a still
    target that is the whole rule: information only accumulates, so
    certainty gets there.

    A drifting target never gets there. Every action adds the entropy
    the drift spreads, and once the best ping is expected to learn no
    more than that, pinging is treading water; the reference digs its
    best guess instead. Comparing certainty rather than information
    there misfires on coarse bands, where a ping near the target
    halves the candidates without raising any one of them much.
    """
    cell, sure = belief.best()
    if sure >= 0.999:
        return 'dig', cell
    ranked = sorted(belief.p, key=lambda c: -belief.p[c])
    pool = set(ranked[:CANDIDATES // 2])
    every = belief.cells
    while len(pool) < min(CANDIDATES, len(every)):
        pool.add(every[rng.randrange(len(every))])
    scored = {c: belief.outlook(c) for c in sorted(pool)}
    probe = min(scored, key=lambda c: scored[c][0])
    if (1.0 - sure) * belief.level.penalty <= PING * 1.2:
        return 'dig', cell
    if belief.level.drift:
        gain = belief.entropy() - scored[probe][0]
        if gain <= belief.spread() + STALLED:
            return 'dig', cell
    return 'ping', probe


def reference_cost(dealt: Deal, seed: int = 0) -> Tuple[float, bool]:
    """What the reference paid on *dealt*, and whether it found it."""
    rng = random.Random(seed)
    play = Round(dealt)
    belief = Belief(dealt.level)
    while not play.over:
        kind, cell = reference_move(belief, rng)
        if kind == 'dig':
            if not play.dig(cell):
                belief.missed(cell)
        else:
            reading = play.ping(cell)
            belief.heard(cell, reading)
    return play.cost, play.found


def par(dealt: Deal) -> float:
    """The cost a round must come in at or under to pass."""
    cost, found = reference_cost(dealt)
    if not found:
        cost = float(dealt.budget) * PING
    return cost + dealt.level.slack


__all__ = ['Belief', 'Deal', 'Grade', 'PING', 'Round', 'band', 'chebyshev',
           'deal', 'grade', 'likelihood', 'par', 'reference_cost',
           'reference_move']
