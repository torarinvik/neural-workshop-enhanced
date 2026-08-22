# -*- coding: utf-8 -*-
"""The 3D Sokoban screen: a warehouse you walk, and a plan that goes stale.

The thinking lives in :mod:`neural_workshop.sokoban3d`; this module is
the corridor drawn on screen, the plan pinned beside it, and the keys
that push the one against the other. Three decisions matter here, and
the first is the whole task:

* **The plan is built once a level and never touched again.** Not when
  the player moves, not when the player turns, and — the part that
  makes this a different task from the 3D Maze next door — *not when a
  box moves*. It shows where every box stood when the level was dealt
  and it goes on showing that for the rest of the level, however many
  of them you have shoved somewhere else. There is no marker saying
  where you are and no marker saying where anything is now. It is
  enforced structurally rather than by good intentions: the plan has
  its own batch, filled by :meth:`Sokoban3D._build_plan` when a level
  is dealt, and nothing in the movement path can reach it.
  :mod:`tests.test_sokoban3d` checks it the only way worth checking, by
  digesting the pixels under the panel before and after a push.

* **A box is drawn as a wall in another colour**, because from inside a
  corridor that is exactly what it is: something solid, at some
  distance, that you cannot see past. The ray caster is not told which
  is which. A box standing on its goal is drawn in the home green, and
  that is the one thing the room gives away for free — worth giving,
  because it is the only feedback in the task that does not require the
  player to have kept count.

* **Undo stays, and stays off the agent boundary.** Sokoban's
  difficulty is irreversibility, and a person exploring a line the way
  a chess player takes moves back in analysis is playing the game
  rather than escaping it. A learner handed the same key would be
  handed a way out of the one thing being measured, so
  :mod:`nwenv.sokoban3d` does not offer it a port. The step count still
  tells the truth about the line that was finally played.

The palettes are imported rather than restated — the room greys from
the 3D Maze, because the two are the same corridor seen the same way,
and the pieces from the 2D Sokoban screen, because a player who has
pushed one should recognise the other at a glance.

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
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..sokoban import GRADES, Level
from .. import sokoban3d as S3
from . import cursor, taskoptions
from .sokoban import BOX, BOX_HOME, GOAL, PLAYER, TRAP, WALL
from .verdict import VerdictLabel, above_the_band
from .youarehere import (DARK_ROOM, EDGE_ON, LIGHT_ROOM, MAP_SHARE, NEAR,
                         VIEW_SHARE)
from ..i18n import _

#: How close to par a run must be for an adaptive run to climb. The
#: flat game's own number: a corridor wrongly taken costs the walk back
#: as well, and the rung should reward getting the line right rather
#: than never once hesitating.
CLIMB_AT = 1.4


class Sokoban3D:
    """Push every box onto a goal, from inside. Esc returns to the hub."""

    instance: Optional['Sokoban3D'] = None

    def __init__(self) -> None:
        if Sokoban3D.instance is not None:
            Sokoban3D.instance.close()
        self.rng = random.Random()
        #: Swapped out by the agent environment for a virtual clock.
        self.clock = time.time
        self.level: Optional[Level] = None
        self.boxes: frozenset = frozenset()
        self.pose = S3.Pose(0, 0)
        self.steps = 0
        self.pushes = 0
        self.bumps = 0
        self.par = 0
        self.certified = False
        self.history: List[Tuple[frozenset, object, int, int]] = []
        self.trial = 0
        self.results: List[Tuple[int, int, int, bool]] = []
        #                 (rung, steps, par, certified)
        self.lost = 0
        self.started_at = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self.plan_drawn: List[object] = []
        self.strips: List[object] = []
        self.ceiling = None
        self.floor = None
        self.plan_batch = pyglet.graphics.Batch()
        self.view_batch = pyglet.graphics.Batch()
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Sokoban3D.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SOKOBAN_3D)
        self.start_rung = int(opts['SOKO3D_LEVEL'])
        self.total_trials = int(opts['SOKO3D_TRIALS'])
        self.adaptive = bool(opts['SOKO3D_ADAPTIVE'])
        self.show_marks = bool(opts['SOKO3D_MARKS'])
        self.show_traps = bool(opts['SOKO3D_TRAPS'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('sokoban_3d',
                                      on_apply=self.apply_options)

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
        self.title = pyglet.text.Label(
            _('3D Sokoban'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Wrapped rather than trimmed. This line has to carry the
        # rung's name, what the par is and whether it is a minimum at
        # all, and on a narrow window one line of that ran off both
        # edges of the screen at once.
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(62),
            width=int(state.window.width * 0.80), multiline=True,
            align='center', anchor_x='center', anchor_y='top',
            font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu   Space: start   Arrows: walk, turn and push'
              '   U: undo   R: restart   C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour. Rebuilt with the chrome, so a verdict already
        # up is put back: on_draw calls ensure_laid_out() before it
        # draws, so the first frame after a level settles is exactly
        # when a relayout would otherwise drop it, and an outcome only
        # sometimes derivable is worse than one that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._build_plan()
        self._build_view()
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _stage(self) -> Tuple[float, float, float, float]:
        """Where the whole screen lives, and it stops above the band.

        A box is Okabe-Ito sky blue, ``(86, 180, 233)``, which is not a
        verdict colour — but drawn against the dark room's near-black
        ceiling its anti-aliased edge runs through ``(69, 140, 180)``,
        and *that* is the outcome reader's pattern for a positive
        verdict exactly. So the stage stops where the workshop's rule
        says art stops, and a corridor a fifth taller is not worth a
        screen that sometimes pays itself a trial it did not win.

        The 3D Maze stops in the same place, and did not always: its
        stage ran sixty-six pixels from the bottom edge and its map
        painted door and key colours down there. That went unnoticed
        for a while because a *sample* could not see it — the map
        letterboxes its grid, so on the tall window the tests and
        ``check_band.py`` run at, a big maze sits clear of the bottom,
        and only a wider window drops its last row onto the panel's
        floor. Which is the argument for enumerating a palette rather
        than drawing some of it: see
        :class:`tests.test_sokoban3d.WhyTheStageStopsAboveTheBand`.
        """
        window = state.window
        top = from_top_edge(96)
        bottom = above_the_band(from_bottom_edge(66))
        return (window.width * 0.03, bottom, window.width * 0.94,
                max(60.0, top - bottom))

    def _view_rect(self) -> Tuple[float, float, float, float]:
        left, bottom, width, height = self._stage()
        return (left, bottom, width * VIEW_SHARE, height)

    def _plan_rect(self) -> Tuple[float, float, float, float]:
        left, bottom, width, height = self._stage()
        return (left + width * (1.0 - MAP_SHARE), bottom,
                width * MAP_SHARE, height)

    def _cell_rect(self, cell: int) -> Tuple[float, float, float]:
        """Where one cell sits on the plan panel."""
        left, bottom, width, height = self._plan_rect()
        level = self.level
        side = min(width / level.width, height / level.height)
        x, y = cell % level.width, cell // level.width
        offset_x = left + (width - side * level.width) / 2.0
        offset_y = bottom + (height - side * level.height) / 2.0
        return (offset_x + x * side,
                offset_y + (level.height - 1 - y) * side, side)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.level = None
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None
        self.lost = 0

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.verdict_shown = None
        self.verdict.clear()
        self.level = S3.deal(self.rung, seed=self.rng.randrange(1 << 30))
        found, bound, _route = S3.solve_bounded(self.level)
        self.certified = found is not None
        self.par = bound if found is None else found
        self._restart_run()
        self.started_at = self.clock()
        self.phase = 'pushing'
        grade = GRADES[self.rung - 1]
        if self.certified:
            self.message = _('%s — minimum %d steps') % (
                _(grade.name), self.par)
        else:
            # Past the search's budget, and honest about it: the
            # frontier proved every remaining line costs at least this.
            self.message = _('%s — provably at least %d steps') % (
                _(grade.name), self.par)
        self._build_plan()
        self._redraw()

    def _restart_run(self) -> None:
        self.boxes = self.level.boxes
        self.pose = S3.Pose(self.level.player, S3.facing_at(self.level))
        self.steps = 0
        self.pushes = 0
        self.bumps = 0
        self.history = []

    def restart(self) -> None:
        """Back to the door, with the count. The plan does not move."""
        if self.phase != 'pushing':
            return
        self._restart_run()
        self.message = _('Back at the door, facing the way you came in')
        self._redraw()

    def undo(self) -> None:
        if self.phase != 'pushing' or not self.history:
            return
        self.boxes, self.pose, self.steps, self.pushes = self.history.pop()
        self._redraw()

    # --- pushing ---------------------------------------------------------

    def walk(self, doing: str) -> None:
        """One action: turn, walk, or push whatever is in the way."""
        if self.phase != 'pushing':
            return
        went, shifted, moved, pushed = S3.move(self.level, self.boxes,
                                               self.pose, doing)
        if not moved and doing in (S3.AHEAD, S3.BACK):
            self.bumps += 1
            self.message = (_('That box will not go that way')
                            if self._box_ahead(doing) else _('A wall'))
            self._update_status()
            return
        self.history.append((self.boxes, self.pose, self.steps, self.pushes))
        self.pose, self.boxes = went, shifted
        self.steps += S3.costs(doing, moved)
        if pushed:
            self.pushes += 1
        if S3.solved(self.level, self.boxes):
            self._solved()
        elif pushed and S3.stuck(self.level, self.boxes):
            self._lost()
        self._redraw()

    def _box_ahead(self, doing: str) -> bool:
        """Whether the thing that stopped the walk was a box."""
        facing = (self.pose.facing if doing == S3.AHEAD
                  else (self.pose.facing + 2) % 4)
        step = S3.step_to(self.level, self.pose.cell, facing)
        return step is not None and step in self.boxes

    def _lost(self) -> None:
        """This warehouse cannot be won any more, so say so.

        :func:`~neural_workshop.sokoban.deadlocked` is sound rather than
        complete: False means "not provably lost" and never "still
        winnable", so this fires late rather than wrongly. It matters
        more here than on the flat screen — from inside a corridor a
        player can be several pushes past the mistake before anything
        looks wrong, and without this the position would be one nothing
        could be paid for and nobody could leave.
        """
        self.lost += 1
        self.message = _('Stuck — that box can never reach a goal now')
        if self.adaptive:
            self.rung = self.clamped(self.rung - 1)
        self.phase = 'lost'
        self.verdict_shown = (False, self.message)
        self.verdict.show(*self.verdict_shown)

    def _solved(self) -> None:
        self.results.append((self.rung, self.steps, self.par,
                             self.certified))
        took = int(self.clock() - self.started_at)
        if self.certified and self.steps <= self.par:
            self.message = _('Done — the minimum %d steps, %ds') % (
                self.par, took)
        elif self.certified:
            self.message = _('Done in %d steps — the minimum was %d') % (
                self.steps, self.par)
        else:
            self.message = _('Done in %d steps — provably at least '
                             '%d') % (self.steps, self.par)
        if self.adaptive:
            if self.steps <= self.par * CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif self.steps > self.par * 2:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'solved'
        self.verdict_shown = (self.steps <= self.par, self.message)
        self.verdict.show(*self.verdict_shown)

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d warehouses, %d%% step efficiency, highest '
                         'rung %d') % (tally['solved'], tally['efficiency'],
                                       tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        pars = sum(par for _r, _s, par, _c in self.results)
        walked = sum(steps for _r, steps, _p, _c in self.results)
        return {
            'solved': len(self.results),
            'efficiency': int(round(100. * pars / walked)) if walked else 0,
            'best_rung': max((rung for rung, _s, _p, _c in self.results),
                             default=0),
            # Kept out of the efficiency, as on the flat screen: a
            # warehouse pushed into a corner has no step count worth
            # averaging.
            'lost': self.lost,
        }

    # --- the plan, drawn once --------------------------------------------

    def _build_plan(self) -> None:
        """Draw the plan. Called when a level is dealt, and never after.

        Everything about where anything *is* is deliberately absent. The
        walls are where the walls are, because walls do not move; the
        goals are where the goals are, for the same reason. The boxes
        are drawn where they stood when the door shut, and the player
        where it came in — and both of those stop being true on the
        first push, which is the task rather than a bug in it.
        """
        for shape in self.plan_drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.plan_drawn = []
        self.plan_batch = pyglet.graphics.Batch()
        if self.level is None:
            return
        level = self.level
        for cell in range(level.width * level.height):
            x, y, side = self._cell_rect(cell)
            if cell in level.walls:
                self.plan_drawn.append(pyglet.shapes.Rectangle(
                    x, y, side + 0.5, side + 0.5, color=WALL,
                    batch=self.plan_batch))
            elif cell in level.goals:
                self.plan_drawn.append(pyglet.shapes.Circle(
                    x + side / 2, y + side / 2, side * 0.16, color=GOAL,
                    batch=self.plan_batch))
            elif self.show_traps and cell in level.traps:
                # The landmines, marked on request: a box pushed onto
                # one of these can never reach a goal again. Training
                # wheels here as on the flat screen, and worth rather
                # more, since from inside a corridor a pocket is not
                # something you can look at.
                self.plan_drawn.append(pyglet.shapes.Line(
                    x + side * 0.34, y + side * 0.34,
                    x + side * 0.66, y + side * 0.66,
                    thickness=1, color=TRAP, batch=self.plan_batch))
                self.plan_drawn.append(pyglet.shapes.Line(
                    x + side * 0.34, y + side * 0.66,
                    x + side * 0.66, y + side * 0.34,
                    thickness=1, color=TRAP, batch=self.plan_batch))
        for box in sorted(level.boxes):
            x, y, side = self._cell_rect(box)
            pad = side * 0.18
            self.plan_drawn.append(pyglet.shapes.Rectangle(
                x + pad, y + pad, side - 2 * pad, side - 2 * pad,
                color=BOX, batch=self.plan_batch))
        x, y, side = self._cell_rect(level.player)
        self.plan_drawn.append(pyglet.shapes.Circle(
            x + side / 2, y + side / 2, side * 0.3, color=PLAYER,
            batch=self.plan_batch))

    # --- the view, drawn every step --------------------------------------

    def _clear_drawn(self) -> None:
        for shape in self.drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.drawn = []

    def _room(self) -> Tuple[Tuple[int, int, int], ...]:
        """Ceiling, floor, near wall and far wall, for this background."""
        return LIGHT_ROOM if self.background[0] else DARK_ROOM

    def _mix(self, near: Tuple[int, int, int], far: Tuple[int, int, int],
             lit: float) -> Tuple[int, int, int]:
        """*near* at ``lit`` of one, *far* at nought, and between between."""
        lit = max(0.0, min(1.0, lit))
        return tuple(int(round(back + (front - back) * lit))
                     for front, back in zip(near, far))

    def _lit(self, sight) -> float:
        strength = NEAR / (NEAR + max(sight.distance, 0.0))
        return strength * (EDGE_ON if sight.side else 1.0)

    def _face_colour(self, sight) -> Tuple[int, int, int]:
        """Grey for rock, and a box's own colour for a box.

        A box keeps its colour all the way to the back of the view,
        fading only towards the far-wall grey rather than towards the
        background: a box you cannot make out at eight cells is a thing
        you will walk into.
        """
        _ceiling, _floor, near, far = self._room()
        if sight.cell in self.boxes:
            near = BOX_HOME if sight.cell in self.level.goals else BOX
        return self._mix(near, far, self._lit(sight))

    def _build_view(self) -> None:
        """Allocate the corridor once: a ceiling, a floor, and the strips.

        Kept and moved rather than thrown away and made again every
        action, for the reason the 3D Maze gives at length: the drawing
        was never the expensive part, the allocation was.
        """
        for shape in [self.ceiling, self.floor] + self.strips:
            if shape is not None:
                try:
                    shape.delete()
                except Exception:
                    pass
        self.view_batch = pyglet.graphics.Batch()
        left, bottom, width, height = self._view_rect()
        middle = bottom + height / 2.0
        ceiling, floor, _near, _far = self._room()
        self.ceiling = pyglet.shapes.Rectangle(
            left, middle, width, height / 2.0, color=ceiling,
            batch=self.view_batch)
        self.floor = pyglet.shapes.Rectangle(
            left, bottom, width, height / 2.0, color=floor,
            batch=self.view_batch)
        step = width / float(S3.COLUMNS)
        self.strips = [pyglet.shapes.Rectangle(
            left + column * step, middle, step + 0.5, 1.0, color=floor,
            batch=self.view_batch) for column in range(S3.COLUMNS)]
        self._hide_room()

    def _hide_room(self) -> None:
        for shape in [self.ceiling, self.floor] + self.strips:
            if shape is not None:
                shape.visible = False

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.level is not None and self.phase in ('pushing', 'solved',
                                                     'lost'):
            sights = S3.look_around(self.level, self.boxes, self.pose)
            self._draw_room(sights)
            if self.show_marks:
                self._draw_marks(S3.marks(self.level, self.boxes,
                                          self.pose), sights)
        else:
            self._hide_room()
        self._update_status()

    def _draw_room(self, sights) -> None:
        """Move the strips to where this action's rays found the solid."""
        _left, bottom, _width, height = self._view_rect()
        middle = bottom + height / 2.0
        self.ceiling.visible = True
        self.floor.visible = True
        for strip, sight in zip(self.strips, sights):
            if sight.distance >= S3.FAR:
                strip.visible = False
                continue
            tall = min(height, height / max(sight.distance, 0.15))
            strip.y = middle - tall / 2.0
            strip.height = tall
            strip.color = self._face_colour(sight)
            strip.visible = True

    def _draw_marks(self, standing, sights) -> None:
        """Goals still wanting a box, hidden behind whatever is in front."""
        left, bottom, width, height = self._view_rect()
        middle = bottom + height / 2.0
        for mote in standing:
            column = int(mote.across * len(sights))
            if not 0 <= column < len(sights):
                continue
            if sights[column].distance <= mote.distance:
                continue
            size = min(height * 0.5, height / max(mote.distance, 0.5) * 0.30)
            at_x = left + mote.across * width
            self.drawn.append(pyglet.shapes.Circle(
                at_x, middle, size * 0.50, color=GOAL,
                batch=self.view_batch))
            self.drawn.append(pyglet.shapes.Circle(
                at_x, middle, size * 0.34, color=self.background,
                batch=self.view_batch))

    def _update_status(self) -> None:
        parts = [self.message]
        if self.level is not None and self.phase == 'pushing':
            # The par is already in the message, so it is not said
            # twice: what belongs here is what the run has spent.
            parts.append(_('warehouse %d/%d   steps %d   pushes %d')
                         % (self.trial, self.total_trials, self.steps,
                            self.pushes))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Sokoban3D.instance is not self:
            return
        self._clear_drawn()
        for shape in self.plan_drawn + self.strips + [self.ceiling,
                                                      self.floor]:
            if shape is None:
                continue
            try:
                shape.delete()
            except Exception:
                pass
        self.plan_drawn = []
        self.strips = []
        self.ceiling = self.floor = None
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        Sokoban3D.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='planning')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase in ('solved', 'lost'):
                self._next_trial()
        elif symbol in (key.UP, key.W):
            self.walk(S3.AHEAD)
        elif symbol in (key.DOWN, key.S):
            self.walk(S3.BACK)
        elif symbol in (key.LEFT, key.A):
            self.walk(S3.LEFT)
        elif symbol in (key.RIGHT, key.D):
            self.walk(S3.RIGHT)
        elif symbol == key.U:
            self.undo()
        elif symbol == key.R:
            self.restart()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.plan_batch.draw()
        self.view_batch.draw()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
