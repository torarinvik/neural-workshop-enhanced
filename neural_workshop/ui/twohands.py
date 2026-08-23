# -*- coding: utf-8 -*-
"""The Two Hands screen: a road drawn from behind the car, and a sky over it.

The thinking lives in :mod:`neural_workshop.twohands`; this module is
the road drawn in perspective, the sky drawn above it, the crosshair
the mouse carries, and the keys that put the two against each other.

Three decisions matter here.

**The road is cast rather than modelled.** One number does all of it:
:func:`Twohands.far`, which turns a distance in drawn rows into how
wide the road is and how high up the screen it sits. Everything else —
the tarmac, the stripes that slide, the lane dividers, every hazard and
the car itself — is that one function called at a different distance.
There is no camera and no matrix, and the reason is the same reason the
3D Maze casts one ray a column: what the task needs from three
dimensions is that *far things are small and arrive late*, and that is
a single division.

**The crosshair is drawn, and it is drawn whoever is moving it.** A
person moves it with the mouse; the agent boundary moves it a notch at
a time through four ports. Both write the same two numbers and the
screen paints the same cross, so what a learner is handed is what a
person sees, and the sights are not a private channel.

**The clock is a bar and not a number.** What a driver has to know at a
glance is whether the pace is being held, which is a comparison between
two fractions — road behind you against time spent — and two bars one
above the other say that in a way that two numbers do not. The bar is
also the only thing on screen that says why a road was lost when it was
lost to the clock rather than to a truck.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from ..twohands import (AIM_DOWN, AIM_LEFT, AIM_RIGHT, AIM_UP, BODY, FASTER,
                        FIRE, GRADES, HOLD, JUMP, KINDS, LANES, LEFT, NUDGE,
                        RIGHT, SLOWER, SUB, Ride, advance, cleared,
                        drawn_lane, generate, late, over, press, rehearse,
                        sighted, start_ride)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Okabe-Ito wherever it stretches, and the assignments are not
#: arbitrary. The car is blue because Donkey's car is blue; the donkey
#: is vermillion because that is what the workshop spends on the thing
#: you must not touch; and the two prizes are the two colours nothing
#: else on the road uses, so a thing worth having never has to be told
#: apart from a thing that will end you by its shape alone.
CAR_COLOUR = (0, 114, 178)
PAINT: Dict[str, Tuple[int, int, int]] = {
    'donkey': (213, 94, 0),         # vermillion
    'truck': (204, 121, 167),       # reddish purple
    'barrier': (230, 159, 0),       # orange
    'log': (90, 62, 40),            # a fallen tree
    'rubble': (130, 130, 130),
    'cone': (240, 228, 66),         # yellow
    'ramp': (86, 180, 233),         # sky blue
    'pad': (0, 158, 115),           # bluish green
    'coin': (0, 158, 115),
}

#: How tall each kind stands, as a share of a lane's near width. The
#: rules read one bit — tall or low — and the screen draws nine things,
#: so the heights have to make that bit legible at a glance: everything
#: a jump clears is drawn flat to the tarmac and everything it does not
#: stands up off it.
HEIGHT: Dict[str, float] = {
    'donkey': 0.80, 'truck': 1.05, 'barrier': 0.62, 'rubble': 0.46,
    'log': 0.14, 'cone': 0.36, 'ramp': 0.20, 'pad': 0.12, 'coin': 0.40,
}

#: The sky's own colours: the target, and the ring left where one was.
TARGET = (240, 228, 66)
DOWNED = (0, 158, 115)

#: The road surface, its markings and the ground beside it, as
#: opacities on the ink. Opacities rather than colours so the screen
#: works on either page — the workshop can be run black on white or
#: white on black, and a road painted in absolute grey is legible on
#: exactly one of them.
ROAD_ALPHA, BAND_ALPHA, MARK_ALPHA, GRASS_ALPHA = 26, 40, 110, 14

#: How many drawn rows of road are visible ahead of the bonnet.
#:
#: Comfortably more than the furthest any commitment reaches — the
#: widest swerve at the highest speed covers three rows — so the press
#: is never aimed at something off the top of the screen. The task is
#: how early you commit, not whether the road told you in time.
SIGHT = 14

#: How fast the road converges. The width at *d* rows ahead is
#: ``DEPTH / (d + DEPTH)`` of the width under the bonnet, so this is
#: the distance at which the road is half as wide as it is here.
DEPTH = 6.0

#: Where the horizon sits in the playfield, as a share of its height.
#: The sky gets the rest of it, and it needs a real share rather than a
#: strip: a crosshair that cannot be told apart from the skyline is a
#: second task about eyesight.
HORIZON = 0.58

#: How long a drawn row takes at one sub-row a tick, and how long the
#: road sits still before it starts moving.
#:
#: A row rather than a tick, because a row is what a person can see
#: going by. The clock inside runs at ``beat_seconds / SUB``, and at
#: speed four the road comes four times as fast as this says — which is
#: the point of the throttle and the reason this default is nearly
#: twice Donkey's.
BEAT_SECONDS = 0.30
SET_SECONDS = 1.2

#: How long a verdict stays up before the next road can be called.
VERDICT_SECONDS = 1.2

#: Clear this share of the last four roads and an adaptive run climbs;
#: fewer than this and it drops.
CLIMB_AT, DROP_BELOW = 0.75, 0.4


class Twohands:
    """A road, a sky, and one tick of attention. Esc returns to the hub."""

    instance: Optional['Twohands'] = None

    def __init__(self) -> None:
        if Twohands.instance is not None:
            Twohands.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        #: Coach mode: paint a verdict on the tick something resolves.
        #: Off for people — it changes the game — and switched on by the
        #: agent boundary. It reads the road and the sky, both drawn.
        self.coach = False
        self.road = None
        self.ride: Optional[Ride] = None
        self.downed: set = set()
        self.shot = 0
        #: A target taken since the last tick, waiting to be paid. The
        #: coach paints on the tick and never on the press -- see
        #: :meth:`_settled_coach` for why it has to.
        self.owed_hit = False
        self.cross_x, self.cross_y = 0.5, 0.5
        self.trial = 0
        self.results: List[Tuple[int, bool]] = []      # (rung, cleared)
        self.points = 0
        self.taken = 0
        self.until = 0.0
        self.beat_at = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_motion,
                                   self.on_mouse_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        Twohands.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.TWO_HANDS)
        self.start_rung = int(opts['TWOHANDS_LEVEL'])
        self.total_trials = int(opts['TWOHANDS_TRIALS'])
        self.beat_seconds = float(opts['TWOHANDS_BEAT_SECONDS'])
        self.set_seconds = float(opts['TWOHANDS_SET_SECONDS'])
        self.adaptive = bool(opts['TWOHANDS_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('two_hands', on_apply=self.apply_options)

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
            _('Two Hands'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch, x=width_center(),
            y=from_top_edge(36), anchor_x='center', anchor_y='center',
            font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.asked = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(94),
            width=int(state.window.width * 0.80), multiline=True,
            align='center', anchor_x='center', anchor_y='top',
            font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   ← → steer   ↑ ↓ gear   Space: start, then '
              'jump   Mouse: aim and fire   C: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the road by this
        # label's colour. Rebuilt with the chrome so a verdict already
        # up is put back: a relayout on the frame a road settles would
        # otherwise drop it, and an outcome only sometimes derivable is
        # worse than one that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        self._update_asked()
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _stage(self) -> Tuple[float, float, float, float]:
        """The playfield: left, bottom, width, height.

        Held clear of the strip the agent boundary reads, for Donkey's
        reason and more of it. The donkey is vermillion, ``(213, 94,
        0)``, which is a negative verdict outright rather than a blend
        that passes for one — and the coin is the workshop's green. A
        road drawn into the band would pay itself a scalar for having
        scenery on it.
        """
        window = state.window
        top = from_top_edge(158)
        bottom = above_the_band(from_bottom_edge(56))
        return (window.width * 0.06, bottom,
                window.width * 0.88, max(80.0, top - bottom))

    def _horizon(self) -> float:
        _left, bottom, _width, height = self._stage()
        return bottom + height * HORIZON

    def _sky_rect(self) -> Tuple[float, float, float, float]:
        """Where the targets fly and the crosshair lives."""
        left, _bottom, width, height = self._stage()
        sky = self._horizon()
        return (left, sky, width, max(20.0, self._stage()[1] + height - sky))

    def _near_half(self) -> float:
        """Half the road's width under the bonnet."""
        _left, _bottom, width, height = self._stage()
        return min(width * 0.34, height * 0.78)

    def far(self, ahead: float) -> Tuple[float, float]:
        """``(screen y, half width)`` for road *ahead* drawn rows away.

        The one piece of perspective in the module. ``ahead`` of zero is
        the bonnet, where the road is at its full width and sits on the
        bottom of the playfield; as it grows the width falls off as
        ``DEPTH / (ahead + DEPTH)`` and the road climbs the same
        fraction of the way to the horizon. Nothing else here knows how
        depth works.
        """
        _left, bottom, _width, _height = self._stage()
        shrink = DEPTH / (max(0.0, ahead) + DEPTH)
        return (bottom + (self._horizon() - bottom) * (1.0 - shrink),
                self._near_half() * shrink)

    def lane_x(self, ahead: float, lane: float) -> float:
        """Where the middle of *lane* is, *ahead* rows away.

        *lane* may be a fraction, which is a car half way through a
        swerve — and it has to be, because for the whole of a swerve
        the car is in both lanes and a car drawn in one of them would
        be the screen telling a lie about the oldest rule in the game.
        """
        left, _bottom, width, _height = self._stage()
        _y, half = self.far(ahead)
        across = (lane + 0.5) / float(LANES)
        return left + width / 2.0 + (across - 0.5) * 2.0 * half

    def _rows_of(self, steps: float) -> float:
        return steps / float(SUB)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.road = None
        self.ride = None
        self.downed = set()
        self.shot = 0
        self.owed_hit = False
        self.cross_x, self.cross_y = 0.5, 0.5
        self.trial = 0
        self.results = []
        self.points = 0
        self.taken = 0
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
        self.road = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self.ride = start_ride(self.road)
        self.downed = set()
        self.shot = 0
        self.owed_hit = False
        self.cross_x, self.cross_y = 0.5, 0.5
        self.phase = 'setting'
        self.until = self.clock() + self.set_seconds
        self.beat_at = self.clock() + self.set_seconds
        self.message = _('Road ahead')
        self._update_asked()
        self._redraw()

    def _update_asked(self) -> None:
        """What the rung is asking, said in two lines above the road.

        Short on purpose. Everything the rung actually does is on the
        options screen, and a paragraph over the road is a paragraph
        the driver reads instead of the road.
        """
        if self.road is None:
            self.asked.text = ''
            return
        road, grade = self.road, self.road.grade
        said = [_('Rung %d, %s: %d rows, %d in the way, %d in the sky, '
                  '%d ticks against a best line of %d.')
                % (self.rung, _(grade.name), road.rows, len(road.hazards),
                   len(road.sky), road.clock, road.par)]
        said.append(_('The swerve takes %d ticks and covers both lanes for '
                      'all of them; a jump clears the flat ones for %d. '
                      'Neither can be called off, and the wheel is deaf '
                      'until they are done — so those ticks are the '
                      'sights’ for nothing.') % (grade.swerve, grade.hang))
        self.asked.text = ' '.join(said)

    # --- what the player does --------------------------------------------

    def act(self, port: int) -> bool:
        """One tick's worth of attention, spent on one thing.

        Six ports go to the wheel and five to the sights, and that is
        the whole task: they come out of one budget. A port spent on
        the crosshair is a port the wheel did not get, and the wheel is
        only listening when the car is settled anyway — so *when* the
        sights are cheap is itself something to work out.

        Nothing here advances the road. The road comes on the clock in
        :meth:`update`, whether or not anybody did anything, because a
        driver who could stop it while he thought would be playing a
        different game.
        """
        if self.phase != 'running' or self.ride is None:
            return False
        if port == FIRE:
            did = self._fire()
        elif port == AIM_LEFT:
            did = self._nudge(-NUDGE, 0.0)
        elif port == AIM_RIGHT:
            did = self._nudge(NUDGE, 0.0)
        elif port == AIM_UP:
            did = self._nudge(0.0, NUDGE)
        elif port == AIM_DOWN:
            did = self._nudge(0.0, -NUDGE)
        else:
            did = self._wheel(port)
        self._redraw()
        return did

    def _wheel(self, port: int) -> bool:
        """Steer, jump or shift. Swallowed whole while a commitment runs."""
        if not self.ride.settled or port == HOLD:
            return False
        was = self.ride
        # The rules own what a port does, not the screen. A press the
        # rung refuses -- a swerve off the edge, a shift past the top
        # gear -- is refused by exactly the code the solver used.
        self.ride = press(was, port, self.road.grade)
        return self.ride != was

    def _nudge(self, dx: float, dy: float) -> bool:
        self.cross_x = min(1.0, max(0.0, self.cross_x + dx))
        self.cross_y = min(1.0, max(0.0, self.cross_y + dy))
        return True

    def _fire(self) -> bool:
        """Pull the trigger at whatever the crosshair is on.

        The hit is *owed* rather than painted. A boundary step is the
        port and then the tick, in that order, and the frame the
        learner is handed is drawn after the tick — so a label put up
        here would be taken down by the tick that follows it and the
        shot would be paid nothing at all. Everything the coach pays is
        painted in one place, on the tick, for exactly this reason.
        """
        found = sighted(self.road, self.ride.at, self.cross_x, self.cross_y,
                        self.downed)
        if found is None:
            return False
        self.downed.add(found)
        self.shot += 1
        self.points += 1
        self.owed_hit = True
        return True

    # --- the clock --------------------------------------------------------

    def tick_seconds(self) -> float:
        """How long one tick takes: a drawn row's worth, cut :data:`SUB` ways.

        The dial is in rows because a row is what a person can watch go
        by. The tick is a quarter of one because that is the rules' own
        unit — and how many of them the road eats a tick is the
        throttle, which is why this is not also the speed.
        """
        return self.beat_seconds / float(SUB)

    def update(self, dt: float) -> None:
        """One tick of road, on the clock rather than on a press.

        The road comes whether or not anybody steers, which is the
        point: a driver who could stop it while he thought would be
        playing a different game, and the game is about having already
        committed rather than about choosing correctly.
        """
        now = self.clock()
        if self.phase == 'setting' and now >= self.until:
            self.phase = 'running'
            self.message = _('Go')
            self._redraw()
        elif self.phase == 'running' and now >= self.beat_at:
            self.beat_at = now + self.tick_seconds()
            was = self.ride
            self.ride = advance(self.ride, self.road)
            self._settled_coach(was, self.ride)
            if over(self.ride, self.road):
                self._settle()
                return
            self._redraw()

    def _settled_coach(self, was: Ride, now: Ride) -> None:
        """Paint what the tick just gone did, if anybody is being coached.

        Not shaping and it should not borrow the word: there is no
        potential here and nothing telescopes. It is the road's own
        haul taken apart, which is what Cookie Thief does — a hazard
        got by is a piece of the green, a coin is another, and a clip
        is the red. Summed over a road it tracks what the road was
        worth, so a learner does not have to reach the far end to be
        told anything.

        It reads the road, the sky and the car, all three of which are
        drawn. There is nothing hidden in this task for it to leak:
        every hazard inside :data:`SIGHT` rows is on the screen and so
        is every target aloft. What the task hides is not information,
        it is whether you had a tick to spare.
        """
        owed, self.owed_hit = self.owed_hit, False
        if now.hit:
            return              # the road's own verdict, painted by _settle
        if now.clipped > was.clipped:
            # A clip outranks anything good in the same tick. One tick
            # pays one label, and the one worth having is the cost.
            self._coach(False, _('Clipped'))
        elif owed:
            self._coach(True, _('Hit'))
        elif now.points > was.points:
            self._coach(True, _('Taken'))
        elif now.passed > was.passed:
            self._coach(True, _('Past one'))
        elif self.coach:
            self.verdict_shown = None
            self.verdict.clear()

    def _coach(self, good: bool, text: str) -> None:
        if not self.coach:
            return
        self.verdict_shown = (good, text)
        self.verdict.show(*self.verdict_shown)

    # --- how it ends ------------------------------------------------------

    def _settle(self) -> None:
        """Score the road: the far end of it, on four wheels, in time."""
        ride, road = self.ride, self.road
        home = cleared(ride, road)
        self.results.append((self.rung, home))
        self.points += ride.points
        self.taken += self.shot
        if home:
            self.message = _('Home in %d of %d ticks, %d past, %d shot'
                             ) % (ride.ticks, road.clock, ride.passed,
                                  self.shot)
        elif late(ride, road):
            self.message = _('Out of time %d rows short — too slow, not too '
                             'careless') % (road.rows - ride.rows_done)
        else:
            self.message = _('Hit one after %d rows, %d past, %d shot'
                             ) % (ride.rows_done, ride.passed, self.shot)
        if self.adaptive:
            share = sum(1 for _r, ok in self.results[-4:] if ok) / float(
                min(4, len(self.results)))
            if share >= CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif share < DROP_BELOW:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'scored'
        self.until = self.clock() + VERDICT_SECONDS
        self.verdict_shown = (home, self.message)
        self.verdict.show(*self.verdict_shown)
        self._update_status()
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.road = None
        self.ride = None
        self.message = _('%d of %d roads driven, %d points, %d out of the '
                         'sky, highest rung %d — the same dodge with the '
                         'sights taken only on spare ticks clears about '
                         '%d%% of these, and taken the moment anything is '
                         'up there about %d%%'
                         ) % (tally['clean'], tally['roads'], tally['points'],
                              tally['shot'], tally['best_rung'],
                              tally['spare'], tally['greedy'])
        self.asked.text = ''
        self._update_status()
        self._redraw()

    def score(self) -> Dict[str, int]:
        """How the run went, and what the shallow policies were worth.

        The two numbers worth reading are the last pair, and they are
        the same driver twice. ``spare`` shoots on the ticks the wheel
        had no use for; ``greedy`` shoots the moment a target is up.
        Measured over sixty deals a rung, the first costs the road
        nothing at all and gets *more* of the sky than the second does.
        Which is the finding: the cost of a second channel is not the
        channel, it is taking it at the wrong moment.
        """
        roads = len(self.results)
        clean = sum(1 for _r, ok in self.results if ok)
        best = max((rung for rung, _ok in self.results), default=0)
        rungs = [rung for rung, _ok in self.results]
        spare = [rehearse(rung, policy='gunner') for rung in rungs]
        greedy = [rehearse(rung, policy='sniper') for rung in rungs]
        return {
            'roads': roads,
            'clean': clean,
            'points': self.points,
            'shot': self.taken,
            'accuracy': int(round(100.0 * clean / roads)) if roads else 0,
            'best_rung': best,
            'spare': int(round(100.0 * sum(spare) / len(spare)))
                     if spare else 0,
            'greedy': int(round(100.0 * sum(greedy) / len(greedy)))
                      if greedy else 0,
        }

    # --- drawing ----------------------------------------------------------

    def _clear_drawn(self) -> None:
        for shape in self.drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.drawn = []

    def _rect(self, x, y, wide, tall, colour, opacity=255):
        shape = pyglet.shapes.Rectangle(x, y, max(1.0, wide), max(1.0, tall),
                                        color=colour, batch=self.batch)
        shape.opacity = opacity
        self.drawn.append(shape)
        return shape

    def _quad(self, points, colour, opacity=255):
        """A trapezoid of road, which is the only shape perspective needs."""
        shape = pyglet.shapes.Polygon(*points, color=colour, batch=self.batch)
        shape.opacity = opacity
        self.drawn.append(shape)
        return shape

    def _dot(self, x, y, radius, colour, opacity=255):
        shape = pyglet.shapes.Circle(x, y, max(1.0, radius), color=colour,
                                     batch=self.batch)
        shape.opacity = opacity
        self.drawn.append(shape)
        return shape

    def _label(self, text, x, y, size=10, anchor='center'):
        label = pyglet.text.Label(
            text, font_size=calc_fontsize(size), color=self.textcolor,
            batch=self.batch, x=x, y=y, anchor_x=anchor,
            anchor_y='center', font_name=FONTLIST)
        self.drawn.append(label)
        return label

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.road is not None and self.phase in ('setting', 'running',
                                                    'scored'):
            self._draw_ground()
            self._draw_road()
            self._draw_hazards()
            self._draw_car()
            self._draw_sky()
            self._draw_crosshair()
            self._draw_dials()
        self._update_status()

    def _draw_ground(self) -> None:
        """The verges, the sky, and the line between them.

        The sky is tinted rather than left as page, and the horizon is
        drawn rather than implied, because the sky is where the
        crosshair lives: a player has to be able to see the edges of
        the box the sights move in without having to find them by
        pushing the mouse into a corner.
        """
        left, bottom, width, height = self._stage()
        sky = self._horizon()
        self._rect(left, bottom, width, sky - bottom, self.ink,
                   opacity=GRASS_ALPHA)
        self._rect(left, sky, width, bottom + height - sky, self.ink,
                   opacity=GRASS_ALPHA + 8)
        self._rect(left, sky, width, max(1.5, height * 0.004), self.ink,
                   opacity=MARK_ALPHA)

    def _draw_road(self) -> None:
        """The tarmac, the bands that slide down it, and the lane dividers.

        The bands are what makes the road move. Without them a clear
        stretch at four sub-rows a tick and a clear stretch at one look
        exactly alike, and the throttle would be a number rather than
        something you can feel.
        """
        at = self.ride.at
        part = (at % SUB) / float(SUB)
        row = at // SUB
        edges = [(step - part, self.far(step - part))
                 for step in range(SIGHT + 2)]
        centre = self._stage()[0] + self._stage()[2] / 2.0
        near, far = edges[0][1], edges[-1][1]
        self._quad([(centre - near[1], near[0]), (centre + near[1], near[0]),
                    (centre + far[1], far[0]), (centre - far[1], far[0])],
                   self.ink, opacity=ROAD_ALPHA)
        for step in range(SIGHT + 1):
            _a, (y_near, half_near) = edges[step]
            _b, (y_far, half_far) = edges[step + 1]
            if (row + step) % 2:
                self._quad([(centre - half_near, y_near),
                            (centre + half_near, y_near),
                            (centre + half_far, y_far),
                            (centre - half_far, y_far)],
                           self.ink, opacity=BAND_ALPHA)
            else:
                # Dashes on the rows between the bands, so the two
                # markings never land on the same stretch and cancel
                # each other out.
                for divider in range(1, LANES):
                    across = divider / float(LANES)
                    thick_near = max(1.0, half_near * 0.035)
                    thick_far = max(0.6, half_far * 0.035)
                    mid_near = centre + (across - 0.5) * 2.0 * half_near
                    mid_far = centre + (across - 0.5) * 2.0 * half_far
                    self._quad([(mid_near - thick_near, y_near),
                                (mid_near + thick_near, y_near),
                                (mid_far + thick_far, y_far),
                                (mid_far - thick_far, y_far)],
                               self.ink, opacity=MARK_ALPHA)
        for side in (-1.0, 1.0):
            self._quad([(centre + side * near[1], near[0]),
                        (centre + side * near[1] * 1.06, near[0]),
                        (centre + side * far[1] * 1.06, far[0]),
                        (centre + side * far[1], far[0])],
                       self.ink, opacity=MARK_ALPHA)

    def _in_view(self):
        """``(rows ahead, hazard)`` for everything near the window.

        Measured from the car's own tail in the sub-rows the rules use,
        so a hazard at zero rows ahead is one the car is inside.
        """
        at = self.ride.at
        for haz in self.road.hazards:
            ahead = self._rows_of(haz.body - at)
            if -0.6 <= ahead <= SIGHT:
                yield ahead, haz

    def _draw_hazards(self) -> None:
        """Everything standing in the road, far ones first.

        Painter's order, which is the only thing this renderer does
        about occlusion and is enough: a nearer thing is drawn over a
        further one, so a truck two rows away hides the cone behind it
        exactly as it should.
        """
        for ahead, haz in sorted(self._in_view(), key=lambda item: -item[0]):
            self._draw_hazard(ahead, haz)

    def _draw_hazard(self, ahead: float, haz) -> None:
        """One thing on the road, drawn so its two bits are legible.

        The rules read exactly two things about a hazard — whether a
        jump goes over it and what meeting it costs — so those are the
        two the drawing has to carry, and it carries them in shape
        rather than in colour: everything a jump clears lies flat on
        the tarmac and everything it does not stands up off it. Colour
        is left to say *which* of the nine it is, which is a thing to
        learn rather than a thing to have to work out at speed.
        """
        kind = KINDS[haz.kind]
        colour = PAINT[kind.name]
        ahead = max(0.0, ahead)
        base, half = self.far(ahead)
        top, _far = self.far(ahead + self._rows_of(BODY))
        lane_wide = 2.0 * half / LANES
        x = self.lane_x(ahead, haz.lane)
        tall = lane_wide * HEIGHT[kind.name]
        wide = lane_wide * (0.74 if kind.tall else 0.66)
        # The footprint: the road the thing actually blocks, drawn from
        # the near edge of its body to the far one. Every kind gets one,
        # so where a hazard *is* never depends on how it is drawn.
        self._quad([(x - wide / 2, base), (x + wide / 2, base),
                    (x + wide * 0.40, top), (x - wide * 0.40, top)],
                   colour, opacity=120 if kind.tall else 200)
        if kind.name == 'coin':
            self._dot(x, base + tall * 1.1, tall * 0.5, colour)
            self._dot(x, base + tall * 1.1, tall * 0.26, self.background)
            return
        if kind.name == 'ramp':
            self._quad([(x - wide / 2, base), (x + wide / 2, base),
                        (x + wide * 0.40, top + tall),
                        (x - wide * 0.40, top + tall)], colour)
            return
        if kind.name == 'pad':
            # A chevron pointing the way you are going: a pad is the
            # one thing here that makes the road come at you faster.
            for step in (0.0, 0.5):
                foot = base + tall * step
                self._quad([(x - wide / 2, foot), (x, foot + tall * 0.55),
                            (x + wide / 2, foot), (x, foot + tall * 0.20)],
                           colour)
            return
        if kind.name == 'cone':
            self._quad([(x - wide / 2, base), (x + wide / 2, base),
                        (x + wide * 0.10, base + tall),
                        (x - wide * 0.10, base + tall)], colour)
            self._rect(x - wide * 0.28, base + tall * 0.45, wide * 0.56,
                       tall * 0.18, self.background)
            return
        if kind.name == 'log':
            self._rect(x - wide / 2, base, wide, max(2.0, tall), colour)
            self._rect(x - wide / 2, base + tall * 0.45, wide,
                       max(1.0, tall * 0.16), self.background)
            return
        # Everything left stands up off the tarmac, which is the bit a
        # jump does not get over.
        self._rect(x - wide / 2, base, wide, tall, colour)
        if kind.name == 'donkey':
            head = wide * 0.30
            self._rect(x + wide * 0.20, base + tall * 0.74, head, head,
                       colour)
            for side in (0.26, 0.50):
                self._rect(x + wide * side, base + tall * 0.98, head * 0.26,
                           head * 0.62, colour)
        elif kind.name == 'truck':
            self._rect(x - wide * 0.34, base + tall * 0.34, wide * 0.68,
                       tall * 0.26, self.background)
            self._rect(x - wide * 0.40, base + tall * 0.74, wide * 0.80,
                       tall * 0.20, self.background)
        elif kind.name == 'barrier':
            for stripe in (0.24, 0.64):
                self._rect(x - wide / 2, base + tall * stripe, wide,
                           tall * 0.18, self.background)
        elif kind.name == 'rubble':
            for side, share in ((-0.30, 0.55), (0.28, 0.75)):
                self._rect(x + wide * side, base + tall, wide * 0.30,
                           tall * share * 0.5, colour)

    def _draw_car(self) -> None:
        """The car, drawn where it actually is between two lanes.

        Under the bonnet, so at :meth:`far` zero, and at a fraction of a
        lane whenever a swerve is running. Lifted off the tarmac while
        it is in the air, because whether the car is off the ground is
        the difference between a log going under it and a log ending
        the road, and a player has to be able to see it.
        """
        ride, grade = self.ride, self.road.grade
        base, half = self.far(0.0)
        lane_wide = 2.0 * half / LANES
        deep = self._horizon() - self._stage()[1]
        x = self.lane_x(0.0, drawn_lane(ride, grade))
        # Wide enough to read as filling a lane and short enough not to
        # be the view. A player looks *past* the car, so anything much
        # over a fifth of the road's height is the car standing in
        # front of the task.
        wide = lane_wide * 0.58
        tall = min(lane_wide * 0.30, deep * 0.20)
        lift = 0.0
        if ride.air:
            # A hop: highest in the middle of it, on the ground at both
            # ends, so the arc says how much of it is left.
            part = 1.0 - (ride.air - 0.5) / float(max(1, grade.hang))
            lift = tall * 1.3 * max(0.0, 1.0 - (2.0 * part - 1.0) ** 2)
            self._rect(x - wide * 0.36, base, wide * 0.72,
                       max(2.0, tall * 0.12), self.ink, opacity=60)
        y = base + lift
        self._rect(x - wide / 2, y, wide, tall, CAR_COLOUR)
        self._rect(x - wide * 0.30, y + tall * 0.42, wide * 0.60,
                   tall * 0.40, self.background)
        for side in (-1, 1):
            # Inside the body rather than under it. A wheel drawn below
            # the bonnet is a wheel drawn below the playfield, and the
            # playfield's bottom edge is the band the boundary reads.
            self._rect(x + side * wide * 0.40 - wide * 0.10, y,
                       wide * 0.20, tall * 0.26, self.ink, opacity=200)

    def _draw_sky(self) -> None:
        """The targets, and a ring where one was taken."""
        left, bottom, width, height = self._sky_rect()
        size = max(4.0, min(width, height) * 0.045)
        for index, target in enumerate(self.road.sky):
            if not target.aloft(self.ride.at):
                continue
            across, up = target.where(self.ride.at)
            x, y = left + across * width, bottom + up * height
            if index in self.downed:
                self._dot(x, y, size * 0.9, DOWNED, opacity=110)
                self._dot(x, y, size * 0.55, self.background, opacity=110)
                continue
            self._dot(x, y, size, TARGET)
            self._dot(x, y, size * 0.45, self.background)

    def _draw_crosshair(self) -> None:
        """Where the sights are pointing, whoever is pointing them.

        Drawn from the same two numbers the ports write, so what a
        learner is handed is what a person is looking at.
        """
        left, bottom, width, height = self._sky_rect()
        x = left + self.cross_x * width
        y = bottom + self.cross_y * height
        arm = max(5.0, min(width, height) * 0.055)
        thick = max(1.5, arm * 0.14)
        loaded = sighted(self.road, self.ride.at, self.cross_x, self.cross_y,
                         self.downed) is not None
        colour = TARGET if loaded else self.ink
        self._rect(x - arm, y - thick / 2, arm * 2, thick, colour)
        self._rect(x - thick / 2, y - arm, thick, arm * 2, colour)
        self._rect(x - thick / 2, y - thick / 2, thick, thick,
                   self.background)

    def _draw_dials(self) -> None:
        """Road behind, clock spent, gear, and what has been taken.

        Stacked down the verge to the left of the road, which is the
        one piece of the playfield the road never reaches — so the
        dials never sit on top of anything a driver is looking at.

        The first two are bars one above the other on purpose. What a
        driver has to know is whether the pace is being held, and that
        is a comparison of two fractions rather than either of them: if
        the clock bar is longer than the road bar the road is being
        lost to the clock, and it says so long before the clock runs
        out.
        """
        left, bottom, width, height = self._stage()
        road, ride = self.road, self.ride
        margin = max(6.0, width * 0.012)
        span = max(40.0, min(width * 0.155,
                             width / 2.0 - self._near_half() - margin * 2))
        x = left + margin
        step = height * 0.155
        y = self._horizon() - height * 0.06
        thick = max(3.0, height * 0.024)
        for share, colour, text in (
                (min(1.0, ride.at / float(max(1, road.length))), DOWNED,
                 _('%d of %d rows') % (ride.rows_done, road.rows)),
                (min(1.0, ride.ticks / float(max(1, road.clock))),
                 PAINT['cone'],
                 _('%d of %d ticks') % (ride.ticks, road.clock))):
            self._rect(x, y, span, thick, self.ink, opacity=40)
            self._rect(x, y, span * share, thick, colour)
            self._label(text, x, y - height * 0.05, anchor='left')
            y -= step
        pip = span / float(road.grade.top)
        for gear in range(road.grade.top):
            self._rect(x + gear * pip, y, pip * 0.74, thick * 1.7,
                       CAR_COLOUR if gear < ride.speed else self.ink,
                       opacity=255 if gear < ride.speed else 40)
        self._label(_('gear %d of %d') % (ride.speed, road.grade.top),
                    x, y - height * 0.05, anchor='left')
        y -= step
        self._label(_('%d points') % (self.points + ride.points), x, y,
                    anchor='left')
        self._label(_('%d of %d shot') % (self.shot, len(road.sky)),
                    x, y - height * 0.05, anchor='left')

    def _update_status(self) -> None:
        if self.road is None or self.ride is None:
            self.status.text = self.message
            return
        self.status.text = _('Road %d of %d     %s'
                             ) % (self.trial, self.total_trials, self.message)

    # --- housekeeping -----------------------------------------------------

    def close(self) -> None:
        if Twohands.instance is not self:
            return
        self._clear_drawn()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_motion,
                                     self.on_mouse_press, self.on_draw)
        Twohands.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events -----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        """The wheel. The sights are on the mouse, which is the point.

        Space does two jobs and the phases keep them apart: it starts
        the run when there is no road under the car, and it jumps when
        there is.
        """
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'scored' and self.clock() >= self.until:
                self._next_trial()
            else:
                self.act(JUMP)
        elif symbol in (key.LEFT, key.A):
            self.act(LEFT)
        elif symbol in (key.RIGHT, key.D):
            self.act(RIGHT)
        elif symbol in (key.UP, key.W):
            self.act(FASTER)
        elif symbol in (key.DOWN, key.S):
            self.act(SLOWER)
        return pyglet.event.EVENT_HANDLED

    def _aim_at(self, x: int, y: int) -> None:
        """Put the crosshair where the mouse is, in the sky's own units."""
        left, bottom, width, height = self._sky_rect()
        self.cross_x = min(1.0, max(0.0, (x - left) / float(max(1.0, width))))
        self.cross_y = min(1.0, max(0.0,
                                    (y - bottom) / float(max(1.0, height))))

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> bool:
        if self.phase in ('setting', 'running', 'scored'):
            self._aim_at(x, y)
            self._redraw()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if button == mouse.LEFT and self.phase == 'running':
            self._aim_at(x, y)
            self.act(FIRE)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['BEAT_SECONDS', 'CAR_COLOUR', 'DEPTH', 'HORIZON', 'PAINT',
           'SET_SECONDS', 'SIGHT', 'Twohands']
