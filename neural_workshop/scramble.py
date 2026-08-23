# -*- coding: utf-8 -*-
"""Corrupt a sentence, and ask for it back.

    the black horse walked along the road
    the balck hrose wlaked alnog the raod

That is rung one. Rung twelve is the same sentence with every letter
of every word free to move, one letter of each thrown away, one
stranger thrown in, the spaces taken out and the words shuffled
about — and the answer is still on the page, because the letters are
still mostly there and English is still English.

The corruption is a pipeline, not a rule, and that is what lets the
ladder run as far as it does. Eight dials, each of which is a
different way of taking information out:

===============  =======================================================
``swap``         adjacent letters transposed, ``black`` → ``balck``
``interior``     the middle permuted, ends kept, ``horse`` → ``hsroe``
``whole``        every letter free to move, ``horse`` → ``orseh``
``drop``         letters deleted, ``horse`` → ``hrse``
``insert``       letters added, ``horse`` → ``hoxrse``
``substitute``   letters replaced by a keyboard neighbour
``spaces``       word boundaries moved (1) or removed entirely (2)
``order``        words permuted inside a window
===============  =======================================================

**The dial that matters is not "how scrambled".** It is *how much is
left*, and that is measurable rather than assertable. For a corrupted
token and a vocabulary, :func:`candidates` is the set of words the
token could have been — every word whose letters are within reach of
the ones on show. The product of those set sizes across a sentence is
the number of readings that survive the letters alone, before a
solver knows anything about English. :attr:`Deal.ambiguity` is its
base-ten logarithm.

Against that, :func:`read_off` is a reader with no idea what a
sentence is: it answers each token with the commonest word whose
letters fit, and where the gaps have moved it picks the segmentation
that makes the commonest words it can. It is the context-free floor.
What it gets back is what the page still says outright; everything
above it is what a reader has to bring.

=====  ======================  =========  =======  ========
rung   name                    ambiguity   pinned  read back
=====  ======================  =========  =======  ========
1      two letters out               0.3     0.92      0.98
2      the middle shuffled           0.0     0.98      1.00
3      longer lines                  0.0     0.99      1.00
4      the ends move too             1.0     0.69      0.98
5      the gaps move                 1.3     0.64      0.82
6      a letter missing              8.4     0.17      0.76
7      letters thrown in            12.8     0.10      0.65
8      gaps and letters both         8.5     0.17      0.27
9      wrong letters                22.5     0.02      0.23
10     no gaps at all                8.8     0.14      0.25
11     out of order                 10.4     0.13      0.23
12     everything at once           27.3     0.01      0.04
=====  ======================  =========  =======  ========

Median ambiguity over forty deals, read back over 120 (13 at rung 12,
which costs two seconds a line). Rerun it with
``tests/bench_scramble.py``.

Three things in that table are worth more than the ladder itself.

**The famous trick removes almost nothing.** Rungs one to four are
typoglycemia — swap two letters, shuffle the middle, shuffle the lot —
and a reader that has never heard of English still gets 98 words in a
hundred back. That is not a defect in the reader. An anagram of an
English word is almost always an anagram of *only* that word, so the
letters of ``hrose`` determine ``horse`` outright, and the whole
effect people find remarkable about jumbled text is a fact about
reading speed rather than about information. Nothing is actually
taken away until rung five.

**Ambiguity and difficulty are not the same axis.** Rung 9 has the
worst ambiguity on the ladder, 10^22, and rungs 8, 10 and 11 read back
within a few points of it on a hundredth of that. Missing letters and
letters out of place leave a huge candidate set that context collapses
easily; moving the gaps leaves a small one that context cannot help
with, because you cannot use a word's neighbours before you know
where the word ends. Two of the columns disagree, and the honest
thing is to print both.

**Rungs 8 to 11 are one shelf as far as the reader is concerned** —
0.27, 0.23, 0.25, 0.23, which is noise. They are ordered by what is
taken away, not by that column, because what separates them is the
spaces and the word order and the reader is blind to both by
construction. ``bench_scramble.py`` prints this rather than leaving it
to be noticed.

The ambiguity column is measured on the true word boundaries, so for
the five rungs that move the gaps it is a floor and not a count. And
the letter budgets deliberately stop growing once the gaps start
moving: soup on top of soup is not a rung, and everything above rung
seven gets harder structurally instead.

**What is not promised.** The crossword can promise its grid has one
answer. This cannot promise its sentence has one reading, because what
rules the others out is knowing English and nothing here knows
English. See :mod:`neural_workshop.sentences` for why real text was
chosen anyway. What is promised is the table: how much of the answer
is still on the page, per rung, counted rather than claimed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
import re
from collections import Counter
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .sentences import Sentence, choose, ranks, vocabulary

LETTERS = 'abcdefghijklmnopqrstuvwxyz'

#: Keys next to each other on a qwerty board. A substitution goes to a
#: neighbour rather than to any letter at all, because a typo is a
#: near miss and a random letter is noise — and the difference shows
#: up in :func:`read_off`, which finds a near miss much easier.
NEAR_KEYS: Dict[str, str] = {
    'a': 'qwsz', 'b': 'vghn', 'c': 'xdfv', 'd': 'serfcx', 'e': 'wsdr',
    'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb', 'i': 'ujko', 'j': 'huikmn',
    'k': 'jiolm', 'l': 'kop', 'm': 'njk', 'n': 'bhjm', 'o': 'iklp',
    'p': 'ol', 'q': 'wa', 'r': 'edft', 's': 'awedxz', 't': 'rfgy',
    'u': 'yhji', 'v': 'cfgb', 'w': 'qase', 'x': 'zsdc', 'y': 'tghu',
    'z': 'asx',
}


class Grade(NamedTuple):
    """One rung: which sentences, and what is done to them."""

    name: str
    #: How many words the sentence may have.
    span: Tuple[int, int]
    #: The rarest word allowed, and equally the vocabulary a solver
    #: draws from. One dial, not two: a solver told the sentence is
    #: made of common words and then shown a rare one has been lied to.
    top_rank: int
    #: Adjacent transpositions inside each word.
    swap: int = 0
    #: Permute the letters between the first and the last.
    interior: bool = False
    #: Permute every letter, first and last included.
    whole: bool = False
    #: Letters deleted from each word, never below two letters left.
    drop: int = 0
    #: Letters added to each word.
    insert: int = 0
    #: Letters replaced by a keyboard neighbour.
    substitute: int = 0
    #: 0 leaves the spaces, 1 moves them, 2 takes them all out.
    spaces: int = 0
    #: Words are permuted inside blocks this wide. 0 and 1 are no-ops.
    order: int = 0


#: Gentle to superhuman. The ambiguity and read-back columns in the
#: module docstring were measured off this table, not guessed, and the
#: table moved twice because of what they said.
GRADES: Tuple[Grade, ...] = (
    #                             span      rank  swap intr whole
    #                                  drop ins sub spaces order
    Grade('two letters out',      (6, 9),   3000, 1),
    Grade('the middle shuffled',  (6, 9),   6000, 0, True),
    Grade('longer lines',         (8, 12), 12000, 0, True),
    Grade('the ends move too',    (8, 12), 12000, 0, False, True),
    Grade('the gaps move',        (8, 12), 20000, 0, False, True,
          0, 0, 0, 1),
    Grade('a letter missing',     (8, 12), 20000, 0, False, True, 1),
    Grade('letters thrown in',    (8, 12), 30000, 0, False, True, 1, 1),
    Grade('gaps and letters both', (8, 12), 30000, 0, False, True,
          1, 0, 0, 1),
    Grade('wrong letters',        (8, 12), 30000, 0, False, True, 1, 1, 1),
    Grade('no gaps at all',       (8, 12), 30000, 0, False, True,
          1, 0, 0, 2),
    Grade('out of order',         (8, 12), 60000, 0, False, True,
          1, 0, 0, 1, 2),
    Grade('everything at once',   (8, 14), 60000, 0, False, True,
          1, 1, 1, 2, 3),
)


def grade_of(rung: int) -> Grade:
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


# --- what the letters still say -------------------------------------------


def anchored(grade: Grade) -> bool:
    """Whether the first and last letters of a word survive intact.

    Only when nothing changes the letters themselves. A single drop
    can take the last letter away, so the moment ``drop``, ``insert``
    or ``substitute`` is on, the ends stop being evidence.
    """
    return (grade.interior and not grade.whole
            and not (grade.drop or grade.insert or grade.substitute))


def removals(grade: Grade) -> int:
    """Letters on show that were never in the word."""
    return grade.insert + grade.substitute


def additions(grade: Grade) -> int:
    """Letters of the word that are not on show."""
    return grade.drop + grade.substitute


def bag_distance(token: str, word: str) -> int:
    """Letters to take out of *token* and put in, to reach *word*."""
    left, right = Counter(token), Counter(word)
    return sum((left - right).values()) + sum((right - left).values())


def feasible(grade: Grade, token: str, word: str) -> bool:
    """Whether *token* could be *word* corrupted at *grade*.

    A superset of what the corruption can actually produce, never a
    subset: it must not reject the truth, or the ambiguity count would
    be a count of the wrong thing. So it tests only what survives
    every ordering of the operators — the length, the letters, and
    the ends when the ends are safe.
    """
    if not word:
        return False
    if not len(word) - grade.drop <= len(token) <= len(word) + grade.insert:
        return False
    if anchored(grade) and (token[:1] != word[:1] or token[-1:] != word[-1:]):
        return False
    return bag_distance(token, word) <= removals(grade) + additions(grade)


class Vocab:
    """The words a solver may draw on, indexed by their letters."""

    def __init__(self, top_rank: int) -> None:
        self.top_rank = top_rank
        self.words = vocabulary(top_rank)
        known = ranks()
        self.rank = {word: known.get(word, 1 << 30) for word in self.words}
        self.by_letters: Dict[str, List[str]] = {}
        for word in self.words:
            self.by_letters.setdefault(''.join(sorted(word)), []).append(word)
        self.longest = max((len(word) for word in self.words), default=1)

    def __len__(self) -> int:
        return len(self.words)


_VOCABS: Dict[int, Vocab] = {}


def vocab_for(grade: Grade) -> Vocab:
    """The vocabulary of *grade*, built once and kept."""
    if grade.top_rank not in _VOCABS:
        _VOCABS[grade.top_rank] = Vocab(grade.top_rank)
    return _VOCABS[grade.top_rank]


def _recipe(grade: Grade) -> Tuple:
    """Everything about a grade that changes what a token could be."""
    return (grade.drop, grade.insert, grade.substitute, grade.whole,
            grade.interior, grade.swap)


_FITS: Dict[Tuple, Tuple[str, ...]] = {}


def candidates(grade: Grade, token: str,
               words: Optional[Vocab] = None) -> Tuple[str, ...]:
    """Every word in the vocabulary that *token* could have been.

    Found by going at the letters rather than at the word list: the
    token's letters, minus up to :func:`removals` of them, plus up to
    :func:`additions` of any, is a bag, and a bag is a key straight
    into :attr:`Vocab.by_letters`. Scanning fifty thousand words per
    token instead would be a hundred times slower and is what the
    first version did.

    The cost of this grows fast in :func:`additions`, which is the
    real reason the ladder stops adding letter noise once it starts
    moving the spaces: with the spaces gone, every substring of the
    line is a token to be looked up, and there are hundreds of those.
    """
    pool = words if words is not None else vocab_for(grade)
    key = (pool.top_rank, _recipe(grade), token)
    if key in _FITS:
        return _FITS[key]
    take, give = removals(grade), additions(grade)
    low, high = len(token) - grade.insert, len(token) + grade.drop
    distinct = sorted(set(token))
    found: set = set()
    for gone in range(take + 1):
        for out in itertools.combinations_with_replacement(distinct, gone):
            left = Counter(token)
            left.subtract(Counter(out))
            if any(count < 0 for count in left.values()):
                continue
            stem = ''.join(sorted(left.elements()))
            for added in range(give + 1):
                if not low <= len(token) - gone + added <= high:
                    continue
                for extra in itertools.combinations_with_replacement(
                        LETTERS, added):
                    for word in pool.by_letters.get(
                            ''.join(sorted(stem + ''.join(extra))), ()):
                        found.add(word)
    if anchored(grade):
        found = {word for word in found
                 if word[:1] == token[:1] and word[-1:] == token[-1:]}
    got = tuple(sorted(found, key=lambda word: pool.rank[word]))
    _FITS[key] = got
    return got


def forget() -> None:
    """Drop the vocabularies and the fit cache. For the tests."""
    _VOCABS.clear()
    _FITS.clear()


# --- doing the corrupting -------------------------------------------------


def scramble_word(grade: Grade, word: str, rng: random.Random) -> str:
    """One word, put through every letter dial *grade* has turned on."""
    letters = list(word)
    for _each in range(min(grade.drop, max(0, len(letters) - 2))):
        letters.pop(rng.randrange(len(letters)))
    if grade.substitute and letters:
        for where in rng.sample(range(len(letters)),
                                min(grade.substitute, len(letters))):
            letters[where] = rng.choice(NEAR_KEYS.get(letters[where], LETTERS))
    for _each in range(grade.insert):
        letters.insert(rng.randrange(len(letters) + 1), rng.choice(LETTERS))
    if grade.whole and len(letters) > 1:
        _shuffled(letters, 0, len(letters), rng)
    elif grade.interior and len(letters) > 3:
        _shuffled(letters, 1, len(letters) - 1, rng)
    for _each in range(grade.swap):
        if len(letters) > 3:
            at = rng.randrange(1, len(letters) - 2)
            letters[at], letters[at + 1] = letters[at + 1], letters[at]
    return ''.join(letters)


def _shuffled(letters: List[str], start: int, stop: int,
              rng: random.Random) -> None:
    """Shuffle a slice in place, trying to actually change it.

    A shuffle that comes back the way it went in is a word that was
    not scrambled, and on a short word that happens often enough to
    notice — one line in five at rung two, before this.
    """
    part = letters[start:stop]
    if len(set(part)) < 2:
        return
    for _try in range(8):
        shuffled = part[:]
        rng.shuffle(shuffled)
        if shuffled != part:
            letters[start:stop] = shuffled
            return
    letters[start:stop] = shuffled


def blocks(count: int, width: int) -> Tuple[Tuple[int, ...], ...]:
    """Index blocks of *width*. Width below two is one index apiece."""
    if width < 2:
        return tuple((one,) for one in range(count))
    return tuple(tuple(range(start, min(start + width, count)))
                 for start in range(0, count, width))


def shuffle_order(grade: Grade, count: int,
                  rng: random.Random) -> Tuple[int, ...]:
    """Which word goes where on the page, as indices into the truth."""
    if grade.order < 2:
        return tuple(range(count))
    out: List[int] = []
    for block in blocks(count, grade.order):
        moved = list(block)
        if len(moved) > 1:
            for _try in range(8):
                rng.shuffle(moved)
                if moved != list(block):
                    break
        out.extend(moved)
    return tuple(out)


def respace(grade: Grade, blob: str, lengths: Sequence[int],
            rng: random.Random) -> Tuple[str, ...]:
    """The line broken up the way it will be shown.

    Moving the gaps means the *same* gaps somewhere else, so the
    chunks are the words' own lengths shuffled and laid back down
    across the line. Cutting at uniformly random points instead —
    which is what this did first — gives one-letter shards and a line
    that reads as noise rather than as a line whose spaces are in the
    wrong places. It also flatters the task: a chunk of one letter is
    obviously not a word, so a bad boundary announced itself.

    Nothing measured changes either way. The reader joins the chunks
    back up before it does anything, so this is for the person.
    """
    if grade.spaces >= 2 or len(blob) < 4:
        return (blob,)
    sizes = list(lengths)
    for _try in range(8):
        rng.shuffle(sizes)
        if sizes != list(lengths):
            break
    out, at = [], 0
    for size in sizes:
        if at >= len(blob):
            break
        out.append(blob[at:at + size])
        at += size
    if at < len(blob):
        out.append(blob[at:])
    return tuple(part for part in out if part)


class Deal(NamedTuple):
    """One corrupted sentence and everything measured about it."""

    grade: Grade
    #: The answer, in the order it was written.
    words: Tuple[str, ...]
    #: Which word of the answer each shown word is, after ``order``.
    placing: Tuple[int, ...]
    #: The corrupted words, in the order they are shown.
    corrupted: Tuple[str, ...]
    #: What is actually printed. More than one chunk means the spaces
    #: are where the corruption left them, not where the words are.
    chunks: Tuple[str, ...]
    #: Base-ten log of the number of readings the letters alone allow.
    #: A floor, not a count, whenever ``spaces`` is on — see the
    #: module docstring.
    ambiguity: float
    #: Words whose letters allow exactly one reading.
    pinned: int

    @property
    def shown(self) -> str:
        return ' '.join(self.chunks)

    @property
    def answer(self) -> str:
        return ' '.join(self.words)

    @property
    def in_view(self) -> Tuple[str, ...]:
        """The true words, in the order they are shown."""
        return tuple(self.words[where] for where in self.placing)


def deal_one(grade: Grade, rng: random.Random,
             text: Optional[Sequence[Sentence]] = None) -> Optional[Deal]:
    """One corrupted sentence at *grade*, or ``None`` with nothing to use."""
    bank = text if text is not None else choose(grade.span, grade.top_rank)
    if not bank:
        return None
    sentence = bank[rng.randrange(len(bank))]
    words = tuple(sentence.words)
    placing = shuffle_order(grade, len(words), rng)
    corrupted = tuple(scramble_word(grade, words[where], rng)
                      for where in placing)
    chunks = (corrupted if grade.spaces < 1
              else respace(grade, ''.join(corrupted),
                           [len(one) for one in corrupted], rng))
    pool = vocab_for(grade)
    counts = [max(1, len(candidates(grade, token, pool)))
              for token in corrupted]
    return Deal(grade, words, placing, corrupted, chunks,
                sum(math.log10(count) for count in counts),
                sum(1 for count in counts if count == 1))


def generate(level_number: int, seed: Optional[int] = None,
             text: Optional[Sequence[Sentence]] = None) -> Optional[Deal]:
    """A deal for *level_number*, one-based into :data:`GRADES`."""
    return deal_one(grade_of(level_number), random.Random(seed), text)


# --- the reader with no idea what a sentence is ---------------------------


def read_off(deal: Deal, words: Optional[Vocab] = None) -> Tuple[str, ...]:
    """What the page says to someone who does not know any English.

    Each token becomes the commonest word whose letters fit. Where the
    spaces have moved this cannot be done a token at a time, so it is
    a shortest-path over the whole line instead, every cut weighed by
    the log rank of the word it makes — which is the same greedy rule
    written out over a lattice rather than a list.

    This is the floor the ladder is measured against. It is not a
    solver and it is not meant to be one: everything it misses is
    exactly the part of the task that needs a reader.
    """
    grade = deal.grade
    pool = words if words is not None else vocab_for(grade)

    def best(token: str) -> Optional[str]:
        fits = candidates(grade, token, pool)
        return fits[0] if fits else None

    if grade.spaces < 1:
        return tuple(best(token) or token for token in deal.chunks)

    blob = ''.join(deal.chunks)
    size = len(blob)
    cost = [math.inf] * (size + 1)
    back: List[Optional[Tuple[int, str]]] = [None] * (size + 1)
    cost[0] = 0.0
    reach = pool.longest + grade.drop
    for start in range(size):
        if cost[start] == math.inf:
            continue
        for stop in range(start + 1, min(size, start + reach) + 1):
            word = best(blob[start:stop])
            if word is None:
                continue
            step = cost[start] + math.log(max(1, pool.rank[word]) + 1.0)
            if step < cost[stop]:
                cost[stop] = step
                back[stop] = (start, word)
    if cost[size] == math.inf:
        return ()
    out: List[str] = []
    at = size
    while at and back[at] is not None:
        at, word = back[at]        # type: ignore[misc]
        out.append(word)
    return tuple(reversed(out))


def read_back(deal: Deal, words: Optional[Vocab] = None) -> float:
    """The share of the sentence :func:`read_off` gets right.

    Scored against the words *in the order they are shown*, so a rung
    that shuffles the words is not also charged for the shuffle. The
    reader identifies; putting the sentence back in order is left to
    whoever can.
    """
    truth = deal.in_view
    got = read_off(deal, words)
    right = sum(1 for one, other in zip(truth, got) if one == other)
    return right / len(truth) if truth else 0.0


# --- marking --------------------------------------------------------------


_TIDY = re.compile(r'[^a-z ]+')


def normalise(text: str) -> str:
    """What a typed answer comes down to: lowercase words and spaces."""
    return ' '.join(_TIDY.sub(' ', text.lower()).split())


def correct(deal: Deal, typed: str) -> bool:
    return normalise(typed) == normalise(deal.answer)


__all__ = ['GRADES', 'LETTERS', 'NEAR_KEYS', 'Deal', 'Grade', 'Vocab',
           'additions', 'anchored', 'bag_distance', 'blocks', 'candidates',
           'correct', 'deal_one', 'feasible', 'forget', 'generate',
           'grade_of', 'normalise', 'read_back', 'read_off', 'removals',
           'respace', 'scramble_word', 'shuffle_order', 'vocab_for']
