# -*- coding: utf-8 -*-
"""What follows from the premises — and how much of it can be faked.

Between two and thirteen lines go up on the screen, all of them about
things named after ordinary English nouns, and one question about two
of those things. The answer is whatever the lines force, and *cannot
be told* is an answer as often as any other, because a set of premises
that pins everything down is not a set of premises anybody has to
reason about.

The names come from the word index the crossword and the Scrabble
rack are built on, and are made up instead where that has not been
fetched. **A real word carries a belief**, which is worth stating as
a cost rather than waving away: the place it could be spent is the
categorical rungs, where two nouns picked at random really are
strangers to each other, and a player who answers from the world
rather than from the page answers *none* every time. Measured, that
reader gets 0.11 and 0.17 against guessing floors of 0.20 — believing
the premises is not a way round these rungs but a way of doing worse
than a coin, because the deal picks its answer before it picks the
premises that give it.

The families are relational-reasoning paradigms rather than
inventions: transitive inference over an order, parity over a
same/opposite chain, vector composition on a grid, categorical
syllogisms, and truth-functional composition over the lot. The shape
of the ladder — a mixed drill that climbs — is the one
Syllogimous v3 popularised; none of its code or wording is here, and
could not be: it is CC BY-NC and this is GPL.

**The answer space is tiny and the derivation is long, so counting
candidates measures almost nothing here.** Ten of the twelve rungs
offer three answers. That is the opposite of Algebra, where the space
is the whole difficulty, and it is why this task is measured by three
baselines that know nothing instead:

*guess* is one over the number of options. *constant* is what the
single best fixed answer gets — the column that says whether "cannot
be told" is really an option or a decoration. *surface* is a reader
that never puts two premises together: it finds the one line that
names the thing being asked about and answers with that line's
relation; on the categorical rungs it is the atmosphere effect
instead — negative premise, negative conclusion. A rung that
*surface* beats chance on is a rung that can be answered without
reasoning, whatever it looks like.

Against those sit two columns about the work: *steps*, how many
premises have to be composed, and *decoys*, how many are printed that
need not have been read at all.

Two conventions are stated on the screen because they are choices
rather than facts. There are no ties in the order family, so "is not
more than" means "is less than" and nothing else — which is why
negation is offered in the two families where it has exactly one
reading, and not in the direction families, where "is not north of"
means any of seven other things. And a direction names which sides a
thing is on rather than an angle: north-east means north of it and
east of it, one square at a time.

The categorical rungs read *at least one* rather than *some*, which
kills the conversational implicature that some means not all. Under
the Boolean reading used here, "every X is a Y" does not say there are
any X.

Measured over 400 deals a rung by ``tests/bench_syllogism.py``, which
is a proportion good to about ±0.03:

===== ================================ ==== ===== ===== ===== ======= =====
rung  what it asks                     ans  lines guess const surface steps
===== ================================ ==== ===== ===== ===== ======= =====
1     same or opposite                    3   5.0  0.33  0.35    0.34   3.8
2     more and less                       3   5.0  0.33  0.34    0.34   3.1
3     a gap in the chain                  3   7.0  0.33  0.36    0.32   4.4
4     not more than                       3   7.0  0.33  0.34    0.34   3.8
5     all and at least one                5   2.0  0.20  0.52    0.48   2.0
6     which way from here                 9   4.0  0.11  0.12    0.09   2.8
7     nine lines, and two that matter     3   9.0  0.33  0.34    0.35   4.6
8     three at once                       5   3.0  0.20  0.28    0.42   2.4
9     up and down as well                27   5.0  0.04  0.06    0.05   3.1
10    the same kind of thing              3   8.0  0.33  0.36    0.32   7.5
11    two questions, one answer           3   8.9  0.33  0.38    0.42   6.5
12    three questions, one answer         3  12.9  0.33  0.34    0.36  10.4
===== ================================ ==== ===== ===== ===== ======= =====

The two categorical rungs are the rows that do not sit at chance, and
it is not a defect in the deal: **the classical rules are the
atmosphere reader.** A valid conclusion is negative exactly when a
premise is and particular exactly when a premise is, so on a
two-premise syllogism atmosphere names the right form whenever
anything follows at all — measured at 192 of 192. The four forms are
one answer between them there, and the only question left is whether
anything follows, so rung five is dealt as the coin it is and both
baselines sit at one half. Rung eight blunts it by asking about a
pair with a premise off the path between them: atmosphere counts that
premise's quality and should not, and it falls to 0.58 of the deals
where something follows, which is 0.42 of all of them.

Rung eleven is the third row over its floor, at 0.42 against 0.33,
and the cause is the connectives rather than the premises: ``or``
with one true half is true whatever the other half was misread as,
so a reader that gets one claim right absorbs being wrong about the
next. Choosing the connective along with the claims took it from
0.57 to here; the rest is what a two-valued join gives away for free.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
import re
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: The answer offered by every family, and the reason the premises are
#: allowed to fall apart into pieces.
UNTOLD = 'cannot be told'

#: The families, named for the algebra underneath rather than the
#: words on top. Before/after and more/less are one family in two
#: costumes, and saying so is cheaper than measuring it twice.
PARITY = 'parity'
ORDER = 'order'
PLANE = 'plane'
SPACE = 'space'
CATEGORICAL = 'categorical'
META = 'meta'
BINARY = 'binary'

#: How many axes each direction family walks on.
AXES = {PLANE: 2, SPACE: 3}

#: Which way each axis points, positive first.
COMPASS = (('north', 'south'), ('east', 'west'), ('above', 'below'))


# --- the words ------------------------------------------------------------
#
# The things reasoned about are named after ordinary English nouns,
# drawn from the word index the crossword and the Scrabble rack are
# built on. Which nouns is decided by :func:`neural_workshop.wordlist.
# nouns`, and the band is a common one on purpose: the difficulty is
# meant to be in putting the premises together, not in the vocabulary.
#
# The belief a real word carries is priced at the top of this file:
# the reader it buys answers *none* on the categorical rungs and does
# worse than guessing. What it costs nowhere is the rest of the
# ladder, and that is measured too — ``either_way`` in the bench deals
# every rung twice, once with real names and once with made-up ones,
# and the two columns agree. They have to: the logic never reads the
# names. The one channel by which they could have mattered is the
# read-back, which throws a deal away if the printed lines do not
# parse, and no deal is thrown away either way.
#
# With no index fetched there is nothing to draw from — the seed list
# is function words — so the names are made up instead, by
# :func:`nonsense`, which is the same task with the belief removed.

ONSETS = ('b', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r',
          's', 't', 'v', 'z')
NUCLEI = ('a', 'e', 'i', 'o', 'u', 'ai', 'ee', 'oo')
CODAS = ('', 'l', 'm', 'n', 'r', 's', 'k', 'p', 't', 'v', 'sk', 'st', 'nd')

_REAL: Optional[frozenset] = None


def _real_words() -> frozenset:
    """Common English words, so a made-up one never turns out to be one.

    Only common ones, and only for the fallback: where the names are
    invented they should be inventions all the way, and a rare word
    that ``bavir`` happened to collide with would carry no belief to
    bias with anyway.
    """
    global _REAL
    if _REAL is None:
        try:
            from .wordlist import SEED_WORDS
            _REAL = frozenset(' '.join(SEED_WORDS).split())
        except Exception:                        # pragma: no cover
            _REAL = frozenset()
    return _REAL


def nonsense(rng: random.Random, count: int) -> Tuple[str, ...]:
    """*count* made-up words, no two of them opening alike.

    Distinct first two letters on purpose. The difficulty is meant to
    be in putting the premises together, not in telling ``vartok``
    from ``vartop`` at a glance.
    """
    if count > 40:
        raise ValueError('%d is more things than a question needs' % count)
    real, used, got = _real_words(), set(), []
    for _try in range(400 * count):
        if len(got) >= count:
            break
        word = rng.choice(ONSETS) + rng.choice(NUCLEI) + rng.choice(CODAS)
        head = word[:2]
        if head in used:
            continue
        if rng.random() < 0.55:
            word += (rng.choice(ONSETS) + rng.choice(NUCLEI)
                     + rng.choice(CODAS))
        if not 4 <= len(word) <= 8 or word in real:
            continue
        used.add(head)
        got.append(word)
    if len(got) < count:                         # pragma: no cover
        raise RuntimeError('could not name %d things' % count)
    return tuple(got)


#: Every word this task prints that is not the name of a thing, so
#: that nothing is ever named after one. "north is north of south" is
#: a line that reads as grammar rather than as a premise, and it is
#: not the reader's job to work out which "north" is which.
#:
#: Taken off the page rather than off the source: the test that guards
#: it deals every rung, tokenises everything printed, and asks that
#: what is left after the names are removed is exactly this set. A
#: frame that gains a word gains it here too, or the test says so.
GRAMMAR = frozenset(
    'a an about above all and are as at be below cannot different east '
    'every exactly false follows from in is it least less links more no '
    'none north not nothing of one opposite or other place premises '
    'same so south stands still than the this three to told true two '
    'way west what when which whole'.split())

#: And a margin, of words that do not appear on the page today but
#: would read as grammar if a name landed on one.
NEARLY = frozenset(
    'after any before both down each either kind left line neither '
    'right some thing under up yes'.split())

_POOL: Optional[Tuple[str, ...]] = None


def _pool() -> Tuple[str, ...]:
    """The nouns a deal may name things after, or empty if there are none.

    Kept, because building it reads the index and the frequency list:
    0.28 s once, against 0.1 ms for a deal. That is the whole of this
    task's start-up cost and it is paid on the first question rather
    than at import, so a machine that never opens Syllogisms never
    pays it.
    """
    global _POOL
    if _POOL is None:
        try:
            from .wordlist import nouns
            _POOL = tuple(one.word for one in nouns().entries
                          if one.word not in GRAMMAR
                          and one.word not in NEARLY)
        except Exception:                        # pragma: no cover
            _POOL = ()
    return _POOL


def forget() -> None:
    """Drop the cached name pool, for a test that changes what is on disk."""
    global _POOL
    _POOL = None


def real_names() -> bool:
    """Whether this machine has words to name things after.

    It has them or it has nothing: the noun pool comes from the
    fetched index, and without that there is no half-way state.
    """
    return bool(_pool())


def things(rng: random.Random, count: int) -> Tuple[str, ...]:
    """*count* things to reason about, no two of them opening alike.

    Real words where the machine has them and made-up ones where it
    does not, and the same rule either way: distinct first two
    letters, because telling ``carpet`` from ``carpel`` at a glance is
    not the skill this task is for.

    The pool has to be forty times what the question needs before it
    is drawn from at all, so that rule never turns into a search.
    Eighteen names out of four thousand words is not a constraint;
    eighteen out of thirty would be, and a thin pool is a sign that
    something is wrong with the index rather than an occasion to
    struggle on.
    """
    found = _pool()
    if len(found) < 40 * count:
        return nonsense(rng, count)
    used, got = set(), []
    for _try in range(400 * count):
        if len(got) >= count:
            break
        word = found[rng.randrange(len(found))]
        if word[:2] in used:
            continue
        used.add(word[:2])
        got.append(word)
    if len(got) < count:                         # pragma: no cover
        return nonsense(rng, count)
    return tuple(got)


# --- what a rung is -------------------------------------------------------


class Grade(NamedTuple):
    """One rung: which algebra, how much of it, and what is hidden."""

    name: str
    family: str
    #: How many named things the premises are about. A family made of
    #: other families ignores this and sizes its parts instead.
    items: int = 4
    #: Premises beyond the ones that hold the web together. A
    #: redundant line in an order is not redundant — it can make two
    #: things comparable that were not — so these are counted as
    #: decoys only when the answer turns out not to need them.
    extra: int = 0
    #: Whether premises may be written in the negative. Offered only
    #: where a negation has exactly one reading.
    negate: bool = False
    #: The families this one is built out of.
    inner: Tuple[str, ...] = ()


class Question(NamedTuple):
    """One dealt question, with everything measured about it."""

    grade: Grade
    #: The premises, in the order they are printed — which is shuffled,
    #: so they cannot be read down the page as a chain.
    lines: Tuple[str, ...]
    #: The question itself.
    asked: str
    #: What may be answered. Fixed per family: an option that is never
    #: right at a rung is a tell, and the bench prints how often each
    #: one is right rather than leaving that to be assumed.
    options: Tuple[str, ...]
    #: Index into :attr:`options`.
    answer: int
    #: What a reader that never composes two premises answers. Not a
    #: solver — a measurement of how much of the rung is atmosphere.
    surface: int
    #: How many premises have to be put together to get the answer.
    steps: int
    #: How many printed premises the answer does not need.
    decoys: int
    #: The derivation, shown after a wrong answer.
    working: Tuple[str, ...]

    @property
    def candidates(self) -> float:
        """Log-ten of what is left standing before any reasoning.

        Printed for the same reason it is printed everywhere else in
        the Workshop, and worth about as much as it looks: on ten of
        the twelve rungs it is log-ten of three.
        """
        return math.log10(len(self.options))

    @property
    def shown_answer(self) -> str:
        return self.options[self.answer]


GRADES: Tuple[Grade, ...] = (
    Grade('same or opposite', PARITY, items=6),
    Grade('more and less', ORDER, items=6),
    Grade('a gap in the chain', PARITY, items=7, extra=1),
    Grade('not more than', ORDER, items=7, extra=1, negate=True),
    Grade('all and at least one', CATEGORICAL, items=3),
    Grade('which way from here', PLANE, items=5),
    Grade('nine lines, and two that matter', ORDER, items=9, extra=1,
          negate=True),
    Grade('three at once', CATEGORICAL, items=4),
    Grade('up and down as well', SPACE, items=6),
    Grade('the same kind of thing', META, items=8, extra=1,
          inner=(ORDER,)),
    Grade('two questions, one answer', BINARY, inner=(PARITY, ORDER)),
    Grade('three questions, one answer', BINARY,
          inner=(ORDER, PLANE, PARITY), negate=True),
)


def grade_of(rung: int) -> Grade:
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


# --- what each family may be answered with --------------------------------


def _direction(value: Sequence[int]) -> str:
    """``'north and east'``, or ``'the same place'``."""
    said = [COMPASS[axis][0 if part > 0 else 1]
            for axis, part in enumerate(value) if part]
    return ' and '.join(said) if said else 'the same place'


def _signs(value: Sequence[int]) -> Tuple[int, ...]:
    return tuple((part > 0) - (part < 0) for part in value)


def _direction_options(axes: int) -> Tuple[str, ...]:
    """Every way one thing can stand to another, and no *cannot be told*.

    The direction families never leave the question open, and so they
    do not offer the answer that would say so. An option that is never
    right is worse than a missing one: it is a free elimination.
    """
    return tuple(_direction(one) for one in
                 itertools.product((1, 0, -1), repeat=axes))


#: The four categorical forms, in the order they are offered.
ALL, NONE, SOME, SOME_NOT = 'all', 'none', 'some', 'some not'
FORMS = (ALL, NONE, SOME, SOME_NOT)
NOTHING = 'nothing follows'

SAYS = {
    ALL: 'every %s is %s %s',
    NONE: 'no %s is %s %s',
    SOME: 'at least one %s is %s %s',
    SOME_NOT: 'at least one %s is not %s %s',
}

#: Words that sound as though they started with the other kind of
#: letter. The rule is about the sound rather than the spelling, and
#: with made-up names the question never came up: it is "a idiot"
#: that gave it away. Prefixes, so ``union`` covers ``unions``.
SOUNDS_CONSONANT = ('uni', 'use', 'usu', 'uti', 'uto', 'ura', 'ute',
                    'eu', 'ewe', 'one')
SOUNDS_VOWEL = ('hour', 'honest', 'honor', 'honour', 'heir')


def article(word: str) -> str:
    """``a`` or ``an``, for a name printed after it."""
    if word.startswith(SOUNDS_VOWEL):
        return 'an'
    if word.startswith(SOUNDS_CONSONANT):
        return 'a'
    return 'an' if word[:1] in 'aeiou' else 'a'


def says(form: str, subject: str, other: str) -> str:
    """One categorical line about two named things."""
    return SAYS[form] % (subject, article(other), other)

OPTIONS: Dict[str, Tuple[str, ...]] = {
    PARITY: ('the same', 'the opposite', UNTOLD),
    ORDER: ('more', 'less', UNTOLD),
    PLANE: _direction_options(2),
    SPACE: _direction_options(3),
    META: ('the same', 'different', UNTOLD),
    BINARY: ('true', 'false', UNTOLD),
}

#: The widest answer a rung ever offers, which is what the agent
#: boundary has to have a port for. Twenty-six directions, standing
#: still, and not being told.
MOST_OPTIONS = max(len(one) for one in OPTIONS.values())


def options_for(grade: Grade, about: Sequence[str] = ()) -> Tuple[str, ...]:
    """What *grade* offers.

    The categorical ones name the two terms being asked about, in the
    order they are asked about them — which is not always the order
    they were introduced in, because whether a conclusion converts is
    half of what there is to get wrong here.
    """
    if grade.family == CATEGORICAL:
        return tuple(says(form, about[0], about[1])
                     for form in FORMS) + (NOTHING,)
    return OPTIONS[grade.family]


# --- the premises, as a graph ---------------------------------------------


class Web(NamedTuple):
    """The premises before they are sentences.

    An edge means different things per family, and one shape carries
    all three: for an order *right* is more than *left*; for a parity
    the value is 0 for the same and 1 for the opposite; for a
    direction *right* stands one step ``value`` away from *left*.
    """

    grade: Grade
    items: Tuple[str, ...]
    edges: Tuple[Tuple[int, int, Tuple[int, ...]], ...]
    #: Where each item sits: a rank, a parity, or a point. Every edge
    #: is read off this, which is what makes the premises consistent
    #: without anything having to check them.
    place: Tuple[Tuple[int, ...], ...]
    #: Which piece of the web each item is in. Two pieces is what
    #: makes *cannot be told* an answer.
    part: Tuple[int, ...]


def _split(rng: random.Random, count: int,
           parts: int) -> List[List[int]]:
    """*count* items in one piece or two, never a piece of one.

    A piece of one item is an item no premise mentions, and a word
    that appears nowhere gives the answer away without any reasoning
    at all.
    """
    nodes = list(range(count))
    rng.shuffle(nodes)
    if parts < 2 or count < 5:
        return [nodes]
    cut = rng.randint(2, count - 2)
    return [nodes[:cut], nodes[cut:]]


def _step(rng: random.Random, family: str) -> Tuple[int, ...]:
    """One premise's worth of movement."""
    if family == PARITY:
        return (rng.randint(0, 1),)
    axes = AXES[family]
    while True:
        got = tuple(rng.randint(-1, 1) for _each in range(axes))
        if any(got):
            return got


def _joined(edges: Sequence[Tuple[int, int, Tuple[int, ...]]],
            one: int, two: int) -> bool:
    return any({left, right} == {one, two} for left, right, _v in edges)


def _grow(rng: random.Random, grade: Grade, parts: int,
          names: Optional[Tuple[str, ...]] = None) -> Optional[Web]:
    """A web of premises for *grade*, in *parts* pieces.

    **The number of printed premises does not depend on the number of
    pieces**, and that is the whole reason ``extra`` moves with
    ``parts``. A rung where two pieces mean one line fewer is a rung
    where counting the lines answers the question.
    """
    items = names or things(rng, grade.items)
    family = grade.family
    groups = _split(rng, grade.items, parts)
    place: List[Optional[Tuple[int, ...]]] = [None] * grade.items
    edges: List[Tuple[int, int, Tuple[int, ...]]] = []
    if family == ORDER:
        ranks = list(range(grade.items))
        rng.shuffle(ranks)
        place = [(one,) for one in ranks]
    axes = 1 if family == PARITY else AXES.get(family, 1)
    for group in groups:
        if family != ORDER:
            place[group[0]] = (0,) * axes
        for position in range(1, len(group)):
            node = group[position]
            # Mostly hang it off the last one, which grows chains
            # rather than stars. A star answers everything in two
            # steps whatever its size, and a rung called "six in a
            # row" ought to be six in a row.
            parent = (group[position - 1] if rng.random() < 0.7
                      else group[rng.randrange(position)])
            if family == ORDER:
                low, high = ((parent, node) if place[node] > place[parent]
                             else (node, parent))
                edges.append((low, high, (1,)))
                continue
            step = _step(rng, family)
            if family == PARITY:
                place[node] = ((place[parent][0] + step[0]) % 2,)
            else:
                place[node] = tuple(a + b for a, b
                                    in zip(place[parent], step))
            edges.append((parent, node, step))
    wanted = grade.extra + len(groups) - 1
    if wanted:
        free = [(one, two) for group in groups
                for one, two in itertools.combinations(sorted(group), 2)
                if not _joined(edges, one, two)]
        if len(free) < wanted:
            return None
        rng.shuffle(free)
        for one, two in free[:wanted]:
            if family == ORDER:
                low, high = ((one, two) if place[two] > place[one]
                             else (two, one))
                edges.append((low, high, (1,)))
            elif family == PARITY:
                edges.append((one, two,
                              ((place[two][0] - place[one][0]) % 2,)))
            else:                                # pragma: no cover
                return None                      # not renderable exactly
    part = [0] * grade.items
    for number, group in enumerate(groups):
        for node in group:
            part[node] = number
    return Web(grade, items, tuple(edges), tuple(place), tuple(part))


# --- reading it back ------------------------------------------------------


def _route(web: Web, start: int, goal: int,
           directed: bool) -> Tuple[int, ...]:
    """Shortest path from *start* to *goal*, as premise numbers.

    ``directed`` follows an order upwards only, which is what makes an
    order different from the others: two things in one piece of the
    web can still be incomparable.
    """
    if start == goal:
        return ()
    seen = {start: ()}
    edge = list(enumerate(web.edges))
    frontier = [start]
    while frontier:
        nxt = []
        for node in frontier:
            for number, (left, right, _value) in edge:
                if left == node:
                    other = right
                elif right == node and not directed:
                    other = left
                else:
                    continue
                if other in seen:
                    continue
                seen[other] = seen[node] + (number,)
                if other == goal:
                    return seen[other]
                nxt.append(other)
        frontier = nxt
    return ()


def _relation(web: Web, subject: int,
              other: int) -> Tuple[str, Tuple[int, ...]]:
    """What *subject* is to *other*, and the premises that say so."""
    family = web.grade.family
    if family == ORDER:
        up = _route(web, other, subject, True)
        if up:
            return 'more', up
        down = _route(web, subject, other, True)
        if down:
            return 'less', down
        return UNTOLD, ()
    if web.part[subject] != web.part[other]:
        return UNTOLD, ()
    path = _route(web, other, subject, False)
    if family == PARITY:
        apart = (web.place[subject][0] - web.place[other][0]) % 2
        return ('the opposite' if apart else 'the same'), path
    return _direction(_signs(tuple(a - b for a, b in
                                   zip(web.place[subject],
                                       web.place[other])))), path


def _usable(found: Dict[str, List]) -> bool:
    """Whether anything but *cannot be told* can be asked of this web.

    A piece of three items with an extra premise across it is a
    triangle, and a triangle states every pair outright: the web is
    consistent, connected and has nothing left to ask. Measured
    before this was checked, a rung that should have answered *cannot
    be told* one time in three answered it six times in ten.
    """
    return any(label != UNTOLD for label in found)


def _askable(web: Web) -> Dict[str, List[Tuple[int, int, Tuple[int, ...]]]]:
    """Every pair worth asking about, grouped by its answer.

    A pair one premise states outright is not worth asking about, so
    it is not here. Grouping by the answer and then picking a group is
    what keeps one option from being right more often than the rest.
    """
    found: Dict[str, List[Tuple[int, int, Tuple[int, ...]]]] = {}
    for subject, other in itertools.permutations(range(len(web.items)), 2):
        if _joined(web.edges, subject, other):
            continue
        label, path = _relation(web, subject, other)
        if label != UNTOLD and len(path) < 2:
            continue
        found.setdefault(label, []).append((subject, other, path))
    return found


# --- putting it into words ------------------------------------------------


ASKED = {
    PARITY: 'Is %s the same as %s, or the opposite?',
    ORDER: 'Is %s more than %s, or less?',
    PLANE: 'Which way is %s from %s?',
    SPACE: 'Which way is %s from %s?',
}


def _render(web: Web, number: int, rng: random.Random) -> str:
    """One premise, said one of the ways it can be said."""
    left, right, value = web.edges[number]
    names = web.items
    family = web.grade.family
    negate = web.grade.negate and rng.random() < 0.5
    if family == ORDER:
        if negate:
            return ('%s is not more than %s' % (names[left], names[right])
                    if rng.random() < 0.5 else
                    '%s is not less than %s' % (names[right], names[left]))
        return ('%s is more than %s' % (names[right], names[left])
                if rng.random() < 0.5 else
                '%s is less than %s' % (names[left], names[right]))
    if family == PARITY:
        same = value[0] == 0
        if negate:
            # With two ways to be and no third, "not the opposite of"
            # says "the same as" and nothing else. That is why the
            # direction families are not offered negation: there,
            # "not north of" says six other things.
            return '%s is not the %s %s' % (
                names[left], 'opposite of' if same else 'same as',
                names[right])
        return '%s is the %s %s' % (names[left],
                                    'same as' if same else 'opposite of',
                                    names[right])
    return _lies(names[right], _direction(value), names[left])


def _conclusion(family: str, subject: str, other: str, label: str) -> str:
    """The answer as a sentence, for the working."""
    if label == UNTOLD:
        return 'nothing in the premises links %s to %s' % (subject, other)
    if family == PARITY:
        return '%s is %s %s' % (subject,
                                'the same as' if label == 'the same'
                                else 'the opposite of', other)
    if family == ORDER:
        return '%s is %s than %s' % (subject, label, other)
    return _lies(subject, label, other)


def _lies(subject: str, label: str, other: str) -> str:
    """A direction as a sentence rather than as a label.

    ``north of`` and ``below`` do not take the same frame, and
    "hust is down of mailnet" is not English.
    """
    if label == 'the same place':
        return '%s is in the same place as %s' % (subject, other)
    parts = label.split(' and ')
    upright = [one for one in parts if one in COMPASS[2]]
    flat = [one for one in parts if one not in COMPASS[2]]
    if flat and upright:
        return '%s is %s and to the %s of %s' % (
            subject, upright[0], ' and '.join(flat), other)
    if flat:
        return '%s is to the %s of %s' % (subject, ' and '.join(flat), other)
    return '%s is %s %s' % (subject, upright[0], other)


def _surface(web: Web, order: Sequence[int], subject: int) -> str:
    """What a reader that never composes two premises answers.

    It finds the first line that names the thing asked about and
    answers with that line's relation, turned round if it has to be.
    This is the atmosphere effect written down: a rung it beats chance
    on can be answered without reasoning.
    """
    family = web.grade.family
    for number in order:
        left, right, value = web.edges[number]
        if subject not in (left, right):
            continue
        if family == ORDER:
            return 'more' if subject == right else 'less'
        if family == PARITY:
            return 'the same' if value[0] == 0 else 'the opposite'
        if subject == right:
            return _direction(value)
        return _direction(tuple(-one for one in value))
    return UNTOLD


def _agreeable(rng: random.Random, options: Sequence[str],
               label: str) -> bool:
    """Whether this deal should be one the surface reader gets right.

    Never, when the answer is one the surface reader cannot give: it
    does not say *cannot be told*, because a reader that composes
    nothing never finds out that nothing composes. **Asking for
    agreement on those deals was worse than useless** — no pair could
    supply it, every attempt was thrown away, and the deal fell back
    to whatever the last web offered. Measured: *cannot be told* came
    up half as often as it should have on the order rungs, and a
    fixed answer scored .51 where chance is .33.

    Otherwise one time in as many answers as that reader can give.
    With the answers themselves spread evenly over the options, that
    puts it at exactly chance.

    **Aimed at chance and no better, in both directions.** Left alone
    the one-line reader answered rung two six times in ten, and the
    atmosphere heuristic answered three quarters of the categorical
    rungs: in a chain, what a thing is to its neighbour is usually
    what it is to everything past it. Aimed at *never* right, the
    reader would be a way round the rung backwards.
    """
    if label in (UNTOLD, NOTHING):
        return False
    return rng.random() < 1.0 / max(1, _sayable(options))


def _sayable(options: Sequence[str]) -> int:
    """How many of these answers a reader that never composes can give."""
    return len(options) - sum(1 for one in (UNTOLD, NOTHING) if one in options)


def _index(options: Sequence[str], label: str) -> int:
    return options.index(label) if label in options else 0


def _chain_question(grade: Grade, rng: random.Random) -> Optional[Question]:
    """One question from an order, a parity or a direction.

    The answer wanted and whether the surface reader should get it are
    both decided **before** any web is built, and then webs are grown
    until one can supply both. Deciding either of them after the fact
    lets whatever the web happens to be good at set the odds.
    """
    options = OPTIONS[grade.family]
    want = options[rng.randrange(len(options))]
    agree = _agreeable(rng, options, want)
    kept = None
    for _try in range(40):
        parts = 1 if grade.family in AXES else rng.choice((1, 2))
        web = _grow(rng, grade, parts)
        if web is None:
            continue
        found = _askable(web)
        if not _usable(found):
            continue
        order = list(range(len(web.edges)))
        rng.shuffle(order)
        if kept is None:
            label = sorted(found)[rng.randrange(len(found))]
            kept = (web, label, found[label], order)
        if want not in found:
            continue
        fitting = [one for one in found[want]
                   if (_surface(web, order, one[0]) == want) == agree]
        if fitting:
            return _dress(rng, web, want, fitting, order)
    if kept is None:
        return None
    return _dress(rng, kept[0], kept[1], kept[2], kept[3])


def _dress(rng: random.Random, web: Web, label: str,
           pairs: Sequence[Tuple[int, int, Tuple[int, ...]]],
           order: Sequence[int]) -> Question:
    """A chosen pair, written out and measured."""
    grade = web.grade
    options = OPTIONS[grade.family]
    # The longest way round, among the pairs still standing. Picked
    # evenly, a nine-premise rung mostly asks two-premise questions:
    # short paths outnumber long ones badly.
    longest = max(len(one[2]) for one in pairs)
    pairs = [one for one in pairs if len(one[2]) == longest]
    subject, other, path = pairs[rng.randrange(len(pairs))]
    # Written once. The working has to quote the lines the player was
    # shown, and a premise rendered twice is a premise said two ways.
    said = {number: _render(web, number, rng) for number in order}
    lines = tuple(said[number] for number in order)
    names = web.items
    # Proving a negative takes every line: to be sure nothing links
    # two things you have to have read all of it.
    steps = len(path) if path else len(lines)
    working = tuple(said[number] for number in path) + (
        'so ' + _conclusion(grade.family, names[subject], names[other],
                            label),)
    return Question(
        grade=grade,
        lines=lines,
        asked=ASKED[grade.family] % (names[subject], names[other]),
        options=options,
        answer=_index(options, label),
        surface=_index(options, _surface(web, order, subject)),
        steps=steps,
        decoys=len(lines) - steps,
        working=working)


# --- all, none and at least one -------------------------------------------
#
# Decided by a fact about this fragment rather than by counting models:
# every universal premise is a condition on one thing at a time, so a
# set of premises has a model exactly when every existential premise
# has a *kind of thing* no universal forbids. That is one pass over
# the 2^n kinds, and it is exact.


def _forbids(statement: Tuple[str, int, int], kind: int) -> bool:
    """Whether a universal premise rules this kind of thing out."""
    form, subject, predicate = statement
    has_subject = bool(kind >> subject & 1)
    has_predicate = bool(kind >> predicate & 1)
    if form == ALL:
        return has_subject and not has_predicate
    return has_subject and has_predicate          # NONE


def _wants(statement: Tuple[str, int, int], kind: int) -> bool:
    """Whether this kind of thing is a witness for an existential."""
    form, subject, predicate = statement
    has_subject = bool(kind >> subject & 1)
    has_predicate = bool(kind >> predicate & 1)
    return has_subject and (has_predicate if form == SOME
                            else not has_predicate)


def satisfiable(count: int,
                statements: Sequence[Tuple[str, int, int]]) -> bool:
    """Whether *count* terms can be arranged so all of these hold.

    The Boolean reading: ``every X is a Y`` does not say there are any
    X, and the empty world satisfies every universal there is.
    """
    universal = [one for one in statements if one[0] in (ALL, NONE)]
    existential = [one for one in statements if one[0] in (SOME, SOME_NOT)]
    kinds = [kind for kind in range(1 << count)
             if not any(_forbids(one, kind) for one in universal)]
    return all(any(_wants(one, kind) for kind in kinds)
               for one in existential)


OPPOSITE = {ALL: SOME_NOT, SOME_NOT: ALL, NONE: SOME, SOME: NONE}


def entails(count: int, premises: Sequence[Tuple[str, int, int]],
            conclusion: Tuple[str, int, int]) -> bool:
    """Whether *conclusion* holds wherever the premises do."""
    denied = (OPPOSITE[conclusion[0]], conclusion[1], conclusion[2])
    return not satisfiable(count, tuple(premises) + (denied,))


def _shapes(count: int) -> List[Tuple[Tuple[str, int, int], ...]]:
    """Every way to link *count* terms in a row with one premise each."""
    links = count - 1
    made = []
    for forms in itertools.product(FORMS, repeat=links):
        for turns in itertools.product((0, 1), repeat=links):
            made.append(tuple(
                (forms[step], step + turns[step], step + 1 - turns[step])
                for step in range(links)))
    return made


def _atmosphere(premises: Sequence[Tuple[str, int, int]]) -> str:
    """The classic no-reasoning answer, and it is a real effect.

    Negative premise, negative conclusion; particular premise,
    particular conclusion. It never answers *nothing follows*, which
    is exactly what makes it worth measuring against.
    """
    negative = any(one[0] in (NONE, SOME_NOT) for one in premises)
    particular = any(one[0] in (SOME, SOME_NOT) for one in premises)
    if negative:
        return SOME_NOT if particular else NONE
    return SOME if particular else ALL


def _categorical_question(grade: Grade,
                          rng: random.Random) -> Optional[Question]:
    """Two or three premises about kinds of thing.

    **The pair asked about is not always the two ends, and not always
    the way round they were introduced.** Both matter. A premise
    off the path between them is a premise whose negative or
    particular form the atmosphere reader counts and should not, and
    a question asked backwards is the illicit conversion that
    "at least one X is not a Y" invites.
    """
    count = grade.items
    terms = things(rng, count)
    ends = [(one, two) for one in range(count) for two in range(count)
            if abs(one - two) > 1]
    subject, other = ends[rng.randrange(len(ends))]
    found: Dict[str, List[Tuple[Tuple[str, int, int], ...]]] = {}
    for premises in _shapes(count):
        if not satisfiable(count, premises):
            continue
        holds = [form for form in FORMS
                 if entails(count, premises, (form, subject, other))]
        if len(holds) > 1:
            # Premises that force a term to pick out nothing entail
            # more than one form at once. Rare, and thrown away rather
            # than dealt with a second right answer.
            continue
        found.setdefault(holds[0] if holds else NOTHING, []).append(premises)
    if not found:
        return None                              # pragma: no cover
    label = _which(rng, found)
    choices = found[label]
    agree = _agreeable(rng, options_for(grade, (terms[subject],
                                                terms[other])), label)
    fitting = [one for one in choices if (_atmosphere(one) == label) == agree]
    choices = fitting or choices
    premises = choices[rng.randrange(len(choices))]
    order = list(range(len(premises)))
    rng.shuffle(order)
    lines = tuple(says(premises[one][0], terms[premises[one][1]],
                       terms[premises[one][2]])
                  for one in order)
    options = options_for(grade, (terms[subject], terms[other]))
    spare = _spare(count, premises, label, subject, other)
    return Question(
        grade=grade,
        lines=lines,
        asked='What follows about %s and %s?' % (terms[subject],
                                                 terms[other]),
        options=options,
        answer=FORMS.index(label) if label != NOTHING else len(FORMS),
        surface=FORMS.index(_atmosphere(premises)),
        steps=len(premises) - spare,
        decoys=spare,
        working=lines + _categorical_working(count, premises, terms, label,
                                             subject, other))


def _which(rng: random.Random, found: Dict[str, List]) -> str:
    """Which answer this deal should have.

    Evenly over the five, **unless the atmosphere reader cannot be
    fooled at this pair** — which is not a quirk of the generator but
    the classical rules themselves: a valid conclusion is negative
    exactly when a premise is, and particular exactly when a premise
    is, so on every valid two-premise syllogism there is, atmosphere
    names the right form. Where that holds, the four forms are one
    answer between them and the only question left is whether
    anything follows at all. So it is asked as the coin it is, and
    both a fixed answer and the atmosphere reader sit at one half —
    which is the honest floor for a rung like that, and the reason
    there are two of these on the ladder rather than six.
    """
    forms = [one for one in sorted(found) if one != NOTHING]
    fooled = any(_atmosphere(one) != label
                 for label in forms for one in found[label])
    if fooled or not forms or NOTHING not in found:
        return sorted(found)[rng.randrange(len(found))]
    if rng.random() < 0.5:
        return NOTHING
    return forms[rng.randrange(len(forms))]


def _spare(count: int, premises: Sequence[Tuple[str, int, int]], label: str,
           subject: int, other: int) -> int:
    """How many premises the conclusion still follows without.

    Counted by leaving each one out and asking again, rather than by
    guessing from where it sits in the chain: a premise off the path
    can still be doing work.
    """
    if label == NOTHING:
        return 0
    spare = 0
    for number in range(len(premises)):
        without = premises[:number] + premises[number + 1:]
        if satisfiable(count, without) and entails(count, without,
                                                  (label, subject, other)):
            spare += 1
    return spare


def _categorical_working(count: int,
                         premises: Sequence[Tuple[str, int, int]],
                         terms: Sequence[str], label: str, subject: int,
                         other: int) -> Tuple[str, ...]:
    """Why. For *nothing follows* that means two worlds, not a shrug."""
    named = (terms[subject], terms[other])
    if label != NOTHING:
        return ('so ' + says(label, *named),
                'and none of the other three follows')
    both = [form for form in FORMS
            if satisfiable(count, tuple(premises) + ((form, subject, other),))]
    if len(both) >= 2:
        return ('the premises are all still true when ' +
                says(both[0], *named) + ',',
                'and all still true when ' + says(both[1], *named) + ',',
                'so nothing follows about %s and %s' % named)
    return ('so nothing follows about %s and %s' % named,)  # pragma: no cover


# --- families made of other families --------------------------------------


def _sub(grade: Grade, family: str, items: int, extra: int = 0) -> Grade:
    """A grade for one part of a question made of several."""
    return Grade(grade.name, family, items=items, extra=extra,
                 negate=grade.negate and family in (PARITY, ORDER))


def _flat(found: Dict[str, List]) -> List[Tuple[str, Tuple]]:
    return [(label, one) for label in sorted(found) for one in found[label]]


def _meta_question(grade: Grade, rng: random.Random) -> Optional[Question]:
    """Two relations out of one web, and whether they are the same kind."""
    inner = grade.inner[0] if grade.inner else ORDER
    sub = _sub(grade, inner, grade.items, grade.extra)
    options = OPTIONS[META]
    want = options[rng.randrange(len(options))]
    agree = _agreeable(rng, options, want)
    kept = None
    for _try in range(40):
        parts = 1 if inner in AXES else rng.choice((1, 2))
        web = _grow(rng, sub, parts)
        if web is None:
            continue
        found = _askable(web)
        if not _usable(found):
            continue
        pairs = _flat(found)
        if len(pairs) < 2:
            continue
        groups: Dict[str, List] = {}
        for one, two in itertools.permutations(pairs, 2):
            if len({one[1][0], one[1][1], two[1][0], two[1][1]}) < 4:
                continue
            if UNTOLD in (one[0], two[0]):
                answer = UNTOLD
            else:
                answer = 'the same' if one[0] == two[0] else 'different'
            groups.setdefault(answer, []).append((one, two))
        if not groups:
            continue
        order = list(range(len(web.edges)))
        rng.shuffle(order)
        if kept is None:
            label = sorted(groups)[rng.randrange(len(groups))]
            kept = (web, label, groups[label], order)
        if want not in groups:
            continue
        fitting = [pair for pair in groups[want]
                   if (_meta_surface(web, order, pair) == want) == agree]
        if fitting:
            return _dress_meta(rng, grade, web, want, fitting, order)
    if kept is None:
        return None
    return _dress_meta(rng, grade, kept[0], kept[1], kept[2], kept[3])


def _dress_meta(rng: random.Random, grade: Grade, web: Web, answer: str,
                choices: Sequence[Tuple], order: Sequence[int]) -> Question:
    inner = web.grade.family
    names = web.items
    one, two = choices[rng.randrange(len(choices))]
    said = {number: _render(web, number, rng) for number in order}
    lines = tuple(said[number] for number in order)
    working: List[str] = []
    steps = 0
    for label, (subject, other, path) in (one, two):
        working.extend(said[number] for number in path)
        working.append('so ' + _conclusion(inner, names[subject],
                                           names[other], label))
        steps += len(path) if path else len(lines)
    working.append('so the two are ' + answer)
    surface = _meta_surface(web, order, (one, two))
    options = OPTIONS[META]
    return Question(
        grade=grade,
        lines=lines,
        asked='Is the way %s stands to %s the same as the way %s stands '
              'to %s?' % (names[one[1][0]], names[one[1][1]],
                          names[two[1][0]], names[two[1][1]]),
        options=options,
        answer=options.index(answer),
        surface=options.index(surface),
        steps=steps,
        decoys=max(0, len(lines) - steps),
        working=tuple(working))


def _meta_surface(web: Web, order: Sequence[int],
                  pair: Sequence[Tuple]) -> str:
    """What the one-line reader makes of the two relations."""
    seen = tuple(_surface(web, order, part[1][0]) for part in pair)
    if UNTOLD in seen:
        return UNTOLD
    return 'the same' if seen[0] == seen[1] else 'different'


#: Three values, because *cannot be told* is one of them. An ``and``
#: with one false half is false whatever the other half is; an
#: *exactly one* with an unsettled half is never settled. That
#: asymmetry is most of what the top two rungs are about.
def _kleene(op: str, left: Optional[bool],
            right: Optional[bool]) -> Optional[bool]:
    if op == 'and':
        if left is False or right is False:
            return False
        return True if left and right else None
    if op == 'or':
        if left is True or right is True:
            return True
        return False if left is False and right is False else None
    if left is None or right is None:
        return None
    return left != right


CONNECTIVES = ('and', 'or', 'exactly one of')


def _say_op(op: str, left: str, right: str) -> str:
    if op == 'exactly one of':
        return 'exactly one of (%s) and (%s)' % (left, right)
    return '(%s) %s (%s)' % (left, op, right)


TRUTH = {True: 'true', False: 'false', None: UNTOLD}


def _claims(rng: random.Random, grade: Grade, family: str, items: int,
            names: Tuple[str, ...]) -> Optional[Tuple]:
    """One sub-question: its premises, and every claim it settles.

    A claim is a definite sentence — *cannot be told* is not something
    a premise says, it is something a reader works out — so the claims
    are drawn from the family's definite answers only.
    """
    for _try in range(20):
        parts = 1 if family in AXES else rng.choice((1, 2))
        # A sub-question widens by a name rather than by a premise
        # when it falls into two pieces. Standing alone that would be
        # a tell — count the words, learn something — but these are
        # shuffled in among another question's premises, and working
        # out which lines belong together is the question.
        sub = _sub(grade, family, items + parts - 1)
        web = _grow(rng, sub, parts, names=names[:items + parts - 1])
        if web is None:
            continue
        found = _askable(web)
        if not _usable(found):
            continue
        definite = [one for one in OPTIONS[family] if one != UNTOLD]
        truths: Dict[Optional[bool], List] = {}
        for label, group in found.items():
            for subject, other, path in group:
                for claim in definite:
                    value = (None if label == UNTOLD
                             else claim == label)
                    truths.setdefault(value, []).append(
                        (subject, other, claim, path))
        return web, truths
    return None


def _binary_question(grade: Grade, rng: random.Random) -> Optional[Question]:
    """Two or three claims, and what the connectives make of them."""
    families = grade.inner
    size = 5
    pool = things(rng, (size + 1) * len(families))
    parts = []
    for number, family in enumerate(families):
        made = _claims(rng, grade, family, size,
                       pool[number * (size + 1):(number + 1) * (size + 1)])
        if made is None:
            return None
        parts.append(made)
    shapes: Dict[Optional[bool], List] = {}
    keys = [sorted(one[1], key=lambda v: (v is None, v)) for one in parts]
    ways = list(itertools.product(CONNECTIVES, repeat=len(families) - 1))
    for chosen in itertools.product(*keys):
        for way in ways:
            value = chosen[0]
            for step, other in enumerate(chosen[1:]):
                value = _kleene(way[step], value, other)
            shapes.setdefault(value, []).append((chosen, way))
    if not shapes:
        return None                              # pragma: no cover
    options = OPTIONS[BINARY]
    want = rng.randrange(len(options))
    order = sorted(shapes, key=lambda v: (v is None, v))
    got = [one for one in order if TRUTH[one] == options[want]]
    value = got[0] if got else order[rng.randrange(len(order))]
    return _dress_binary(rng, grade, parts, shapes[value], value)


def _binary_surface(parts: Sequence[Tuple], orders: Sequence[Sequence[int]],
                    claims: Sequence[Tuple],
                    way: Sequence[str]) -> Optional[bool]:
    """The one-line reader's answer to the whole thing.

    It reads each claim off a single premise and then combines them
    correctly, so what this measures is whether the composing is
    where the difficulty is, rather than whether the reader can
    compose at all.
    """
    seen = []
    for number, (web, _truths) in enumerate(parts):
        subject, _other, claim, _path = claims[number]
        read = _surface(web, orders[number], subject)
        seen.append(None if read == UNTOLD else read == claim)
    got = seen[0]
    for number, other in enumerate(seen[1:]):
        got = _kleene(way[number], got, other)
    return got


def _dress_binary(rng: random.Random, grade: Grade, parts: Sequence[Tuple],
                  shapes: Sequence[Tuple], value: Optional[bool]) -> Question:
    """The claims picked, the premises shuffled together, the sum measured.

    **The connectives are chosen along with the claims**, not before
    them, because they decide whether a misreading matters at all: an
    *or* with one true half is true however badly the other half is
    read, so the one-line reader gets the whole thing right by being
    wrong in a place that could not count. Left to pick only the
    claims, this rung sat at .57 against a floor of .33 — better than
    the reader manages on either half of it alone.
    """
    lines: List[str] = []
    said: List[Dict[int, str]] = []
    orders: List[List[int]] = []
    for web, _truths in parts:
        order = list(range(len(web.edges)))
        rng.shuffle(order)
        writing = {one: _render(web, one, rng) for one in order}
        lines.extend(writing[one] for one in order)
        said.append(writing)
        orders.append(order)
    agree = _agreeable(rng, OPTIONS[BINARY], TRUTH[value])
    best = None
    for _try in range(40):
        chosen, way = shapes[rng.randrange(len(shapes))]
        trying = [parts[number][1][chosen[number]] for number in
                  range(len(parts))]
        trying = [one[rng.randrange(len(one))] for one in trying]
        if best is None:
            best = (chosen, way, trying)
        if (_binary_surface(parts, orders, trying, way) == value) == agree:
            best = (chosen, way, trying)
            break
    chosen, way, claims = best
    # Shuffled across the sub-questions as well as inside them: which
    # premises talk to each other is part of the question.
    together = list(range(len(lines)))
    rng.shuffle(together)
    shown = tuple(lines[one] for one in together)
    sentences = []
    working: List[str] = []
    steps = 0
    for number, (web, _truths) in enumerate(parts):
        subject, other, claim, path = claims[number]
        sentence = _conclusion(web.grade.family, web.items[subject],
                               web.items[other], claim)
        sentences.append(sentence)
        working.extend(said[number][one] for one in path)
        working.append('so "%s" is %s' % (sentence, TRUTH[chosen[number]]))
        steps += len(path) if path else len(web.edges)
    asked = sentences[0]
    for number, sentence in enumerate(sentences[1:]):
        asked = _say_op(way[number], asked, sentence)
    steps += len(parts) - 1
    options = OPTIONS[BINARY]
    working.append('so the whole of it is ' + TRUTH[value])
    return Question(
        grade=grade,
        lines=shown,
        asked='Is this true?  ' + asked,
        options=options,
        answer=options.index(TRUTH[value]),
        surface=options.index(
            TRUTH[_binary_surface(parts, orders, claims, way)]),
        steps=steps,
        decoys=max(0, len(shown) - steps),
        working=tuple(working))


# --- dealing one ----------------------------------------------------------


BUILDERS = {
    PARITY: _chain_question,
    ORDER: _chain_question,
    PLANE: _chain_question,
    SPACE: _chain_question,
    CATEGORICAL: _categorical_question,
    META: _meta_question,
    BINARY: _binary_question,
}


def deal_one(grade: Grade, rng: random.Random) -> Optional[Question]:
    """One question at *grade*, read back before it is handed over."""
    builder = BUILDERS.get(grade.family)
    if builder is None:
        return None
    for _try in range(12):
        made = builder(grade, rng)
        if made is not None and checks_out(made):
            return made
    return None


def generate(level_number: int, seed: Optional[int] = None) \
        -> Optional[Question]:
    """A question for *level_number*, one-based into :data:`GRADES`."""
    return deal_one(grade_of(level_number), random.Random(seed))


def correct(question: Question, chosen: int) -> bool:
    """Whether *chosen* answers it. One option, and no partial credit."""
    return 0 <= int(chosen) < len(question.options) and (
        int(chosen) == question.answer)


# --- read back off the page -----------------------------------------------
#
# A generator that checks itself proves only that it is consistent. So
# the printed lines are parsed back into relations by something that
# never saw the web, and solved again. This catches what a self-check
# cannot: a negation rendered the wrong way round, a direction written
# in a frame that says something else, a premise the shuffle dropped.
#
# For the categorical rungs the decision procedure is the same code
# run twice, so what the read-back checks there is the printing rather
# than the logic. Said plainly rather than left to be assumed.

WORD_AXIS = {word: (axis, 1 if which == 0 else -1)
             for axis, pair in enumerate(COMPASS)
             for which, word in enumerate(pair)}

ORDER_LINE = re.compile(r'^(\w+) is (not )?(more|less) than (\w+)$')
PARITY_LINE = re.compile(
    r'^(\w+) is (not )?the (same as|opposite of) (\w+)$')
FLAT_LINE = re.compile(r'^(\w+) is (?:(above|below) and )?to the '
                       r'([a-z ]+) of (\w+)$')
UPRIGHT_LINE = re.compile(r'^(\w+) is (above|below) (\w+)$')
FORM_LINE = re.compile(r'^(every|no|at least one) (\w+) is (not )?an? (\w+)$')
#: Never a premise — a step is a step — but a claim can say it.
STILL_LINE = re.compile(r'^(\w+) is in the same place as (\w+)$')

ASKED_LINE = {
    PARITY: re.compile(r'^Is (\w+) the same as (\w+), or the opposite\?$'),
    ORDER: re.compile(r'^Is (\w+) more than (\w+), or less\?$'),
    PLANE: re.compile(r'^Which way is (\w+) from (\w+)\?$'),
    CATEGORICAL: re.compile(r'^What follows about (\w+) and (\w+)\?$'),
}
ASKED_LINE[SPACE] = ASKED_LINE[PLANE]


def parse_line(text: str) -> Optional[Tuple]:
    """One printed premise, back into what it says.

    ``(family, left, right, value)`` — and the value is what the words
    mean, not what built them, so a negation written wrongly reads
    back wrongly.
    """
    found = ORDER_LINE.match(text)
    if found:
        left, negated, word, right = found.groups()
        more = (word == 'more') != bool(negated)
        return (ORDER, right, left, (1,)) if more else (ORDER, left, right,
                                                        (1,))
    found = PARITY_LINE.match(text)
    if found:
        left, negated, word, right = found.groups()
        same = (word == 'same as') != bool(negated)
        return (PARITY, left, right, (0 if same else 1,))
    found = STILL_LINE.match(text)
    if found:
        right, left = found.groups()
        return (PLANE, left, right, (0, 0))
    found = FLAT_LINE.match(text)
    if found:
        right, upright, flat, left = found.groups()
        words = flat.split(' and ') + ([upright] if upright else [])
    else:
        found = UPRIGHT_LINE.match(text)
        if not found:
            found = FORM_LINE.match(text)
            if found:
                word, subject, negated, predicate = found.groups()
                form = (ALL if word == 'every' else NONE if word == 'no'
                        else SOME_NOT if negated else SOME)
                return (CATEGORICAL, subject, predicate, form)
            return None
        right, upright, left = found.groups()
        words = [upright]
    axes = 3 if any(one in COMPASS[2] for one in words) else 2
    value = [0, 0, 0]
    for one in words:
        if one not in WORD_AXIS:
            return None
        axis, sign = WORD_AXIS[one]
        value[axis] = sign
        axes = max(axes, axis + 1)
    return (PLANE if axes == 2 else SPACE, left, right, tuple(value[:axes]))


def _reread(family: str, edges: Sequence[Tuple], subject: str,
            other: str) -> Optional[str]:
    """Solve the parsed premises without ever having seen the web."""
    if family == ORDER:
        for want, start, goal in (('more', other, subject),
                                  ('less', subject, other)):
            seen, frontier = {start}, [start]
            while frontier:
                nxt = []
                for node in frontier:
                    for low, high, _value in edges:
                        if low == node and high not in seen:
                            if high == goal:
                                return want
                            seen.add(high)
                            nxt.append(high)
                frontier = nxt
        return UNTOLD
    seen = {other: (0,) * len(edges[0][2])}
    frontier = [other]
    while frontier:
        nxt = []
        for node in frontier:
            for left, right, value in edges:
                for near, far, way in ((left, right, 1), (right, left, -1)):
                    if near != node or far in seen:
                        continue
                    seen[far] = tuple(one + way * two for one, two
                                      in zip(seen[node], value))
                    nxt.append(far)
        frontier = nxt
    if subject not in seen:
        return UNTOLD
    if family == PARITY:
        return 'the opposite' if seen[subject][0] % 2 else 'the same'
    return _direction(_signs(seen[subject]))


def _bank(parsed: Sequence[Tuple]) -> Dict[str, List[Tuple]]:
    """The parsed premises, grouped by which question they belong to.

    A direction premise with nothing vertical in it reads as flat
    whether it came from a flat question or an upright one, so the
    directions are banked together and padded to the widest of them.
    """
    axes = max([len(one[3]) for one in parsed
                if one[0] in (PLANE, SPACE)] or [0])
    banked: Dict[str, List[Tuple]] = {}
    for family, left, right, value in parsed:
        if family in (PLANE, SPACE):
            value = tuple(value) + (0,) * (axes - len(value))
            family = PLANE if axes == 2 else SPACE
        banked.setdefault(family, []).append((left, right, value))
    return banked


def _holds(claim: Tuple, banked: Dict[str, List[Tuple]]) -> Optional[bool]:
    """Whether a claim sentence is true of the premises, or unsettled."""
    family, left, right, value = claim
    if family in (PLANE, SPACE):
        family = PLANE if len(banked.get(PLANE, ())) else SPACE
        edges = banked.get(family)
        if not edges:
            return None
        wide = len(edges[0][2])
        value = tuple(value) + (0,) * (wide - len(value))
        said = _direction(value)
        subject, other = right, left
    elif family == ORDER:
        edges, said = banked.get(ORDER), 'more'
        subject, other = right, left
    else:
        edges = banked.get(PARITY)
        said = 'the same' if value[0] == 0 else 'the opposite'
        subject, other = left, right
    if not edges:
        return None
    got = _reread(family, edges, subject, other)
    return None if got == UNTOLD else got == said


def _take_group(text: str) -> Tuple[str, str]:
    """A bracketed piece off the front of *text*, and what is left."""
    if not text.startswith('('):
        return text, ''
    depth = 0
    for spot, letter in enumerate(text):
        depth += (letter == '(') - (letter == ')')
        if depth == 0:
            return text[1:spot], text[spot + 1:]
    return text, ''


def _read_claim(text: str) -> Optional[Tuple]:
    """The printed question of a made-of-others rung, back into a tree."""
    text = text.strip()
    if text.startswith('exactly one of '):
        left, rest = _take_group(text[len('exactly one of '):])
        if not rest.startswith(' and '):
            return None
        right, _more = _take_group(rest[5:])
        return ('exactly one of', _read_claim(left), _read_claim(right))
    if text.startswith('('):
        left, rest = _take_group(text)
        for word in (' and ', ' or '):
            if rest.startswith(word):
                right, _more = _take_group(rest[len(word):])
                return (word.strip(), _read_claim(left), _read_claim(right))
        return _read_claim(left)
    return ('claim', text)


def _value_of(tree: Optional[Tuple],
              banked: Dict[str, List[Tuple]]) -> Optional[bool]:
    if tree is None:
        raise ParseError('unreadable claim')
    if tree[0] == 'claim':
        claim = parse_line(tree[1])
        if claim is None:
            raise ParseError(tree[1])
        return _holds(claim, banked)
    return _kleene(tree[0], _value_of(tree[1], banked),
                   _value_of(tree[2], banked))


class ParseError(ValueError):
    """The printed page did not read back. A fault, not a wrong answer."""


META_ASKED = re.compile(r'^Is the way (\w+) stands to (\w+) the same as '
                        r'the way (\w+) stands to (\w+)\?$')
CLAIM_ASKED = re.compile(r'^Is this true\?\s+(.*)$')


def read_back(question: Question) -> Optional[int]:
    """The answer, worked out again from the printed page alone.

    ``None`` where the page cannot be read back at all, which is a
    fault rather than a wrong answer, and is why :func:`checks_out`
    treats it as one.
    """
    family = question.grade.family
    parsed = [parse_line(one) for one in question.lines]
    if any(one is None for one in parsed):
        return None
    banked = _bank(parsed)
    if family == META:
        asking = META_ASKED.match(question.asked)
        if asking is None or len(banked) != 1:
            return None
        inner = list(banked)[0]
        first, second, third, fourth = asking.groups()
        seen = (_reread(inner, banked[inner], first, second),
                _reread(inner, banked[inner], third, fourth))
        got = (UNTOLD if UNTOLD in seen else
               'the same' if seen[0] == seen[1] else 'different')
        return question.options.index(got)
    if family == BINARY:
        asking = CLAIM_ASKED.match(question.asked)
        if asking is None:
            return None
        try:
            value = _value_of(_read_claim(asking.group(1)), banked)
        except ParseError:
            return None
        return question.options.index(TRUTH[value])
    if family not in ASKED_LINE:
        return None
    asking = ASKED_LINE[family].match(question.asked)
    if asking is None:
        return None
    subject, other = asking.groups()
    if family == CATEGORICAL:
        if list(banked) != [CATEGORICAL]:
            return None
        terms = [subject, other]
        for left, right, _value in banked[CATEGORICAL]:
            for word in (left, right):
                if word not in terms:
                    terms.append(word)
        where = {word: number for number, word in enumerate(terms)}
        statements = [(value, where[left], where[right])
                      for left, right, value in banked[CATEGORICAL]]
        holds = [form for form in FORMS
                 if entails(len(terms), statements,
                            (form, where[subject], where[other]))]
        if len(holds) != 1:
            return len(FORMS)
        return FORMS.index(holds[0])
    wanted = PLANE if family in (PLANE, SPACE) else family
    banked_family = (SPACE if SPACE in banked else PLANE) if (
        wanted == PLANE) else family
    if banked_family not in banked:
        return None
    got = _reread(banked_family, banked[banked_family], subject, other)
    return (question.options.index(got) if got in question.options
            else question.options.index(UNTOLD)
            if UNTOLD in question.options else None)


def checks_out(question: Question) -> bool:
    """Whether the question survives being read back off its own page."""
    if not 0 <= question.answer < len(question.options):
        return False
    if len(set(question.options)) != len(question.options):
        return False
    if not 0 <= question.surface < len(question.options):
        return False
    if question.steps < 1 or question.decoys < 0:
        return False
    if any(parse_line(one) is None for one in question.lines):
        return False
    # A page that will not read back is a fault rather than a wrong
    # answer, and it is dealt again rather than handed over.
    return read_back(question) == question.answer


__all__ = ['ALL', 'BINARY', 'CATEGORICAL', 'FORMS', 'GRADES', 'GRAMMAR',
           'article',
           'Grade',
           'META', 'MOST_OPTIONS', 'NEARLY', 'NONE', 'NOTHING', 'OPTIONS',
           'ORDER',
           'PARITY', 'PLANE', 'Question', 'SOME', 'SOME_NOT', 'SPACE',
           'UNTOLD', 'Web', 'checks_out', 'correct', 'deal_one', 'entails',
           'forget', 'generate', 'grade_of', 'nonsense', 'options_for',
           'parse_line', 'read_back', 'real_names', 'satisfiable', 'says',
           'things']
