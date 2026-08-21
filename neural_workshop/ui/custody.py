# -*- coding: utf-8 -*-
"""Chain of Custody: deliver the box that was ringed, in the state asked for.

A carousel of boxes runs round a belt. One of them is ringed for a
moment at the start — that is the Core — and then the ring goes and it
looks like the rest. Move the claw round the ring, pick the Core up,
put it through whatever machines the round asks for, and set it down in
the bay.

**The board is drawn as a loop and it is one.** The top row runs right
and the bottom row runs back left, and slot numbers go round: past the
end of the top row is the start of the bottom. The claw travels the
same ring, so left and right are along the belt rather than across the
screen — which reads oddly for the first few seconds and then stops
mattering, because everything on this board lives at a slot.

**A claw cannot chase a box.** Both move one slot a step, so the way to
pick something up is to stand still and let the ring bring it to you.
That is the task's first real lesson and it is deliberately not
signposted.

Everything drawn here is everything there is, with one exception: which
box is the Core. The charge bar, the heat tint, the machines and the
bay are all on screen, which is what lets coach mode shape the routing
without giving the identity away — see
:func:`neural_workshop.custody.potential`.

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
from ..custody import (CHARGER, COOLER, GRADES, PAINTER, Box, Layout,
                       core_of, fresh_boxes, generate, grab, machine_at,
                       potential, put_down, step_belt, wanted)
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Okabe-Ito, as everywhere else in the workshop. Two coats is what the
#: ladder deals; the rest are here so a wider deal stays legible.
COATS: Tuple[Tuple[int, int, int], ...] = (
    (0, 114, 178),          # blue
    (240, 228, 66),         # yellow
    (0, 158, 115),          # green
    (204, 121, 167),        # reddish purple
)

#: The machines, and the colour each is drawn in. Deliberately not the
#: coat colours: a machine is furniture and must never read as a box.
MACHINE_INK: Dict[str, Tuple[int, int, int]] = {
    CHARGER: (230, 159, 0),         # orange
    COOLER: (86, 180, 233),         # sky blue
    PAINTER: (150, 150, 150),       # grey
}

MACHINE_WORD: Dict[str, str] = {
    CHARGER: _('charge'), COOLER: _('cool'), PAINTER: _('paint'),
}

#: Where the two runs of the loop sit in the canvas, as shares of its
#: height. Named because the belt, the boxes, the machines, the claw
#: and the bay all have to agree about them, and they did not: the
#: claw's arm reached far enough above the top row to be drawn over
#: the line of text saying what the round wanted.
TOP_ROW, BOTTOM_ROW = 0.76, 0.34

#: A slot's box, as a share of the space between slot centres and of
#: the canvas height. Under a slot's width, because a machine is drawn
#: wider than the box it holds and has to stay inside its own slot —
#: at 0.78 the machines overlapped their neighbours and there was no
#: telling which slot one was in.
SLOT_SHARE, ROW_SHARE = 0.72, 0.22

#: How long a belt step takes. The same number serves a person at sixty
#: frames a second and an agent stepping a virtual clock at the same
#: rate, so neither is playing a different game.
BELT_SECONDS = 0.40

#: How long the Core is ringed at the start of a round.
MARK_SECONDS = 1.6

#: How long a verdict stays up before the next round can be called.
VERDICT_SECONDS = 1.0

#: Deliver this share of a run's rounds right and an adaptive run
#: climbs; fewer than this and it drops. A round is all or nothing, so
#: the two marks are close together.
CLIMB_AT, DROP_BELOW = 0.75, 0.4


class ChainOfCustody:
    """The carousel, the claw and the bay. Esc returns to the hub."""

    instance: Optional['ChainOfCustody'] = None

    def __init__(self) -> None:
        if ChainOfCustody.instance is not None:
            ChainOfCustody.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        #: Coach mode: paint a consequence verdict after every claw move
        #: that carried the held box nearer or further from where it
        #: next has to be. Off for people — it changes the game — and
        #: switched on by the agent boundary, where it is potential-based
        #: shaping: one move changes the distance by exactly one, so
        #: green/red is the term d - d' and any closed loop of moves
        #: sums to zero. It is blind to which box is the Core.
        self.coach = False
        self.layout: Optional[Layout] = None
        self.boxes: List[Box] = []
        self.held: Optional[Box] = None
        self.claw = 0
        self.spent = 0
        self.until = 0.0
        self.belt_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, bool]] = []       # (rung, delivered ok)
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
        ChainOfCustody.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.CUSTODY)
        self.start_rung = int(opts['CUSTODY_LEVEL'])
        self.total_trials = int(opts['CUSTODY_TRIALS'])
        self.belt_seconds = float(opts['CUSTODY_BELT_SECONDS'])
        self.mark_seconds = float(opts['CUSTODY_MARK_SECONDS'])
        self.adaptive = bool(opts['CUSTODY_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('chain_of_custody',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        """Create the batch, the colours and the fixed labels."""
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.ink = (fg, fg, fg)
        self.muted = (fg, fg, fg, 130)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Chain of Custody'), font_size=calc_fontsize(22),
            weight='bold', color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.asked = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(98),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     arrows: move the claw'
              '     Z: pick up / put down     C: options'),
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
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        # Refilled here for the same reason the verdict is put back: a
        # resize rebuilds the chrome mid-round, and a round whose
        # standing requirement had quietly gone blank would be asking
        # for something the screen no longer said.
        self._update_asked()
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _canvas(self) -> Tuple[float, float, float, float]:
        """Where the carousel lives: left, bottom, width, height.

        Held clear of the band the agent boundary reads. The boxes are
        drawn in saturated coats and the machines in orange and sky
        blue, every one of which would be counted as a verdict down
        there.
        """
        window = state.window
        top = from_top_edge(130)
        bottom = above_the_band(from_bottom_edge(76))
        return (window.width * 0.07, bottom,
                window.width * 0.86, max(60.0, top - bottom))

    def _slot_rect(self, slot: int) -> Tuple[float, float, float]:
        """Middle and side of one slot's square on screen.

        The ring is drawn as two rows: the first *width* slots run left
        to right along the top, and the rest run right to left along
        the bottom, so slot and slot+1 are always neighbours on screen
        as well as on the belt.
        """
        left, bottom, width, height = self._canvas()
        span = self.layout.width if self.layout is not None else 1
        step = width / span
        side = min(step * SLOT_SHARE, height * ROW_SHARE)
        row, along = divmod(slot, span)
        if row:
            along = span - 1 - along
        x = left + (along + 0.5) * step
        y = bottom + height * (BOTTOM_ROW if row else TOP_ROW)
        return x, y, side

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.layout = None
        self.boxes = []
        self.held = None
        self.claw = 0
        self.spent = 0
        self.trial = 0
        self.results = []
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
        self.layout = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self.boxes = fresh_boxes(self.layout, self.rng)
        self.held = None
        self.claw = 0
        self.spent = 0
        self.phase = 'marking'
        self.until = self.clock() + self.mark_seconds
        self.belt_at = self.clock() + self.belt_seconds
        self.message = _('This one')
        self._update_asked()
        self._redraw()

    def _update_asked(self) -> None:
        """The standing requirement, said in words above the belt."""
        if self.layout is None:
            self.asked.text = ''
            return
        wants = [_('rung %d, %s:') % (self.rung, _(GRADES[self.rung - 1].name)),
                 _('deliver the ringed box to the bay')]
        if self.layout.need_charge:
            wants.append(_('charged to %d') % self.layout.need_charge)
        if self.layout.max_heat < 100:
            wants.append(_('under %d heat') % self.layout.max_heat)
        self.asked.text = '   '.join(wants)

    # --- what the player does --------------------------------------------

    def move(self, step: int) -> None:
        """Slide the claw one slot round the ring."""
        if self.phase != 'running':
            return
        before = potential(self.held, self.claw, self.layout)
        self.claw = (self.claw + step) % self.layout.slots
        if self.held is not None:
            self.held.slot = self.claw
        after = potential(self.held, self.claw, self.layout)
        self._coach_verdict(None if before is None or after is None
                            else after - before)
        self._update_status()
        self._redraw()

    def take_or_place(self) -> None:
        """One key for both, because the claw is only ever in one state."""
        if self.phase != 'running':
            return
        # Neither picking up nor putting down is a step toward anything,
        # so both clear the coach label rather than paying it. Were a
        # grab to pay, grabbing and dropping on the spot would farm
        # reward forever and the shaping would stop telescoping.
        self._coach_verdict(None)
        if self.held is None:
            self.held = grab(self.boxes, self.claw)
            self.message = (_('Picked it up') if self.held is not None
                            else _('Nothing there'))
        elif put_down(self.held, self.boxes, self.claw, self.layout):
            done = self.held
            self.held = None
            if done.delivered:
                self._settle(done)
                return
            kind = machine_at(self.layout, self.claw)
            self.message = (_('Into the %s') % MACHINE_WORD[kind]
                            if kind is not None else _('Put down'))
        else:
            self.message = _('That slot is taken')
        self._update_status()
        self._redraw()

    def _coach_verdict(self, delta: Optional[int]) -> None:
        """Paint what the move just made did to the held box's journey.

        Still a verdict and not a directive: it reports the consequence
        of the action already taken, never which action to take next.
        ``None`` — an empty claw, a pick-up, a put-down — clears the
        label, because those change no distance and must read as scalar
        zero or the shaping stops telescoping.
        """
        if not self.coach:
            return
        if delta is None or delta == 0:
            self.verdict_shown = None
            self.verdict.clear()
            return
        closer = delta < 0
        self.verdict_shown = (closer, _('Warmer') if closer else _('Colder'))
        self.verdict.show(*self.verdict_shown)

    # --- how it ends ------------------------------------------------------

    def _settle(self, delivered: Optional[Box]) -> None:
        """Score the round: the right box, in the right state, or not."""
        core = core_of(self.boxes, self.layout)
        right = (delivered is not None and delivered is core
                 and wanted(delivered, self.layout))
        self.results.append((self.rung, right))
        if delivered is None:
            self.message = _('Out of actions')
        elif delivered is not core:
            self.message = _('That was not the one')
        elif not wanted(delivered, self.layout):
            self.message = (_('The right box, but %d charge and %d heat')
                            % (delivered.charge, delivered.heat))
        else:
            self.message = _('Delivered, in %d actions') % self.spent
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
        self.layout = None
        self.boxes = []
        self.held = None
        tally = self.score()
        self.message = _('%d of %d delivered, highest rung %d — guessing '
                         'would have scored about %d%%'
                         ) % (tally['delivered'], tally['rounds'],
                              tally['best_rung'], tally['floor'])
        self.asked.text = ''
        self._update_status()
        self._redraw()

    def score(self) -> Dict[str, int]:
        """How the run went, against what guessing would have paid.

        The floor is reported beside the score because on its own the
        percentage means very little here: a run at rung three is
        guessing one in two and a half, and one at rung ten one in six,
        so the same percentage is a different achievement.
        """
        rounds = len(self.results)
        best = max((rung for rung, _ok in self.results), default=0)
        floors = [1.0 / GRADES[rung - 1].rivals for rung, _ok in self.results]
        return {
            'rounds': rounds,
            'delivered': sum(1 for _r, ok in self.results if ok),
            'accuracy': int(round(100.0 * sum(1 for _r, ok in self.results
                                              if ok) / rounds)) if rounds
                        else 0,
            'best_rung': best,
            'floor': int(round(100.0 * sum(floors) / len(floors)))
                     if floors else 0,
        }

    # --- the clock --------------------------------------------------------

    def update(self, dt: float) -> None:
        """One beat of the round: the belt moves, and the clock runs down.

        **The budget is spent here rather than on each action**, so it
        is a clock rather than an allowance. That is what makes it the
        same round for a person and for an agent: a person waits by not
        pressing anything and it costs them the time it costs, and an
        agent spends an action to let a beat pass and it costs the same
        beat. Charged per action instead, waiting would have been free
        for one of them and not the other, and the two would have been
        playing different games under one set of numbers.

        A still belt still runs the clock: the first two rungs have
        nothing moving on them, and a round there would otherwise have
        no end at all.
        """
        now = self.clock()
        if self.phase == 'marking' and now >= self.until:
            self.phase = 'running'
            self.message = _('Which one was it?')
            self._redraw()
        elif self.phase == 'running' and now >= self.belt_at:
            self.belt_at = now + self.belt_seconds
            self.spent += 1
            step_belt(self.boxes, self.layout)
            if self.spent >= self.layout.budget:
                self._settle(None)
                return
            self._update_status()
            self._redraw()

    # --- drawing ----------------------------------------------------------

    def _clear_drawn(self) -> None:
        for shape in self.drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.drawn = []

    def _rect(self, x, y, wide, tall, colour, opacity=255):
        shape = pyglet.shapes.Rectangle(x, y, wide, tall, color=colour,
                                        batch=self.batch)
        shape.opacity = opacity
        self.drawn.append(shape)
        return shape

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.layout is not None and self.phase in ('marking', 'running',
                                                      'scored'):
            self._draw_belt()
            self._draw_machines()
            self._draw_bay()
            for box in self.boxes:
                if not box.delivered:
                    self._draw_box(box)
            self._draw_claw()
            self._draw_budget()
        self._update_status()

    def _draw_belt(self) -> None:
        """The two runs of the loop, and the ends that join them."""
        left, bottom, width, height = self._canvas()
        rail = max(2.0, height * 0.012)
        for share in (BOTTOM_ROW, TOP_ROW):
            self._rect(left, bottom + height * share - rail / 2,
                       width, rail, self.ink, opacity=70)
        for side in (left, left + width - rail):
            self._rect(side, bottom + height * BOTTOM_ROW, rail,
                       height * (TOP_ROW - BOTTOM_ROW), self.ink, opacity=70)

    def _draw_machines(self) -> None:
        for machine in self.layout.machines:
            x, y, side = self._slot_rect(machine.slot)
            colour = MACHINE_INK[machine.kind]
            self._rect(x - side * 0.62, y - side * 0.72,
                       side * 1.24, side * 1.44, colour, opacity=60)
            edge = max(2.0, side * 0.07)
            for rect in ((x - side * 0.62, y - side * 0.72, side * 1.24, edge),
                         (x - side * 0.62, y + side * 0.72 - edge,
                          side * 1.24, edge)):
                self._rect(*rect, colour)
            label = pyglet.text.Label(
                MACHINE_WORD[machine.kind], font_size=calc_fontsize(9),
                color=self.textcolor, batch=self.batch, x=x,
                y=y + side * 0.95, anchor_x='center', anchor_y='center',
                font_name=FONTLIST)
            self.drawn.append(label)

    def _draw_bay(self) -> None:
        """The chute under the bottom row. Nothing else is ever there.

        No box is ever dealt into the bay's slot and putting one down
        there delivers it, so the column is the bay's alone and the
        chute can hang below the belt without anything to collide
        with.
        """
        x, y, side = self._slot_rect(self.layout.bay)
        below = y - side * 1.15
        tall = side * 0.8
        self._rect(x - side * 0.7, below, side * 1.4, tall,
                   self.ink, opacity=45)
        label = pyglet.text.Label(
            # Under the chute rather than in it: the claw reaches down
            # into the bay to deliver, and its crossbar was landing
            # squarely on the word.
            _('bay'), font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=x, y=below - side * 0.22,
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.drawn.append(label)

    def _draw_box(self, box: Box) -> None:
        x, y, side = self._slot_rect(box.slot)
        if box.held:
            # Lifted towards the outside of the loop, which is up on
            # the top run and down on the bottom one — the same side
            # the claw reaches in from, so a held box reads as held
            # rather than as one sitting next to the arm.
            y += side * 0.55 * (1 if box.slot < self.layout.width else -1)
        coat = COATS[box.look % len(COATS)]
        self._rect(x - side * 0.4, y - side * 0.4, side * 0.8, side * 0.8,
                   coat)
        if self.layout.need_charge:
            self._draw_charge(box, x, y, side)
        if self.layout.max_heat < 100 and box.heat:
            # Heat as a rim rather than a tint, so it never changes what
            # coat the box reads as — the coat is the thing a player is
            # trying to follow and it must not be muddied by state.
            hot = max(2.0, side * 0.09)
            self._rect(x - side * 0.4, y + side * 0.4 - hot, side * 0.8, hot,
                       (213, 94, 0),
                       opacity=int(60 + 195 * min(1.0, box.heat / 100.0)))
        if self.phase == 'marking' and box.latent == self.layout.core:
            self._draw_ring(x, y, side)

    def _draw_charge(self, box: Box, x: float, y: float, side: float) -> None:
        wide, tall = side * 0.8, max(2.0, side * 0.12)
        base = y - side * 0.62
        self._rect(x - wide / 2, base, wide, tall, self.ink, opacity=50)
        share = min(1.0, box.charge / 100.0)
        if share:
            enough = box.charge >= self.layout.need_charge
            self._rect(x - wide / 2, base, wide * share, tall,
                       (0, 158, 115) if enough else (150, 150, 150))

    def _draw_ring(self, x: float, y: float, side: float) -> None:
        """The one moment the Core is told apart from the rest."""
        ring = pyglet.shapes.Arc(x, y, side * 0.72, color=self.ink,
                                 thickness=max(2.0, side * 0.09),
                                 batch=self.batch)
        self.drawn.append(ring)

    def _draw_claw(self) -> None:
        """The arm, reaching in from outside whichever run it is on.

        Kept to under a slot's height. It used to reach further, and
        on the top row that put its crossbar straight through the line
        of text saying what the round wanted.
        """
        x, y, side = self._slot_rect(self.claw)
        arm = max(2.0, side * 0.1)
        reach = side * (0.85 if self.claw < self.layout.width else -0.85)
        self._rect(x - arm / 2, min(y, y + reach), arm, abs(reach),
                   self.ink, opacity=150)
        self._rect(x - side * 0.52, y + reach - (arm if reach > 0 else 0),
                   side * 1.04, arm, self.ink)

    def _draw_budget(self) -> None:
        """Actions left, as a bar as well as a number.

        A bar because the number alone is read too late: what a player
        needs is to notice the room running out while there is still
        room, which is a length rather than a digit.
        """
        left, bottom, width, _height = self._canvas()
        tall = max(3.0, width * 0.006)
        base = bottom - tall * 4
        share = max(0.0, 1.0 - self.spent / float(self.layout.budget))
        self._rect(left, base, width, tall, self.ink, opacity=45)
        if share:
            self._rect(left, base, width * share, tall, self.ink,
                       opacity=170)

    def _update_status(self) -> None:
        if self.layout is None:
            self.status.text = self.message
            return
        # The rung and what it wants live on the line below, so this one
        # stays short enough to fit: with both on it the ends ran off
        # either side of the window.
        self.status.text = _('Round %d of %d     %d actions left     %s'
                             ) % (self.trial, self.total_trials,
                                  max(0, self.layout.budget - self.spent),
                                  self.message)

    # --- housekeeping -----------------------------------------------------

    def close(self) -> None:
        if ChainOfCustody.instance is not self:
            return
        self._clear_drawn()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        ChainOfCustody.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='working_memory')

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
        elif symbol in (key.LEFT, key.A):
            self.move(-1)
        elif symbol in (key.RIGHT, key.D):
            self.move(1)
        elif symbol in (key.Z, key.DOWN, key.UP):
            self.take_or_place()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['BELT_SECONDS', 'COATS', 'MARK_SECONDS', 'ChainOfCustody']
