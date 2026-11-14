# -*- coding: utf-8 -*-
"""Camera: go and stand where the photograph was taken.

The player is put in a field of objects, and a photograph taken
somewhere in that field is pinned in the corner of the screen. Walk with
the keyboard, look with the mouse, and press Enter when the view in
front of you is the photograph. It passes if the eye is close enough to
where the photographer stood and the line of sight close enough to
theirs; how close is what the ladder tightens, and it tightens without
end. :mod:`neural_workshop.camera` holds the field, the poses and the
ladder; this module draws them and takes the keys.

Both views are drawn by the same 3D stage the Marble Maze uses, from
the same meshes, through the same lens, so the photograph is a frame of
this world and not a picture of something like it. Each view has a
stage of its own, because a stage reallocates its offscreen buffers
whenever it is asked for a different size, and the photograph and the
live view are different sizes every frame.

For the agent boundary the motion comes in steps rather than held keys:
ten moves at three sizes — a whole step, an eighth of one, and a step
fine enough to land inside the rung's tolerance — and a port that says
"this is it". The finest step scales with the rung on purpose. A ladder
whose top rungs could not be reached by any sequence of ports would be
measuring the port table, not the player.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Sequence, Tuple

import pyglet
from pyglet.math import Mat4, Vec3
from pyglet.window import key

from .. import camera as world
from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, framebuffer_size, from_bottom_edge,
                        from_top_edge, pixel_size, width_center)
from ..i18n import _
from . import cursor, render3d, taskoptions
from .verdict import VerdictLabel, above_the_band

#: A material id no branch of the stage's shader claims, so a surface
#: is plain lit colour: no grain, no metal, no hole.
PLAIN = 9

LIGHT = render3d.Light(
    direction=(-0.42, 0.80, 0.30),
    colour=(1.0, 0.97, 0.92),
    sky=(0.70, 0.78, 0.90),
    ground=(0.40, 0.42, 0.34),
    span=20.0)

SKY = (0.66, 0.77, 0.89)
FIELD = (0.62, 0.68, 0.50)
OUTSIDE = (0.36, 0.40, 0.32)

#: The three sizes an agent's step comes in. The last is a stand-in:
#: the real finest step is worked out from the rung, see :meth:`press`.
SCALES = (1.0, 0.125, None)

#: Walking speed for a person, metres a second, and how much Shift
#: slows everything down.
WALK = 3.2
TURN = 80.0
SLOW = 0.12
#: Degrees of turn per pixel of mouse drag.
DRAG = 0.22

#: Seconds the verdict stays up before the next photograph.
FEEDBACK = 1.8


# --- meshes ------------------------------------------------------------------

def _tri(builder: render3d.Builder, points, normals) -> None:
    """One triangle, wound so its face agrees with its normals.

    The stage's shader flips a normal on a back face, so a triangle
    wound the wrong way round is lit as if it faced inwards. Rather
    than get every winding right by hand, each triangle is checked
    against the normals it was given and turned over if need be.
    """
    a, b, c = points
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    face = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0])
    mean = [sum(n[i] for n in normals) for i in range(3)]
    if sum(f * m for f, m in zip(face, mean)) < 0:
        points = (a, c, b)
        normals = (normals[0], normals[2], normals[1])
    base = len(builder.positions) // 3
    for point, normal in zip(points, normals):
        builder.positions.extend(point)
        builder.normals.extend(normal)
    builder.indices.extend((base, base + 1, base + 2))


def _lathe(builder: render3d.Builder,
           profile: Sequence[Tuple[float, float]], sides: int,
           twist: float = 0.0) -> None:
    """Revolve a (radius, height) profile about the vertical axis."""
    for (r0, y0), (r1, y1) in zip(profile, profile[1:]):
        dr, dy = r1 - r0, y1 - y0
        length = math.hypot(dr, dy) or 1.0
        nr, ny = dy / length, -dr / length
        for side in range(sides):
            a0 = twist + 2.0 * math.pi * side / sides
            a1 = twist + 2.0 * math.pi * (side + 1) / sides
            # Few sides means facets, and a facet wants one normal.
            mid = (a0 + a1) / 2.0 if sides < 8 else None

            def normal(a):
                at = mid if mid is not None else a
                return (nr * math.cos(at), ny, nr * math.sin(at))

            p00 = (r0 * math.cos(a0), y0, r0 * math.sin(a0))
            p01 = (r0 * math.cos(a1), y0, r0 * math.sin(a1))
            p10 = (r1 * math.cos(a0), y1, r1 * math.sin(a0))
            p11 = (r1 * math.cos(a1), y1, r1 * math.sin(a1))
            n0, n1 = normal(a0), normal(a1)
            if r0 > 1e-9:
                _tri(builder, (p00, p10, p01), (n0, n0, n1))
            if r1 > 1e-9:
                _tri(builder, (p01, p10, p11), (n1, n0, n1))


def _ring(builder: render3d.Builder, around: int = 28, tube: int = 12
          ) -> None:
    """A hoop standing on edge in the x-y plane, resting on the ground."""
    big, small = 0.38, 0.11
    centre_y = big + small

    def point(u, v):
        cu, su, cv, sv = math.cos(u), math.sin(u), math.cos(v), math.sin(v)
        normal = (cu * cv, su * cv, sv)
        return ((big + small * cv) * cu, centre_y + (big + small * cv) * su,
                small * sv), normal

    for i in range(around):
        u0, u1 = 2 * math.pi * i / around, 2 * math.pi * (i + 1) / around
        for j in range(tube):
            v0, v1 = 2 * math.pi * j / tube, 2 * math.pi * (j + 1) / tube
            (a, na), (b, nb) = point(u0, v0), point(u1, v0)
            (c, nc), (d, nd) = point(u1, v1), point(u0, v1)
            _tri(builder, (a, b, c), (na, nb, nc))
            _tri(builder, (a, c, d), (na, nc, nd))


def shape_builder(shape: str) -> render3d.Builder:
    """A unit-height mesh of *shape*, standing on the origin."""
    builder = render3d.Builder()
    if shape == 'box':
        builder.box(-0.42, 0.0, -0.42, 0.42, 1.0, 0.42)
    elif shape == 'ball':
        steps = 16
        profile = [(0.5 * math.sin(math.pi * i / steps),
                    0.5 - 0.5 * math.cos(math.pi * i / steps))
                   for i in range(steps + 1)]
        _lathe(builder, profile, 28)
    elif shape == 'cylinder':
        _lathe(builder, [(0.0, 0.0), (0.4, 0.0), (0.4, 1.0), (0.0, 1.0)], 28)
    elif shape == 'cone':
        _lathe(builder, [(0.0, 0.0), (0.48, 0.0), (0.0, 1.0)], 28)
    elif shape == 'pyramid':
        _lathe(builder, [(0.0, 0.0), (0.58, 0.0), (0.0, 1.0)], 4,
               twist=math.pi / 4)
    elif shape == 'ring':
        _ring(builder)
    else:
        raise ValueError(shape)
    return builder


class _View:
    """One stage and the meshes built for it."""

    def __init__(self) -> None:
        self.stage = render3d.Stage()
        self.meshes: Dict[str, render3d.Mesh] = {}

    @property
    def ok(self) -> bool:
        return self.stage.ok

    def build(self, field: float) -> None:
        self.drop()
        if not self.stage.ok:
            return
        program, depth = self.stage.program, self.stage.depth_program
        for shape in world.SHAPES:
            self.meshes[shape] = shape_builder(shape).build(program, depth)
        ground = render3d.Builder()
        ground.quad_xz(-field, -field, field, field, 0.0)
        self.meshes['field'] = ground.build(program, depth)
        far = field * 6.0 + 60.0
        outside = render3d.Builder()
        outside.quad_xz(-far, -far, far, far, -0.01)
        self.meshes['outside'] = outside.build(program, depth)

    def drop(self) -> None:
        for mesh in self.meshes.values():
            mesh.delete()
        self.meshes = {}

    def close(self) -> None:
        self.drop()
        self.stage.close()


def view_proj(pose: world.Pose, aspect: float, field: float) -> Mat4:
    eye = Vec3(pose.x, pose.y, pose.z)
    fwd = pose.forward()
    view = Mat4.look_at(eye, Vec3(pose.x + fwd[0], pose.y + fwd[1],
                                  pose.z + fwd[2]), Vec3(0.0, 1.0, 0.0))
    proj = Mat4.perspective_projection(aspect, 0.05, field * 8.0 + 80.0,
                                       fov=world.FOV)
    return proj @ view


class CameraTask:
    """Walk a field until the view matches a photograph taken in it."""

    instance: Optional['CameraTask'] = None

    def __init__(self) -> None:
        if CameraTask.instance is not None:
            CameraTask.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.scene: Optional[world.Scene] = None
        self.pose: Optional[world.Pose] = None
        self.rung = 1
        self.trial = 0
        self.steps = 0
        self.started_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, float, float, float]] = []
        self.phase = 'ready'
        self.held: set = set()
        self.slow = False
        self.peek = False
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.live = _View()
        self.photo = _View()
        self.drawn: List[object] = []
        self._read_options()
        self.message = _('Press Space to start')
        if not self.live.ok:
            self.message = _('Camera needs OpenGL 3.3, which this machine '
                             'did not provide')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_key_release,
                                   self.on_mouse_drag, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        CameraTask.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.CAMERA)
        self.start_rung = int(opts['CAMERA_RUNG'])
        self.total_trials = int(opts['CAMERA_TRIALS'])
        self.adaptive = bool(opts['CAMERA_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('camera', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            _('Camera'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        view_left, _vb, view_w, _vh = self._view_rect()
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=view_left, y=from_top_edge(70),
            anchor_x='left', anchor_y='center', font_name=FONTLIST)
        self.info = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=view_left + view_w, y=from_top_edge(70),
            anchor_x='right', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('WASD walk  drag/arrows look  Q/E up, down  Shift slow  '
              'T photo  Enter match  Esc menu'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _view_rect(self) -> Tuple[float, float, float, float]:
        """The live view, in layout pixels: the largest frame of the
        photograph's aspect that fits between the labels and the band."""
        window_w, window_h = pixel_size()
        bottom = above_the_band(from_bottom_edge(58))
        top = from_top_edge(92)
        room_w, room_h = window_w * 0.94, max(48.0, top - bottom)
        width = min(room_w, room_h * world.ASPECT)
        height = width / world.ASPECT
        left = (window_w - width) / 2.0
        return (left, bottom + (room_h - height) / 2.0, width, height)

    def _photo_rect(self) -> Tuple[float, float, float, float]:
        left, bottom, width, height = self._view_rect()
        small_w = width * 0.30
        small_h = small_w / world.ASPECT
        pad = max(6.0, width * 0.012)
        return (left + width - small_w - pad, bottom + height - small_h - pad,
                small_w, small_h)

    @staticmethod
    def _to_framebuffer(rect: Tuple[float, float, float, float]
                        ) -> Tuple[int, int, int, int]:
        window_w, window_h = pixel_size()
        fb_w, fb_h = framebuffer_size(state.window)
        sx = fb_w / float(window_w) if window_w else 1.0
        sy = fb_h / float(window_h) if window_h else 1.0
        left, bottom, width, height = rect
        return (int(left * sx), int(bottom * sy), int(width * sx),
                int(height * sy))

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.scene = None
        self.pose = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self.rung = max(1, self.start_rung)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        if not self.live.ok:
            self.phase = 'ready'
            self._redraw()
            return
        self.trial += 1
        try:
            self.scene = world.deal(self.rung, rng=self.rng)
        except world.Unbuildable:
            self.scene = world.deal(max(1, self.rung - 1), rng=self.rng)
        self.pose = self.scene.start
        field = self.scene.level.field
        self.live.build(field)
        self.photo.build(field)
        self.steps = 0
        self.held = set()
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'searching'
        self.message = _('Stand where the photo was taken')
        self._redraw()

    def press(self, move: int, scale: int = 0) -> None:
        """One step of one move, for the agent boundary.

        *move* indexes :data:`neural_workshop.camera.MOVES`; one past the
        end is "this is it". *scale* picks a whole step, an eighth, or
        the finest step, which is half the rung's tolerance — so the top
        of the ladder is out of reach because of judgement, never
        because the ports cannot get there.
        """
        if self.phase != 'searching' or self.scene is None:
            return
        if move >= len(world.MOVES):
            self.submit()
            return
        name = world.MOVES[move]
        amount = SCALES[scale] if scale < 2 else self._finest(name)
        self.pose = world.moved(self.pose, name, amount, self.scene.level)
        self.steps += 1
        self._redraw()

    def _finest(self, move: str) -> float:
        level = self.scene.level
        if move in ('turn_left', 'turn_right', 'look_up', 'look_down'):
            return min(1 / 64., 0.5 * level.aim / world.STEP_DEGREES)
        if move in ('rise', 'sink'):
            return min(1 / 64., 0.5 * level.reach / world.STEP_RISE)
        return min(1 / 64., 0.5 * level.reach / world.STEP_METRES)

    def submit(self) -> None:
        if self.phase != 'searching' or self.scene is None:
            return
        level, target = self.scene.level, self.scene.target
        off = world.distance(self.pose, target)
        turned = world.angle(self.pose, target)
        passed = world.matches(self.pose, target, level)
        took = self.clock() - self.started_at
        self.results.append((level.rung, passed, off, turned, took))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.held = set()
        self.peek = False
        self.feedback_until = self.clock() + FEEDBACK
        if passed:
            self.message = (_('Matched: %s and %s off') %
                            (_metres(off), _degrees(turned)))
        else:
            self.message = (_('Missed: %s and %s off') %
                            (_metres(off), _degrees(turned)))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.scene = None
        self.live.drop()
        self.photo.drop()
        tally = self.score()
        self.message = (_('%d of %d matched   highest rung matched %d')
                        % (tally['matched'], tally['trials'],
                           tally['best_rung']))
        self._redraw()

    def score(self) -> Dict[str, float]:
        trials = len(self.results)
        return {
            'trials': trials,
            'matched': sum(1 for r in self.results if r[1]),
            'best_rung': max((r[0] for r in self.results if r[1]),
                             default=0),
            'mean_seconds': (sum(r[4] for r in self.results) / trials
                             if trials else 0.0),
        }

    # --- time ------------------------------------------------------------

    _KEYS = {key.W: 'forward', key.S: 'back', key.A: 'left', key.D: 'right',
             key.LEFT: 'turn_left', key.RIGHT: 'turn_right',
             key.UP: 'look_up', key.DOWN: 'look_down',
             key.Q: 'rise', key.E: 'sink'}

    def update(self, dt: float) -> None:
        if self.phase == 'judged' and self.clock() >= self.feedback_until:
            self._next_trial()
            return
        if self.phase != 'searching' or not self.held or self.scene is None:
            return
        dt = min(dt, 0.1)
        slow = SLOW if self.slow else 1.0
        for move in self.held:
            if move in ('turn_left', 'turn_right', 'look_up', 'look_down'):
                amount = TURN * dt * slow / world.STEP_DEGREES
            elif move in ('rise', 'sink'):
                amount = WALK * 0.5 * dt * slow / world.STEP_RISE
            else:
                amount = WALK * dt * slow / world.STEP_METRES
            self.pose = world.moved(self.pose, move, amount,
                                    self.scene.level)
        self._redraw()

    # --- drawing ---------------------------------------------------------

    def _draws(self, view: _View) -> List[render3d.Draw]:
        draws = []
        model, nscale = render3d.placed((0.0, 0.0, 0.0))
        draws.append(render3d.Draw(view.meshes['outside'], model, nscale,
                                   PLAIN, OUTSIDE, casts=False))
        draws.append(render3d.Draw(view.meshes['field'], model, nscale,
                                   PLAIN, FIELD, casts=False))
        for thing in self.scene.things:
            spin = Mat4.from_rotation(math.radians(thing.spin),
                                      Vec3(0.0, 1.0, 0.0))
            if thing.occluder:
                scale = (thing.size * 1.6, thing.size, thing.size * 0.9)
            else:
                scale = (thing.size, thing.size, thing.size)
            model, nscale = render3d.placed((thing.x, 0.0, thing.z),
                                            scale=scale, spin=spin)
            draws.append(render3d.Draw(view.meshes[thing.shape], model,
                                       nscale, PLAIN, thing.colour))
        return draws

    def _render(self, view: _View, pose: world.Pose,
                rect: Tuple[float, float, float, float]) -> None:
        field = self.scene.level.field
        fb_rect = self._to_framebuffer(rect)
        aspect = fb_rect[2] / float(max(1, fb_rect[3]))
        light = LIGHT._replace(span=field * 1.25 + 4.0)
        view.stage.render(fb_rect, self._draws(view),
                          view_proj(pose, aspect, field),
                          (pose.x, pose.y, pose.z), light,
                          (0.0, 0.0, 0.0), (), SKY)

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _redraw(self) -> None:
        """The 2D furniture: the photograph's frame, the meter, labels."""
        self._clear_drawn()
        if self.phase in ('searching', 'judged') and self.scene is not None:
            left, bottom, width, height = self._photo_rect()
            if not self.peek:
                self.drawn.append(pyglet.shapes.Box(
                    left - 3, bottom - 3, width + 6, height + 6,
                    thickness=3, color=(250, 250, 250, 255),
                    batch=self.batch))
            if self.scene.level.meter and self.phase == 'searching':
                warmth = world.closeness(self.pose, self.scene.target,
                                         self.scene.level)
                vleft, vbottom, vwidth, _vh = self._view_rect()
                bar_h = 10
                self.drawn.append(pyglet.shapes.Rectangle(
                    vleft, vbottom + 8, vwidth * 0.4, bar_h,
                    color=(40, 40, 48, 200), batch=self.batch))
                self.drawn.append(pyglet.shapes.Rectangle(
                    vleft, vbottom + 8, vwidth * 0.4 * warmth, bar_h,
                    color=(90, 140, 230, 255), batch=self.batch))
        self._update_labels()

    def _update_labels(self) -> None:
        self.status.text = self.message
        if self.phase in ('searching', 'judged') and self.scene is not None:
            level = self.scene.level
            self.info.text = (_('rung %d  photo %d/%d  within %s, %s')
                              % (level.rung, self.trial, self.total_trials,
                                 _metres(level.reach), _degrees(level.aim)))
        else:
            self.info.text = ''

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if CameraTask.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_key_release,
                                     self.on_mouse_drag, self.on_draw)
        self._clear_drawn()
        self.live.close()
        self.photo.close()
        CameraTask.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='perception')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        self.slow = bool(modifiers & key.MOD_SHIFT)
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol in (key.SPACE,) and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol in (key.RETURN, key.ENTER, key.SPACE) \
                and self.phase == 'searching':
            self.submit()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.T:
            self.peek = True
            self._redraw()
        elif symbol in (key.LSHIFT, key.RSHIFT):
            self.slow = True
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in self._KEYS and self.phase == 'searching':
            self.held.add(self._KEYS[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol: int, modifiers: int) -> bool:
        if symbol in (key.LSHIFT, key.RSHIFT):
            self.slow = False
        elif symbol == key.T:
            self.peek = False
            self._redraw()
        self.held.discard(self._KEYS.get(symbol))
        return pyglet.event.EVENT_HANDLED

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int,
                      buttons: int, modifiers: int) -> bool:
        if self.phase != 'searching' or self.scene is None:
            return pyglet.event.EVENT_HANDLED
        slow = SLOW if modifiers & key.MOD_SHIFT else 1.0
        level = self.scene.level
        turn = -dx * DRAG * slow / world.STEP_DEGREES
        look = dy * DRAG * slow / world.STEP_DEGREES
        self.pose = world.moved(self.pose, 'turn_left', turn, level)
        self.pose = world.moved(self.pose, 'look_up', look, level)
        self._redraw()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        if self.phase in ('searching', 'judged') and self.scene is not None:
            view = self._view_rect()
            if self.peek:
                self._render(self.photo, self.scene.target, view)
            else:
                self._render(self.live, self.pose, view)
                self._render(self.photo, self.scene.target,
                             self._photo_rect())
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def _metres(value: float) -> str:
    if value >= 1.0:
        return '%.2f m' % value
    if value >= 0.01:
        return '%.1f cm' % (value * 100)
    if value >= 1e-5:
        return '%.2f mm' % (value * 1000)
    return '%.2g mm' % (value * 1000)


def _degrees(value: float) -> str:
    if value >= 1.0:
        return '%.1f°' % value
    if value >= 0.01:
        return '%.2f°' % value
    return '%.2g°' % value
