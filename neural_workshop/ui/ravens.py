# -*- coding: utf-8 -*-
"""Matrix Reasoning: finish the pattern.

A three-by-three grid of drawings follows rules the player has to
work out — a shape repeats down the columns, turns a little at each
step, shrinks, changes shading, gains a copy, or two cells combine
into a third. The bottom-right cell is missing, and eight candidates
sit beside the grid. Exactly one of them is right.

The puzzles are generated, not drawn: :mod:`neural_workshop.ravens`
builds one from a seed in well under a millisecond, so a run never
repeats itself and the difficulty can move with the player.

**Why the puzzle is drawn on white paper in both themes.** The five
shadings are translucent inks — a fill is a wash over the paper, not a
flat colour — and that is what makes them read as a ordered series
from unfilled to solid. Composited over a black background instead,
the lightest and the darkest both come out black and the series
collapses: two rules that differ only in shading would become
indistinguishable. Rather than invent a second set of shadings for
dark mode and hope they carry the same ordering, the puzzle keeps its
paper. Everything around it follows the theme.

**Why it is rendered offscreen.** The shapes are drawn once per trial
into a texture three times the size they are shown at, then scaled
down. That is plain supersampling, and it is here because the outlines
carry the rules: a rotation of an eighth of a turn has to be visible
as a rotation, and a staircase of hard pixel edges hides small angles.
Drawing the shapes directly every frame would also mean re-tessellating
several hundred triangles sixty times a second to show a picture that
never moves.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pyglet
from pyglet import gl
from pyglet.image import Framebuffer, Texture
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from ..ravens import GRADES, generate
from ..ravens.palette import GREYS, PALETTES
from ..ravens.figures import Figure
from ..ravens.geometry import triangulate
from . import cursor, taskoptions

#: How much bigger than its final size a card is drawn before being
#: scaled down. Three is where the stair-stepping on a slow diagonal
#: stops being visible; higher costs texture memory for no gain the
#: eye can find.
SUPERSAMPLE = 3

#: Panel size the card is laid out in. Purely internal: the engine
#: places figures in a unit square and the card is drawn at whatever
#: the window allows, so this only fixes the arithmetic below.
CELL_UNITS = 100

#: Gap between panels, in the same units. Wide enough that the figures
#: in neighbouring panels are plainly separate things.
GAP_UNITS = 7

#: The paper the puzzle is drawn on, and the ink used for outlines.
PAPER = (255, 255, 255, 255)
INK = (0, 0, 0, 255)

#: Panel borders on the paper: enough to group the figures, faint
#: enough not to be read as figures themselves. A printed Raven's sheet
#: rules its matrix in hairlines for the same reason.
RULE_LINE = (176, 176, 176, 255)

#: The border on the empty panel, which is a question rather than a
#: panel that happens to be blank.
EMPTY_LINE = (110, 110, 110, 255)

#: How thick a figure's outline is drawn, as a share of a panel. Thin
#: and even: a heavy line turns a small figure into a blot, and the
#: sizes have to stay tellable apart at the bottom of the ladder.
STROKE_SHARE = 0.016

#: The hairline the panels are ruled with, in the same share.
RULE_SHARE = 0.006

#: The answer choices are laid out beside the grid in two columns;
#: how many rows depends on the puzzle, because the easy grades offer
#: four answers where the rest offer eight.
CHOICE_COLUMNS = 2


class Card:
    """A texture holding one drawn grid, rendered offscreen.

    ``draw`` is handed a batch and works in card units with y growing
    *downward*, the space the engine lays shapes out in; the projection
    set here is what flips it, so no caller has to remember to.
    """

    def __init__(self, units_wide: float, units_high: float,
                 pixels_wide: int) -> None:
        self.units_wide = units_wide
        self.units_high = units_high
        self.pixels_wide = max(1, int(pixels_wide))
        self.pixels_high = max(1, int(pixels_wide * units_high / units_wide))
        self.texture = Texture.create(self.pixels_wide * SUPERSAMPLE,
                                      self.pixels_high * SUPERSAMPLE,
                                      min_filter=gl.GL_LINEAR,
                                      mag_filter=gl.GL_LINEAR)
        self.framebuffer = Framebuffer()
        self.framebuffer.attach_texture(self.texture)

    def render(self, draw: Callable[[pyglet.graphics.Batch], List]) -> None:
        """Paint the card. ``draw`` adds shapes to the batch it is given.

        The clear colour is put back before returning. It is global
        GL state, and the window's own ``clear()`` uses it: leaving it
        set to paper white repainted the whole window white on the
        next frame, which on the dark theme meant white text on white.
        """
        window = state.window
        batch = pyglet.graphics.Batch()
        held = draw(batch)          # kept alive until the draw call is done

        was_clear = (gl.GLfloat * 4)()
        gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE, was_clear)
        saved = window.projection

        self.framebuffer.bind()
        gl.glViewport(0, 0, self.texture.width, self.texture.height)
        gl.glClearColor(PAPER[0] / 255., PAPER[1] / 255., PAPER[2] / 255., 1.)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        window.projection = pyglet.math.Mat4.orthogonal_projection(
            0, self.units_wide, self.units_high, 0, -1, 1)
        batch.draw()
        self.framebuffer.unbind()

        window.projection = saved
        gl.glClearColor(*was_clear)
        gl.glViewport(0, 0, window.width, window.height)
        del held

    def delete(self) -> None:
        try:
            self.framebuffer.delete()
            self.texture.delete()
        except Exception:
            pass


class Ribbon:
    """Triangles accumulated for one card, uploaded in a single list.

    A shape object per triangle is the readable way to do this, and it
    was too slow to use: an ellipse alone flattens to seventy-odd
    triangles, and a two-layer grid runs to thousands, each of which
    would carry its own vertex list. Painting a trial's nine cards that
    way took about ninety milliseconds — five dropped frames, every
    time a puzzle appeared. Gathering the vertices and handing them
    over once takes a couple.
    """

    def __init__(self) -> None:
        self.points: List[float] = []
        self.colors: List[float] = []

    def add(self, corners: Sequence[Tuple[float, float]],
            color: Tuple[int, int, int, int]) -> None:
        """One triangle, as three ``(x, y)`` pairs."""
        for x, y in corners:
            self.points.extend((x, y))
        self.colors.extend([channel / 255. for channel in color] * 3)

    def upload(self, batch: pyglet.graphics.Batch,
               group: Optional[pyglet.graphics.Group] = None):
        """Hand the triangles to the batch; returns the vertex list."""
        count = len(self.points) // 2
        if not count:
            return None
        program = pyglet.shapes.get_default_shader()
        return program.vertex_list(
            count, gl.GL_TRIANGLES, batch=batch, group=group,
            position=('f', self.points), colors=('f', self.colors),
            translation=('f', (0.0, 0.0) * count))


def _thick_line(ribbon: Ribbon, start: Tuple[float, float],
                end: Tuple[float, float], thickness: float,
                color: Tuple[int, int, int, int]) -> None:
    """A line segment as two triangles, plus a square cap at each end.

    The caps are what keep a corner from opening up: without them a
    turn in an outline shows daylight on the outside of the bend, and
    every shape here is nothing but corners.
    """
    (start_x, start_y), (end_x, end_y) = start, end
    run, rise = end_x - start_x, end_y - start_y
    length = math.hypot(run, rise)
    if length < 1e-9:
        return
    half = thickness / 2.0
    offset_x, offset_y = -rise / length * half, run / length * half
    one = (start_x + offset_x, start_y + offset_y)
    two = (end_x + offset_x, end_y + offset_y)
    three = (end_x - offset_x, end_y - offset_y)
    four = (start_x - offset_x, start_y - offset_y)
    ribbon.add((one, two, three), color)
    ribbon.add((one, three, four), color)
    for corner_x, corner_y in (start, end):
        ribbon.add(((corner_x - half, corner_y - half),
                    (corner_x + half, corner_y - half),
                    (corner_x + half, corner_y + half)), color)
        ribbon.add(((corner_x - half, corner_y - half),
                    (corner_x + half, corner_y + half),
                    (corner_x - half, corner_y + half)), color)


def draw_outline(ribbon: Ribbon, points: Sequence[Tuple[float, float]],
                 thickness: float,
                 color: Tuple[int, int, int, int]) -> None:
    """Stroke a closed outline."""
    for index in range(len(points)):
        _thick_line(ribbon, points[index], points[(index + 1) % len(points)],
                    thickness, color)


def draw_panel(ribbon: Ribbon, figures: Sequence[Figure],
               left: float, top: float, size: float) -> None:
    """Draw one panel's figures, in card units.

    The engine places figures in a unit square, so the only work here
    is moving that square to where the panel is.

    Every fill goes down before any outline, so that a figure drawn
    over another cannot paint out the line around it — which is what
    an inside-and-outside layout depends on.
    """
    stroke = max(0.5, STROKE_SHARE * size)
    placed = []
    for figure in figures:
        outline = [(left + point.x * size, top + point.y * size)
                   for point in figure.outline()]
        placed.append(outline)
        if figure.fill.color[3]:
            for one, two, three in triangulate(list(figure.outline())):
                ribbon.add(((left + one.x * size, top + one.y * size),
                            (left + two.x * size, top + two.y * size),
                            (left + three.x * size, top + three.y * size)),
                           figure.fill.color)
    for outline in placed:
        draw_outline(ribbon, outline, stroke, INK)


def _border(ribbon: Ribbon, left: float, top: float, width: float,
            height: float, color: Tuple[int, int, int, int],
            thickness: float) -> None:
    draw_outline(ribbon, ((left, top), (left + width, top),
                          (left + width, top + height),
                          (left, top + height)), thickness, color)


class MatrixReasoning:
    """Show a matrix and its candidates, take one, say if it was right."""

    instance: Optional['MatrixReasoning'] = None

    def __init__(self) -> None:
        if MatrixReasoning.instance is not None:
            MatrixReasoning.instance.close()
        self.rng = random.Random()
        self.puzzle = None
        self.level = 0
        #: The level of the puzzle on screen. Kept apart from
        #: :attr:`level`, which has already moved on by the time an
        #: answer is being shown: reporting the next puzzle's level
        #: beside this one's result would say a wrong answer had been
        #: given at a level it was not.
        self.trial_level = 0
        self.trial = 0
        self.correct = 0
        self.asked_at = 0.0
        self.feedback_until = 0.0
        self.picked: Optional[int] = None
        self.hovered: Optional[int] = None
        self.results: List[Tuple[bool, float, int]] = []
        self.phase = 'ready'
        self.matrix_card: Optional[Card] = None
        self.choice_cards: List[Card] = []
        self.sprites: List[pyglet.sprite.Sprite] = []
        self.drawn: List[object] = []
        self.numbers: List[pyglet.text.Label] = []
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_mouse_motion, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        MatrixReasoning.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.MATRIX_REASONING)
        self.start_level = int(opts['RAVENS_LEVEL'])
        self.total_trials = int(opts['RAVENS_TRIALS'])
        self.exposure_ms = int(opts['RAVENS_EXPOSURE_MS'])
        self.adaptive = bool(opts['RAVENS_ADAPTIVE'])
        self.feedback = bool(opts['RAVENS_FEEDBACK'])
        self.explain = bool(opts['RAVENS_EXPLAIN'])
        self.palettes = PALETTES if bool(opts['RAVENS_COLOR']) else (GREYS,)
        self.level = self.clamped(self.start_level - 1)

    def clamped(self, level: int) -> int:
        return max(0, min(len(GRADES) - 1, level))

    def open_options(self) -> None:
        taskoptions.open_task_options('matrix_reasoning',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        """Create the batch, the labels and the cards, at this size."""
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.accent = (64, 96, 255, 255)
        self.rightcolor = (46, 160, 67, 255)
        self.wrongcolor = (200, 64, 64, 255)
        self.batch = pyglet.graphics.Batch()
        self.card_group = pyglet.graphics.Group(order=0)
        self.mark_group = pyglet.graphics.Group(order=1)
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Matrix Reasoning'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     1-8 or click'
              '     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Anchored at its bottom, above the key line, so that a puzzle
        # carrying five rules grows upward into the empty page rather
        # than downward through the keys.
        self.notes = pyglet.text.Label(
            '', font_size=calc_fontsize(10), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(42),
            anchor_x='center', anchor_y='bottom', font_name=FONTLIST,
            multiline=True, width=state.window.width * 0.94, align='center')
        self._build_cards()
        self._redraw()

    def _choice_count(self) -> int:
        """How many answers the puzzle on screen offers.

        Between puzzles it is the count the current level would offer,
        so the chrome is laid out for the puzzle about to appear.
        """
        if self.puzzle is not None:
            return len(self.puzzle.choices)
        return GRADES[self.level].choices

    def _across(self) -> int:
        """How many panels the grid is on a side, likewise."""
        if self.puzzle is not None:
            return self.puzzle.across
        return GRADES[self.level].across

    def _choice_rows(self) -> int:
        count = self._choice_count()
        return (count + CHOICE_COLUMNS - 1) // CHOICE_COLUMNS

    def _canvas(self) -> Tuple[float, float, float, float]:
        """Where the puzzle lives: left, bottom, width, height in pixels."""
        window = state.window
        top = from_top_edge(96)
        # A puzzle with five rules needs several lines to say so. The
        # room is taken out of the puzzle rather than written over it.
        bottom = from_bottom_edge(112 if self.explain else 76)
        return (window.width * 0.04, bottom,
                window.width * 0.92, max(40.0, top - bottom))

    def _geometry(self) -> Tuple[float, float, float, float, float]:
        """Matrix square and choice block: sizes and origins in pixels.

        The two are sized together rather than each to its own share of
        the room, so that a candidate is drawn at exactly the size the
        cell it would fill is drawn at. Judging whether a shape is the
        right size is one of the things a matrix asks, and it cannot be
        asked if the candidates are a different scale from the grid.
        """
        left, bottom, width, height = self._canvas()
        gap = width * 0.04
        across = self._across()
        # The matrix is `across` cells wide and the choices two more.
        # Both share one cell size, so that a candidate is drawn at
        # exactly the size the cell it would fill is drawn at.
        by_width = (width - gap) / float(across + CHOICE_COLUMNS)
        by_height = min(height / float(across), height / self._choice_rows())
        cell = min(by_width, by_height)
        matrix_side = cell * across
        choices_wide = cell * CHOICE_COLUMNS
        used = matrix_side + gap + choices_wide
        origin = left + (width - used) / 2
        top = bottom + height
        return cell, origin, top, matrix_side, choices_wide

    def _matrix_rect(self) -> Tuple[float, float, float, float]:
        """The grid, centred against the block of candidates.

        Whichever of the two is shorter is centred against the taller;
        with four candidates the block is shorter than the grid, and
        centring the grid against it the other way pushed the grid up
        out of the canvas and through the title."""
        cell, origin, top, side, _wide = self._geometry()
        block = cell * self._choice_rows()
        tall = max(side, block)
        return origin, top - (tall + side) / 2, side, side

    def _choice_rects(self) -> List[Tuple[float, float, float, float]]:
        """Each candidate's box: left, bottom, width, height in pixels."""
        cell, origin, top, side, wide = self._geometry()
        left = origin + side + self._canvas()[2] * 0.04
        rects = []
        block = cell * self._choice_rows()
        first_top = top - max(0.0, (side - block) / 2)
        for index in range(self._choice_count()):
            row = index // CHOICE_COLUMNS
            column = index % CHOICE_COLUMNS
            rects.append((left + column * cell, first_top - (row + 1) * cell,
                          cell, cell))
        return rects

    def _build_cards(self) -> None:
        """Make the textures at the size the window can show them."""
        self._delete_cards()
        _left, _bottom, width, _height = self._matrix_rect()
        across = self._across()
        units = CELL_UNITS * across + GAP_UNITS * (across + 1)
        self.matrix_card = Card(units, units, int(width))
        choice = self._choice_rects()[0]
        cell_units = CELL_UNITS + GAP_UNITS * 2
        self.choice_cards = [Card(cell_units, cell_units, int(choice[2]))
                             for _ in range(self._choice_count())]

    def _delete_cards(self) -> None:
        if self.matrix_card is not None:
            self.matrix_card.delete()
        self.matrix_card = None
        for card in self.choice_cards:
            card.delete()
        self.choice_cards = []

    def relayout(self) -> None:
        """Rebuild at the window's new size, keeping the same puzzle."""
        self._build_chrome()
        if self.puzzle is not None:
            self._paint_cards()
            self._redraw()

    # --- painting the cards ----------------------------------------------

    def _paint_cards(self) -> None:
        """Render the current puzzle into its textures."""
        puzzle = self.puzzle
        if puzzle is None or self.matrix_card is None:
            return

        def paint_matrix(batch: pyglet.graphics.Batch) -> List:
            ribbon = Ribbon()
            across = len(puzzle.panels)
            for row in range(across):
                for column in range(across):
                    left = GAP_UNITS + column * (CELL_UNITS + GAP_UNITS)
                    top = GAP_UNITS + row * (CELL_UNITS + GAP_UNITS)
                    last = row == across - 1 and column == across - 1
                    _border(ribbon, left, top, CELL_UNITS, CELL_UNITS,
                            EMPTY_LINE if last else RULE_LINE,
                            RULE_SHARE * CELL_UNITS * (2.0 if last else 1.0))
                    if not last:
                        draw_panel(ribbon, puzzle.panels[row][column],
                                   left, top, CELL_UNITS)
            return [ribbon.upload(batch)]

        self.matrix_card.render(paint_matrix)

        for index, card in enumerate(self.choice_cards):
            shapes = (puzzle.choices[index] if index < len(puzzle.choices)
                      else [])

            def paint_choice(batch: pyglet.graphics.Batch,
                             shapes=shapes) -> List:
                ribbon = Ribbon()
                _border(ribbon, GAP_UNITS, GAP_UNITS, CELL_UNITS, CELL_UNITS,
                        RULE_LINE, RULE_SHARE * CELL_UNITS)
                draw_panel(ribbon, shapes, GAP_UNITS, GAP_UNITS, CELL_UNITS)
                return [ribbon.upload(batch)]

            card.render(paint_choice)

    # --- a trial ---------------------------------------------------------

    def _reset(self) -> None:
        self.puzzle = None
        self.trial = 0
        self.correct = 0
        self.picked = None
        self.results = []
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self.level = self.clamped(self.start_level - 1)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.trial_level = self.level
        self.puzzle = generate(level=self.level + 1,
                               seed=self.rng.randrange(1 << 30),
                               palettes=self.palettes)
        expected = (CELL_UNITS * self.puzzle.across
                    + GAP_UNITS * (self.puzzle.across + 1))
        if (len(self.choice_cards) != len(self.puzzle.choices)
                or (self.matrix_card is not None
                    and self.matrix_card.units_wide != expected)):
            # An adaptive run has crossed between grades that differ
            # in how many answers they offer or how big the grid is,
            # and the cards' sizes depend on both. Everything is made
            # afresh, batch included: deleting a texture quietly
            # changes its sprite group's hash, and a batch holding a
            # group whose hash has shifted under it cannot draw.
            self._build_chrome()
        self.picked = None
        self.asked_at = time.time()
        self.phase = 'asking'
        self.message = _('Which one finishes the pattern?')
        self._paint_cards()
        self._redraw()

    def answer(self, choice: int) -> None:
        """Take the candidate at *choice* and score it."""
        if self.phase != 'asking' or self.puzzle is None:
            return
        if not 0 <= choice < len(self.puzzle.choices):
            return
        right = choice == self.puzzle.answer
        self.picked = choice
        self.results.append((right, time.time() - self.asked_at,
                             self.trial_level))
        if right:
            self.correct += 1
        self._adapt(right)
        if self.feedback:
            self.phase = 'feedback'
            self.feedback_until = time.time() + (1.6 if self.explain else 0.9)
            self.message = (_('Right') if right
                            else _('No — %d was the answer')
                            % (self.puzzle.answer + 1))
            self._redraw()
        else:
            self._next_trial()

    def _adapt(self, right: bool) -> None:
        if not self.adaptive:
            return
        self.level = self.clamped(self.level + (1 if right else -1))

    def _finish(self) -> None:
        self.phase = 'done'
        self.puzzle = None
        tally = self.score()
        self.message = _('%d%% — %d of %d, %.1fs each, hardest level %d'
                         ) % (tally['accuracy'], tally['correct'],
                              tally['trials'], tally['mean_seconds'],
                              tally['best_level'])
        self._redraw()

    def score(self) -> Dict[str, float]:
        """How the run went.

        The hardest level reached is reported beside the percentage,
        because on an adaptive run the two mean different things: the
        percentage hovers near the point the player is being held at,
        so on its own it says nothing about how hard that point was.
        """
        trials = len(self.results)
        times = [took for _right, took, _level in self.results]
        return {
            'trials': trials,
            'correct': self.correct,
            'accuracy': int(round(100. * self.correct / trials)) if trials
                        else 0,
            'mean_seconds': (sum(times) / len(times)) if times else 0.0,
            'best_level': (max(level for _r, _t, level in self.results) + 1
                           if self.results else 0),
        }

    def update(self, dt: float) -> None:
        now = time.time()
        if self.phase == 'feedback' and now >= self.feedback_until:
            self._next_trial()
        elif (self.phase == 'asking' and self.exposure_ms > 0
                and now - self.asked_at >= self.exposure_ms / 1000.):
            self.phase = 'hidden'
            self._redraw()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []
        for sprite in self.sprites:
            sprite.delete()
        self.sprites = []
        for label in self.numbers:
            label.delete()
        self.numbers = []

    def _place(self, card: Card, left: float, bottom: float,
               width: float) -> None:
        sprite = pyglet.sprite.Sprite(card.texture, x=left, y=bottom,
                                      batch=self.batch, group=self.card_group)
        sprite.scale = width / float(card.texture.width)
        self.sprites.append(sprite)

    def _redraw(self) -> None:
        self._clear_drawn()
        showing = self.phase in ('asking', 'feedback') and self.puzzle
        if showing:
            left, bottom, width, _height = self._matrix_rect()
            self._place(self.matrix_card, left, bottom, width)
            for index, rect in enumerate(self._choice_rects()):
                if index >= len(self.choice_cards):
                    break
                self._place(self.choice_cards[index], rect[0], rect[1],
                            rect[2])
                self._mark(index, rect)
        self._update_labels()

    def _mark(self, index: int, rect: Tuple[float, float, float, float]
              ) -> None:
        """Number each candidate, and outline the one under the mouse."""
        left, bottom, width, height = rect
        color = self.textcolor
        thickness = 1.0
        if self.phase == 'feedback' and self.picked is not None:
            if index == self.puzzle.answer:
                color, thickness = self.rightcolor, 3.0
            elif index == self.picked:
                color, thickness = self.wrongcolor, 3.0
        elif index == self.hovered:
            color, thickness = self.accent, 2.5
        if thickness > 1.0:
            self.drawn.append(pyglet.shapes.Box(
                left, bottom, width, height, thickness=thickness,
                color=color, batch=self.batch, group=self.mark_group))
        # Inside the box, not under it: a number below a box sits
        # just as close to the box beneath, and picking by number is
        # the whole of how the task is answered.
        inset = width * 0.09
        self.numbers.append(pyglet.text.Label(
            str(index + 1), font_size=calc_fontsize(11),
            color=(110, 110, 110, 255), batch=self.batch,
            group=self.mark_group,
            x=left + inset, y=bottom + height - inset,
            anchor_x='center', anchor_y='center', font_name=FONTLIST))

    def _update_labels(self) -> None:
        parts = [self.message]
        if self.phase in ('asking', 'hidden', 'feedback'):
            parts.append(_('%d of %d   right %d   level %d')
                         % (self.trial, self.total_trials, self.correct,
                            self.trial_level + 1))
        self.status.text = '     '.join(parts)
        if self.explain and self.puzzle is not None \
                and self.phase == 'feedback':
            self.notes.text = '   ·   '.join(self.puzzle.explanation)
        else:
            self.notes.text = ''

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if MatrixReasoning.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_mouse_motion, self.on_draw)
        self._clear_drawn()
        self._delete_cards()
        MatrixReasoning.instance = None

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
        elif key._1 <= symbol <= key._8:
            self.answer(symbol - key._1)
        elif key.NUM_1 <= symbol <= key.NUM_8:
            self.answer(symbol - key.NUM_1)
        return pyglet.event.EVENT_HANDLED

    def _at(self, x: int, y: int) -> Optional[int]:
        for index, (left, bottom, width, height) in \
                enumerate(self._choice_rects()):
            if left <= x <= left + width and bottom <= y <= bottom + height:
                return index
        return None

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        found = self._at(x, y)
        if found is not None:
            self.answer(found)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> bool:
        found = self._at(x, y) if self.phase == 'asking' else None
        if found != self.hovered:
            self.hovered = found
            self._redraw()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
