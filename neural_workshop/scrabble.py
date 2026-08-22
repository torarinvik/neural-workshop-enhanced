# -*- coding: utf-8 -*-
"""One rack, one board, and the best play on it — worked out exactly.

The game of Scrabble is two players and a bag. What is interesting
about it, and what a workshop can actually measure, is one position:
here are your tiles, here is the board, what is the most you can score.
That is a search problem with an exact answer, and the exact answer is
what this module computes, so a play is graded against the best play
rather than against a threshold somebody chose.

The Traveling Salesman screen already works this way and it is the
right shape for a task: the score is *yours against the optimum*, so a
rung cannot be passed by being told what good is.

**What makes a position hard is not the rack.** Seven tiles is seven
tiles at every rung. Three things move:

*How obscure the best play is allowed to be.* Drawn from the three
thousand commonest words, the best play is something you know and the
work is finding where it goes. Drawn from the whole list, the best play
is often a word you have never met, and the ceiling stops being
reachable by vocabulary — which is where "superhuman" starts meaning
something.

This is the number the ladder is built on, and it is a measurement.
Take a player who knows only the three thousand commonest words and
who — unlike any person — always finds the best play among them. Over
twenty-five positions a rung, that player scores this share of the
optimum:

    1.00  1.00  1.00  0.77  0.77  0.54  0.61  0.41  0.39  0.42

Perfect at the bottom, because down there the optimum *is* an everyday
word and the whole task is placing it. Two fifths at the top, because
up there it is not. Each rung's passing share sits a little above what
that player would get, so a rung is passed by knowing more words or by
placing them better and not by either alone.

*How much board there is to hook onto.* One word in the middle of an
empty board gives a handful of anchor squares. Four crossing words give
dozens, and the premium squares that matter are no longer the ones near
the middle.

*How close to the best you have to come.* The bottom of the ladder pays
for half of the optimum. The top pays only for the optimum itself.

**The scoring is the real one**, because a made-up one would be a
different puzzle: the standard English letter values and distribution,
double and triple letter and word squares, every word formed by a play
scored, word premiums multiplying every word they fall in, and fifty
for laying all seven. The board is square and smaller than a real one
at the lower rungs, with the premium squares laid out by the same
symmetry rather than copied, because a fifteen by fifteen is mostly
empty space when only one word is on it.

**Blank tiles are not dealt.** A blank multiplies the search by
twenty-six per blank and adds nothing a rung cannot get by being drawn
from a wider band. Said here because their absence is a rule of this
task rather than an oversight.

The solver is the Appel and Jacobson one: for every square next to a
letter already on the board, extend left through what is there and
right through the rack, pruning on a prefix set, and check the
perpendicular word every time a tile lands. Cells are indexed
``row * size + column``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

from .wordlist import Lexicon, pool

#: The English letter values, which are the game's and not ours.
VALUES: Dict[str, int] = {
    'a': 1, 'b': 3, 'c': 3, 'd': 2, 'e': 1, 'f': 4, 'g': 2, 'h': 4,
    'i': 1, 'j': 8, 'k': 5, 'l': 1, 'm': 3, 'n': 1, 'o': 1, 'p': 3,
    'q': 10, 'r': 1, 's': 1, 't': 1, 'u': 1, 'v': 4, 'w': 4, 'x': 8,
    'y': 4, 'z': 10,
}

#: How many of each letter the bag holds, blanks left out. Kept because
#: a rack drawn uniformly over the alphabet is a rack of consonants and
#: is not the game.
BAG: Dict[str, int] = {
    'a': 9, 'b': 2, 'c': 2, 'd': 4, 'e': 12, 'f': 2, 'g': 3, 'h': 2,
    'i': 9, 'j': 1, 'k': 1, 'l': 4, 'm': 2, 'n': 6, 'o': 8, 'p': 2,
    'q': 1, 'r': 6, 's': 4, 't': 6, 'u': 4, 'v': 2, 'w': 2, 'x': 1,
    'y': 2, 'z': 1,
}

#: Premium squares. ``''`` is plain.
PLAIN, DOUBLE_LETTER, TRIPLE_LETTER = '', 'DL', 'TL'
DOUBLE_WORD, TRIPLE_WORD = 'DW', 'TW'

#: What the board pays for using every tile in the rack.
BINGO = 50

#: A full rack. Seven at every rung, because the rack is not the dial.
RACK = 7


class Play(NamedTuple):
    """One legal placement: where the tiles go, and what it comes to."""

    #: Cell to the letter put on it. Only the newly laid tiles.
    laid: Tuple[Tuple[int, str], ...]
    #: The main word formed, for saying what was played.
    word: str
    #: Every word the play makes, main one first.
    words: Tuple[str, ...]
    score: int
    down: bool

    @property
    def cells(self) -> Tuple[int, ...]:
        return tuple(cell for cell, _letter in self.laid)


class Board(NamedTuple):
    """A position: the squares, what is on them, and what they pay."""

    size: int
    #: One letter a cell, ``''`` where the board is empty.
    letters: Tuple[str, ...]
    #: One premium a cell, ``''`` where the square is plain.
    premiums: Tuple[str, ...]

    def at(self, row: int, col: int) -> str:
        return self.letters[row * self.size + col]

    def empty(self, cell: int) -> bool:
        return not self.letters[cell]

    def filled(self) -> int:
        return sum(1 for one in self.letters if one)


class Grade(NamedTuple):
    """One rung: what the board looks like and what counts as passing."""

    name: str
    size: int
    #: Rank band the pre-placed words and the best play are drawn from.
    top_rank: int
    #: Words already on the board when the rack is handed over.
    seeded: int
    #: Share of the best play's score that pays green.
    share: float
    #: Tiles in the rack. Seven except at the very bottom, where a
    #: shorter rack is the only honest way to make a first rung that
    #: does not need the whole game explained first.
    rack: int = RACK


#: Gentle to superhuman. The bands, the share and the seed counts were
#: all measured — ``tests/bench_words.py`` prints what a player who
#: only knows everyday words scores at each of them, and the shares
#: below were set from that rather than chosen.
GRADES: Tuple[Grade, ...] = (
    #                          size   rank   seeded  share  rack
    Grade('a first word',        7,    3000,    1,   0.50,   4),
    Grade('room to place',       7,    3000,    1,   0.60,   5),
    Grade('a fuller rack',       9,    3000,    2,   0.70,   7),
    Grade('common words',       11,   10000,    2,   0.75,   7),
    Grade('a busier board',     11,   10000,    3,   0.80,   7),
    Grade('familiar words',     13,   30000,    3,   0.85,   7),
    Grade('the crowded middle', 13,   30000,    4,   0.88,   7),
    Grade('bookish',            15,   80000,    4,   0.92,   7),
    Grade('the whole list',     15, 1 << 30,    4,   0.96,   7),
    Grade('nothing but best',   15, 1 << 30,    5,   1.00,   7),
)


def grade_of(rung: int) -> Grade:
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


# --- the board ------------------------------------------------------------


def premiums(size: int) -> Tuple[str, ...]:
    """Premium squares for a board of *size*, laid out by symmetry.

    Generated rather than copied from the fifteen by fifteen, because
    the boards here run from seven to fifteen and the real layout does
    not scale by cutting bits off it: the triple words sit at the
    corners and the edge midpoints, the double words on the diagonals
    inward from them, and the letter premiums on a ring between. Every
    square keeps the eightfold symmetry the real board has, so no
    corner of a rung's board is worth more than another.
    """
    middle = size // 2
    found = [PLAIN] * (size * size)
    for row in range(size):
        for col in range(size):
            near_row = min(row, size - 1 - row)
            near_col = min(col, size - 1 - col)
            cell = row * size + col
            if (near_row, near_col) in ((0, 0),) or (
                    near_row == 0 and col == middle) or (
                    near_col == 0 and row == middle):
                found[cell] = TRIPLE_WORD
            elif near_row == near_col and 1 <= near_row <= middle - 1:
                found[cell] = DOUBLE_WORD
            elif abs(near_row - near_col) == 2 and min(near_row,
                                                       near_col) <= 1:
                found[cell] = TRIPLE_LETTER
            elif (near_row + near_col) % 4 == 1 and near_row and near_col:
                found[cell] = DOUBLE_LETTER
    found[middle * size + middle] = DOUBLE_WORD
    return tuple(found)


def blank_board(size: int) -> Board:
    return Board(size, tuple([''] * (size * size)), premiums(size))


def written(board: Board, laid: Sequence[Tuple[int, str]]) -> Board:
    """*board* with *laid* added, which is what a play leaves behind."""
    letters = list(board.letters)
    for cell, letter in laid:
        letters[cell] = letter
    return board._replace(letters=tuple(letters))


# --- reading words off the board -----------------------------------------


def _run(board: Board, cell: int, down: bool,
         extra: Dict[int, str]) -> Tuple[str, Tuple[int, ...]]:
    """The whole word through *cell* in one direction, and its cells."""
    size = board.size
    step = size if down else 1
    row = cell // size

    def held(at: int) -> str:
        return extra.get(at) or board.letters[at]

    def inside(at: int) -> bool:
        if not 0 <= at < size * size:
            return False
        return True if down else at // size == row

    start = cell
    while inside(start - step) and held(start - step):
        start -= step
    cells: List[int] = []
    at = start
    while inside(at) and held(at):
        cells.append(at)
        at += step
    return ''.join(held(one) for one in cells), tuple(cells)


def score_play(board: Board, laid: Sequence[Tuple[int, str]],
               down: bool) -> Tuple[int, Tuple[str, ...]]:
    """What *laid* scores on *board*, and every word it makes.

    The premium under a tile already on the board is spent and does not
    pay again; a word premium multiplies every word it falls in,
    including the perpendicular one, which is the rule people most
    often get wrong and the reason a triple word under a crossing is
    worth so much.
    """
    extra = dict(laid)
    fresh = set(extra)
    total = 0
    words: List[str] = []
    main, _cells = _run(board, laid[0][0], down, extra)
    for direction, seeds in ((down, [laid[0][0]]),
                             (not down, [cell for cell, _l in laid])):
        for seed in seeds:
            word, cells = _run(board, seed, direction, extra)
            if len(word) < 2:
                continue
            if direction != down and len(laid) == len(cells) and word == main:
                continue
            value = 0
            multiplier = 1
            for one in cells:
                letter = extra.get(one) or board.letters[one]
                pay = VALUES.get(letter, 0)
                if one in fresh:
                    premium = board.premiums[one]
                    if premium == DOUBLE_LETTER:
                        pay *= 2
                    elif premium == TRIPLE_LETTER:
                        pay *= 3
                    elif premium == DOUBLE_WORD:
                        multiplier *= 2
                    elif premium == TRIPLE_WORD:
                        multiplier *= 3
                value += pay
            total += value * multiplier
            words.append(word)
    if len(laid) == RACK:
        total += BINGO
    return total, tuple(words)


def legal(board: Board, laid: Sequence[Tuple[int, str]], down: bool,
          words: Lexicon) -> bool:
    """Whether *laid* is a play this board and this pool allow."""
    if not laid:
        return False
    cells = [cell for cell, _letter in laid]
    if any(not board.empty(cell) for cell in cells):
        return False
    size = board.size
    lines = {cell // size if not down else cell % size for cell in cells}
    if len(lines) != 1:
        return False
    extra = dict(laid)
    main, run = _run(board, cells[0], down, extra)
    if not set(cells) <= set(run):
        return False              # a gap the play did not fill
    if len(main) < 2 or not words.valid(main):
        return False
    if board.filled() and not any(
            not board.empty(one) for one in run):
        return False              # floating free of everything on the board
    for cell in cells:
        across, _their = _run(board, cell, not down, extra)
        if len(across) > 1 and not words.valid(across):
            return False
    return True


# --- the exact best play --------------------------------------------------


def anchors(board: Board) -> Tuple[int, ...]:
    """Empty squares touching something, or the centre on a bare board."""
    size = board.size
    if not board.filled():
        return (size // 2 * size + size // 2,)
    found = []
    for cell in range(size * size):
        if not board.empty(cell):
            continue
        row, col = divmod(cell, size)
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            r, c = row + dr, col + dc
            if 0 <= r < size and 0 <= c < size and not board.empty(
                    r * size + c):
                found.append(cell)
                break
    return tuple(found)


def _cross_check(board: Board, cell: int, down: bool,
                 words: Lexicon) -> Set[str]:
    """Letters that make a legal perpendicular word at *cell*."""
    size = board.size
    step = 1 if down else size
    row = cell // size

    def inside(at: int) -> bool:
        if not 0 <= at < size * size:
            return False
        return True if not down else at // size == row

    before = ''
    at = cell - step
    while inside(at) and not board.empty(at):
        before = board.letters[at] + before
        at -= step
    after = ''
    at = cell + step
    while inside(at) and not board.empty(at):
        after += board.letters[at]
        at += step
    if not before and not after:
        return set(VALUES)
    return {letter for letter in VALUES
            if words.valid(before + letter + after)}


def plays(board: Board, rack: str, words: Lexicon) -> List[Play]:
    """Every legal play from *rack*. Exhaustive, which is the point.

    Slow on purpose rather than by accident: nothing here is allowed to
    be a heuristic, because the number a rung reports is the player's
    score *as a share of the best*, and a best that was only nearly the
    best would flatter everybody by an unknown amount.
    """
    size = board.size
    found: List[Play] = []
    seen: Set[Tuple] = set()
    spots = anchors(board)
    for down in (False, True):
        step = size if down else 1
        checks = {cell: _cross_check(board, cell, down, words)
                  for cell in spots}
        for anchor in spots:
            _extend(board, anchor, down, step, rack, words, checks, found,
                    seen)
    return found


def _line_of(board: Board, cell: int, down: bool) -> int:
    return cell % board.size if down else cell // board.size


def _extend(board: Board, anchor: int, down: bool, step: int, rack: str,
            words: Lexicon, checks: Dict[int, Set[str]],
            found: List[Play], seen: Set[Tuple]) -> None:
    """Grow a play through *anchor*, left first and then right."""
    size = board.size
    line = _line_of(board, anchor, down)

    def inside(at: int) -> bool:
        return (0 <= at < size * size
                and _line_of(board, at, down) == line)

    # How far left the play may start: back to the previous letter, or
    # as far as the rack could reach.
    room = 0
    at = anchor - step
    while inside(at) and board.empty(at) and at not in checks:
        room += 1
        at -= step
    before = ''
    at = anchor - step
    while inside(at) and not board.empty(at):
        before = board.letters[at] + before
        at -= step
    if before:
        room = 0

    for back in range(0, min(room, len(rack)) + 1):
        start = anchor - back * step
        if not inside(start):
            break
        _walk(board, start, anchor, down, step, rack, before, words, checks,
              found, seen)


def _walk(board: Board, start: int, anchor: int, down: bool, step: int,
          rack: str, before: str, words: Lexicon, checks: Dict[int, Set[str]],
          found: List[Play], seen: Set[Tuple]) -> None:
    """Lay tiles from *start* rightwards, pruning on the prefix set."""
    size = board.size
    line = _line_of(board, start, down)
    prefixes = words.prefixes()

    def inside(at: int) -> bool:
        return (0 <= at < size * size
                and _line_of(board, at, down) == line)

    def go(at: int, left: List[str], laid: List[Tuple[int, str]],
           so_far: str) -> None:
        if laid and so_far and words.valid(so_far) and (
                not inside(at) or board.empty(at)):
            # Two starts can reach the same tiles, so a play is kept
            # once. Sorted rather than in laying order: the same tiles
            # laid the same way are the same play however it was
            # arrived at, and scoring one of them twice would put a
            # duplicate at the top of the list.
            key = (down, tuple(sorted(laid)))
            if key not in seen and legal(board, laid, down, words):
                seen.add(key)
                score, made = score_play(board, laid, down)
                found.append(Play(tuple(laid), so_far, made, score, down))
        if not inside(at):
            return
        if so_far and so_far not in prefixes and not words.valid(so_far):
            return
        if not board.empty(at):
            go(at + step, left, laid, so_far + board.letters[at])
            return
        if not left:
            return
        allowed = checks.get(at)
        for letter in sorted(set(left)):
            if allowed is not None and letter not in allowed:
                continue
            rest = list(left)
            rest.remove(letter)
            go(at + step, rest, laid + [(at, letter)], so_far + letter)

    go(start, list(rack), [], before)


def best_play(board: Board, rack: str, words: Lexicon) -> Optional[Play]:
    """The highest-scoring legal play, or ``None`` if there is none."""
    every = plays(board, rack, words)
    return max(every, key=lambda one: (one.score, one.word)) if every else None


# --- dealing --------------------------------------------------------------


def draw(rng: random.Random, count: int) -> str:
    """*count* tiles from the bag, in its own distribution."""
    tiles = [letter for letter, many in BAG.items() for _ in range(many)]
    rng.shuffle(tiles)
    return ''.join(sorted(tiles[:count]))


class Deal(NamedTuple):
    """A dealt position: the board, the rack and what the best play is."""

    board: Board
    rack: str
    best: Play
    grade: Grade

    @property
    def ceiling(self) -> int:
        return self.best.score


def hooks(board: Board, word: str,
          words: Lexicon) -> List[Tuple[Tuple[Tuple[int, str], ...], bool]]:
    """Every legal way of laying *word* onto *board* through one letter.

    Enumerated rather than sampled. The first version picked a random
    letter on the board and a random offset into the word and gave up
    after two hundred tries, and what it mostly did was give up: a
    board asked for four crossing words came out with two, so the
    rungs that were supposed to differ by how crowded the board is did
    not differ at all.
    """
    size = board.size
    found = []
    on_board = [cell for cell in range(size * size) if not board.empty(cell)]
    for hook in on_board:
        here = board.letters[hook]
        for offset, letter in enumerate(word):
            if letter != here:
                continue
            for down in (False, True):
                step = size if down else 1
                start = hook - offset * step
                if not down and start // size != hook // size:
                    continue
                laid = []
                fits = True
                for position, want in enumerate(word):
                    cell = start + position * step
                    if not 0 <= cell < size * size:
                        fits = False
                        break
                    if not down and cell // size != hook // size:
                        fits = False
                        break
                    if cell == hook:
                        continue
                    if not board.empty(cell):
                        fits = False
                        break
                    laid.append((cell, want))
                if fits and laid and legal(board, laid, down, words):
                    found.append((tuple(laid), down))
    return found


def _seed_board(grade: Grade, words: Lexicon,
                rng: random.Random) -> Optional[Board]:
    """A board with *seeded* words already crossing on it."""
    board = blank_board(grade.size)
    middle = grade.size // 2
    longest = min(grade.size - 2, 8)
    pool_of = [one.word for one in words.entries
               if 3 <= len(one.word) <= longest]
    if not pool_of:
        return None
    first = pool_of[rng.randrange(len(pool_of))]
    at = middle * grade.size + (grade.size - len(first)) // 2
    board = written(board, [(at + step, letter)
                            for step, letter in enumerate(first)])
    for _more in range(max(0, grade.seeded - 1)):
        placed = False
        for _try in range(30):
            word = pool_of[rng.randrange(len(pool_of))]
            ways = hooks(board, word, words)
            if not ways:
                continue
            laid, _down = ways[rng.randrange(len(ways))]
            board = written(board, laid)
            placed = True
            break
        if not placed:
            break
    return board


def deal_one(grade: Grade, rng: random.Random,
             words: Optional[Lexicon] = None) -> Optional[Deal]:
    """A position at *grade*, with its best play already worked out."""
    pooled = words if words is not None else pool(grade.top_rank)
    narrow = pooled.narrowed(hi=grade.top_rank,
                             lengths=tuple(range(2, grade.size + 1)))
    for _try in range(40):
        board = _seed_board(grade, narrow, rng)
        if board is None:
            return None
        rack = draw(rng, grade.rack)
        best = best_play(board, rack, narrow)
        if best is not None and best.score > 0:
            return Deal(board, rack, best, grade)
    return None


def generate(level_number: int, seed: Optional[int] = None,
             words: Optional[Lexicon] = None) -> Optional[Deal]:
    """A position for *level_number*, one-based into :data:`GRADES`."""
    return deal_one(grade_of(level_number), random.Random(seed), words)


__all__ = ['BAG', 'BINGO', 'Board', 'Deal', 'GRADES', 'Grade', 'Play', 'RACK',
           'VALUES', 'anchors', 'best_play', 'blank_board', 'deal_one',
           'draw', 'generate', 'grade_of', 'hooks', 'legal', 'plays',
           'premiums', 'score_play', 'written']
