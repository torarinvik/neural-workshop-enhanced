# -*- coding: utf-8 -*-
"""Cookie Thief: take what the round asks for, and be still before she looks.

A boy, a jar and a doorway. Reaching makes him faster and he eats
whatever his speed came to that beat, so the cookies come quicker the
longer he keeps at it — and the same number that is earning him cookies
is the number of beats it will take him to stop.

**The stop is the whole task.** Mother comes when the jar is down far
enough, or when she was going to anyway, and there is a warning of a
few beats before her eyes are actually on him. Up to the fifth rung
that warning is longer than his stopping distance and the round can be
played by watching the doorway. After it, never again: by the time
there is anything to react to it is already too late, and the only
defence left is not having been going that fast.

**Stopping is committing.** Stand still for three beats with something
already taken and he sneaks off, and the round is scored where he left
it. That is what makes stopping a decision rather than a pause.

Everything the round turns on is drawn. The jar shows how far down it
is and shades the depth at which she starts noticing; the bar under the
boy is his speed; the row of pips is what he has got against what was
asked. The two things that are not drawn are the two that are meant to
be hidden: which cookie inside that shaded band is the one that brings
her, and the beat she was going to come anyway.

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
from ..cookiethief import (COMING, DOG, FREEZE, GOLD_BEATS, GRADES, LUNGE,
                           MOTHER, REACH, SISTER, WATCHING, Thief, beat,
                           cleared, generate, over, press, rehearse,
                           stopping_bites)
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Okabe-Ito. The cookie is orange and the golden one is yellow, which
#: are the two that read as the same object in different states.
COOKIE = (230, 159, 0)
GOLDEN = (240, 228, 66)
SPEED_INK = (86, 180, 233)

#: Who might be in the doorway, and how they are drawn. The height is
#: what tells them apart at a glance, because on the top rungs there is
#: exactly one beat to do it in and a colour read alone is a colour read
#: too slowly.
FIGURES: Dict[str, Tuple[Tuple[int, int, int], float, str]] = {
    MOTHER: ((204, 121, 167), 1.00, _('Mother')),
    SISTER: ((0, 114, 178), 0.62, _('your sister')),
    DOG: ((0, 158, 115), 0.28, _('the dog')),
}

#: Where the three things live across the canvas, as shares of its width.
JAR_AT, BOY_AT, DOOR_AT = 0.14, 0.50, 0.85

#: How long a beat takes. The same number serves a person at sixty
#: frames a second and an agent stepping a virtual clock, so neither is
#: playing a different game.
BEAT_SECONDS = 0.35

#: How long the round sits still before the first beat, so the quota can
#: be read.
SET_SECONDS = 0.9

#: How long a verdict stays up before the next round can be called.
VERDICT_SECONDS = 1.2

#: Clear this share of the last four rounds and an adaptive run climbs;
#: fewer than this and it drops.
CLIMB_AT, DROP_BELOW = 0.75, 0.4


class CookieThief:
    """The jar, the boy and the doorway. Esc returns to the hub."""

    instance: Optional['CookieThief'] = None

    def __init__(self) -> None:
        if CookieThief.instance is not None:
            CookieThief.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        #: Coach mode: paint a verdict on the beat a cookie lands and on
        #: the beats her eyes are on a boy who has not stopped. Off for
        #: people — it changes the game — and switched on by the agent
        #: boundary. It is blind to the trigger and to the deadline: see
        #: the wrapper's docstring for why that matters.
        self.coach = False
        self.setup = None
        self.thief: Optional[Thief] = None
        self.trial = 0
        self.results: List[Tuple[int, bool]] = []       # (rung, cleared)
        self.cookies = 0
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
            _('Esc: menu   Space: start   X: reach   Z: stop'
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
                 _('Take %d, and be still before she looks.') % grade.quota]
        if not grade.reactive:
            wants.append(_('She is quicker than you can stop.'))
        if grade.gold:
            wants.append(_('The golden one is worth %d.') % grade.gold)
        if grade.decoys:
            wants.append(_('Not everyone at the door is her.'))
        self.asked.text = ' '.join(wants)

    # --- what the player does --------------------------------------------

    def act(self, port: int) -> bool:
        """One press. The beat that follows it is the clock's business."""
        if self.phase != 'running' or self.thief is None:
            return False
        return press(self.thief, port, self.setup)

    def reach(self) -> None:
        self.act(REACH)

    def freeze(self) -> None:
        self.act(FREEZE)

    def lunge(self) -> None:
        self.act(LUNGE)

    # --- the clock --------------------------------------------------------

    def update(self, dt: float) -> None:
        """One beat of the kitchen, on the clock rather than on a press.

        The round runs whether or not anybody acts, which is the point:
        a thief who could freeze the world while he thought would be
        answering a question nobody asked. Standing still is a real move
        here and it costs the same beat it costs a person.
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

    def _coach_verdict(self, gained: int) -> None:
        """Paint what the beat just past did, one beat at a time.

        Not the shaping the maze and the belt got: there is no potential
        here and nothing telescopes. It is the round's own verdict taken
        apart — a cookie the round asked for is a piece of the green,
        and a cookie taken under her eye is the whole of the red — so
        the sum over a round orders policies the same way the round's
        one scalar does, and it does it without a learner having to
        reach the end of a round first.

        The beats she is looking pay red as soon as the outcome is
        settled rather than when it lands, because
        :func:`~neural_workshop.cookiethief.stopping_bites` already
        knows: a boy still carrying a cookie's worth of momentum with
        her eyes on him has been caught, and saying so a beat early is
        the same fact sooner.

        It reads the jar, the pips, the boy's speed and the doorway.
        Never :attr:`Setup.trigger` and never :attr:`Setup.deadline` —
        those are the two hidden things, and a coach that knew them
        would have answered the question the task asks.
        """
        if not self.coach or self.thief is None:
            return
        thief, grade = self.thief, self.setup.grade
        if thief.phase == WATCHING and (
                thief.took or stopping_bites(thief.speed, thief.crumbs,
                                             grade, thief.locked)):
            self.verdict_shown = (False, _('She can see you'))
        elif gained and thief.eaten <= grade.quota:
            self.verdict_shown = (True, _('Got one'))
        else:
            self.verdict_shown = None
            self.verdict.clear()
            return
        self.verdict.show(*self.verdict_shown)

    # --- how it ends ------------------------------------------------------

    def _settle(self) -> None:
        """Score the round: enough cookies, and not one of them seen."""
        thief, grade = self.thief, self.setup.grade
        right = cleared(thief, self.setup)
        self.results.append((self.rung, right))
        self.cookies += thief.eaten
        if thief.caught:
            self.message = _('Caught with %d') % thief.caught
        elif thief.eaten < grade.quota:
            self.message = _('Only %d of %d') % (thief.eaten, grade.quota)
        else:
            self.message = _('Away with %d') % thief.eaten
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
        self.message = _('%d of %d clean, %d cookies, highest rung %d — '
                         'guessing would have scored about %d%%'
                         ) % (tally['clean'], tally['rounds'],
                              tally['cookies'], tally['best_rung'],
                              tally['floor'])
        self.asked.text = ''
        self._update_status()
        self._redraw()

    def score(self) -> Dict[str, int]:
        """How the run went, against what guessing would have paid.

        The floor is reported beside the score because the percentage
        means very little without it, and it is *measured* rather than
        derived: there is nothing to derive here, since what a run of
        random presses is worth is whatever a random walk in speed
        happens to eat before somebody walks in.
        """
        rounds = len(self.results)
        clean = sum(1 for _r, ok in self.results if ok)
        best = max((rung for rung, _ok in self.results), default=0)
        floors = [rehearse(rung) for rung, _ok in self.results]
        return {
            'rounds': rounds,
            'clean': clean,
            'cookies': self.cookies,
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
        """The jar, what is gone from it, and the depth she notices at.

        The band is a band and never a line, which is the whole of the
        partial observability: a thief can see that he is into the
        range where she might come and cannot see which cookie inside it
        is the one that brings her.
        """
        left, bottom, width, height = self._canvas()
        grade = self.setup.grade
        held = grade.quota + grade.spread + 3
        wide = width * 0.16
        x = left + width * JAR_AT - wide / 2
        tall = height * 0.66
        base = bottom + height * 0.16
        self._rect(x, base, wide, tall, self.ink, opacity=35)
        step = tall / float(held)
        # The band, drawn from the depth the count could first bring her
        # to the depth it certainly does. Wider than the jar on purpose:
        # drawn inside it the cookies still in the way cover the very
        # thing a thief is trying to see the surface coming down to.
        low = base + tall - step * (grade.quota + grade.spread)
        self._rect(x - wide * 0.18, low, wide * 1.36, step * grade.spread,
                   (213, 94, 0), opacity=70)
        radius = min(step * 0.42, wide * 0.17)
        for index in range(held - self.thief.jar):
            row, column = divmod(index, 2)
            self._disc(x + wide * (0.3 + 0.4 * column),
                       base + step * (row + 0.5), radius, COOKIE)
        label = pyglet.text.Label(
            _('%d gone') % self.thief.jar, font_size=calc_fontsize(11),
            color=self.textcolor, batch=self.batch, x=x + wide / 2,
            y=base - height * 0.07, anchor_x='center', anchor_y='center',
            font_name=FONTLIST)
        self.drawn.append(label)

    def _draw_boy(self) -> None:
        """The thief, his arm, and the speed the arm is going at.

        The bar is the one number a player has to read off him, so it is
        a length rather than a figure: what matters is noticing the
        momentum while there is still room to spend it, and that is not
        something a digit gets across in time.
        """
        left, bottom, width, height = self._canvas()
        thief, grade = self.thief, self.setup.grade
        x = left + width * BOY_AT
        base = bottom + height * 0.20
        body = height * 0.30
        wide = width * 0.05
        self._rect(x - wide / 2, base, wide, body, self.ink, opacity=180)
        self._disc(x, base + body + wide * 0.5, wide * 0.5, self.ink,
                   opacity=180)
        # The arm reaches back towards the jar as he speeds up, so speed
        # is legible from the figure as well as from the bar.
        reach = (x - left - width * JAR_AT) * thief.speed
        self._rect(x - reach, base + body * 0.72, max(2.0, reach),
                   max(2.0, height * 0.022), self.ink, opacity=200)
        if thief.locked:
            # Both feet off the ground: there is no brake for a beat or
            # two, and a player who cannot see that cannot plan round it.
            self._rect(x - wide, base + body * 0.62, wide * 2,
                       height * 0.05, GOLDEN, opacity=110)
        bar_w = width * 0.20
        bar_y = base - height * 0.10
        tall = max(4.0, height * 0.035)
        self._rect(x - bar_w / 2, bar_y, bar_w, tall, self.ink, opacity=40)
        self._rect(x - bar_w / 2, bar_y, bar_w * thief.speed, tall, SPEED_INK)
        # How far the momentum still has to run, in cookies, which is
        # the number the stop has to be planned against.
        left_to_go = stopping_bites(thief.speed, thief.crumbs, grade,
                                    thief.locked)
        label = pyglet.text.Label(
            _('%d more if he stops now') % left_to_go,
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=x, y=bar_y - height * 0.07,
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.drawn.append(label)
        if self.thief.gold_on_offer:
            self._draw_gold(x, base, height, width)

    def _draw_gold(self, x, base, height, width) -> None:
        """The golden one, on the counter, with the window running out."""
        gone = self.thief.beat - self.thief.gold_from
        share = max(0.0, 1.0 - gone / float(GOLD_BEATS))
        cx = x + width * 0.11
        cy = base + height * 0.44
        self._disc(cx, cy, min(width * 0.022, height * 0.06), GOLDEN)
        self._rect(cx - width * 0.03, cy - height * 0.10, width * 0.06,
                   max(3.0, height * 0.022), self.ink, opacity=40)
        self._rect(cx - width * 0.03, cy - height * 0.10, width * 0.06 * share,
                   max(3.0, height * 0.022), GOLDEN)

    def _draw_door(self) -> None:
        """The doorway, and whoever is standing in it.

        Height tells them apart, not colour. On the top rungs there is
        one beat to read the figure in, and one beat is not long enough
        to name a colour — but it is long enough to see that whatever is
        in the door only comes up to your knee.
        """
        left, bottom, width, height = self._canvas()
        thief = self.thief
        wide = width * 0.15
        x = left + width * DOOR_AT - wide / 2
        base = bottom + height * 0.20
        tall = height * 0.62
        self._rect(x, base, wide, tall, self.ink, opacity=30)
        for edge in ((x, base, max(2.0, wide * 0.06), tall),
                     (x + wide - max(2.0, wide * 0.06), base,
                      max(2.0, wide * 0.06), tall),
                     (x, base + tall - max(2.0, wide * 0.06), wide,
                      max(2.0, wide * 0.06))):
            self._rect(*edge, self.ink, opacity=90)
        if thief.phase not in (COMING, WATCHING) or thief.who is None:
            return
        colour, share, name = FIGURES[thief.who]
        looking = thief.phase == WATCHING
        figure = tall * 0.66 * share
        body = wide * 0.42
        # She steps out of the doorway when she is actually looking, so
        # "in the door" and "in the room" are different pictures rather
        # than the same picture in two shades.
        cx = x + wide / 2 - (wide * 0.5 if looking else 0.0)
        self._rect(cx - body / 2, base, body, figure, colour,
                   opacity=255 if looking else 170)
        self._disc(cx, base + figure + body * 0.4, body * 0.4, colour,
                   opacity=255 if looking else 170)
        if looking:
            for side in (-1, 1):
                self._disc(cx + side * body * 0.16,
                           base + figure + body * 0.45, body * 0.09,
                           self.background)
        label = pyglet.text.Label(
            name if not looking else _('%s is looking') % name,
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=x + wide / 2, y=base + tall + height * 0.06,
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.drawn.append(label)

    def _draw_pips(self) -> None:
        """What he has got, against what the round asked for."""
        left, bottom, width, height = self._canvas()
        grade = self.setup.grade
        wanted = grade.quota
        step = min(width * 0.035, width * 0.5 / max(1, wanted))
        radius = step * 0.34
        start = left + width * 0.30
        y = bottom + height * 0.94
        for index in range(wanted):
            got = index < self.thief.eaten
            self._disc(start + step * index, y, radius,
                       COOKIE if got else self.ink,
                       opacity=255 if got else 45)
        spare = self.thief.eaten - wanted
        if spare > 0:
            label = pyglet.text.Label(
                _('+%d') % spare, font_size=calc_fontsize(11),
                color=self.textcolor, batch=self.batch,
                x=start + step * wanted + radius * 2, y=y,
                anchor_x='left', anchor_y='center', font_name=FONTLIST)
            self.drawn.append(label)

    def _update_status(self) -> None:
        if self.setup is None or self.thief is None:
            self.status.text = self.message
            return
        self.status.text = _('Round %d of %d     beat %d     %s'
                             ) % (self.trial, self.total_trials,
                                  self.thief.beat, self.message)

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
            self.reach()
        elif symbol in (key.Z, key.DOWN):
            self.freeze()
        elif symbol in (key.G, key.RIGHT):
            self.lunge()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['BEAT_SECONDS', 'CookieThief', 'SET_SECONDS']
