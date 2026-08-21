# -*- coding: utf-8 -*-
"""Concentration: turn cards over two at a time and find the pairs.

The board deals each item twice and hides everything. A turn reveals
two cards: a pair stays up, anything else goes back down. The whole
board is the task, so the score is how few turns it took.

Two media, and they are different games. Photographs can be compared
at a glance, so the work is remembering *where* something was. Sounds
cannot — a clip has to be held in mind while the second card plays,
which is a harder and much less visual kind of remembering.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, media, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band
from ..i18n import _


class Card:
    """One card on the board: an item, and whether it is showing."""

    __slots__ = ('path', 'index', 'face_up', 'matched', 'rect')

    def __init__(self, path: str, index: int) -> None:
        self.path = path
        self.index = index          # which pair it belongs to
        self.face_up = False
        self.matched = False
        self.rect: Tuple[float, float, float, float] = (0, 0, 0, 0)

    def contains(self, x: float, y: float) -> bool:
        left, bottom, width, height = self.rect
        return left <= x <= left + width and bottom <= y <= bottom + height


class Concentration:
    """A board of face-down pairs. Click two; Esc returns to the hub."""

    instance: Optional['Concentration'] = None

    def __init__(self) -> None:
        if Concentration.instance is not None:
            Concentration.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.cards: List[Card] = []
        self.flipped: List[Card] = []
        self.turns = 0
        self.started_at = 0.0
        self.finished_at = 0.0
        self.hide_at = 0.0
        self.peek_until = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to deal')
        self.player: Optional[object] = None
        self._read_options()
        self.shapes: List[object] = []
        self.sprites: List[object] = []
        self.card_labels: List[pyglet.text.Label] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        Concentration.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.CONCENTRATION)
        self.pairs = int(opts['CONCENTRATION_PAIRS'])
        self.medium = str(opts['CONCENTRATION_MEDIUM'])
        self.peek_ms = int(opts['CONCENTRATION_PEEK_MS'])
        self.hide_ms = int(opts['CONCENTRATION_HIDE_MS'])
        self.show_turns = bool(opts['CONCENTRATION_SHOW_TURNS'])
        self.pool = media.pool_for(self.medium, self.rng)

    def open_options(self) -> None:
        taskoptions.open_task_options('concentration',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        """Create the batch, the colours and the fixed labels."""
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.shapes = []
        self.sprites = []
        self.card_labels = []
        self.title = pyglet.text.Label(
            _('Concentration'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: new board     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(30),
            anchor_x='center', anchor_y='center')
        # Read by the agent boundary, which pays the trial by this
        # label's colour; tests/check_band.py is what says nothing else
        # this task draws puts a saturated colour in the bottom quarter.
        # Rebuilt with the chrome, so a verdict already up is put back —
        # a relayout on the frame a trial settles would otherwise drop
        # it, and an outcome only sometimes derivable is worse than one
        # that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        self._layout_board()
        self._redraw()

    def relayout(self) -> None:
        """Rebuild at the window's current size, mid-board if need be."""
        self._build_chrome()

    def _grid_shape(self) -> Tuple[int, int]:
        """Columns and rows that fit the cards into the window."""
        count = max(2, len(self.cards) or self.pairs * 2)
        window = state.window
        room = max(80.0, from_top_edge(88) - above_the_band())
        aspect = max(0.2, (window.width * 0.9) / room)
        columns = max(2, min(count, int(round(math.sqrt(count * aspect)))))
        rows = int(math.ceil(count / float(columns)))
        while columns * rows - count >= rows and columns > 2:
            columns -= 1
            rows = int(math.ceil(count / float(columns)))
        return columns, rows

    def _layout_board(self) -> None:
        """Place every card in the grid for the current window."""
        if not self.cards:
            return
        window = state.window
        columns, rows = self._grid_shape()
        # The room the board has: down to the top of the band the agent
        # boundary reads, and no further. The cards are photographs and
        # a photograph holds every colour there is, so a board that
        # reached into the band would be read as a verdict about as
        # often as not.
        floor = above_the_band()
        ceiling = from_top_edge(88)
        span_w = window.width * 0.9
        span_h = max(80.0, ceiling - floor)
        gap = max(4.0, min(span_w / columns, span_h / rows) * 0.09)
        card_w = (span_w - gap * (columns - 1)) / columns
        card_h = (span_h - gap * (rows - 1)) / rows
        side = min(card_w, card_h)
        total_w = side * columns + gap * (columns - 1)
        total_h = side * rows + gap * (rows - 1)
        left = (window.width - total_w) / 2
        top = floor + total_h + (span_h - total_h) / 2
        for position, card in enumerate(self.cards):
            column = position % columns
            row = position // columns
            card.rect = (left + column * (side + gap),
                         top - (row + 1) * side - row * gap,
                         side, side)

    # --- the board -------------------------------------------------------

    def _reset(self) -> None:
        self._stop_sound()
        self.cards = []
        self.flipped = []
        self.turns = 0
        self.seen = {}
        self.lapses = 0
        self.phase = 'ready'
        self.message = _('Press Space to deal')
        self.verdict_shown = None

    def needed_items(self) -> int:
        return self.pairs

    def deal(self) -> bool:
        """Draw fresh items and lay a new board. False if none available."""
        self.pool.reload()
        if not self.pool.ready(self.needed_items()):
            self.phase = 'ready'
            self.message = _('No %s library yet — see the Readme') % self.medium
            self._redraw()
            return False
        paths = self.pool.take_many(self.pairs)
        if len(paths) < self.pairs:
            self.pairs = max(2, len(paths))
            paths = paths[:self.pairs]
        cards = [Card(path, index)
                 for index, path in enumerate(paths) for _copy in (0, 1)]
        self.rng.shuffle(cards)
        self.cards = cards
        self.flipped = []
        self.turns = 0
        self.seen = {}
        self.lapses = 0
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.finished_at = 0.0
        self._layout_board()
        if self.peek_ms > 0 and self.medium != 'sound':
            for card in self.cards:
                card.face_up = True
            self.phase = 'peek'
            self.peek_until = self.clock() + self.peek_ms / 1000.
            self.message = _('Look')
        else:
            self.phase = 'playing'
            self.message = _('Find the pairs')
        self._redraw()
        return True

    def _stop_sound(self) -> None:
        if self.player is not None:
            try:
                self.player.pause()
            except Exception:
                pass
            self.player = None

    def _play(self, card: Card) -> None:
        if self.medium != 'sound':
            return
        source = self.pool.item(card.path)
        if source is None:
            return
        self._stop_sound()
        try:
            self.player = source.play()
        except Exception:
            self.player = None

    def flip(self, card: Card) -> None:
        """Turn *card* over. The move a click makes; used by tests too."""
        if self.phase != 'playing' or card.face_up or card.matched:
            return
        if len(self.flipped) >= 2:
            self._resolve()
        seen_before = id(card) in self.seen.get(card.index, ())
        card.face_up = True
        self.flipped.append(card)
        self._play(card)
        self.seen.setdefault(card.index, set()).add(id(card))
        if len(self.flipped) == 1:
            # Counted with this card, so it covers both of the cases a
            # player who forgot nothing would act on: a pair it can
            # already see the whole of somewhere else, and the partner
            # of the card it has just turned over.
            self.owed = self._known_pair()
        else:
            self.turns += 1
            first, second = self.flipped
            if first.index == second.index:
                first.matched = second.matched = True
                self.flipped = []
                self._check_finished()
                self.owed = False
            else:
                if self.owed or seen_before:
                    self.lapses += 1
                self.hide_at = self.clock() + self.hide_ms / 1000.
        self._redraw()

    def _known_pair(self) -> bool:
        """Is a whole unmatched pair already turned over somewhere?

        The one thing this board can be scored on. Whether a turn
        matched is mostly luck early on and mostly memory later, and
        the two are not worth telling apart by counting turns. What a
        player who forgot nothing would never do is *this*: leave a
        pair on the table when both of its cards have already been
        turned over once, or turn over a card it has seen before in
        the hope of a match it has already been shown is not there.

        A board cleared with none of those is a board played the way
        perfect memory would have played it, whatever the deal gave.
        Turns are not the measure -- an unlucky deal costs turns
        nobody could have saved.
        """
        matched = {card.index for card in self.cards if card.matched}
        return any(len(where) == 2 and index not in matched
                   for index, where in self.seen.items())

    def _resolve(self) -> None:
        """Turn an unmatched pair back down."""
        for card in self.flipped:
            if not card.matched:
                card.face_up = False
        self.flipped = []

    def _check_finished(self) -> None:
        if any(not card.matched for card in self.cards):
            return
        self.finished_at = self.clock()
        self.phase = 'done'
        elapsed = self.finished_at - self.started_at
        self.message = _('Cleared in %d turns, %ds') % (self.turns, elapsed)
        clean = self.lapses == 0
        self.verdict_shown = (clean, _('Cleared in %d turns — nothing '
                                       'forgotten') % self.turns if clean
                              else _('Cleared in %d turns — %d forgotten')
                              % (self.turns, self.lapses))
        self.verdict.show(*self.verdict_shown)

    def card_at(self, x: float, y: float) -> Optional[Card]:
        for card in self.cards:
            if card.contains(x, y):
                return card
        return None

    def update(self, dt: float) -> None:
        now = self.clock()
        if self.phase == 'peek' and now >= self.peek_until:
            for card in self.cards:
                card.face_up = False
            self.phase = 'playing'
            self.message = _('Find the pairs')
            self._redraw()
        elif len(self.flipped) == 2 and now >= self.hide_at:
            self._resolve()
            self._redraw()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.shapes + self.sprites:
            try:
                item.delete()
            except Exception:
                pass
        self.shapes = []
        self.sprites = []
        for label in self.card_labels:
            label.delete()
        self.card_labels = []

    def _card_fill(self, card: Card) -> Tuple[int, int, int, int]:
        if card.matched:
            return (46, 170, 92, 255)
        if card.face_up:
            return (236, 239, 245, 255)
        if state.cfg.BLACK_BACKGROUND:
            return (44, 50, 66, 255)
        return (86, 110, 168, 255)

    def _redraw(self) -> None:
        self._clear_drawn()
        for card in self.cards:
            left, bottom, side, height = card.rect
            rect = pyglet.shapes.Rectangle(
                left, bottom, side, height, color=self._card_fill(card),
                batch=self.batch)
            self.shapes.append(rect)
            if not card.face_up and not card.matched:
                continue
            if self.medium == 'sound':
                label = pyglet.text.Label(
                    '♪%d' % (card.index + 1),
                    font_size=max(8, calc_fontsize(side * 0.20)),
                    weight='bold', color=(20, 24, 32, 255), batch=self.batch,
                    x=left + side / 2, y=bottom + height / 2,
                    anchor_x='center', anchor_y='center', font_name=FONTLIST)
                self.card_labels.append(label)
                continue
            image = self.pool.item(card.path)
            if image is None:
                continue
            inset = side * 0.06
            sprite = pyglet.sprite.Sprite(
                image, x=left + inset, y=bottom + inset, batch=self.batch)
            sprite.scale = (side - inset * 2) / max(1, image.width)
            self.sprites.append(sprite)
        found = sum(1 for card in self.cards if card.matched) // 2
        parts = [self.message]
        if self.show_turns and self.cards:
            parts.append(_('%d/%d pairs, %d turns')
                         % (found, self.pairs, self.turns))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Concentration.instance is not self:
            return
        self._stop_sound()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        Concentration.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='long_term_memory')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.deal()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        card = self.card_at(x, y)
        if card is not None:
            self.flip(card)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
