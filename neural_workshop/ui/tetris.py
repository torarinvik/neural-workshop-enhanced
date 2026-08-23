# -*- coding: utf-8 -*-
"""Freeform Tetris: choose the piece, hold the spin, leave no gap.

Three things are different from the game this is named after, and each
one is there to move the difficulty off the clock and onto the eye.

**The queue is a hand, not a conveyor.** Five pieces are on offer and
the player clicks the one that should come next. Nothing is dealt at
anybody; the question the game asks is *which of these, and where*,
and both halves of it are the player's.

**Rotation is continuous.** Holding Up or Down winds the piece round
at a steady rate through the whole circle rather than clacking through
four poses. Within a few degrees of a quarter turn the pose is pulled
onto the grid — a detent, wide enough to catch by hand — because a
piece square to the grid is the only kind whose cells are whole cells
and therefore the only kind that can be relied on to bury nothing.
Everywhere else the piece lands as the grid sees it, which is ragged,
and the ghost shows exactly how ragged before anything is committed.
The freedom is real and so is its price, and the screen shows both.

**Difficulty is shape and never speed.** Gravity is one setting the
player chooses once. The ladder underneath — see
:mod:`neural_workshop.tetris` — climbs by cutting more awkward pieces:
rectangles at the bottom, then one-step notches, then dented combs
that straddle six columns. A rung that is harder is harder to *see*,
and a player who has run out of ability has run out of it at packing
rather than at reacting.

The well is much wider and much finer than a tetris well —
seventy-two columns of about eleven-pixel cells by default against ten
of thirty — which is what turns "which of ten slots" into a search.

What is scored is gaps. Every placement either buries empty cells or
does not, the verdict says which, and the run reports the share of
placements that left the pile solid. That is a number the game can
promise is reachable: the engine keeps every piece in the queue cut so
that some gapless drop for it exists, re-cuts any piece the last move
stranded, and prints each piece's count of them beside it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state, tetris
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: The ghost's two colours: what this drop would do if it were let go
#: now. Teal buries nothing, red-orange buries something, and the
#: count of how much is on the status line beside it. Drawn as hollow
#: outlines rather than filled cells, which is the part that makes
#: them readable: the pile is already seven colours deep and a filled
#: ghost in any of them reads as another piece, whereas an outline
#: reads as a place. Neither is a verdict colour, and both are far
#: from the band the boundary reads, which is below the well entirely.
CLEAN_GHOST: Tuple[int, int, int] = (38, 166, 154)
RAGGED_GHOST: Tuple[int, int, int] = (240, 70, 30)

#: Okabe-Ito, the palette the rest of the workshop already uses, less
#: its pale yellow: a pile of ``(240, 228, 66)`` cells on the light
#: background is barely there, and the pile is the thing being read.
#: A violet stands in for it. A piece is coloured by how many cells it
#: has, so a glance at the tray sorts the hand by size without anybody
#: counting.
PIECE_COLORS: Tuple[Tuple[int, int, int], ...] = (
    (86, 180, 233), (0, 158, 115), (140, 110, 220), (0, 114, 178),
    (213, 94, 0), (204, 121, 167), (230, 159, 0))

#: How long a piece sits on what it has landed on before it locks, and
#: how many times a move or a spin may buy that time back. Generous on
#: purpose: this game's difficulty is not supposed to be in the wrist.
LOCK_DELAY: float = 0.6
LOCK_RESETS: int = 12

#: How much faster a piece falls while the soft drop is held.
SOFT_DROP: float = 12.0

#: How long the verdict stays up between placements. The action window
#: is shut for all of it — the piece is already in the pile — which is
#: what makes it a verdict rather than an answer key.
LANDED_SECONDS: float = 0.5

#: Sideways room a spin is allowed to take to get out of trouble, in
#: cells, tried nearest first. Without these a piece turning against a
#: wall simply refuses, and a continuous spin that refuses feels
#: broken rather than blocked.
KICKS: Tuple[Tuple[float, float], ...] = (
    (0.0, 0.0), (0.0, 0.3), (0.3, 0.0), (-0.3, 0.0), (0.0, 0.6),
    (0.6, 0.0), (-0.6, 0.0), (0.0, 1.0))

#: Clean placements in a row that climb a rung, and gapped placements
#: that fall off one. Asymmetric because climbing should take a run of
#: evidence and falling should take only enough to be sure.
CLIMB_AFTER: int = 6
SLIP_BUDGET: int = 3

#: Number keys that arm a tray slot, in slot order. Six, because six
#: is the widest tray the options screen offers.
NUMBER_KEYS: Tuple[int, ...] = (key._1, key._2, key._3, key._4, key._5,
                                key._6)


class FreeformTetris:
    """A wide fine well, a hand of pieces, and the whole circle to turn in."""

    instance: Optional['FreeformTetris'] = None

    def __init__(self) -> None:
        if FreeformTetris.instance is not None:
            FreeformTetris.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.held: set = set()
        self.spin = 0.0
        self.soft = False
        self.spun = 0.0
        self.piece: Optional[tetris.Piece] = None
        self.pose: Optional[tetris.Pose] = None
        self.landed_at: Optional[float] = None
        self.resets = 0
        self.until = 0.0
        self.results: List[Tuple[int, float, int]] = []
        self.pile: List[object] = []
        self.flying: List[object] = []
        self.ghost: List[object] = []
        self.tray: List[object] = []
        self.guides: List[object] = []
        self.slot_labels: List[pyglet.text.Label] = []
        self.slot_rects: List[Tuple[float, float, float, float]] = []
        self._read_options()
        self._reset()
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_key_release,
                                   self.on_mouse_press, self.on_mouse_motion,
                                   self.on_mouse_drag, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        FreeformTetris.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.TETRIS)
        self.cols = int(opts['TETRIS_COLUMNS'])
        self.rows = int(opts['TETRIS_ROWS'])
        self.start_rung = int(opts['TETRIS_RUNG'])
        self.total_pieces = int(opts['TETRIS_PIECES'])
        self.queue_size = int(opts['TETRIS_QUEUE'])
        self.fall_rate = float(opts['TETRIS_FALL'])
        self.spin_rate = float(opts['TETRIS_SPIN'])
        self.detent = float(opts['TETRIS_DETENT'])
        self.adaptive = bool(opts['TETRIS_ADAPTIVE'])
        self.show_ghost = bool(opts['TETRIS_GHOST'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(tetris.GRADES), int(rung)))

    def open_options(self) -> None:
        taskoptions.open_task_options('tetris', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.rung = self.clamped(self.start_rung)
        self.board = tetris.Board(self.cols, self.rows)
        self.queue = tetris.Queue(self.board, tetris.grade_at(self.rung),
                                  self.rng, self.queue_size)
        self.piece = None
        self.pose = None
        self.armed = 0
        self.placed = 0
        self.clean = 0
        self.buried = 0
        self.lines = 0
        self.streak = 0
        self.slips = 0
        self.recut = 0
        self.landing_gaps = 0
        self.best_rung = self.rung
        self.results = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        """Start a run at whatever the dials now say.

        The chrome is rebuilt rather than reused: the well's size and
        the width of the tray are both settings, and both decide where
        every shape on the screen goes.
        """
        self._reset()
        self._build_chrome()
        self._deal()

    def _deal(self) -> None:
        """Spawn the piece the player armed, and cut one to replace it."""
        self.piece = self.queue.take(self.armed)
        _width, height = tetris.extent(self.piece)
        self.spun = 0.0
        self.pose = tetris.Pose(0.0, self.cols / 2.0,
                                self.rows - height / 2.0)
        # Squared up on the way in. The middle of the well is half a
        # cell off the columns an odd-width piece will fill, and a
        # piece that starts off the lattice moves half a cell on its
        # first nudge and a whole one after -- which reads as the
        # controls being unreliable rather than as arithmetic.
        self._square_across()
        self.landed_at = None
        self.resets = 0
        self.verdict_shown = None
        self.verdict.clear()
        if tetris.blocked(self.board, self.piece, self.pose):
            self._finish(topped=True)
            return
        self.phase = 'falling'
        self.message = ''
        self._repaint()

    def _finish(self, topped: bool = False) -> None:
        self.phase = 'done'
        self.piece = None
        self.pose = None
        tally = self.score()
        self.message = (
            _('Topped out after %d pieces — %d%% of them left no gap, '
              '%d cells buried, %d rows cleared, rung %d')
            if topped else
            _('%d pieces — %d%% of them left no gap, %d cells buried, '
              '%d rows cleared, rung %d')) % (
            tally['pieces'], tally['clean'], tally['buried'],
            tally['lines'], tally['best_rung'])
        self._repaint()

    def score(self) -> Dict[str, float]:
        """How the run went. The share that left no gap is the score.

        Rows cleared is reported beside it and is deliberately not the
        headline: on a well this wide a row is seventy-two cells and
        clearing one says more about how long the run was than about
        how well it was packed.
        """
        placed = self.placed
        return {
            'pieces': placed,
            'clean': int(round(100.0 * self.clean / placed)) if placed else 0,
            'buried': self.buried,
            'lines': self.lines,
            'best_rung': self.best_rung,
            'recut': self.recut,
        }

    # --- the falling piece ------------------------------------------------

    def _detent(self, spun: float) -> float:
        """The angle a wound-to angle actually holds the piece at.

        Within the detent's width of a quarter turn this is that
        quarter turn exactly, and everywhere else it is what was
        wound. One angle, used for drawing, for collision, for the
        ghost and for the lock alike — so nothing the player is shown
        is a different piece from the one that lands.

        The detent exists because a piece square to the grid is the
        only kind whose cells are whole cells, and a corridor a few
        degrees wide is what makes one reachable while a piece is
        falling. It costs about a sixth of the circle, which the
        options screen will give back: set it to nothing and every one
        of the 360 degrees is held exactly as wound, with **S** the
        way to square up on purpose rather than by luck.
        """
        if abs((spun + 45.0) % 90.0 - 45.0) <= self.detent:
            return (round(spun / 90.0) % 4) * 90.0
        return spun % 360.0

    def on_the_grid(self) -> bool:
        """Whether the piece is square to the grid right now."""
        return self.pose is not None and self.pose.angle % 90.0 == 0.0

    def _touched(self) -> None:
        """A move or a spin buys a little more time before it locks."""
        if self.landed_at is not None and self.resets < LOCK_RESETS:
            self.landed_at = self.clock()
            self.resets += 1

    def _square_across(self) -> None:
        """Put a piece that is square to the grid on whole columns.

        Only sideways. A piece held at a quarter turn covers whole
        cells wherever its centre happens to be — the rasterisation
        rounds for it — so a centre a third of a cell to the left of
        the column it is filling is drawn a third of a cell left of
        where it will land. Half a cell of that is six pixels of lying
        about which column you are aiming at, on a game whose whole
        difficulty is which column you are aiming at.

        Vertically the same slack is *wanted*: it is what makes the
        fall a fall rather than a series of hops, and the ghost is
        already saying where the piece will come to rest.
        """
        square = tetris.snapped(self.piece, self.pose, 0.0)
        if square is not None:
            self.pose = tetris.Pose(self.pose.angle, square.cx, self.pose.cy)

    def _turn(self, degrees: float) -> bool:
        if not degrees or self.piece is None:
            return False
        spun = (self.spun + degrees) % 360.0
        angle = self._detent(spun)
        for dx, dy in KICKS:
            tried = tetris.Pose(angle, self.pose.cx + dx, self.pose.cy + dy)
            if not tetris.blocked(self.board, self.piece, tried):
                self.spun = spun
                self.pose = tried
                self._square_across()
                self._touched()
                return True
        return False

    def _slide(self, cx: float) -> bool:
        if self.piece is None:
            return False
        moved = tetris.Pose(self.pose.angle, cx, self.pose.cy)
        if tetris.blocked(self.board, self.piece, moved):
            return False
        self.pose = moved
        self._touched()
        return True

    def _slide_toward(self, target: float) -> None:
        """Walk sideways to *target*, stopping at whatever is in the way.

        Stepping rather than jumping is what stops the mouse from
        putting a piece through a wall of the pile it could not have
        travelled through.
        """
        target = max(0.0, min(float(self.cols), target))
        for _step in range(4 * self.cols + 4):
            gap = target - self.pose.cx
            if abs(gap) < 1e-6:
                break
            nudge = max(-0.25, min(0.25, gap))
            if not self._slide(self.pose.cx + nudge):
                break
        # Squared up once at the end rather than on every quarter-cell
        # step, so the walk still converges on the target it was given.
        self._square_across()

    def _sink(self, distance: float) -> None:
        while distance > 0.0:
            step = min(tetris.DROP_STEP, distance)
            lower = tetris.Pose(self.pose.angle, self.pose.cx,
                                self.pose.cy - step)
            if tetris.blocked(self.board, self.piece, lower):
                return
            self.pose = lower
            distance -= step

    def _resting(self) -> bool:
        below = tetris.Pose(self.pose.angle, self.pose.cx,
                            self.pose.cy - tetris.DROP_STEP)
        return tetris.blocked(self.board, self.piece, below)

    def drop(self) -> None:
        """Send the piece down as far as it goes and lock it there."""
        if self.phase != 'falling':
            return
        self._square_across()
        self.pose = tetris.settle(self.board, self.piece, self.pose)
        self._lock()

    def update(self, dt: float) -> None:
        if self.phase == 'falling':
            dt = min(dt, 0.1)
            if self.spin:
                self._turn(self.spin * self.spin_rate * dt)
            self._sink(self.fall_rate * dt
                       * (SOFT_DROP if self.soft else 1.0))
            if self._resting():
                if self.landed_at is None:
                    self.landed_at = self.clock()
                    self.resets = 0
                elif self.clock() - self.landed_at >= LOCK_DELAY:
                    self._lock()
                    return
            else:
                self.landed_at = None
            self._paint_flying()
            self._sync_labels()
        elif self.phase == 'landed' and self.clock() >= self.until:
            self._next_piece()

    # --- landing ----------------------------------------------------------

    def _lock(self) -> None:
        """Commit the piece where it stands, and say what that cost.

        The footprint is taken from the pose the player is looking at,
        so what lands is what was drawn. Gaps are counted before rows
        are cleared: a placement that buried three cells buried them
        whether or not the same move happened to complete a row.
        """
        cells = tetris.footprint(self.piece, self.pose)
        gaps = tetris.gaps_under(self.board, cells)
        topped = any(y >= self.rows for _x, y in cells)
        tint = 1 + (len(self.piece) % len(PIECE_COLORS))
        for x, y in cells:
            self.board.fill(x, y, tint)
        cleared = self.board.clear_full_rows()
        self.placed += 1
        self.lines += cleared
        self.buried += gaps
        self.results.append((self.rung, self.clock(), gaps))
        if gaps:
            self.streak = 0
            self.slips += 1
        else:
            self.clean += 1
            self.streak += 1
            self.slips = max(0, self.slips - 1)
        self.recut += self.queue.revalidate()
        if self.adaptive:
            self._reconsider_rung()
        self.piece = None
        self.pose = None
        self.phase = 'landed'
        self.until = self.clock() + LANDED_SECONDS
        self.message = self._landing_message(gaps, cleared)
        # Shown only now, with the piece already in the pile and the
        # action window shut: a verdict a player can still act on is an
        # answer key rather than a verdict.
        self.verdict_shown = (gaps == 0, self.message)
        self.verdict.show(*self.verdict_shown)
        self._repaint()
        if topped:
            self._finish(topped=True)

    def _landing_message(self, gaps: int, cleared: int) -> str:
        if gaps:
            said = _('Buried %d cells') % gaps
        else:
            said = _('No gap')
        if cleared:
            said += _(' — %d rows cleared') % cleared
        return said

    def _reconsider_rung(self) -> None:
        """Climb on a run of clean placements, fall off on a run of gaps."""
        if self.streak >= CLIMB_AFTER and self.rung < len(tetris.GRADES):
            self.rung = self.clamped(self.rung + 1)
            self.streak = 0
            self.slips = 0
            self.queue.grade = tetris.grade_at(self.rung)
        elif self.slips >= SLIP_BUDGET and self.rung > 1:
            self.rung = self.clamped(self.rung - 1)
            self.slips = 0
            self.queue.grade = tetris.grade_at(self.rung)
        self.best_rung = max(self.best_rung, self.rung)

    def _next_piece(self) -> None:
        # Guarded because two clocks call this: the task's own feedback
        # pause and, under the agent boundary, the driver dealing once
        # a settled frame has been published. Ungated, a run driven
        # that way would deal two pieces and score one.
        if self.phase != 'landed':
            return
        if self.placed >= self.total_pieces:
            self._finish()
            return
        self._deal()

    # --- choosing ---------------------------------------------------------

    def arm(self, slot: int) -> None:
        """Choose which of the pieces on offer comes next."""
        if self.phase not in ('falling', 'landed'):
            return
        self.armed = max(0, min(len(self.queue) - 1, int(slot)))
        self._paint_queue()
        self._sync_labels()

    #: What each opaque port does, for the agent boundary. The first
    #: five are the controls a person has on the keyboard; the rest arm
    #: a slot of the tray, which is what the mouse does.
    PORTS: Tuple[str, ...] = ('left', 'right', 'spin_out', 'spin_in',
                              'drop', 'arm', 'arm', 'arm', 'arm', 'arm',
                              'arm')

    def press(self, port: int) -> None:
        """One opaque action, by index. See :data:`PORTS`.

        A spin port turns by a fixed notch rather than holding the key
        down, because a stepped boundary has no notion of holding one.
        The notch is a fifteenth of a turn, so the whole circle is
        twenty-four presses and every quarter turn is reachable exactly.
        """
        if not 0 <= port < len(self.PORTS):
            return
        if self.phase != 'falling':
            if self.PORTS[port] == 'arm':
                self.arm(port - 5)
            return
        doing = self.PORTS[port]
        if doing == 'left':
            self._slide_toward(self.pose.cx - 1.0)
        elif doing == 'right':
            self._slide_toward(self.pose.cx + 1.0)
        elif doing == 'spin_out':
            self._turn(15.0)
        elif doing == 'spin_in':
            self._turn(-15.0)
        elif doing == 'drop':
            self.drop()
        else:
            self.arm(port - 5)

    # --- layout -----------------------------------------------------------

    def _canvas(self) -> Tuple[float, float, float, float]:
        """Left, bottom, width and height of the room the game may use."""
        window = state.window
        top = from_top_edge(92)
        bottom = above_the_band(from_bottom_edge(52))
        return (window.width * 0.03, bottom, window.width * 0.94,
                max(60.0, top - bottom))

    def _layout(self) -> None:
        """Work out the cell size, and everything that follows from it.

        The cell is whatever makes the whole well fit, which on an
        ordinary window is about eleven pixels — a third of a tetris
        cell, and the reason a piece is a small thing on a wide board
        rather than a large thing in a chimney.
        """
        left, bottom, width, height = self._canvas()
        tray = max(44.0, min(96.0, height * 0.22))
        room = max(30.0, height - tray - 12.0)
        self.cell = max(2.0, min(width / self.cols, room / self.rows))
        self.field_width = self.cell * self.cols
        self.field_height = self.cell * self.rows
        self.field_left = left + (width - self.field_width) / 2.0
        self.field_bottom = bottom
        self.tray_bottom = bottom + self.field_height + 12.0
        self.tray_height = tray
        slot = self.field_width / len(self.queue)
        self.slot_rects = [(self.field_left + index * slot, self.tray_bottom,
                            slot, tray) for index in range(len(self.queue))]

    def relayout(self) -> None:
        self._build_chrome()

    # --- chrome -----------------------------------------------------------

    def _clear_shapes(self) -> None:
        for store in (self.pile, self.flying, self.ghost, self.tray,
                      self.guides):
            for shape in store:
                try:
                    shape.delete()
                except Exception:
                    pass
            del store[:]

    def _build_chrome(self) -> None:
        """Create the batch, the colours and everything sized from the window.

        Called when the task opens and again after a resize, so a
        verdict already painted is put back at the end — a relayout on
        the frame a placement settles would otherwise drop the label,
        and an outcome only sometimes derivable is worse than one that
        never is.
        """
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.muted = (fg, fg, fg, 150)
        self.accent = (64, 96, 255, 255)
        self.linecolor = (fg, fg, fg)
        self._clear_shapes()
        self.batch = pyglet.graphics.Batch()
        self.back_group = pyglet.graphics.Group(order=0)
        self.pile_group = pyglet.graphics.Group(order=1)
        self.ghost_group = pyglet.graphics.Group(order=2)
        self.fly_group = pyglet.graphics.Group(order=3)
        self.tray_group = pyglet.graphics.Group(order=4)
        self.title = pyglet.text.Label(
            _('Freeform Tetris'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(30),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status_size = calc_fontsize(13)
        self.readout_size = calc_fontsize(11)
        self.status = pyglet.text.Label(
            '', font_size=self.status_size, color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(56),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.readout = pyglet.text.Label(
            '', font_size=self.readout_size, color=self.muted,
            batch=self.batch, x=width_center(), y=from_top_edge(76),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start, then drop   mouse: aim   '
              'hold Up/Down: spin   S: square up   '
              'click a piece or press 1-6: choose the next one   '
              'C: options'),
            font_size=calc_fontsize(10), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays each placement by this
        # label's colour. Everything this task draws otherwise stops at
        # above_the_band(), and tests/check_band.py is what says so.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=52)
        self._shrink(self.footnote, self.footnote.font_size)
        self._layout()
        self._build_frame()
        self._build_slot_labels()
        self._repaint()
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)

    def _build_frame(self) -> None:
        """The well, its guide lines, and a box round each tray slot.

        A guide every eight columns, because seventy-two cells of bare
        outline is a width nobody can count across, and every line
        would be a thicket.
        """
        well = pyglet.shapes.Rectangle(
            self.field_left, self.field_bottom, self.field_width,
            self.field_height, color=self.linecolor, batch=self.batch,
            group=self.back_group)
        well.opacity = 22
        self.guides.append(well)
        for column in range(8, self.cols, 8):
            line = pyglet.shapes.Line(
                self.field_left + column * self.cell, self.field_bottom,
                self.field_left + column * self.cell,
                self.field_bottom + self.field_height, thickness=1.0,
                color=self.linecolor, batch=self.batch,
                group=self.back_group)
            line.opacity = 34
            self.guides.append(line)
        for row in range(8, self.rows, 8):
            line = pyglet.shapes.Line(
                self.field_left, self.field_bottom + row * self.cell,
                self.field_left + self.field_width,
                self.field_bottom + row * self.cell, thickness=1.0,
                color=self.linecolor, batch=self.batch,
                group=self.back_group)
            line.opacity = 34
            self.guides.append(line)
        edge = pyglet.shapes.Box(
            self.field_left, self.field_bottom, self.field_width,
            self.field_height, thickness=1.5, color=self.linecolor,
            batch=self.batch, group=self.back_group)
        edge.opacity = 120
        self.guides.append(edge)
        for left, bottom, width, height in self.slot_rects:
            box = pyglet.shapes.Box(
                left + 3, bottom, width - 6, height, thickness=1.0,
                color=self.linecolor, batch=self.batch,
                group=self.back_group)
            box.opacity = 60
            self.guides.append(box)

    def _build_slot_labels(self) -> None:
        """One line under each tray slot: its number and its fit count.

        The count is the promise on display. It is how many different
        gapless drops that piece has on the board as it stands right
        now, recomputed after every placement, and it is never zero —
        a piece stranded by the last move is cut again before this is
        painted.
        """
        self.slot_labels = []
        for index, (left, bottom, width, _height) in \
                enumerate(self.slot_rects):
            self.slot_labels.append(pyglet.text.Label(
                '', font_size=calc_fontsize(9), color=self.muted,
                batch=self.batch, group=self.tray_group,
                x=left + width / 2.0, y=bottom - 8,
                anchor_x='center', anchor_y='center', font_name=FONTLIST))

    # --- painting ---------------------------------------------------------

    def _pool(self, store: List[object], count: int,
              group: pyglet.graphics.Group) -> List[object]:
        """*count* rectangles from *store*, growing it and hiding the rest.

        Pooled rather than rebuilt because the falling piece is redrawn
        sixty times a second, and a game that allocates a vertex list
        per cell per frame spends its time in the allocator.
        """
        while len(store) < count:
            store.append(pyglet.shapes.Rectangle(
                0.0, 0.0, 1.0, 1.0, color=(128, 128, 128),
                batch=self.batch, group=group))
        for spare in store[count:]:
            spare.visible = False
        return store[:count]

    def _outlines(self, store: List[object], count: int,
                  group: pyglet.graphics.Group) -> List[object]:
        """*count* hollow boxes from *store*, pooled the same way."""
        while len(store) < count:
            store.append(pyglet.shapes.Box(
                0.0, 0.0, 1.0, 1.0, thickness=1.0, color=(128, 128, 128),
                batch=self.batch, group=group))
        for spare in store[count:]:
            spare.visible = False
        return store[:count]

    def _retext(self, label: pyglet.text.Label, text: str,
                wanted: float) -> None:
        """Put *text* on *label* at *wanted* points, or smaller if it must.

        A status line is a sentence whose length depends on the rung's
        name, the numbers in it and the language it was translated
        into; a window is whatever size the player made it. Measuring
        is the only thing that copes with all three, and the
        alternative is a line that is comfortable in English on a wide
        window and runs off both edges everywhere else — which is what
        the first version of this screen did.

        Scaled by the ratio rather than stepped down, because glyph
        widths are near enough linear in the point size that one
        correction lands, and this runs while a piece is spinning.
        Skipped entirely when the text has not changed, which is most
        frames.
        """
        if label.text != text:
            label.text = text
            self._shrink(label, wanted)

    @staticmethod
    def _shrink(label: pyglet.text.Label, wanted: float) -> None:
        """Set *label* to *wanted* points, then down until it fits."""
        label.font_size = wanted
        room = state.window.width * 0.96
        for _pass in range(2):
            width = label.content_width
            if width <= room or not width:
                return
            label.font_size = max(5.0, label.font_size * room / width)

    def _repaint(self) -> None:
        self._paint_pile()
        self._paint_queue()
        self._paint_flying()
        self._sync_labels()

    def _paint_pile(self) -> None:
        stacked: List[Tuple[int, int, int]] = []
        for y in range(self.rows):
            row = self.board.cells[y]
            for x in range(self.cols):
                if row[x]:
                    stacked.append((x, y, row[x]))
        for shape, (x, y, tint) in zip(
                self._pool(self.pile, len(stacked), self.pile_group),
                stacked):
            shape.anchor_position = (0.0, 0.0)
            shape.rotation = 0.0
            shape.x = self.field_left + x * self.cell
            shape.y = self.field_bottom + y * self.cell
            shape.width = shape.height = max(1.0, self.cell - 1.0)
            shape.color = PIECE_COLORS[(tint - 1) % len(PIECE_COLORS)]
            shape.opacity = 235
            shape.visible = True

    def _paint_queue(self) -> None:
        """The hand, each piece drawn to fit its slot."""
        drawn: List[Tuple[float, float, float, Tuple[int, int, int], int]] = []
        for index, piece in enumerate(self.queue.pieces):
            left, bottom, width, height = self.slot_rects[index]
            span, tall = tetris.extent(piece)
            size = max(2.0, min((width - 14.0) / span, (height - 14.0) / tall,
                                self.cell * 1.6))
            origin_x = left + (width - size * span) / 2.0
            origin_y = bottom + (height - size * tall) / 2.0
            colour = PIECE_COLORS[len(piece) % len(PIECE_COLORS)]
            alpha = 255 if index == self.armed else 185
            for x, y in sorted(piece):
                drawn.append((origin_x + x * size, origin_y + y * size,
                              size, colour, alpha))
        for shape, (x, y, size, colour, alpha) in zip(
                self._pool(self.tray, len(drawn), self.tray_group), drawn):
            shape.anchor_position = (0.0, 0.0)
            shape.rotation = 0.0
            shape.x = x
            shape.y = y
            shape.width = shape.height = max(1.0, size - 1.0)
            shape.color = colour
            shape.opacity = alpha
            shape.visible = True
        counted = self.queue.fits
        for index, label in enumerate(self.slot_labels):
            fits = counted[index] if index < len(counted) else 0
            mark = _('%d) %d fits') % (index + 1, fits)
            if self.queue.recut[index]:
                mark += _(' · re-cut')
            label.text = mark
            label.color = self.accent if index == self.armed else self.muted

    def _paint_flying(self) -> None:
        """The piece in the air, and the ghost of where it would land."""
        if self.piece is None or self.pose is None:
            self._outlines(self.ghost, 0, self.ghost_group)
            self._pool(self.flying, 0, self.fly_group)
            return
        landing = tetris.settle(self.board, self.piece, self.pose)
        shadow = sorted(tetris.footprint(self.piece, landing))
        self.landing_gaps = tetris.gaps_under(self.board, shadow)
        colour = CLEAN_GHOST if not self.landing_gaps else RAGGED_GHOST
        shadow = shadow if self.show_ghost else []
        thick = max(1.0, round(self.cell * 0.16))
        for shape, (x, y) in zip(
                self._outlines(self.ghost, len(shadow), self.ghost_group),
                shadow):
            shape.anchor_position = (0.0, 0.0)
            shape.rotation = 0.0
            shape.x = self.field_left + x * self.cell
            shape.y = self.field_bottom + y * self.cell
            shape.width = shape.height = max(2.0, self.cell - 1.0)
            shape.thickness = thick
            shape.color = colour
            shape.opacity = 235
            shape.visible = True
        colour = PIECE_COLORS[len(self.piece) % len(PIECE_COLORS)]
        half = self.cell / 2.0
        for shape, (bx, by) in zip(
                self._pool(self.flying, len(self.piece), self.fly_group),
                tetris.centres(self.piece, self.pose)):
            shape.anchor_position = (half, half)
            shape.x = self.field_left + bx * self.cell
            shape.y = self.field_bottom + by * self.cell
            shape.width = shape.height = max(1.0, self.cell - 0.5)
            # pyglet turns clockwise; the piece's angle is anticlockwise.
            shape.rotation = -self.pose.angle
            shape.color = colour
            shape.opacity = 255
            shape.visible = True

    def _sync_labels(self) -> None:
        grade = tetris.grade_at(self.rung)
        parts: List[str] = []
        if self.phase in ('falling', 'landed'):
            parts.append(_('rung %d · %s   piece %d/%d   no gap %d/%d   '
                           'buried %d   rows %d')
                         % (self.rung, grade.name, self.placed + 1,
                            self.total_pieces, self.clean, self.placed,
                            self.buried, self.lines))
        if self.phase != 'falling':
            parts.append(self.message)
        said: List[str] = []
        if self.pose is not None:
            said.append(_('%d° %s') % (
                round(self.pose.angle),
                _('square') if self.on_the_grid() else _('free')))
            said.append(_('this drop leaves no gap') if not self.landing_gaps
                        else _('this drop buries %d') % self.landing_gaps)
        if self.queue.fits:
            said.append(_('every piece still fits (fewest %d ways)')
                        % min(self.queue.fits))
        self._retext(self.status, '   '.join(parts), self.status_size)
        self._retext(self.readout, '   '.join(said), self.readout_size)

    # --- events -----------------------------------------------------------

    def _in_field(self, x: float, y: float) -> bool:
        return (self.field_left <= x <= self.field_left + self.field_width
                and self.field_bottom <= y
                <= self.field_bottom + self.field_height)

    def _slot_at(self, x: float, y: float) -> Optional[int]:
        for index, (left, bottom, width, height) in \
                enumerate(self.slot_rects):
            if left <= x <= left + width and bottom <= y <= bottom + height:
                return index
        return None

    def square_up(self) -> None:
        """Wind to the nearest quarter turn in one go."""
        if self.phase == 'falling':
            self._turn((round(self.spun / 90.0) * 90.0) - self.spun
                       or 0.0001)

    def _sync_spin(self) -> None:
        self.spin = ((1.0 if 'out' in self.held else 0.0)
                     - (1.0 if 'in' in self.held else 0.0))

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            else:
                self.drop()
        elif symbol == key.UP:
            self.held.add('out')
            self._sync_spin()
        elif symbol == key.DOWN:
            self.held.add('in')
            self._sync_spin()
        elif symbol in (key.LEFT, key.A) and self.phase == 'falling':
            self._slide_toward(self.pose.cx - 1.0)
        elif symbol in (key.RIGHT, key.D) and self.phase == 'falling':
            self._slide_toward(self.pose.cx + 1.0)
        elif symbol in (key.LSHIFT, key.RSHIFT):
            self.soft = True
        elif symbol == key.S:
            self.square_up()
        elif symbol in NUMBER_KEYS:
            self.arm(NUMBER_KEYS.index(symbol))
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.UP:
            self.held.discard('out')
            self._sync_spin()
        elif symbol == key.DOWN:
            self.held.discard('in')
            self._sync_spin()
        elif symbol in (key.LSHIFT, key.RSHIFT):
            self.soft = False
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> bool:
        if self.phase == 'falling' and self._in_field(x, y):
            self._slide_toward((x - self.field_left) / self.cell)
            self._paint_flying()
            self._sync_labels()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int,
                      buttons: int, modifiers: int) -> bool:
        return self.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase in ('ready', 'done'):
            # Anywhere at all, including the tray: a click on a piece
            # before the run has started is somebody asking to play,
            # not somebody choosing the second piece.
            self.start_run()
            return pyglet.event.EVENT_HANDLED
        slot = self._slot_at(x, y)
        if slot is not None:
            self.arm(slot)
        elif self.phase == 'falling' and self._in_field(x, y):
            self.drop()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED

    # --- lifecycle --------------------------------------------------------

    def close(self) -> None:
        if FreeformTetris.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(
            self.on_key_press, self.on_key_release, self.on_mouse_press,
            self.on_mouse_motion, self.on_mouse_drag, self.on_draw)
        self._clear_shapes()
        FreeformTetris.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='planning')
