# -*- coding: utf-8 -*-
"""Cookie Thief: one cookie a press, and stop before the door opens.

The boy stands **at** the jar with his hand over it. Press and he takes
one, now — it is in the count on the beat you asked for and his hand is
back at his side on the same beat. There is nothing to wind up and
nothing to wait out, and at a sixth of a second a beat the whole round
is over in three or four seconds.

What you are watching is **the door**, and it only ever opens. Every
cookie leaves a gap she would notice on its own, and that part of the
opening never closes again; taking them quickly is noisy on top of
that, and that part dies away on a quiet beat. Both are drawn, in two
shades, because they are two different things: one is what you have
taken and one is how loudly you took it.

She comes the first beat the door reaches a number nobody is told. The
range it is in is shaded on the frame, so you can see that you are into
the part where she might be and not which press is the one. On the
first five rungs she stands in the doorway for a beat or two before her
eyes are on the jar and *leave* still saves you. From the sixth there
is no warning at all: the press that opens the door far enough is the
press she walks in on.

So there are four things to do with a beat and every one of them is
worth doing. Grab. Wait, which lets the noise die down and buys the
grab after next. **Leave**, which banks the haul and ends the round —
the only move that cannot go wrong and the only one that stops you
earning. And reach for the golden one, which is two beats you cannot
take back.

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
from ..cookiethief import (COMING, DOG, GOLD_BEATS, GRAB, GRADES, LEAVE,
                           LUNGE, MOTHER, SAFE, SISTER, WATCHING, Thief,
                           after_a_grab, beat, cleared, door, floor_of,
                           generate, haul, over, press, rehearse)
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Okabe-Ito. The cookie is orange and the golden one is yellow, which
#: are the two that read as the same object in different states.
COOKIE = (230, 159, 0)
GOLDEN = (240, 228, 66)

#: The door's opening. One colour in two weights rather than two
#: colours: the solid part is the gap the missing cookies left and it
#: never closes, the faint part on top of it is the noise a quick hand
#: made and that does. They are the same door opened further, so they
#: read better as one thing in two strengths than as two things — and
#: the second colour it used to have was the golden cookie's yellow,
#: which is a thing on the counter and must not turn up in the doorway.
DOOR_INK = (213, 94, 0)
FLOOR_ALPHA, NOISE_ALPHA = 120, 45

#: Who might be in the doorway. The height is what tells them apart at a
#: glance, because on the top rungs there is one beat to do it in and a
#: colour read alone is a colour read too slowly.
FIGURES: Dict[str, Tuple[Tuple[int, int, int], float, str]] = {
    MOTHER: ((204, 121, 167), 1.00, _('Mother')),
    SISTER: ((0, 114, 178), 0.62, _('your sister')),
    DOG: ((0, 158, 115), 0.28, _('the dog')),
}

#: Where things sit across the canvas, as shares of its width. The boy
#: is up against the jar rather than across the kitchen from it: his
#: hand is already over the lid and a press is a press, not a journey.
JAR_AT, BOY_AT, DOOR_AT = 0.16, 0.30, 0.78

#: How long a beat takes. Short, because the whole point of one cookie a
#: press is that presses come quickly. The same number serves a person
#: at sixty frames a second and an agent stepping a virtual clock, so
#: neither is playing a different game.
BEAT_SECONDS = 0.16

#: How long the round sits still before the first beat, so the quota can
#: be read.
SET_SECONDS = 0.8

#: How long a verdict stays up before the next round can be called.
VERDICT_SECONDS = 1.0

#: Clear this share of the last four rounds and an adaptive run climbs;
#: fewer than this and it drops.
CLIMB_AT, DROP_BELOW = 0.75, 0.4


class CookieThief:
    """The jar, the boy and the door. Esc returns to the hub."""

    instance: Optional['CookieThief'] = None

    def __init__(self) -> None:
        if CookieThief.instance is not None:
            CookieThief.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        #: Coach mode: paint a verdict on the beat a cookie lands and on
        #: the beats she has her eyes on him. Off for people — it
        #: changes the game — and switched on by the agent boundary. It
        #: is blind to the trigger and to the deadline: see the
        #: wrapper's docstring for why that matters.
        self.coach = False
        self.setup = None
        self.thief: Optional[Thief] = None
        self.trial = 0
        self.results: List[Tuple[int, bool]] = []       # (rung, cleared)
        self.cookies = 0
        self.points = 0
        #: True on the frames his hand is in the jar. One beat, and it
        #: is set the moment the key is pressed rather than on the next
        #: beat: a press that does not show until the clock comes round
        #: is a key that feels broken.
        self.grabbing = False
        self.until = 0.0
        self.beat_at = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        CookieThief.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.COOKIE_THIEF)
        self.start_rung = int(opts['COOKIE_LEVEL'])
        self.total_trials = int(opts['COOKIE_TRIALS'])
        self.beat_seconds = float(opts['COOKIE_BEAT_SECONDS'])
        self.set_seconds = float(opts['COOKIE_SET_SECONDS'])
        self.adaptive = bool(opts['COOKIE_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('cookie_thief',
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
            _('Cookie Thief'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch, x=width_center(),
            y=from_top_edge(36), anchor_x='center', anchor_y='center',
            font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Wrapped rather than trimmed: the top rungs have three things
        # to say about themselves and on a narrow window one line of
        # them ran off both edges of the screen.
        self.asked = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(94),
            width=int(state.window.width * 0.78), multiline=True,
            align='center', anchor_x='center', anchor_y='top',
            font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   X: take one   Z: leave'
              '   G: golden   C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the round by this
        # label's colour. Rebuilt with the chrome so a verdict already
        # up is put back: a relayout on the frame a round settles would
        # otherwise drop it, and an outcome only sometimes derivable is
        # worse than one that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        self._update_asked()
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _canvas(self) -> Tuple[float, float, float, float]:
        """Where the kitchen lives: left, bottom, width, height.

        Held clear of the band the agent boundary reads. The jar is
        orange and Mother is reddish purple, and either of them down
        there would be counted as a verdict.
        """
        window = state.window
        top = from_top_edge(168)
        bottom = above_the_band(from_bottom_edge(64))
        return (window.width * 0.07, bottom,
                window.width * 0.86, max(60.0, top - bottom))

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.setup = None
        self.thief = None
        self.trial = 0
        self.results = []
        self.cookies = 0
        self.points = 0
        self.grabbing = False
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
        self.setup = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self.thief = Thief()
        self.grabbing = False
        self.phase = 'setting'
        self.until = self.clock() + self.set_seconds
        self.beat_at = self.clock() + self.set_seconds
        self.message = _('The jar is full')
        self._update_asked()
        self._redraw()

    def _update_asked(self) -> None:
        """What the round wants, said in words above the kitchen."""
        if self.setup is None:
            self.asked.text = ''
            return
        grade = self.setup.grade
        wants = [_('Rung %d, %s.') % (self.rung, _(grade.name)),
                 _('Take %d and get out.') % grade.quota]
        wants.append(_('She stands in the door for %d beats first.')
                     % grade.warn if grade.reactive else
                     _('No warning at all: the press that opens the door far '
                       'enough is the one she sees.'))
        if grade.gold:
            wants.append(_('The golden one is worth %d.') % grade.gold)
        if grade.decoys:
            wants.append(_('Not everyone at the door is her.'))
        self.asked.text = ' '.join(wants)

    # --- what the player does --------------------------------------------

    def act(self, port: int) -> bool:
        """One press, and it happens now.

        The screen is redrawn here rather than left to the next beat.
        At a sixth of a second a beat that is the difference between a
        key that answers and a key that looks broken, and the thing it
        answers with is the hand: it goes into the jar on the frame you
        pressed and is back at his side on the next one.
        """
        if self.phase != 'running' or self.thief is None:
            return False
        did = press(self.thief, port, self.setup)
        if did and port == GRAB:
            self.grabbing = True
        self._update_status()
        self._redraw()
        return did

    def grab(self) -> None:
        self.act(GRAB)

    def leave(self) -> None:
        self.act(LEAVE)

    def lunge(self) -> None:
        self.act(LUNGE)

    # --- the clock --------------------------------------------------------

    def update(self, dt: float) -> None:
        """One beat of the kitchen, on the clock rather than on a press.

        The round runs whether or not anybody acts, which is the point:
        a thief who could freeze the world while he thought would be
        answering a question nobody asked. Waiting is a real move here
        and it costs the same beat it costs a person.
        """
        now = self.clock()
        if self.phase == 'setting' and now >= self.until:
            self.phase = 'running'
            self.message = _('Go on, then')
            self._redraw()
        elif self.phase == 'running' and now >= self.beat_at:
            self.beat_at = now + self.beat_seconds
            was = self.thief.eaten
            beat(self.thief, self.setup)
            self._coach_verdict(self.thief.eaten - was)
            if over(self.thief, self.setup):
                self._settle()
                return
            self._update_status()
            self._redraw()
            # Cleared after the drawing rather than before it, so the
            # frame the beat produced still has his hand in the jar. The
            # next one does not, which is what makes it a snap.
            self.grabbing = False

    def _coach_verdict(self, gained: int) -> None:
        """Paint what the beat just past did, one beat at a time.

        Not the shaping the maze and the belt got: there is no potential
        here and nothing telescopes. It is the *haul* taken apart — a
        cookie he got away with is a piece of the green and a grab she
        had her eyes on is the red — so the sum over a round tracks
        :func:`~neural_workshop.cookiethief.haul` rather than the
        round's one bit, and a learner does not have to reach the end of
        a round to be told anything.

        Every safe cookie pays, including the ones past the quota,
        because that is the same rule the haul uses. Capped at the quota
        it would argue for stopping dead on the bar while the score on
        the screen argued for carrying more, and two objectives under
        one game is worse than either.

        It reads the jar, the pips, the door and the doorway. Never the
        trigger and never the deadline — those two are the whole of what
        the task hides, and a coach that knew when she was coming would
        have answered the only question it asks.
        """
        if not self.coach or self.thief is None:
            return
        thief = self.thief
        if thief.seen:
            self.verdict_shown = (False, _('She saw that'))
        elif gained:
            self.verdict_shown = (True, _('Got one'))
        else:
            self.verdict_shown = None
            self.verdict.clear()
            return
        self.verdict.show(*self.verdict_shown)

    # --- how it ends ------------------------------------------------------

    def _settle(self) -> None:
        """Score the round: enough cookies, and not one grab seen."""
        thief, grade = self.thief, self.setup.grade
        right = cleared(thief, self.setup)
        got = haul(thief)
        self.results.append((self.rung, right))
        self.cookies += thief.eaten
        self.points += got
        if thief.caught:
            self.message = _('Seen %d times, %d taken — %+d points'
                             ) % (thief.caught, thief.eaten, got)
        elif thief.eaten < grade.quota:
            self.message = _('Only %d of %d — %+d points'
                             ) % (thief.eaten, grade.quota, got)
        else:
            self.message = _('Away with %d — %+d points') % (thief.eaten, got)
        if self.adaptive:
            share = sum(1 for _r, ok in self.results[-4:] if ok) / float(
                min(4, len(self.results)))
            if share >= CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif share < DROP_BELOW:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'scored'
        self.until = self.clock() + VERDICT_SECONDS
        self.verdict_shown = (right, self.message)
        self.verdict.show(*self.verdict_shown)
        self._update_status()
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.setup = None
        self.thief = None
        self.message = _('%d of %d clean, %d points off %d cookies, highest '
                         'rung %d — guessing gets away clean about %d%% of '
                         'the time'
                         ) % (tally['clean'], tally['rounds'], tally['points'],
                              tally['cookies'], tally['best_rung'],
                              tally['floor'])
        self.asked.text = ''
        self._update_status()
        self._redraw()

    def score(self) -> Dict[str, int]:
        """How the run went, on both counts, and what guessing was worth.

        ``clean`` is the bar: rounds that met the quota with nothing
        seen. ``points`` is the haul, which is a different question — a
        cookie he got away with is worth one and a grab she saw costs
        two, so a bad round takes the total *down* rather than merely
        failing to add to it.

        The floor is reported beside them because a percentage means
        very little on its own, and it is *measured* rather than
        derived: there is nothing to derive here, since what a run of
        random presses is worth is whatever a random hand happens to
        take before the door is open far enough.
        """
        rounds = len(self.results)
        clean = sum(1 for _r, ok in self.results if ok)
        best = max((rung for rung, _ok in self.results), default=0)
        floors = [rehearse(rung) for rung, _ok in self.results]
        return {
            'rounds': rounds,
            'clean': clean,
            'cookies': self.cookies,
            'points': self.points,
            'accuracy': int(round(100.0 * clean / rounds)) if rounds else 0,
            'best_rung': best,
            'floor': int(round(100.0 * sum(floors) / len(floors)))
                     if floors else 0,
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

    def _disc(self, x, y, radius, colour, opacity=255):
        shape = pyglet.shapes.Circle(x, y, max(1.0, radius), color=colour,
                                     batch=self.batch)
        shape.opacity = opacity
        self.drawn.append(shape)
        return shape

    def _label(self, text, x, y, size=11):
        label = pyglet.text.Label(
            text, font_size=calc_fontsize(size), color=self.textcolor,
            batch=self.batch, x=x, y=y, anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.drawn.append(label)
        return label

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.setup is not None and self.phase in ('setting', 'running',
                                                     'scored'):
            self._draw_jar()
            self._draw_boy()
            self._draw_door()
            self._draw_pips()
        self._update_status()

    def _draw_jar(self) -> None:
        """The jar and what is left in it."""
        left, bottom, width, height = self._canvas()
        grade = self.setup.grade
        held = grade.room + 4
        wide = width * 0.13
        x = left + width * JAR_AT - wide / 2
        tall = height * 0.52
        base = bottom + height * 0.20
        self._rect(x, base, wide, tall, self.ink, opacity=30)
        for edge in ((x, base, max(2.0, wide * 0.06), tall),
                     (x + wide - max(2.0, wide * 0.06), base,
                      max(2.0, wide * 0.06), tall)):
            self._rect(*edge, self.ink, opacity=70)
        step = tall / float(max(1, held))
        radius = min(step * 0.42, wide * 0.19)
        for index in range(max(0, held - self.thief.jar)):
            row, column = divmod(index, 2)
            self._disc(x + wide * (0.3 + 0.4 * column),
                       base + step * (row + 0.6), radius, COOKIE)
        self._label(_('%d gone') % self.thief.jar, x + wide / 2,
                    base - height * 0.07)

    def _draw_boy(self) -> None:
        """The thief, standing at the jar with his hand over it.

        The arm is in the jar on the beat he took one and at his side on
        every other beat. It is the whole of the animation and it is
        deliberately the whole of it: there is no wind-up to watch and
        nothing to wait for, which is what makes a press feel like a
        press.
        """
        left, bottom, width, height = self._canvas()
        x = left + width * BOY_AT
        base = bottom + height * 0.22
        body = height * 0.30
        wide = width * 0.045
        self._rect(x - wide / 2, base, wide, body, self.ink, opacity=180)
        self._disc(x, base + body + wide * 0.55, wide * 0.55, self.ink,
                   opacity=180)
        jar_x = left + width * JAR_AT
        arm = max(2.0, height * 0.022)
        if self.grabbing or self.thief.committed:
            # Straight into the jar, on the frame the key was pressed.
            self._rect(jar_x, base + body * 0.80, x - jar_x, arm,
                       self.ink, opacity=220)
        else:
            # At his side: a short stub, so the difference between the
            # two reads at a glance rather than needing a comparison.
            self._rect(x - wide * 0.9, base + body * 0.42, wide * 0.9, arm,
                       self.ink, opacity=150)
        if self.thief.committed:
            self._label(_('reaching'), x, base + body + height * 0.10)
        if self.thief.gold_on_offer:
            self._draw_gold(x, base, height, width)

    def _draw_gold(self, x, base, height, width) -> None:
        """The golden one, on the counter, with the window running out."""
        gone = self.thief.beat - self.thief.gold_from
        share = max(0.0, 1.0 - gone / float(GOLD_BEATS))
        cx = x + width * 0.10
        cy = base + height * 0.30
        self._disc(cx, cy, min(width * 0.020, height * 0.055), GOLDEN)
        self._rect(cx - width * 0.03, cy - height * 0.09, width * 0.06,
                   max(3.0, height * 0.020), self.ink, opacity=40)
        self._rect(cx - width * 0.03, cy - height * 0.09, width * 0.06 * share,
                   max(3.0, height * 0.020), GOLDEN)

    def _draw_door(self) -> None:
        """The doorway, how far it is open, and whoever is in it.

        The opening is drawn in two weights. The solid part is the gap
        the missing cookies left and it never closes again; the light
        part on top of it is the noise a quick hand made, and that dies
        away on a quiet beat. The shaded strip near the far edge is the
        range she might be behind — a range and never a line, which is
        the whole of what the task hides.
        """
        left, bottom, width, height = self._canvas()
        thief, grade = self.thief, self.setup.grade
        wide = width * 0.20
        x = left + width * DOOR_AT - wide / 2
        base = bottom + height * 0.20
        tall = height * 0.58
        self._rect(x, base, wide, tall, self.ink, opacity=25)
        rail = max(2.0, wide * 0.05)
        for edge in ((x, base, rail, tall), (x + wide - rail, base, rail, tall),
                     (x, base + tall - rail, wide, rail)):
            self._rect(*edge, self.ink, opacity=90)
        # The opening, from the hinge on the left.
        limit = float(max(1, grade.limit))
        span = wide - 2 * rail
        low = floor_of(thief, grade)
        opened = door(thief, grade)
        self._rect(x + rail, base, span * min(1.0, low / limit), tall,
                   DOOR_INK, opacity=FLOOR_ALPHA)
        if opened > low:
            self._rect(x + rail + span * min(1.0, low / limit), base,
                       span * min(1.0, (opened - low) / limit), tall,
                       DOOR_INK, opacity=NOISE_ALPHA)
        # The range she might be in, marked on the frame above the door.
        zone = base + tall + max(3.0, height * 0.02)
        thick = max(3.0, height * 0.022)
        self._rect(x + rail, zone, span, thick, self.ink, opacity=35)
        self._rect(x + rail + span * (SAFE / limit), zone,
                   span * (1.0 - SAFE / limit), thick, DOOR_INK, opacity=150)
        nudge = span * min(1.0, opened / limit)
        self._rect(x + rail + nudge - max(1.0, span * 0.006), zone - thick,
                   max(2.0, span * 0.012), thick * 3, self.ink, opacity=220)
        self._label(_('one more would open it to %d of %d')
                    % (min(999, after_a_grab(thief, grade)), grade.limit),
                    x + wide / 2, base - height * 0.07)
        self._draw_figure(x, base, wide, tall, height)

    def _draw_figure(self, x, base, wide, tall, height) -> None:
        thief = self.thief
        if thief.phase not in (COMING, WATCHING) or thief.who is None:
            return
        colour, share, name = FIGURES[thief.who]
        looking = thief.phase == WATCHING
        figure = tall * 0.62 * share
        body = wide * 0.30
        cx = x + wide / 2 - (wide * 0.55 if looking else 0.0)
        self._rect(cx - body / 2, base, body, figure, colour,
                   opacity=255 if looking else 170)
        self._disc(cx, base + figure + body * 0.4, body * 0.4, colour,
                   opacity=255 if looking else 170)
        if looking:
            for side in (-1, 1):
                self._disc(cx + side * body * 0.16,
                           base + figure + body * 0.45, body * 0.09,
                           self.background)
        self._label(_('%s is looking') % name if looking else name,
                    x + wide / 2, base + tall + height * 0.10)

    def _draw_pips(self) -> None:
        """What he has, against what the round asked for.

        The ones past the quota are drawn too, and in the golden colour,
        because they are worth the same point each and are the whole of
        the reason to still be standing there.
        """
        left, bottom, width, height = self._canvas()
        grade = self.setup.grade
        wanted = grade.quota
        shown = max(wanted, min(self.thief.eaten, grade.room + 6))
        step = min(width * 0.026, width * 0.62 / max(1, shown))
        radius = step * 0.32
        start = left + width * 0.20
        y = bottom + height * 0.95
        for index in range(shown):
            got = index < self.thief.eaten
            spare = index >= wanted
            self._disc(start + step * index, y, radius,
                       (GOLDEN if spare else COOKIE) if got else self.ink,
                       opacity=255 if got else 45)

    def _update_status(self) -> None:
        if self.setup is None or self.thief is None:
            self.status.text = self.message
            return
        self.status.text = _('Round %d of %d     %d taken     %s'
                             ) % (self.trial, self.total_trials,
                                  self.thief.eaten, self.message)

    # --- housekeeping -----------------------------------------------------

    def close(self) -> None:
        if CookieThief.instance is not self:
            return
        self._clear_drawn()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        CookieThief.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='self_control')

    # --- events -----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'scored' and self.clock() >= self.until:
                self._next_trial()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in (key.X, key.UP):
            self.grab()
        elif symbol in (key.Z, key.DOWN):
            self.leave()
        elif symbol in (key.G, key.RIGHT):
            self.lunge()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['BEAT_SECONDS', 'CookieThief', 'SET_SECONDS']
