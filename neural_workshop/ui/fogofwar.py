# -*- coding: utf-8 -*-
"""The Fog of War screen: arrows walk, and the dark only lifts where you go.

The world lives in :mod:`neural_workshop.fogworld`; this module is it
drawn through a hole in the dark. One decision governs the whole file,
and it is worth stating plainly because it is the reason the screen
looks as bare as it does:

    **The frame is a pure function of where the walker is and what has
    been revealed. Nothing else reaches it.**

No step counter, no coverage read-out, no clock, no bump flash, no
score popping up, nothing that blinks. That is not minimalism for its
own sake. An agent trained on a prediction-based intrinsic reward will
find the cheapest way to make the screen surprising, and if walking
into a wall produces *any* visible event at all, walking into a wall is
cheaper than travelling and it will do that instead — measured
elsewhere at corr(payment, bumping) +0.79 against corr(payment,
coverage) −0.59. So a bump here changes nothing: not a pixel, not a
label, not a colour. It costs a move from the budget and is otherwise
as if it never happened, which makes it strictly worse than any step
that goes somewhere. :mod:`tests.test_env_fog` holds the screen to that
by bumping a wall and comparing frame bytes.

The cost of the rule is that a human player is told very little while
playing. What was covered is reported when a world ends, which is the
one moment saying so cannot teach a walker to stand still and admire
it.

The other half of the design is that the dark is real. A cell outside
the eye's reach is painted flat black whatever is under it, so two
worlds that differ only somewhere far off draw the same bytes until
somebody walks over there.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Set, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..fogworld import World, coverage, generate, visible
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from . import cursor, taskoptions
from ..i18n import _

#: The dark. Painted rather than left as background, so the picture
#: inside the world is the same whichever way round the workshop's
#: black-background setting is turned.
FOG = (0, 0, 0)
#: Floor and wall, once seen. Both well clear of the fog and of each
#: other, and both flat fills: what is counted off these frames is
#: counted by exact byte match, so a gradient here would be a bug.
FLOOR = (176, 176, 176)
WALL = (64, 64, 64)
#: The walker, in the same reddish purple the maze uses for its own.
WALKER = (204, 121, 167)

#: Arrow keys and the four ways, in the order the environment's ports
#: expect them: the port order lives here so both sides read it off one
#: list.
STEPS: Tuple[Tuple[int, int], ...] = ((0, 0), (0, -1), (0, 1), (-1, 0),
                                      (1, 0))


class FogOfWar:
    """Walk the dark and see how much of it you can light. Esc leaves."""

    instance: Optional['FogOfWar'] = None

    def __init__(self, persist_revealed: Optional[bool] = None) -> None:
        if FogOfWar.instance is not None:
            FogOfWar.instance.close()
        self.rng = random.Random()
        #: Swapped out by the agent environment for a virtual clock.
        self.clock = time.time
        self.world: Optional[World] = None
        self.at = 0
        self.revealed: Set[int] = set()
        self.moves = 0
        self.bumps = 0
        self.walked: Set[int] = set()
        self.trial = 0
        self.results: List[Tuple[int, float]] = []    # (moves, coverage)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        if persist_revealed is not None:
            self.persist = bool(persist_revealed)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        FogOfWar.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.FOG_OF_WAR)
        self.radius = int(opts['FOG_RADIUS'])
        self.moves_allowed = int(opts['FOG_MOVES'])
        self.total_trials = int(opts['FOG_WORLDS'])
        self.persist = bool(opts['FOG_PERSIST'])

    def open_options(self) -> None:
        taskoptions.open_task_options('fog_of_war',
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
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Fog of War'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     arrows: walk'
              '     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _canvas(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(100)
        bottom = from_bottom_edge(56)
        return (window.width * 0.06, bottom,
                window.width * 0.88, max(40.0, top - bottom))

    def _cell_rect(self, cell: int) -> Tuple[float, float, float]:
        """Left, bottom and side of one cell's square on screen."""
        left, bottom, width, height = self._canvas()
        side = min(width / self.world.width, height / self.world.height)
        offset_x = left + (width - side * self.world.width) / 2
        offset_y = bottom + (height - side * self.world.height) / 2
        x, y = cell % self.world.width, cell // self.world.width
        return (offset_x + x * side,
                offset_y + (self.world.height - 1 - y) * side, side)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.world = None
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.world = generate(self.rng.randrange(1 << 30))
        self.at = self.world.start
        self.moves = 0
        self.bumps = 0
        self.walked = {self.at}
        self.revealed = set()
        self._look()
        self.phase = 'exploring'
        self.message = _('Find your way about')
        self._redraw()

    def _look(self) -> None:
        """Take in what can be seen from here."""
        seen = visible(self.world, self.at, self.radius)
        if self.persist:
            self.revealed |= seen
        else:
            self.revealed = set(seen)

    def covered(self) -> float:
        """What share of the walkable world has been walked.

        Walked, not seen: with the map turned off there is nothing to
        accumulate on screen, and where the walker has actually been is
        the one measure that means the same thing either way. The
        screen never shows this while a world is being explored.
        """
        if self.world is None:
            return 0.0
        return coverage(self.world, frozenset(self.walked))

    def update(self, dt: float) -> None:
        """Nothing moves on its own. The walk is the whole clock."""
        del dt

    def step(self, dx: int, dy: int) -> bool:
        """One move. Returns whether the walker actually went anywhere.

        A move into a wall or off the edge is a bump: it spends the
        move and changes nothing else, on screen or off. There is no
        flash, no sound, no counter — a bump is the one action in this
        task that is guaranteed to leave the picture exactly as it was.
        """
        if self.phase != 'exploring':
            return False
        world = self.world
        x, y = self.at % world.width, self.at // world.width
        nx, ny = x + dx, y + dy
        moved = False
        if (0 <= nx < world.width and 0 <= ny < world.height
                and world.walkable(ny * world.width + nx)):
            self.at = ny * world.width + nx
            self.walked.add(self.at)
            self._look()
            moved = True
        else:
            self.bumps += 1
        if dx or dy:
            self.moves += 1
        if moved:
            self._redraw()
        if self.moves >= self.moves_allowed:
            self.end_world()
        return moved

    def end_world(self) -> None:
        """Close this world off and report what was walked.

        Public because the agent environment ends a world on its own
        tick budget as well as on the move budget, and reaching into
        a private to do it would hide a real control action.
        """
        share = self.covered()
        self.results.append((self.moves, share))
        self.message = _('%d%% of that world walked, in %d moves') % (
            int(round(share * 100)), self.moves)
        self.phase = 'finished'
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d worlds, %d%% walked on average') % (
            tally['worlds'], tally['coverage'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        shares = [share for _m, share in self.results]
        return {
            'worlds': len(self.results),
            'coverage': int(round(100. * sum(shares) / len(shares)))
            if shares else 0,
            'moves': sum(moves for moves, _s in self.results),
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
        if self.world is not None and self.phase in ('exploring', 'finished'):
            self._draw_world()
        self._update_status()

    def _draw_world(self) -> None:
        """The dark, then the holes in it, then the walker.

        The fog is one rectangle rather than three hundred, which keeps
        a redraw cheap enough to do on every move; what is drawn over it
        is exactly the revealed cells and nothing else, so an unseen
        cell cannot leave a trace even by accident.
        """
        _left, _bottom, width, height = self._canvas()
        side = min(width / self.world.width, height / self.world.height)
        first_x, first_y, _s = self._cell_rect(0)
        self.drawn.append(pyglet.shapes.Rectangle(
            first_x, first_y - side * (self.world.height - 1),
            side * self.world.width, side * self.world.height,
            color=FOG, batch=self.batch))
        for cell in sorted(self.revealed):
            x, y, _s = self._cell_rect(cell)
            self.drawn.append(pyglet.shapes.Rectangle(
                x, y, side + 1, side + 1,
                color=WALL if cell in self.world.walls else FLOOR,
                batch=self.batch))
        x, y, _s = self._cell_rect(self.at)
        self.drawn.append(pyglet.shapes.Rectangle(
            x + side * 0.22, y + side * 0.22, side * 0.56, side * 0.56,
            color=WALKER, batch=self.batch))

    def _update_status(self) -> None:
        """The status line, which must not move while a world is open.

        Only the world's number is shown while exploring, and it can
        only change between worlds. Anything that changed on a move
        would be a thing to chase instead of ground to cover.
        """
        parts = [self.message]
        if self.world is not None and self.phase == 'exploring':
            parts = [_('World %d of %d') % (self.trial, self.total_trials)]
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if FogOfWar.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        FogOfWar.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='working_memory')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'finished':
                self._next_trial()
        elif symbol in (key.UP, key.W):
            self.step(0, -1)
        elif symbol in (key.DOWN, key.S):
            self.step(0, 1)
        elif symbol in (key.LEFT, key.A):
            self.step(-1, 0)
        elif symbol in (key.RIGHT, key.D):
            self.step(1, 0)
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
