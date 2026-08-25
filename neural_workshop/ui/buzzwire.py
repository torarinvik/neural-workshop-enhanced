# -*- coding: utf-8 -*-
"""The Buzz Wire screen: a bent wire, a loop on it, and a hand that is not
quite still.

The physics and the wire are :mod:`neural_workshop.buzzwire`; the
renderer is :mod:`neural_workshop.ui.scene3d`; this is the stage they
meet on, the keys that drive it and the label the boundary reads.

Four decisions live here rather than in either of those, and each is
about what the *picture* is allowed to tell you.

* **The camera does not move, and it does not follow the loop.** Every
  wire is framed whole from the first frame, so nothing is hidden and
  nothing has to be searched for — this is a task about holding a line,
  not about finding one. It also means the wire is drawn once a level
  and never again, which is what makes a mesh of two thousand triangles
  affordable in Python at sixty frames a second.

* **Where the camera stands is a difficulty dial.** At the bottom of the
  ladder it is square to the wire's run, so a bend towards you and a
  bend away from you are plainly different. It swings round towards the
  wire's own axis as the rungs climb, until at the top the two look
  nearly alike and what separates them is perspective, shading and the
  shadow on the board — which is exactly why the board and the shadow
  are drawn at all. They are not decoration; they are the depth cue that
  is left when the parallax is gone.

* **The beads are the only running score, and they are on the wire.**
  Coach mode pays the loop for reaching one and charges it for losing
  one, and a learner is owed an account of that it can *see*: so the
  beads it has passed are lit and the ones ahead are not, and the count
  the shaping is computed from is a thing on screen rather than a
  number in the task. See :meth:`_coach_verdict`.

* **A buzz is a spark, not a red screen.** The verdict band at the
  bottom of the frame is the boundary's, and the workshop's rule is that
  the art stops above it — so the stage does, and the one thing that
  changes when the loop touches is the loop itself going white-hot for a
  third of a second, in both panels. That is what a shorted circuit
  looks like, and it is a colour no outcome reader will ever mistake for
  a score.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet import gl
from pyglet.window import key

from .. import buzzwire as B
from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .scene3d import (Camera, DepthPass, Light, Solid, merge, rod, slab,
                      torus, tube)
from .verdict import VerdictLabel, above_the_band

#: How wide a view the camera takes, in degrees. Narrow enough that the
#: perspective is gentle rather than a fish eye, wide enough that a
#: wire the length of the board still fills the stage.
FOV = 34.0

#: The stage's own light. Off to one side and above, so a tube lit by it
#: has a bright edge, a terminator and a dark edge — which is the whole
#: of what says "cylinder" rather than "line" in a still frame.
LIGHT = Light(towards=(-0.42, 0.80, 0.43), ambient=0.30, key=0.80,
              shine=0.62, hardness=30.0, haze=(24, 27, 34), fades_at=170.0)

#: The board everything is bolted to, and the two sides of the sky
#: behind it. Painted by the task rather than taken from the workshop's
#: light/dark setting, because a lit stage is what makes the shading
#: readable and a white page would leave the wire invisible.
SKY_HIGH, SKY_LOW = (44, 50, 63), (17, 19, 25)
BOARD = (58, 64, 78)
POST = (129, 135, 148)
#: Bright steel. The wire has to read against the sky at forty
#: centimetres and against the board at four.
WIRE = (198, 205, 218)
#: Brass, for the loop, so that it never reads as part of the wire.
LOOP = (212, 176, 92)
#: And the loop when it is touching: the arc, not a red light.
SPARK = (255, 250, 214)
#: Beads passed, and beads still ahead. Okabe-Ito sky blue against a
#: grey that is plainly *off* rather than merely dimmer.
BEAD_DONE, BEAD_TODO = (86, 180, 233), (88, 93, 105)
SHADOW = (20, 23, 30)

#: How long a spark stays up after a touch, in seconds.
SPARK_SECONDS = 0.30

#: How the stage is divided: the whole wire on the left, the sight
#: down it on the right. The same split the 3D Maze uses, for the same
#: reason -- one panel says where everything is and the other says what
#: is happening where you are.
VIEW_SHARE, SIGHT_SHARE = 0.635, 0.345

#: The sight: how far up the wire it shows, how many stations it cuts
#: that into, how many sides each has, and how wide a view it takes.
SIGHT_AHEAD, SIGHT_STATIONS, SIGHT_SIDES, SIGHT_FOV = 13.0, 30, 7, 22.0

#: The last few stations of the sight's slice draw in to nothing, so
#: the wire fades into the distance rather than stopping on the open
#: end of a pipe. Cosmetic, but the open end reads as an object.
SIGHT_TAPER = 6

#: How much of the sight panel's height the loop fills. The eye's
#: distance is solved from this rather than fixed, so a loop three
#: millimetres across on the top rung is drawn exactly as large as a
#: loop of two centimetres on the bottom one -- which is the whole
#: point of the panel.
SIGHT_FILL = 0.46

#: And how far off the wire's line the sight stands, as a share of that
#: distance. Straight down the wire would put the wire behind the loop
#: through the eye; a little above it, and the hole reads as a shallow
#: ellipse, which is worth having anyway.
SIGHT_RISE = 0.30

#: Which key does what. Six for the loop, four for the wrist, one to
#: brace — the same eleven the boundary hands out, in the same order,
#: so that the two versions are the same game.
KEYS: Dict[int, str] = {
    key.UP: 'up', key.DOWN: 'down', key.LEFT: 'left', key.RIGHT: 'right',
    key.W: 'in', key.S: 'out',
    key.I: 'tilt up', key.K: 'tilt down',
    key.J: 'tilt left', key.L: 'tilt right',
    key.LSHIFT: B.GRIP, key.RSHIFT: B.GRIP,
}

#: How close to the deadline a run may finish and still climb a rung on
#: an adaptive run. Two thirds of the clock, which on a rung the player
#: has the measure of is comfortable and on one they do not is not.
CLIMB_AT = 0.68


class Beads:
    """The milestones on the wire, lit as the loop passes them.

    Its own vertex list rather than a :class:`~.scene3d.Solid` because
    what changes here is the *colour*, one bead at a time, and nothing
    else: the camera does not move and neither do the beads, so their
    places and depths are worked out when the level is dealt and never
    again.
    """

    def __init__(self, wire: B.Wire, camera: Camera,
                 batch: pyglet.graphics.Batch, size: float) -> None:
        self.count = wire.beads
        places: List[float] = []
        depths: List[float] = []
        for bead in range(1, wire.beads + 1):
            point, _tangent = wire.at(wire.bead_arc(bead))
            for corner in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0),
                           (-1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)):
                at = (point[0] + camera.right[0] * corner[0] * size
                      + camera.up[0] * corner[1] * size,
                      point[1] + camera.right[1] * corner[0] * size
                      + camera.up[1] * corner[1] * size,
                      point[2] + camera.right[2] * corner[0] * size
                      + camera.up[2] * corner[1] * size)
                x, y, depth = camera.project(at)
                places.extend((x, y))
                # A shade in front of the wire, so a bead is never half
                # swallowed by the tube it is sitting on.
                depths.append(depth * 1.004)
        program = pyglet.shapes.get_default_shader()
        corners = 6 * self.count
        self.list = program.vertex_list(
            corners, gl.GL_TRIANGLES, batch=batch,
            position=('f', places), zposition=('f', depths),
            colors=('f', [0.0] * (4 * corners)),
            translation=('f', [0.0] * (2 * corners)))
        self.reached = -1
        self.mark(0)

    def mark(self, reached: int) -> None:
        """Light every bead up to *reached* and dim the rest."""
        if reached == self.reached:
            return
        self.reached = reached
        done = [channel / 255. for channel in BEAD_DONE] + [1.0]
        todo = [channel / 255. for channel in BEAD_TODO] + [0.65]
        colours: List[float] = []
        for bead in range(1, self.count + 1):
            colours.extend((done if bead <= reached else todo) * 6)
        self.list.colors[:] = colours

    def delete(self) -> None:
        try:
            self.list.delete()
        except Exception:
            pass


class BuzzWire:
    """Run the loop from post to post without touching. Esc leaves."""

    instance: Optional['BuzzWire'] = None

    def __init__(self) -> None:
        if BuzzWire.instance is not None:
            BuzzWire.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.wire: Optional[B.Wire] = None
        self.hand: Optional[B.Hand] = None
        self.grade = B.GRADES[0]
        self.camera: Optional[Camera] = None
        self.trial = 0
        self.results: List[Tuple[int, bool, int, float]] = []
        #                 (rung, home, buzzes, seconds)
        self.buzzes = 0
        self.started_at = 0.0
        self.deadline = 0.0
        self.spark_until = -1.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        #: Off for a person, so the human game is pixel-identical to
        #: what it was before coach mode existed. Turned on only by a
        #: boundary that will actually pay per action -- see
        #: :class:`nwenv.buzzwire.BuzzWireEnv`.
        self.coach = False
        #: Seconds a wire is allowed, or None for the rung's own clock.
        #: A knob rather than a fixed number so that a boundary can ask
        #: for a short wire without pretending to be a different rung --
        #: a sweep that wants to see a verdict inside nine hundred ticks
        #: needs one, and changing the rung to get it would be measuring
        #: a different wire.
        self.seconds: Optional[float] = None
        self.held: set = set()
        self._asked: Optional[int] = None
        self._read_options()
        self.rung = B.clamped_rung(self.start_rung)
        self.scene = pyglet.graphics.Batch()
        self.sight = pyglet.graphics.Batch()
        self.flat = pyglet.graphics.Batch()
        self.solids: List[Solid] = []
        self.sight_wire: Optional[Solid] = None
        self.sight_loop: Optional[Solid] = None
        self.loop: Optional[Solid] = None
        self.shade: Optional[Solid] = None
        self.beads: Optional[Beads] = None
        self.backdrop: List[object] = []
        #: Where the board's top face sits, in world centimetres. Set
        #: when a level is dealt; only read once there is one.
        self.floor = 0.0
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_key_release,
                                   self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        BuzzWire.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.BUZZ_WIRE)
        self.start_rung = int(opts['BUZZ_LEVEL'])
        self.total_trials = int(opts['BUZZ_TRIALS'])
        self.adaptive = bool(opts['BUZZ_ADAPTIVE'])
        self.show_meter = bool(opts['BUZZ_METER'])
        self.show_beads = bool(opts['BUZZ_BEADS'])
        self.show_sight = bool(opts['BUZZ_SIGHT'])

    def open_options(self) -> None:
        taskoptions.open_task_options('buzz_wire', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _view_rect(self) -> Tuple[float, float, float, float]:
        """The left panel: the whole wire, from this rung's camera."""
        left, bottom, width, height = self._stage()
        return (left, bottom, width * VIEW_SHARE, height)

    def _sight_rect(self) -> Tuple[float, float, float, float]:
        """The right panel: the view down the wire from behind the loop.

        Without this the task is not playable and not learnable, and the
        reason is arithmetic rather than taste. A wire is forty
        centimetres of stage; the clearance on the top rung is under two
        millimetres. Drawn to scale that gap is a fifth of a pixel, so
        the one quantity the whole game is about would not be in the
        picture at all -- and a task whose answer is not in the frame is
        not a task this workshop can wrap.

        What it does *not* do is give the game away, and the line is
        worth being exact about. It shows where the loop sits in its
        hole now, and the wire for a few centimetres ahead. It does not
        show the rest of the wire, so which way the run bends after that
        -- and therefore when to start turning the wrist -- is still
        read off the left panel, where the camera's angle is the
        difficulty dial it was before.
        """
        left, bottom, width, height = self._stage()
        return (left + width * (1.0 - SIGHT_SHARE), bottom,
                width * SIGHT_SHARE, height)

    def _stage(self) -> Tuple[float, float, float, float]:
        """Where the world is drawn, and it stops above the band.

        Everything in this task is a lit metal surface against a dark
        sky, and a lit metal surface passes through every colour on its
        way to the background — so which of its blends land on the
        outcome reader's pattern is not a thing a palette can be chosen
        to avoid. The workshop's answer is the one used here: the art
        stops where :func:`~.verdict.above_the_band` says it stops, and
        the bottom quarter of the frame belongs to the verdict alone.
        """
        window = state.window
        top = from_top_edge(106)
        bottom = above_the_band(from_bottom_edge(64))
        return (window.width * 0.03, bottom, window.width * 0.94,
                max(80.0, top - bottom))

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            _('Buzz Wire'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(58),
            width=int(state.window.width * 0.94), multiline=True,
            align='center', anchor_x='center', anchor_y='top',
            font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu   Space: start   Arrows: move the loop'
              '   W/S: along the wire   I/K/J/L: turn it   Shift: brace'
              '   C: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour. Rebuilt with the chrome so a verdict already
        # up is put back: on_draw lays out before it draws, so the first
        # frame after a wire settles is exactly when a relayout would
        # otherwise drop it, and an outcome only sometimes derivable is
        # worse than one that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=58)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._build_scene()
        # And the status line with it. A relayout lands on the frame
        # the window changed size, which is not a frame anyone is
        # looking for a bug on, and an empty status line for a whole
        # trial is the sort of thing that gets blamed on the task.
        self._update_status()

    def relayout(self) -> None:
        self._build_chrome()

    # --- the world -------------------------------------------------------

    def _clear_scene(self) -> None:
        for solid in self.solids + [self.sight_wire, self.sight_loop]:
            if solid is not None:
                solid.delete()
        self.solids = []
        self.loop = self.shade = None
        self.sight_wire = self.sight_loop = None
        if self.beads is not None:
            self.beads.delete()
            self.beads = None
        for shape in self.backdrop:
            try:
                shape.delete()
            except Exception:
                pass
        self.backdrop = []

    def _aim(self, wire: B.Wire) -> Camera:
        """Stand the camera where the whole wire fits, and no closer.

        The distance is found rather than chosen: put the eye on this
        rung's line of sight, ask whether every point of the wire lands
        inside the stage, and back off by whatever factor it missed by.
        Two or three passes settle it. A fixed distance would frame a
        long wire badly and a short one from orbit, and the wires differ
        by half their length across the ladder.
        """
        rect = self._view_rect()
        _right, _up, forward = B.camera_basis(self.grade)
        # The board is drawn too, and it is wider than the wire, so
        # framing the wire alone puts a third of the board off the
        # panel and the whole scene visibly off to one side.
        low = [min(point[axis] for point in wire.points) for axis in range(3)]
        high = [max(point[axis] for point in wire.points) for axis in range(3)]
        board = wire.span * 0.62
        deep = wire.span * 0.30
        floor = low[1] - 6.0
        corners = list(wire.points) + [
            (side * board, floor, back * deep)
            for side in (-1.0, 1.0) for back in (-1.0, 1.0)]
        # Room for the handle, which stands well above the wire and is
        # the first thing to disappear off the top of a snug framing.
        corners += [(point[0], point[1] + 6.0, point[2])
                    for point in wire.points[::8]]
        middle = [(low[axis] + high[axis]) / 2.0 for axis in range(3)]
        middle[1] = (high[1] + floor) / 2.0
        aim = tuple(middle)
        away = (max(high[axis] - low[axis] for axis in range(3)) or 1.0) * 1.6
        camera = None
        for _pass in range(10):
            eye = (aim[0] - forward[0] * away, aim[1] - forward[1] * away,
                   aim[2] - forward[2] * away)
            camera = Camera(eye, aim, FOV, rect)
            fits, over = camera.frames(corners)
            if not fits:
                away *= over
                continue
            # Fitting is not the same as being centred: the middle of a
            # box in the world is not the middle of its picture once
            # there is any perspective at all. So slide the aim until
            # the drawn extremes sit either side of the panel's centre.
            spots = [camera.project(corner) for corner in corners]
            drift_x = (min(x for x, _y, _d in spots)
                       + max(x for x, _y, _d in spots)) / 2.0 - rect[0] \
                - rect[2] / 2.0
            drift_y = (min(y for _x, y, _d in spots)
                       + max(y for _x, y, _d in spots)) / 2.0 - rect[1] \
                - rect[3] / 2.0
            if abs(drift_x) < 1.0 and abs(drift_y) < 1.0:
                break
            scale = camera.focal / away
            aim = B.add(aim, B.add(B.scale(camera.right, drift_x / scale),
                                   B.scale(camera.up, drift_y / scale)))
        return camera

    def _build_scene(self) -> None:
        """Everything that does not move, projected once."""
        self._clear_scene()
        self.scene = pyglet.graphics.Batch()
        self.sight = pyglet.graphics.Batch()
        self.flat = pyglet.graphics.Batch()
        # The sky, drawn flat and first, once for each panel. Nothing
        # writes depth with the test off, so the world lands on top of
        # it cleanly.
        self.backdrop = []
        panels = [self._view_rect()]
        if self.show_sight:
            panels.append(self._sight_rect())
        for left, bottom, width, height in panels:
            self.backdrop += [pyglet.shapes.Rectangle(
                left, bottom + height * band / 6.0, width, height / 6.0 + 1.0,
                color=tuple(int(round(low + (high - low) * (band + 0.5) / 6.0))
                            for low, high in zip(SKY_LOW, SKY_HIGH)),
                batch=self.flat) for band in range(6)]
        if self.wire is None or self.camera is None:
            return
        wire, camera = self.wire, self.camera
        floor = min(point[1] for point in wire.points) - 5.2

        board = slab((0.0, floor - 1.5, 0.0),
                     (wire.span * 0.60, 1.5, wire.span * 0.30))
        self.solids.append(Solid(*board, colour=BOARD, batch=self.scene,
                                 shine=0.10))
        self.solids[-1].place(camera, LIGHT)

        posts = [rod((point[0], floor, point[2]), point, 0.34, sides=8)
                 for point in (wire.points[0], wire.points[-1])]
        self.solids.append(Solid(*merge(*posts), colour=POST,
                                 batch=self.scene, shine=0.35))
        self.solids[-1].place(camera, LIGHT)

        # The wire's own shadow on the board. With the camera swung
        # round towards the wire's axis this is most of what is left to
        # say which way a bend goes, so it is drawn for every rung.
        flattened = [(point[0], floor + 0.02, point[2])
                     for point in wire.points]
        runs = [B.unit(B.sub(after, before))
                for before, after in zip(flattened, flattened[1:])]
        # The last station has no station after it to point at, so it
        # keeps the one before's heading. Letting it fall out as a zero
        # vector puts one ring of the mesh at a right angle to the rest,
        # which shows on the board as a flake at the far post.
        runs.append(runs[-1])
        self.solids.append(Solid(*tube(flattened, runs, wire.radius * 2.4,
                                       sides=4),
                                 colour=SHADOW, batch=self.scene, shine=0.0))
        self.solids[-1].place(camera, LIGHT)

        self.solids.append(Solid(*tube(wire.points, wire.tangents,
                                       wire.radius, sides=10),
                                 colour=WIRE, batch=self.scene, shine=1.0))
        self.solids[-1].place(camera, LIGHT)

        if self.show_beads:
            self.beads = Beads(wire, camera, self.scene,
                               wire.radius * 1.15)

        # And the two things that do move: the loop, and its shadow.
        self.shade = Solid(*torus(self.grade.hole, B.RIM * 0.5, around=16,
                                  through=4),
                           colour=SHADOW, batch=self.scene, shine=0.0)
        self.loop = Solid(*merge(torus(self.grade.hole, B.RIM, around=22,
                                       through=7),
                                 rod((0.0, self.grade.hole + B.RIM, 0.0),
                                     (0.0, self.grade.hole + B.RIM + 4.6,
                                      1.1), 0.30, sides=6)),
                          colour=LOOP, batch=self.scene, shine=1.0)
        self.floor = floor
        self._build_sight()
        self._place_loop()

    def _build_sight(self) -> None:
        """Allocate the sight's slice of wire and its own copy of the loop.

        The slice is a different piece of wire every frame but always
        the same number of stations, so one vertex list serves the whole
        level and :meth:`~.scene3d.Solid.reshape` writes the new
        geometry into it. Allocating a mesh a frame is the one thing
        this renderer cannot afford.
        """
        self.sight_wire = self.sight_loop = None
        if not self.show_sight or self.wire is None:
            return
        empty = [(0.0, 0.0, 0.0)] * SIGHT_STATIONS
        along = [(1.0, 0.0, 0.0)] * SIGHT_STATIONS
        self.sight_wire = Solid(*tube(empty, along, self.wire.radius,
                                      sides=SIGHT_SIDES, taper=SIGHT_TAPER),
                                colour=WIRE, batch=self.sight, shine=1.0)
        self.sight_loop = Solid(*torus(self.grade.hole, B.RIM, around=30,
                                       through=8),
                                colour=LOOP, batch=self.sight, shine=1.0)

    def _place_sight(self) -> None:
        """Re-aim the sight and refill the slice of wire it looks down."""
        if self.sight_wire is None or self.hand is None:
            return
        hand, wire = self.hand, self.wire
        _here, tangent = wire.at(hand.arc)
        away = ((self.grade.hole + B.RIM)
                / max(1e-6, SIGHT_FILL * math.tan(math.radians(SIGHT_FOV / 2))))
        rise = B.unit(B.sub((0.0, 1.0, 0.0),
                            B.scale(tangent, tangent[1])))
        eye = B.add(B.sub(hand.centre, B.scale(tangent, away)),
                    B.scale(rise, away * SIGHT_RISE))
        camera = Camera(eye, hand.centre, SIGHT_FOV, self._sight_rect())

        # From the loop forward only, and no further than the point
        # where the wire turns back towards the eye. Both halves matter.
        # The wire *behind* the loop lies between here and the eye, so
        # drawing it would fill the panel with the inside of a tube; and
        # on the top rungs the wire ahead bends tightly enough to come
        # back past the eye within a few centimetres, which looks the
        # same and is the same problem arriving from the other end.
        forward = B.unit(B.sub(hand.centre, eye))
        reach = SIGHT_AHEAD
        probes = 24
        for probe in range(1, probes + 1):
            at = min(wire.length, hand.arc + SIGHT_AHEAD * probe / probes)
            point, _run = wire.at(at)
            if B.dot(B.sub(point, eye), forward) < away * 0.95:
                reach = SIGHT_AHEAD * (probe - 1) / probes
                break
        step = max(0.02, reach) / float(SIGHT_STATIONS - 1)
        points, runs = [], []
        for station in range(SIGHT_STATIONS):
            at = min(wire.length, hand.arc - 0.04 + station * step)
            point, run = wire.at(at)
            points.append(point)
            runs.append(run)
        verts, norms, _indices = tube(points, runs, wire.radius,
                                      sides=SIGHT_SIDES,
                                      taper=SIGHT_TAPER)
        self.sight_wire.reshape(verts, norms)
        self.sight_wire.place(camera, LIGHT)
        spark = self.clock() < self.spark_until
        self.sight_loop.place(camera, LIGHT, turn=self._loop_frame(),
                              offset=hand.centre,
                              tint=SPARK if spark else LOOP)

    def _loop_frame(self) -> Tuple[B.Vec, B.Vec, B.Vec]:
        """Where the loop's own x, y and z axes point in the world."""
        axis = self.hand.axis
        across = B.unit(B.cross(axis, (0.0, 1.0, 0.0)))
        return (across, B.cross(across, axis), axis)

    def _place_loop(self) -> None:
        """Move the loop and its shadow to where the hand has them."""
        if self.loop is None or self.hand is None or self.camera is None:
            return
        hand, camera = self.hand, self.camera
        axis = hand.axis
        spark = self.clock() < self.spark_until
        self.loop.place(camera, LIGHT, turn=self._loop_frame(),
                        offset=hand.centre, tint=SPARK if spark else LOOP)
        if self.shade is not None:
            # Flattened onto the board: the loop's own frame with the
            # height taken out and the axis laid down.
            flat_axis = B.unit((axis[0], 0.0, axis[2]))
            flat_across = B.unit(B.cross(flat_axis, (0.0, 1.0, 0.0)))
            self.shade.place(
                camera, LIGHT,
                turn=(flat_across, (0.0, 0.06, 0.0), flat_axis),
                offset=(hand.centre[0], self.floor + 0.05, hand.centre[2]))
        if self.beads is not None:
            self.beads.mark(hand.bead())
        self._place_sight()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.wire = None
        self.hand = None
        self.rung = B.clamped_rung(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None
        self.held = set()
        self._asked = None

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _allowed(self) -> float:
        """Seconds this wire gets: the caller's, or the rung's own."""
        return float(self.seconds) if self.seconds else self.grade.seconds

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.verdict_shown = None
        self.verdict.clear()
        self.grade = B.grade_of(self.rung)
        self.wire = B.deal(self.rung, seed=self.rng.randrange(1 << 30))
        self.hand = B.Hand(self.wire, self.grade, rng=self.rng)
        self.camera = self._aim(self.wire)
        self.buzzes = 0
        self.held = set()
        self._asked = None
        self.spark_until = -1.0
        self.started_at = self.clock()
        self.deadline = self.started_at + self._allowed()
        self.phase = 'flying'
        allowed = self.grade.touches
        self.message = (
            _('Level %d, "%s" — no touches allowed') % (self.rung,
                                                        _(self.grade.name))
            if allowed == 0 else
            _('Level %d, "%s" — %d touches allowed')
            % (self.rung, _(self.grade.name), allowed))
        self._build_scene()
        self._update_status()

    # --- driving ---------------------------------------------------------

    def press(self, port: int) -> None:
        """One port, applied on the next tick.

        Held rather than acted on immediately, because the physics is
        integrated once a frame and an impulse applied outside that
        would be worth an amount that depended on when it arrived. A
        person holding a key and a boundary naming a port therefore
        buy exactly the same thing.
        """
        if self.phase != 'flying':
            return
        if 0 <= int(port) < len(B.PORTS):
            self._asked = int(port)

    def _wanted(self) -> Tuple[Optional[B.Vec], Tuple[float, float], bool]:
        """This tick's shove, twist and brace, from keys and from ports."""
        names = set(self.held)
        if self._asked is not None:
            names.add(B.PORTS[self._asked])
            self._asked = None
        shove = (0.0, 0.0, 0.0)
        pushing = False
        for name in names & set(B.PUSHES):
            shove = B.add(shove, B.push_vector(self.grade, name))
            pushing = True
        pitch = ((1.0 if 'tilt up' in names else 0.0)
                 - (1.0 if 'tilt down' in names else 0.0))
        yaw = ((1.0 if 'tilt left' in names else 0.0)
               - (1.0 if 'tilt right' in names else 0.0))
        # Two keys at once is a diagonal, not a shove half again as
        # hard: the arm has one strength whichever way it is pointed.
        if pushing and B.length(shove) > 1e-9:
            shove = B.unit(shove)
        elif pushing:
            shove = None
            pushing = False
        return (shove if pushing else None, (pitch, yaw), B.GRIP in names)

    def update(self, dt: float) -> None:
        """One frame of the world."""
        if self.phase != 'flying' or self.hand is None:
            return
        push, twist, grip = self._wanted()
        before = self.hand.beads_left()
        step = self.hand.advance(min(dt, 0.1), push=push, twist=twist,
                                 grip=grip)
        if step.buzzed:
            self.buzzes += 1
            self.spark_until = self.clock() + SPARK_SECONDS
        self._place_loop()
        if self.buzzes > self.grade.touches:
            self._lost(_('Buzz — one touch and the run is over')
                       if self.buzzes == 1 else
                       _('Buzz — %d touches and the run is over')
                       % self.buzzes)
        elif step.home:
            self._home()
        elif self.clock() >= self.deadline:
            self._lost(_('Out of time, %d%% of the way along')
                       % int(100.0 * self.hand.arc / self.wire.length))
        else:
            self._coach_verdict(self.hand.beads_left() - before)
        self._update_status()

    def _coach_verdict(self, delta: int) -> None:
        """Paint what the tick just past did to the distance still to go.

        A consequence of a move already made, never a hint about the
        next one. The potential is the count of beads still ahead and
        nothing else: it is a function of what is drawn — the lit beads
        *are* the count — and one tick can change it by one at most,
        which :func:`neural_workshop.buzzwire.bead_count` guarantees by
        spacing the beads against the furthest a tick could ever carry
        the loop. Under those two the sign of the change is exactly the
        potential-based shaping term of Ng et al.: every closed loop of
        actions telescopes to zero and the best policy is the same one
        the sparse verdict would have picked.

        A tick that gained no bead and lost none clears the label and is
        paid nothing. That is not tidiness either — a tick that paid for
        standing still would be a tick worth repeating forever.
        """
        if not self.coach:
            return
        if delta == 0:
            self.verdict_shown = None
            self.verdict.clear()
            return
        closer = delta < 0
        self.verdict_shown = (closer,
                              _('Warmer') if closer else _('Colder'))
        self.verdict.show(*self.verdict_shown)

    def _home(self) -> None:
        took = self.clock() - self.started_at
        self.results.append((self.rung, True, self.buzzes, took))
        if not self.buzzes:
            self.message = _('Home, clean, in %.1fs') % took
        elif self.buzzes == 1:
            self.message = _('Home in %.1fs, with one touch') % took
        else:
            self.message = _('Home in %.1fs, with %d touches') % (
                took, self.buzzes)
        if self.adaptive and took <= self._allowed() * CLIMB_AT:
            self.rung = B.clamped_rung(self.rung + 1)
        self.phase = 'won'
        self.verdict_shown = (True, self.message)
        self.verdict.show(*self.verdict_shown)
        self._update_status()

    def _lost(self, why: str) -> None:
        took = self.clock() - self.started_at
        self.results.append((self.rung, False, self.buzzes, took))
        self.message = why
        if self.adaptive:
            self.rung = B.clamped_rung(self.rung - 1)
        self.phase = 'lost'
        self.verdict_shown = (False, why)
        self.verdict.show(*self.verdict_shown)
        self._update_status()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d wires of %d run clean through, highest level %d')\
            % (tally['home'], tally['wires'], tally['best_rung'])
        self._update_status()

    def score(self) -> Dict[str, int]:
        return {
            'wires': len(self.results),
            'home': sum(1 for _r, home, _b, _s in self.results if home),
            'touches': sum(buzz for _r, _h, buzz, _s in self.results),
            'best_rung': max((rung for rung, home, _b, _s in self.results
                              if home), default=0),
        }

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase == 'flying' and self.hand is not None:
            along = int(100.0 * self.hand.arc / max(1e-6, self.wire.length))
            left = max(0.0, self.deadline - self.clock())
            said = _('wire %d/%d   %d%%   %.0fs   touched %d/%d') \
                % (self.trial, self.total_trials, along, left, self.buzzes,
                   self.grade.touches)
            if self.show_meter:
                room = max(1e-6, B.clearance(self.grade))
                used = min(1.0, self.hand.offset() / room)
                said += _('   gap %s') % _gauge(used)
            parts.append(said)
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if BuzzWire.instance is not self:
            return
        self._clear_scene()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_key_release,
                                     self.on_draw)
        BuzzWire.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase in ('won', 'lost'):
                self._next_trial()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in KEYS:
            self.held.add(KEYS[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol: int, modifiers: int) -> bool:
        self.held.discard(KEYS.get(symbol))
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.flat.draw()
        DepthPass(self.scene, inside=self._view_rect()).draw()
        if self.show_sight:
            DepthPass(self.sight, inside=self._sight_rect()).draw()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def _gauge(used: float, cells: int = 8) -> str:
    """A little bar of how much of the clearance is gone."""
    full = int(round(min(1.0, max(0.0, used)) * cells))
    return '[%s%s]' % ('#' * full, '.' * (cells - full))
