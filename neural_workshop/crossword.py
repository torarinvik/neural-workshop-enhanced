# -*- coding: utf-8 -*-
"""Crosswords generated to order, from easy to a fully checked word square.

A crossword is two puzzles wearing one grid. There is the vocabulary
half — do you know a six-letter word for a practice of lending money at
unreasonable rates — and there is the constraint half, where the third
letter of that word is also the first letter of something else and the
two have to be settled together. Which of the two a grid is mostly
testing is set by how many of its cells are crossed, and that is the
axis this ladder is built on.

**A grid here is always fully checked.** Every cell belongs to an
across entry and a down entry, both at least three letters, so every
letter can be reached two ways. That is the American convention rather
than the British one, and it is not a matter of taste: a half-checked
grid has cells that only one clue reaches, and a solver who does not
know that clue has nothing to work with, so the puzzle stops being
solvable by reasoning and becomes a vocabulary quiz with gaps.

The two dials, in the order they matter:

**How long an entry may be.** A grid whose longest entry is four has
short words and a crossing every few letters; take the blocks away
entirely and every row and every column is a word of the full width,
which is a word square and is a different order of thing. The blocks
are placed by splitting the longest run over and over until nothing is
longer than the rung asked for, so a rung names the entry length and
the block count is whatever that took.

Not every length is reachable, and that is geometry rather than
search. A five by five cannot be brought below five: giving every row
an entry of four or less needs a block in every row, and so does every
column, and there is no way to do both without leaving a run of one or
two somewhere. So a five by five is always a word square, and a four
by four is always a word square, and the ladder uses them as such
rather than pretending. Six is the first width with a choice about it.

**Rank band.** Entries are drawn from a slice of the frequency list,
so a rung says both how the grid is shaped and how obscure it is
allowed to be. ``usury`` is rank 22,445 and ``sourish`` is rank
120,000-odd, and no amount of crossing makes the second one fair on a
person.

Those two do not compose the way one would expect, and the measurement
is worth keeping: a nine by nine drawn from the 30,000 commonest words
costs 2.3 seconds to deal and one from the whole list costs 0.8. The
narrow band is the *harder* grid to build, because there are fewer
words to cross with — which is exactly why it is the lower rung. A
rung is not harder to solve because it was harder to deal.

Then two smaller dials. Some cells can be given away at the start,
which is the whole of the gentle end; and clues can be **withheld**,
which is the whole of the far end. An entry with no clue has to be got
from its crossings alone, and a grid where half the clues are missing
is a constraint problem with a vocabulary prior — the point at which
"hard" stops meaning "knows more words".

What is *not* on the ladder is a six by six word square. Thirty-six
letters, every one of them in two words at once, out of the 15,700 six
letter words the pool holds: twenty million candidate placements found
none, and the literature finds them with dictionaries several times
this one. The top of this ladder is a five by five square with two
clues in five withheld, which is hard enough to be interesting and can
actually be dealt.

Generation fills across entries row by row, so every down entry is
filled contiguously from its top and can be checked against the pool's
prefix set the moment a row closes. Dead branches die at the row that
killed them rather than at the bottom of the grid. Cells are indexed
``row * size + column``, a block is an empty string in the solution,
and the whole thing is a flat tuple the screen draws straight from.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

from .wordlist import Lexicon, pool

#: The shortest entry a fully checked grid may hold. Two-letter entries
#: are legal in some traditions and they are the ones nobody can clue.
MIN_ENTRY = 3


class Slot(NamedTuple):
    """One entry: where it runs, what it is, and what is said about it."""

    number: int
    down: bool
    cells: Tuple[int, ...]
    word: str
    #: Empty when this rung withheld it. Not the same as having no
    #: clue in the pool — the pool always has one.
    clue: str

    @property
    def length(self) -> int:
        return len(self.cells)


class Puzzle(NamedTuple):
    """A dealt crossword: the shape, the answer, and what is on show."""

    size: int
    #: Cells with no letter in them.
    blocks: frozenset
    #: One letter a cell, ``''`` where the grid is blocked.
    solution: Tuple[str, ...]
    slots: Tuple[Slot, ...]
    #: Cells whose letter is written in before the player starts.
    givens: frozenset
    #: What it cost to find this grid, in candidate words tried. Junior
    #: to everything else and reported because a rung that is expensive
    #: to deal is worth knowing about before the screen freezes.
    tried: int

    def blanks(self) -> int:
        return sum(1 for cell, letter in enumerate(self.solution)
                   if letter and cell not in self.givens)

    def unclued(self) -> int:
        return sum(1 for slot in self.slots if not slot.clue)


class Grade(NamedTuple):
    """One rung of the ladder."""

    name: str
    size: int
    #: The longest entry the grid may hold. At or above *size* nothing
    #: is blocked at all and every row and column is a word, which is a
    #: word square rather than a crossword.
    longest_entry: int
    #: The rank band entries are drawn from.
    top_rank: int
    #: Cells written in before the player starts, as a share of the
    #: blanks. The gentle end of the ladder is almost entirely this.
    given: float
    #: Share of entries whose clue is withheld. The far end is this.
    withheld: float
    #: Candidate words to try before giving up and reshaping the grid.
    #: A budget rather than a stopwatch, so the same seed deals the
    #: same puzzle on any machine.
    tries: int = 4000


#: Gentle to superhuman. Every one of these was measured rather than
#: guessed — the deal costs and the fill rates are in
#: ``tests/bench_words.py``, and the ladder was moved twice by what it
#: said.
GRADES: Tuple[Grade, ...] = (
    #                          size  entry   rank    given  withheld  tries
    Grade('first crossing',       4,    4,     3000,  0.50,   0.00,    60000),
    Grade('a small grid',         6,    4,    10000,  0.30,   0.00,   120000),
    Grade('a proper one',         7,    5,    10000,  0.15,   0.00,   400000),
    Grade('wider',                9,    6,    30000,  0.08,   0.00,  6000000),
    Grade('no help',              9,    6,    30000,  0.00,   0.00,  6000000),
    Grade('bookish',              9,    6,  1 << 30,  0.00,   0.00,  6000000),
    Grade('a clue short',         9,    6,  1 << 30,  0.00,   0.25,  6000000),
    Grade('the square',           5,    5,    30000,  0.00,   0.00,  4000000),
    Grade('a square, half said',  5,    5,  1 << 30,  0.00,   0.40,  4000000),
    Grade('half of it unsaid',    9,    6,  1 << 30,  0.00,   0.50,  6000000),
)

#: Grids to try before giving up on a rung. The budget is split
#: between them rather than pooled, because a grid that cannot be
#: filled will happily eat a whole rung's budget proving it, and the
#: answer is nearly always in the next grid rather than deeper in this
#: one. Measured: pooled, a seven by seven dealt none out of eight;
#: split twelve ways, eight out of eight.
RESTARTS = 12

#: Longest entry the generator will attempt. Past this the pool thins
#: out faster than the crossing constrains it and a fill turns into a
#: search for the one word of that length that fits.
MAX_ENTRY = 11


def grade_of(rung: int) -> Grade:
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


# --- the shape ------------------------------------------------------------


def runs(size: int, blocks: Set[int], down: bool) -> List[Tuple[int, ...]]:
    """Every maximal unblocked run in one direction, in reading order."""
    found: List[Tuple[int, ...]] = []
    for line in range(size):
        current: List[int] = []
        for step in range(size):
            cell = (step * size + line) if down else (line * size + step)
            if cell in blocks:
                if current:
                    found.append(tuple(current))
                current = []
            else:
                current.append(cell)
        if current:
            found.append(tuple(current))
    return found


def well_formed(size: int, blocks: Set[int]) -> bool:
    """Whether every run in both directions is long enough to be an entry.

    A run of one or two is what makes a grid unbuildable rather than
    hard: a single cell is an entry nobody can clue, and it is also a
    cell only one direction reaches, which is the half-checked grid
    this module refuses to deal.

    Only the floor, deliberately. This once checked a ceiling too, and
    that quietly stopped :func:`shape` from working on anything wider
    than the ceiling: an empty thirteen by thirteen is already over it,
    every single block leaves it still over it, and so every step of
    the growth was rolled back and the grid came out empty. A ceiling
    is a property of the rung being aimed at, not of a legal grid.
    """
    for down in (False, True):
        for run in runs(size, blocks, down):
            if len(run) < MIN_ENTRY:
                return False
    return True


def connected(size: int, blocks: Set[int]) -> bool:
    """Whether the unblocked cells are one piece."""
    open_cells = [cell for cell in range(size * size) if cell not in blocks]
    if not open_cells:
        return False
    seen = {open_cells[0]}
    stack = [open_cells[0]]
    while stack:
        cell = stack.pop()
        row, col = divmod(cell, size)
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            r, c = row + dr, col + dc
            near = r * size + c
            if 0 <= r < size and 0 <= c < size and near not in blocks \
                    and near not in seen:
                seen.add(near)
                stack.append(near)
    return len(seen) == len(open_cells)


def longest(size: int, blocks: Set[int]) -> int:
    """The longest run either way, which is what a block count is for."""
    return max((len(run) for down in (False, True)
                for run in runs(size, blocks, down)), default=0)


def split_points(length: int) -> Tuple[int, ...]:
    """Where a block may go in a run of *length*, leaving legal pieces.

    Either end, which shortens the run by one, or far enough inside to
    leave an entry on both sides. The middle of a five is neither: it
    would leave a two, and a two-letter entry is the thing
    :data:`MIN_ENTRY` exists to refuse. Leaving the ends out of this
    was why nothing above rung one dealt at all — a run of five has no
    interior split, so a five-by-five could never be broken up and came
    out as a word square wearing a crossword's rung.
    """
    ends = [at for at in (0, length - 1) if length - 1 >= MIN_ENTRY]
    inside = [at for at in range(MIN_ENTRY, length - MIN_ENTRY)]
    return tuple(dict.fromkeys(ends + inside))


def shape(size: int, longest_entry: int, rng: random.Random,
          attempts: int = 600) -> frozenset:
    """A block pattern with 180-degree symmetry and no run past *longest_entry*.

    Written this way after the obvious version failed to deal anything
    above rung one. Scattering a fixed *share* of blocks at random and
    keeping whatever stayed well formed put nearly all of them on the
    edges — a block in the middle of an empty grid leaves a run of one
    somewhere far more often than one in a corner does — so a nine by
    nine came out as a nine by nine word square with the corners
    nibbled, which is not an ordinary crossword and cannot be filled.

    So the blocks are aimed instead of scattered: find the longest run,
    split it, repeat. What comes out is a grid of three-to-*n* letter
    entries crossing each other, which is what a crossword is, and the
    block count is whatever that took rather than a number chosen in
    advance.
    """
    if longest_entry >= size:
        return frozenset()
    blocks: Set[int] = set()
    for _try in range(attempts):
        if longest(size, blocks) <= longest_entry:
            break
        worst = max((run for down in (False, True)
                     for run in runs(size, blocks, down)), key=len)
        if len(worst) <= longest_entry:
            break
        cuts = list(split_points(len(worst)))
        if not cuts:
            break
        rng.shuffle(cuts)
        for at in cuts:
            cell = worst[at]
            twin = size * size - 1 - cell
            if cell in blocks or twin in blocks:
                continue
            blocks.update((cell, twin))
            if well_formed(size, blocks) and connected(size, blocks):
                break
            blocks.difference_update((cell, twin))
        else:
            break
    return frozenset(blocks)


def a_shape(size: int, longest_entry: int, rng: random.Random,
            attempts: int = 40) -> frozenset:
    """A block pattern that really does come down to *longest_entry*.

    :func:`shape` aims and does not always land — at eleven by eleven
    it reaches an entry of six about two times in five, and the rest
    of the time leaves a seven or an eleven somewhere. Those are legal
    grids and much harder to fill, and a deal that accepted them spent
    its whole budget on the hard ones and came back empty two times in
    eight. Reshaping is free, so it is done until the shape is the one
    that was asked for.
    """
    best = frozenset()
    for _try in range(attempts):
        made = shape(size, longest_entry, rng)
        if longest(size, set(made)) <= longest_entry:
            return made
        if not best or longest(size, set(made)) < longest(size, set(best)):
            best = made
    return best


def number(size: int, blocks: Set[int]) -> Dict[int, int]:
    """Cell to printed number, for the cells an entry starts at."""
    numbers: Dict[int, int] = {}
    count = 0
    for cell in range(size * size):
        if cell in blocks:
            continue
        row, col = divmod(cell, size)
        starts_across = (col == 0 or cell - 1 in blocks)
        starts_down = (row == 0 or cell - size in blocks)
        if starts_across or starts_down:
            count += 1
            numbers[cell] = count
    return numbers


# --- the fill -------------------------------------------------------------


class _Budget:
    """Candidate words left to try, shared by every branch of the fill."""

    def __init__(self, tries: int) -> None:
        self.left = int(tries)
        self.spent = 0

    def take(self) -> bool:
        self.spent += 1
        self.left -= 1
        return self.left > 0


def _down_runs(size: int, blocks: Set[int]) -> Dict[int, Tuple[int, ...]]:
    """Cell to the down run it belongs to."""
    owner: Dict[int, Tuple[int, ...]] = {}
    for run in runs(size, blocks, True):
        for cell in run:
            owner[cell] = run
    return owner


def fill(size: int, blocks: frozenset, words: Lexicon, rng: random.Random,
         budget: _Budget) -> Optional[List[str]]:
    """Letters for every unblocked cell, or ``None`` if none was found.

    Across entries are filled in reading order, so a down entry always
    holds a contiguous run from its own top and can be tested against
    the pool's prefix set the instant a row closes. A branch that has
    made a column impossible dies at that row rather than at the bottom
    of the grid, which is the difference between a six-by-six square
    taking a second and taking all afternoon.
    """
    across = [run for run in runs(size, blocks, False)]
    down_of = _down_runs(size, blocks)
    grid: List[str] = ['' if cell in blocks else '.'
                       for cell in range(size * size)]

    def columns_alive(touched: Sequence[int]) -> bool:
        for run in {down_of[cell] for cell in touched}:
            so_far = ''
            for cell in run:
                if grid[cell] == '.':
                    break
                so_far += grid[cell]
            if not so_far:
                continue
            if len(so_far) == len(run):
                if not words.valid(so_far):
                    return False
            elif so_far not in words.prefixes(len(run)):
                return False
        return True

    def place(at: int) -> bool:
        if at >= len(across):
            return True
        run = across[at]
        pattern = ''.join(grid[cell] for cell in run)
        options = list(words.fitting(pattern))
        rng.shuffle(options)
        for option in options:
            if not budget.take():
                return False
            for cell, letter in zip(run, option.word):
                grid[cell] = letter
            if columns_alive(run) and place(at + 1):
                return True
            for cell, letter in zip(run, pattern):
                grid[cell] = letter
        return False

    return grid if place(0) else None


# --- dealing --------------------------------------------------------------


def deal_one(grade: Grade, rng: random.Random,
             words: Optional[Lexicon] = None) -> Optional[Puzzle]:
    """One puzzle at *grade*, or ``None`` if the budget ran out."""
    lengths = range(MIN_ENTRY, min(MAX_ENTRY, grade.size) + 1)
    pooled = words if words is not None else pool(grade.top_rank)
    narrow = pooled.narrowed(hi=grade.top_rank, lengths=tuple(lengths))
    tried = 0
    ceiling = min(grade.longest_entry, max(lengths))
    for _restart in range(RESTARTS):
        budget = _Budget(max(1, grade.tries // RESTARTS))
        blocks = a_shape(grade.size, ceiling, rng)
        if not well_formed(grade.size, set(blocks)):
            continue
        if longest(grade.size, set(blocks)) > ceiling:
            # The grid would not come down to the entry length this
            # rung asked for. A legal crossword, but a harder one than
            # the rung promised and one the narrowed pool may hold no
            # words long enough for, so it is dropped rather than
            # filled. Free: nothing was spent on it.
            continue
        letters = fill(grade.size, blocks, narrow, rng, budget)
        tried += budget.spent
        if letters is None:
            continue
        return _dress(grade, blocks, letters, narrow, rng,
                      tried + budget.spent)
    return None


def _dress(grade: Grade, blocks: frozenset, letters: Sequence[str],
           words: Lexicon, rng: random.Random, tried: int) -> Puzzle:
    """Number the grid, attach clues, and give some of it away."""
    size = grade.size
    numbers = number(size, set(blocks))
    slots: List[Slot] = []
    for down in (False, True):
        for run in runs(size, set(blocks), down):
            word = ''.join(letters[cell] for cell in run)
            slots.append(Slot(numbers.get(run[0], 0), down, run, word,
                              words.clue(word)))
    slots.sort(key=lambda one: (one.number, one.down))

    hush = int(round(len(slots) * grade.withheld))
    if hush:
        for at in rng.sample(range(len(slots)), hush):
            slots[at] = slots[at]._replace(clue='')

    open_cells = [cell for cell in range(size * size) if cell not in blocks]
    handed = int(round(len(open_cells) * grade.given))
    givens = frozenset(rng.sample(open_cells, handed)) if handed else frozenset()
    return Puzzle(size, blocks, tuple(letters), tuple(slots), givens, tried)


def generate(level_number: int, seed: Optional[int] = None,
             words: Optional[Lexicon] = None) -> Optional[Puzzle]:
    """A puzzle for *level_number*, one-based into :data:`GRADES`."""
    grade = grade_of(level_number)
    rng = random.Random(seed)
    return deal_one(grade, rng, words)


__all__ = ['GRADES', 'MAX_ENTRY', 'MIN_ENTRY', 'Grade', 'Puzzle', 'Slot',
           'connected', 'deal_one', 'fill', 'generate', 'grade_of', 'number',
           'runs', 'shape', 'well_formed']
