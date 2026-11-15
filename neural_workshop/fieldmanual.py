# -*- coding: utf-8 -*-
"""Field Manual: carry out written orders on a machine you have to turn
over in your hands.

A cube of a machine floats in front of you with buttons, switches,
dials and sliders on its faces. An order comes up in words -- "Press
the red button", "Turn the green dial to 5", "After the third beep,
flip the switch left of the blue dial" -- and you carry it out before
the clock runs down, then the next.

Mouse: drag the machine (or the space round it) to turn it; click
buttons and switches; drag a dial sideways to turn it a notch at a
time; drag a slider's handle along its track. Keys: the digits type
numbers, and Shift is held for orders that say so.

The machine answers in sound: a click for a button, a tick for every
notch of a dial and a bell on its hidden notch, a tone that follows a
slider while it is dragged, a hum to match it to, beeps to count.

The ladder:

* rungs 1-3: one order, a few parts, all on the front face;
* rungs 4-6: two orders; parts on the sides too, so the machine has to
  be turned; dials, sliders and numbers to type;
* rungs 7-9: three orders, every face; parts named by what they are
  next to; numbers painted on the faces to find and type;
* rungs 10-12: "until it tocks" (by ear alone), Shift held with a
  click, and "every button except ...";
* rungs 13-15: four orders; "after the third beep"; a slider matched to
  a hum by ear;
* rungs 16-19: the machine turns by itself, the beeps come high and low
  and only one kind counts, and there is noise;
* from rung 20: orders are shown for a few seconds and then go; more
  orders, more parts, a faster spin and less time every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec, add, dot, scale, sub, unit
from .i18n import _

DIGIT = H.KEYS                 # ports 14-23 type 0-9
SHIFT = H.KEYS + 10            # port 24, held
PORTS = H.KEYS + 11
EVENTS = H.HAND_EVENTS + tuple(range(DIGIT, DIGIT + 10))

BUTTON, SWITCH, DIAL, SLIDER = range(4)
KINDS = (_('button'), _('switch'), _('dial'), _('slider'))
COLOURS = (_('red'), _('green'), _('blue'), _('yellow'), _('white'),
           _('orange'))
ORDINALS = (_('first'), _('second'), _('third'), _('fourth'), _('fifth'))
NOTCHES = 8
PITCH = 0.58                   # the grid on a face
TRACK = 0.22                   # half a slider's track
TURN = 0.45                    # degrees turned per unit dragged
NOTCH = 14.0                   # units dragged per notch of a dial
BEEP_FIRST, BEEP_GAP = 1.0, 1.1
CLICK, TICK, TOCK, TONE, HUM, BEEP, BUZZ = range(7)
PATCHES = ('wood', 'pluck', 'bell', 'sine', 'organ', 'glass', 'growl')

EYE: Vec = (0.0, 0.0, 6.5)
VIEW = H.lens(EYE, (0.0, 0.0, 0.0), 1100.0, 500.0, 275.0)
# normal, right, up of each face: front, right, back, left, top, bottom.
FACES: Tuple[Tuple[Vec, Vec, Vec], ...] = (
    ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
    ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
    ((0, -1, 0), (1, 0, 0), (0, 0, 1)))
#: The yaw and pitch that bring each face to the front.
FRONT = ((0.0, 0.0), (-90.0, 0.0), (180.0, 0.0), (90.0, 0.0),
         (None, 90.0), (None, -90.0))


class Grade(NamedTuple):
    rung: int
    steps: int
    parts: int
    faces: Tuple[int, ...]
    orders: Tuple[str, ...]
    relate: bool               # parts named by their neighbours
    shift: bool
    wait: bool
    tones: bool                # high and low beeps
    spin: float                # degrees a second
    noise: bool
    show: float                # seconds an order stays up, 0 for always
    pace: float                # seconds allowed an order
    slack: float               # how close a slider has to be


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    orders = ['press', 'flip']
    if r >= 4:
        orders += ['dial', 'slide', 'type']
    if r >= 7:
        orders += ['facenum']
    if r >= 10:
        orders += ['listen', 'except']
    if r >= 13:
        orders += ['match']
    return Grade(
        rung=r,
        steps=(1 if r < 4 else 2 if r < 7 else 3 if r < 13 else 4 if r < 20
               else 5 + top // 3),
        parts=(3 if r < 4 else 6 if r < 7 else 9 if r < 13 else 12 if r < 20
               else min(22, 14 + top // 2)),
        faces=((0,) if r < 4 else (0, 1, 3) if r < 7 else (0, 1, 2, 3, 4, 5)),
        orders=tuple(orders), relate=r >= 7, shift=r >= 10, wait=r >= 13,
        tones=r >= 16,
        spin=0.0 if r < 16 else 8.0 if r < 20 else min(28.0, 10.0 + top),
        noise=r >= 16,
        show=0.0 if r < 20 else max(1.5, 5.0 - 0.1 * top),
        pace=(16.0 if r < 4 else 14.0 if r < 10 else 12.0 if r < 20
              else max(6.5, 11.0 - 0.15 * top)),
        slack=0.09 if r < 20 else max(0.05, 0.09 - 0.002 * top))


class Part(NamedTuple):
    kind: int
    colour: int
    face: int
    col: int
    row: int


class Step(NamedTuple):
    kind: str
    text: str
    targets: Tuple[int, ...]   # parts (empty for typing)
    value: object              # a notch, a slider value, or digits
    shift: bool = False
    wait: int = 0              # act only after this many (counted) beeps
    tone: int = -1             # -1 every beep counts, 0 low, 1 high
    beeps: Tuple[int, ...] = ()   # each beep, low 0 or high 1


class Job(NamedTuple):
    level: Grade
    parts: Tuple[Part, ...]
    numbers: Dict[int, str]    # painted on faces
    secrets: Tuple[int, ...]   # each dial's hidden notch
    start: Tuple[object, ...]  # each part's state at the start
    steps: Tuple[Step, ...]
    seconds: float
    seed: int


def name(part: Part) -> str:
    return _('the %s %s') % (COLOURS[part.colour], KINDS[part.kind])


def freq(value: float) -> float:
    """The tone a slider makes at *value*."""
    return 220.0 * 2 ** (1.5 * value)


def _build(level: Grade, draw: random.Random) -> Optional[Job]:
    cells = [(f, c, r) for f in level.faces for c in (-1, 0, 1)
             for r in (-1, 0, 1)]
    draw.shuffle(cells)
    kinds = [BUTTON, SWITCH] if level.rung < 4 else \
        [BUTTON, SWITCH, DIAL, SLIDER]
    free = {k: draw.sample(range(len(COLOURS)), len(COLOURS)) for k in kinds}
    parts: List[Part] = []
    for n in range(level.parts):
        kind = kinds[n % len(kinds)] if n < 2 * len(kinds) else \
            draw.choice([k for k in kinds if free[k]] or kinds)
        if not free[kind]:
            continue
        f, c, r = cells[n]
        parts.append(Part(kind, free[kind].pop(), f, c, r))
    numbers = {}
    if level.rung >= 7:
        seen = set()
        for f in level.faces:
            while True:
                word = '%d' % draw.randrange(100, 1000)
                if word not in seen:
                    break
            seen.add(word)
            numbers[f] = word
    state: List[object] = [False if p.kind in (BUTTON, SWITCH) else
                           draw.randrange(NOTCHES) if p.kind == DIAL else
                           round(draw.uniform(0.3, 0.7), 2) for p in parts]
    secrets = tuple(draw.randrange(NOTCHES) for _p in parts)
    start = tuple(state)
    of = lambda kind: [i for i, p in enumerate(parts) if p.kind == kind]  # noqa

    def describe(i: int) -> str:
        p = parts[i]
        if level.relate and p.face < 4 and draw.random() < 0.6:
            near = [(j, q) for j, q in enumerate(parts) if j != i and
                    q.face == p.face and q.row == p.row and
                    abs(q.col - p.col) == 1]
            if near:
                j, q = draw.choice(near)
                side = _('left') if p.col < q.col else _('right')
                return _('the %s %s of %s') % (KINDS[p.kind], side, name(q))
        return name(p)

    steps: List[Step] = []
    seconds = 0.0
    last = -1
    for _s in range(level.steps * 6):
        if len(steps) == level.steps:
            break
        for _try in range(30):
            kind = draw.choice(level.orders)
            if kind in ('press', 'flip'):
                pool = of(BUTTON if kind == 'press' else SWITCH)
            elif kind in ('dial', 'listen'):
                pool = of(DIAL)
            elif kind in ('slide', 'match'):
                pool = of(SLIDER)
            elif kind == 'except':
                pool = of(draw.choice((BUTTON, SWITCH)))
                if len(pool) < 3:
                    continue
            elif kind == 'facenum':
                pool = list(range(len(parts)))
            else:
                pool = [0]
            pool = [i for i in pool if i != last] if kind != 'type' else pool
            if pool:
                break
        else:
            return None
        i = draw.choice(pool)
        shift, wait, tone, beeps = False, 0, -1, ()
        if kind in ('press', 'flip'):
            verb = _('press') if kind == 'press' else _('flip')
            what = describe(i)
            roll = draw.random()
            if level.wait and roll < 0.35:
                wait = draw.randint(2, 3 if level.rung < 20 else 4)
                if level.tones:
                    tone = draw.randrange(2)
                    beeps, got = [], 0
                    while got < wait:
                        b = draw.randrange(2)
                        beeps.append(b)
                        got += b == tone
                    beeps += [draw.randrange(2) for _k in range(6)]
                    text = _('After the %s %s beep, %s %s.') % (
                        ORDINALS[wait - 1],
                        _('high') if tone else _('low'), verb, what)
                else:
                    beeps = [0] * (wait + 6)
                    text = _('After the %s beep, %s %s.') % (
                        ORDINALS[wait - 1], verb, what)
                seconds += BEEP_FIRST + BEEP_GAP * len(
                    [b for b in beeps[:-6]])
            elif level.shift and roll < 0.65:
                shift = True
                text = _('Hold Shift and %s %s.') % (verb, what)
            else:
                text = _('%s %s.') % (verb.capitalize(), what)
            step = Step(kind, text, (i,), None, shift, wait, tone,
                        tuple(beeps))
        elif kind == 'except':
            k = parts[i].kind
            keep = tuple(j for j in of(k) if j != i)
            text = (_('Press every button except the %s one.')
                    if k == BUTTON else
                    _('Flip every switch except the %s one.')) % \
                COLOURS[parts[i].colour]
            step = Step('press' if k == BUTTON else 'flip', text, keep, None)
            seconds += 2.5 * len(keep)
        elif kind == 'dial':
            n = draw.choice([v for v in range(NOTCHES) if v != state[i]])
            state[i] = n
            step = Step(kind, _('Turn %s to %d.') % (describe(i), n), (i,), n)
        elif kind == 'listen':
            if state[i] == secrets[i]:
                continue
            state[i] = secrets[i]
            step = Step(kind, _('Turn %s until it tocks.') % describe(i),
                        (i,), secrets[i])
        elif kind == 'slide':
            where = draw.choice([w for w in (0, 1, 2)
                                 if w != _third(state[i])])
            state[i] = (0.0, 0.5, 1.0)[where]
            step = Step(kind, _('Slide %s to the %s.') % (
                describe(i), (_('bottom'), _('middle'), _('top'))[where]),
                (i,), where)
        elif kind == 'match':
            v = round(draw.uniform(0.1, 0.9), 2)
            if abs(v - state[i]) < 0.2:
                continue
            state[i] = v
            step = Step(kind, _('Slide %s until it matches the hum.')
                        % describe(i), (i,), v)
        elif kind == 'type':
            word = '%d' % draw.randrange(100, 1000 if level.rung < 13
                                         else 100000)
            step = Step('type', _('Type %s.') % word, (), word)
        else:
            step = Step('type', _('Type the number on the face with %s.')
                        % name(parts[i]), (i,), numbers[parts[i].face])
        if kind == 'except' or step.kind == 'type' and not step.targets:
            last = -1
        else:
            last = i
        steps.append(step)
        seconds += level.pace
    if len(steps) < level.steps:
        return None
    return Job(level, tuple(parts), numbers, secrets, start, tuple(steps),
               seconds, draw.randrange(1 << 30))


def _third(v: float) -> int:
    return 0 if v <= 0.15 else 2 if v >= 0.85 else 1 if 0.4 <= v <= 0.6 \
        else -1


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Job:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _try in range(60):
        job = _build(level, random.Random(draw.getrandbits(32)))
        if job is not None and play(job)[0]:
            return job
    raise RuntimeError('no job for rung %d' % rung)


def turned(yaw: float, pitch: float, p: Vec) -> Vec:
    a, b = math.radians(yaw), math.radians(pitch)
    x = p[0] * math.cos(a) + p[2] * math.sin(a)
    z = -p[0] * math.sin(a) + p[2] * math.cos(a)
    return (x, p[1] * math.cos(b) - z * math.sin(b),
            p[1] * math.sin(b) + z * math.cos(b))


def wrap(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


class Run(H.HandRun):
    def __init__(self, job: Job) -> None:
        super().__init__(job.seconds)
        self.job, self.level = job, job.level
        self.yaw, self.pitch = (18.0, 14.0) if job.level.rung < 4 else \
            (25.0, 20.0)
        self.state = list(job.start)
        self.step_no = 0
        self.done: set = set()
        self.typed = 0
        self.since = 0.0               # when this order came up
        self.grab: object = None       # None, 'turn', or a part
        self.pull = 0.0                # how far a dial has been dragged
        self.from_notch = 0
        self.last = (self.hand.x, self.hand.y)
        self.beeped = 0
        self.hum_at = 0.4
        self.tone_at = 0.0
        self.noise = random.Random(job.seed)
        self.noise_at = 1.0

    # --- where things are
    def local(self, i: int, along: float = 0.0) -> Vec:
        p = self.job.parts[i]
        n, r, u = FACES[p.face]
        return add(add(n, scale(r, p.col * PITCH)),
                   scale(u, p.row * PITCH + along))

    def world(self, p: Vec) -> Vec:
        return turned(self.yaw, self.pitch, p)

    def facing(self, face: int) -> float:
        n = self.world(FACES[face][0])
        return dot(n, unit(sub(EYE, n)))

    def spot(self, i: int) -> Optional[Tuple[float, float, float]]:
        """(x, y, radius) of part *i* on the screen, or None if its face
        is turned away. A slider's spot is its handle."""
        p = self.job.parts[i]
        if self.facing(p.face) < 0.12:
            return None
        along = 0.0
        if p.kind == SLIDER:
            along = (2 * self.state[i] - 1) * TRACK
        q = VIEW.see(self.world(self.local(i, along)))
        if q is None:
            return None
        size = (0.17, 0.17, 0.24, 0.13)[p.kind]
        return q[0], q[1], max(13.0, VIEW.size(size, q[2]))

    def track(self, i: int):
        a = VIEW.see(self.world(self.local(i, -TRACK)))
        b = VIEW.see(self.world(self.local(i, TRACK)))
        return a, b

    def hit(self) -> Optional[int]:
        best, depth = None, 1e9
        for i in range(len(self.job.parts)):
            s = self.spot(i)
            if s is None:
                continue
            if math.hypot(self.hand.x - s[0], self.hand.y - s[1]) <= s[2]:
                z = self.world(self.local(i))[2]
                if -z < depth:
                    best, depth = i, -z
        return best

    @property
    def order(self) -> Optional[Step]:
        steps = self.job.steps
        return steps[self.step_no] if self.step_no < len(steps) else None

    def reading(self) -> str:
        """The order as the screen shows it now."""
        step = self.order
        if step is None:
            return ''
        if self.level.show and self.t - self.since > self.level.show:
            return ''
        return step.text

    def counted(self) -> int:
        """Beeps of the kind the order counts, so far."""
        step = self.order
        if step is None or not step.wait:
            return 0
        heard = step.beeps[:self.beeped]
        return len(heard) if step.tone < 0 else \
            sum(1 for b in heard if b == step.tone)

    # --- the hand
    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        self.last = (self.hand.x, self.hand.y)
        i = self.hit()
        self.grab = 'turn' if i is None else i
        if i is not None and self.job.parts[i].kind == DIAL:
            self.pull, self.from_notch = 0.0, self.state[i]

    def release(self) -> None:
        if not self.hand.down:
            return
        self.hand.down = False
        grab, self.grab = self.grab, None
        if self.result is not None or grab is None or grab == 'turn':
            return
        part = self.job.parts[grab]
        step = self.order
        if part.kind in (BUTTON, SWITCH):
            if self.hit() != grab:
                return
            if part.kind == SWITCH:
                self.state[grab] = not self.state[grab]
            self.note(0.08, 300.0 if part.kind == BUTTON else 420.0, CLICK,
                      0.6)
            if step.kind not in ('press', 'flip') or \
                    grab not in step.targets or grab in self.done:
                return self._fail(_('That was the wrong control'))
            if step.wait and self.counted() < step.wait:
                return self._fail(_('Too soon'))
            if step.shift and not self.holding(SHIFT):
                return self._fail(_('Shift was not held'))
            self.done.add(grab)
            if len(self.done) == len(step.targets):
                self._next()
            return
        if step.targets != (grab,):
            return
        v = self.state[grab]
        if step.kind in ('dial', 'listen') and v == step.value:
            self._next()
        elif step.kind == 'slide' and _third(v) == step.value:
            self._next()
        elif step.kind == 'match' and abs(v - step.value) <= self.level.slack:
            self._next()

    def key(self, digit: int) -> None:
        step = self.order
        if self.result is not None or step is None:
            return
        self.note(0.05, 500.0, CLICK, 0.4)
        if step.kind != 'type' or step.value[self.typed] != '%d' % digit:
            return self._fail(_('That was the wrong key'))
        self.typed += 1
        if self.typed == len(step.value):
            self._next()

    def _fail(self, why: str) -> None:
        self.note(0.4, 90.0, BUZZ, 0.6)
        self.result = (False, why)

    def _next(self) -> None:
        self.step_no += 1
        self.done, self.typed = set(), 0
        self.since, self.beeped = self.t, 0
        self.hum_at = self.t + 0.4
        for j, semis in enumerate((0, 7)):
            self.note(0.2, 660.0 * 2 ** (semis / 12.0), TOCK, 0.45,
                      at=self.t + 0.08 * j)
        if self.step_no >= len(self.job.steps):
            self.result = (True, _('Every order carried out'))

    # --- the clock
    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.controls(control)
        self.t += dt
        hx, hy = self.hand.x, self.hand.y
        dx, dy = hx - self.last[0], hy - self.last[1]
        self.last = (hx, hy)
        grab = self.grab
        if grab == 'turn':
            self.yaw = wrap(self.yaw + dx * TURN)
            self.pitch = max(-90.0, min(90.0, self.pitch - dy * TURN))
        else:
            self.yaw = wrap(self.yaw + self.level.spin * dt)
        if isinstance(grab, int):
            part = self.job.parts[grab]
            if part.kind == DIAL:
                self.pull += dx
                n = (self.from_notch + int(round(self.pull / NOTCH))) \
                    % NOTCHES
                if n != self.state[grab]:
                    self.state[grab] = n
                    step = self.order
                    if n == self.job.secrets[grab] and step is not None \
                            and step.kind == 'listen':
                        self.note(0.3, 880.0, TOCK, 0.6)
                    else:
                        self.note(0.04, 700.0, TICK, 0.35)
            elif part.kind == SLIDER:
                a, b = self.track(grab)
                if a is not None and b is not None:
                    vx, vy = b[0] - a[0], b[1] - a[1]
                    d2 = vx * vx + vy * vy
                    if d2 > 16.0:
                        self.state[grab] = max(0.0, min(1.0, (
                            (hx - a[0]) * vx + (hy - a[1]) * vy) / d2))
                if self.t >= self.tone_at:
                    self.tone_at = self.t + 0.12
                    self.note(0.14, freq(self.state[grab]), TONE, 0.4)
        step = self.order
        if step is not None and step.wait:
            while self.beeped < len(step.beeps) and self.t >= self.since + \
                    BEEP_FIRST + BEEP_GAP * self.beeped:
                high = step.beeps[self.beeped]
                self.note(0.15, 1320.0 if high else 660.0, BEEP, 0.5)
                self.beeped += 1
        if step is not None and step.kind == 'match' and \
                self.t >= self.hum_at:
            self.hum_at = self.t + 0.9
            self.note(0.5, freq(step.value), HUM, 0.3)
        if self.level.noise and self.t >= self.noise_at:
            self.noise_at = self.t + self.noise.uniform(0.4, 1.6)
            self.note(0.06, self.noise.choice((240.0, 380.0, 520.0, 990.0)),
                      TICK, 0.25, pan=self.noise.uniform(-1, 1))
        if self.result is None and self.t >= self.end:
            self._fail(_('Out of time'))


def act(run: Run, port: int) -> None:
    if port < H.PRESS:
        run.hand.move(port)
    elif port == H.PRESS:
        run.press()
    elif port == H.RELEASE:
        run.release()
    elif DIGIT <= port < DIGIT + 10:
        run.key(port - DIGIT)


# --- the reference ------------------------------------------------------------------

ANCHOR = (70.0, 300.0)
RIGHT_S, LEFT_S = 3 * 3 + 2, 2 * 3 + 2


def _swing(run: Run, face: int) -> Tuple[float, float]:
    """How far the yaw and pitch are from showing *face*."""
    yaw, pitch = FRONT[face]
    if yaw is None:
        yaw = round(run.yaw / 90.0) * 90.0
    lead = run.level.spin * 0.4
    return wrap(yaw - lead - run.yaw), pitch - run.pitch


def autopilot(run: Run) -> List[int]:
    """Do the current order the plain way, one port a step."""
    step = run.order
    if run.result is not None or step is None:
        return []
    hand = run.hand
    if step.kind == 'type' and not step.targets:
        return [DIGIT + int(step.value[run.typed])]
    todo = [i for i in step.targets if i not in run.done]
    i = todo[0]
    part = run.job.parts[i]
    dyaw, dpitch = _swing(run, part.face)
    turning = run.grab == 'turn'
    if run.facing(part.face) < 0.8 or \
            turning and max(abs(dyaw), abs(dpitch)) > 6.0:
        if hand.down and not turning:
            return [H.RELEASE]
        if not hand.down:
            # Start from the side that leaves room to drag.
            ax = ANCHOR[0] if dyaw > 0 else H.W - ANCHOR[0]
            move = H.toward(hand, ax, ANCHOR[1])
            return [move] if move is not None else [H.PRESS]
        if abs(dyaw) >= abs(dpitch):
            need, way = abs(dyaw) / TURN, (3 if dyaw > 0 else 2)
            stuck = hand.x >= H.W - 1 if dyaw > 0 else hand.x <= 1
        else:
            need, way = abs(dpitch) / TURN, (1 if dpitch > 0 else 0)
            stuck = hand.y <= 1 if dpitch > 0 else hand.y >= H.H - 1
        if stuck:
            return [H.RELEASE]
        size = 0 if need >= 80 else 1 if need >= 20 else 2
        return [way * 3 + size]
    if turning:
        return [H.RELEASE]
    if step.kind == 'type':
        return [DIGIT + int(step.value[run.typed])]
    spot = run.spot(i)
    if spot is None:
        return []
    if not hand.down:
        move = H.toward(hand, spot[0], spot[1], tol=4.0)
        if move is not None:
            return [move]
        if step.wait and run.counted() < step.wait:
            return []
        if step.shift and not run.holding(SHIFT):
            return [SHIFT]
        return [H.PRESS]
    if run.grab != i:
        return [H.RELEASE]
    if part.kind in (BUTTON, SWITCH):
        return [H.RELEASE]
    if part.kind == DIAL:
        gap = (step.value - run.state[i]) % NOTCHES
        if gap == 0:
            return [H.RELEASE]
        return [RIGHT_S if gap <= NOTCHES // 2 else LEFT_S]
    if step.kind == 'slide':
        want, slack = (0.0, 0.5, 1.0)[step.value], 0.08
    else:
        want, slack = step.value, 0.6 * run.level.slack
    a, b = run.track(i)
    if a is None or b is None:
        return [H.RELEASE]
    err = want - run.state[i]
    if abs(err) <= slack:
        return [H.RELEASE]
    vx, vy = b[0] - a[0], b[1] - a[1]
    need = abs(err) * math.hypot(vx, vy)
    size = 0 if need >= 80 else 1 if need >= 20 else 2
    if abs(vy) >= abs(vx):
        way = 0 if err * vy > 0 else 1
    else:
        way = 3 if err * vx > 0 else 2
    return [way * 3 + size]


def play(job: Job, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(job), pilot, EVENTS, act, dt)
