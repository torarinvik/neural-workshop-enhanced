# -*- coding: utf-8 -*-
"""Hidden Rule: find out what lights the lamp, then prove you know.

A lamp lights for some objects and stays dark for others, by a rule
nobody states. An object is a handful of properties -- a colour, a
shape, a size and so on -- and the player may put any object under the
lamp to see what it does. Each *test* costs a point. When the player
thinks they have the rule they sit an *exam*: objects are shown one at
a time and each must be called, lit or dark, with no lamp to check
against and nothing said until the last one. Every wrong call costs
the rung's penalty. The round's cost is tests plus penalties, and it
is scored against what a reference player paid on the very same deal.

Matrix Reasoning asks which of eight pictures finishes a pattern. This
asks the three things that leaves out.

* **Forming the hypotheses.** Two free examples open the notebook, one
  that lights the lamp and one that does not, and a dozen rules fit
  them. Nobody lists the candidates; seeing that "blue" and "round"
  and "blue and round" are all still standing is the player's work.
* **Choosing the experiment.** A test that every surviving hypothesis
  agrees about tells nothing whichever way it comes out. The test
  worth a point is the one they disagree about, and the best is the
  one that splits them in half. People are bad at this in a specific
  way -- they test what they expect to light the lamp -- and a rule
  like "blue or round" is only ever found by testing something that
  should not.
* **Knowing when you know.** The exam is on objects not seen before,
  so it measures the rule and not the notebook. Sit it too early and
  the penalties cost more than the tests saved; too late and the tests
  cost more than the penalties avoided.

The ladder widens the world and deepens the rules one step at a time:
more properties, more values of each, then negation, two conditions
that must both hold, either of two, exactly one of two, three at once,
and mixtures. From rung twelve the lamp itself is unreliable -- a test
now and then reports the opposite -- so one test is no longer proof
and a contradiction in the notebook has to be weighed, not believed.

**The reference is fair because it plays the identical deal.** Which
tests the lamp lies on is fixed by how many tests have been made, not
by what was tested, so the reference's fifth test meets the same lie
the player's fifth does, and the exam is the same objects in the same
order. It is a Bayesian experimenter: every rule the rung allows,
weighted by how many readings it contradicts; the test the weighted
rules are most evenly split on; the exam once what it still expects
to lose there is worth less than a test. That is strong but not
optimal -- it looks one test ahead and it never plans two that only
pay together -- and past rung twenty the round has to cost less than
it paid, by more at every rung.

Nothing here imports pyglet.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import itertools
import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

#: What a test costs. Everything else is priced in tests.
TEST = 1.0

#: The reference sits the exam once what it expects to lose there is
#: no more than this many tests.
ENOUGH = 1.0

#: The properties an object can have, in the order rungs bring them in,
#: and the most values each can take.
FEATURES = ('colour', 'shape', 'size', 'count', 'fill', 'bar')
MOST_VALUES = (4, 4, 2, 3, 2, 2)

#: Every form a rule can take, simplest first. Where two forms pick out
#: the same objects the simpler one is the rule.
FORMS = ('is', 'both', 'either', 'one_of', 'all', 'any', 'two_of',
         'both_or', 'either_and')

#: Tests a round allows: what the notebook holds.
BUDGET = 48

#: The most the lamp ever lies.
NOISIEST = 0.10

#: A reading that contradicts a rule multiplies the rule's weight by
#: the odds of a lie. Rules this many times less likely than one that
#: contradicts nothing are dropped.
NEGLIGIBLE = 1e-6


class Grade(NamedTuple):
    rung: int
    #: How many values each property in play can take.
    values: Tuple[int, ...]
    #: The forms a rule may take.
    forms: Tuple[str, ...]
    #: 0: every condition is "is"; 1: a rule of one condition may be
    #: "is not"; 2: any condition may be.
    nots: int
    #: Chance the lamp reports the opposite on a test.
    noise: float
    #: Questions in the exam, half of them lit.
    exam: int
    #: Cost of a wrong answer, in tests.
    penalty: float
    #: Tests allowed: what the notebook holds.
    budget: int
    #: Par is the reference's cost times :attr:`factor`, plus this.
    slack: float
    factor: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    features = (2 if r <= 2 else 3 if r <= 5 else 4 if r <= 9
                else 5 if r <= 14 else 6)
    wide = 2 if r <= 3 else 3 if r <= 7 else 4
    counts = 2 if r <= 11 else 3
    forms = ['is']
    if r >= 6:
        forms.append('both')
    if r >= 8:
        forms.append('either')
    if r >= 10:
        forms.append('one_of')
    if r >= 13:
        forms += ['all', 'any']
    if r >= 16:
        forms += ['two_of', 'both_or', 'either_and']
    return Grade(
        rung=r,
        values=(wide, wide, 2, counts, 2, 2)[:features],
        forms=tuple(forms),
        nots=0 if r < 4 else (1 if r < 19 else 2),
        noise=0.0 if r < 12 else min(NOISIEST, 0.02 * (r - 11)),
        exam=6 if r <= 4 else (8 if r <= 11 else 10),
        penalty=float(min(24, 3 + r)),
        budget=BUDGET,
        # Twice the reference's cost and a spare test at the bottom,
        # where its cost is too small for a share of it to be anything;
        # the reference's cost and nothing more from rung twelve; less
        # than it past rung twenty. The allowance is always worth less
        # than one wrong answer, so it buys spare tests and never a
        # guess.
        slack=1.0 if r < 12 else 0.0,
        factor=(max(1.0, 2.0 - (r - 1) / 11.0) if r <= 20
                else 1.0 / (1.0 + 0.04 * (r - 20))),
    )


# --- rules -------------------------------------------------------------------

#: (property, value, whether the object must have it or must not).
Atom = Tuple[int, int, bool]

#: An object: one value index for each property in play.
Item = Tuple[int, ...]


class Rule(NamedTuple):
    form: str
    atoms: Tuple[Atom, ...]
    #: Bit *i* is set if object *i* of the rung's universe lights the lamp.
    mask: int


class Space(NamedTuple):
    """Every object and every rule a rung allows."""

    items: Tuple[Item, ...]
    rules: Tuple[Rule, ...]
    #: For each object, the rules that light for it, as bits over
    #: :attr:`rules`. Kept this way round because what the reference
    #: asks, over and over, is how many surviving rules light for an
    #: object, and that is one AND and a count of bits.
    lights: Tuple[int, ...]
    #: Every rule.
    everyone: int


def _combine(form: str, masks: Sequence[int]) -> int:
    if form == 'is':
        return masks[0]
    if form == 'both':
        return masks[0] & masks[1]
    if form == 'either':
        return masks[0] | masks[1]
    if form == 'one_of':
        return masks[0] ^ masks[1]
    a, b, c = masks
    if form == 'all':
        return a & b & c
    if form == 'any':
        return a | b | c
    if form == 'two_of':
        return (a & b) | (a & c) | (b & c)
    if form == 'both_or':
        return (a & b) | c
    if form == 'either_and':
        return (a | b) & c
    raise ValueError(form)


@functools.lru_cache(maxsize=64)
def _space(values: Tuple[int, ...], forms: Tuple[str, ...],
           nots: int) -> Space:
    items = tuple(itertools.product(*(range(v) for v in values)))
    full = (1 << len(items)) - 1
    is_mask = {}
    for feature, count in enumerate(values):
        for value in range(count):
            mask = 0
            for index, item in enumerate(items):
                if item[feature] == value:
                    mask |= 1 << index
            is_mask[(feature, value)] = mask
    plain: List[Atom] = [(f, v, True) for (f, v) in sorted(is_mask)]
    # "Not blue" among two colours is "orange": only a property with
    # three values or more has a negation worth the name.
    negated: List[Atom] = [(f, v, False) for (f, v) in sorted(is_mask)
                           if values[f] >= 3]

    def mask_of(atom: Atom) -> int:
        feature, value, positive = atom
        mask = is_mask[(feature, value)]
        return mask if positive else full & ~mask

    rules: List[Rule] = []
    seen = set()

    def add(form: str, atoms: Tuple[Atom, ...]) -> None:
        mask = _combine(form, [mask_of(atom) for atom in atoms])
        if mask in (0, full) or mask in seen:
            return
        seen.add(mask)
        rules.append(Rule(form, atoms, mask))

    for form in FORMS:
        if form not in forms:
            continue
        if form == 'is':
            for atom in plain + (negated if nots >= 1 else []):
                add(form, (atom,))
        elif form in ('both', 'either', 'one_of'):
            pool = plain + (negated if nots >= 2 else [])
            for pair in itertools.combinations(pool, 2):
                add(form, pair)
        elif form in ('all', 'any', 'two_of'):
            for triple in itertools.combinations(plain, 3):
                add(form, triple)
        else:
            # (a and b) or c, (a or b) and c: which of the three stands
            # alone matters, so each triple gives three rules.
            for a, b, c in itertools.combinations(plain, 3):
                add(form, (a, b, c))
                add(form, (a, c, b))
                add(form, (b, c, a))

    # Turn the table on its side: one string of bits per rule, read
    # down the columns, is one string of bits per object.
    width = len(items)
    rows = [format(rule.mask, '0%db' % width) for rule in rules]
    lights = [0] * width
    for column, bits in enumerate(zip(*rows)):
        lights[width - 1 - column] = int(''.join(reversed(bits)), 2)
    return Space(items, tuple(rules), tuple(lights), (1 << len(rules)) - 1)


def space(level: Grade) -> Space:
    return _space(level.values, level.forms, level.nots)


def lit(rule: Rule, index: int) -> bool:
    """Whether object *index* lights the lamp under *rule*."""
    return bool((rule.mask >> index) & 1)


# --- a round -----------------------------------------------------------------

class Deal(NamedTuple):
    """One round: the rule, and everything the player will meet.

    ``lies[k]`` is whether the lamp reports the opposite on the *k*-th
    test, whatever is tested; ``exam`` is the objects asked, in order.
    """

    level: Grade
    rule: Rule
    #: The free examples, (object, lit): one of each, and never a lie.
    seeds: Tuple[Tuple[int, bool], ...]
    lies: Tuple[bool, ...]
    exam: Tuple[int, ...]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    rng = rng or random.Random(seed)
    level = grade(rung)
    world = space(level)
    rule = world.rules[rng.randrange(len(world.rules))]
    bright = [i for i in range(len(world.items)) if lit(rule, i)]
    dark = [i for i in range(len(world.items)) if not lit(rule, i)]
    seeds = ((bright[rng.randrange(len(bright))], True),
             (dark[rng.randrange(len(dark))], False))
    lies = tuple(rng.random() < level.noise for _ in range(level.budget))

    def draw(pool: List[int], count: int) -> List[int]:
        # Without repeats while the pool lasts: a rule that lights for
        # two objects still has to fill half an exam.
        picked: List[int] = []
        while len(picked) < count:
            round_ = list(pool)
            rng.shuffle(round_)
            picked += round_[:count - len(picked)]
        return picked

    half = level.exam // 2
    exam = draw(bright, half) + draw(dark, level.exam - half)
    rng.shuffle(exam)
    return Deal(level, rule, seeds, lies, tuple(exam))


class Round:
    """The state of one round, for the player or the reference alike."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        #: (object, what the lamp showed) for each test, in order.
        self.tests: List[Tuple[int, bool]] = []
        #: What was called for each exam question answered so far.
        self.answers: List[bool] = []
        self.examining = False
        self.over = False

    @property
    def tests_left(self) -> int:
        return self.level.budget - len(self.tests)

    def test(self, index: int) -> Optional[bool]:
        """Put object *index* under the lamp. None if it cannot be."""
        if self.examining or self.over or self.tests_left <= 0:
            return None
        if not 0 <= index < len(space(self.level).items):
            return None
        shown = lit(self.deal.rule, index) != self.deal.lies[len(self.tests)]
        self.tests.append((index, shown))
        return shown

    def start_exam(self) -> bool:
        if self.examining or self.over:
            return False
        self.examining = True
        return True

    @property
    def question(self) -> Optional[int]:
        """The object being asked about, once the exam has started."""
        if not self.examining or self.over:
            return None
        return self.deal.exam[len(self.answers)]

    def answer(self, call: bool) -> bool:
        """Call the object in question lit or dark. Nothing is said."""
        if self.question is None:
            return False
        self.answers.append(bool(call))
        if len(self.answers) >= len(self.deal.exam):
            self.over = True
        return True

    @property
    def wrong(self) -> int:
        return sum(1 for index, call in zip(self.deal.exam, self.answers)
                   if call != lit(self.deal.rule, index))

    @property
    def cost(self) -> float:
        return len(self.tests) * TEST + self.wrong * self.level.penalty


# --- the reference -----------------------------------------------------------

class Belief:
    """An exact posterior over the rung's rules.

    A lamp that never lies makes this a list of the rules still
    standing. One that lies makes it a list of such lists, by how many
    readings each rule contradicts: every rule in a list has the same
    weight, the odds of a lie raised to that count, so the posterior
    never has to be held rule by rule.
    """

    def __init__(self, level: Grade,
                 seeds: Sequence[Tuple[int, bool]] = ()) -> None:
        self.level = level
        self.space = space(level)
        self.odds = (level.noise / (1.0 - level.noise)
                     if level.noise else 0.0)
        self.deepest = 0
        if self.odds:
            while self.odds ** (self.deepest + 1) >= NEGLIGIBLE:
                self.deepest += 1
        self.known = self.space.everyone
        for index, shown in seeds:
            self.known &= self._agreeing(index, shown)
        #: ``tiers[c]``: the rules that contradict exactly *c* readings.
        self.tiers: List[int] = [self.known]

    def _agreeing(self, index: int, shown: bool) -> int:
        lights = self.space.lights[index]
        return lights if shown else self.space.everyone & ~lights

    def saw(self, index: int, shown: bool) -> None:
        """Take in a reading, which on a noisy rung may be a lie."""
        agree = self._agreeing(index, shown)
        moved = [tier & ~agree for tier in self.tiers]
        tiers = [tier & agree for tier in self.tiers] + [0]
        for count, tier in enumerate(moved):
            tiers[count + 1] |= tier
        tiers = tiers[:self.deepest + 1]
        while len(tiers) > 1 and not tiers[-1]:
            tiers.pop()
        if not any(tiers):
            # Every rule ruled out: more lies than the tiers were kept
            # for. Start again from what is known for certain rather
            # than divide by nought.
            tiers = [self.known]
        self.tiers = tiers

    def _weights(self) -> List[float]:
        return [self.odds ** count if count else 1.0
                for count in range(len(self.tiers))]

    def chances(self) -> List[float]:
        """For every object, the chance it lights the lamp."""
        weights = self._weights()
        total = sum(weight * tier.bit_count()
                    for weight, tier in zip(weights, self.tiers))
        return [sum(weight * (tier & lights).bit_count()
                    for weight, tier in zip(weights, self.tiers)) / total
                for lights in self.space.lights]

    def chance(self, index: int) -> float:
        return self.chances()[index]

    def standing(self) -> int:
        """How many rules contradict nothing seen so far."""
        return self.tiers[0].bit_count()


def exam_doubt(chances: Sequence[float]) -> float:
    """The share of exam answers expected wrong, calling each object
    the way it more likely is.

    The exam is half lit objects and half dark ones, so the two halves
    are weighed separately: a rule that lights for one object in fifty
    would otherwise look nearly known to someone who had learned
    nothing but "mostly dark".
    """
    bright = sum(chances)
    dark = len(chances) - bright
    missed = sum(q for q in chances if q < 0.5)
    false = sum(1.0 - q for q in chances if q >= 0.5)
    doubt = 0.0
    if bright > 0:
        doubt += 0.5 * missed / bright
    if dark > 0:
        doubt += 0.5 * false / dark
    return doubt


def reference_move(belief: Belief, tests_left: int) -> Optional[int]:
    """The object the reference tests next, or None to sit the exam.

    It tests the object its rules are most evenly split on, weighted
    by how well each has stood up, which is the test that settles the
    most whichever way it comes out. It stops when what it expects to
    lose in the exam is worth no more than a test, when no object is
    left that its rules disagree about, or when the notebook is full.
    """
    if tests_left <= 0:
        return None
    level = belief.level
    chances = belief.chances()
    if level.exam * level.penalty * exam_doubt(chances) <= TEST * ENOUGH:
        return None
    best = min(range(len(chances)),
               key=lambda index: (abs(chances[index] - 0.5), index))
    if abs(chances[best] - 0.5) >= 0.5 - 1e-12:
        return None
    return best


def reference_round(dealt: Deal) -> Round:
    """The reference's whole round on *dealt*."""
    play = Round(dealt)
    belief = Belief(dealt.level, dealt.seeds)
    while True:
        index = reference_move(belief, play.tests_left)
        if index is None:
            break
        belief.saw(index, play.test(index))
    play.start_exam()
    chances = belief.chances()
    while not play.over:
        play.answer(chances[play.question] >= 0.5)
    return play


def par(dealt: Deal) -> float:
    """The cost a round must come in at or under to pass."""
    level = dealt.level
    return reference_round(dealt).cost * level.factor + level.slack


__all__ = ['Atom', 'Belief', 'Deal', 'FEATURES', 'FORMS', 'Grade', 'Item',
           'MOST_VALUES', 'Round', 'Rule', 'Space', 'TEST', 'deal',
           'exam_doubt', 'grade', 'lit', 'par', 'reference_move',
           'reference_round', 'space']
