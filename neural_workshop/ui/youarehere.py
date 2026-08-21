# -*- coding: utf-8 -*-
"""The You Are Here screen: a view you walk, and a map that never moves.

The thinking lives in :mod:`neural_workshop.youarehere`; this module
is the corridor drawn on screen, the map pinned beside it, and the
keys that walk the one against the other. Three decisions matter here,
and the first is the whole task:

* **The map is built once a maze and never touched again.** It is not
  redrawn when the player moves, or turns, or picks something up, and
  there is no marker on it saying where the player is. That is not an
  omission — it is the task, and it is enforced structurally rather
  than by good intentions: the map has its own batch, filled by
  :meth:`YouAreHere._build_map` when a maze is dealt, and nothing in
  the movement path can reach it. :mod:`tests.test_youarehere` checks
  it the only way worth checking, by digesting the pixels under the
  map panel before and after a walk.

* The view is drawn from the ray casting and nothing else. No
  compass, no coordinates, no trail on the floor, no little arrow.
  What the player knows about where it is stands or falls on what it
  has been keeping in its own head since the maze opened.

* Walls, floor and ceiling each keep to their own band of grey, and
  a wall fades only as far as the far-wall shade. Fading everything
  towards the background is what this did first and it did not work:
  past a few cells the wall, the floor and the ceiling all arrived at
  the same pale grey and the end of a corridor became impossible to
  make out. Both bands are given twice over, once for a light
  background and once for a dark one, because a scheme that fades
  towards black is illegible on black.

The palette is imported from the 2D Maze screen rather than restated,
because the two share a generator and a ladder and the map here ought
to look exactly like the map there — a player who has walked one
should recognise the other at a glance.

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
from ..maze import GRADES, Maze
from ..youarehere import (AHEAD, BACK, COLUMNS, FAR, LEFT, RIGHT, Pose,
                          Sight, costs, deal, facing_at, move, par,
                          picked_up)
from . import cursor, taskoptions
from .maze import KEY_COLORS, WALKER, WALL
from .verdict import VerdictLabel
from ..i18n import _

#: How much of the width the corridor gets, and how much the map. The
#: map needs enough room for a thirty-seven cell grid to stay
#: countable, and the view needs enough to tell a junction from a
#: doorway; a third and a bit under two thirds does both.
VIEW_SHARE = 0.63
MAP_SHARE = 0.33

#: How near a wall has to be to be drawn at full strength, in cells.
NEAR = 3.0

#: The four greys the corridor is made of: ceiling, floor, a wall up
#: close, and a wall as far off as it ever gets, for a light
#: background and then for a dark one.
#:
#: They are set out flat rather than derived by fading everything
#: towards the background, which is what this did first and what did
#: not work: at any distance worth having, the wall, the floor and the
#: ceiling all arrived at the same pale grey and the end of a corridor
#: became impossible to see. Walls now stay inside their own band and
#: the band stays clear of the other two, so a wall reads as a wall at
#: any distance and the depth cue is what is left over.
LIGHT_ROOM = ((238, 238, 238), (212, 212, 212), (80, 80, 80),
              (170, 170, 170))
DARK_ROOM = ((18, 18, 18), (46, 46, 46), (200, 200, 200), (88, 88, 88))

#: A wall face square on to the player is drawn at full strength and
#: one seen edge-on at this much of it, which is what makes a corner
#: read as a corner rather than as one continuous surface.
EDGE_ON = 0.68

#: How close to par a walk must be for an adaptive run to climb. Looser
#: than the 2D maze's quarter, because a corridor wrongly taken here
#: costs the walk back as well, and the rung should reward getting the
#: route right rather than never once hesitating.
CLIMB_AT = 1.4


class YouAreHere:
    """Walk the maze from inside it. Esc returns to the hub."""

    instance: Optional['YouAreHere'] = None

    def __init__(self) -> None:
        if YouAreHere.instance is not None:
            YouAreHere.instance.close()
        self.rng = random.Random()
        #: Swapped out by the agent environment for a virtual clock.
        self.clock = time.time
        self.maze: Optional[Maze] = None
        self.pose = Pose(0, 0)
        self.held = 0
        self.steps = 0
        self.par = 0
        self.bumps = 0
        self.trial = 0
        self.results: List[Tuple[int, int, int]] = []   # (rung, steps, par)
        self.started_at = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        #: Coach mode: paint a per-move consequence verdict (warmer/colder
        #: by Manhattan distance to the way out).  Off for people -- it
        #: changes the game -- and switched on by the agent boundary, where
        #: it is potential-based reward shaping: a move to an adjacent cell
        #: shifts the distance by exactly 1, so green(+1)/red(-1) *is* the
        #: shaping term d - d', and any closed loop of moves sums to zero.
        self.coach = False
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self.map_drawn: List[object] = []
        self.strips: List[object] = []
        self.ceiling = None
        self.floor = None
        self.map_batch = pyglet.graphics.Batch()
        self.view_batch = pyglet.graphics.Batch()
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        YouAreHere.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.YOU_ARE_HERE)
        self.start_rung = int(opts['HERE_LEVEL'])
        self.total_trials = int(opts['HERE_TRIALS'])
        self.adaptive = bool(opts['HERE_ADAPTIVE'])
        self.show_marks = bool(opts['HERE_MARKS'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('you_are_here',
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
            _('You Are Here'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu   Space: start   Arrows: walk and turn'
              '   R: restart   C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Sits above the footnote, and inside the band the agent
        # boundary reads: a task that paints this needs no deriver and no
        # verifier of its own. Measured across every rung, nothing else
        # this task draws puts a saturated colour down there.
        #
        # relayout() rebuilds this whole batch, so a verdict already on
        # screen has to be put back or it disappears on the next window
        # change -- and on_draw calls ensure_laid_out() before it draws,
        # so the very first frame after solving is exactly when that
        # happens. An outcome that is only sometimes derivable is worse
        # than one that never is, because it looks like it works.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        self._build_map()
        self._build_view()
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _stage(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(96)
        bottom = from_bottom_edge(66)
        return (window.width * 0.03, bottom, window.width * 0.94,
                max(60.0, top - bottom))

    def _view_rect(self) -> Tuple[float, float, float, float]:
        left, bottom, width, height = self._stage()
        return (left, bottom, width * VIEW_SHARE, height)

    def _map_rect(self) -> Tuple[float, float, float, float]:
        left, bottom, width, height = self._stage()
        return (left + width * (1.0 - MAP_SHARE), bottom,
                width * MAP_SHARE, height)

    def _cell_rect(self, cell: int) -> Tuple[float, float, float]:
        """Where one maze cell sits on the map panel."""
        left, bottom, width, height = self._map_rect()
        maze = self.maze
        side = min(width / maze.width, height / maze.height)
        x, y = cell % maze.width, cell // maze.width
        offset_x = left + (width - side * maze.width) / 2.0
        offset_y = bottom + (height - side * maze.height) / 2.0
        return (offset_x + x * side,
                offset_y + (maze.height - 1 - y) * side, side)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.maze = None
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
        self.verdict_shown = None
        self.verdict.clear()
        self.maze = deal(self.rung, seed=self.rng.randrange(1 << 30))
        self.par = par(self.maze)
        self._restart_walk()
        self.started_at = self.clock()
        self.phase = 'walking'
        grade = GRADES[self.rung - 1]
        doors = len(self.maze.doors)
        if doors:
            self.message = _('%s — %d doors, %d steps at best') % (
                _(grade.name), doors, self.par)
        else:
            self.message = _('%s — %d steps at best') % (
                _(grade.name), self.par)
        self._build_map()
        self._redraw()

    def _restart_walk(self) -> None:
        self.pose = Pose(self.maze.start, facing_at(self.maze))
        self.held = picked_up(self.maze, self.maze.start, 0)
        self.steps = 0
        self.bumps = 0

    def restart(self) -> None:
        """Back to the start, with the count. The map does not move."""
        if self.phase != 'walking':
            return
        self._restart_walk()
        self.message = _('Back to the start, facing the way you began')
        self._redraw()

    # --- walking ---------------------------------------------------------

    def walk(self, doing: str) -> None:
        """One action: turn, or try to walk."""
        if self.phase != 'walking':
            return
        before = self._distance_out()
        went, got, moved = move(self.maze, self.pose, self.held, doing)
        if not moved and doing in (AHEAD, BACK):
            self.bumps += 1
            blocked = self._blocked(doing)
            self.message = (_('Locked — that door needs its key')
                            if blocked is not None else _('A wall'))
            self._coach_verdict(None)
            self._update_status()
            return
        self.pose, self.held = went, got
        self.steps += costs(doing, moved)
        if self.pose.cell == self.maze.way_out:
            self._solved()
        else:
            self._coach_verdict(self._distance_out() - before
                                if moved else None)
        self._redraw()

    def _blocked(self, doing: str) -> Optional[int]:
        """The door colour in the way, or None when it is a plain wall."""
        from ..youarehere import ahead_of, locked
        facing = (self.pose.facing if doing == AHEAD
                  else (self.pose.facing + 2) % 4)
        step = ahead_of(self.maze, self.pose.cell, facing)
        return None if step is None else locked(self.maze, step, self.held)

    def _distance_out(self) -> int:
        """Manhattan distance from here to the way out, in cells."""
        w = self.maze.width
        hx, hy = self.pose.cell % w, self.pose.cell // w
        tx, ty = self.maze.way_out % w, self.maze.way_out // w
        return abs(hx - tx) + abs(hy - ty)

    def _coach_verdict(self, delta: Optional[int]) -> None:
        """Paint what the move just taken did to the distance out.

        Still a verdict, not a directive: it reports the consequence of the
        action already committed, never which action to take next.  ``None``
        (a turn, or a bump) clears the label -- turning is free of
        consequence and must read as scalar zero, or the shaping stops
        telescoping.
        """
        if not self.coach:
            return
        if delta is None:
            self.verdict_shown = None
            self.verdict.clear()
            return
        closer = delta < 0
        self.verdict_shown = (closer,
                              _('Warmer') if closer else _('Colder'))
        self.verdict.show(*self.verdict_shown)

    def _solved(self) -> None:
        self.results.append((self.rung, self.steps, self.par))
        took = int(self.clock() - self.started_at)
        if self.steps <= self.par:
            self.message = _('Out — the minimum %d steps, %ds') % (
                self.par, took)
        else:
            self.message = _('Out in %d steps — the minimum was %d') % (
                self.steps, self.par)
        if self.adaptive:
            if self.steps <= self.par * CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif self.steps > self.par * 2:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'solved'
        # Only now: the way out is reached, the action window is shut, and
        # nothing the learner does next can change what this says.  Coach
        # mode paints earlier, but only ever about the move already taken --
        # a running verdict of the past, not an answer key for the future.
        self.verdict_shown = (self.steps <= self.par, self.message)
        self.verdict.show(*self.verdict_shown)

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d mazes, %d%% step efficiency, highest '
                         'rung %d') % (tally['solved'], tally['efficiency'],
                                       tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        pars = sum(step for _r, _s, step in self.results)
        walked = sum(steps for _r, steps, _p in self.results)
        return {
            'solved': len(self.results),
            'efficiency': int(round(100. * pars / walked)) if walked else 0,
            'best_rung': max((rung for rung, _s, _p in self.results),
                             default=0),
            'perfect': sum(1 for _r, steps, step in self.results
                           if steps <= step),
        }

    # --- the map, drawn once ---------------------------------------------

    def _build_map(self) -> None:
        """Draw the map. Called when a maze is dealt, and never after.

        Everything about where the player *is* is deliberately absent:
        no marker, no facing, no trail, no dimming of what has been
        walked. What is here is the maze, where it began, where it
        lets out, and every door and key in its colour — the same
        picture on the first step and the last.
        """
        for shape in self.map_drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.map_drawn = []
        self.map_batch = pyglet.graphics.Batch()
        if self.maze is None:
            return
        maze = self.maze
        for cell in maze.walls:
            x, y, side = self._cell_rect(cell)
            self.map_drawn.append(pyglet.shapes.Rectangle(
                x, y, side + 0.5, side + 0.5, color=WALL,
                batch=self.map_batch))
        for colour, door in enumerate(maze.doors):
            x, y, side = self._cell_rect(door)
            self.map_drawn.append(pyglet.shapes.Rectangle(
                x, y, side, side, color=KEY_COLORS[colour % len(KEY_COLORS)],
                batch=self.map_batch))
        for colour, spot in enumerate(maze.keys):
            x, y, side = self._cell_rect(spot)
            self.map_drawn.append(pyglet.shapes.Circle(
                x + side / 2, y + side / 2, side * 0.42, color=self.ink,
                batch=self.map_batch))
            self.map_drawn.append(pyglet.shapes.Circle(
                x + side / 2, y + side / 2, side * 0.32,
                color=KEY_COLORS[colour % len(KEY_COLORS)],
                batch=self.map_batch))
        self._mark_start()
        self._mark_way_out()

    def _mark_start(self) -> None:
        """Where the maze began: a filled square in the walker's colour."""
        x, y, side = self._cell_rect(self.maze.start)
        self.map_drawn.append(pyglet.shapes.Rectangle(
            x + side * 0.18, y + side * 0.18, side * 0.64, side * 0.64,
            color=WALKER, batch=self.map_batch))

    def _mark_way_out(self) -> None:
        """The way out: a ring, so it never reads as somebody standing there."""
        x, y, side = self._cell_rect(self.maze.way_out)
        self.map_drawn.append(pyglet.shapes.Circle(
            x + side / 2, y + side / 2, side * 0.48, color=self.ink,
            batch=self.map_batch))
        self.map_drawn.append(pyglet.shapes.Circle(
            x + side / 2, y + side / 2, side * 0.30,
            color=self.background, batch=self.map_batch))

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

    def _lit(self, sight: Sight) -> float:
        strength = NEAR / (NEAR + max(sight.distance, 0.0))
        return strength * (EDGE_ON if sight.side else 1.0)

    def _wall_colour(self, sight: Sight) -> Tuple[int, int, int]:
        """Grey for a wall, and the door's own colour for a doorway.

        A door keeps its colour all the way to the back of the view,
        fading only towards the far-wall grey rather than towards the
        background: a doorway you cannot make out at ten cells is a
        landmark that only works once you no longer need it.
        """
        _ceiling, _floor, near, far = self._room()
        for colour, door in enumerate(self.maze.doors):
            if door == sight.cell:
                near = KEY_COLORS[colour % len(KEY_COLORS)]
                break
        return self._mix(near, far, self._lit(sight))

    def _build_view(self) -> None:
        """Allocate the corridor once: a ceiling, a floor, and the strips.

        The strips are kept and moved rather than thrown away and made
        again every step, which is the one part of this screen where
        that was worth doing. Measured on a 31x31 maze, building the
        hundred and eighty afresh cost 3.9ms an action, against 1.2ms
        to move them and well under a tenth of a millisecond to submit
        the finished batch. The drawing was never the expensive part;
        the allocation was. Everything else on this screen churns a
        dozen shapes an action and is left alone, because at that size
        it does not matter and a pool would only be something else to
        keep in step with the window.
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
        step = width / float(COLUMNS)
        self.strips = [pyglet.shapes.Rectangle(
            left + column * step, middle, step + 0.5, 1.0, color=floor,
            batch=self.view_batch) for column in range(COLUMNS)]
        self._hide_room()

    def _hide_room(self) -> None:
        for shape in [self.ceiling, self.floor] + self.strips:
            if shape is not None:
                shape.visible = False

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.maze is not None and self.phase in ('walking', 'solved'):
            from ..youarehere import look, motes
            sights = look(self.maze, self.pose, columns=COLUMNS)
            self._draw_room(sights)
            if self.show_marks:
                self._draw_motes(motes(self.maze, self.pose, self.held),
                                 sights)
            self._draw_held()
        else:
            self._hide_room()
        self._update_status()

    def _draw_room(self, sights: Tuple[Sight, ...]) -> None:
        """Move the strips to where this step's rays found the walls."""
        _left, bottom, _width, height = self._view_rect()
        middle = bottom + height / 2.0
        self.ceiling.visible = True
        self.floor.visible = True
        for strip, sight in zip(self.strips, sights):
            if sight.distance >= FAR:
                strip.visible = False
                continue
            tall = min(height, height / max(sight.distance, 0.15))
            strip.y = middle - tall / 2.0
            strip.height = tall
            strip.color = self._wall_colour(sight)
            strip.visible = True

    def _draw_motes(self, standing, sights: Tuple[Sight, ...]) -> None:
        """Keys and the way out, hidden behind whatever is in front of them."""
        left, bottom, width, height = self._view_rect()
        middle = bottom + height / 2.0
        for mote in standing:
            column = int(mote.across * len(sights))
            if not 0 <= column < len(sights):
                continue
            if sights[column].distance <= mote.distance:
                continue
            size = min(height * 0.5, height / max(mote.distance, 0.5) * 0.34)
            at_x = left + mote.across * width
            shade = (self.ink if mote.what == 'way out'
                     else KEY_COLORS[mote.which % len(KEY_COLORS)])
            self.drawn.append(pyglet.shapes.Circle(
                at_x, middle, size * 0.55, color=self.ink,
                batch=self.view_batch))
            self.drawn.append(pyglet.shapes.Circle(
                at_x, middle, size * 0.42,
                color=self.background if mote.what == 'way out' else shade,
                batch=self.view_batch))

    def _draw_held(self) -> None:
        """The keys in your pocket. Not the map — what you are carrying."""
        left, bottom, width, _height = self._view_rect()
        if not self.maze.keys:
            return
        pip = max(5.0, width / 44.0)
        for colour in range(len(self.maze.keys)):
            at_x = left + pip * 2.2 * colour + pip
            spot = bottom - pip * 1.9
            self.drawn.append(pyglet.shapes.Circle(
                at_x, spot, pip * 0.62, color=self.ink,
                batch=self.view_batch))
            self.drawn.append(pyglet.shapes.Circle(
                at_x, spot, pip * 0.46,
                color=(KEY_COLORS[colour % len(KEY_COLORS)]
                       if self.held >> colour & 1 else self.background),
                batch=self.view_batch))

    def _update_status(self) -> None:
        parts = [self.message]
        if self.maze is not None and self.phase == 'walking':
            parts.append(_('maze %d/%d   %d steps   %d at best')
                         % (self.trial, self.total_trials, self.steps,
                            self.par))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if YouAreHere.instance is not self:
            return
        self._clear_drawn()
        for shape in self.map_drawn + self.strips + [self.ceiling,
                                                     self.floor]:
            if shape is None:
                continue
            try:
                shape.delete()
            except Exception:
                pass
        self.map_drawn = []
        self.strips = []
        self.ceiling = self.floor = None
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        YouAreHere.instance = None

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
            elif self.phase == 'solved':
                self._next_trial()
        elif symbol in (key.UP, key.W):
            self.walk(AHEAD)
        elif symbol in (key.DOWN, key.S):
            self.walk(BACK)
        elif symbol in (key.LEFT, key.A):
            self.walk(LEFT)
        elif symbol in (key.RIGHT, key.D):
            self.walk(RIGHT)
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
        self.map_batch.draw()
        self.view_batch.draw()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
