# -*- coding: utf-8 -*-
"""Live Claw Machine: a real claw on a real rope over a pit of prizes.

The cabinet of an arcade crane, simulated as the thing itself and not
as a drawing of it. A gantry carries a winch about the top; from the
winch hangs a rope, and on the rope a claw of three hinged fingers,
which swings when the gantry starts and stops, turns on its rope, and
lands on whatever is under it. The prizes are loose bodies heaped in
the pit: they roll, lean on each other and slide out of a weak grip.
In the front left corner is the chute, fenced on its two inner sides.

One play is what a play is on the machine: steer the gantry with the
stick while the time runs; press the button (or run out of time) and
the machine takes over -- the claw is let down on its rope until it
rests on something, the fingers close, the winch winds it up, the
gantry drives home over the chute, the fingers open. Whatever falls
down the chute is won.

The grip is the machine's own, set by its operator as on the real
thing: how hard the fingers close, and how much of that is kept once
the claw has left the heap. On the low rungs it is a generous machine;
higher up it is an honest one.

The ladder:

* rungs 1-3: one ball in an empty pit, a firm grip that holds, a rope
  that hardly swings;
* rungs 4-6: three prizes of different shapes, any of them a win;
* rungs 7-9: six prizes; the grip slackens once the claw is up;
* rungs 10-12: a heap of ten, a rope that swings freely, less time;
* rungs 13-15: only the gold prize counts;
* from rung 16: a weaker grip, heavier prizes, more of them and less
  time, a little worse every rung.

Distances are metres, times seconds, x to the right, y away from the
player, z up; the pit's floor is z = 0.

For the agent boundary: ports 0-3 drive the gantry left, right, away
and nearer for the step they are sent in; port 4 is the button; port 5
walks round to the other window (front, then the right side), as a
player does to judge how far in the claw is.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

import mujoco

from .i18n import _

LEFT, RIGHT, AWAY, NEAR, DROP, VIEW = range(6)
PORTS = 6
EVENTS = (DROP, VIEW)

HALF = 0.30                    # the pit is x, y in [-HALF, HALF]
TOP = 0.62                     # the winch's height above the floor
CHUTE = 0.17                   # the chute's side, in the front left corner
FENCE = 0.085                  # how high its fence stands
HOME = (-HALF + CHUTE / 2, -HALF + CHUTE / 2)
REACH = HALF - 0.065           # how far from the middle the gantry goes
SPEED = 0.16                   # the gantry, metres a second
ACCEL = 1.2                    # how briskly it starts and stops
ROPE0 = 0.10                   # rope out when the claw is wound up
PAY_OUT = 0.24                 # the winch letting down, metres a second
WIND_IN = 0.17                 # and winding up
EYE = 0.055                    # the rope's eye above the claw's hub
TIP = 0.150                    # the fingertips below the hub, open
FINGERS = 3
SHUT = 0.78                    # the finger hinge's range, radians
SPRING = 0.06                  # the spring that opens them, N m a radian
STEP = 0.002

COLOURS = ((0.90, 0.30, 0.32), (0.30, 0.55, 0.92), (0.45, 0.80, 0.45),
           (0.78, 0.45, 0.86), (0.95, 0.60, 0.25), (0.30, 0.80, 0.80),
           (0.95, 0.50, 0.70))
GOLD = (0.98, 0.80, 0.22)


class Grade(NamedTuple):
    rung: int
    prizes: int
    kinds: Tuple[str, ...]
    grip: float          # the torque closing each finger, N m
    hold: float          # the share of it kept once the claw is up
    calm: float          # how strongly the claw's swing dies away
    seconds: float       # at the stick
    gold: bool           # only the gold prize counts
    heavy: float         # the prizes' density against plain plush


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        return Grade(r, 1, ('ball',), 0.30, 1.0, 0.9, 40.0, False, 1.0)
    if r < 7:
        return Grade(r, 3, ('ball', 'egg', 'box'), 0.26, 1.0, 0.6, 40.0,
                     False, 1.0)
    if r < 10:
        return Grade(r, 6, ('ball', 'egg', 'box'), 0.22, 0.7, 0.35, 35.0,
                     False, 1.0)
    if r < 13:
        return Grade(r, 10, ('ball', 'egg', 'box', 'puck'), 0.2, 0.6, 0.12,
                     30.0, False, 1.1)
    if r < 16:
        return Grade(r, 12, ('ball', 'egg', 'box', 'puck'), 0.2, 0.6, 0.12,
                     30.0, True, 1.1)
    k = r - 16
    return Grade(r, min(18, 13 + k // 2), ('ball', 'egg', 'box', 'puck'),
                 max(0.13, 0.18 * 0.97 ** k), max(0.45, 0.55 - 0.01 * k),
                 0.06, max(15.0, 28.0 - k), True, min(1.5, 1.15 + 0.03 * k))


class Prize(NamedTuple):
    kind: str                    # 'ball', 'egg', 'box' or 'puck'
    size: Tuple[float, float, float]     # half-extents
    colour: Tuple[float, float, float]
    pos: Tuple[float, float, float]      # where it lies, settled
    quat: Tuple[float, float, float, float]


class Cabinet(NamedTuple):
    level: Grade
    prizes: Tuple[Prize, ...]    # the first is the gold one
    seed: int


class Shape(NamedTuple):
    """One solid, where it is now: for whoever draws it."""
    kind: str                    # 'box', 'ball' (an ellipsoid) or 'rod'
    size: Tuple[float, float, float]
    pos: Tuple[float, float, float]
    mat: Tuple[float, ...]       # its turn, nine numbers by rows
    colour: Tuple[float, float, float]
    part: str                    # 'prize', 'gold', 'claw', 'gantry', 'cabinet'


# --- the machine as the engine has it -----------------------------------------

def _finger(k: int) -> str:
    a = 2 * math.pi * k / FINGERS
    q = (math.cos(a / 2), 0.0, 0.0, math.sin(a / 2))
    return (
        '<body name="finger%d" pos="%.5f %.5f 0" quat="%.6f %.6f %.6f %.6f">'
        '<joint name="hinge%d" type="hinge" axis="0 1 0" range="0 %.3f" '
        'stiffness="%.4f" springref="0" damping="0.004" armature="0.0002"/>'
        '<geom class="claw" type="capsule" size="0.006" '
        'fromto="0 0 0 0.072 0 -0.052"/>'
        # The lower finger is a flat blade, as wide as a thumb: a wire
        # would let a ball squirt out between two of them.
        '<geom class="claw" type="box" size="0.004 0.012" '
        'fromto="0.072 0 -0.052 0.068 0 -0.135"/>'
        '<geom class="claw" type="box" size="0.004 0.012" '
        'fromto="0.068 0 -0.135 0.046 0 -%.3f"/>'
        '</body>'
        % (k, 0.03 * math.cos(a), 0.03 * math.sin(a), q[0], q[1], q[2], q[3],
           k, SHUT, SPRING, TIP))


def _prize_geom(p: Prize, level: Grade) -> str:
    density = 150.0 * level.heavy
    if p.kind == 'box':
        shape = 'type="box" size="%.4f %.4f %.4f"' % p.size
        density *= 0.75
    else:
        shape = 'type="ellipsoid" size="%.4f %.4f %.4f"' % p.size
    return ('<geom class="prize" %s density="%.1f"/>' % (shape, density))


def mjcf(cab: Cabinet, fixed: bool = True) -> str:
    """The cabinet for the engine. Prizes start where the deal settled
    them, or (not *fixed*) wherever they are being dropped from."""
    level = cab.level
    h, c = HALF, CHUTE
    wall = 0.012
    parts = [
        '<mujoco>',
        '<compiler angle="radian"/>',
        '<option timestep="%.4f" integrator="implicitfast" cone="elliptic" '
        'noslip_iterations="3" impratio="5"/>' % STEP,
        '<size memory="20M"/>',
        '<default>',
        '<geom condim="4" friction="0.9 0.02 0.001" solref="0.008 1"/>',
        # Plush gives: a soft, dead contact.
        # ... and does not roll: it squashes where it lies.
        '<default class="prize"><geom condim="6" friction="1.0 0.03 0.012" '
        'solref="0.018 1.1" solimp="0.85 0.95 0.004"/></default>',
        '<default class="claw"><geom condim="4" friction="0.95 0.03 0.001" '
        'solref="0.008 1" density="900"/></default>',
        '</default>',
        '<worldbody>',
        # The floor, in two slabs that leave the chute open.
        '<geom name="floor_a" type="box" pos="%.5f 0 -0.01" '
        'size="%.5f %.5f 0.01"/>' % (c / 2, h - c / 2, h),
        '<geom name="floor_b" type="box" pos="%.5f %.5f -0.01" '
        'size="%.5f %.5f 0.01"/>' % (-h + c / 2, c / 2, c / 2, h - c / 2),
        # Glass all round.
        '<geom type="box" pos="%.5f 0 0.3" size="%.4f %.4f 0.45"/>'
        % (h + wall, wall, h + 2 * wall),
        '<geom type="box" pos="%.5f 0 0.3" size="%.4f %.4f 0.45"/>'
        % (-h - wall, wall, h + 2 * wall),
        '<geom type="box" pos="0 %.5f 0.3" size="%.4f %.4f 0.45"/>'
        % (h + wall, h + 2 * wall, wall),
        '<geom type="box" pos="0 %.5f 0.3" size="%.4f %.4f 0.45"/>'
        % (-h - wall, h + 2 * wall, wall),
        # The chute's fence, and the tray under it.
        '<geom name="fence_x" type="box" pos="%.5f %.5f %.5f" '
        'size="0.005 %.5f %.5f"/>' % (-h + c + 0.005, -h + c / 2, FENCE / 2,
                                     c / 2 + 0.005, FENCE / 2),
        '<geom name="fence_y" type="box" pos="%.5f %.5f %.5f" '
        'size="%.5f 0.005 %.5f"/>' % (-h + c / 2, -h + c + 0.005, FENCE / 2,
                                     c / 2, FENCE / 2),
        '<geom name="tray" type="box" pos="%.5f %.5f -0.36" '
        'size="%.5f %.5f 0.01"/>' % (-h + c / 2, -h + c / 2, c / 2, c / 2),
        '<body name="gantry" mocap="true" pos="%.5f %.5f %.5f">'
        '<site name="winch" pos="0 0 0"/></body>' % (HOME[0], HOME[1], TOP),
        '<body name="claw" pos="%.5f %.5f %.5f">' % (HOME[0], HOME[1],
                                                    TOP - ROPE0 - EYE),
        '<freejoint name="swing"/>',
        '<site name="eye" pos="0 0 %.4f"/>' % EYE,
        '<geom class="claw" type="cylinder" size="0.034 0.012" density="1500"/>',
        '<geom class="claw" type="capsule" size="0.007" fromto="0 0 0 0 0 %.4f"/>'
        % EYE,
        # The plunger housing: weight low in the middle, as on the
        # machine, so the claw hangs true.
        '<geom class="claw" type="cylinder" size="0.016 0.02" pos="0 0 -0.03" '
        'density="2500"/>',
    ]
    parts += [_finger(k) for k in range(FINGERS)]
    parts.append('</body>')
    for i, p in enumerate(cab.prizes):
        parts.append(
            '<body name="prize%d" pos="%.5f %.5f %.5f" '
            'quat="%.6f %.6f %.6f %.6f"><freejoint/>%s</body>'
            % ((i,) + tuple(p.pos) + tuple(p.quat) + (_prize_geom(p, level),)))
    parts.append('</worldbody>')
    parts.append(
        '<tendon><spatial name="rope" limited="true" range="0 %.4f" '
        'solreflimit="0.006 1" damping="0.02">'
        '<site site="winch"/><site site="eye"/></spatial></tendon>' % ROPE0)
    parts.append('<actuator>')
    parts += ['<motor name="grip%d" joint="hinge%d" gear="1"/>' % (k, k)
              for k in range(FINGERS)]
    parts.append('</actuator>')
    parts.append('</mujoco>')
    return ''.join(parts)


# --- a deal ---------------------------------------------------------------------

def _loose(level: Grade, draw: random.Random) -> List[Prize]:
    prizes = []
    for i in range(level.prizes):
        kind = draw.choice(level.kinds)
        r = draw.uniform(0.036, 0.05)
        if kind == 'ball':
            size = (r, r, r)
        elif kind == 'egg':
            size = (r * 0.8, r * 0.8, r * 1.35)
        elif kind == 'puck':
            size = (r * 1.15, r * 1.15, r * 0.55)
        else:
            size = (r * draw.uniform(0.7, 1.0), r * draw.uniform(0.7, 1.0),
                    r * draw.uniform(0.6, 0.9))
        colour = GOLD if i == 0 else COLOURS[draw.randrange(len(COLOURS))]
        prizes.append(Prize(kind, size, colour, (0.0, 0.0, 0.0),
                            (1.0, 0.0, 0.0, 0.0)))
    return prizes


def in_chute(x: float, y: float, margin: float = 0.0) -> bool:
    return x < -HALF + CHUTE + margin and y < -HALF + CHUTE + margin


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Cabinet:
    """A cabinet with its prizes dropped in and left to come to rest."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    for attempt in range(30):
        draw = random.Random(seed * 31 + attempt)
        loose = _loose(level, draw)
        # Dropped in one after another from a little way up, over the
        # middle of the pit when there are many: a heap, not a carpet.
        spread = 0.13 if level.prizes == 1 else 0.2 if level.prizes <= 6 \
            else 0.14
        placed: List[Prize] = []
        for i, p in enumerate(loose):
            for _try in range(200):
                x = draw.uniform(-spread, spread) + 0.04
                y = draw.uniform(-spread, spread) + 0.04
                if not in_chute(x, y, 0.09) and all(
                        math.hypot(x - q.pos[0], y - q.pos[1]) > 0.105
                        or abs(q.pos[2] - (0.07 + 0.11 * (i // 4))) > 0.05
                        for q in placed):
                    break
            a = draw.uniform(0, math.pi)
            ax = [draw.gauss(0, 1) for _k in range(3)]
            n = math.sqrt(sum(v * v for v in ax)) or 1.0
            quat = (math.cos(a / 2),) + tuple(math.sin(a / 2) * v / n
                                              for v in ax)
            if level.prizes == 1:
                quat = (1.0, 0.0, 0.0, 0.0)
            placed.append(p._replace(pos=(x, y, 0.07 + 0.11 * (i // 4)),
                                     quat=quat))
        cab = Cabinet(level, tuple(placed), seed)
        model = mujoco.MjModel.from_xml_string(mjcf(cab))
        data = mujoco.MjData(model)
        bodies = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY,
                                    'prize%d' % i) for i in range(len(placed))]
        # Left until nothing moves (or it is plain that something will not).
        for _spell in range(8):
            for _k in range(int(1.0 / STEP)):
                mujoco.mj_step(model, data)
            if _spell >= 1 and all(
                    float(abs(data.cvel[b][3:]).max()) < 0.01 for b in bodies):
                break
        settled = []
        ok = True
        for i, p in enumerate(placed):
            body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY,
                                     'prize%d' % i)
            pos = tuple(float(v) for v in data.xpos[body])
            speed = float(abs(data.cvel[body][3:]).max())
            if pos[2] < 0.0 or in_chute(pos[0], pos[1], 0.02) or speed > 0.02:
                ok = False
            settled.append(p._replace(
                pos=pos, quat=tuple(float(v) for v in data.xquat[body])))
        if ok:
            return Cabinet(level, tuple(settled), seed)
    raise RuntimeError('no cabinet for rung %d' % rung)


# --- a play ---------------------------------------------------------------------

class Run:
    """One play of the machine."""

    def __init__(self, cab: Cabinet) -> None:
        self.cab = cab
        self.level = cab.level
        self.model = mujoco.MjModel.from_xml_string(mjcf(cab))
        self.data = mujoco.MjData(self.model)
        m = self.model
        name = lambda kind, n: mujoco.mj_name2id(m, kind, n)   # noqa: E731
        self.claw_body = name(mujoco.mjtObj.mjOBJ_BODY, 'claw')
        self.prize_bodies = [name(mujoco.mjtObj.mjOBJ_BODY, 'prize%d' % i)
                             for i in range(len(cab.prizes))]
        swing = name(mujoco.mjtObj.mjOBJ_JOINT, 'swing')
        self.swing_dof = int(m.jnt_dofadr[swing])
        # Air and the rope's own stiffness: what stills a swinging claw.
        m.dof_damping[self.swing_dof:self.swing_dof + 3] = \
            0.02 + 0.5 * self.level.calm
        m.dof_damping[self.swing_dof + 3:self.swing_dof + 6] = \
            0.0004 + 0.002 * self.level.calm
        self.hinges = [name(mujoco.mjtObj.mjOBJ_JOINT, 'hinge%d' % k)
                       for k in range(FINGERS)]
        self.x, self.y = HOME
        self.vx = self.vy = 0.0
        self.rope = ROPE0
        self.t = 0.0
        self.phase = 'aim'
        self.since = 0.0             # seconds in this phase
        self.slack = 0.0
        self.won: List[int] = []     # which prizes went down the chute
        self.result: Optional[Tuple[bool, str]] = None
        self.view = 0                # 0 the front window, 1 the right side
        self._bank = 0.0
        mujoco.mj_forward(self.model, self.data)

    # --- what can be seen ------------------------------------------------

    @property
    def left(self) -> float:
        return max(0.0, self.level.seconds - self.t) if self.phase == 'aim' \
            else 0.0

    def claw(self) -> Tuple[float, float, float]:
        return tuple(float(v) for v in self.data.xpos[self.claw_body])

    def prize(self, i: int) -> Tuple[float, float, float]:
        return tuple(float(v) for v in self.data.xpos[self.prize_bodies[i]])

    def closed(self) -> float:
        """How far shut the fingers are, 0 open to 1."""
        q = [float(self.data.qpos[self.model.jnt_qposadr[h]])
             for h in self.hinges]
        return sum(q) / len(q) / SHUT

    def shapes(self) -> List[Shape]:
        """Every moving solid, where it is now."""
        m, d = self.model, self.data
        out = []
        for g in range(m.ngeom):
            body = int(m.geom_bodyid[g])
            if body == 0:
                continue
            kind = int(m.geom_type[g])
            size = tuple(float(v) for v in m.geom_size[g])
            if kind == mujoco.mjtGeom.mjGEOM_BOX:
                shape = 'box'
            elif kind == mujoco.mjtGeom.mjGEOM_ELLIPSOID:
                shape = 'ball'
            elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
                shape, size = 'rod', (size[0], size[0], size[1] + size[0])
            else:
                shape, size = 'drum', (size[0], size[0], size[1])
            if body in self.prize_bodies:
                i = self.prize_bodies.index(body)
                part = 'gold' if i == 0 else 'prize'
                colour = self.cab.prizes[i].colour
            else:
                part, colour = 'claw', (0.8, 0.8, 0.84)
            out.append(Shape(shape, size,
                             tuple(float(v) for v in d.geom_xpos[g]),
                             tuple(float(v) for v in d.geom_xmat[g]),
                             colour, part))
        return out

    def rope_ends(self):
        eye = self.data.site_xpos[mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_SITE, 'eye')]
        return (self.x, self.y, TOP), tuple(float(v) for v in eye)

    # --- the machine -----------------------------------------------------

    def press(self) -> None:
        if self.phase == 'aim':
            self._go('lower')

    def _go(self, phase: str) -> None:
        self.phase = phase
        self.since = 0.0
        self.slack = 0.0

    def _drive(self, dt: float, wx: float, wy: float) -> None:
        """The gantry, toward a wanted velocity, no faster than its
        motors pick up."""
        for axis in (0, 1):
            v = self.vx if axis == 0 else self.vy
            want = wx if axis == 0 else wy
            p = self.x if axis == 0 else self.y
            dv = max(-ACCEL * dt, min(ACCEL * dt, want - v))
            v += dv
            p += v * dt
            if abs(p) > REACH:
                p = max(-REACH, min(REACH, p))
                v = 0.0
            if axis == 0:
                self.vx, self.x = v, p
            else:
                self.vy, self.y = v, p

    def _grip(self, torque: float) -> None:
        self.data.ctrl[:FINGERS] = torque

    def _tick(self, dt: float, control: Optional[int]) -> None:
        level = self.level
        self.t += dt
        self.since += dt
        wx = wy = 0.0
        if self.phase == 'aim':
            if control == LEFT:
                wx = -SPEED
            elif control == RIGHT:
                wx = SPEED
            elif control == AWAY:
                wy = SPEED
            elif control == NEAR:
                wy = -SPEED
            if self.t >= level.seconds:
                self._go('lower')
        elif self.phase == 'lower':
            longest = TOP - EYE - TIP - 0.004
            self.rope = min(longest, self.rope + PAY_OUT * dt)
            # Resting on something, the rope goes slack: the machine
            # feels that and stops letting out.
            taut = float(self.data.ten_length[0]) > self.rope - 0.006
            self.slack = 0.0 if taut else self.slack + dt
            if self.slack > 0.12 or (self.rope >= longest
                                     and self.since > 0.3):
                self._go('grip')
        elif self.phase == 'grip':
            self._grip(level.grip)
            if self.since > 0.7:
                self._go('raise')
        elif self.phase == 'raise':
            self.rope = max(ROPE0, self.rope - WIND_IN * dt)
            # Full strength to break the prize out of the heap, then
            # what the operator set.
            self._grip(level.grip * (1.0 if self.since < 0.35
                                     else level.hold))
            if self.rope <= ROPE0 and self.since > 0.5:
                self._go('carry')
        elif self.phase == 'carry':
            dx, dy = HOME[0] - self.x, HOME[1] - self.y
            far = math.hypot(dx, dy)
            if far > 0.004:
                # Slowing as it comes in, as a motor run to a stop does.
                v = min(SPEED, math.sqrt(2 * ACCEL * 0.6 * far))
                wx, wy = v * dx / far, v * dy / far
                self.since = 0.0
            elif self.since > 0.6:
                self._go('release')
        elif self.phase == 'release':
            self._grip(-0.06)
            if self.since > 1.6:
                self._judge()
        self._drive(dt, wx, wy)
        self.model.tendon_range[0, 1] = self.rope
        self.data.mocap_pos[0] = (self.x, self.y, TOP)
        mujoco.mj_step(self.model, self.data)
        for i, body in enumerate(self.prize_bodies):
            if i not in self.won and self.data.xpos[body][2] < -0.06:
                self.won.append(i)

    def _judge(self) -> None:
        if self.level.gold:
            ok = 0 in self.won
            said = _('The gold prize is yours') if ok else \
                _('A prize, but not the gold one') if self.won else \
                _('Nothing in the chute')
        else:
            ok = bool(self.won)
            said = _('A prize in the chute') if ok else \
                _('Nothing in the chute')
        self.result = (ok, said)
        self.phase = 'over'

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self._bank += dt
        while self._bank >= STEP - 1e-12 and self.result is None:
            self._bank -= STEP
            self._tick(STEP, control)


def act(run: Run, port: int) -> None:
    if port == DROP:
        run.press()
    elif port == VIEW:
        run.view = 1 - run.view


# --- a pilot --------------------------------------------------------------------

def target(run: Run) -> int:
    """The prize a careful player would go for: the gold one where it
    must be gold, else whichever lies highest and clearest."""
    if run.level.gold:
        return 0
    best, score = 0, -1e9
    for i in range(len(run.cab.prizes)):
        x, y, z = run.prize(i)
        if z < 0 or in_chute(x, y, 0.02):
            continue
        near = sum(1 for j in range(len(run.cab.prizes)) if j != i
                   and math.hypot(run.prize(j)[0] - x, run.prize(j)[1] - y)
                   < 0.09)
        edge = min(HALF - abs(x), HALF - abs(y))
        s = z * 2.0 - near * 0.03 + min(edge, 0.1) * 0.5
        if run.cab.prizes[i].kind == 'ball':
            s += 0.02
        if s > score:
            best, score = i, s
    return best


def autopilot(run: Run) -> List[int]:
    """What to send this step: steer over the target, let the claw
    hang still, press."""
    if run.phase != 'aim':
        return []
    x, y, _z = run.prize(target(run))
    x = max(-REACH, min(REACH, x))
    y = max(-REACH, min(REACH, y))
    # Where the gantry will have stopped if let go now.
    sx = run.x + run.vx * abs(run.vx) / (2 * ACCEL)
    sy = run.y + run.vy * abs(run.vy) / (2 * ACCEL)
    if abs(x - sx) > 0.004:
        return [RIGHT if x > sx else LEFT]
    if abs(run.vx) > 1e-3:
        return []
    if abs(y - sy) > 0.004:
        return [AWAY if y > sy else NEAR]
    if abs(run.vy) > 1e-3:
        return []
    cx, cy, _cz = run.claw()
    v = run.data.qvel[run.swing_dof:run.swing_dof + 2]
    still = math.hypot(cx - run.x, cy - run.y) < 0.006 and \
        math.hypot(float(v[0]), float(v[1])) < 0.02
    if still or run.left < 1.5:
        return [DROP]
    return []


def play(cab: Cabinet, pilot=autopilot, limit: float = 90.0) -> Run:
    run = Run(cab)
    dt = 1 / 60.0
    while run.result is None and run.t < limit:
        ports = pilot(run)
        control = None
        for port in ports:
            if port in EVENTS:
                act(run, port)
            else:
                control = port
        run.step(dt, control)
    return run
