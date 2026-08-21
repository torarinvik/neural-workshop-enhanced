# -*- coding: utf-8 -*-
"""Sudoku, rated by what it actually takes to solve rather than by holes.

Counting the blanks is the obvious way to grade a sudoku and it is very
nearly worthless: a puzzle with twenty-two givens can fall to nothing
but "this cell has one candidate left" twenty-two times over, while one
with thirty can need a fish. What a puzzle *costs* is the deepest
technique it forces, so that is what this module measures and what the
ladder is built out of.

The rating is done by solving. :func:`rate` runs a stack of techniques
in increasing order of difficulty, always applying the cheapest one
that changes anything, and reports the deepest it had to reach:

===  ==========================  ===================================
  0  naked single                one candidate left in a cell
  1  hidden single               one home left in a unit for a digit
  2  locked candidates           a digit boxed into one line, or the
                                 reverse
  3  naked subset                *k* cells holding only *k* digits
  4  hidden subset               *k* digits living in only *k* cells
  5  fish                        x-wing and its bigger cousins
  6  search                      this module's logic ran out
===  ==========================  ===================================

Tier six is the honest one. It does not mean "no logic could do it" --
somebody's chain solver would get further -- it means the reasoning
written down here is exhausted and the rest is trial. Puzzles that
reach it also carry :attr:`Puzzle.guesses`, the number of branch points
a propagating search still had to guess at, and that number keeps
climbing long after the techniques have stopped distinguishing
anything. It is what the top of the ladder is graded on.

Size is the other dial, and it is structural rather than measured: a
box of two is a four by four, three is the usual nine, four is a
sixteen by sixteen on digits 1-9 and A-G. Sixteens are where
"superhuman" stops being a figure of speech -- the same tier of
technique over two hundred and fifty-six cells is a different
proposition from over eighty-one.

Cells are indexed ``row * size + column`` and a blank is ``0``, so a
grid is a flat tuple the screen can draw straight from.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from itertools import combinations
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: The techniques, cheapest first. The index into this is a puzzle's
#: tier, and the last entry is not a technique but the admission that
#: the ones before it were not enough.
TECHNIQUES: Tuple[str, ...] = (
    'naked single', 'hidden single', 'locked candidates',
    'naked subset', 'hidden subset', 'fish', 'search',
)
SEARCH_TIER = len(TECHNIQUES) - 1

#: The largest subset and fish this module looks for. Four would find a
#: little more and costs a great deal more on a sixteen; measured, it
#: moved no rung of the ladder.
WIDEST_SUBSET = 3
WIDEST_FISH = 3

#: Box sizes the palette and the keyboard can carry: 4x4, 9x9, 16x16.
BOXES: Tuple[int, ...] = (2, 3, 4)


class Puzzle(NamedTuple):
    """A dealt puzzle: what is shown, what it comes to, and what it cost."""

    box: int
    #: The grid as dealt, ``0`` for a blank.
    givens: Tuple[int, ...]
    #: The one grid it comes to. Every puzzle here has exactly one.
    solution: Tuple[int, ...]
    #: Deepest technique the rating solver had to reach; an index into
    #: :data:`TECHNIQUES`.
    tier: int
    #: Branch points a propagating search still had to guess at once
    #: the techniques ran out. Zero for anything logic finished.
    guesses: int

    @property
    def size(self) -> int:
        return self.box * self.box

    def blanks(self) -> int:
        return sum(1 for value in self.givens if not value)


class Grade(NamedTuple):
    """One rung: the size, and the band a deal has to land in.

    A band rather than a floor, and that is a measurement talking. Over
    four hundred minimal nine-by-nines the tiers came out 0.8, 38, 12,
    6.8, 1.2, 0.5 and 40 per cent -- so "at least tier two" is
    satisfied four times in ten by a puzzle the logic cannot finish at
    all, and a rung asking for *moderate* would keep dealing
    *diabolical*. Asking for a band is the only way a middle rung can
    mean anything.
    """

    name: str
    box: int
    #: Lowest and highest tier this rung will accept, inclusive.
    floor: int
    ceiling: int
    #: The junior axis: the fewest branch points a search may still
    #: need once the logic has run out. Only meaningful at the search
    #: tier, and never allowed to outrank the band.
    guesses: int = 0
    #: Stop digging with this many givens still on the board; ``0``
    #: digs until nothing more will come out. This is the whole lever
    #: for the easy end -- a puzzle dug to minimal is nearly always
    #: hard, so gentleness is reached by stopping early rather than by
    #: hoping for it.
    keep: int = 0
    #: How many deals to spend looking for this rung's band. Per rung
    #: rather than one number for the ladder, because a deal costs a
    #: hundredth of a second on a nine and two seconds on a dug-out
    #: sixteen -- a budget that is thrifty for one is a four-minute
    #: wait for the other. A count and not a stopwatch, so the same
    #: seed deals the same puzzle on any machine.
    tries: int = 60


#: Extremely easy to superhuman. Every floor here was measured rather
#: than guessed -- see the calibration in :mod:`tests.test_sudoku` --
#: and the two axes are ranked, not merged: the tier is what the rung
#: promises and what the screen reports, and the guess floor only
#: picks between puzzles that already clear it.
GRADES: Tuple[Grade, ...] = (
    #                     box  floor  ceil  guess  keep  tries
    Grade('first squares',  2,   0,    0,     0,     0,    20),
    Grade('gentle',         3,   0,    0,     0,    45,    30),
    Grade('easy',           3,   1,    1,     0,    32,    60),
    Grade('moderate',       3,   2,    2,     0,     0,   120),
    Grade('tricky',         3,   3,    3,     0,     0,   120),
    Grade('hard',           3,   4,    5,     0,     0,   200),
    Grade('fiendish',       3,   6,    6,     1,     0,    60),
    Grade('diabolical',     3,   6,    6,     8,     0,   150),
    Grade('the sixteen',    4,   0,    1,     0,   150,    10),
    Grade('sixteen hard',   4,   1,    1,     0,   120,    10),
    Grade('inhuman',        4,   3,    6,     0,   110,    20),
    Grade('superhuman',     4,   6,    6,    40,   100,     4),
)

_UNITS: Dict[int, Tuple[Tuple[int, ...], ...]] = {}
_PEERS: Dict[int, Tuple[Tuple[int, ...], ...]] = {}
_UNITS_OF: Dict[int, Tuple[Tuple[int, ...], ...]] = {}


def units(box: int) -> Tuple[Tuple[int, ...], ...]:
    """Every row, column and box, as tuples of cell indices."""
    if box not in _UNITS:
        size = box * box
        rows = [tuple(r * size + c for c in range(size)) for r in range(size)]
        cols = [tuple(r * size + c for r in range(size)) for c in range(size)]
        boxes = []
        for band in range(box):
            for stack in range(box):
                boxes.append(tuple(
                    (band * box + r) * size + stack * box + c
                    for r in range(box) for c in range(box)))
        _UNITS[box] = tuple(rows + cols + boxes)
    return _UNITS[box]


def peers(box: int) -> Tuple[Tuple[int, ...], ...]:
    """For each cell, every other cell that shares a unit with it."""
    if box not in _PEERS:
        size = box * box
        found: List[set] = [set() for _cell in range(size * size)]
        for unit in units(box):
            for cell in unit:
                found[cell].update(unit)
        for cell, group in enumerate(found):
            group.discard(cell)
        _PEERS[box] = tuple(tuple(sorted(group)) for group in found)
    return _PEERS[box]


def units_of(box: int) -> Tuple[Tuple[int, ...], ...]:
    """For each cell, the indices of the units it belongs to."""
    if box not in _UNITS_OF:
        size = box * box
        found: List[List[int]] = [[] for _cell in range(size * size)]
        for index, unit in enumerate(units(box)):
            for cell in unit:
                found[cell].append(index)
        _UNITS_OF[box] = tuple(tuple(group) for group in found)
    return _UNITS_OF[box]


def _bits(mask: int) -> List[int]:
    """The digits (1-based) a candidate mask holds."""
    out, digit = [], 1
    while mask:
        if mask & 1:
            out.append(digit)
        mask >>= 1
        digit += 1
    return out


def candidates(grid: Sequence[int], box: int) -> Optional[List[int]]:
    """A candidate mask per cell, or None when the grid contradicts itself."""
    size = box * box
    every = (1 << size) - 1
    cand = [every] * len(grid)
    for cell, value in enumerate(grid):
        if value:
            cand[cell] = 1 << (value - 1)
    near = peers(box)
    for cell, value in enumerate(grid):
        if not value:
            continue
        bit = 1 << (value - 1)
        for other in near[cell]:
            if grid[other]:
                if grid[other] == value:
                    return None
            else:
                cand[other] &= ~bit
                if not cand[other]:
                    return None
    return cand


def _assign(grid: List[int], cand: List[int], box: int, cell: int,
            digit: int) -> bool:
    """Put *digit* in *cell* and strike it from the neighbours."""
    grid[cell] = digit
    bit = 1 << (digit - 1)
    cand[cell] = bit
    for other in peers(box)[cell]:
        if not grid[other] and cand[other] & bit:
            cand[other] &= ~bit
            if not cand[other]:
                return False
    return True


# --- the techniques ---------------------------------------------------

#: What a technique reports back. ``True`` it changed something,
#: ``False`` it found nothing to do, ``None`` the grid contradicts
#: itself. Three states rather than two, because "nothing to do" and
#: "this puzzle is broken" are opposite answers and telling them apart
#: by watching the candidates for a change is both slow and a lie --
#: an elimination that empties a cell changes it too.
Verdict = Optional[bool]


def _strike(cand: List[int], cell: int, bits: int) -> Verdict:
    """Take *bits* out of a cell. None when that leaves it with nothing."""
    cand[cell] &= ~bits
    return True if cand[cell] else None


def _naked_single(grid: List[int], cand: List[int], box: int) -> Verdict:
    for cell, value in enumerate(grid):
        if value:
            continue
        mask = cand[cell]
        if not mask:
            return None
        if not mask & (mask - 1):
            return True if _assign(grid, cand, box, cell,
                                   mask.bit_length()) else None
    return False


def _hidden_single(grid: List[int], cand: List[int], box: int) -> Verdict:
    size = box * box
    for unit in units(box):
        placed = 0
        for cell in unit:
            if grid[cell]:
                placed |= 1 << (grid[cell] - 1)
        for digit in range(1, size + 1):
            bit = 1 << (digit - 1)
            if placed & bit:
                continue
            homes = [c for c in unit if not grid[c] and cand[c] & bit]
            if not homes:
                return None                # a digit with nowhere to go
            if len(homes) == 1:
                return True if _assign(grid, cand, box, homes[0],
                                       digit) else None
    return False


def _locked_candidates(grid: List[int], cand: List[int], box: int) -> Verdict:
    """A digit boxed into one line, or confined to one box by a line.

    Which row, column or box a set of cells shares is arithmetic, so it
    is computed rather than found by trying every unit against every
    other -- on a sixteen that is the difference between this technique
    costing nothing and costing more than the rest put together.
    """
    size = box * box
    every = units(box)
    rows, cols, boxes = every[:size], every[size:2 * size], every[2 * size:]

    def box_of(cell: int) -> int:
        return (cell // size // box) * box + (cell % size) // box

    for digit in range(1, size + 1):
        bit = 1 << (digit - 1)
        for unit in boxes:                 # pointing: box -> line
            spots = [c for c in unit if not grid[c] and cand[c] & bit]
            if len(spots) < 2:
                continue
            for line in (rows[spots[0] // size]
                         if len({c // size for c in spots}) == 1 else None,
                         cols[spots[0] % size]
                         if len({c % size for c in spots}) == 1 else None):
                if line is None:
                    continue
                held = set(spots)
                touched = False
                for cell in line:
                    if cell not in held and not grid[cell] and cand[cell] & bit:
                        if _strike(cand, cell, bit) is None:
                            return None
                        touched = True
                if touched:
                    return True
        for unit in rows + cols:           # claiming: line -> box
            spots = [c for c in unit if not grid[c] and cand[c] & bit]
            if len(spots) < 2 or len({box_of(c) for c in spots}) != 1:
                continue
            held = set(spots)
            touched = False
            for cell in boxes[box_of(spots[0])]:
                if cell not in held and not grid[cell] and cand[cell] & bit:
                    if _strike(cand, cell, bit) is None:
                        return None
                    touched = True
            if touched:
                return True
    return False


def _naked_subset(grid: List[int], cand: List[int], box: int) -> Verdict:
    for unit in units(box):
        open_cells = [c for c in unit if not grid[c]]
        for width in range(2, WIDEST_SUBSET + 1):
            small = [c for c in open_cells if bin(cand[c]).count('1') <= width]
            for group in combinations(small, width):
                shared = 0
                for cell in group:
                    shared |= cand[cell]
                if bin(shared).count('1') != width:
                    continue
                held = set(group)
                touched = False
                for cell in open_cells:
                    if cell not in held and cand[cell] & shared:
                        if _strike(cand, cell, shared) is None:
                            return None
                        touched = True
                if touched:
                    return True
    return False


def _hidden_subset(grid: List[int], cand: List[int], box: int) -> Verdict:
    size = box * box
    for unit in units(box):
        open_cells = [c for c in unit if not grid[c]]
        homes = {}
        for digit in range(1, size + 1):
            bit = 1 << (digit - 1)
            spots = tuple(c for c in open_cells if cand[c] & bit)
            if spots:
                homes[digit] = spots
        for width in range(2, WIDEST_SUBSET + 1):
            fitting = [d for d, spots in homes.items() if len(spots) <= width]
            for group in combinations(fitting, width):
                shared = set()
                for digit in group:
                    shared.update(homes[digit])
                if len(shared) != width:
                    continue
                keep = 0
                for digit in group:
                    keep |= 1 << (digit - 1)
                touched = False
                for cell in shared:
                    if cand[cell] & ~keep:
                        if _strike(cand, cell, ~keep) is None:
                            return None
                        touched = True
                if touched:
                    return True
    return False


def _fish(grid: List[int], cand: List[int], box: int) -> Verdict:
    """X-wing and its bigger cousins, both ways round.

    *width* lines that hold a digit between them in only *width* lanes
    own those lanes, so the digit comes out of every other cell in
    them.
    """
    size = box * box
    every = units(box)
    rows, cols = every[:size], every[size:2 * size]
    for digit in range(1, size + 1):
        bit = 1 << (digit - 1)
        for base, cover in ((rows, cols), (cols, rows)):
            spots = []
            for index, line in enumerate(base):
                where = [pos for pos, cell in enumerate(line)
                         if not grid[cell] and cand[cell] & bit]
                if len(where) >= 2:
                    spots.append((index, where))
            for width in range(2, WIDEST_FISH + 1):
                narrow = [s for s in spots if len(s[1]) <= width]
                for group in combinations(narrow, width):
                    lanes = set()
                    for _index, where in group:
                        lanes.update(where)
                    if len(lanes) != width:
                        continue
                    mine = {index for index, _where in group}
                    touched = False
                    for lane in lanes:
                        for pos, cell in enumerate(cover[lane]):
                            if pos in mine or grid[cell]:
                                continue
                            if cand[cell] & bit:
                                if _strike(cand, cell, bit) is None:
                                    return None
                                touched = True
                    if touched:
                        return True
    return False


_LOGIC = (_naked_single, _hidden_single, _locked_candidates,
          _naked_subset, _hidden_subset, _fish)


# --- solving and rating -----------------------------------------------

def _logic_solve(grid: List[int], cand: List[int],
                 box: int) -> Tuple[int, bool]:
    """Run the stack to a standstill. Returns the deepest tier and sanity.

    Always the cheapest technique that does anything, and back to the
    top of the stack after every one that does -- which is what makes
    the tier a floor on the puzzle rather than an artefact of the
    order things were tried in.
    """
    deepest = 0
    while any(not value for value in grid):
        moved = False
        for tier, technique in enumerate(_LOGIC):
            got = technique(grid, cand, box)
            if got is None:
                return deepest, False          # a contradiction fell out
            if got:
                deepest = max(deepest, tier)
                moved = True
                break
        if not moved:
            break
    return deepest, True


def _propagate(grid: List[int], cand: List[int], box: int) -> bool:
    """Naked and hidden singles to a fixpoint. False on a contradiction.

    Not a rater -- it makes no attempt to say which technique did what,
    and it is not used for rating. It exists because the search needs
    to be *cheap*, and a search that only forces naked singles branches
    far more than it has to. Measured on a sixteen, adding the hidden
    singles here took a uniqueness check from twenty-one seconds to
    under a hundredth of one.
    """
    size = box * box
    every = (1 << size) - 1
    moving = True
    while moving:
        moving = False
        for cell, value in enumerate(grid):
            if value:
                continue
            mask = cand[cell]
            if not mask:
                return False
            if not mask & (mask - 1):
                if not _assign(grid, cand, box, cell, mask.bit_length()):
                    return False
                moving = True
        for unit in units(box):
            once = twice = placed = 0
            for cell in unit:
                value = grid[cell]
                if value:
                    placed |= 1 << (value - 1)
                    continue
                mask = cand[cell]
                twice |= once & mask
                once |= mask
            if every & ~placed & ~once:
                return False           # a digit with nowhere left to go
            alone = once & ~twice
            while alone:
                bit = alone & -alone
                alone ^= bit
                for cell in unit:
                    if not grid[cell] and cand[cell] & bit:
                        if not _assign(grid, cand, box, cell,
                                       bit.bit_length()):
                            return False
                        moving = True
                        break
    return True


def _search(grid: List[int], cand: List[int], box: int,
            limit: int = 2) -> Tuple[int, List[List[int]]]:
    """Propagating depth-first search. Returns guesses and up to *limit* wins."""
    guesses = [0]
    found: List[List[int]] = []

    def walk(grid: List[int], cand: List[int]) -> None:
        if len(found) >= limit:
            return
        if not _propagate(grid, cand, box):
            return
        open_cells = [c for c, value in enumerate(grid) if not value]
        if not open_cells:
            found.append(list(grid))
            return
        cell = min(open_cells, key=lambda c: bin(cand[c]).count('1'))
        choices = _bits(cand[cell])
        if len(choices) > 1:
            guesses[0] += 1
        for digit in choices:
            ahead, spare = list(grid), list(cand)
            if _assign(ahead, spare, box, cell, digit):
                walk(ahead, spare)
            if len(found) >= limit:
                return

    walk(list(grid), list(cand))
    return guesses[0], found


def solutions(givens: Sequence[int], box: int,
              limit: int = 2) -> List[Tuple[int, ...]]:
    """Up to *limit* complete grids the givens allow."""
    cand = candidates(givens, box)
    if cand is None:
        return []
    return [tuple(found)
            for found in _search(list(givens), cand, box, limit)[1]]


def rate(givens: Sequence[int], box: int) -> Tuple[int, int]:
    """The deepest technique this puzzle forces, and the guesses left over.

    ``(SEARCH_TIER, n)`` when the stack runs dry with *n* branch points
    still to guess at; ``(tier, 0)`` when the logic finished it.
    """
    cand = candidates(givens, box)
    if cand is None:
        return SEARCH_TIER, 0
    grid = list(givens)
    deepest, sane = _logic_solve(grid, cand, box)
    if sane and all(grid):
        return deepest, 0
    guesses, found = _search(list(givens), candidates(givens, box), box, 1)
    return SEARCH_TIER, guesses if found else 0


# --- generation --------------------------------------------------------

#: Branches a single attempt at filling a grid may take before it is
#: abandoned and started over. A fill normally finishes in a few
#: hundred; a run of bad luck on a sixteen can otherwise backtrack
#: essentially for ever -- measured, one seed in a handful took two
#: hundred and sixteen seconds where its neighbours took four
#: thousandths of one. Restarting is not a heuristic to tune, it is
#: the difference between bounded and unbounded.
FILL_BUDGET = 20000


def _full_grid(box: int, rng: random.Random) -> List[int]:
    """One complete, valid grid, chosen at random.

    Randomised depth-first, but propagating after every placement and
    giving up on an attempt that goes too deep rather than backtracking
    out of it. Both matter: propagation finds the dead ends early, and
    the restart bounds what happens when it does not.
    """
    size = box * box
    while True:
        grid = [0] * (size * size)
        cand = candidates(grid, box)
        assert cand is not None
        spent = [0]

        def walk(grid: List[int], cand: List[int]) -> Optional[List[int]]:
            if spent[0] > FILL_BUDGET:
                return None
            if not _propagate(grid, cand, box):
                return None
            open_cells = [c for c, value in enumerate(grid) if not value]
            if not open_cells:
                return grid
            cell = min(open_cells, key=lambda c: bin(cand[c]).count('1'))
            choices = _bits(cand[cell])
            rng.shuffle(choices)
            for digit in choices:
                spent[0] += 1
                if spent[0] > FILL_BUDGET:
                    return None
                ahead, spare = list(grid), list(cand)
                if _assign(ahead, spare, box, cell, digit):
                    got = walk(ahead, spare)
                    if got is not None:
                        return got
            return None

        got = walk(grid, cand)
        if got is not None:
            return got


def _still_only_one(givens: List[int], box: int, cell: int,
                    held: int) -> bool:
    """Whether blanking *cell* leaves the puzzle with one solution still.

    Asked the cheap way round. Counting solutions and checking there is
    exactly one means proving a second does not exist, which is a whole
    exhausted search tree; asking instead whether any *particular* other
    digit fits in the blanked cell pins that cell first, and a pinned
    cell prunes so hard that nearly every one of these dies during
    propagation. Measured on a sixteen, this took digging from thirty
    seconds a puzzle to under one.
    """
    cand = candidates(givens, box)
    if cand is None:
        return False
    for digit in _bits(cand[cell]):
        if digit == held:
            continue
        trial = list(givens)
        trial[cell] = digit
        if solutions(trial, box, 1):
            return False               # a second solution: put it back
    return True


def _dig(full: Sequence[int], box: int, rng: random.Random,
         keep: int = 0) -> List[int]:
    """Blank as many cells as will still leave exactly one solution.

    *keep* stops early with that many givens left, which is what makes
    an easy rung easy: a puzzle dug all the way out is nearly always a
    hard one, so the gentle end of the ladder is reached by stopping.
    """
    givens = list(full)
    order = list(range(len(givens)))
    rng.shuffle(order)
    filled = len(givens)
    for cell in order:
        if keep and filled <= keep:
            break
        held = givens[cell]
        givens[cell] = 0
        if _still_only_one(givens, box, cell, held):
            filled -= 1
        else:
            givens[cell] = held
    return givens


#: What falling short of a rung costs against overshooting it. A rung
#: that cannot find its band should hand back something harder than it
#: promised rather than something easier -- the promise is a floor on
#: the work, and a puzzle that is too hard still honours it while one
#: that is too easy does not. Tiers four and five are rare enough
#: (measured at 1.0% of nine-by-nines between them) that the rung
#: asking for them does sometimes fall back, and this is the direction
#: it falls.
UNDERSHOOT_COST = 3


def _miss(made: Puzzle, grade: Grade) -> Tuple[int, int]:
    """How far off the rung a puzzle is; smaller is better.

    Distance from the band first, shortfall in guesses second, which
    is the ranking the ladder promises: a puzzle of the right depth
    always beats one of the wrong depth, however much either branches.
    """
    if made.tier < grade.floor:
        adrift = (grade.floor - made.tier) * UNDERSHOOT_COST
    elif made.tier > grade.ceiling:
        adrift = made.tier - grade.ceiling
    else:
        adrift = 0
    return adrift, max(0, grade.guesses - made.guesses)


def deal_one(grade: Grade, rng: random.Random) -> Puzzle:
    """One puzzle at *grade*, whatever it turns out to be worth."""
    full = _full_grid(grade.box, rng)
    givens = _dig(full, grade.box, rng, keep=grade.keep)
    tier, guesses = rate(givens, grade.box)
    return Puzzle(box=grade.box, givens=tuple(givens), solution=tuple(full),
                  tier=tier, guesses=guesses, )


def generate(level_number: int, seed: Optional[int] = None,
             attempts: Optional[int] = None) -> Puzzle:
    """A puzzle at *level_number*, inside that rung's band.

    Rejection sampling, because there is no way to dig *towards* a
    tier -- the tier is a property of the finished puzzle and only a
    solver knows it. The measured hit rates are what set each rung's
    budget: a nine-by-nine deal costs about a hundredth of a second
    and lands its band once in three to once in ten, while a dug-out
    sixteen costs nearly two seconds and lands almost every time.

    When nothing lands, the nearest miss is handed back rather than
    nothing at all, and it is nearest in a direction:
    :data:`UNDERSHOOT_COST` makes a puzzle harder than the rung asked
    for beat one that is easier, so a rung's name is a floor on the
    work even on the deals where its band was not found. The screen
    reports the tier it actually got, never the one it wanted.

    The only rung where that happens often is *hard*, which asks for
    tiers four to five -- 1.0% of nine-by-nines between them, so
    roughly one deal in seven falls back, always upwards.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    rng = random.Random(seed)
    nearest: Optional[Puzzle] = None
    closest = (99, 99)
    for _attempt in range(max(1, attempts or grade.tries)):
        made = deal_one(grade, rng)
        adrift = _miss(made, grade)
        if adrift == (0, 0):
            return made
        if adrift < closest:
            nearest, closest = made, adrift
    assert nearest is not None
    return nearest
