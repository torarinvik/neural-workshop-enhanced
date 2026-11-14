# -*- coding: utf-8 -*-
"""Camera: the world, the poses and the ladder, with no window in sight.

The player stands in a field of objects and is shown a photograph taken
somewhere in it. The task is to go and stand where the photographer
stood, look where they looked, and say so. It is visual localisation —
the oldest problem in robot navigation and one people do every time
they line up a holiday photo with the view in front of them — and it
takes three things at once: working out from a flat picture where in a
three-dimensional scene it was taken, planning a way there, and the
fine motor control to land on it.

**The match is judged on the pose, never on pixels.** A pose is a
position and a direction of view, the game knows the photographer's
exactly, and the error is two plain numbers: how far away the eye is,
in metres, and how far off the line of sight is, in degrees. Comparing
images instead sounds more natural and is worse in every way that
matters — a large object filling the frame swamps it, lighting moves
it, and a tolerance in "image difference" means nothing anyone can
reason about.

**The ladder has no top.** Every rung is a formula in the rung number
rather than a row in a table, and the two tolerances shrink
geometrically for ever: rung one accepts anywhere within three metres
and thirty degrees with a meter that says how warm you are, and by
rung forty the eye has to be placed to within a fraction of a
millimetre. Somewhere past rung twenty it is beyond any human hand,
and past that it is beyond anything at all, which is what a test of
superhuman precision has to look like. The world grows with the rung
too — more objects, a larger field, objects that look more and more
alike, viewpoints off the ground, occluders — up to sizes that keep a
frame drawable, after which the tolerances carry the difficulty on
their own.

**A photograph has to be unambiguous to be fair.** A target is only
dealt if enough distinct objects sit well inside its frame, so there
is something to line up against; a viewpoint looking at empty ground
is rejected and another drawn.

Nothing here imports pyglet, so the geometry is tested without a GL
context.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

#: Field of view of both the player's camera and the photograph's,
#: vertical, in degrees. The same lens for both: matching through two
#: different lenses is a different and much nastier problem.
FOV = 60.0

#: The aspect ratio the photograph is composed for, and the one the
#: player's view is drawn at. Fixed so the frame test below is the frame
#: the player actually sees.
ASPECT = 16.0 / 9.0

#: Standing eye height, metres.
EYE = 1.6

#: How close to an object the eye may be when a target is chosen.
STANDOFF = 0.6

#: The shapes an object can be. Names only; the renderer owns the meshes.
SHAPES = ('box', 'ball', 'cylinder', 'cone', 'pyramid', 'ring')

#: A palette chosen for being told apart at a glance and in shade, so an
#: early rung's objects are all different from each other on sight.
PALETTE = (
    (0.86, 0.22, 0.20), (0.18, 0.46, 0.84), (0.95, 0.76, 0.18),
    (0.20, 0.64, 0.32), (0.58, 0.30, 0.72), (0.96, 0.52, 0.16),
    (0.10, 0.70, 0.74), (0.88, 0.40, 0.62), (0.45, 0.32, 0.20),
    (0.92, 0.92, 0.90), (0.22, 0.22, 0.26), (0.64, 0.80, 0.28),
)

#: Above these the world stops growing, and only the tolerances keep
#: rising. A frame has to stay drawable at sixty a second.
MOST_OBJECTS = 260
LARGEST_FIELD = 120.0


class Grade(NamedTuple):
    """Everything one rung of the ladder decides."""

    rung: int
    #: How far the eye may be from the photographer's, metres.
    reach: float
    #: How far the line of sight may be off, degrees.
    aim: float
    objects: int
    #: Half the side of the square field, metres.
    field: float
    #: How many different-looking kinds of object there are. When this
    #: is at least ``objects`` every object is unique; at one, they are
    #: all the same object.
    kinds: int
    #: How far the photograph's eye may rise above or sink below
    #: standing height, metres. Nought keeps it at eye level.
    lift: float
    #: How far it may look up or down, degrees.
    tilt: float
    #: Large blocks that hide one part of the field from another.
    occluders: int
    #: How far from the photographer the player starts, metres.
    start: float
    #: How far the player's starting heading is off, at most, degrees.
    turn: float
    #: Show a meter that says how close the current view is.
    meter: bool
    #: Objects that must sit well inside the photograph.
    anchors: int


def grade(rung: int) -> Grade:
    """The rung's settings. Defined for every rung from one upwards."""
    r = max(1, int(rung))
    k = r - 1
    objects = min(MOST_OBJECTS, 4 + int(round(2.2 * k + 0.06 * k * k)))
    field = min(LARGEST_FIELD, 7.0 + 1.6 * k + 0.04 * k * k)
    # Every object its own look for the first rungs; then kinds fall off
    # until, at the very top of the world's growth, there are three.
    distinct = len(SHAPES) * len(PALETTE)
    kinds = max(3, min(distinct, int(round(objects * 0.92 ** max(0, k - 6)))))
    kinds = min(kinds, objects)
    return Grade(
        rung=r,
        reach=3.0 * 0.72 ** k,
        aim=30.0 * 0.76 ** k,
        objects=objects,
        field=field,
        kinds=kinds,
        lift=0.0 if r < 6 else min(field * 0.25, 0.5 * (r - 5)),
        tilt=6.0 if r < 6 else min(70.0, 6.0 + 4.0 * (r - 5)),
        occluders=0 if r < 8 else min(40, (r - 7) * 2),
        start=min(field * 1.4, 1.2 + 1.3 * k),
        turn=min(180.0, 15.0 + 22.0 * k),
        meter=r <= 3,
        anchors=2 if r < 5 else 3,
    )


class Pose(NamedTuple):
    """Where an eye is and where it looks. Yaw 0 looks down -z; pitch up
    is positive. Degrees, metres, y up."""

    x: float
    y: float
    z: float
    yaw: float
    pitch: float

    def forward(self) -> Tuple[float, float, float]:
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        return (-math.sin(yaw) * math.cos(pitch), math.sin(pitch),
                -math.cos(yaw) * math.cos(pitch))


def distance(one: Pose, two: Pose) -> float:
    """How far apart two eyes are, metres."""
    return math.sqrt((one.x - two.x) ** 2 + (one.y - two.y) ** 2
                     + (one.z - two.z) ** 2)


def angle(one: Pose, two: Pose) -> float:
    """How far apart two lines of sight are, degrees."""
    a, b = one.forward(), two.forward()
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.degrees(math.acos(dot))


def matches(pose: Pose, target: Pose, level: Grade) -> bool:
    return (distance(pose, target) <= level.reach
            and angle(pose, target) <= level.aim)


def closeness(pose: Pose, target: Pose, level: Grade) -> float:
    """A warmth reading, one at a match and falling towards nought.

    Each error is measured in units of its own tolerance and the worse
    one decides, so the meter cannot be pinned high by standing in the
    right place facing the wrong way.
    """
    worst = max(distance(pose, target) / level.reach,
                angle(pose, target) / level.aim)
    return 1.0 / (1.0 + max(0.0, worst - 1.0) * 0.35)


class Thing(NamedTuple):
    """One object in the field. Sits on the ground at (x, z)."""

    shape: str
    colour: Tuple[float, float, float]
    x: float
    z: float
    size: float         # its height, and roughly its width
    spin: float         # turn about the vertical, degrees
    occluder: bool = False

    @property
    def radius(self) -> float:
        """Footprint radius, for keeping eyes and things apart."""
        return self.size * (1.2 if self.occluder else 0.62)


class Scene(NamedTuple):
    level: Grade
    things: Tuple[Thing, ...]
    target: Pose
    start: Pose


class Unbuildable(Exception):
    """No acceptable photograph was found for this field."""


def _kinds(level: Grade, rng: random.Random
           ) -> List[Tuple[str, Tuple[float, float, float]]]:
    every = [(shape, colour) for shape in SHAPES for colour in PALETTE]
    rng.shuffle(every)
    return every[:max(1, level.kinds)]


def _place_things(level: Grade, rng: random.Random) -> List[Thing]:
    kinds = _kinds(level, rng)
    things: List[Thing] = []
    field = level.field
    for index in range(level.occluders):
        size = rng.uniform(2.2, 3.6)
        for _try in range(60):
            x, z = rng.uniform(-field, field), rng.uniform(-field, field)
            if all(math.hypot(x - t.x, z - t.z) > t.radius + size * 1.2 + 1.0
                   for t in things):
                things.append(Thing('box', (0.62, 0.60, 0.56), x, z, size,
                                    rng.uniform(0, 90), occluder=True))
                break
    for index in range(level.objects):
        shape, colour = kinds[index % len(kinds)]
        size = rng.uniform(0.6, 1.6)
        for _try in range(80):
            x, z = rng.uniform(-field, field), rng.uniform(-field, field)
            if all(math.hypot(x - t.x, z - t.z)
                   > t.radius + size * 0.62 + 0.5 for t in things):
                things.append(Thing(shape, colour, x, z, size,
                                    rng.uniform(0, 360)))
                break
    return things


def in_frame(pose: Pose, point: Tuple[float, float, float],
             margin: float = 0.8) -> Optional[float]:
    """How far in front of *pose* the point is, if it is inside the
    central *margin* of the frame; ``None`` otherwise."""
    yaw, pitch = math.radians(pose.yaw), math.radians(pose.pitch)
    fwd = pose.forward()
    right = (math.cos(yaw), 0.0, -math.sin(yaw))
    up = (math.sin(yaw) * math.sin(pitch), math.cos(pitch),
          math.cos(yaw) * math.sin(pitch))
    rel = (point[0] - pose.x, point[1] - pose.y, point[2] - pose.z)
    depth = sum(a * b for a, b in zip(rel, fwd))
    if depth <= 0.3:
        return None
    half_v = math.tan(math.radians(FOV) / 2.0)
    half_h = half_v * ASPECT
    across = sum(a * b for a, b in zip(rel, right)) / depth
    lift = sum(a * b for a, b in zip(rel, up)) / depth
    if abs(across) > half_h * margin or abs(lift) > half_v * margin:
        return None
    return depth


def anchors(pose: Pose, things: Sequence[Thing], field: float) -> int:
    """How many non-occluder objects sit well inside the frame, near
    enough to be made out — and nought unless one of them is close.

    A photograph of a few specks on the horizon is not one anybody can
    line up on, at any rung; the close one is what fixes the distance.
    Occlusion is not traced: a target needs its anchors *before*
    anything can hide them, and the occluders themselves are landmarks
    for the player regardless."""
    far = 6.0 + field * 0.5
    near = max(4.0, field * 0.3)
    seen, nearest = 0, float('inf')
    for thing in things:
        if thing.occluder:
            continue
        depth = in_frame(pose, (thing.x, thing.size * 0.5, thing.z))
        if depth is not None and depth <= far:
            seen += 1
            nearest = min(nearest, depth)
    return seen if nearest <= near else 0


def _clear(x: float, z: float, things: Sequence[Thing]) -> bool:
    return all(math.hypot(x - t.x, z - t.z) > t.radius + STANDOFF
               for t in things)


def _target(level: Grade, things: Sequence[Thing],
            rng: random.Random) -> Pose:
    field = level.field
    for _try in range(4000):
        x, z = rng.uniform(-field, field), rng.uniform(-field, field)
        if not _clear(x, z, things):
            continue
        y = max(0.3, EYE + rng.uniform(-level.lift, level.lift))
        # Aimed at something, give or take a third of the frame: a
        # photographer points the camera at the scene, not at the sky.
        subject = rng.choice([t for t in things if not t.occluder])
        yaw = math.degrees(math.atan2(-(subject.x - x), -(subject.z - z)))
        yaw += rng.uniform(-FOV * ASPECT / 6.0, FOV * ASPECT / 6.0)
        flat = math.hypot(subject.x - x, subject.z - z) or 1.0
        down = math.degrees(math.atan2(subject.size * 0.5 - y, flat))
        pitch = max(-level.tilt, min(level.tilt,
                                     down + rng.uniform(-level.tilt,
                                                        level.tilt) * 0.5))
        pose = Pose(x, y, z, yaw % 360.0, pitch)
        if anchors(pose, things, field) >= level.anchors:
            return pose
    raise Unbuildable('no viewpoint sees %d objects' % level.anchors)


def _start(level: Grade, target: Pose, things: Sequence[Thing],
           rng: random.Random) -> Pose:
    """Somewhere *level.start* away, facing up to *level.turn* off.

    Never already matching: a deal the player has won before moving
    teaches nothing, so the start is pushed out past both tolerances.
    """
    bound = level.field + 2.0
    # Behind the photographer at the bottom of the ladder, so the scene
    # in the photo is the scene in front of you; spreading round to any
    # side as the turn allowance grows.
    behind = math.radians(target.yaw)
    for _try in range(400):
        heading = behind + math.radians(rng.uniform(-level.turn, level.turn))
        away = max(level.start, level.reach * 1.6)
        x = target.x + math.sin(heading) * away
        z = target.z + math.cos(heading) * away
        if abs(x) > bound or abs(z) > bound or not _clear(x, z, things):
            continue
        yaw = (target.yaw + rng.uniform(-level.turn, level.turn)) % 360.0
        pose = Pose(x, EYE, z, yaw, 0.0)
        if not matches(pose, target, level):
            return pose
    # The field is crowded around the target; stand on it and turn away.
    return Pose(target.x, EYE, target.z,
                (target.yaw + 180.0) % 360.0, 0.0)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Scene:
    """A field, a photograph somewhere in it, and where the player starts."""
    rng = rng or random.Random(seed)
    level = grade(rung)
    for _attempt in range(30):
        things = _place_things(level, rng)
        try:
            target = _target(level, things, rng)
        except Unbuildable:
            continue
        return Scene(level, tuple(things), target,
                     _start(level, target, things, rng))
    raise Unbuildable('rung %d would not deal' % level.rung)


#: The moves a step can make, in the player's own frame: forward, back,
#: left, right, turn left, turn right, look up, look down, rise, sink.
MOVES = ('forward', 'back', 'left', 'right', 'turn_left', 'turn_right',
         'look_up', 'look_down', 'rise', 'sink')

#: The size of one whole step of each kind of move: metres for the
#: four walks and the two vertical moves, degrees for the four turns.
STEP_METRES = 1.0
STEP_DEGREES = 15.0
STEP_RISE = 0.5


def moved(pose: Pose, move: str, amount: float, level: Grade) -> Pose:
    """*pose* after *amount* of *move* (one is a whole step).

    Walking is level whatever the pitch, as it is for a person. The eye
    is kept inside the field's fence, above the ground, and pitch inside
    a right angle of the horizon; rising and sinking are only allowed on
    rungs whose photographs can be taken off the ground.
    """
    x, y, z, yaw, pitch = pose
    rad = math.radians(yaw)
    fwd = (-math.sin(rad), -math.cos(rad))
    right = (math.cos(rad), -math.sin(rad))
    walk = STEP_METRES * amount
    if move == 'forward':
        x, z = x + fwd[0] * walk, z + fwd[1] * walk
    elif move == 'back':
        x, z = x - fwd[0] * walk, z - fwd[1] * walk
    elif move == 'right':
        x, z = x + right[0] * walk, z + right[1] * walk
    elif move == 'left':
        x, z = x - right[0] * walk, z - right[1] * walk
    elif move == 'turn_left':
        yaw = yaw + STEP_DEGREES * amount
    elif move == 'turn_right':
        yaw = yaw - STEP_DEGREES * amount
    elif move == 'look_up':
        pitch = pitch + STEP_DEGREES * amount
    elif move == 'look_down':
        pitch = pitch - STEP_DEGREES * amount
    elif move == 'rise' and level.lift > 0:
        y = y + STEP_RISE * amount
    elif move == 'sink' and level.lift > 0:
        y = y - STEP_RISE * amount
    bound = level.field + 2.0
    x = max(-bound, min(bound, x))
    z = max(-bound, min(bound, z))
    y = max(0.3, min(EYE + level.lift + 1.0, y))
    pitch = max(-89.0, min(89.0, pitch))
    return Pose(x, y, z, yaw % 360.0, pitch)


__all__ = ['ASPECT', 'EYE', 'FOV', 'Grade', 'MOVES', 'PALETTE', 'Pose',
           'SHAPES', 'Scene', 'Thing', 'Unbuildable', 'angle', 'anchors',
           'closeness', 'deal', 'distance', 'grade', 'in_frame', 'matches',
           'moved']
