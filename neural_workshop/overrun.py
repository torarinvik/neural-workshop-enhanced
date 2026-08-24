# -*- coding: utf-8 -*-
"""A line of text creeping towards the right-hand edge, and a keyboard.

The line is a real sentence, it drifts right at a rate the level sets,
and the only thing that pushes it back is typing it. Clear a word and
the rest of the line snaps left by that word's width; clear the whole
sentence and the line is gone before it ever reached the edge. Let the
end of it cross the edge and a life goes.

Three decisions make this a task rather than a toy, and all three are
about the arithmetic rather than the drawing.

**The runway is exactly as long as the text.** A wave starts with its
right-hand end half its own length from the margin — a forty-character
line has forty characters of clear road ahead of it, a twenty-eight
character line has twenty-eight. So the time a wave allows is its
length divided by the drift, and the rate it demands is the drift,
whatever sentence was dealt. Without that rule a short sentence would
be a gift and a long one a sentence of death, and the level would
mean a different thing on every deal.

**The level is the clock and nothing else.** Every rung draws from the
same sentences, of the same lengths, out of the same vocabulary; what
changes between rung one and rung twelve is how fast the line moves,
and nothing else. So a run that climbs is a run that got faster, and a
learning curve drawn across the rungs is about rate rather than about
words. Freeform Tetris makes the opposite promise for the same reason
— its ladder is shape and never speed — and both promises exist so
that a number taken off a rung can be compared with a number taken off
another one.

**A mistyped letter stays until it is rubbed out.** It would have been
kinder to ignore a wrong key, and it was written that way first. What
that costs is the whole floor of the task: with wrong keys ignored the
correct prefix can only ever grow, so a walk hitting keys at random
lands a letter every twenty-six presses, which at sixty presses a
second is 2.3 characters a second. The arithmetic says that beats the
bottom three rungs. Played out rather than worked out, it is worse
than that — it clears *every* wave to the fifth rung, ninety-five in a
hundred at the sixth, and one in eight as high as the tenth, because
the mean rate is not the race: the deadline walks forward every time a
word goes, so a walk that gets lucky in its first two words carries
that slack down the rest of the line. Two thirds of the ladder, from
something that cannot read. With the letter sticking, a word clears
only on an exact match, and the same walk clears nothing at any rung
at all. Both columns are in ``tests/bench_overrun.py``.

The ladder, measured over 600 waves a rung by ``tests/bench_overrun.py``.
*drift* is the dial and everything else is what it comes to: *seconds*
is how long a wave allows and *wpm* is what clearing one asks of the
fingers, a word being five characters as it always is when typing is
sold by the minute. The last column is the counterfactual above — how
many waves a walk clears when a wrong key is ignored.

===== ===== ====== ====== ======= ===== ========
 rung drift  chars   keys seconds   wpm  ignored
===== ===== ====== ====== ======= ===== ========
    1   1.9   36.6   30.6    19.3  19.0     1.00
    2   2.2   37.2   30.9    16.9  21.9     1.00
    3   2.5   36.9   30.7    14.8  24.9     1.00
    4   2.9   36.6   30.4    12.6  28.9     1.00
    5   3.3   37.0   30.8    11.2  32.9     1.00
    6   3.8   36.8   30.6     9.7  37.9     0.95
    7   4.3   37.0   30.8     8.6  42.9     0.82
    8   4.9   36.9   30.7     7.5  48.9     0.53
    9   5.6   36.7   30.5     6.5  55.8     0.37
   10   6.4   36.8   30.6     5.7  63.9     0.13
   11   7.3   36.5   30.4     5.0  72.9     0.02
   12   8.4   36.6   30.4     4.4  83.6     0.00
===== ===== ====== ====== ======= ===== ========

The middle three columns barely move, which is the point of them being
printed: every rung deals from the same sentences, so *wpm* is a
straight multiple of *drift* and the ladder is a typing speed rather
than a mixture of things called a level.

The text comes from :mod:`neural_workshop.sentences`, which is Simple
English Wikipedia, and the sentences are the short end of it: twenty-four
to forty-four characters, so that a whole one fits on the screen with
its own length of road ahead of it. That is about ten thousand of the
thirty-six thousand the bank holds, and fifty-eight of the seventy that
are written into the source for a machine that has fetched nothing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import statistics
from typing import Dict, NamedTuple, Optional, Sequence, Tuple

from .sentences import Sentence, bank

#: How many characters wide the lane is. Twice :data:`LONGEST`, and that
#: is not a coincidence — it is what makes the runway rule above work
#: for the longest line the task will deal. A shorter line starts
#: further along the lane and has less road, in exactly the proportion
#: that it has less to type.
CELLS = 88

#: The shortest and longest line a wave may be, in characters. The
#: bottom is there so a wave is a sentence rather than a phrase; the top
#: is half the lane.
SHORTEST, LONGEST = 24, 44

#: The rarest word a wave may hold. The bank is already cut at 60,000;
#: this is tighter because a word you have to work out is a word you
#: cannot type at speed, and speed is the whole of the task.
TOP_RANK = 20000

#: Lives at the start of a run, and the most a run may hold.
#:
#: The ceiling is not decoration. Past nine, a run of the usual length
#: cannot be lost however badly the rest of it goes, so the extra lives
#: stop being a stake and become a score — and the score is already
#: printed, in words a minute, which says more.
START_LIVES = 3
MOST_LIVES = 9


class Grade(NamedTuple):
    """One rung. Only the clock differs between them."""

    name: str
    #: Characters a second the line creeps right. Spaces are characters
    #: here and are not typed, so the rate this demands of the fingers is
    #: about five sixths of it — measured, per rung, by
    #: :func:`demand` and published by ``tests/bench_overrun.py``.
    speed: float


#: Nineteen words a minute to eighty-four, in twelve steps of about a
#: seventh each. The numbers in the comment are measured over the bank
#: rather than declared: see ``tests/bench_overrun.py``.
GRADES: Tuple[Grade, ...] = (
    Grade('one finger at a time', 1.9),             # ~19 wpm
    Grade('two fingers', 2.2),                      # ~22
    Grade('still looking at the keys', 2.5),        # ~25
    Grade('the keys stay where you left them', 2.9),  # ~29
    Grade('both hands, most of the time', 3.3),     # ~33
    Grade('a working pace', 3.8),                   # ~38
    Grade('no time to look down', 4.3),             # ~43
    Grade('faster than you could say it', 4.9),     # ~49
    Grade('the line does not wait', 5.6),           # ~56
    Grade("a typist's pace", 6.4),                  # ~64
    Grade('no room for a second try', 7.3),         # ~73
    Grade('as fast as the line goes', 8.4),         # ~84
)


def grade_of(rung: int) -> Grade:
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


# --- one wave -------------------------------------------------------------


def starts_of(words: Sequence[str]) -> Tuple[int, ...]:
    """Where each word begins in the line, counting from its first letter.

    One space between words, so the offsets are what ``' '.join`` would
    have put them at. This is the whole of the layout: everything else
    here is these offsets plus the drift.
    """
    made = []
    at = 0
    for word in words:
        made.append(at)
        at += len(word) + 1
    return tuple(made)


class Wave(NamedTuple):
    """One sentence, laid out on the lane's character grid."""

    words: Tuple[str, ...]
    #: Character offset of each word within the whole line.
    starts: Tuple[int, ...]
    grade: Grade

    @property
    def line(self) -> str:
        return ' '.join(self.words)

    @property
    def length(self) -> int:
        """Characters in the whole line, spaces included."""
        return len(self.line)

    @property
    def letters(self) -> int:
        """Keys that have to be pressed to clear it. Spaces are free."""
        return sum(len(word) for word in self.words)

    @property
    def start_cell(self) -> int:
        """The cell the line's left-hand end sits in before it moves.

        The runway rule, in one line: the right-hand end starts
        :attr:`length` cells from the margin, so the left-hand end
        starts twice that back from it.
        """
        return CELLS - 2 * self.length

    @property
    def seconds(self) -> float:
        """How long the whole wave allows, if not one letter is typed."""
        return self.length / self.grade.speed

    @property
    def demand(self) -> float:
        """Letters a second that clearing this wave asks for."""
        return self.letters / self.seconds


def words_a_minute(letters: float, seconds: float) -> float:
    """The usual conversion: a word is five keystrokes.

    Comparable with what any typing test would tell the same person,
    and it is worth saying why, because the line has gaps in it that
    nobody types. Both counts are *keys*: a typing test's five
    characters include the space bar, and here there is no space bar at
    all — a word clears itself and the gap after it comes back with it
    — so the letters are the whole of the keyboard work either way.
    """
    return 0.0 if seconds <= 0 else (letters / 5.0) * (60.0 / seconds)


def left_cell(wave: Wave, drift: float) -> float:
    """Where the front of the line is, in cells, after *drift* cells of it.

    The front of the line is where the word being typed begins, and it
    does not depend on how many words have gone: clearing one takes the
    line's front away, and what is behind it moves up. So the eye has a
    fixed place to look, and only the clock moves it.
    """
    return wave.start_cell + drift


def right_cell(wave: Wave, cleared: int, drift: float) -> float:
    """Where the end of the line is once *cleared* words have gone."""
    if cleared >= len(wave.words):
        return wave.start_cell + drift
    return wave.start_cell + drift + wave.length - wave.starts[cleared]


def deadline(wave: Wave, cleared: int) -> float:
    """The second at which the line runs out, *cleared* words in.

    Every word cleared buys its own width plus the space after it, so
    the deadline walks forward by exactly what was typed away.
    """
    if cleared >= len(wave.words):
        return float('inf')
    return (wave.length + wave.starts[cleared]) / wave.grade.speed


def overrun(wave: Wave, cleared: int, drift: float) -> bool:
    """Whether the end of the line has crossed the margin."""
    if cleared >= len(wave.words):
        return False
    return right_cell(wave, cleared, drift) >= CELLS


# --- what there is to deal ------------------------------------------------


_POOL: Dict[Tuple[int, int, int], Tuple[Sentence, ...]] = {}


def pool(span: Tuple[int, int] = (SHORTEST, LONGEST),
         top_rank: int = TOP_RANK) -> Tuple[Sentence, ...]:
    """Every sentence short enough to fit the lane with its own runway.

    Cached: a rung asks for the same band on every wave, and walking
    thirty-six thousand sentences a deal is a pause you can see.
    """
    key = (int(span[0]), int(span[1]), int(top_rank))
    if key not in _POOL:
        _POOL[key] = tuple(
            one for one in bank()
            if span[0] <= len(one.text) <= span[1] and one.hardest <= top_rank)
    return _POOL[key]


def deal_one(grade: Grade, rng: random.Random) -> Optional[Wave]:
    """One wave, or ``None`` when there is no sentence to make one of."""
    found = pool()
    if not found:
        return None                                  # pragma: no cover
    picked = found[rng.randrange(len(found))]
    return Wave(picked.words, starts_of(picked.words), grade)


def generate(rung: int, seed: Optional[int] = None) -> Optional[Wave]:
    """One wave at *rung*, reproducibly when *seed* is given."""
    return deal_one(grade_of(rung), random.Random(seed))


# --- what a rung asks for -------------------------------------------------


_SHARE: Optional[float] = None


def letter_share() -> float:
    """What fraction of a line's characters have to be typed.

    The gaps between words are cells like any other — they are part of
    what a cleared word hands back, along with its own letters — but
    they are not keys. So the rate a rung asks of the fingers is its
    drift times this, and this is measured over the sentences the task
    actually deals rather than assumed to be five sixths of it.
    """
    global _SHARE
    if _SHARE is None:
        found = pool()
        _SHARE = (statistics.mean(sum(len(word) for word in one.words)
                                  / len(one.text) for one in found)
                  if found else 1.0)
    return _SHARE


def pace(rung: int) -> float:
    """Words a minute *rung* demands, a word being five characters."""
    return 12.0 * grade_of(rung).speed * letter_share()


def forget() -> None:
    """Drop the cached pool. For the tests, and after a fetch."""
    global _SHARE
    _POOL.clear()
    _SHARE = None


__all__ = ['CELLS', 'GRADES', 'Grade', 'LONGEST', 'MOST_LIVES', 'SHORTEST',
           'START_LIVES', 'TOP_RANK', 'Wave', 'deadline', 'deal_one',
           'forget', 'generate', 'grade_of', 'left_cell', 'letter_share',
           'overrun', 'pace', 'pool', 'right_cell', 'starts_of',
           'words_a_minute']
