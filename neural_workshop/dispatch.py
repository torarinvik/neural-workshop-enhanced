# -*- coding: utf-8 -*-
"""Dispatch: a town that does not wait while you decide.

Incidents appear on a map and get worse until someone deals with them.
A handful of crews can be sent to them; travel takes time, a crew on
one job is not available for the next, and an incident left too long
burns out and is lost. That is the whole game, and it is the one thing
no other task in the workshop asks: to decide, with the clock running
and more to do than hands to do it, what matters most *now*.

It is built out of the decisions a turn-based task cannot pose.

* **Triage.** Two incidents and one free crew: the big one across town
  or the small one next door? Size, growth and distance pull different
  ways, and the answer changes while the crew is on the road.
* **Tempo.** Incidents come in bursts and lulls. A burst wants the
  nearest free crew sent at once; a lull is the only time there is to
  move crews to where the next burst is likely to need them. Thinking
  hard in a burst and twitching through a lull both lose.
* **Uncertainty.** From rung four some reports are false alarms, and
  from rung six a report's size is only an estimate. A scout is fast
  and can go and look, but looking takes time the incident keeps
  growing through.
* **Error correction.** Any crew can be redirected at any moment. When
  the scout finds a false alarm, or something worse appears, turning a
  crew round is the skill — and abandoning a job half done has a price,
  because what was not finished starts growing again.
* **Now against later.** From rung eight a crew can be sent to a
  station for a refit: twelve seconds standing there, and it works
  twice as fast for the rest of the round. Those twelve seconds are
  the price — a town one crew short — and a refit broken off to answer
  a call is lost whole. When to pay it, with which crew, how many at
  once, and whether an incident is worth throwing away a refit that is
  nearly done are all the player's to decide, against a clock that
  makes the refit worth less the later it is bought.

**Everything that happens to the town is fixed by the clock, not by the
player.** Where and when each incident appears, how fast it grows,
whether it is real and how wrong its report is are all dealt before
the round starts. So a reference dispatcher can play the identical
round, and its damage is the par the player's is measured against. The
reference is deliberately plain — the most urgent incident a free crew
can still save, the scout to whatever is unconfirmed, and a crew with
nothing to do in for its refit, one crew at a time — and it never
moves a crew to where the next burst will be, never doubles up and
never changes its mind. Past rung twenty the round has to be lost by
less than it loses, by more at every rung.

**The simulation steps in fixed twentieths of a second** whatever it is
handed, so a round played at sixty frames a second and the reference's
round played in one go are the same dynamics, not two integrations of
them.

Nothing here imports pyglet.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: The fixed step of the simulation, seconds.
SIM_DT = 0.05

#: How many incidents can be open at once: one letter each on screen,
#: one port each at the boundary.
SLOTS = 8

#: An incident whose need reaches this is lost. Need is in crew-seconds:
#: one crew clears one unit of it a second.
BURN = 10.0
WORK = 1.0

#: Map units a second. The map is a unit square, so a crew crosses it in
#: about eight seconds and the scout in under three.
CREW_SPEED = 0.12
SCOUT_SPEED = 0.40

#: Damage is the seconds real incidents spent open, plus this for each
#: one lost. A loss is worth twenty seconds of anything waiting.
LOSS = 20.0

#: Seconds a crew stands at a station being refitted, and how many
#: times faster it works for the rest of the round once it has been.
#: A crew in for a refit is a crew not on the road: weaker now, for the
#: sake of being stronger later. Work rate is what is worth buying --
#: measured handed over free at the start of the round, two more crews
#: cut the reference's damage by about an eighth at best and by nothing
#: at all up to rung ten, because it is the road and the job that take
#: the time and not the wait for a free crew; every crew working twice
#: as fast cuts it by between a quarter and a third on every rung.
REFIT = 12.0
HEAVY = 2.0

#: Where crews wait. Three stations, spread so no corner is far from all.
STATIONS: Tuple[Tuple[float, float], ...] = (
    (0.22, 0.26), (0.78, 0.30), (0.50, 0.78))

#: How often the reference looks at the map, seconds.
POLICY_DT = 0.25


class Grade(NamedTuple):
    rung: int
    crews: int
    scout: bool
    #: Chance a report is a false alarm.
    false_rate: float
    #: A report's size is the truth times one plus or minus this.
    error: float
    #: Growth of an unattended incident, need a second: low and high.
    growth: Tuple[float, float]
    #: What an incident starts at: low and high.
    need: Tuple[float, float]
    #: The most incidents in one burst.
    burst: int
    #: Seconds between bursts: low and high.
    lull: Tuple[float, float]
    #: No incident appears after this many seconds.
    length: float
    #: Seconds a refit takes, or nought on rungs where there is none.
    refit: float
    #: Par is the reference's damage times this, plus :attr:`grace`.
    factor: float
    grace: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    # The load has to outgrow the hands. Crews stop at three while
    # growth keeps climbing, until an incident across town burns out
    # before a crew that sets off at once can reach it, and where the
    # crews were standing when it appeared is what decides it.
    harder = min(7.0, 1.0 + 0.2 * (r - 1))
    if r <= 20:
        factor, grace = max(1.0, 2.0 - (r - 1) / 11.0), 3.0
    else:
        factor, grace = 1.0 / (1.0 + 0.04 * (r - 20)), 0.0
    return Grade(
        rung=r,
        crews=2 if r <= 4 else 3,
        scout=r >= 4,
        false_rate=0.0 if r < 4 else min(0.5, 0.08 * (r - 3)),
        error=0.0 if r < 6 else min(0.6, 0.06 * (r - 5)),
        growth=(0.10 * harder, 0.18 * harder),
        need=(2.0 + min(1.0, 0.05 * (r - 1)), 4.0 + min(2.0, 0.1 * (r - 1))),
        burst=min(6, 1 + r // 3),
        lull=(max(2.0, 9.0 - 0.4 * r), max(4.0, 16.0 - 0.6 * r)),
        length=min(100.0, 40.0 + 3.0 * r),
        refit=0.0 if r < 8 else REFIT,
        factor=factor,
        grace=grace,
    )


def longest_life(level: Grade) -> float:
    """The longest an incident can stay open if nobody abandons it.

    Unattended it burns out by ``(BURN - need) / growth``; attended at
    the last moment it takes at most ``BURN / WORK`` more to clear. The
    schedule never puts more than :data:`SLOTS` incidents inside one
    such window, so a dispatcher who never walks away from a job can
    never find the board full.
    """
    return (BURN - level.need[0]) / level.growth[0] + BURN / WORK


class Report(NamedTuple):
    """One scheduled incident, as dealt."""

    at: float           # when it appears
    x: float
    y: float
    need: float         # what it starts at
    growth: float
    false: bool
    factor: float       # reported size over true size


class Deal(NamedTuple):
    level: Grade
    reports: Tuple[Report, ...]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    """A round: every incident it will throw, fixed in advance."""
    rng = rng or random.Random(seed)
    level = grade(rung)
    window = longest_life(level)
    times: List[float] = []
    t = rng.uniform(2.0, 4.0)
    while t <= level.length:
        for _one in range(rng.randint(1, level.burst)):
            recent = [u for u in times if u > t - window]
            if len(recent) >= SLOTS:
                t = recent[0] + window + 0.1
            if t > level.length:
                break
            times.append(t)
            t += rng.uniform(0.3, 1.2)
        t += rng.uniform(*level.lull)
    reports = []
    for at in times:
        while True:
            x, y = rng.uniform(0.06, 0.94), rng.uniform(0.06, 0.94)
            if all(math.hypot(x - sx, y - sy) > 0.09 for sx, sy in STATIONS):
                break
        reports.append(Report(
            at=at, x=x, y=y, need=rng.uniform(*level.need),
            growth=rng.uniform(*level.growth),
            false=rng.random() < level.false_rate,
            factor=1.0 + rng.uniform(-level.error, level.error)))
    return Deal(level, tuple(reports))


class Incident:
    """An incident on the board."""

    def __init__(self, ident: int, report: Report, slot: int) -> None:
        self.ident = ident
        self.report = report
        self.slot = slot
        self.need = report.need
        self.confirmed = False

    @property
    def x(self) -> float:
        return self.report.x

    @property
    def y(self) -> float:
        return self.report.y

    @property
    def shown(self) -> float:
        """The size on screen: the truth once confirmed, the report's
        estimate before."""
        if self.confirmed:
            return self.need
        return self.need * self.report.factor

    @property
    def shown_growth(self) -> float:
        if self.confirmed:
            return self.report.growth
        return self.report.growth * self.report.factor


#: ('incident', ident), ('station', index) to go and wait there, or
#: ('refit', index) to go there and be refitted.
Target = Tuple[str, int]


class Unit:
    """A crew or the scout."""

    def __init__(self, index: int, scout: bool, x: float, y: float) -> None:
        self.index = index
        self.scout = scout
        self.x, self.y = x, y
        self.target: Optional[Target] = None
        self.working = False
        #: Refitted: works :data:`HEAVY` times as fast from then on.
        self.heavy = False
        #: Seconds of the refit it is in the middle of.
        self.refit = 0.0

    @property
    def speed(self) -> float:
        return SCOUT_SPEED if self.scout else CREW_SPEED

    @property
    def idle(self) -> bool:
        return self.target is None


class World:
    """One round in progress, for the player or the reference alike."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        self.time = 0.0
        self._carry = 0.0
        self._next = 0
        self.incidents: Dict[int, Incident] = {}
        self.slots: List[Optional[int]] = [None] * SLOTS
        self.units: List[Unit] = []
        for index in range(self.level.crews):
            sx, sy = STATIONS[index % len(STATIONS)]
            self.units.append(Unit(index, False, sx, sy))
        if self.level.scout:
            sx, sy = STATIONS[len(self.units) % len(STATIONS)]
            self.units.append(Unit(len(self.units), True, sx, sy))
        self.damage = 0.0
        self.saved = 0
        self.lost = 0
        self.false_alarms = 0
        #: ('saved' | 'lost' | 'false' | 'report' | 'refit', x, y) since
        #: last read.
        self.events: List[Tuple[str, float, float]] = []
        self.over = False

    # --- orders ----------------------------------------------------------

    def incident_in(self, slot: int) -> Optional[Incident]:
        if not 0 <= slot < SLOTS or self.slots[slot] is None:
            return None
        return self.incidents.get(self.slots[slot])

    def send(self, unit: int, kind: str, index: int) -> bool:
        """Order a unit to an incident slot, to a station, or to a
        station for a refit.

        Any unit can be redirected at any time, a crew at work included;
        what it leaves unfinished starts growing again. A refit that is
        interrupted is lost: the crew called out of one starts the next
        from nothing.
        """
        if self.over or not 0 <= unit < len(self.units):
            return False
        mover = self.units[unit]
        if kind == 'incident':
            incident = self.incident_in(index)
            if incident is None:
                return False
            target: Target = ('incident', incident.ident)
        elif kind == 'station' and 0 <= index < len(STATIONS):
            target = ('station', index)
        elif kind == 'refit' and 0 <= index < len(STATIONS):
            if not self.can_refit(mover):
                return False
            target = ('refit', index)
        else:
            return False
        if mover.target == target:
            return True
        mover.target = target
        mover.working = False
        mover.refit = 0.0
        return True

    def can_refit(self, unit: Unit) -> bool:
        """Whether *unit* has a refit still to be had: a crew, once."""
        return bool(self.level.refit) and not unit.scout and not unit.heavy

    # --- time ------------------------------------------------------------

    def step(self, dt: float) -> None:
        """Advance by *dt*, in whole fixed steps; the rest is carried."""
        if self.over:
            return
        self._carry += dt
        while self._carry >= SIM_DT - 1e-12 and not self.over:
            self._carry -= SIM_DT
            self._tick()

    def _tick(self) -> None:
        self.time += SIM_DT
        reports = self.deal.reports
        while self._next < len(reports) \
                and reports[self._next].at <= self.time:
            self._appear(self._next, reports[self._next])
            self._next += 1
        for unit in self.units:
            self._move(unit)
        crews: Dict[int, float] = {}
        for unit in self.units:
            if not unit.working or unit.target is None:
                continue
            kind, index = unit.target
            if kind == 'refit':
                unit.refit += SIM_DT
                if unit.refit >= self.level.refit - 1e-9:
                    unit.heavy = True
                    unit.refit = 0.0
                    unit.target = None
                    unit.working = False
                    self.events.append(('refit', unit.x, unit.y))
                continue
            crews[index] = crews.get(index, 0.0) + (
                HEAVY if unit.heavy else 1.0)
        for incident in list(self.incidents.values()):
            hands = crews.get(incident.ident, 0.0)
            if hands:
                incident.need -= hands * WORK * SIM_DT
            else:
                incident.need += incident.report.growth * SIM_DT
            if not incident.report.false:
                self.damage += SIM_DT
            if incident.need <= 0.0:
                self._close(incident, 'saved')
            elif incident.need >= BURN:
                self._close(incident,
                            'expired' if incident.report.false else 'lost')
        if self._next >= len(reports) and not self.incidents:
            self.over = True

    def _appear(self, ident: int, report: Report) -> None:
        free = [slot for slot, held in enumerate(self.slots) if held is None]
        if not free:
            # The board is full, which only abandoning jobs can cause:
            # the report is never even logged.
            if not report.false:
                self.lost += 1
                self.damage += LOSS
                self.events.append(('lost', report.x, report.y))
            return
        self.incidents[ident] = Incident(ident, report, free[0])
        self.slots[free[0]] = ident
        self.events.append(('report', report.x, report.y))

    def _move(self, unit: Unit) -> None:
        if unit.target is None or unit.working:
            return
        kind, index = unit.target
        incident = None
        if kind == 'incident':
            incident = self.incidents.get(index)
            if incident is None:
                unit.target = None
                return
            tx, ty = incident.x, incident.y
        else:
            tx, ty = STATIONS[index]
        dx, dy = tx - unit.x, ty - unit.y
        gap = math.hypot(dx, dy)
        reach = unit.speed * SIM_DT
        if gap > reach:
            unit.x += dx / gap * reach
            unit.y += dy / gap * reach
            return
        unit.x, unit.y = tx, ty
        if kind == 'station':
            unit.target = None
            return
        if kind == 'refit':
            unit.working = True
            return
        incident.confirmed = True
        if incident.report.false:
            self._close(incident, 'false')
        elif unit.scout:
            unit.target = None
        else:
            unit.working = True

    def _close(self, incident: Incident, how: str) -> None:
        if how == 'saved':
            self.saved += 1
        elif how == 'lost':
            self.lost += 1
            self.damage += LOSS
        elif how == 'false':
            self.false_alarms += 1
        if how != 'expired':
            self.events.append((how, incident.x, incident.y))
        del self.incidents[incident.ident]
        self.slots[incident.slot] = None
        for unit in self.units:
            if unit.target == ('incident', incident.ident):
                unit.target = None
                unit.working = False

    def take_events(self) -> List[Tuple[str, float, float]]:
        events, self.events = self.events, []
        return events


# --- the reference -----------------------------------------------------------

#: unit, 'incident' | 'station' | 'refit', slot or station
Order = Tuple[int, str, int]


def nearest_station(x: float, y: float) -> int:
    return min(range(len(STATIONS)), key=lambda index: (
        math.hypot(STATIONS[index][0] - x, STATIONS[index][1] - y), index))


def reference_orders(world: World) -> List[Order]:
    """What the reference would order now, reading only what is shown.

    The scout, when it has nothing to do, goes to the nearest report
    nobody has confirmed. Each crew with nothing to do goes to the most
    urgent incident no crew is on — the one with the least time left
    that it can still reach before it burns, by the size and growth on
    screen — and waits for the scout rather than drive to a report the
    scout is already on its way to, once false alarms are common.

    A crew that finds nothing to go to goes to the nearest station for
    its refit instead, if it has not had one and no other crew is in
    for one, and stays until it is done whatever comes up. One at a
    time is the plain rule that holds on every rung. Measured over
    sixty rounds a rung it takes 13 to 21% less damage than never
    refitting, and sending every idle crew in at once gives two thirds
    of that back at rung eight, a third at rung sixteen, and from rung
    twenty loses the better part of an incident more a round.
    """
    orders: List[Order] = []
    level = world.level
    taken = {unit.target[1] for unit in world.units
             if not unit.scout and unit.target is not None
             and unit.target[0] == 'incident'}
    scouting = {unit.target[1] for unit in world.units
                if unit.scout and unit.target is not None
                and unit.target[0] == 'incident'}
    refitting = any(unit.target is not None and unit.target[0] == 'refit'
                    for unit in world.units)
    for unit in world.units:
        if not unit.idle:
            continue
        if unit.scout:
            unknown = [i for i in world.incidents.values()
                       if not i.confirmed and i.ident not in scouting]
            if unknown:
                pick = min(unknown, key=lambda i: (
                    math.hypot(i.x - unit.x, i.y - unit.y), i.ident))
                scouting.add(pick.ident)
                orders.append((unit.index, 'incident', pick.slot))
            continue
        best, best_slack = None, None
        for incident in world.incidents.values():
            if incident.ident in taken:
                continue
            if (not incident.confirmed and level.false_rate >= 0.25
                    and incident.ident in scouting):
                continue
            eta = math.hypot(incident.x - unit.x,
                             incident.y - unit.y) / unit.speed
            growth = max(1e-6, incident.shown_growth)
            arriving = incident.shown + growth * eta
            if arriving >= BURN:
                continue
            slack = (BURN - arriving) / growth
            if not incident.confirmed:
                slack /= max(0.05, 1.0 - level.false_rate)
            if best_slack is None or (slack, incident.ident) < best_slack:
                best, best_slack = incident, (slack, incident.ident)
        if best is not None:
            taken.add(best.ident)
            orders.append((unit.index, 'incident', best.slot))
        elif not refitting and world.can_refit(unit):
            refitting = True
            orders.append((unit.index, 'refit',
                           nearest_station(unit.x, unit.y)))
    return orders


def reference_round(dealt: Deal) -> World:
    """The reference's whole round on *dealt*."""
    world = World(dealt)
    steps = int(round(POLICY_DT / SIM_DT))
    while not world.over:
        for unit, kind, index in reference_orders(world):
            world.send(unit, kind, index)
        for _step in range(steps):
            world.step(SIM_DT)
    return world


def idle_round(dealt: Deal) -> World:
    """The round with nobody sent anywhere: the worst it can go."""
    world = World(dealt)
    while not world.over:
        world.step(1.0)
    return world


def par(dealt: Deal) -> float:
    """The damage a round must come in at or under to pass."""
    level = dealt.level
    return reference_round(dealt).damage * level.factor + level.grace


__all__ = ['BURN', 'CREW_SPEED', 'Deal', 'Grade', 'HEAVY', 'Incident', 'LOSS',
           'POLICY_DT', 'REFIT', 'Report', 'SCOUT_SPEED', 'SIM_DT', 'SLOTS',
           'STATIONS', 'Unit', 'World', 'deal', 'grade', 'idle_round',
           'longest_life', 'nearest_station', 'par', 'reference_orders',
           'reference_round']
