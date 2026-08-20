# -*- coding: utf-8 -*-
"""Jigsaw Puzzle: put a scrambled photograph back together.

A photograph is cut into a square grid of tiles and the tiles are
shuffled; clicking two of them swaps them, and the puzzle is done when
the picture is whole again. The reasoning is in the looking: every
tile carries edges, colours and fragments of things, and the work is
inferring where a fragment belongs in a picture you have never seen —
or holding the picture in mind from the preview and searching for the
piece that continues it.

The score is not just finishing. Any scramble can be solved in a
knowable minimum number of swaps — one less than the length of each
cycle of the shuffle, summed — and the run reports how close to that
minimum each solution came. Swapping tiles about at random finishes
eventually; seeing where each tile goes before touching it finishes
at the minimum, and the gap between the two is what is measured.

The photographs are the DIV2K set, 2K-resolution and detailed enough
that a tile from the sky and a tile from the sea genuinely take
looking at. The library is downloaded once — see the Readme — and the
task says so if it is missing rather than failing.

Every image in the library is shown before any is shown again, and
the rotation is remembered *across sessions* in a small file beside
the library. A jigsaw of a picture you have already assembled is a
memory task, not a reasoning one — you place tiles by recalling where
they went — so freshness is part of what the puzzle is, and a session
boundary should not quietly reset it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import datasets, display, media, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions

#: Grid sides a puzzle may use. Two-by-two is four tiles a child can
#: do; ten-by-ten is a hundred tiles of one photograph. The ceiling is
#: the tiles themselves: past ten a side they drop under forty pixels
#: on an ordinary window, too small to tell one patch of sky from
#: another.
SMALLEST_SIDE, LARGEST_SIDE = 2, 10

#: The gap ruled between tiles, in pixels. Wide enough that tile edges
#: never fuse into a finished-looking picture before it is finished.
SEAM = 2

#: How efficient a solution has to be before an adaptive run grows the
#: grid, and how far below that it falls before the grid shrinks.
#: Efficiency is the minimum number of swaps over the number used, so
#: one is a perfect solve.
GROW_AT, SHRINK_AT = 0.7, 0.45


def scramble(side: int, rng: random.Random) -> List[int]:
    """A shuffle of the grid's tiles, never the solved one.

    ``order[position]`` is the tile shown at *position*. The identity
    is redrawn away rather than patched away — swapping a pair into an
    almost-sorted shuffle would bias small grids toward one-swap
    puzzles.
    """
    order = list(range(side * side))
    while all(tile == position for position, tile in enumerate(order)):
        rng.shuffle(order)
    return order


def minimum_swaps(order: List[int]) -> int:
    """The fewest swaps that sort *order*.

    Each cycle of length n needs n - 1 swaps, so the total is the size
    of the grid minus the number of cycles. This is the par a solution
    is measured against.
    """
    seen = [False] * len(order)
    cycles = 0
    for start in range(len(order)):
        if seen[start]:
            continue
        cycles += 1
        position = start
        while not seen[position]:
            seen[position] = True
            position = order[position]
    return len(order) - cycles


class JigsawPuzzle:
    """Show a scrambled photograph, swap tiles by clicks, score it."""

    instance: Optional['JigsawPuzzle'] = None

    def __init__(self) -> None:
        if JigsawPuzzle.instance is not None:
            JigsawPuzzle.instance.close()
        self.rng = random.Random()
        self.pool = media.jigsaw_pool(self.rng)
        #: Paths shown this run, so that even a library too small for
        #: the run repeats as late as it can.
        self.shown: List[str] = []
        self.image = None
        self.tiles: List[pyglet.image.AbstractImage] = []
        self.order: List[int] = []
        self.side = SMALLEST_SIDE
        self.trial_side = SMALLEST_SIDE
        self.picked: Optional[int] = None
        self.hovered: Optional[int] = None
        self.swaps = 0
        self.par = 0
        self.puzzle = 0
        self.started_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, float, float]] = []
        self.phase = 'ready'
        self.sprites: List[pyglet.sprite.Sprite] = []
        self.drawn: List[object] = []
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_mouse_motion, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        JigsawPuzzle.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.JIGSAW)
        self.start_side = int(opts['JIGSAW_SIDE'])
        self.total_puzzles = int(opts['JIGSAW_PUZZLES'])
        self.adaptive = bool(opts['JIGSAW_ADAPTIVE'])
        self.preview = bool(opts['JIGSAW_PREVIEW'])
        self.mark_placed = bool(opts['JIGSAW_MARK_PLACED'])
        self.side = self.clamped(self.start_side)

    @staticmethod
    def clamped(side: int) -> int:
        return max(SMALLEST_SIDE, min(LARGEST_SIDE, side))

    def open_options(self) -> None:
        taskoptions.open_task_options('jigsaw', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.accent = (64, 96, 255, 255)
        self.rightcolor = (46, 160, 67, 255)
        self.batch = pyglet.graphics.Batch()
        self.tile_group = pyglet.graphics.Group(order=0)
        self.mark_group = pyglet.graphics.Group(order=1)
        self.title = pyglet.text.Label(
            _('Jigsaw Puzzle'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     click two tiles to swap'
              '     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self._redraw()

    def _canvas(self) -> Tuple[float, float, float, float]:
        """Left, bottom, width, height of the room the board may use."""
        window = state.window
        top = from_top_edge(96)
        bottom = from_bottom_edge(56)
        return (window.width * 0.04, bottom,
                window.width * 0.92, max(40.0, top - bottom))

    def _board_rect(self) -> Tuple[float, float, float]:
        """Left, bottom and size of the puzzle square.

        With the preview on, the board leaves a quarter of the width
        to its right for the finished picture — the lid of the box.
        """
        left, bottom, width, height = self._canvas()
        room = width * (0.72 if self.preview else 1.0)
        size = min(room, height)
        return (left + (room - size) / 2, bottom + (height - size) / 2,
                size)

    def _preview_rect(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._canvas()
        size = min(width * 0.24, height * 0.5)
        return (left + width - size, bottom + height - size, size)

    def _tile_rects(self) -> List[Tuple[float, float, float, float]]:
        board_left, board_bottom, size = self._board_rect()
        span = (size - SEAM * (self.trial_side - 1)) / self.trial_side
        rects = []
        for position in range(self.trial_side * self.trial_side):
            row, column = divmod(position, self.trial_side)
            left = board_left + column * (span + SEAM)
            top = board_bottom + size - row * (span + SEAM)
            rects.append((left, top - span, span, span))
        return rects

    def relayout(self) -> None:
        self._build_chrome()

    # --- a puzzle --------------------------------------------------------

    def _reset(self) -> None:
        self.puzzle = 0
        self.results = []
        self.order = []
        self.tiles = []
        self.image = None
        self.picked = None
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self.shown = []
        self.side = self.clamped(self.start_side)
        self._next_puzzle()

    # --- picking a photograph nobody has assembled lately ----------------

    def _seen_file(self) -> str:
        return os.path.join(datasets.local_dir(self.pool.dataset),
                            'seen.txt')

    def _seen(self) -> List[str]:
        try:
            with open(self._seen_file()) as handle:
                return [line.strip() for line in handle if line.strip()]
        except OSError:
            return []

    def _take_fresh(self) -> Optional[str]:
        """A photograph not assembled before, if one is left.

        The rotation lives on disk, not in this object: every image in
        the library gets a turn before any gets a second, whether the
        turns fall in one evening or across a month. When the library
        has been exhausted the rotation starts over — there is nothing
        else it could do — still holding back anything already shown
        in this run for as long as the library allows.
        """
        self.pool.reload()
        paths = list(self.pool.paths)
        if not paths:
            return None
        seen = set(self._seen())
        unseen = [path for path in paths
                  if os.path.basename(path) not in seen]
        if not unseen:
            try:
                os.remove(self._seen_file())
            except OSError:
                pass
            unseen = [path for path in paths
                      if path not in self.shown] or paths
        path = self.rng.choice(unseen)
        self.shown.append(path)
        try:
            with open(self._seen_file(), 'a') as handle:
                handle.write(os.path.basename(path) + '\n')
        except OSError:
            pass                    # a read-only disk only loses rotation
        return path

    def _cut(self, image) -> List[pyglet.image.AbstractImage]:
        """The largest centred square of *image*, in reading order."""
        square = min(image.width, image.height)
        left = (image.width - square) // 2
        bottom = (image.height - square) // 2
        span = square // self.trial_side
        tiles = []
        for row in range(self.trial_side):
            for column in range(self.trial_side):
                tiles.append(image.get_region(
                    left + column * span,
                    bottom + (self.trial_side - 1 - row) * span,
                    span, span))
        return tiles

    def _next_puzzle(self) -> None:
        if self.puzzle >= self.total_puzzles:
            self._finish()
            return
        path = self._take_fresh()
        image = self.pool.item(path) if path else None
        if image is None:
            self.phase = 'ready'
            self.message = _('No photograph library yet — see the Readme')
            self._redraw()
            return
        self.puzzle += 1
        self.trial_side = self.side
        # A library smaller than the run cannot help repeating itself,
        # and that should be said up front rather than discovered.
        stocked = len(self.pool.paths)
        self.small_library = (_('only %d photographs downloaded — '
                                'pictures will repeat; see the Readme')
                              % stocked
                              if stocked < self.total_puzzles else '')
        self.image = image
        self.tiles = self._cut(image)
        self.order = scramble(self.trial_side, self.rng)
        self.par = minimum_swaps(self.order)
        self.swaps = 0
        self.picked = None
        self.started_at = time.time()
        self.phase = 'solving'
        self.message = _('Put the picture back together')
        self._redraw()

    def _pick(self, position: int) -> None:
        """First click marks a tile; the second swaps the two."""
        if self.phase != 'solving':
            return
        if self.picked is None:
            self.picked = position
        elif self.picked == position:
            self.picked = None
        else:
            self.order[self.picked], self.order[position] = \
                self.order[position], self.order[self.picked]
            self.swaps += 1
            self.picked = None
            if all(tile == where for where, tile in enumerate(self.order)):
                self._solved()
        self._redraw()

    def _solved(self) -> None:
        took = time.time() - self.started_at
        efficiency = self.par / max(self.par, self.swaps)
        self.results.append((self.trial_side, efficiency, took))
        if self.adaptive:
            if efficiency >= GROW_AT:
                self.side = self.clamped(self.side + 1)
            elif efficiency < SHRINK_AT:
                self.side = self.clamped(self.side - 1)
        self.phase = 'solved'
        self.feedback_until = time.time() + 1.6
        self.message = (_('Solved in %d swaps — the minimum was %d — '
                          'in %.0fs') % (self.swaps, self.par, took))
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.image = None
        self.tiles = []
        self.order = []
        tally = self.score()
        self.message = _('%d puzzles, %d%% swap efficiency, %.0fs each, '
                         'largest grid %dx%d'
                         ) % (tally['puzzles'], tally['efficiency'],
                              tally['mean_seconds'], tally['best_side'],
                              tally['best_side'])
        self._redraw()

    def score(self) -> Dict[str, float]:
        """How the run went, on both of its axes.

        Efficiency is reported beside the time because they trade
        against each other: swapping fast and loose finishes sooner
        and scores lower, and the run should say which kind of solving
        it saw.
        """
        puzzles = len(self.results)
        return {
            'puzzles': puzzles,
            'efficiency': int(round(100 * sum(eff for _s, eff, _t
                                              in self.results) / puzzles)
                              ) if puzzles else 0,
            'mean_seconds': (sum(took for _s, _e, took in self.results)
                             / puzzles) if puzzles else 0.0,
            'best_side': max((side for side, _e, _t in self.results),
                             default=0),
        }

    def update(self, dt: float) -> None:
        if self.phase == 'solved' and time.time() >= self.feedback_until:
            self._next_puzzle()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for sprite in self.sprites:
            sprite.delete()
        self.sprites = []
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.phase in ('solving', 'solved') and self.tiles:
            rects = self._tile_rects()
            for position, (left, bottom, span, _height) in enumerate(rects):
                tile = self.tiles[self.order[position]]
                sprite = pyglet.sprite.Sprite(
                    tile, x=left, y=bottom, batch=self.batch,
                    group=self.tile_group)
                sprite.scale = span / float(tile.width)
                self.sprites.append(sprite)
                self._mark(position, rects[position])
            if self.preview and self.image is not None:
                left, bottom, size = self._preview_rect()
                square = min(self.image.width, self.image.height)
                lid = self.image.get_region(
                    (self.image.width - square) // 2,
                    (self.image.height - square) // 2, square, square)
                sprite = pyglet.sprite.Sprite(lid, x=left, y=bottom,
                                              batch=self.batch,
                                              group=self.tile_group)
                sprite.scale = size / float(square)
                self.sprites.append(sprite)
        self._update_labels()

    def _mark(self, position: int,
              rect: Tuple[float, float, float, float]) -> None:
        left, bottom, span, height = rect
        color: Optional[Tuple[int, int, int, int]] = None
        thickness = 2.0
        if position == self.picked:
            color, thickness = self.accent, 3.0
        elif self.phase == 'solved':
            color = self.rightcolor
        elif position == self.hovered:
            color = self.accent
        elif self.mark_placed and self.order[position] == position:
            color = self.rightcolor
        if color is not None:
            self.drawn.append(pyglet.shapes.Box(
                left, bottom, span, height, thickness=thickness,
                color=color, batch=self.batch, group=self.mark_group))

    def _update_labels(self) -> None:
        parts = [self.message]
        if self.phase in ('solving', 'solved'):
            parts.append(_('puzzle %d of %d   swaps %d   minimum %d   '
                           'tiles %dx%d')
                         % (self.puzzle, self.total_puzzles, self.swaps,
                            self.par, self.trial_side, self.trial_side))
            if getattr(self, 'small_library', ''):
                parts.append(self.small_library)
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if JigsawPuzzle.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_mouse_motion, self.on_draw)
        self._clear_drawn()
        JigsawPuzzle.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def _at(self, x: int, y: int) -> Optional[int]:
        for position, (left, bottom, span, height) in \
                enumerate(self._tile_rects()):
            if left <= x <= left + span and bottom <= y <= bottom + height:
                return position
        return None

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'solving':
            found = self._at(x, y)
            if found is not None:
                self._pick(found)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> bool:
        found = self._at(x, y) if self.phase == 'solving' else None
        if found != self.hovered:
            self.hovered = found
            self._redraw()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
