# -*- coding: utf-8 -*-
"""The Scrabble screen: one rack, one board, and the best play to beat.

The scoring and the search live in :mod:`neural_workshop.scrabble`;
this module is the board drawn, the rack under it, and the keys that
put one on the other. Four decisions matter here:

* **It is one position, not a game.** There is no opponent and no bag
  to draw from. A trial hands over a board and a rack, you lay one
  play, and it is scored against the best play that existed. That is
  the whole task, and it is a task with an exact answer, which a game
  against an opponent is not.

* **The best score is not shown until you have played.** It is on the
  screen afterwards, because a rung means nothing without it; showing
  it during would turn the search into a hot-and-cold game against a
  number.

* **An illegal play is refused, not scored.** Tiles that spell nothing,
  or that float free of the board, come back with a reason and the
  tiles stay where they are. Only a legal play settles the trial. A
  screen that scored nonsense as zero would be paying for the
  difference between a bad play and a misunderstanding of the rules,
  which is not what any rung here is about.

* **Only the tiles you laid this turn can be taken back.** Backspace
  lifts the last one. What was on the board when the trial opened is
  the position and is not editable.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (MAX_FONT_SIZE, calc_fontsize, from_bottom_edge,
                        from_top_edge, width_center)
from ..scrabble import (Deal, GRADES, VALUES, generate, grade_of, legal,
                        score_play)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band
from ..i18n import _

#: The lines between squares.
RULE = (120, 120, 120)
#: Where the cursor is.
HERE = (86, 180, 233)          # sky blue
#: A tile laid this turn, as against one that was already there.
MINE = (0, 114, 178)           # blue

#: What each premium square is painted. Kept pale: a board is mostly
#: premiums and a saturated one would be unreadable under the tiles.
PREMIUM_COLOURS: Dict[str, Tuple[int, int, int]] = {
    'DL': (170, 205, 230),
    'TL': (110, 160, 205),
    'DW': (240, 190, 170),
    'TW': (225, 140, 110),
}

LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def fit(step: float, share: float) -> float:
    """A font size taken from the square rather than from the window."""
    return max(4.0, min(MAX_FONT_SIZE, step * share))


class Scrabble:
    """Lay the best play you can. Arrows move, 1-7 lay, Enter plays."""

    instance: Optional['Scrabble'] = None

    def __init__(self) -> None:
        if Scrabble.instance is not None:
            Scrabble.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.deal: Optional[Deal] = None
        #: Tiles laid this turn, in the order they were laid.
        self.laid: List[Tuple[int, str]] = []
        #: Rack positions already spent, so a tile is played once.
        self.spent: List[int] = []
        self.at = 0
        self.down = False
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, int, int, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.message = _('Press Space to start')
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Scrabble.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SCRABBLE)
        self.start_rung = int(opts['SCRABBLE_LEVEL'])
        self.total_trials = int(opts['SCRABBLE_TRIALS'])
        self.show_premiums = bool(opts['SCRABBLE_SHOW_PREMIUMS'])
        self.adaptive = bool(opts['SCRABBLE_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('scrabble', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.ink = (fg, fg, fg)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Scrabble'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(64),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   arrows: move   1-7: lay'
              '   Bksp: undo   Tab: turn   Enter: play   O: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour; tests/check_band.py is what says nothing else
        # this task draws puts a saturated colour in the bottom quarter.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def size(self) -> int:
        return self.deal.board.size if self.deal is not None else 1

    def _floor(self) -> float:
        """The lowest anything this task draws may reach.

        The rack is drawn *below* the board, so the board's own
        clearance is not the task's. Both are measured off this, and
        ``tests/test_scrabble.py`` asserts the rack box clears it —
        against the geometry rather than against a sweep, because a
        premium square is painted vermilion and that is a colour the
        verdict reader counts. Whether a run painted one low enough to
        be read would otherwise depend on which board was dealt, and a
        clean sweep of a thing that only sometimes happens proves
        nothing.
        """
        return above_the_band(from_bottom_edge(44))

    def _rack_step(self) -> float:
        """How tall a rack tile is, which is also how tall its strip is."""
        return max(14.0, min(56.0, (from_top_edge(84) - self._floor()) * 0.13))

    def _board(self) -> Tuple[float, float, float]:
        """Left, bottom and side of the board on screen."""
        window = state.window
        top = from_top_edge(84)
        bottom = self._floor() + self._rack_step() * 1.6
        side = max(40.0, min(window.width * 0.8, top - bottom))
        return ((window.width - side) / 2, bottom + (top - bottom - side) / 2,
                side)

    def _cell_rect(self, cell: int) -> Tuple[float, float, float]:
        left, bottom, side = self._board()
        step = side / self.size()
        x, y = cell % self.size(), cell // self.size()
        return (left + x * step, bottom + (self.size() - 1 - y) * step, step)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.deal = None
        self.laid = []
        self.spent = []
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        made = generate(self.rung, seed=self.rng.randrange(1 << 30))
        if made is None:
            self.phase = 'done'
            self.message = _('No position could be dealt at this level')
            self._redraw()
            return
        self.deal = made
        self.laid = []
        self.spent = []
        # The middle square is where the first word was laid, so it is
        # taken. Opening the cursor on it means the first tile a
        # player lays is refused, which reads as the keyboard not
        # working rather than as the square being occupied.
        self.at = self._nearest_empty(made.board.size // 2 * made.board.size
                                      + made.board.size // 2)
        self.down = False
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'playing'
        grade = grade_of(self.rung)
        self.message = _('%s — your rack is %s') % (
            _(grade.name), made.rack.upper())
        self._redraw()

    # --- playing ---------------------------------------------------------

    def _nearest_empty(self, from_cell: int) -> int:
        """The free square closest to *from_cell*, by rows then columns."""
        board = self.deal.board
        size = board.size
        row, col = divmod(from_cell, size)
        order = sorted(range(size * size),
                       key=lambda cell: (abs(cell // size - row)
                                         + abs(cell % size - col), cell))
        return next((cell for cell in order if board.empty(cell)), from_cell)

    def rack_left(self) -> str:
        """The tiles still in hand, in their dealt positions."""
        if self.deal is None:
            return ''
        return ''.join(letter for position, letter in enumerate(self.deal.rack)
                       if position not in self.spent)

    def move(self, dx: int, dy: int) -> None:
        if self.phase != 'playing':
            return
        size = self.size()
        x, y = self.at % size + dx, self.at // size + dy
        if 0 <= x < size and 0 <= y < size:
            self.at = y * size + x
            if dx or dy:
                self.down = bool(dy)
            self._redraw()

    def turn(self) -> None:
        if self.phase != 'playing':
            return
        self.down = not self.down
        self._redraw()

    def lay(self, slot: int) -> None:
        """Put rack tile *slot* on the cursor's square and step on."""
        if self.phase != 'playing' or self.deal is None:
            return
        if not 0 <= slot < len(self.deal.rack) or slot in self.spent:
            return
        if not self.deal.board.empty(self.at) or any(
                cell == self.at for cell, _l in self.laid):
            self.message = _('That square is taken')
            self._update_status()
            return
        self.laid.append((self.at, self.deal.rack[slot]))
        self.spent.append(slot)
        size = self.size()
        step = size if self.down else 1
        ahead = self.at + step
        if 0 <= ahead < size * size and (
                self.down or ahead // size == self.at // size):
            self.at = ahead
        self._redraw()

    def take_back(self) -> None:
        """Lift the last tile laid this turn."""
        if self.phase != 'playing' or not self.laid:
            return
        cell, _letter = self.laid.pop()
        self.spent.pop()
        self.at = cell
        self._redraw()

    def here(self) -> Dict[int, str]:
        return dict(self.laid)

    def submit(self) -> None:
        """Play what is laid, if it is legal. Refused rather than scored."""
        if self.phase != 'playing' or self.deal is None:
            return
        if not self.laid:
            self.message = _('Nothing laid yet')
            self._update_status()
            return
        from ..wordlist import pool
        grade = grade_of(self.rung)
        words = pool(grade.top_rank).narrowed(
            hi=grade.top_rank,
            lengths=tuple(range(2, self.deal.board.size + 1)))
        for down in (self.down, not self.down):
            if legal(self.deal.board, self.laid, down, words):
                self._played(down)
                return
        self.message = _('That is not a legal play')
        self._update_status()

    def _played(self, down: bool) -> None:
        got, made = score_play(self.deal.board, self.laid, down)
        best = self.deal.ceiling
        share = got / float(best) if best else 0.0
        took = self.clock() - self.started_at
        self.results.append((self.rung, got, best, took))
        grade = grade_of(self.rung)
        won = share >= grade.share
        self.message = _('%s for %d; the best was %s for %d') % (
            '/'.join(word.upper() for word in made), got,
            self.deal.best.word.upper(), best)
        if self.adaptive:
            if won:
                self.rung = self.clamped(self.rung + 1)
            elif share < grade.share * 0.6:
                self.rung = self.clamped(self.rung - 1)
        # Green means this rung's share of the best play that existed.
        # Not "a legal play", which every settled trial is by
        # construction, and not a threshold in points, which would mean
        # something different on every board.
        self.verdict_shown = (won, self.message)
        self.verdict.show(*self.verdict_shown)
        self.phase = 'scored'
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d played, %d points of a possible %d') % (
            tally['played'], tally['points'], tally['ceiling'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        return {
            'played': len(self.results),
            'points': sum(got for _r, got, _b, _t in self.results),
            'ceiling': sum(best for _r, _g, best, _t in self.results),
            'best_rung': max((rung for rung, _g, _b, _t in self.results),
                             default=0),
            'seconds': int(sum(took for _r, _g, _b, took in self.results)),
        }

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for shape in self.drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.drawn = []

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.deal is not None and self.phase in ('playing', 'scored'):
            self._draw_board()
            self._draw_rack()
        self._update_status()

    def _draw_board(self) -> None:
        left, bottom, side = self._board()
        size = self.size()
        step = side / size
        mine = self.here()
        board = self.deal.board

        self.drawn.append(pyglet.shapes.Rectangle(
            left, bottom, side, side, color=self.background,
            batch=self.batch))
        for cell in range(size * size):
            x, y, _s = self._cell_rect(cell)
            premium = board.premiums[cell]
            if premium and self.show_premiums and board.empty(cell) \
                    and cell not in mine:
                self.drawn.append(pyglet.shapes.Rectangle(
                    x, y, step, step, color=PREMIUM_COLOURS[premium],
                    batch=self.batch))
            letter = mine.get(cell) or board.letters[cell]
            if letter:
                self.drawn.append(pyglet.text.Label(
                    letter.upper(), font_size=fit(step, 0.46),
                    weight='bold' if cell not in mine else 'normal',
                    color=(MINE if cell in mine else self.ink) + (255,),
                    batch=self.batch, x=x + step / 2, y=y + step * 0.46,
                    anchor_x='center', anchor_y='center', font_name=FONTLIST))
        self._draw_rules(left, bottom, side, size, step)
        x, y, _s = self._cell_rect(self.at)
        self.drawn.append(pyglet.shapes.BorderedRectangle(
            x, y, step, step, border=max(2.0, step * 0.1),
            color=(0, 0, 0, 0), border_color=HERE, batch=self.batch))

    def _draw_rules(self, left: float, bottom: float, side: float,
                    size: int, step: float) -> None:
        for line in range(size + 1):
            at = line * step
            width = max(1.0, step * 0.03)
            self.drawn.append(pyglet.shapes.Line(
                left, bottom + at, left + side, bottom + at,
                thickness=width, color=RULE, batch=self.batch))
            self.drawn.append(pyglet.shapes.Line(
                left + at, bottom, left + at, bottom + side,
                thickness=width, color=RULE, batch=self.batch))

    def rack_box(self) -> Tuple[float, float]:
        """Bottom and top of the strip the rack is drawn in."""
        step = self._rack_step()
        top = self._board()[1] - step * 0.3
        return (top - step * 1.3, top)

    def _draw_rack(self) -> None:
        """The tiles still in hand, numbered by the key that lays them."""
        step = self._rack_step()
        wide = step * len(self.deal.rack)
        start = (state.window.width - wide) / 2
        top = self.rack_box()[1]
        for position, letter in enumerate(self.deal.rack):
            if position in self.spent:
                continue
            x = start + position * step
            self.drawn.append(pyglet.shapes.BorderedRectangle(
                x, top - step, step * 0.9, step, border=1.0,
                color=self.background, border_color=RULE, batch=self.batch))
            self.drawn.append(pyglet.text.Label(
                letter.upper(), font_size=fit(step, 0.42),
                color=self.textcolor, batch=self.batch,
                x=x + step * 0.45, y=top - step * 0.52,
                anchor_x='center', anchor_y='center', font_name=FONTLIST))
            self.drawn.append(pyglet.text.Label(
                '%d·%d' % (position + 1, VALUES[letter]),
                font_size=fit(step, 0.2), color=self.ink + (190,),
                batch=self.batch, x=x + step * 0.45, y=top - step * 0.9,
                anchor_x='center', anchor_y='center', font_name=FONTLIST))

    def _update_status(self) -> None:
        parts = [self.message]
        if self.deal is not None and self.phase == 'playing':
            parts.append(_('board %d/%d   %s   in hand: %s')
                         % (self.trial, self.total_trials,
                            _('down') if self.down else _('across'),
                            self.rack_left().upper() or _('none')))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Scrabble.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        Scrabble.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    _RACK_KEYS = {
        key._1: 0, key._2: 1, key._3: 2, key._4: 3, key._5: 4, key._6: 5,
        key._7: 6, key.NUM_1: 0, key.NUM_2: 1, key.NUM_3: 2, key.NUM_4: 3,
        key.NUM_5: 4, key.NUM_6: 5, key.NUM_7: 6,
    }

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'scored':
                self._next_trial()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.F11:
            display.toggle_fullscreen()
            return pyglet.event.EVENT_HANDLED
        if symbol in (key.O, key.C):
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        if symbol in (key.ENTER, key.RETURN, key.NUM_ENTER):
            self.submit()
        elif symbol == key.TAB:
            self.turn()
        elif symbol == key.UP:
            self.move(0, -1)
        elif symbol == key.DOWN:
            self.move(0, 1)
        elif symbol == key.LEFT:
            self.move(-1, 0)
        elif symbol == key.RIGHT:
            self.move(1, 0)
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.take_back()
        elif symbol in self._RACK_KEYS:
            self.lay(self._RACK_KEYS[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
