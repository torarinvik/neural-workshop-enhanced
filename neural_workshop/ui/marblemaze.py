# -*- coding: utf-8 -*-
"""The Marble Maze screen: a wooden tray, seen in three dimensions, tipping.

The physics and the trays live in :mod:`neural_workshop.marblemaze`;
this module is the picture of them and the two knobs that tip the
picture. It is the workshop's only screen with a real perspective
pipeline behind it — depth buffer, directional light, shadow map — and
:mod:`neural_workshop.ui.render3d` is where that lives.

**Why it has to be real 3D**, when the 3D Maze and 3D Sokoban get by on
ray-cast columns: those two draw a corridor from inside it, where every
surface is vertical and the only unknown is distance. Here the thing
the player is learning to operate is *the angle of a plane*, and the
whole feedback loop is watching that plane tip and predicting what the
marble will do about it. A flat rendering can show where the marble is;
it cannot show the tilt, which is the input. The task would be a
different task.

**What the frame gives away, and what it does not.** Everything the
player needs is drawn: the tray, its walls, every hole, the cup in
green, the marbles, and the tilt itself — which is legible from the
tray's silhouette and from the shadows swinging under it. What is *not*
drawn is any route, any distance, any marking of which hole is near, and
no number that a solver would want. The status line carries the rung,
the count and the clock, and those are all recoverable from watching.

**The clock is the driver's.** ``self.clock`` is swapped for a virtual
one by :mod:`nwenv.marblemaze`, and the physics is stepped from ``dt``
rather than from elapsed real time, so a stepped run and a played run
are the same run. Nothing here calls :func:`time.time` except the one
line that installs the default.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.math import Mat4, Quaternion, Vec3
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, framebuffer_size, from_bottom_edge,
                        from_top_edge, pixel_size, width_center)
from .. import marblemaze as MM
from ..i18n import _
from . import cursor, render3d, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Seconds the verdict stays up before the next tray is dealt.
FEEDBACK_SECONDS = 2.6

#: How close to par a run has to be for an adaptive run to climb. Looser
#: than the flat puzzles', because a tray is finished by steering rather
#: than by finding, and a good line taken carefully is still slow.
CLIMB_AT = 1.6

#: Materials, in the light this room has.
PINE = (0.80, 0.63, 0.41)
WALNUT = (0.29, 0.18, 0.11)
STEEL = (0.86, 0.88, 0.93)
#: The board's own thickness, seen down a hole. Timber rather than
#: black: a hole shaded flat black reads as a sticker on the tray.
SAWN = (0.58, 0.44, 0.31)
GREEN = (0.16, 0.55, 0.30)


def _cup_collar_outer_radius(hole, walls) -> Optional[float]:
    """Fit the decorative cup collar inside the nearest wall clearance.

    The hole itself is guaranteed a small wall gap by the tray generator, but
    the original full-size collar is wider than that opening and could be
    hidden under a wall. Keep the clear aperture unchanged and trim only the
    visual annulus; return None if a malformed/very tight board leaves no room.
    """
    nearest_wall = min((
        math.hypot(max(wall.x0 - hole.x, 0.0, hole.x - wall.x1),
                   max(wall.y0 - hole.y, 0.0, hole.y - wall.y1))
        for wall in walls
    ), default=math.inf)
    available = min(hole.radius * 1.34,
                    nearest_wall - MM.HOLE_WALL_CLEARANCE)
    return available if available > hole.radius else None

#: Where the light is, and what the room around the tray looks like to a
#: mirrored surface. High, over the player's left shoulder — the angle a
#: desk lamp would be, and the one that puts a marble's shadow where the
#: eye expects to find it.
LIGHT = render3d.Light(
    direction=(-0.38, 0.86, 0.34),
    colour=(1.0, 0.97, 0.90),
    sky=(0.76, 0.81, 0.90),
    # The "ground" is what a mirrored surface sees *downwards*, and on
    # this screen that is the tray. Warm rather than neutral grey, and
    # the difference is the whole of whether a marble looks like a ball
    # bearing on wood or a white ball in a vacuum.
    ground=(0.42, 0.30, 0.19),
    span=0.30)

#: Camera elevation and how much of the tray to leave around the edges.
ELEVATION = math.radians(47.0)
FRAMING = 1.30


def _turned(marble: MM.Marble) -> Mat4:
    """A marble's orientation, as a matrix in the stage's frame.

    The model keeps it as a quaternion in the *tray's* frame, where x
    runs across the tray, y up it and z out of it. The stage works in
    the room's frame, which the tray meets at ``(x, z, -y)``, and a
    rotation carries between them by moving its axis the same way —
    which for a quaternion means moving the vector part and leaving the
    scalar alone.

    The conjugate is there because pyglet's ``Quaternion.to_mat4``
    hands back the transpose of what ``Mat4.from_rotation`` builds for
    the same turn, and this end of the pipe is the one that has to
    agree with the rest of the stage.
    """
    return Quaternion(marble.qw, -marble.qx, -marble.qz,
                      marble.qy).to_mat4()


class MarbleMaze:
    """Tip the tray, roll the marbles home, miss the holes. Esc for the hub."""

    instance: Optional['MarbleMaze'] = None

    def __init__(self) -> None:
        if MarbleMaze.instance is not None:
            MarbleMaze.instance.close()
        self.rng = random.Random()
        #: Swapped out by the agent environment for a virtual clock.
        self.clock = time.time
        self.tray: Optional[MM.Tray] = None
        self.sim: Optional[MM.Simulation] = None
        #: This tray's budget in seconds, once one is dealt.
        self.seconds = 0.0
        self.trial = 0
        self.results: List[Tuple[int, float, int, int]] = []
        #                 (rung, seconds, home, lost)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.until = 0.0
        self.started_at = 0.0
        self.held: set = set()
        #: Held-key time not yet spent as knob nudges. See :meth:`update`.
        self._nudge_due = 0.0
        #: When the last frame was drawn, on the wall clock. None until
        #: the first, and only ever read under a running event loop.
        self._drawn_at: Optional[float] = None
        #: Set by the agent boundary when it is paying per action. Off
        #: for a person, so the human game stays pixel-identical.
        self.coach = False
        self._last_potential: Optional[int] = None
        self._read_options()
        self.rung = MM.clamped_rung(self.start_rung)
        self.stage = render3d.Stage()
        self.textured = self._load_marble_maps()
        self.meshes: Dict[str, render3d.Mesh] = {}
        self.marble_mesh: Optional[render3d.Mesh] = None
        self._holes_uniform: Tuple[Tuple[float, float, float, float], ...] = ()
        self._build_chrome()
        # Nothing is scheduled on the pyglet clock, and that is the
        # third design for this line, so the graveyard is worth
        # keeping. A 1/60 *interval* drifted against the redraw — which
        # is another interval item — so a drawn frame would carry two
        # physics steps in one stretch of play and none in the next,
        # and on a gliding sphere that alternation reads as the speed
        # pulsing. An *every-tick* item cured the drift and cost a
        # core: pyglet's loop stops sleeping when one exists, and the
        # update ran forty thousand times a second, measured. What a
        # marble needs is neither schedule — it is one step per drawn
        # frame, of exactly the wall time that frame represents, and
        # the only place that binding exists is the draw itself. See
        # the top of :meth:`on_draw`. The driver's path is unchanged:
        # it calls :meth:`update` with the dt it owns, as ever.
        state.window.push_handlers(self.on_key_press, self.on_key_release,
                                   self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        MarbleMaze.instance = self

    # --- the marble's surface --------------------------------------------

    def _load_marble_maps(self) -> bool:
        """The baked colour, roughness and normal maps, if they are here.

        They are baked out of a source asset that is not in this
        repository — ``tools/bake_marble_textures.py`` does it and the
        result is committed — so a checkout without them is a real case
        rather than a broken one, and :data:`render3d.FRAGMENT` keeps a
        procedural fallback for exactly that. A plainer marble is a
        fine outcome; a black one would not be.
        """
        from ..paths import get_res_dir
        folder = os.path.join(get_res_dir(), 'marblemaze')
        paths = [os.path.join(folder, name)
                 for name in ('marble_colour.png', 'marble_rough.png',
                              'marble_normal.png')]
        if not all(os.path.exists(path) for path in paths):
            return False
        return self.stage.load_marble_maps(*paths)

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.MARBLE_MAZE)
        self.start_rung = int(opts['MARBLE_MAZE_LEVEL'])
        self.total_trials = int(opts['MARBLE_MAZE_TRIALS'])
        self.adaptive = bool(opts['MARBLE_MAZE_ADAPTIVE'])
        self.show_shadows = bool(opts['MARBLE_MAZE_SHADOWS'])
        #: Seconds a tray is allowed. Nought means "whatever the rung
        #: says", which is what a player almost always wants; the
        #: override exists because a rung's own budget runs to well over
        #: two minutes, and both a player in a hurry and a test driving
        #: the boundary need a shorter tray to be the *same* tray rather
        #: than a different task. It is on the options screen rather
        #: than on the agent boundary alone, because an interface only
        #: the learner has would make the two into two games.
        self.time_limit = float(opts['MARBLE_MAZE_SECONDS'])

    def open_options(self) -> None:
        taskoptions.open_task_options('marble_maze',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            _('Marble Maze'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(62),
            width=int(state.window.width * 0.84), multiline=True,
            align='center', anchor_x='center', anchor_y='top',
            font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu   Space: start   Arrows: tip the tray'
              '   L: level it   R: restart   C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour. Rebuilt with the chrome, so a verdict already
        # up is put back — on_draw lays out before it draws, so the
        # first frame after a tray settles is exactly when a relayout
        # would otherwise drop it.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._update_status()

    def relayout(self) -> None:
        self._build_chrome()

    def _stage_rect(self) -> Tuple[int, int, int, int]:
        """Where the 3D pass goes, in framebuffer pixels.

        It stops where :func:`~neural_workshop.ui.verdict.above_the_band`
        says art stops, and here that is not a formality. The tray is
        lit pine over a warm shadow, and a wooden midtone like
        ``(196, 128, 74)`` is a saturated red as far as the outcome
        reader is concerned: red over 180, the other two under 140. A
        tray reaching into the bottom quarter of the frame would pay
        itself a losing verdict on any frame it happened to be lit
        that way, on trays nobody had lost.
        """
        window_w, window_h = pixel_size()
        bottom = above_the_band(from_bottom_edge(58))
        top = from_top_edge(88)
        left = int(window_w * 0.03)
        width = int(window_w * 0.94)
        height = max(48, top - bottom)
        # glViewport works in framebuffer pixels, which are the same as
        # layout pixels everywhere except under pyglet's stretched DPI
        # scaling. Getting this wrong puts the tray half off the screen
        # on exactly the machines nobody tests on.
        fb_w, fb_h = framebuffer_size(state.window)
        sx = fb_w / float(window_w) if window_w else 1.0
        sy = fb_h / float(window_h) if window_h else 1.0
        return (int(left * sx), int(bottom * sy),
                int(width * sx), int(height * sy))

    # --- the scene -------------------------------------------------------

    def _drop_meshes(self) -> None:
        for mesh in list(self.meshes.values()):
            mesh.delete()
        self.meshes = {}

    def _build_scene(self) -> None:
        """Turn the dealt tray into meshes. Once a tray, never per frame.

        Every wall is one box and every pit one tube, but they are all
        welded into three meshes rather than a hundred and thirty, so a
        frame is nine draw calls instead of two hundred and sixty across
        the two passes. Nothing here moves relative to anything else
        here — the tray tips as one rigid body — so there is nothing a
        per-object transform would buy.
        """
        self._drop_meshes()
        if not self.stage.ok or self.tray is None:
            return
        tray = self.tray
        program, depth = self.stage.program, self.stage.depth_program
        half_w, half_d = tray.width / 2.0, tray.depth / 2.0
        slab = 0.013
        pit_floor = -0.032
        rail = 0.016
        rail_high = max(0.020, tray.height * 1.25)

        def wx(bx: float) -> float:
            return bx - half_w

        def wz(by: float) -> float:
            return half_d - by

        # The body: the board itself, cut through by its holes. Cutting
        # the slab as well as its top face is what makes the holes go
        # *through* — a hole that stops at the surface has a floor 14mm
        # down, and the eye reads that as a dish rather than a drop.
        body = render3d.Builder()
        body.box(-half_w, -slab, -half_d, half_w, 0.0, half_d)
        self.meshes['body'] = body.build(program, depth)

        # The rails around the edge, which are not cut and do not need
        # to be: nothing is ever holed under them.
        frame = render3d.Builder()
        frame.box(-half_w - rail, -slab, -half_d - rail,
                  half_w + rail, rail_high, -half_d)
        frame.box(-half_w - rail, -slab, half_d,
                  half_w + rail, rail_high, half_d + rail)
        frame.box(-half_w - rail, -slab, -half_d,
                  -half_w, rail_high, half_d)
        frame.box(half_w, -slab, -half_d, half_w + rail, rail_high, half_d)
        self.meshes['frame'] = frame.build(program, depth)

        walls = render3d.Builder()
        for wall in tray.walls:
            walls.box(wx(wall.x0), 0.0, wz(wall.y1),
                      wx(wall.x1), tray.height, wz(wall.y0))
        if not walls.empty:
            self.meshes['walls'] = walls.build(program, depth)

        pits = render3d.Builder()
        cups = render3d.Builder()
        collar = render3d.Builder()
        for hole in tray.holes:
            target = cups if hole.home else pits
            target.tube(wx(hole.x), wz(hole.y), hole.radius, 0.0,
                        pit_floor, floor_disc=True)
            if hole.home:
                collar_outer = _cup_collar_outer_radius(hole, tray.walls)
                if collar_outer is not None:
                    collar.ring(wx(hole.x), wz(hole.y), hole.radius,
                                collar_outer, 0.0006)
        if not pits.empty:
            self.meshes['pits'] = pits.build(program, depth)
        if not cups.empty:
            self.meshes['cup'] = cups.build(program, depth)
        if not collar.empty:
            self.meshes['collar'] = collar.build(program, depth)

        if self.marble_mesh is None:
            ball = render3d.Builder()
            ball.sphere(MM.MARBLE_RADIUS)
            self.marble_mesh = ball.build(program, depth)

        # What the floor shader cuts, in the body's own coordinates.
        self._holes_uniform = tuple(
            (wx(hole.x), wz(hole.y), hole.radius, 1.0 if hole.home else 0.0)
            for hole in tray.holes)
        cut = self.stage.set_holes(self._holes_uniform)
        if cut < len(self._holes_uniform):
            # Never yet reached — the top rung asks for thirty-eight
            # against a ceiling of ninety-six — but a hole the shader
            # will not cut is a hole the physics still swallows marbles
            # into and the player cannot see, so it is said out loud
            # rather than discovered.
            self.message = _('This tray has more holes than can be drawn')
        self.stage.grain_seed = self.rng.random() * 4.0

    def _tilt_frame(self) -> Mat4:
        """The rigid rotation the whole tray is under.

        Pitch tips the far edge up, roll tips the right edge *down* —
        which is the sign the simulation uses, so a positive roll and a
        marble accelerating to the right are the same statement made
        twice.
        """
        sim = self.sim
        pitch = sim.pitch if sim else 0.0
        roll = sim.roll if sim else 0.0
        return (Mat4.from_rotation(pitch, Vec3(1.0, 0.0, 0.0))
                @ Mat4.from_rotation(-roll, Vec3(0.0, 0.0, 1.0)))

    def _camera(self, aspect: float
                ) -> Tuple[Mat4, Tuple[float, float, float]]:
        tray = self.tray
        width = tray.width if tray else MM.BOARD_WIDTH
        depth = tray.depth if tray else MM.BOARD_DEPTH
        # Far enough back that the whole tray fits whichever way the
        # viewport is shaped: the width needs the horizontal field and
        # the depth, foreshortened by the elevation, needs the vertical.
        fov = math.radians(36.0)
        half_v = math.tan(fov / 2.0)
        half_h = half_v * max(aspect, 0.35)
        span_x = width / 2.0 * FRAMING
        span_z = depth / 2.0 * FRAMING * math.sin(ELEVATION)
        distance = max(span_x / half_h, span_z / half_v) + depth * 0.25
        eye = (0.0, math.sin(ELEVATION) * distance,
               math.cos(ELEVATION) * distance)
        view = Mat4.look_at(Vec3(*eye), Vec3(0.0, 0.0, 0.0),
                            Vec3(0.0, 1.0, 0.0))
        proj = Mat4.perspective_projection(aspect, 0.02, 12.0, fov=36.0)
        return proj @ view, eye

    def _draws(self) -> List[render3d.Draw]:
        frame = self._tilt_frame()
        unit = (1.0, 1.0, 1.0)
        draws: List[render3d.Draw] = []

        def add(name: str, material: int, tint, cut: bool = False,
                casts: bool = True) -> None:
            mesh = self.meshes.get(name)
            if mesh is not None:
                draws.append(render3d.Draw(mesh, frame, unit, material,
                                           tint, cut, casts))

        add('body', render3d.OAK, PINE, cut=True)
        add('frame', render3d.OAK, PINE)
        add('walls', render3d.STAIN, WALNUT)
        add('pits', render3d.PIT, SAWN, casts=False)
        add('cup', render3d.PIT, (0.24, 0.44, 0.29), casts=False)
        add('collar', render3d.CUP, GREEN, casts=False)

        if self.sim is not None and self.marble_mesh is not None:
            half_w = self.tray.width / 2.0
            half_d = self.tray.depth / 2.0
            for marble in self.sim.marbles:
                if marble.state in ('home', 'lost'):
                    continue
                spin = _turned(marble)
                model, nscale = render3d.placed(
                    (marble.x - half_w, marble.z, half_d - marble.y),
                    spin=spin, frame=frame)
                draws.append(render3d.Draw(self.marble_mesh, model, nscale,
                                           render3d.STEEL, STEEL))
        return draws

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.tray = None
        self.sim = None
        self.rung = MM.clamped_rung(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None
        self._last_potential = None
        self.held.clear()
        self._drop_meshes()

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
        self.held.clear()
        self.tray = MM.deal(self.rung, seed=self.rng.randrange(1 << 30))
        self.seconds = self.time_limit or self.tray.seconds
        self.sim = MM.Simulation(self.tray)
        self._build_scene()
        self.started_at = self.clock()
        self.phase = 'rolling'
        grade = MM.GRADES[self.tray.rung - 1]
        # The rung's name and its clock, and nothing else. The marble
        # count is not repeated here: the status line already carries
        # "home 0/4" beside it, and saying it twice — "four marbles —
        # 4 marbles, 120s" — is what pushed the line onto a second row.
        self.message = _('%s — %ds') % (_(grade.name), int(self.seconds))
        self._last_potential = self.sim.potential() if self.paying else None
        self._update_status()

    def restart(self) -> None:
        """Put the marbles back at the door. The clock is not put back."""
        if self.phase != 'rolling' or self.tray is None:
            return
        self.sim = MM.Simulation(self.tray)
        self.held.clear()
        self._last_potential = self.sim.potential() if self.paying else None
        self.message = _('Marbles back at the start')
        self._update_status()

    @property
    def paying(self) -> bool:
        """Whether a per-action warmer/colder label is being painted.

        Single-marble trays only, and the restriction is not caution —
        it is the shaping rule. The potential is the summed quantised
        distance of every live marble, and the guarantee that one tick
        moves it by at most one step comes from a marble travelling at
        most 16.7mm in a tick against a 25mm quantum. That argument is
        about *a* marble. Three of them can each cross a boundary in the
        same tick, and measured on the top rung they do: the potential
        jumped by two, which is no longer the sign of a potential
        difference and no longer telescopes to nothing round a loop.
        So the upper rungs are honestly sparse rather than dishonestly
        dense.
        """
        return bool(self.coach and self.sim is not None
                    and len(self.sim.marbles) == 1)

    # --- the knobs -------------------------------------------------------

    def tilt(self, which: str) -> None:
        """One nudge of one knob. The agent boundary's whole vocabulary."""
        if self.phase != 'rolling' or self.sim is None:
            return
        self.sim.tilt(which)

    def level_tray(self) -> None:
        if self.phase == 'rolling' and self.sim is not None:
            self.sim.level()

    # --- the clock -------------------------------------------------------

    def update(self, dt: float) -> None:
        """One tick of real time: nudge the held knobs, step the sim.

        Two disciplines in here, both about *dt* being whatever the
        clock says rather than a sixtieth.

        The knobs are nudged on held-key *time*, through an
        accumulator, so a key held for a second is sixty nudges however
        often this happens to be called — every-tick scheduling runs
        once per clock tick, and another overlay's timer can add ticks.

        The sim is stepped in pieces no longer than a sixtieth, because
        its substep count is sized for that: one substep of a 60Hz step
        moves a capped marble 4mm, safely under a wall's thickness, and
        a long frame handed over whole would stretch the substeps past
        what the tunnelling test certifies. The 0.05 clamp is the usual
        spiral-of-death stop: a truly late frame drops time rather than
        spending the next frames catching up.
        """
        now = self.clock()
        if self.phase == 'rolling' and self.sim is not None:
            piece = min(dt, 0.05)
            if self.held:
                self._nudge_due += piece
                while self._nudge_due >= 1 / 60.:
                    self._nudge_due -= 1 / 60.
                    for which in self.held:
                        self.sim.tilt(which)
            else:
                self._nudge_due = 0.0
            left = piece
            while left > 0.0:
                bite = min(left, 1 / 60.)
                self.sim.step(bite)
                left -= bite
            self._pay_coach()
            if self.sim.settled:
                self._settle()
            elif self.sim.elapsed >= self.seconds:
                self._settle(timed_out=True)
            self._update_status()
        elif self.phase in ('won', 'lost') and now >= self.until:
            self._next_trial()

    def _pay_coach(self) -> None:
        """Warmer or colder, once per tick, on single-marble trays.

        The potential reads only what the frame already shows — where
        the marble is and where the cup is — so the label accelerates a
        learner without telling it anything a pixel does not. A tick in
        which the potential did not move pays nothing and the label
        comes down: an action that changes nothing must be worth
        nothing, or standing still against a wall would farm it.
        """
        if not self.paying:
            return
        now = self.sim.potential()
        before = self._last_potential
        self._last_potential = now
        if now is None or before is None or now == before:
            self.verdict_shown = None
            self.verdict.clear()
            return
        closer = now < before
        self.verdict_shown = (closer, _('Warmer') if closer else _('Colder'))
        self.verdict.show(*self.verdict_shown)

    def _settle(self, timed_out: bool = False) -> None:
        sim, tray = self.sim, self.tray
        took = sim.elapsed
        self.results.append((tray.rung, took, sim.home, sim.lost))
        par = MM.par_seconds(tray)
        won = sim.won and not timed_out
        if won:
            self.message = (_('Home in %ds — a good line was about %ds')
                            % (int(took), int(par)))
        elif timed_out:
            self.message = _('Out of time — %d of %d home') % (
                sim.home, len(sim.marbles))
        elif sim.lost == 1:
            self.message = _('Down a hole — %d of %d home') % (
                sim.home, len(sim.marbles))
        else:
            self.message = _('%d marbles down a hole') % sim.lost
        if self.adaptive:
            if won and took <= par * CLIMB_AT:
                self.rung = MM.clamped_rung(self.rung + 1)
            elif not won:
                self.rung = MM.clamped_rung(self.rung - 1)
        self.phase = 'won' if won else 'lost'
        self.until = self.clock() + FEEDBACK_SECONDS
        # Painted only now, with the action window already shut: a
        # verdict up while a port still does something is an answer key
        # rather than a verdict.
        self.verdict_shown = (won, self.message)
        self.verdict.show(*self.verdict_shown)
        self._update_status()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d trays of %d, %d marbles lost, highest '
                         'rung %d') % (tally['won'], tally['trays'],
                                       tally['lost'], tally['best_rung'])
        self.verdict_shown = None
        self.verdict.clear()
        self._update_status()

    def score(self) -> Dict[str, int]:
        won = sum(1 for _r, _s, _h, lost in self.results if not lost)
        return {
            'trays': len(self.results),
            'won': won,
            'lost': sum(lost for _r, _s, _h, lost in self.results),
            'home': sum(home for _r, _s, home, _l in self.results),
            'best_rung': max((rung for rung, _s, _h, _l in self.results),
                             default=0),
            'seconds': int(sum(took for _r, took, _h, _l in self.results)),
        }

    # --- the words -------------------------------------------------------

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase == 'rolling' and self.sim is not None:
            left = max(0.0, self.seconds - self.sim.elapsed)
            parts.append(_('tray %d/%d   home %d/%d   %ds left   '
                           'tilt %d°/%d°')
                         % (self.trial, self.total_trials, self.sim.home,
                            len(self.sim.marbles), int(left),
                            round(math.degrees(self.sim.roll)),
                            round(math.degrees(self.sim.pitch))))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if MarbleMaze.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        self._drop_meshes()
        if self.marble_mesh is not None:
            self.marble_mesh.delete()
            self.marble_mesh = None
        self.stage.close()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_key_release,
                                     self.on_draw)
        MarbleMaze.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events ----------------------------------------------------------

    #: Arrow keys to knobs. Up sends the marble away from the player,
    #: which is north on the tray — and the knobs are named for where
    #: the marble goes, so the map is the identity it looks like.
    _KEYS = {
        key.UP: MM.TILT_NORTH, key.W: MM.TILT_NORTH,
        key.DOWN: MM.TILT_SOUTH, key.S: MM.TILT_SOUTH,
        key.LEFT: MM.TILT_WEST, key.A: MM.TILT_WEST,
        key.RIGHT: MM.TILT_EAST, key.D: MM.TILT_EAST,
    }

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase in ('won', 'lost'):
                self._next_trial()
        elif symbol in self._KEYS:
            self.held.add(self._KEYS[symbol])
        elif symbol == key.L:
            self.level_tray()
        elif symbol == key.R:
            self.restart()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol: int, modifiers: int) -> bool:
        self.held.discard(self._KEYS.get(symbol))
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        # A person's physics is stepped here, and only here: once per
        # drawn frame, by the wall time since the last one, so what the
        # eye is shown is exactly the motion that time held. Gated on
        # the event loop actually running, which is true for a person
        # and false everywhere else — the driver calls update() with a
        # dt it owns and dispatches this handler for captures, and a
        # test that draws a frame must not nudge the sim by however
        # long the test happened to take.
        loop = pyglet.app.event_loop
        if loop is not None and loop.is_running:
            now = time.perf_counter()
            last, self._drawn_at = self._drawn_at, now
            if last is not None:
                self.update(now - last)
        display.ensure_laid_out()
        state.window.clear()
        if self.tray is not None and self.stage.ok:
            aspect_rect = self._stage_rect()
            aspect = aspect_rect[2] / float(max(1, aspect_rect[3]))
            view_proj, eye = self._camera(aspect)
            backdrop = ((0.055, 0.055, 0.065) if self.background[0] == 0
                        else (0.90, 0.905, 0.925))
            light = LIGHT._replace(
                span=max(self.tray.width, self.tray.depth) * 0.78)
            self.stage.render(aspect_rect, self._draws(), view_proj, eye,
                              light, (0.0, 0.0, 0.0), self._holes_uniform,
                              backdrop)
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
