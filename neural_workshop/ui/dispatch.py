# -*- coding: utf-8 -*-
"""Dispatch: send crews to incidents while the town keeps happening.

A map, three stations, a few crews and — from rung four — a scout.
Incidents appear as discs that grow; when a disc fills its ring the
incident is lost. Click a crew, then click where it should go. A crew
at an incident shrinks it until it is gone. Any crew can be sent
somewhere else at any moment, and what it leaves unfinished starts
growing again.

An unconfirmed report is drawn pale with a question mark: it may be a
false alarm, and its size may be wrong. It turns solid when a crew or
the scout reaches it and it turns out to be real, and vanishes if it
was not. The round passes if the town took no more damage than it did
under the reference dispatcher on the identical round.
:mod:`neural_workshop.dispatch` holds the town, the schedule and the
reference; this module draws them and takes the orders.

Every shape on the map is made once and moved, never rebuilt: the map
changes on every frame, and allocating forty shapes sixty times a
second is the slow part of drawing them.

For the agent boundary an order is two ports, as a swap is in the
jigsaw: one names a unit, the next names an incident slot or a station.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import dispatch as town
from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Seconds the round's verdict stays up before the next round.
FEEDBACK = 2.2

#: The most units a rung fields, and so how many unit ports there are.
UNITS = 6

#: Ports: units first, then incident slots, then stations.
FIRST_SLOT = UNITS
FIRST_STATION = UNITS + town.SLOTS
PORTS = FIRST_STATION + len(town.STATIONS)

LETTERS = 'ABCDEFGH'
STATION_KEYS = (key.J, key.K, key.L)
STATION_NAMES = 'JKL'

UNCONFIRMED = (236, 174, 64)
CONFIRMED = (212, 98, 52)
CREW = (44, 112, 222)
SCOUT = (20, 158, 168)
STATION = (128, 132, 140)
SELECT = (250, 250, 250)

#: How long a note about something that just happened stays on the map.
NOTE_SECONDS = 1.2


class Dispatch:
    """Keep the town's damage at or under the reference's."""

    instance: Optional['Dispatch'] = None

    def __init__(self) -> None:
        if Dispatch.instance is not None:
            Dispatch.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        #: Coach mode: paint a verdict on the tick an incident is saved
        #: or lost, for an agent boundary that pays per event. Off for
        #: people, and off in any build that pays per round.
        self.coach = False
        self.world: Optional[town.World] = None
        self.par = 0.0
        self.rung = 1
        self.trial = 0
        self.selected: Optional[int] = None
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, float, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._coach_queue: List[Tuple[bool, str]] = []
        self._coach_up = False
        self._notes: List[Tuple[float, pyglet.text.Label]] = []
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        Dispatch.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.DISPATCH)
        self.start_rung = int(opts['DISPATCH_RUNG'])
        self.total_trials = int(opts['DISPATCH_TRIALS'])
        self.adaptive = bool(opts['DISPATCH_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('dispatch',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _map(self) -> Tuple[float, float, float]:
        """Left, bottom and size of the square map."""
        window = state.window
        top = from_top_edge(116)
        bottom = above_the_band(from_bottom_edge(58))
        size = max(40.0, min(window.width * 0.9, top - bottom))
        return ((window.width - size) / 2.0,
                bottom + (top - bottom - size) / 2.0, size)

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        left, bottom, size = self._map()
        return left + x * size, bottom + y * size

    def _build_chrome(self) -> None:
        dark = bool(state.cfg.BLACK_BACKGROUND)
        fg = 255 if dark else 0
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        ground = pyglet.graphics.Group(order=0)
        lines = pyglet.graphics.Group(order=1)
        things = pyglet.graphics.Group(order=2)
        movers = pyglet.graphics.Group(order=3)
        text = pyglet.graphics.Group(order=4)
        self._text_group = text

        def label(words, size, x, y, anchor='center', group=None, bold=False):
            return pyglet.text.Label(
                words, font_size=size, color=self.textcolor,
                weight='bold' if bold else 'normal',
                batch=self.batch, x=x, y=y, anchor_x=anchor,
                anchor_y='center', font_name=FONTLIST, group=group)

        self.title = label(_('Dispatch'), calc_fontsize(22), width_center(),
                           from_top_edge(36), bold=True)
        self.status = label('', calc_fontsize(14), width_center(),
                            from_top_edge(70))
        self.facts = label('', calc_fontsize(12), width_center(),
                           from_top_edge(96))
        self.footnote = label(
            _('click a unit, then where to send it    keys: 1-4 unit, '
              'A-H incident, J K L station    Esc: menu'),
            calc_fontsize(12), width_center(), from_bottom_edge(26))
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)

        left, bottom, size = self._map()
        self._size = size
        self._ground = pyglet.shapes.Rectangle(
            left, bottom, size, size,
            color=(38, 42, 50) if dark else (232, 235, 240),
            batch=self.batch, group=ground)
        self._stations = []
        for index, (sx, sy) in enumerate(town.STATIONS):
            px, py = self._at(sx, sy)
            half = size * 0.022
            self._stations.append((
                pyglet.shapes.Rectangle(px - half, py - half, 2 * half,
                                        2 * half, color=STATION,
                                        batch=self.batch, group=things),
                label(STATION_NAMES[index], max(6.0, size * 0.016), px,
                      py - half * 1.9, group=text)))
        self._rings, self._discs, self._letters = [], [], []
        for slot in range(town.SLOTS):
            self._rings.append(pyglet.shapes.Arc(
                0, 0, size * 0.045, thickness=max(1.5, size * 0.003),
                color=(150, 150, 156), batch=self.batch, group=things))
            self._discs.append(pyglet.shapes.Circle(
                0, 0, 4, color=CONFIRMED, batch=self.batch, group=things))
            self._letters.append(label(LETTERS[slot],
                                       max(7.0, size * 0.02), 0, 0,
                                       group=text, bold=True))
        self._routes, self._bodies, self._numbers = [], [], []
        for index in range(UNITS):
            self._routes.append(pyglet.shapes.Line(
                0, 0, 0, 0, thickness=max(1.0, size * 0.002),
                color=(150, 156, 170), batch=self.batch, group=lines))
            self._bodies.append(pyglet.shapes.Circle(
                0, 0, size * 0.019, color=CREW, batch=self.batch,
                group=movers))
            number = label(str(index + 1), max(6.0, size * 0.017), 0, 0,
                           group=text, bold=True)
            number.color = (255, 255, 255, 255)
            self._numbers.append(number)
        self._halo = pyglet.shapes.Arc(
            0, 0, size * 0.03, thickness=max(2.0, size * 0.005),
            color=SELECT if dark else (20, 20, 24), batch=self.batch,
            group=movers)
        for _until, note in self._notes:
            note.delete()
        self._notes = []
        self._sync()

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.world = None
        self.selected = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None
        self._coach_queue = []
        self._coach_up = False

    def start_run(self) -> None:
        self._reset()
        self.rung = max(1, self.start_rung)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        dealt = town.deal(self.rung, rng=self.rng)
        self.par = town.par(dealt)
        self.world = town.World(dealt)
        self.selected = None
        self._coach_queue = []
        self._coach_up = False
        self.verdict_shown = None
        self.verdict.clear()
        self.phase = 'running'
        self.message = _('Keep the damage to %d or less') % int(self.par)
        self._sync()

    # --- orders ----------------------------------------------------------

    def press(self, port: int) -> None:
        """One agent port: a unit, then an incident slot or a station."""
        if self.phase != 'running' or self.world is None:
            return
        if port < FIRST_SLOT:
            if port < len(self.world.units):
                self.selected = None if self.selected == port else port
        elif self.selected is not None:
            if port < FIRST_STATION:
                sent = self.world.send(self.selected, 'incident',
                                       port - FIRST_SLOT)
            else:
                sent = self.world.send(self.selected, 'station',
                                       port - FIRST_STATION)
            if sent:
                self.selected = None
        self._sync()

    def update(self, dt: float) -> None:
        if self.phase == 'judged':
            if self.clock() >= self.feedback_until:
                self._next_trial()
            return
        if self.phase != 'running' or self.world is None:
            return
        world = self.world
        world.step(min(dt, 0.25))
        for kind, x, y in world.take_events():
            if kind == 'saved':
                self._note(_('saved'), x, y)
                self._coach_queue.append((True, _('Saved one')))
            elif kind == 'lost':
                self._note(_('lost'), x, y)
                self._coach_queue.append((False, _('Lost one')))
            elif kind == 'false':
                self._note(_('false alarm'), x, y)
        waiting = False
        if self.coach:
            # One event a tick, up for exactly that tick: a label left up
            # would be paid again on every tick it stayed.
            if self._coach_queue:
                self.verdict_shown = self._coach_queue.pop(0)
                self.verdict.show(*self.verdict_shown)
                self._coach_up = True
                waiting = True
            elif self._coach_up:
                self.verdict_shown = None
                self.verdict.clear()
                self._coach_up = False
        else:
            self._coach_queue = []
        if world.over and not waiting:
            self._judge()
        self._sync()

    def _judge(self) -> None:
        world = self.world
        passed = world.damage <= self.par + 1e-9
        self.results.append((world.level.rung, passed, world.damage,
                             self.par))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.selected = None
        self.feedback_until = self.clock() + FEEDBACK
        self.message = (_('Damage %d against a par of %d: %d saved, '
                          '%d lost')
                        % (round(world.damage), int(self.par), world.saved,
                           world.lost))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)

    def _finish(self) -> None:
        self.phase = 'done'
        self.world = None
        tally = self.score()
        self.message = (_('%d of %d rounds under par   highest rung '
                          'passed %d')
                        % (tally['passed'], tally['trials'],
                           tally['best_rung']))
        self._sync()

    def score(self) -> Dict[str, float]:
        trials = len(self.results)
        return {
            'trials': trials,
            'passed': sum(1 for r in self.results if r[1]),
            'best_rung': max((r[0] for r in self.results if r[1]),
                             default=0),
            'mean_damage': (sum(r[2] for r in self.results) / trials
                            if trials else 0.0),
        }

    # --- drawing ---------------------------------------------------------

    def _note(self, words: str, x: float, y: float) -> None:
        px, py = self._at(x, y)
        self._notes.append((self.clock() + NOTE_SECONDS, pyglet.text.Label(
            words, font_size=max(6.0, self._size * 0.016),
            color=self.textcolor, batch=self.batch, x=px,
            y=py + self._size * 0.05, anchor_x='center', anchor_y='center',
            font_name=FONTLIST, group=self._text_group)))

    def _sync(self) -> None:
        """Move every shape to where the town now has it."""
        world = self.world
        live = world is not None and self.phase in ('running', 'judged')
        size = self._size
        now = self.clock()
        kept = []
        for until, note in self._notes:
            if until <= now or not live:
                note.delete()
            else:
                kept.append((until, note))
        self._notes = kept
        self._ground.visible = live
        for square, name in self._stations:
            square.visible = live
            name.visible = live
        for slot in range(town.SLOTS):
            incident = world.incident_in(slot) if live else None
            ring, disc, letter = (self._rings[slot], self._discs[slot],
                                  self._letters[slot])
            shown = incident is not None
            ring.visible = disc.visible = letter.visible = shown
            if not shown:
                continue
            px, py = self._at(incident.x, incident.y)
            full = size * 0.045
            share = max(0.14, min(1.12, incident.shown / town.BURN))
            ring.position = (px, py)
            disc.position = (px, py)
            disc.radius = full * share
            if incident.confirmed:
                disc.color = CONFIRMED
                disc.opacity = 255
                letter.text = LETTERS[slot]
            else:
                disc.color = UNCONFIRMED
                disc.opacity = 120
                letter.text = LETTERS[slot] + '?'
            letter.x, letter.y = px, py
        units = world.units if live else []
        for index in range(UNITS):
            route, body, number = (self._routes[index],
                                   self._bodies[index],
                                   self._numbers[index])
            shown = index < len(units)
            body.visible = number.visible = shown
            route.visible = False
            if not shown:
                continue
            unit = units[index]
            px, py = self._unit_at(unit)
            body.position = (px, py)
            body.color = SCOUT if unit.scout else CREW
            body.radius = size * (0.014 if unit.scout else 0.019)
            number.x, number.y = px, py
            if unit.target is not None and not unit.working:
                kind, where = unit.target
                if kind == 'station':
                    tx, ty = self._at(*town.STATIONS[where])
                else:
                    target = world.incidents.get(where)
                    if target is None:
                        continue
                    tx, ty = self._at(target.x, target.y)
                route.x, route.y, route.x2, route.y2 = px, py, tx, ty
                route.visible = True
        chosen = (self.selected is not None and live
                  and self.selected < len(units)
                  and self.phase == 'running')
        self._halo.visible = chosen
        if chosen:
            self._halo.position = self._unit_at(units[self.selected])
        self._update_labels()

    def _unit_at(self, unit: town.Unit) -> Tuple[float, float]:
        """Where a unit is drawn: on the ring's edge when it is at an
        incident, each unit at its own angle, so neither the incident's
        size nor its letter is hidden under the crew working on it."""
        px, py = self._at(unit.x, unit.y)
        full = self._size * 0.045
        for incident in self.world.incidents.values():
            ix, iy = self._at(incident.x, incident.y)
            if math.hypot(px - ix, py - iy) < full:
                turn = math.radians(50 + 70 * unit.index)
                return (ix + math.cos(turn) * full * 1.15,
                        iy + math.sin(turn) * full * 1.15)
        return px, py

    def _update_labels(self) -> None:
        self.status.text = self.message
        world = self.world
        if world is None or self.phase not in ('running', 'judged'):
            self.facts.text = ''
            return
        level = world.level
        parts = [_('rung %d  %d/%d') % (level.rung, self.trial,
                                        self.total_trials),
                 _('%ds') % int(world.time),
                 _('damage %d') % round(world.damage),
                 _('saved %d  lost %d') % (world.saved, world.lost)]
        if level.false_rate:
            parts.append(_('false alarms %d%%')
                         % round(level.false_rate * 100))
        if level.error:
            parts.append(_('sizes ±%d%%') % round(level.error * 100))
        self.facts.text = '   '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Dispatch.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        for _until, note in self._notes:
            note.delete()
        self._notes = []
        Dispatch.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='decisions')

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
        elif self.phase == 'running':
            if key._1 <= symbol <= key._6:
                self.press(symbol - key._1)
            elif key.A <= symbol <= key.H:
                self.press(FIRST_SLOT + symbol - key.A)
            elif symbol in STATION_KEYS:
                self.press(FIRST_STATION + STATION_KEYS.index(symbol))
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase != 'running' or self.world is None:
            return pyglet.event.EVENT_HANDLED
        port = self._port_at(x, y)
        if port is None:
            self.selected = None
            self._sync()
        else:
            self.press(port)
        return pyglet.event.EVENT_HANDLED

    def _port_at(self, x: float, y: float) -> Optional[int]:
        """What a click at (x, y) means: the nearest thing within reach.

        A unit wins a tie with what it is standing on while nothing is
        selected, so a crew at work can be picked up; once something is
        selected the place wins, so a crew can be sent to an incident
        another crew is already on.
        """
        size = self._size
        reach = size * 0.05
        world = self.world

        def nearest(candidates, on_screen=False):
            best = None
            for port, (cx, cy) in candidates:
                px, py = (cx, cy) if on_screen else self._at(cx, cy)
                gap = math.hypot(px - x, py - y)
                if gap <= reach and (best is None or gap < best[0]):
                    best = (gap, port)
            return None if best is None else best[1]

        units = [(unit.index, self._unit_at(unit)) for unit in world.units]
        places = [(FIRST_SLOT + slot, (incident.x, incident.y))
                  for slot in range(town.SLOTS)
                  for incident in [world.incident_in(slot)]
                  if incident is not None]
        places += [(FIRST_STATION + index, spot)
                   for index, spot in enumerate(town.STATIONS)]
        if self.selected is None:
            return nearest(units, on_screen=True)
        found = nearest(places)
        return found if found is not None else nearest(units, on_screen=True)

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
