# -*- coding: utf-8 -*-
"""Jigsaw Puzzle: put a scrambled photograph back together.

A photograph is cut into a grid of tiles -- two of them, or a dozen, or
hundreds; there is no ceiling but the pixels -- and the tiles are
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

import math
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
from .verdict import VerdictLabel, above_the_band

#: The fewest pieces a puzzle may have: a picture cut in two. There is
#: no most. A grid is as many columns and rows as come closest to the
#: number asked for, so the count dealt can be a little over it; past a
#: few hundred the tiles are small, and telling one patch of sky from
#: another is the puzzle.
FEWEST = 2

#: Agent ports: one to a board position for the first hundred, then a
#: cursor -- up, down, left, right, pick -- which reaches any board.
DIRECT = 100
UP, DOWN, LEFT, RIGHT, PICK = 100, 101, 102, 103, 104
PORTS = 105

#: How efficient a solution has to be before an adaptive run grows the
#: grid, and how far below that it falls before the grid shrinks.
#: Efficiency is the minimum number of swaps over the number used, so
#: one is a perfect solve.
GROW_AT, SHRINK_AT = 0.7, 0.45


def grid_for(pieces: int, aspect: float = 1.0) -> Tuple[int, int]:
    """Columns and rows for about *pieces* tiles of a picture *aspect*
    wide for its height: the grid whose tiles are nearest square with
    at least that many of them."""
    pieces = max(FEWEST, int(pieces))
    columns = max(1, int(round(math.sqrt(pieces * aspect))))
    rows = max(1, -(-pieces // columns))
    if columns * rows < FEWEST:
        rows = FEWEST
    return columns, rows


def count_for(pieces: int, aspect: float = 1.0) -> int:
    columns, rows = grid_for(pieces, aspect)
    return columns * rows


def _settled(pieces: int, aspect: float) -> bool:
    """Whether asking for *pieces* deals exactly that many."""
    return count_for(pieces, aspect) == pieces


def bigger(pieces: int, aspect: float = 1.0) -> int:
    """The next grid up from the one *pieces* deals."""
    more = count_for(pieces, aspect) + 1
    while not _settled(more, aspect):
        more += 1
    return more


def smaller(pieces: int, aspect: float = 1.0) -> int:
    """The next grid down, never below two pieces."""
    fewer = count_for(pieces, aspect) - 1
    while fewer > FEWEST and not _settled(fewer, aspect):
        fewer -= 1
    return max(FEWEST, fewer)


def seam_for(span: float) -> float:
    """The gap ruled between tiles: wide enough that edges never fuse
    into a finished-looking picture, and gone once tiles are too small
    to spare it."""
    return 2.0 if span >= 24 else (1.0 if span >= 10 else 0.0)


def scramble(count: int, rng: random.Random) -> List[int]:
    """A shuffle of *count* tiles, never the solved one.

    ``order[position]`` is the tile shown at *position*. The identity
    is redrawn away rather than patched away — swapping a pair into an
    almost-sorted shuffle would bias small grids toward one-swap
    puzzles.
    """
    order = list(range(count))
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
    """Show a scrambled picture, swap tiles by clicks, score it.

    The tiles are regions of one texture. A photograph leaves it
    alone; :class:`neural_workshop.ui.videojigsaw.VideoJigsaw` pours
    each frame of a clip into it, so every tile plays its own part of
    the picture in step and no sprite is touched to do it.
    """

    instance: Optional['JigsawPuzzle'] = None

    #: What a subclass changes: its name, its options, where it lives.
    TITLE = 'Jigsaw Puzzle'
    TASK_ID = 'jigsaw'
    PREFIX = 'JIGSAW'
    CATEGORY = 'reasoning'
    #: Width over height of the picture the board shows.
    ASPECT = 1.0
    #: Frames a second, where the picture moves.
    FPS = 15

    def __init__(self) -> None:
        cls = type(self)
        if cls.instance is not None:
            cls.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.pool = self._make_pool()
        #: Paths shown this run, so that even a library too small for
        #: the run repeats as late as it can.
        self.shown: List[str] = []
        self.image = None
        self.tiles: List[pyglet.image.AbstractImage] = []
        self.order: List[int] = []
        self.pieces = FEWEST
        self.columns, self.rows = grid_for(FEWEST, self.ASPECT)
        self.picked: Optional[int] = None
        self.hovered: Optional[int] = None
        #: The keyboard's and the agent's cursor, shown once it is used.
        self.cursor = 0
        self.cursor_shown = False
        self.swaps = 0
        self.par = 0
        self.puzzle = 0
        self.started_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, float, float]] = []
        self.phase = 'ready'
        self.small_library = ''
        self.verdict_shown: Optional[Tuple[bool, str]] = None
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
        cls.instance = self

    def _make_pool(self):
        return media.jigsaw_pool(self.rng)

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        prefix = self.PREFIX
        opts = taskoptions.settings(getattr(taskoptions, prefix))
        self.start_pieces = int(opts[prefix + '_PIECES'])
        self.total_puzzles = int(opts[prefix + '_PUZZLES'])
        self.adaptive = bool(opts[prefix + '_ADAPTIVE'])
        self.preview = bool(opts[prefix + '_PREVIEW'])
        self.mark_placed = bool(opts[prefix + '_MARK_PLACED'])
        self.pieces = self.clamped(self.start_pieces)

    @staticmethod
    def clamped(pieces: int) -> int:
        return max(FEWEST, int(pieces))

    @property
    def trial_pieces(self) -> int:
        return self.columns * self.rows

    def open_options(self) -> None:
        taskoptions.open_task_options(self.TASK_ID,
                                      on_apply=self.apply_options)

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
        self.cursorcolor = (240, 150, 30, 255)
        self.batch = pyglet.graphics.Batch()
        self.tile_group = pyglet.graphics.Group(order=0)
        self.mark_group = pyglet.graphics.Group(order=1)
        self.title = pyglet.text.Label(
            _(self.TITLE), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu   Space: start   click two tiles to swap '
              '(or arrows and Enter)   C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour; tests/check_band.py is what says nothing else
        # this task draws puts a saturated colour in the bottom quarter.
        # Rebuilt with the chrome, so a verdict already up is put back —
        # a relayout on the frame a trial settles would otherwise drop
        # it, and an outcome only sometimes derivable is worse than one
        # that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        # The sprites belonged to the old batch.
        self.sprites = []
        self.drawn = []
        self._redraw()

    def _canvas(self) -> Tuple[float, float, float, float]:
        """Left, bottom, width, height of the room the board may use."""
        window = state.window
        top = from_top_edge(96)
        bottom = above_the_band(from_bottom_edge(56))
        return (window.width * 0.04, bottom,
                window.width * 0.92, max(40.0, top - bottom))

    def _board_rect(self) -> Tuple[float, float, float, float]:
        """Left, bottom, width and height of the board.

        With the preview on, the board leaves a quarter of the width
        to its right for the finished picture — the lid of the box.
        """
        left, bottom, width, height = self._canvas()
        room = width * (0.72 if self.preview else 1.0)
        board_w = min(room, height * self.ASPECT)
        board_h = board_w / self.ASPECT
        return (left + (room - board_w) / 2,
                bottom + (height - board_h) / 2, board_w, board_h)

    def _preview_rect(self) -> Tuple[float, float, float, float]:
        left, bottom, width, height = self._canvas()
        w = min(width * 0.24, height * 0.5 * self.ASPECT)
        h = w / self.ASPECT
        return (left + width - w, bottom + height - h, w, h)

    def _spans(self) -> Tuple[float, float, float]:
        """A tile's width and height on the board, and the seam."""
        _left, _bottom, board_w, board_h = self._board_rect()
        seam = seam_for(min(board_w / self.columns, board_h / self.rows))
        return ((board_w - seam * (self.columns - 1)) / self.columns,
                (board_h - seam * (self.rows - 1)) / self.rows, seam)

    def _rect(self, position: int) -> Tuple[float, float, float, float]:
        left, bottom, _w, board_h = self._board_rect()
        span_w, span_h, seam = self._spans()
        row, column = divmod(position, self.columns)
        top = bottom + board_h - row * (span_h + seam)
        return (left + column * (span_w + seam), top - span_h, span_w,
                span_h)

    def _tile_rects(self) -> List[Tuple[float, float, float, float]]:
        return [self._rect(p) for p in range(self.trial_pieces)]

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
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self.shown = []
        self.pieces = self.clamped(self.start_pieces)
        self._next_puzzle()

    # --- picking a picture nobody has assembled lately --------------------

    #: The rotation's file, beside the library.
    SEEN = 'seen.txt'

    def _seen_file(self) -> str:
        return os.path.join(datasets.local_dir(self.pool.dataset),
                            self.SEEN)

    def _seen(self) -> List[str]:
        try:
            with open(self._seen_file()) as handle:
                return [line.strip() for line in handle if line.strip()]
        except OSError:
            return []

    def _take_fresh(self) -> Optional[str]:
        """A picture not assembled before, if one is left.

        The rotation lives on disk, not in this object: every item in
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

    def _load_picture(self) -> Optional[pyglet.image.AbstractImage]:
        """The next picture, or None with the reason left in
        :attr:`message`."""
        path = self._take_fresh()
        image = self.pool.item(path) if path else None
        if image is None:
            self.message = _('No photograph library yet — see the Readme')
            return None
        # The largest centred square of the photograph.
        square = min(image.width, image.height)
        return image.get_region((image.width - square) // 2,
                                (image.height - square) // 2,
                                square, square)

    def _library_note(self) -> str:
        stocked = len(self.pool.paths)
        return (_('only %d photographs downloaded — pictures will '
                  'repeat; see the Readme') % stocked
                if stocked < self.total_puzzles else '')

    def _cut(self, image) -> List[pyglet.image.AbstractImage]:
        """*image* in tiles, in reading order."""
        span_w = image.width // self.columns
        span_h = image.height // self.rows
        tiles = []
        for row in range(self.rows):
            for column in range(self.columns):
                tiles.append(image.get_region(
                    column * span_w, (self.rows - 1 - row) * span_h,
                    span_w, span_h))
        return tiles

    def _next_puzzle(self) -> None:
        if self.puzzle >= self.total_puzzles:
            self._finish()
            return
        picture = self._load_picture()
        if picture is None:
            self.phase = 'ready'
            self._redraw()
            return
        self.puzzle += 1
        # A grid finer than the picture's pixels cannot be cut.
        columns, rows = grid_for(self.pieces, self.ASPECT)
        self.columns = max(1, min(columns, picture.width))
        self.rows = max(1, min(rows, picture.height))
        # A library smaller than the run cannot help repeating itself,
        # and that should be said up front rather than discovered.
        self.small_library = self._library_note()
        # One texture, and every tile a region of it: a board of
        # hundreds is then one draw call, not hundreds.
        self.image = picture.get_texture()
        self.tiles = self._cut(self.image)
        self.order = scramble(self.trial_pieces, self.rng)
        self.par = minimum_swaps(self.order)
        self.swaps = 0
        self.picked = None
        self.cursor = 0
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'solving'
        self.message = _('Put the picture back together')
        self._redraw()

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        """One agent port: a board position (the first hundred), or the
        cursor -- up, down, left, right, pick."""
        if port < DIRECT:
            self._pick(port)
        elif port == PICK:
            self.cursor_shown = True
            self._pick(self.cursor)
        elif port in (UP, DOWN, LEFT, RIGHT):
            self.move_cursor({UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0),
                              RIGHT: (1, 0)}[port])

    def move_cursor(self, step: Tuple[int, int]) -> None:
        if self.phase != 'solving':
            return
        row, column = divmod(self.cursor, self.columns)
        column = max(0, min(self.columns - 1, column + step[0]))
        row = max(0, min(self.rows - 1, row + step[1]))
        self.cursor = row * self.columns + column
        self.cursor_shown = True
        self._remark()

    def _pick(self, position: int) -> None:
        """First click marks a tile; the second swaps the two.

        A position off the end of the board is refused. A click cannot
        produce one, but a caller driving the task directly can, and a
        swap against an index nothing is at would corrupt the
        permutation rather than fail.
        """
        if self.phase != 'solving' or not 0 <= position < len(self.order):
            return
        if self.picked is None:
            self.picked = position
        elif self.picked == position:
            self.picked = None
        else:
            other = self.picked
            self.order[other], self.order[position] = \
                self.order[position], self.order[other]
            self.swaps += 1
            self.picked = None
            # Only the two tiles that moved are redrawn: a board of
            # hundreds must not be rebuilt for one swap.
            for where in (other, position):
                if where < len(self.sprites):
                    self.sprites[where].image = self.tiles[self.order[where]]
            if all(tile == where for where, tile in enumerate(self.order)):
                self._solved()
                return
        self._remark()

    def _grow(self, efficiency: float) -> None:
        if efficiency >= GROW_AT:
            self.pieces = bigger(self.pieces, self.ASPECT)
        elif efficiency < SHRINK_AT:
            self.pieces = smaller(self.pieces, self.ASPECT)

    def _solved(self) -> None:
        took = self.clock() - self.started_at
        efficiency = self.par / max(self.par, self.swaps)
        self.results.append((self.trial_pieces, efficiency, took))
        if self.adaptive:
            self._grow(efficiency)
        self.phase = 'solved'
        self.feedback_until = self.clock() + 1.6
        self.message = (_('Solved in %d swaps — the minimum was %d — '
                          'in %.0fs') % (self.swaps, self.par, took))
        # Green means the fewest swaps this scramble could be undone
        # in, which is exact: the minimum is n minus the number of
        # cycles in the permutation, not a bound on it.
        self.verdict_shown = (self.swaps <= self.par, self.message)
        self.verdict.show(*self.verdict_shown)
        self._remark()

    def _finish(self) -> None:
        self.phase = 'done'
        self.image = None
        self.tiles = []
        self.order = []
        tally = self.score()
        self.message = _('%d puzzles, %d%% swap efficiency, %.0fs each, '
                         'largest puzzle %d pieces'
                         ) % (tally['puzzles'], tally['efficiency'],
                              tally['mean_seconds'], tally['most_pieces'])
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
            'most_pieces': max((count for count, _e, _t in self.results),
                               default=0),
        }

    def _play(self) -> None:
        """Move a moving picture on; a photograph has nothing to do."""

    def update(self, dt: float) -> None:
        if self.phase == 'solved' and self.clock() >= self.feedback_until:
            self._next_puzzle()
            return
        if self.phase in ('solving', 'solved'):
            self._play()

    # --- drawing ---------------------------------------------------------

    def _clear_marks(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _clear_drawn(self) -> None:
        for sprite in self.sprites:
            try:
                sprite.delete()
            except Exception:
                pass
        self.sprites = []
        self._clear_marks()

    def _redraw(self) -> None:
        """Rebuild the board: once a puzzle, and when the window moves."""
        self._clear_drawn()
        if self.phase in ('solving', 'solved') and self.tiles:
            span_w, span_h, _seam = self._spans()
            for position in range(self.trial_pieces):
                left, bottom, _w, _h = self._rect(position)
                tile = self.tiles[self.order[position]]
                sprite = pyglet.sprite.Sprite(
                    tile, x=left, y=bottom, batch=self.batch,
                    group=self.tile_group)
                sprite.scale_x = span_w / float(tile.width)
                sprite.scale_y = span_h / float(tile.height)
                self.sprites.append(sprite)
            if self.preview and self.image is not None:
                left, bottom, w, h = self._preview_rect()
                sprite = pyglet.sprite.Sprite(self.image, x=left, y=bottom,
                                              batch=self.batch,
                                              group=self.tile_group)
                sprite.scale_x = w / float(self.image.width)
                sprite.scale_y = h / float(self.image.height)
                self.sprites.append(sprite)
        self._remark()

    def _remark(self) -> None:
        """Redraw the outlines and the words, and nothing else."""
        self._clear_marks()
        if self.phase in ('solving', 'solved') and self.order:
            marked = {}
            if self.phase == 'solved':
                # One frame round the whole picture, not one per tile.
                left, bottom, w, h = self._board_rect()
                self.drawn.append(pyglet.shapes.Box(
                    left - 3, bottom - 3, w + 6, h + 6, thickness=3.0,
                    color=self.rightcolor, batch=self.batch,
                    group=self.mark_group))
            else:
                if self.mark_placed:
                    for position, tile in enumerate(self.order):
                        if tile == position:
                            marked[position] = (self.rightcolor, 2.0)
                if self.hovered is not None:
                    marked[self.hovered] = (self.accent, 2.0)
                if self.cursor_shown:
                    marked[self.cursor] = (self.cursorcolor, 3.0)
                if self.picked is not None:
                    marked[self.picked] = (self.accent, 3.0)
            for position, (color, thickness) in marked.items():
                if position >= len(self.order):
                    continue
                left, bottom, span_w, span_h = self._rect(position)
                self.drawn.append(pyglet.shapes.Box(
                    left, bottom, span_w, span_h, thickness=thickness,
                    color=color, batch=self.batch, group=self.mark_group))
        self._update_labels()

    def _update_labels(self) -> None:
        if self.phase in ('solving', 'solved'):
            # The verdict label says how a solve went; this line is
            # the count, and must fit a board's worth of digits.
            parts = [_('puzzle %d of %d   swaps %d   minimum %d   '
                       '%d pieces (%dx%d)')
                     % (self.puzzle, self.total_puzzles, self.swaps,
                        self.par, self.trial_pieces, self.columns,
                        self.rows)]
            if self.small_library:
                parts.append(self.small_library)
        else:
            parts = [self.message]
        self.status.font_size = calc_fontsize(14)
        self.status.text = '     '.join(parts)
        room = state.window.width * 0.96
        if self.status.content_width > room:
            self.status.font_size = max(
                6, calc_fontsize(14) * room / self.status.content_width)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        cls = type(self)
        if cls.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_mouse_motion, self.on_draw)
        self._clear_drawn()
        cls.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category=self.CATEGORY)

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
        elif self.phase == 'solving':
            arrows = {key.UP: (0, -1), key.DOWN: (0, 1),
                      key.LEFT: (-1, 0), key.RIGHT: (1, 0)}
            if symbol in arrows:
                self.move_cursor(arrows[symbol])
            elif symbol in (key.RETURN, key.ENTER, key.SPACE):
                self.steer(PICK)
        return pyglet.event.EVENT_HANDLED

    def _at(self, x: int, y: int) -> Optional[int]:
        if not self.order:
            return None
        left, bottom, board_w, board_h = self._board_rect()
        if not (left <= x <= left + board_w
                and bottom <= y <= bottom + board_h):
            return None
        span_w, span_h, seam = self._spans()
        column = min(self.columns - 1, int((x - left) / (span_w + seam)))
        row = min(self.rows - 1,
                  int((bottom + board_h - y) / (span_h + seam)))
        return row * self.columns + column

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
            self._remark()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
