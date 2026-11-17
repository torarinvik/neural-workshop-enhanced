# -*- coding: utf-8 -*-
"""Kerbside: cross the street with your eyes shut.

The screen shows the street from above and you on it, and no cars: only
the ear says where they are. An engine grows louder as it comes, sits
to the side it comes from, drops in pitch as it passes (the Doppler
shift), and fades. Walk across lane by lane; the white lines between
lanes are safe to stand on, the middle of a lane is not when a car
comes.

* rung 1: one lane, one slow car that is coming as you start -- wait
  for it to pass, then walk;
* rungs 2-3: two lanes, one each way;
* rungs 4-6: three and four lanes, faster and busier;
* rungs 7-9: quiet electric cars (a hiss of tyres and a faint whine)
  among the engines, and vans parked along the kerb that muffle what
  is behind them;
* rungs 10 and up: more lanes, faster cars, closer together, more of
  them electric, and wind over everything, growing without end.

Every street dealt is one the reference crosses -- it knows where every
car is -- and one where walking straight across without listening is
hit, whether it sets off at once or after waiting any whole number of
seconds up to twelve (a few of those thirteen may slip through, never
more than three).

For the agent boundary: port 0 walks forward and port 1 back for the
step it is sent in. The cars are on the audio channel.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import livesound as LS
from .drshape import Note
from .i18n import _

FORWARD, BACK = range(2)
PORTS = 2
EVENTS = ()
LANE = 3.2                     # metres
HALF_CAR = 1.0                 # half a car's width
BODY = 0.3
CAR_LONG = 4.4
WALK, BACKS = 1.4, 1.0         # metres a second
START = -1.2                   # where you stand on the kerb
SOUND = 343.0
PATCHES = ('wood', 'bell', 'growl')


class Grade(NamedTuple):
    rung: int
    lanes: int
    speed: float               # metres a second
    gap: float                 # mean seconds between cars in a lane
    electric: float            # share of quiet cars
    vans: bool
    wind: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, 1, 7.0, 5.0, 0.0, False, 0.0)
    if r < 4:
        return Grade(r, 2, 8.0 + r, 7.0, 0.0, False, 0.0)
    if r < 7:
        return Grade(r, (3, 3, 4)[r - 4], 11.0 + (r - 4), 8.0, 0.0, False,
                     0.0)
    if r < 10:
        return Grade(r, 4, 13.0, 8.5, 0.25 + 0.1 * (r - 7), True, 0.0)
    return Grade(r, min(8, 4 + (r - 10) // 3), min(25.0, 13.0 + 0.6 * (r - 10)),
                 max(4.5, 8.0 - 0.2 * (r - 10)),
                 min(0.85, 0.45 + 0.03 * (r - 10)), True,
                 min(0.25, 0.03 * (r - 9)))


class Car(NamedTuple):
    lane: int
    dir: int                   # +1 moves to +x (from your left)
    speed: float
    at: float                  # when it passes x = 0
    electric: bool
    pitch: float               # its engine


class Street(NamedTuple):
    level: Grade
    cars: Tuple[Car, ...]
    vans: Tuple[Tuple[float, float], ...]   # x spans parked on your kerb
    seconds: float


def car_x(car: Car, t: float) -> float:
    return car.dir * car.speed * (t - car.at)


def lane_centre(lane: int) -> float:
    return LANE * lane + LANE / 2


def far_side(level: Grade) -> float:
    return LANE * level.lanes + 1.0


def hit(street: Street, t: float, y: float) -> Optional[Car]:
    for car in street.cars:
        if abs(y - lane_centre(car.lane)) < HALF_CAR + BODY and \
                abs(car_x(car, t)) < CAR_LONG / 2 + BODY:
            return car
    return None


def _build(level: Grade, draw: random.Random) -> Street:
    seconds = 30.0 + 12.0 * level.lanes
    cars = []
    for lane in range(level.lanes):
        d = 1 if lane % 2 == 0 else -1
        t = -draw.uniform(0, level.gap)
        if lane == 0:
            # the one coming as you start: in lane 0 while a walker who
            # does not wait is there
            t = draw.uniform(1.0, 2.4)
            cars.append(Car(0, d, level.speed * draw.uniform(0.9, 1.1), t,
                            False, draw.uniform(55, 85)))
        while t < seconds + 10:
            t += max(2.2, draw.expovariate(1.0 / level.gap))
            cars.append(Car(lane, d, level.speed * draw.uniform(0.85, 1.15),
                            t, draw.random() < level.electric,
                            draw.uniform(55, 90)))
    vans = ()
    if level.vans:
        a = draw.uniform(4, 9)
        vans = ((-a - 6, -a), (a, a + 6))
    return Street(level, tuple(cars), vans, seconds)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Street:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(200):
        street = _build(level, random.Random(draw.getrandbits(32)))
        # crossable at the coarse step, and as an environment ticks
        if play(street)[0] and play(street, dt=1 / 60.0, sub=2)[0] and \
                blind(street) <= 3:
            return street
    raise RuntimeError('kerbside: no street for rung %d' % rung)


class Run(object):
    def __init__(self, street: Street) -> None:
        self.street = street
        self.level = street.level
        self.t = 0.0
        self.y = START
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = street.seconds
        self.tracks: List[LS.Track] = []
        for car in street.cars:
            if car.electric:
                parts = ((1, 0.25), (2, 0.1))
                noise = 0.9
            else:
                parts = ((1, 1.0), (2, 0.7), (3, 0.45), (4, 0.3))
                noise = 0.25
            self.tracks.append(LS.Track(parts, noise))
        self.wind = LS.Track(((1, 0.0),), 1.0)
        self.steps: List[Tuple[float, float]] = [(0.0, START)]
        self._sound()

    def _sound(self) -> None:
        t, y = self.t, self.y
        for car, tr in zip(self.street.cars, self.tracks):
            x = car_x(car, t)
            dy = lane_centre(car.lane) - y
            r = math.hypot(x, dy)
            if r > 90 or self.result is not None:
                tr.set(t, 100.0, 0.0, 0.0)
                continue
            radial = car.dir * car.speed * x / max(r, 0.5)
            f = (600.0 if car.electric else car.pitch) * SOUND / (
                SOUND + radial)
            g = (0.18 if car.electric else 0.5) / (1.0 + r / 4.0)
            for a, b in self.street.vans:
                if a <= x <= b and dy > 0:
                    g *= 0.35
            tr.set(t, f, *LS.pan(g, x / max(r, 0.5)))
        w = self.level.wind if self.result is None else 0.0
        self.wind.set(t, 1.0, w, w)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        on = {control} if isinstance(control, int) else set(control or ())
        if FORWARD in on:
            self.y += WALK * dt
        elif BACK in on:
            self.y = max(START, self.y - BACKS * dt)
        if self.steps[-1][1] != self.y:
            self.steps.append((self.t, self.y))
        car = hit(self.street, self.t, self.y)
        if car is not None:
            self.result = (False, _('Hit in lane %d') % (car.lane + 1))
            self.notes.append(Note(self.t, 0.5, 90.0, 0.0, 0.0, 0.6, 0.6,
                                   0.5, 2, 1, -1, 0.0))
        elif self.y >= far_side(self.level):
            self.result = (True, _('Across in %.1f s') % self.t)
            self.notes.append(Note(self.t, 0.3, 1320.0, 0.0, 0.0, 0.3, 0.3,
                                   0.8, 1, 2, -1, 0.0))
        elif self.t > self.street.seconds:
            self.result = (False, _('Still on the street'))
        self._sound()


def wait_then_walk(k: float):
    """A player who does not listen: waits *k* seconds, then walks."""
    return lambda run: [FORWARD] if run.t >= k else []


def blind(street: Street) -> int:
    """Of the thirteen deaf players who wait 0..12 seconds and walk,
    how many get across."""
    return sum(play(street, wait_then_walk(k))[0] for k in range(13))


def act(run: Run, port: int) -> None:
    pass


def _clear(street: Street, t: float, y0: float, y1: float) -> bool:
    """Is walking from *y0* to *y1*, starting at *t*, safe all the way
    -- and for a moment after, standing at *y1*?"""
    y, s = y0, t
    while y < y1:
        if hit(street, s, y) is not None:
            return False
        y += WALK * 0.05
        s += 0.05
    return all(hit(street, s + k * 0.1, y1) is None for k in range(6))


def autopilot(run: Run) -> List[int]:
    """Knows where every car is: walks to the next line between lanes
    when the way there is clear, and waits on the line otherwise."""
    if run.result is not None:
        return []
    street, y = run.street, run.y
    lanes = run.level.lanes
    nxt = min((LANE * k for k in range(lanes + 1) if LANE * k > y + 0.05),
              default=far_side(run.level))
    if nxt >= LANE * lanes:
        nxt = far_side(run.level)
    if hit(street, run.t + 0.1, y) is not None:
        return [BACK]
    if _clear(street, run.t, y, nxt):
        return [FORWARD]
    return []


def mix(run: Run, t0: float, t1: float) -> bytes:
    return LS.mix(run.tracks + [run.wind], t0, t1, run.notes,
                  LS.make_patches(PATCHES))


def play(street: Street, pilot=autopilot, dt: float = 1 / 30.0,
         sub: int = 1) -> Tuple[bool, str]:
    """One crossing: *pilot* asked every *dt*, the street stepped in
    *sub* slices of it (as an environment does: 1/60, in two)."""
    run = Run(street)
    run._sound = lambda: None          # silent: only the walk is judged
    while run.result is None:
        ports = pilot(run)
        for _s in range(sub):
            run.step(dt / sub, ports[0] if ports else None)
            if run.result is not None:
                break
    return run.result
