# -*- coding: utf-8 -*-
"""Traveling Salesman: the shortest round trip you can see.

Cities are scattered on the screen and the task is to visit all of
them and come home by the shortest route you can find, clicking them
in order. Nothing is hidden — every distance is on the screen — so
what is exercised is planning under combinatorics: the routes multiply
faster than anything can enumerate, and a person does well by seeing
shape instead, following the hull, keeping crossings out, leaving no
city stranded to be collected at great expense later.

The scoring is against the true optimum, not a heuristic. Up to the
sizes offered here the shortest tour is computed exactly (Held-Karp:
dynamic programming over subsets, exponential but comfortably inside
a dozen cities), so a round says precisely how much longer your route
was than the best possible one. People are famously good at this —
untrained players land within a few per cent of optimal — which is
what makes the score meaningful: the gap is read against a standard
players can actually approach.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Sequence, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions

#: Cities a round may hold. Five is a warm-up; twelve is the most the
#: exact solver is asked for, and plenty to plan over.
FEWEST_CITIES, MOST_CITIES = 5, 12

#: How close to the optimum a tour has to come before an adaptive run
#: adds a city, and how far off before one is taken away. Closeness
#: is the optimal length over the tour's length, so one is perfect.
GROW_AT, SHRINK_AT = 0.97, 0.85

#: How far apart cities are placed, as a share of the panel — near
#: enough coincident cities make length judgements about pixels, not
#: routes.
SPREAD = 0.13

Point = Tuple[float, float]


def tour_length(cities: Sequence[Point], order: Sequence[int]) -> float:
    """The length of the round trip visiting *order* and coming home."""
    total = 0.0
    for here in range(len(order)):
        ax, ay = cities[order[here]]
        bx, by = cities[order[(here + 1) % len(order)]]
        total += math.hypot(ax - bx, ay - by)
    return total


def optimal_tour(cities: Sequence[Point]) -> Tuple[List[int], float]:
    """The shortest round trip, exactly, by Held-Karp.

    Dynamic programming over subsets: the best way to have visited a
    set of cities and be standing at one of them. Exponential in the
    number of cities and quadratic on top, which at twelve cities is
    a few hundred thousand table entries — well under a blink, and it
    buys the honest word "optimal" for the score.

    The tour starts at city 0 by convention; a round trip has no
    start, so nothing is lost.
    """
    count = len(cities)
    if count < 2:
        return list(range(count)), 0.0
    span = [[math.hypot(ax - bx, ay - by) for bx, by in cities]
            for ax, ay in cities]
    if count == 2:
        return [0, 1], span[0][1] * 2
    best: Dict[Tuple[int, int], Tuple[float, int]] = {}
    for city in range(1, count):
        best[(1 << city, city)] = (span[0][city], 0)
    for size in range(2, count):
        for mask in range(1 << count):
            if mask & 1 or bin(mask).count('1') != size:
                continue
            for last in range(1, count):
                if not mask >> last & 1:
                    continue
                without = mask ^ (1 << last)
                found = None
                for previous in range(1, count):
                    if not without >> previous & 1:
                        continue
                    before = best.get((without, previous))
                    if before is None:
                        continue
                    cost = before[0] + span[previous][last]
                    if found is None or cost < found[0]:
                        found = (cost, previous)
                if found is not None:
                    best[(mask, last)] = found
    everyone = (1 << count) - 2         # all but city 0
    ending = min(((best[(everyone, last)][0] + span[last][0], last)
                  for last in range(1, count)), key=lambda pair: pair[0])
    length, last = ending
    order = [0]
    mask = everyone
    while last:
        order.append(last)
        mask, last = mask ^ (1 << last), best[(mask, last)][1]
    order = [order[0]] + order[:0:-1]
    return order, length


def scatter(count: int, rng: random.Random) -> List[Point]:
    """*count* cities in the unit square, none of them crowding.

    Rejection sampling against a minimum separation, relaxed a little
    whenever a layout refuses to fit, so the function always returns
    rather than insisting on room that dense counts do not have.
    """
    apart = SPREAD
    while True:
        cities: List[Point] = []
        for _try in range(400):
            candidate = (0.05 + 0.9 * rng.random(),
                         0.05 + 0.9 * rng.random())
            if all(math.hypot(candidate[0] - cx, candidate[1] - cy) >= apart
                   for cx, cy in cities):
                cities.append(candidate)
                if len(cities) == count:
                    return cities
        apart *= 0.8


class TravelingSalesman:
    """Show the cities, take a tour by clicks, score it against truth."""

    instance: Optional['TravelingSalesman'] = None

    def __init__(self) -> None:
        if TravelingSalesman.instance is not None:
            TravelingSalesman.instance.close()
        self.rng = random.Random()
        self.cities: List[Point] = []
        self.route: List[int] = []
        self.best_order: List[int] = []
        self.best_length = 0.0
        self.city_count = FEWEST_CITIES
        self.trial_cities = FEWEST_CITIES
        self.round = 0
        self.started_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, float, float]] = []
        self.phase = 'ready'
        self.drawn: List[object] = []
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        TravelingSalesman.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SALESMAN)
        self.start_cities = int(opts['TSP_CITIES'])
        self.total_rounds = int(opts['TSP_ROUNDS'])
        self.adaptive = bool(opts['TSP_ADAPTIVE'])
        self.show_best = bool(opts['TSP_SHOW_BEST'])
        self.city_count = self.clamped(self.start_cities)

    @staticmethod
    def clamped(count: int) -> int:
        return max(FEWEST_CITIES, min(MOST_CITIES, count))

    def open_options(self) -> None:
        taskoptions.open_task_options('salesman',
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
        self.citycolor = (fg, fg, fg, 255)
        self.routecolor = (64, 96, 255, 255)
        self.bestcolor = (46, 160, 67, 255)
        self.batch = pyglet.graphics.Batch()
        self.line_group = pyglet.graphics.Group(order=0)
        self.city_group = pyglet.graphics.Group(order=1)
        self.title = pyglet.text.Label(
            _('Traveling Salesman'), font_size=calc_fontsize(22),
            weight='bold', color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     click cities in order,'
              ' the last again to undo     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self._redraw()

    def _canvas(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(100)
        bottom = from_bottom_edge(56)
        return (window.width * 0.06, bottom,
                window.width * 0.88, max(40.0, top - bottom))

    def _place(self, city: Point) -> Tuple[float, float]:
        left, bottom, width, height = self._canvas()
        return left + city[0] * width, bottom + city[1] * height

    def relayout(self) -> None:
        self._build_chrome()

    # --- a round ---------------------------------------------------------

    def _reset(self) -> None:
        self.round = 0
        self.results = []
        self.cities = []
        self.route = []
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self.city_count = self.clamped(self.start_cities)
        self._next_round()

    def _next_round(self) -> None:
        if self.round >= self.total_rounds:
            self._finish()
            return
        self.round += 1
        self.trial_cities = self.city_count
        self.cities = scatter(self.trial_cities, self.rng)
        self.best_order, self.best_length = optimal_tour(self.cities)
        self.route = []
        self.started_at = time.time()
        self.phase = 'touring'
        self.message = _('Visit every city and come home, the short way')
        self._redraw()

    def _pick(self, city: int) -> None:
        """Extend the tour; picking the last city again retracts it."""
        if self.phase != 'touring':
            return
        if self.route and city == self.route[-1]:
            self.route.pop()
        elif city not in self.route:
            self.route.append(city)
            if len(self.route) == self.trial_cities:
                self._toured()
        self._redraw()

    def _toured(self) -> None:
        took = time.time() - self.started_at
        length = tour_length(self.cities, self.route)
        closeness = self.best_length / max(length, self.best_length)
        self.results.append((self.trial_cities, closeness, took))
        if self.adaptive:
            if closeness >= GROW_AT:
                self.city_count = self.clamped(self.city_count + 1)
            elif closeness < SHRINK_AT:
                self.city_count = self.clamped(self.city_count - 1)
        self.phase = 'toured'
        self.feedback_until = time.time() + (2.2 if self.show_best else 1.4)
        over = 100.0 * (length / self.best_length - 1.0)
        if over < 0.05:
            self.message = _('The shortest route there is — in %.0fs') % took
        else:
            self.message = (_('%.0f%% longer than the shortest route — '
                              'in %.0fs') % (over, took))
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.cities = []
        self.route = []
        tally = self.score()
        self.message = _('%d routes, %d%% of optimal on average, '
                         '%.0fs each, most cities %d'
                         ) % (tally['rounds'], tally['closeness'],
                              tally['mean_seconds'], tally['best_cities'])
        self._redraw()

    def score(self) -> Dict[str, float]:
        rounds = len(self.results)
        return {
            'rounds': rounds,
            'closeness': int(round(100 * sum(close for _c, close, _t
                                             in self.results) / rounds)
                             ) if rounds else 0,
            'mean_seconds': (sum(took for _c, _cl, took in self.results)
                             / rounds) if rounds else 0.0,
            'best_cities': max((cities for cities, _cl, _t in self.results),
                               default=0),
        }

    def update(self, dt: float) -> None:
        if self.phase == 'toured' and time.time() >= self.feedback_until:
            self._next_round()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _line(self, one: int, two: int, color, width=3.0,
              group=None) -> None:
        ax, ay = self._place(self.cities[one])
        bx, by = self._place(self.cities[two])
        self.drawn.append(pyglet.shapes.Line(
            ax, ay, bx, by, thickness=width, color=color,
            batch=self.batch, group=group or self.line_group))

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.phase in ('touring', 'toured') and self.cities:
            if self.phase == 'toured' and self.show_best:
                for here in range(len(self.best_order)):
                    self._line(self.best_order[here],
                               self.best_order[(here + 1)
                                               % len(self.best_order)],
                               self.bestcolor, width=5.0)
            for here in range(len(self.route) - 1):
                self._line(self.route[here], self.route[here + 1],
                           self.routecolor)
            if self.phase == 'toured' and len(self.route) > 1:
                self._line(self.route[-1], self.route[0], self.routecolor)
            for city, position in enumerate(self.cities):
                x, y = self._place(position)
                visited = city in self.route
                self.drawn.append(pyglet.shapes.Circle(
                    x, y, 9 if city == (self.route[0] if self.route
                                        else -1) else 7,
                    color=self.routecolor if visited else self.citycolor,
                    batch=self.batch, group=self.city_group))
        self._update_labels()

    def _update_labels(self) -> None:
        parts = [self.message]
        if self.phase in ('touring', 'toured'):
            parts.append(_('route %d of %d   visited %d of %d')
                         % (self.round, self.total_rounds,
                            len(self.route), self.trial_cities))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if TravelingSalesman.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        TravelingSalesman.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='planning')

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
        return pyglet.event.EVENT_HANDLED

    def _at(self, x: int, y: int) -> Optional[int]:
        nearest, best = None, 18.0 ** 2
        for city, position in enumerate(self.cities):
            cx, cy = self._place(position)
            apart = (x - cx) ** 2 + (y - cy) ** 2
            if apart < best:
                nearest, best = city, apart
        return nearest

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'touring':
            found = self._at(x, y)
            if found is not None:
                self._pick(found)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
