# -*- coding: utf-8 -*-
"""Out of Sight: hold on to dots that stop being visible.

A few dots flash a colour and then look like all the others, the way
Moving Targets begins. What follows is different in two ways, and both
are aimed at the same thing: making the picture on screen right now
insufficient.

The first is the crossing. Every so often two dots are aimed at the
point exactly between them, so they arrive together, overlap as one,
and pass through. At that instant nothing in the frame says which came
from which side. The second is the blinds — solid slabs the dots pass
behind. For a stretch there is no dot to look at at all, only where it
was going and how fast, and a blind that hangs over the wall lets a dot
bounce while it is hidden, so the place it comes back out is not on the
line it went in on.

The question is asked *during* the motion, not after it. Now and then
one dot is ringed and there are two keys: J for "that one is mine", F
for "it is not". A round is a handful of those, and the ring hunts the
moments identity was just at risk — the dot that has this second come
out from behind a blind, or the one that has just passed through
another. Asking at the end would let a good guess at the last moment
stand in for having held on the whole way; asking in the middle, while
everything keeps moving, cannot be answered that way.

That makes the task a poor one for anything that reads a single frame,
and a fair one for anything that carries state: the dots move in
straight lines and bounce off walls, so a tracker that keeps a
position and a velocity for each of them can follow every crossing and
predict every emergence exactly. Nothing is ever decided by a coin.
The dots never change course while hidden — that would make the task
unanswerable rather than hard, and there is no interest in a question
with no right answer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        scale_to_height, width_center)
from . import cursor, taskoptions
from .tracking import CAUGHT, CUED, MISSED, PLAIN, bounced
from ..i18n import _

#: Dots a round may hold, and how many of them can be yours. The
#: ceilings are room rather than code, the same bargain the ball flock
#: makes, and a round must leave one dot that is not yours or the
#: question answers itself.
FEWEST_DOTS, MOST_DOTS = 3, 30

#: How the phases pace themselves, in seconds. The cue is long enough
#: to find every flashed dot once and the flock stands still for it;
#: the reveal at the end of a round shows what was lost.
CUE_SECONDS = 2.0
REVEAL_SECONDS = 1.8

#: How long a ring stays up waiting for an answer, and how long the
#: answer's colour stays on it afterwards.
PROBE_SECONDS = 1.6
VERDICT_SECONDS = 0.6

#: The quiet stretch between one ring going away and the next arriving.
#: Long enough that the ring is not the whole task, short enough that a
#: round of six questions is about half a minute.
SHORTEST_GAP, LONGEST_GAP = 1.0, 3.0

#: How long after a crossing, or after coming back out from behind a
#: blind, a dot still counts as one whose identity was just in doubt.
#: The ring prefers those dots, because that is where the answer is
#: worth something.
RISK_SECONDS = 2.5

#: The two answer keys: the home-row pair, one per hand, the same
#: pair Lookout uses. True is "that one is mine".
ANSWER_KEYS = {key.J: True, key.F: False}

#: The slabs the dots hide behind, dark enough to read as solid on
#: either background and far from every dot colour.
BLIND_ON_BLACK = (78, 82, 92)
BLIND_ON_WHITE = (148, 152, 162)

#: The most of the field the slabs may take between them. It is a
#: playability floor first — half a field with nothing visible in it
#: is not a tracking task — and a termination proof second: the rest
#: of the field is always open, so looking for a spawn spot in the
#: clear always finds one.
MOST_COVERED = 0.45


class Blind(NamedTuple):
    """A slab the dots pass behind, in fractions of the window.

    It is drawn over them rather than consulted before drawing them,
    so a dot halfway in is halfway visible with no arithmetic — but
    the ring needs to know whether a dot can be pointed at, and that
    is what :meth:`covers` is for.
    """

    left: float
    bottom: float
    width: float
    height: float

    def covers(self, x: float, y: float) -> bool:
        """Is the point (*x*, *y*) behind this slab?"""
        return (self.left <= x <= self.left + self.width
                and self.bottom <= y <= self.bottom + self.height)

    def overlaps(self, other: 'Blind') -> bool:
        """Do the two slabs share any area?"""
        return (self.left < other.left + other.width
                and other.left < self.left + self.width
                and self.bottom < other.bottom + other.height
                and other.bottom < self.bottom + self.height)


def area_in(blind: Blind, field: Tuple[float, float, float, float]) -> float:
    """How much of *field* — low x, high x, low y, high y — a slab eats.

    A slab may hang past the wall, and the part that hangs over costs
    the flock nothing, so only the overlap is charged for.
    """
    low_x, high_x, low_y, high_y = field
    across = min(blind.left + blind.width, high_x) - max(blind.left, low_x)
    up = min(blind.bottom + blind.height, high_y) - max(blind.bottom, low_y)
    return max(0., across) * max(0., up)


def hidden(blinds: Sequence[Blind], x: float, y: float) -> bool:
    """Is a dot centred on (*x*, *y*) out of sight?

    Centre rather than circle: a dot more than half covered is one the
    ring has no business pointing at, and one still showing an edge is
    one you can still answer about.
    """
    return any(blind.covers(x, y) for blind in blinds)


def rendezvous(one: 'Dot', other: 'Dot', speed: float,
               aspect: float) -> float:
    """Aim two dots at the point between them; return the seconds.

    The midpoint is the only meeting place both can reach at the same
    pace, because it is exactly as far from one as from the other. So
    neither has to hurry to make the appointment, and nothing about
    how a dot moves — not its speed, not its heading — says whether it
    is one of yours or which one it is. They arrive together, overlap,
    and pass through; the outgoing velocities are each other's exact
    negatives, which is what makes the instant of the crossing
    symmetric.

    A velocity is screen-heights a second on *both* axes, so the
    horizontal reach has to be put in those units before the two are
    measured against each other.
    """
    mid_x, mid_y = (one.x + other.x) / 2., (one.y + other.y) / 2.
    reach_x = (mid_x - one.x) / aspect
    reach_y = mid_y - one.y
    span = math.hypot(reach_x, reach_y)
    if span <= 0. or speed <= 0.:
        return 0.
    seconds = span / speed
    one.vx, one.vy = reach_x / seconds, reach_y / seconds
    other.vx, other.vy = -one.vx, -one.vy
    return seconds


class Dot:
    """One dot: where it is, where it is going, and what it was.

    *busy_until* is the moment a crossing it is committed to happens,
    and zero when it is committed to none; *risky_until* is how long
    it stays a dot the ring would rather ask about.
    """

    __slots__ = ('x', 'y', 'vx', 'vy', 'target', 'busy_until',
                 'risky_until', 'was_hidden', 'circle')

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 target: bool) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.target = target
        self.busy_until = 0.0
        self.risky_until = 0.0
        self.was_hidden = False
        self.circle: Optional[pyglet.shapes.Circle] = None


class OutOfSight:
    """Follow dots through crossings and behind blinds. Esc returns."""

    instance: Optional['OutOfSight'] = None

    def __init__(self) -> None:
        if OutOfSight.instance is not None:
            OutOfSight.instance.close()
        self.rng = random.Random()
        self.dots: List[Dot] = []
        self.blinds: List[Blind] = []
        self.blind_shapes: List[object] = []
        self.round = 0
        self.results: List[Tuple[int, int, int]] = []  # (held, asked, right)
        self.hits = 0
        self.wrong = 0
        self.late = 0
        self.reaction_times: List[float] = []
        self.probe: Optional[Dot] = None
        self.ring: Optional[pyglet.shapes.Arc] = None
        self.probe_at = 0.0
        self.probe_ends = 0.0
        self.next_probe = 0.0
        self.next_cross = 0.0
        self.probes_done = 0
        self.round_right = 0
        self.schedule: List[bool] = []
        self.verdict: Optional[bool] = None
        self.verdict_until = 0.0
        self.phase = 'ready'
        self.until = 0.0
        self.message = _('Press Space to start')
        self._read_options()
        self.held = self.clamped_targets(self.start_targets)
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        OutOfSight.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.OUT_OF_SIGHT)
        self.dot_count = int(opts['SIGHT_DOTS'])
        self.start_targets = int(opts['SIGHT_TARGETS'])
        self.speed = int(opts['SIGHT_SPEED']) / 100.  # screen heights / s
        self.blind_count = int(opts['SIGHT_BLINDS'])
        self.blind_width = int(opts['SIGHT_BLIND_WIDTH']) / 100.
        self.cross_gap = int(opts['SIGHT_CROSS_MS']) / 1000.
        self.probes_per_round = int(opts['SIGHT_PROBES'])
        self.total_rounds = int(opts['SIGHT_ROUNDS'])
        self.adaptive = bool(opts['SIGHT_ADAPTIVE'])

    def clamped_targets(self, count: int) -> int:
        """At least one of yours, and at least one dot that is not."""
        return max(1, min(self.dot_count - 1, count))

    def open_options(self) -> None:
        taskoptions.open_task_options('out_of_sight',
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
        self.ink = (fg, fg, fg)
        self.slab = BLIND_ON_BLACK if state.cfg.BLACK_BACKGROUND \
            else BLIND_ON_WHITE
        self.batch = pyglet.graphics.Batch()
        # Dots, then the ring over the dot it points at, then the
        # blinds over both: a hidden dot takes its ring with it.
        self.dot_group = pyglet.graphics.Group(order=0)
        self.ring_group = pyglet.graphics.Group(order=1)
        self.blind_group = pyglet.graphics.Group(order=2)
        self.title = pyglet.text.Label(
            _('Out of Sight'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     J: that one is mine'
              '     F: it is not     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # The old batch owns the old drawables; let them all be remade.
        for dot in self.dots:
            dot.circle = None
        self.blind_shapes = []
        self.ring = None
        self._sync_blinds()
        self._sync_dots()
        self._update_status()

    def relayout(self) -> None:
        self._build_chrome()

    def radius(self) -> float:
        return max(7.0, float(scale_to_height(19)))

    def _bounds(self) -> Tuple[float, float, float, float]:
        """low x, high x, low y, high y — in fractions, dot centre."""
        window = state.window
        edge_x = self.radius() / window.width
        edge_y = self.radius() / window.height
        return (edge_x + 0.01, 1.0 - edge_x - 0.01,
                edge_y + 0.11, 1.0 - edge_y - 0.15)

    def _aspect(self) -> float:
        return state.window.height / max(1, state.window.width)

    # --- the field -------------------------------------------------------

    def _lay_blinds(self) -> None:
        """Scatter the slabs, sized in screen heights and kept apart.

        A slab may hang a third of itself past the wall on purpose:
        then a dot can bounce while it is hidden and come back out
        somewhere the straight line it went in on never reaches. That
        is the one place the task asks for a bounce to be predicted
        rather than seen, and it is still exactly predictable.

        Asking for more slabs than the field can take is not an error
        and not a clamp that can be worked out in advance: a slab is
        laid if it fits beside the ones already down and inside the
        share of the field the slabs are allowed between them, and
        dropped if it does not. That share is what keeps the field
        playable at the widest slab the menu offers — and what makes
        finding spawn spots in the open terminate at all.
        """
        self.blinds = []
        if self.blind_count <= 0 or self.blind_width <= 0:
            return
        field = self._bounds()
        low_x, high_x, low_y, high_y = field
        room = (high_x - low_x) * (high_y - low_y) * MOST_COVERED
        aspect = self._aspect()
        narrow, along = self.blind_width, self.blind_width * 2.6
        for _slab in range(self.blind_count):
            for _attempt in range(200):
                upright = self.rng.random() < 0.5
                width = (narrow if upright else along) * aspect
                height = along if upright else narrow
                candidate = Blind(
                    self.rng.uniform(low_x - width / 3.,
                                     high_x - 2 * width / 3.),
                    self.rng.uniform(low_y - height / 3.,
                                     high_y - 2 * height / 3.),
                    width, height)
                taken = area_in(candidate, field)
                if taken > room:
                    continue
                if not any(candidate.overlaps(laid)
                           for laid in self.blinds):
                    self.blinds.append(candidate)
                    room -= taken
                    break

    def _scattered(self) -> List[Tuple[float, float]]:
        """Spawn spots in clear air, and never behind a blind.

        Every dot has to be seen at least once, when the cue names
        yours, so a spot the slabs already cover is no spot at all.
        """
        low_x, high_x, low_y, high_y = self._bounds()
        apart = 2.4 * self.radius() / state.window.height
        while True:
            spots: List[Tuple[float, float]] = []
            for _attempt in range(self.dot_count * 80):
                spot = (self.rng.uniform(low_x, high_x),
                        self.rng.uniform(low_y, high_y))
                if hidden(self.blinds, spot[0], spot[1]):
                    continue
                if all((spot[0] - x) ** 2 + (spot[1] - y) ** 2
                       >= apart * apart for x, y in spots):
                    spots.append(spot)
                    if len(spots) == self.dot_count:
                        return spots
            apart *= 0.8

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self._drop_dots()
        self._drop_ring()
        self.blinds = []                # a field belongs to its run
        self._sync_blinds()
        self.round = 0
        self.results = []
        self.hits = self.wrong = self.late = 0
        self.reaction_times = []
        self.held = self.clamped_targets(self.start_targets)
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self._next_round()

    def _probe_schedule(self) -> List[bool]:
        """Which questions this round asks about a dot of yours.

        An independent coin per question, and deliberately not an
        even half and half. A round balanced exactly would pay for
        counting instead of tracking: having seen three answers of
        "yours" in a round of six, the last three would have to be
        the others, and a player who kept score rather than kept
        hold would beat one who did the task. A coin leaves nothing
        to count, and still leaves any fixed answer on fifty per
        cent over a run.
        """
        return [self.rng.random() < 0.5
                for _question in range(self.probes_per_round)]

    def _next_round(self) -> None:
        if self.round >= self.total_rounds:
            self._finish()
            return
        self.round += 1
        self._drop_dots()
        self._drop_ring()
        self._lay_blinds()
        self._sync_blinds()
        count = self.clamped_targets(self.held)
        chosen = set(self.rng.sample(range(self.dot_count), count))
        dots = []
        for index, (x, y) in enumerate(self._scattered()):
            heading = self.rng.uniform(0.0, 2 * math.pi)
            dots.append(Dot(x, y,
                            vx=self.speed * math.cos(heading),
                            vy=self.speed * math.sin(heading),
                            target=index in chosen))
        self.dots = dots
        self.schedule = self._probe_schedule()
        self.probes_done = 0
        self.round_right = 0
        self.verdict = None
        self.phase = 'cueing'
        self.until = time.time() + CUE_SECONDS
        self.message = _('Hold on to the %s') % (
            _('coloured dot') if count == 1 else
            _('%d coloured dots') % count)
        self._sync_dots()
        self._update_status()

    def held_now(self) -> int:
        return sum(1 for dot in self.dots if dot.target)

    # --- the motion ------------------------------------------------------

    def _move(self, dt: float) -> None:
        """Advance the flock, bouncing off the walls.

        The dots pass through each other rather than colliding, for
        the same reason the ball flock does: two identical dots
        crossing is the moment tracking is hard, and bouncing them
        apart would delete the difficulty in the name of physics.
        """
        low_x, high_x, low_y, high_y = self._bounds()
        aspect = self._aspect()
        for dot in self.dots:
            dot.x += dot.vx * dt * aspect
            dot.y += dot.vy * dt
            dot.x, dot.vx = bounced(dot.x, dot.vx, low_x, high_x)
            dot.y, dot.vy = bounced(dot.y, dot.vy, low_y, high_y)

    def _mark_risk(self, now: float) -> None:
        """Note the two moments a dot's identity was just in doubt.

        A crossing it has now made, and a return to the open from
        behind a slab. Both are moments the frame alone stopped
        saying which dot this is, so both are what the ring hunts.
        """
        for dot in self.dots:
            if dot.busy_until and now >= dot.busy_until:
                dot.busy_until = 0.0
                dot.risky_until = now + RISK_SECONDS
            out_of_sight = hidden(self.blinds, dot.x, dot.y)
            if dot.was_hidden and not out_of_sight:
                dot.risky_until = now + RISK_SECONDS
            dot.was_hidden = out_of_sight

    def _maybe_cross(self, now: float) -> None:
        """Send two dots through each other, if one is due.

        The pair is drawn at random from every dot not already
        committed to a crossing. Drawing it any other way — always
        including one of yours, say — would make the crossings
        themselves say which dots are yours.
        """
        if self.cross_gap <= 0 or now < self.next_cross:
            return
        self.next_cross = now + self.rng.uniform(0.6, 1.4) * self.cross_gap
        free = [dot for dot in self.dots if not dot.busy_until]
        if len(free) < 2:
            return
        one, other = self.rng.sample(free, 2)
        meets = now + rendezvous(one, other, self.speed, self._aspect())
        one.busy_until = other.busy_until = meets

    # --- the questions ---------------------------------------------------

    def _probeable(self, want: bool) -> Optional[Dot]:
        """A dot to ring: one of *want*'s kind, and one you can see.

        Among those, one whose identity was recently in doubt, when
        there is one. Risk is dealt out by the crossings and the
        slabs, neither of which knows which dots are yours, so
        preferring risky dots does not leak the answer.
        """
        now = time.time()
        open_air = [dot for dot in self.dots
                    if dot.target == want
                    and not hidden(self.blinds, dot.x, dot.y)]
        if not open_air:
            return None
        risky = [dot for dot in open_air if dot.risky_until > now]
        return self.rng.choice(risky or open_air)

    def _raise_probe(self, now: float) -> None:
        """Ring a dot and start its clock.

        When every dot of the wanted kind is behind a slab there is
        nothing to point at, so the question simply waits — the flock
        is moving, and one will be out in a moment.
        """
        dot = self._probeable(self.schedule[self.probes_done])
        if dot is None:
            return
        self.probe = dot
        self.probe_at = now
        self.probe_ends = now + PROBE_SECONDS
        self.message = _('This one — yours?')

    def answer(self, mine: bool) -> None:
        """A press of J (mine) or F (not mine) on the ringed dot."""
        if self.phase != 'tracking' or self.probe is None:
            return
        if self.verdict is not None:
            return
        now = time.time()
        right = mine == self.probe.target
        self.reaction_times.append(now - self.probe_at)
        if right:
            self.hits += 1
            self.message = _('Yes — %d ms') % int(
                self.reaction_times[-1] * 1000)
        else:
            self.wrong += 1
            self.message = (_('No — that one was yours') if
                            self.probe.target else
                            _('No — that one was never yours'))
        self._settle(right, now)

    def _too_slow(self, now: float) -> None:
        """The ring ran out with no answer."""
        self.late += 1
        self.message = (_('Too slow — that one was yours') if
                        self.probe is not None and self.probe.target else
                        _('Too slow — that one was not yours'))
        self._settle(False, now)

    def _settle(self, right: bool, now: float) -> None:
        self.verdict = right
        self.verdict_until = now + VERDICT_SECONDS
        self.probes_done += 1
        self.round_right += int(right)
        self._update_status()

    def _retire_probe(self, now: float) -> None:
        self.probe = None
        self.verdict = None
        self._drop_ring()
        self.next_probe = now + self.rng.uniform(SHORTEST_GAP, LONGEST_GAP)
        self.message = _('Keep hold of them')

    # --- the clock -------------------------------------------------------

    def update(self, dt: float) -> None:
        now = time.time()
        if self.phase == 'cueing':
            if now < self.until:
                return
            self.phase = 'tracking'
            self.next_probe = now + self.rng.uniform(SHORTEST_GAP,
                                                     LONGEST_GAP)
            self.next_cross = now + self.rng.uniform(0.3, 1.0)
            for dot in self.dots:
                dot.was_hidden = hidden(self.blinds, dot.x, dot.y)
            self.message = _('Keep hold of them')
        elif self.phase == 'tracking':
            self._move(min(dt, 0.1))
            self._mark_risk(now)
            self._maybe_cross(now)
            if self.verdict is not None:
                if now >= self.verdict_until:
                    self._retire_probe(now)
            elif self.probe is not None:
                if now >= self.probe_ends:
                    self._too_slow(now)
            elif self.probes_done >= self.probes_per_round:
                self._end_round(now)
            elif now >= self.next_probe:
                self._raise_probe(now)
        elif self.phase == 'revealing':
            self._move(min(dt, 0.1))
            if now >= self.until:
                self._next_round()
                return
        else:
            return
        self._sync_dots()
        self._update_status()

    def _end_round(self, now: float) -> None:
        asked, right = self.probes_done, self.round_right
        self.results.append((self.held_now(), asked, right))
        if right == asked:
            self.message = _('All %d — nothing lost') % asked
        else:
            self.message = _('%d of %d') % (right, asked)
        if self.adaptive:
            grown = self.held + 1 if right == asked else self.held - 1
            self.held = self.clamped_targets(grown)
        self.phase = 'revealing'
        self.until = now + REVEAL_SECONDS

    def _finish(self) -> None:
        self.phase = 'done'
        self._drop_ring()
        tally = self.score()
        self.message = _('%d%% — %d of %d held, %d ms average') % (
            tally['accuracy'], tally['hits'], tally['asked'],
            tally['mean_ms'])
        self._update_status()

    def score(self) -> Dict[str, int]:
        asked = self.hits + self.wrong + self.late
        mean = (sum(self.reaction_times) / len(self.reaction_times)
                if self.reaction_times else 0.0)
        return {
            'rounds': len(self.results),
            'asked': asked,
            'hits': self.hits,
            'wrong': self.wrong,
            'late': self.late,
            'accuracy': int(round(100. * self.hits / asked)) if asked else 0,
            'mean_ms': int(round(mean * 1000)),
            'most_held': max((held for held, ask, right in self.results
                              if ask and right == ask), default=0),
        }

    # --- drawing ---------------------------------------------------------

    def _colour(self, dot: Dot) -> Tuple[int, int, int]:
        if self.phase in ('cueing', 'revealing') and dot.target:
            return CUED
        return PLAIN

    def _ring_colour(self) -> Tuple[int, int, int]:
        if self.verdict is True:
            return CAUGHT
        if self.verdict is False:
            return MISSED
        return self.ink

    def _sync_dots(self) -> None:
        window = state.window
        for dot in self.dots:
            if dot.circle is None:
                dot.circle = pyglet.shapes.Circle(
                    0, 0, self.radius(), color=PLAIN, batch=self.batch,
                    group=self.dot_group)
            dot.circle.position = (dot.x * window.width,
                                   dot.y * window.height)
            dot.circle.color = self._colour(dot)
        self._sync_ring()

    def _sync_ring(self) -> None:
        if self.probe is None:
            self._drop_ring()
            return
        window = state.window
        radius = self.radius()
        if self.ring is None:
            self.ring = pyglet.shapes.Arc(
                0, 0, radius * 1.7, thickness=max(2.0, radius * 0.2),
                color=self.ink, batch=self.batch, group=self.ring_group)
        self.ring.position = (self.probe.x * window.width,
                              self.probe.y * window.height)
        self.ring.color = self._ring_colour()

    def _sync_blinds(self) -> None:
        for shape in self.blind_shapes:
            try:
                shape.delete()
            except Exception:
                pass
        self.blind_shapes = []
        window = state.window
        for blind in self.blinds:
            self.blind_shapes.append(pyglet.shapes.Rectangle(
                blind.left * window.width, blind.bottom * window.height,
                blind.width * window.width, blind.height * window.height,
                color=self.slab, batch=self.batch, group=self.blind_group))

    def _drop_ring(self) -> None:
        if self.ring is not None:
            try:
                self.ring.delete()
            except Exception:
                pass
            self.ring = None

    def _drop_dots(self) -> None:
        for dot in self.dots:
            if dot.circle is not None:
                try:
                    dot.circle.delete()
                except Exception:
                    pass
                dot.circle = None
        self.dots = []
        self.probe = None

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase not in ('ready', 'done'):
            if self.total_rounds:
                parts.append(_('round %d/%d') % (self.round,
                                                 self.total_rounds))
            parts.append(_('question %d/%d') % (
                min(self.probes_done + 1, self.probes_per_round),
                self.probes_per_round))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if OutOfSight.instance is not self:
            return
        self._drop_dots()
        self._drop_ring()
        for shape in self.blind_shapes:
            try:
                shape.delete()
            except Exception:
                pass
        self.blind_shapes = []
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        OutOfSight.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol in ANSWER_KEYS:
            self.answer(ANSWER_KEYS[symbol])
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
