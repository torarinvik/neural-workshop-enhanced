# -*- coding: utf-8 -*-
"""Buzz Wire: the wire, the loop threaded on it, and the arm that shakes.

The fairground game. A bent wire runs between two posts, a metal loop is
threaded over it, and the loop has to travel from one post to the other
without the two ever touching. Touch and the circuit closes and it buzzes.

Everything here is geometry and physics; nothing here draws. The screen
lives in :mod:`neural_workshop.ui.buzzwire` and the agent boundary in
:mod:`nwenv.buzzwire`.

Three decisions shape the whole task, and each is the answer to "what
makes this hard in a way that is worth measuring".

* **The loop is a hole, not a point.** Contact is decided between a
  *circle in space* and a *tube in space*, exactly, with no grid and no
  fudge factor. That matters because of what falls out of it for free:
  when the wire runs at an angle to the loop's axis, the tube's
  cross-section through the loop's plane is an **ellipse**, with its
  long axis stretched by ``1 / cos θ``. A wire square to the loop needs
  a hole ``2r`` wide; a wire at sixty degrees needs one twice that. So
  at a bend the loop must be *turned*, and it must be turned before the
  bend arrives rather than in it. Nobody had to write that rule down —
  it is what the geometry says, and the top of the ladder is built on it
  (see :func:`crossing_contact`).

* **The arm is a physical object.** The loop has mass, momentum and
  viscous drag; the hand has a downward sag it never quite cancels and a
  tremor that is a real Ornstein-Uhlenbeck process rather than
  per-frame white noise — which is to say it has a *correlation time*,
  a tenth of a second or less, and produces drifts you have to catch
  rather than jitter that averages out. A tenth of a second is inside
  anybody's reaction time, so what a person can do about it is hold
  still and hope; what a controller running at sixty ticks a second can
  do about it is answer it, and the gap between those two is most of
  what the word "superhuman" is doing at the top of this ladder.

* **The whole wire is in view from the first frame.** There is nothing
  hidden, nothing remembered and nothing to search for; a perfect player
  with a perfect hand scores every rung. What separates the rungs is
  precision, anticipation and how much the picture tells you about
  *depth* — which is why the camera swings towards the wire's own axis
  as the ladder climbs, until a bend towards you and a bend away from
  you look nearly alike and the only thing separating them is
  perspective and shading.

**The ladder was measured rather than described.** ``tests/bench_buzzwire.py``
flies every rung twelve times with :func:`pilot_port`, a fixed-gain
controller reading the true state through the same eleven ports a
learner has, and the shape it reports is the claim this module makes::

    rung                  gap(mm)  ticks  grip   used   buzz/m   flown
     1 a gentle bow          10.5   16.0     -   0.33     0.00   12/12
     4 a coiling run          6.5   11.0  21.0   0.34     0.00   12/12
     7 turn your wrist        4.0    8.0  10.7   0.37     0.00   12/12
     9 a hand that shakes     2.9    6.0   6.0   0.46     0.00   12/12
    10 nothing to spare       2.5    5.5   4.4   0.58     0.61   11/12
    11 past a steady hand     2.1    5.0   3.0   0.78    10.05    0/12
    12 nobody could hold      1.8    4.5   2.2   0.91    29.65    0/12

*ticks* is how many frames of full thrust it takes to cross the gap —
under about four nothing could hold the wire at any skill. *grip* is
the arm's authority against the tremor over the tremor's own
correlation time. *used* is the 95th percentile of how much of the gap
the pilot spent, and it is the column that says a rung is hard rather
than impossible: at 0.33 there is room in it, at 0.91 it is passing on
luck. The pilot is a yardstick and not a ceiling — it is beatable, and
the top two rungs are meant to beat it.

Contact is a hard constraint rather than a bounce: a loop cannot pass
through a wire, so the step that would have put it there is projected
back onto the constraint and the velocity into it is removed. A buzz is
counted once per *touch* rather than once per frame of scraping, which is
what the real buzzer does and also what stops a single graze reading as
sixty faults.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

Vec = Tuple[float, float, float]

# --- small vector arithmetic ---------------------------------------------
#
# Tuples and module functions rather than a class. This is the inner
# loop of the task -- a contact test runs several times a frame -- and a
# NamedTuple with operators measured about three times the cost.


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def length(a: Vec) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def unit(a: Vec) -> Vec:
    size = length(a)
    if size < 1e-12:
        return (1.0, 0.0, 0.0)
    return (a[0] / size, a[1] / size, a[2] / size)


def lerp(a: Vec, b: Vec, t: float) -> Vec:
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


# --- the world, in centimetres -------------------------------------------
#
# Not abstract units. A fairground buzz wire is half a metre of 3mm
# welding rod with a loop a couple of centimetres across, and keeping the
# numbers on that scale is what lets the sag, the tremor and the top
# speed be argued about rather than tuned blind.

#: The wire's own radius. 3mm rod, so 1.5mm. Fixed across the ladder --
#: the clearance moves because the *loop* shrinks, which is what a
#: harder version of this game actually does.
WIRE_RADIUS = 0.15

#: How much metal the loop is made of, outside its hole. The wire can
#: strike this from outside as well as from inside, which is what makes
#: :func:`crossing_contact` symmetric.
RIM = 0.28

#: How steeply a wire may cut the loop's plane before the crossing stops
#: being a crossing. Past this the elliptical cross-section is so long
#: that no hole on the ladder admits it, so it is a jam rather than a
#: pass, and clamping here only keeps the arithmetic finite.
MIN_COS = 0.10

#: Samples around the elliptical cross-section when looking for its
#: nearest and furthest points from the loop's centre. Refined by
#: bisection afterwards, so this only has to bracket the extremes.
ARC_SAMPLES = 32

#: How far along the lead-in the loop is threaded, in cm. **Not
#: nought**, and the reason is worth keeping: the loop's plane cuts the
#: wire where the wire changes sides of it, and a loop balanced exactly
#: on the end of the wire has no wire on one side to change from. There
#: is then no crossing, the loop reads as having come off the near post,
#: and it is put back where it already is -- for ever. Threading it a
#: centimetre in is both what a person does and what makes the question
#: well posed.
THREADED_AT = 1.1

#: How much straight wire is grown onto each end, in cm. The lead-in a
#: loop is threaded onto and the lead-out it comes off, as on the real
#: thing, and the only reason the start and the finish are unambiguous.
LEAD = 2.2

#: Milestone beads a wire is divided into, at most. The count actually
#: used is capped so that one action can never cross two of them --
#: see :func:`bead_count`, which is what makes the coach's signal a
#: potential in the sense of Ng et al. rather than merely a hint.
BEADS_WANTED = 40

#: Multiplied by the furthest one action could ever slide the loop
#: along the wire to get the closest two beads may sit. Two would be
#: exactly enough; this leaves a margin, and
#: :mod:`tests.test_buzzwire` asserts it against every grade.
BEAD_MARGIN = 2.5

#: The slowest tick the physics is meant for. Bead spacing is sized
#: against this, so a run driven at any rate from here up keeps the
#: one-bead-per-action property. :attr:`nwenv.buzzwire.BuzzWireEnv`
#: refuses a slower boundary and :meth:`Hand.advance` clamps a long
#: frame down to it, so a person on a stuttering machine gets slow
#: motion rather than a loop through the wire.
SLOWEST_HZ = 30.0

#: Extra drag while the grip is squeezed, as a multiple of the usual.
#: Steadying the hand is a real thing a player does and it costs the
#: action it takes, which is the whole of its price.
GRIP_DRAG = 6.0

#: How fast the wrist follows the wire when the loop aligns itself, in
#: e-folds a second. Only used below the rung where the tilt becomes
#: the player's own problem.
ALIGN_RATE = 9.0

#: How much of the speed into a contact survives it. Metal on metal
#: through a hand: almost none.
BOUNCE = 0.15

#: How long the loop has to be clear of the wire before the buzzer
#: stops, in seconds. Debounce, and the real thing has it too.
#:
#: Without it a loop *held* against the wire counts a fresh touch every
#: few frames, because the contact is resolved by projecting the loop
#: back to exactly the constraint -- so the next tick starts clear,
#: touches again, and the buzzer reads a single graze as a run's worth
#: of faults. Measured before this existed: one press held for ten
#: seconds on the bottom rung counted forty-one touches against an
#: allowance of six.
QUIET_SECONDS = 0.06

#: How far the loop may be tilted off the wire's general run before the
#: stop, in radians. Not a rule of the game -- a wrist joint.
TILT_LIMIT = 1.15


class Grade(NamedTuple):
    """One rung: a wire to thread, a hand to do it with, and how long.

    ``hole`` is the dial that matters most and the one to read first:
    it is the radius of the loop's *hole*, against a wire of radius
    :data:`WIRE_RADIUS`, so the clearance a player actually has is
    ``hole - WIRE_RADIUS`` and at the top of the ladder that is a
    millimetre and a half.
    """

    name: str
    #: Length of the wire's axis, before the bends lengthen it.
    span: float
    #: How many harmonics the shape is built from. More means finer
    #: detail; the amplitude of each is set by :attr:`slope`.
    waves: int
    #: How far the wire swings off its axis.
    swing: float
    #: Spectral slope. A high number puts nearly all the amplitude in
    #: the first harmonic, so the wire is one long lazy bend; a low one
    #: leaves the fast harmonics with real amplitude and the wire gets
    #: corners. This, not :attr:`swing`, is what makes a wire vicious.
    slope: float
    #: Radius of the loop's hole.
    hole: float
    #: Downward acceleration the arm fails to cancel, cm/s².
    sag: float
    #: Tremor strength, cm/s² rms, and its correlation time in seconds.
    tremor: float
    tremor_tau: float
    #: What one thrust port is worth, cm/s².
    thrust: float
    #: Viscous drag, in reciprocal seconds. High drag makes the loop
    #: behave like a position; low drag leaves it a momentum to fight.
    drag: float
    #: Fastest the loop may travel, cm/s.
    top_speed: float
    #: What one tilt port is worth, rad/s², and the cap on the rate.
    #: ``0.0`` means the wrist follows the wire by itself and the four
    #: tilt ports do nothing -- true of the bottom half of the ladder.
    twist: float
    top_twist: float
    #: Buzzes allowed before the run is lost. Zero is the real game.
    touches: int
    #: Seconds to get from one post to the other.
    seconds: float
    #: Where the camera stands, as an angle off broadside in degrees.
    #: At nought the wire runs squarely across the screen and its
    #: excursions towards you are plain; swung round towards the wire's
    #: own axis they stop being plain, and only perspective and shading
    #: separate a bend towards you from a bend away.
    view: float


#: The ladder. Twelve rungs from a hoop on a bent coat hanger to a wire
#: nobody could hold. Measured rather than guessed: see
#: ``tests/bench_buzzwire.py``, which flies every rung with the
#: reference pilot in :func:`pilot_port` and prints what gets through.
#:
#: The tremor column is the one that was **derived** rather than tuned,
#: and it is worth saying how, because the first version of this table
#: had it twenty times too big and every rung above the fifth was
#: unplayable by anything. Under viscous drag ``γ`` an
#: Ornstein-Uhlenbeck acceleration of strength ``σ`` and correlation
#: time ``τ`` — with ``τ`` well under ``1/γ``, which it is throughout —
#: leaves the loop with a stationary speed of about ``σ·sqrt(τ/γ)``.
#: That is the number that has to stay small against what one tick of
#: thrust can take back, ``thrust/hz``. So the column was written by
#: choosing the wander a rung should have, from a tenth of a
#: centimetre a second to one and a third, and solving for ``σ``. Every
#: other column is a dial someone turned; this one is arithmetic, and
#: :mod:`tests.test_buzzwire` checks it still holds.
GRADES: Tuple[Grade, ...] = (
    #      name              span waves swing slope  hole  sag tremor  tau
    #      thrust drag  top  twist ttw touches secs view
    Grade('a gentle bow',           26.0,  1,  4.2,  3.00, 1.20,  0.0,  0.00, 0.13,
           55.1, 14.00, 4.53,  0.0, 0.00,  6,  20.0,  0.0),
    Grade('two easy bends',         28.0,  2,  4.5,  2.60, 1.05,  2.6,  0.00, 0.13,
           52.1, 13.50, 4.44,  0.0, 0.00,  5,  21.0,  4.0),
    Grade('a lazy S',               30.0,  2,  4.8,  2.40, 0.92,  4.5,  2.40, 0.13,
           50.1, 13.00, 4.43,  0.0, 0.00,  4,  22.0,  8.0),
    Grade('a coiling run',          32.0,  3,  5.1,  2.10, 0.80,  5.8,  2.70, 0.13,
           44.4, 12.50, 4.08,  0.0, 0.00,  3,  26.0, 12.0),
    Grade('shoulder height',        33.0,  3,  5.3,  1.90, 0.70,  6.3,  3.00, 0.12,
           39.6, 12.00, 3.80,  0.0, 0.00,  3,  29.0, 16.0),
    Grade('the tight bend',         34.0,  4,  5.4,  1.70, 0.62,  6.8,  3.20, 0.12,
           36.0, 11.50, 3.60,  0.0, 0.00,  2,  32.0, 20.0),
    Grade('turn your wrist',        34.0,  5,  5.4,  1.50, 0.55,  7.3,  3.40, 0.11,
           33.0, 11.00, 3.45, 15.7, 1.43,  2,  34.0, 24.0),
    Grade('the corkscrew',          33.0,  6,  5.3,  1.42, 0.49,  7.7,  4.00, 0.11,
           30.6, 10.50, 3.35, 13.3, 1.27,  1,  36.0, 28.0),
    Grade('a hand that '
          'shakes',                 32.0,  7,  5.1,  1.35, 0.44,  8.1,  4.80, 0.10,
           29.0, 10.00, 3.34, 12.7, 1.27,  1,  40.0, 32.0),
    Grade('nothing to '
          'spare',                  31.0,  8,  5.0,  1.36, 0.40,  7.9,  5.80, 0.10,
           26.2,  9.60, 3.14, 10.8, 1.12,  1,  40.0, 36.0),
    Grade('past a steady '
          'hand',                   30.0,  8,  4.8,  1.42, 0.36,  7.7,  7.00, 0.09,
           23.2,  9.20, 2.90,  9.2, 1.00,  0,  43.0, 40.0),
    Grade('nobody could '
          'hold this',              29.0,  9,  4.6,  1.48, 0.33,  7.6,  8.40, 0.08,
           21.6,  9.00, 2.76,  9.0, 1.00,  0,  47.0, 44.0),
)


def hand_speed(grade: Grade) -> float:
    """Fastest the loop travels under one port held down, cm/s.

    ``thrust / drag``, which is the number the whole table is built
    around and the reason the drag column is as high as it is. The arm
    holding a loop is a servo, not a projectile: it settles to a speed
    in about a tenth of a second and the loop goes where the hand
    goes. So the useful quantum is not "how much acceleration" but
    **how far one tick of thrust ends up moving the loop**, which is
    this speed times the frame time, and it is what has to stay small
    against the clearance.

    The first version of this table missed that and had thrust in the
    hundreds against a drag of three: one tick of a key was worth a
    centimetre and a third of eventual travel, against a clearance of
    two millimetres, so above the sixth rung nothing — pilot, person or
    learner — could have held the wire, and the ladder had no top half
    at all. :func:`ticks_per_clearance` is the ratio that had to be
    got right, and the test suite holds it.
    """
    return grade.thrust / max(1e-9, grade.drag)


def ticks_per_clearance(grade: Grade, hz: float = 60.0) -> float:
    """How many ticks of full thrust it takes to cross the clearance.

    Under one, a single frame's mistake is already a buzz and no
    controller can hold the wire. This runs from about sixty at the
    bottom of the ladder to about four at the top, which is the honest
    statement of what "superhuman" means here: four frames of grace,
    at sixty frames a second, with a tremor moving underneath.
    """
    step = hand_speed(grade) / hz
    return clearance(grade) / step if step > 0.0 else float('inf')


def tremor_wander(grade: Grade) -> float:
    """Roughly how fast the tremor alone would carry the loop, cm/s.

    The stationary speed of a viscously damped point driven by an
    Ornstein-Uhlenbeck acceleration, in the regime this ladder lives in
    (``tremor_tau`` well below ``1 / drag``). What makes the number
    worth having is the comparison it invites: one tick of thrust is
    worth ``thrust / hz`` of speed, so ``wander × hz / thrust`` says
    what share of a controller's authority the tremor is eating, and
    that ratio is the ladder's real shape.
    """
    if grade.tremor <= 0.0:
        return 0.0
    return grade.tremor * math.sqrt(grade.tremor_tau / grade.drag)


def clamped_rung(rung: int) -> int:
    """Hold *rung* inside the ladder."""
    return max(1, min(len(GRADES), int(rung)))


def grade_of(rung: int) -> Grade:
    return GRADES[clamped_rung(rung) - 1]


def clearance(grade: Grade) -> float:
    """How far off centre the loop may sit before it buzzes, in cm.

    Only the truth for a wire square to the loop. Tilt the wire and the
    ellipse eats into this, which is the point of the whole task.
    """
    return grade.hole - WIRE_RADIUS


# --- the wire ------------------------------------------------------------

class Wire(NamedTuple):
    """A bent tube in space, sampled at even steps along its own length."""

    points: Tuple[Vec, ...]
    tangents: Tuple[Vec, ...]
    arcs: Tuple[float, ...]
    span: float
    length: float
    radius: float
    beads: int

    def spacing(self) -> float:
        """Distance between consecutive samples, in cm."""
        return self.length / max(1, len(self.points) - 1)

    def index_at(self, arc: float) -> int:
        """The sample at or before arc length *arc*."""
        step = self.spacing()
        if step <= 0.0:
            return 0
        return max(0, min(len(self.points) - 2, int(arc / step)))

    def at(self, arc: float) -> Tuple[Vec, Vec]:
        """Where the wire is at arc length *arc*, and which way it runs."""
        index = self.index_at(arc)
        step = self.spacing()
        blend = 0.0 if step <= 0.0 else min(1.0, max(
            0.0, (arc - self.arcs[index]) / step))
        return (lerp(self.points[index], self.points[index + 1], blend),
                unit(lerp(self.tangents[index], self.tangents[index + 1],
                          blend)))

    def bead_at(self, arc: float) -> int:
        """Which milestone bead arc length *arc* has reached."""
        if self.length <= 0.0:
            return 0
        share = min(1.0, max(0.0, arc / self.length))
        return min(self.beads, int(share * self.beads))

    def bead_arc(self, bead: int) -> float:
        """Where bead number *bead* sits, in arc length."""
        return self.length * bead / float(max(1, self.beads))


def bead_count(grade: Grade, wire_length: float) -> int:
    """How many milestones a wire of this length may be divided into.

    The cap is the whole of the coach's honesty. One action moves the
    loop along the wire by at most ``top_speed * dt`` and a contact may
    push it along by as much again, so :data:`BEAD_MARGIN` times that,
    at the slowest tick the physics allows, is the closest two beads may
    ever sit. Then *no* action can cross two beads, the count of beads
    still ahead changes by one or by nothing, and its sign is the
    potential-based shaping term of Ng et al. rather than a hint someone
    thought looked helpful.

    ``tests/test_buzzwire.py`` asserts the inequality against every
    grade, because the argument is geometric and a sweep would only
    ever fail to find the case that breaks it.
    """
    furthest = 2.0 * grade.top_speed / SLOWEST_HZ
    closest = BEAD_MARGIN * furthest
    if closest <= 0.0:
        return BEADS_WANTED
    return max(4, min(BEADS_WANTED, int(wire_length / closest)))


def _series(rng: random.Random, grade: Grade) -> List[float]:
    """Amplitudes for one lateral axis, as a **cosine** series.

    Cosines of ``k·pi·t`` rather than sines of ``2·pi·k·t``, and the
    difference is the whole reason the ends of the wire are usable:
    every term of a cosine series has zero slope at both ends, so the
    wire arrives at each post running straight along its own axis
    without anything having to be done to it.

    The first version windowed a sine series down to nothing at the
    ends instead, and that is worth recording because it looked right
    and was the opposite of right. Forcing the offset to nought over a
    tenth of the span means the *whole* swing has to happen in that
    tenth — so the lead-in, the piece meant to be gentle, came out as
    the steepest part of the wire, at nearly sixty degrees, and the
    reference pilot was buzzing on the bottom rung inside half a
    second.
    """
    return [rng.choice((-1.0, 1.0)) * rng.uniform(0.45, 1.0)
            / (k ** grade.slope)
            for k in range(1, grade.waves + 1)]


def _offset(weights: Sequence[float], share: float) -> float:
    return sum(w * math.cos(k * math.pi * share)
               for k, w in enumerate(weights, start=1))


def _grow_lead(points: List[Vec], at_start: bool) -> List[Vec]:
    """Straight wire, tangent to the curve, off one end of it.

    Grown rather than blended in. The cosine series already arrives at
    each end running along the axis, so a segment tangent to it there
    is straight wire and joins without a kink -- and a straight piece to
    thread the loop onto is the only thing that makes "at the start" and
    "at the finish" mean anything definite.

    Comes back in the wire's own order, so the caller can put the three
    pieces end to end: the near lead runs *towards* the curve, the far
    one away from it, and neither repeats the tip.
    """
    tip, inwards = ((points[0], points[1]) if at_start
                    else (points[-1], points[-2]))
    away = unit(sub(tip, inwards))
    steps = 12
    reach = (range(steps, 0, -1) if at_start else range(1, steps + 1))
    return [add(tip, scale(away, LEAD * step / steps)) for step in reach]


def deal(rung: int, seed: Optional[int] = None) -> Wire:
    """Bend a fresh wire for *rung*.

    A sum of harmonics with random phases, one series for each of the
    two lateral axes, windowed to leave straight ends. Two things make
    this the right generator rather than a pile of random control
    points: the curve is smooth to every order, so there is no corner
    that is an artefact of the sampling rather than of the wire; and
    the difficulty is a *spectrum*, so :attr:`Grade.slope` moves the
    curvature without touching how far the wire wanders, which no
    control-point scheme lets you do independently.

    The axis is monotone by construction — the wire never doubles back
    along its own run — so "how far along" is a number rather than an
    argument, and the loop can be threaded on at one end and taken off
    at the other with nothing ambiguous in between.
    """
    grade = grade_of(rung)
    rng = random.Random(seed)
    up, out = _series(rng, grade), _series(rng, grade)

    # Normalise each series to the swing this rung asked for, so that
    # the slope changes the *shape* and only the shape. Without this a
    # low slope both roughens the wire and shrinks it, and the two
    # would never be separable in a result.
    fine = [i / 600.0 for i in range(601)]
    peak_up = max(abs(_offset(up, t)) for t in fine) or 1.0
    peak_out = max(abs(_offset(out, t)) for t in fine) or 1.0
    gain_up = grade.swing / peak_up
    # Squarer than it is tall, like a real one: the game is bolted to a
    # board and the wire leans off it rather than towering over it.
    gain_out = grade.swing * 0.78 / peak_out

    raw = [(grade.span * (t - 0.5), _offset(up, t) * gain_up,
            _offset(out, t) * gain_out) for t in fine]
    raw = _grow_lead(raw, True) + raw + _grow_lead(raw, False)

    # Resample at even steps of arc length. Everything downstream --
    # the loop's progress, the beads, the tube mesh -- wants even
    # spacing, and a curve sampled evenly in its parameter is not.
    runs = [0.0]
    for before, after in zip(raw, raw[1:]):
        runs.append(runs[-1] + length(sub(after, before)))
    total = runs[-1]
    samples = max(120, int(total / 0.22))
    points: List[Vec] = []
    cursor = 0
    for i in range(samples + 1):
        want = total * i / samples
        while cursor < len(runs) - 2 and runs[cursor + 1] < want:
            cursor += 1
        run = runs[cursor + 1] - runs[cursor]
        blend = 0.0 if run <= 0.0 else (want - runs[cursor]) / run
        points.append(lerp(raw[cursor], raw[cursor + 1], blend))

    tangents: List[Vec] = []
    for i in range(len(points)):
        before = points[max(0, i - 1)]
        after = points[min(len(points) - 1, i + 1)]
        tangents.append(unit(sub(after, before)))

    arcs = [0.0]
    for before, after in zip(points, points[1:]):
        arcs.append(arcs[-1] + length(sub(after, before)))

    return Wire(points=tuple(points), tangents=tuple(tangents),
                arcs=tuple(arcs), span=grade.span, length=arcs[-1],
                radius=WIRE_RADIUS,
                beads=bead_count(grade, arcs[-1]))


# --- where the loop is looking from --------------------------------------

def camera_basis(grade: Grade) -> Tuple[Vec, Vec, Vec]:
    """Right, up and forward for this rung's camera, as world vectors.

    Lives here rather than in the screen because the ports are named in
    it — "left" means left *as drawn* — and the reference pilot has to
    speak the same six directions a player does.
    """
    angle = math.radians(grade.view)
    # Forward runs from the camera into the scene. At nought the camera
    # is square to the wire's axis; swinging the angle up walks it round
    # towards looking along the wire.
    forward = unit((math.sin(angle), -0.36, -math.cos(angle)))
    right = unit(cross(forward, (0.0, 1.0, 0.0)))
    up = unit(cross(right, forward))
    return right, up, forward


#: The ports, in the order the boundary hands them out. A player's keys
#: are bound to the same six directions and the same wrist.
PUSHES: Tuple[str, ...] = ('up', 'down', 'left', 'right', 'in', 'out')
TWISTS: Tuple[str, ...] = ('tilt up', 'tilt down', 'tilt left', 'tilt right')
GRIP = 'grip'
PORTS: Tuple[str, ...] = PUSHES + TWISTS + (GRIP,)


def push_vector(grade: Grade, name: str) -> Vec:
    """Which way in the world one thrust port shoves the loop."""
    right, up, forward = camera_basis(grade)
    return {
        'up': up,
        'down': scale(up, -1.0),
        'left': scale(right, -1.0),
        'right': right,
        'in': forward,
        'out': scale(forward, -1.0),
    }[name]


# --- contact -------------------------------------------------------------

class Crossing(NamedTuple):
    """Where the wire cuts the loop's plane, and how squarely."""

    point: Vec
    tangent: Vec
    arc: float
    #: Cosine of the angle between the wire and the loop's axis, at
    #: least :data:`MIN_COS`. The ellipse's long semi-axis is
    #: ``WIRE_RADIUS / square``, so this is the whole of why a bend has
    #: to be turned into.
    square: float


class Contact(NamedTuple):
    """A touch: how deep, which way out, and where along the wire."""

    depth: float
    #: Unit vector, in the loop's plane, along which moving the loop's
    #: centre by :attr:`depth` ends the contact.
    escape: Vec
    arc: float
    #: True when the wire struck the outside of the loop rather than
    #: the inside of its hole.
    outside: bool
    #: True when no move of the loop's centre can clear it, because the
    #: cross-section is wider than the hole. A jam: the wrist turned
    #: somewhere the wire will not allow.
    jammed: bool


def _ellipse_reach(offset_long: float, offset_wide: float,
                   semi_long: float, semi_wide: float) -> Tuple[
                       float, float, float]:
    """Nearest and furthest points of an ellipse from the origin.

    The ellipse is centred at ``(offset_long, offset_wide)`` with
    semi-axes along the two coordinate directions. Returns the nearest
    distance, the furthest distance, and the angle at which the furthest
    one sits.

    Coarse samples then a bisection on the derivative, because the
    furthest point decides whether a trial buzzes and a one-percent
    sampling error is a fault the player did not commit.
    """
    def at(angle: float) -> float:
        x = offset_long + semi_long * math.cos(angle)
        y = offset_wide + semi_wide * math.sin(angle)
        return x * x + y * y

    step = 2.0 * math.pi / ARC_SAMPLES
    best_far, far_angle = -1.0, 0.0
    best_near = float('inf')
    for i in range(ARC_SAMPLES):
        angle = i * step
        value = at(angle)
        if value > best_far:
            best_far, far_angle = value, angle
        if value < best_near:
            best_near = value
    # Refine the maximum inside the sample either side of it.
    low, high = far_angle - step, far_angle + step
    for _ in range(24):
        third = (high - low) / 3.0
        one, two = low + third, high - third
        if at(one) < at(two):
            low = one
        else:
            high = two
    far_angle = (low + high) / 2.0
    best_far = max(best_far, at(far_angle))
    return math.sqrt(best_near), math.sqrt(best_far), far_angle


def crossings(wire: Wire, centre: Vec, axis: Vec, arc: float,
              reach: float) -> List[Crossing]:
    """Every place the wire cuts the loop's plane, near *arc*.

    Only a window of the wire is examined: a crossing a metre away is
    not something the loop can be touching, and walking the whole
    polyline every frame is the one thing here that would not fit in a
    frame's budget.
    """
    span = reach + 4.0
    step = wire.spacing()
    if step <= 0.0:
        return []
    first = max(0, int((arc - span) / step))
    last = min(len(wire.points) - 2, int((arc + span) / step) + 1)
    found: List[Crossing] = []
    before = dot(sub(wire.points[first], centre), axis)
    for index in range(first, last + 1):
        after = dot(sub(wire.points[index + 1], centre), axis)
        if (before <= 0.0 < after) or (before >= 0.0 > after):
            gap = before - after
            blend = 0.0 if abs(gap) < 1e-12 else before / gap
            blend = min(1.0, max(0.0, blend))
            point = lerp(wire.points[index], wire.points[index + 1], blend)
            tangent = unit(lerp(wire.tangents[index],
                                wire.tangents[index + 1], blend))
            found.append(Crossing(
                point=point, tangent=tangent,
                arc=wire.arcs[index] + blend * step,
                square=max(MIN_COS, abs(dot(tangent, axis)))))
        before = after
    return found


def crossing_contact(crossing: Crossing, centre: Vec, axis: Vec,
                     hole: float, radius: float = WIRE_RADIUS,
                     rim: float = RIM) -> Optional[Contact]:
    """Whether the wire touches the loop at this crossing, and how hard.

    The heart of the task. In the loop's own plane the wire's tube cuts
    an **ellipse**: half a wire thick across, and ``radius / square``
    long, stretched along the direction the wire leans. The loop is an
    annulus in that same plane, hole radius *hole*, metal out to
    ``hole + rim``.

    So there are exactly three cases, and the first two are the ones a
    player is trying for:

    * the ellipse lies wholly inside the hole — the wire is threaded
      cleanly and nothing is touching;
    * the ellipse lies wholly outside the metal — this crossing is
      some other part of the wire passing by, and it misses;
    * anything else is a touch, and the shortest way out of it is
      along the line to whichever extreme of the ellipse is at fault.

    The stretch is what turns a bend into a thing you have to *plan*
    for. At forty-five degrees the wire needs a hole 1.41 times as
    wide; at sixty, twice; and the wrist has to have started turning
    before the bend, because at the bend it is already too late.
    """
    offset = sub(crossing.point, centre)
    # In-plane frame: `along` is the direction the wire leans, which is
    # the ellipse's long axis by construction.
    leaning = sub(crossing.tangent, scale(axis, dot(crossing.tangent, axis)))
    if length(leaning) < 1e-9:
        # Dead square to the loop. Any in-plane direction will do, and
        # the ellipse is a circle, so the choice cannot matter.
        along = unit(sub(offset, scale(axis, dot(offset, axis))))
        if length(sub(along, (1.0, 0.0, 0.0))) < 1e-9:
            along = unit(cross(axis, (0.0, 1.0, 0.0)))
    else:
        along = unit(leaning)
    wide = unit(cross(axis, along))

    semi_long = radius / crossing.square
    semi_wide = radius
    near, far, angle = _ellipse_reach(dot(offset, along), dot(offset, wide),
                                      semi_long, semi_wide)
    outer = hole + rim
    if near > outer:
        return None                      # passing by, outside the metal
    if far < hole:
        return None                      # threaded cleanly
    if far - hole <= outer - near:
        # The inside of the hole is the closer wall to escape past.
        deep = add(scale(along, dot(offset, along)
                         + semi_long * math.cos(angle)),
                   scale(wide, dot(offset, wide)
                         + semi_wide * math.sin(angle)))
        escape = unit(deep)
        return Contact(depth=far - hole, escape=escape, arc=crossing.arc,
                       outside=False, jammed=semi_long >= hole)
    # The wire is against the outside of the loop: back the loop off.
    outward = sub(offset, scale(axis, dot(offset, axis)))
    escape = scale(unit(outward), -1.0) if length(outward) > 1e-9 else wide
    return Contact(depth=outer - near, escape=escape, arc=crossing.arc,
                   outside=True, jammed=False)


# --- the hand ------------------------------------------------------------

class Step(NamedTuple):
    """What one tick of the physics did."""

    #: Arc length the loop's threading point reached, in cm.
    arc: float
    #: True on the tick a fresh touch began. A scrape held for twenty
    #: frames is one touch, which is what the buzzer does.
    buzzed: bool
    #: Whether the loop is in contact right now, fresh or not.
    scraping: bool
    #: True when the loop has come off the far post: the wire is done.
    home: bool


class Hand:
    """The loop, its momentum, and the arm that is not quite still.

    Mutable and stepped in place; one of these is a run in progress.
    """

    def __init__(self, wire: Wire, grade: Grade,
                 rng: Optional[random.Random] = None) -> None:
        self.wire = wire
        self.grade = grade
        self.rng = rng or random.Random()
        point, tangent = wire.at(THREADED_AT)
        self.centre: Vec = point
        self.velocity: Vec = (0.0, 0.0, 0.0)
        self.yaw, self.pitch = _angles_of(tangent)
        self.yaw_rate = self.pitch_rate = 0.0
        #: The tremor: an Ornstein-Uhlenbeck process on acceleration,
        #: so it has a correlation time rather than being white noise
        #: that averages away inside one frame.
        self.drift: Vec = (0.0, 0.0, 0.0)
        self.arc = THREADED_AT
        self.touches = 0
        self.scraping = False
        self.quiet = 0.0
        self.home = False

    # --- what the loop looks like right now ------------------------------

    @property
    def axis(self) -> Vec:
        return _axis_of(self.yaw, self.pitch)

    def bead(self) -> int:
        return self.wire.bead_at(self.arc)

    def beads_left(self) -> int:
        """The coach's potential: milestones still between here and home."""
        return self.wire.beads - self.bead()

    def offset(self) -> float:
        """How far off the wire's centre the loop is sitting, in cm.

        Nothing in the physics reads it: it is for the screen's gauge
        and for the reference pilot, both of which want the one number
        that says how close a buzz is without saying anything about the
        wire.

        A loop with no crossing at all reads as *fully* off centre
        rather than as perfectly centred, which is the opposite of what
        the obvious ``0.0`` would say. Nothing should ever see that
        state -- :meth:`_locate` puts a loop that has come off back on
        the wire in the same tick -- but a gauge that reads "dead
        centre" when it means "cannot find the wire" is the kind of
        instrument that gets believed.
        """
        found = crossings(self.wire, self.centre, self.axis, self.arc,
                          self.grade.hole + RIM)
        if not found:
            return self.grade.hole
        return min(length(sub(one.point, self.centre)) for one in found)

    # --- one tick --------------------------------------------------------

    def advance(self, dt: float, push: Optional[Vec] = None,
                twist: Tuple[float, float] = (0.0, 0.0),
                grip: bool = False) -> Step:
        """Integrate one frame and settle whatever it ran into.

        *push* is a unit world direction to thrust along, or None.
        *twist* is ``(pitch, yaw)`` in units of one tilt port. *grip* is
        the hand being braced, which costs the tick and buys drag.

        Semi-implicit Euler: the velocity is updated first and the
        position from the new velocity. For a damped system driven at
        the frame rate that is both stabler and cheaper than anything
        higher-order, and being stable at a hundred and thirty
        centimetres per second squared of tremor is the whole
        requirement.
        """
        dt = min(max(dt, 0.0), 1.0 / SLOWEST_HZ)
        if dt <= 0.0 or self.home:
            return Step(self.arc, False, self.scraping, self.home)
        grade = self.grade

        self._shiver(dt)
        drag = grade.drag * (GRIP_DRAG if grip else 1.0)
        accel = (self.drift[0] - drag * self.velocity[0],
                 self.drift[1] - drag * self.velocity[1] - grade.sag,
                 self.drift[2] - drag * self.velocity[2])
        if push is not None and not grip:
            accel = add(accel, scale(push, grade.thrust))

        speed = add(self.velocity, scale(accel, dt))
        fast = length(speed)
        if fast > grade.top_speed:
            speed = scale(speed, grade.top_speed / fast)
        self.velocity = speed
        was = self.centre
        self.centre = add(self.centre, scale(speed, dt))

        held_yaw, held_pitch = self.yaw, self.pitch
        self._turn(dt, twist, grip)
        buzzed = self._settle(dt, was, held_yaw, held_pitch)
        self._locate()
        return Step(self.arc, buzzed, self.scraping, self.home)

    def _shiver(self, dt: float) -> None:
        """Advance the tremor one tick, exactly rather than by Euler.

        An Ornstein-Uhlenbeck process has a closed-form update over any
        step, so the tremor a run feels is the same whether it is driven
        at thirty ticks a second or at two hundred. Integrating it the
        obvious way would make the disturbance a function of the frame
        rate, and then the ladder would mean something different on
        every machine.
        """
        grade = self.grade
        if grade.tremor <= 0.0:
            self.drift = (0.0, 0.0, 0.0)
            return
        keep = math.exp(-dt / max(1e-3, grade.tremor_tau))
        kick = grade.tremor * math.sqrt(max(0.0, 1.0 - keep * keep))
        self.drift = (self.drift[0] * keep + kick * self.rng.gauss(0.0, 1.0),
                      self.drift[1] * keep + kick * self.rng.gauss(0.0, 1.0),
                      self.drift[2] * keep + kick * self.rng.gauss(0.0, 1.0))

    def _turn(self, dt: float, twist: Tuple[float, float],
              grip: bool) -> None:
        """Roll the wrist, or let it follow the wire by itself."""
        grade = self.grade
        if grade.twist <= 0.0:
            # The bottom half of the ladder aims the loop for you, with
            # a lag. The four tilt ports are still there and still do
            # nothing, which is the same deal every task here gives a
            # port a rung does not use.
            _point, tangent = self.wire.at(self.arc)
            want_yaw, want_pitch = _angles_of(tangent)
            blend = min(1.0, ALIGN_RATE * dt)
            self.yaw += _wrap(want_yaw - self.yaw) * blend
            self.pitch += (want_pitch - self.pitch) * blend
            self.yaw_rate = self.pitch_rate = 0.0
            return
        damp = grade.drag * (GRIP_DRAG if grip else 1.0)
        pitch_push, yaw_push = (0.0, 0.0) if grip else twist
        self.pitch_rate += (grade.twist * pitch_push
                            - damp * self.pitch_rate) * dt
        self.yaw_rate += (grade.twist * yaw_push - damp * self.yaw_rate) * dt
        self.pitch_rate = max(-grade.top_twist,
                              min(grade.top_twist, self.pitch_rate))
        self.yaw_rate = max(-grade.top_twist,
                            min(grade.top_twist, self.yaw_rate))
        self.pitch += self.pitch_rate * dt
        self.yaw += self.yaw_rate * dt
        if abs(self.pitch) > TILT_LIMIT:
            self.pitch = math.copysign(TILT_LIMIT, self.pitch)
            self.pitch_rate = 0.0

    def _settle(self, dt: float, was: Vec, held_yaw: float,
                held_pitch: float) -> bool:
        """Push the loop back out of the wire, and say if that was fresh.

        A hard constraint rather than a bounce. The loop is projected
        onto the outside of the constraint and the part of its velocity
        heading into it is removed, all but :data:`BOUNCE` of it. A
        wrist turned somewhere the wire will not admit is put back where
        it was, because the wire is in the way of the *turn* as much as
        of the move, and that is the difference between a loop that has
        to be aimed and one that can be spun freely at the last moment.
        """
        hit = self._deepest()
        if hit is None:
            self.quiet += dt
            if self.quiet >= QUIET_SECONDS:
                self.scraping = False
            return False
        self.quiet = 0.0
        if hit.jammed:
            self.yaw, self.pitch = held_yaw, held_pitch
            self.yaw_rate = self.pitch_rate = 0.0
            hit = self._deepest()
        if hit is not None:
            self.centre = add(self.centre, scale(hit.escape, hit.depth))
            into = dot(self.velocity, hit.escape)
            if into < 0.0:
                self.velocity = add(self.velocity,
                                    scale(hit.escape, -into * (1.0 + BOUNCE)))
            if self._deepest() is not None:
                # Still stuck after one projection: the tick asked for
                # something the wire simply does not allow, so it does
                # not happen at all.
                self.centre = was
                self.velocity = (0.0, 0.0, 0.0)
        fresh = not self.scraping
        self.scraping = True
        if fresh:
            self.touches += 1
        return fresh

    def _deepest(self) -> Optional[Contact]:
        """The worst thing the loop is touching, or None if it is clear."""
        axis = self.axis
        worst: Optional[Contact] = None
        for crossing in crossings(self.wire, self.centre, axis, self.arc,
                                  self.grade.hole + RIM):
            hit = crossing_contact(crossing, self.centre, axis,
                                   self.grade.hole, self.wire.radius)
            if hit is not None and (worst is None or hit.depth > worst.depth):
                worst = hit
        return worst

    def _locate(self) -> None:
        """Re-read how far along the wire the loop has got.

        By continuity rather than by proximity: of the crossings the
        loop's plane has, the one that *was* the threading point is the
        one nearest where it was last tick. Picking the nearest to the
        loop's centre instead would jump between the two halves of a
        hairpin, and progress would flicker for reasons nothing on
        screen could account for.
        """
        found = crossings(self.wire, self.centre, self.axis, self.arc,
                          self.grade.hole + RIM)
        threaded = [one for one in found
                    if length(sub(one.point, self.centre))
                    <= self.grade.hole + RIM]
        if not threaded:
            # Off the wire. **Which end matters, and only one answer to
            # that question is allowed to pay a green.** The loop cannot
            # cross the wire -- the contact projection sees to that, and
            # a tick moves it less than the loop's own rim is thick, so
            # it cannot tunnel through either -- so coming off can only
            # happen at an end. Anything else is arithmetic having a bad
            # moment, and the safe reading of a bad moment is *not* "the
            # wire is finished": that would be a green paid for a wire
            # nobody flew, which is the one mistake on this boundary
            # that no verifier could catch.
            if self.arc >= self.wire.length - LEAD * 0.5:
                self.home = True
                self.arc = self.wire.length
            else:
                # Anywhere else, the loop is simply put back on the wire
                # where it was. At the near post that is the real thing's
                # own end stop; in the middle it is a recovery that
                # cannot be mistaken for finishing.
                self.arc = max(THREADED_AT, min(self.arc, self.wire.length))
                point, _tangent = self.wire.at(self.arc)
                self.centre = point
                self.velocity = (0.0, 0.0, 0.0)
            return
        want = min(threaded, key=lambda one: abs(one.arc - self.arc))
        # A safety rail rather than a rule of the game. Speed and the
        # contact projection are both bounded, so this cannot bind --
        # and if it ever did, the coach's one-bead-per-action promise
        # would go with it, so it is cheaper to make the promise true
        # here than to reason about it afterwards.
        cap = 2.0 * self.grade.top_speed / SLOWEST_HZ
        self.arc = min(self.arc + cap, max(self.arc - cap, want.arc))
        if self.arc >= self.wire.length - 1e-6:
            self.home = True


def _axis_of(yaw: float, pitch: float) -> Vec:
    """The loop's normal, from the two wrist angles."""
    flat = math.cos(pitch)
    return (flat * math.cos(yaw), math.sin(pitch), -flat * math.sin(yaw))


def _angles_of(axis: Vec) -> Tuple[float, float]:
    """The two wrist angles that would produce *axis*."""
    unit_axis = unit(axis)
    pitch = math.asin(max(-1.0, min(1.0, unit_axis[1])))
    yaw = math.atan2(-unit_axis[2], unit_axis[0])
    return yaw, pitch


def _wrap(angle: float) -> float:
    """An angle difference brought into (-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle <= -math.pi:
        angle += 2.0 * math.pi
    return angle


# --- a hand that knows what it is doing ----------------------------------
#
# The reference pilot. It exists for two reasons and neither is play:
# to give tests/test_env_tasks.py a policy that can actually finish a
# wire through the same eleven ports a learner has, and to let
# tests/bench_buzzwire.py measure the ladder instead of anyone guessing
# at it. It reads the true state, which is exactly what makes it a
# yardstick rather than a competitor.

#: Position gain, in reciprocal seconds: how much speed the pilot asks
#: for per centimetre it is behind the point it is chasing.
PILOT_GAIN = 8.0

#: Velocity gain, also reciprocal seconds.
PILOT_BRAKE = 12.0

#: Fraction of a rung's top speed the pilot cruises at when it has
#: room, and the fraction it falls back to when it has none.
PILOT_CRUISE, PILOT_CRAWL = 0.72, 0.18

#: Radians of misalignment the pilot will tolerate before it stops
#: steering and spends the tick on its wrist instead. Also how far
#: ahead, in seconds, it reads its own turning rate when deciding --
#: without which it winds the wrist past where it wanted it and
#: oscillates.
TILT_SLACK, TILT_LEAD = 0.10, 0.16


def look_ahead(grade: Grade) -> float:
    """How far in front of itself the pilot reads the wire, in cm.

    Only the *heading* is taken from up there, never the position — see
    :func:`pilot_port`. Tied to the clearance so a tight rung looks a
    short way ahead and a loose one a long way, which is what makes a
    single set of gains work across the whole ladder.
    """
    return max(0.55, min(2.4, 2.2 * clearance(grade)))


def pilot_port(hand: Hand) -> int:
    """One port, chosen by a controller that can see everything.

    The demand is split in two, and keeping the halves apart is what
    makes it work at all. **Sideways** it steers at the wire's own
    centreline *here*, at the loop's own station, so it is never trying
    to be anywhere but in the middle of its hole. **Forwards** it runs
    along the heading a little way up the wire, so it leans into a bend
    before arriving in one. Aiming the loop's *position* at a point up
    the wire — the obvious thing, and the first thing this did — steers
    it along the chord instead of the arc, and on a rung whose hole is
    three millimetres the chord is outside the wire before the corner is
    halfway through.

    One port a tick is the same budget a learner has, and it is the
    binding constraint rather than an inconvenience: the pilot cannot
    both steer and turn on the same tick, and the top of the ladder is
    mostly about which of the two the next tick should go to.
    """
    grade = hand.grade
    ahead = min(hand.wire.length, hand.arc + look_ahead(grade))
    _target, tangent = hand.wire.at(ahead)
    room = max(1e-6, clearance(grade))
    risk = min(1.0, hand.offset() / room)

    if grade.twist > 0.0:
        want_yaw, want_pitch = _angles_of(tangent)
        off_yaw = _wrap(want_yaw - hand.yaw) - hand.yaw_rate * TILT_LEAD
        off_pitch = (want_pitch - hand.pitch) - hand.pitch_rate * TILT_LEAD
        worst = max(abs(off_yaw), abs(off_pitch))
        # A wrist badly out of line beats anything else, because past
        # about sixty degrees no amount of steering helps: the hole
        # stops admitting the wire at all.
        if worst > TILT_SLACK and (risk < 0.7 or worst > 3.0 * TILT_SLACK):
            if abs(off_pitch) > abs(off_yaw):
                return PORTS.index('tilt up' if off_pitch > 0.0
                                   else 'tilt down')
            return PORTS.index('tilt left' if off_yaw > 0.0 else 'tilt right')

    # Slow for the edge and slow for the bend. Both are the same
    # instinct a person has and both are worth having: speed is only
    # ever spent to beat the clock, and the clock is generous.
    here, running = hand.wire.at(hand.arc)
    bend = max(0.0, 1.0 - dot(running, tangent))
    pace = PILOT_CRUISE - (PILOT_CRUISE - PILOT_CRAWL) * risk
    pace *= max(0.3, 1.0 - 6.0 * bend)
    cruise = hand_speed(grade) * pace

    # Sideways: whatever it takes to sit in the middle of the hole.
    off_centre = sub(here, hand.centre)
    sideways = sub(off_centre, scale(running, dot(off_centre, running)))
    wanted = add(scale(tangent, cruise), scale(sideways, PILOT_GAIN))
    fast = length(wanted)
    if fast > grade.top_speed:
        wanted = scale(wanted, grade.top_speed / fast)
    # The plant already takes `drag * v` off every tick, so a demand
    # that did not put it back would always fall short of what it asked
    # for -- which is how the first version of this deadlocked, sitting
    # a centimetre short of its own target with nothing left to say.
    demand = add(add(scale(sub(wanted, hand.velocity), PILOT_BRAKE),
                     scale(hand.velocity, grade.drag)),
                 (0.0, grade.sag, 0.0))
    # Deliberately *not* corrected for `hand.drift`. The pilot reads the
    # loop's position and speed, which are two consecutive frames away
    # from anything looking at the screen; the tremor is a force inside
    # the arm and nothing on screen carries it. An earlier version
    # subtracted it and cancelled the disturbance exactly, and the whole
    # ladder came out flyable to the last rung — which is a measurement
    # of the cheat rather than of the wire.
    if length(demand) < grade.thrust * 0.04:
        return PORTS.index(GRIP)
    best, score = PORTS.index(GRIP), 0.0
    for index, name in enumerate(PUSHES):
        value = dot(push_vector(grade, name), demand)
        if value > score:
            best, score = index, value
    return best


__all__ = [
    'ARC_SAMPLES', 'BEADS_WANTED', 'BEAD_MARGIN', 'BOUNCE', 'Contact',
    'Crossing', 'GRADES', 'GRIP', 'GRIP_DRAG', 'Grade', 'Hand', 'MIN_COS',
    'PORTS', 'PUSHES', 'RIM', 'SLOWEST_HZ', 'Step', 'TILT_LIMIT', 'TWISTS',
    'WIRE_RADIUS', 'Wire', 'add', 'bead_count', 'camera_basis', 'clamped_rung',
    'clearance', 'cross', 'crossing_contact', 'crossings', 'deal', 'dot',
    'grade_of', 'hand_speed', 'length', 'lerp', 'look_ahead', 'pilot_port',
    'push_vector', 'scale', 'sub', 'ticks_per_clearance', 'tremor_wander',
    'unit',
]
