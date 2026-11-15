# -*- coding: utf-8 -*-
"""Dr Shape on screen: a neon lab where a turtle draws in the air.

The turtle is a glowing arrowhead flying through a dark stage over a
receding grid; every stroke it lays down rings out as a note and sends a
ripple from the pen, and the two ear meters at the sides show where the
note sits between left and right. Then the look-alikes appear on cards,
turning slowly (tumbling higher up), each with its number; when the
chorus sings, the card that is singing is lit. Under overload the stage
fills with drifting sparks and flicker, the cards shake, and the colours
stop meaning anything.

Keys 1-6 or a click pick a card. For the agent boundary: ports 0-5 pick
cards 1-6, and every frame carries the stereo sound made since the last.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

import pyglet
from pyglet.window import key

from .. import drshape as model
from .. import runtime
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .tones import Voice as _Voice

HUES = ((255, 92, 120), (255, 160, 60), (250, 220, 70), (140, 230, 90),
        (60, 220, 170), (60, 200, 250), (90, 140, 255), (160, 110, 255),
        (230, 100, 240), (255, 120, 190), (200, 240, 255), (255, 200, 150))
NUMBER_KEYS = {getattr(key, '_%d' % (k + 1)): k for k in range(model.MOST)}
NUMBER_KEYS.update({getattr(key, 'NUM_%d' % (k + 1)): k
                    for k in range(model.MOST)})
LENS = 3.4               # camera distance, in shape radii
FOG = (40, 28, 78)       # what far things fade toward
LIGHT = (-0.42, 0.72, -0.55)   # toward the light, in a camera's frame
BADGE = pyglet.graphics.Group(order=6)
#: A place drawn on a card: its fills over the card, its lines over those.
PLACE_FILL = pyglet.graphics.Group(order=2.3)
PLACE_LINE = pyglet.graphics.Group(order=2.6)


class DrShape(ClockedTask):
    """Watch and hear the turtle's shape; find it among look-alikes."""

    instance: Optional['DrShape'] = None

    TITLE = 'Dr Shape'
    TASK_ID = 'dr_shape'
    PREFIX = 'DRSHAPE'
    CATEGORY = 'perception'
    FEEDBACK = 2.5
    MODEL = model
    SUBSTEP = 1 / 30.0
    EVENT_KEYS = NUMBER_KEYS
    FOOTNOTE = _('Watch and listen as the turtle draws   1-6 or click: '
                 'pick the card that matches   Esc: menu')

    def __init__(self) -> None:
        self.player = None
        self.heard_to = 0.0
        super().__init__()

    # --- the run and its sound ---------------------------------------------

    def _deal(self) -> bool:
        ok = super()._deal()
        self.heard_to = 0.0
        puzzle = self.run.puzzle
        self.message = {
            'see': _('Watch and listen: the turtle draws a shape'),
            'hear': _('Listen: the shape is only heard'),
            'sing': _('Watch: the turtle draws in silence'),
            'echo': _('Listen to the tune'),
            'scene': _('Watch and listen: where does each thing stand?'),
            'hear_scene': _('Listen: where does each thing stand?'),
        }[puzzle.mode]
        if puzzle.floor:
            self.message = _('Watch and listen: how big is it, how far?')
        self._start_sound()
        return ok

    def _start_sound(self) -> None:
        self._stop_sound()
        if runtime.HEADLESS or self.run is None:
            return
        p = self.run.puzzle
        try:
            player = pyglet.media.Player()
            player.queue(_Voice(p.notes, p.patches, p.show_end + p.choose))
            player.play()
            self.player = player
        except Exception as exc:          # no audio device: play silent
            runtime.debug_msg(exc)
            self.player = None

    def _stop_sound(self) -> None:
        if self.player is not None:
            try:
                self.player.pause()
                self.player.delete()
            except Exception:
                pass
        self.player = None

    def _judge(self, passed: bool, message: str) -> None:
        self._stop_sound()
        super()._judge(passed, message)

    def _clear_trial(self) -> None:
        self._stop_sound()
        super()._clear_trial()

    def audio_window(self):
        """The sound made since the last call, for the agent boundary."""
        run = self.run
        if run is None or run.t <= self.heard_to:
            return None
        t0, self.heard_to = self.heard_to, run.t
        return {'pcm': model.synth(run.puzzle.notes, t0, run.t,
                                   run.puzzle.patches),
                'rate': model.RATE, 'channels': 2}

    # --- layout -------------------------------------------------------------

    def _cells(self) -> List[Tuple[float, float, float, float]]:
        """Card rectangles for the candidates (and the shape, if kept)."""
        left, bottom, width, height = self._area()
        p = self.run.puzzle
        n = len(p.candidates)
        top = bottom + height * 0.93
        x0, w = left, width
        if self._panel():
            x0, w = left + width * 0.28, width * 0.72
        cols = n if n <= 4 else 3
        rows = 1 if n <= 4 else 2
        gap = min(w, height) * 0.03
        cw = (w - gap * (cols + 1)) / cols
        ch = (top - bottom - gap * (rows + 1)) / rows
        side = min(cw, ch * 1.25)
        cw, ch = side, min(ch, side)
        span_w = cols * cw + (cols - 1) * gap
        out = []
        for k in range(n):
            r, c = divmod(k, cols)
            cx = x0 + (w - span_w) / 2 + c * (cw + gap)
            span_h = rows * ch + (rows - 1) * gap
            cy = bottom + (top - bottom - span_h) / 2 + (rows - 1 - r) * \
                (ch + gap)
            out.append((cx, cy, cw, ch))
        return out

    def _panel(self) -> bool:
        """Whether the shape stays in view beside the cards."""
        p = self.run.puzzle
        return p.level.keep or p.mode == 'sing'

    # --- scenery ------------------------------------------------------------

    def _build_scenery(self) -> None:
        left, bottom, width, height = self._area()
        out, batch = self.scenery, self.batch
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        polish.card(out, batch, left - 4, bottom - 4, width + 8, height + 8,
                    (30, 20, 50), radius=16, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        polish.gradient(out, batch, left, bottom, width, height,
                        (14, 10, 34), (46, 18, 72), bands=28, group=g0)
        # A receding neon grid on the floor.
        hy = bottom + height * 0.42
        cx = left + width / 2
        for k in range(-14, 15):
            out.append(pyglet.shapes.Line(
                cx + k * width * 0.012, hy, cx + k * width * 0.11, bottom,
                thickness=1, color=(200, 80, 255, 70), batch=batch,
                group=g1))
        for k in range(1, 10):
            f = (k / 9.0) ** 2
            out.append(pyglet.shapes.Line(
                left, hy - (hy - bottom) * f, left + width,
                hy - (hy - bottom) * f, thickness=1,
                color=(80, 200, 255, int(30 + 60 * f)), batch=batch,
                group=g1))
        polish.glow(out, batch, cx, hy, width * 0.22, (255, 80, 200),
                    strength=50, group=g1)
        stars = random.Random(7)
        for _k in range(70):
            out.append(pyglet.shapes.Circle(
                left + stars.random() * width,
                hy + stars.random() * (bottom + height - hy),
                stars.choice((0.8, 1.2, 1.6)),
                color=(220, 220, 255, stars.randrange(60, 200)),
                batch=batch, group=g1))

    # --- drawing a shape -----------------------------------------------------

    # --- cameras ------------------------------------------------------------
    #
    # A camera maps a point of a form to (screen x, screen y, depth, near,
    # point in the camera's frame). The frame is x right, y up, z ahead;
    # depth sorts far to near; near (0..1) brightens and fattens strokes.

    def _orbit_cam(self, view, cx, cy, size):
        def cam(p):
            x, y, z = model.apply(view, p)
            f = LENS / (LENS - z)
            return (cx + x * size * f, cy + y * size * f, -z,
                    max(0.0, min(1.0, (z + 1) / 2)), (x, y, -z))
        return cam

    def _floor_cam(self, cx, hy, focal, view, size, side, depth, lift):
        def cam(p):
            x, y, z = model.apply(view, p)
            x, y, z = x * size + side, y * size + lift, z * size + depth
            z = max(0.3, z)
            return (cx + focal * x / z, hy + focal * (y - model.FLOOR_EYE) / z,
                    z, max(0.0, min(1.0, 1.0 - (z - 1.8) / 6.0)), (x, y, z))
        return cam

    def _scene_cam(self, cx, cy, focal, look, turn, x0, z0, lift):
        def cam(p):
            q = model.apply(turn, p)
            w = (q[0] * model.OBJECT + x0, q[1] * model.OBJECT + lift,
                 q[2] * model.OBJECT + z0)
            c = model.seen_from(look, w)
            z = max(0.5, c[2])
            return (cx + focal * c[0] / z, cy + focal * c[1] / z, z,
                    max(0.0, min(1.0, 1.0 - (z - model.ORBIT + 2.5) / 5.0)),
                    c)
        return cam

    # --- drawing a form -------------------------------------------------------

    def _form(self, form, cam, hues, scale, upto=None, wobble=0.0, seed=0,
              faded=False, glow=False, shadow=None, group=None):
        """Draw *form* through *cam*: shaded faces, lit tubes and
        jointed corners, far parts fogged, far to near. *shadow* maps a
        point to where its shadow falls on screen. Returns the pen's
        screen point when only *upto* strokes are drawn."""
        d, batch = self.drawn, self.batch
        group = group or self.text_group
        jig = random.Random(seed)
        n = len(form.segs)
        full = n if upto is None else min(n, upto)
        whole = int(math.floor(full))
        items = []
        pen = None

        def at(p):
            sx, sy, depth, near, c = cam(p)
            if wobble:
                sx += jig.uniform(-1, 1) * wobble * scale
                sy += jig.uniform(-1, 1) * wobble * scale
            return sx, sy, depth, near, c

        for k, ((a, b), tint) in enumerate(zip(form.segs, form.tints)):
            if k > whole or (k == whole and full - whole <= 0):
                break
            if k == whole:
                share = full - whole
                b = tuple(a[i] + (b[i] - a[i]) * share for i in range(3))
            pa, pb = at(a), at(b)
            items.append(((pa[2] + pb[2]) / 2, 1, (pa, pb, tint)))
            pen = (pb[0], pb[1])
            if shadow is not None:
                sa, sb = shadow(a), shadow(b)
                d.append(pyglet.shapes.Line(
                    sa[0], sa[1], sb[0], sb[1],
                    thickness=max(2.0, scale * 0.05),
                    color=(0, 0, 0, 80), batch=batch, group=PLACE_LINE))
        if full >= n:
            for poly, tint in form.faces:
                pts = [at(v) for v in poly]
                depth = sum(p[2] for p in pts) / len(pts) + 0.05
                items.append((depth, 0, (pts, tint)))
        items.sort(key=lambda it: (-it[0], it[1]))
        for _depth, kind, data in items:
            if kind == 0:
                self._face(data[0], self._hue(hues, data[1]), faded, group)
            else:
                self._tube(data[0], data[1], self._hue(hues, data[2]), scale,
                           faded, glow, group)
        return pen

    def _hue(self, hues, tint):
        return HUES[hues[tint % len(hues)] % len(HUES)]

    def _fogged(self, colour, near, faded):
        c = polish.mix(FOG, colour, 0.35 + 0.65 * near)
        if faded:
            c = polish.mix(c, (90, 90, 110), 0.6)
        return c

    def _face(self, pts, hue, faded, group):
        (ax, ay, _d, _n, a), (bx, by, _e, _m, b), (_x, _y, _f, _o, c) = \
            pts[0], pts[1], pts[2]
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        nx, ny, nz = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                      u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        lam = abs(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / length
        near = sum(p[3] for p in pts) / len(pts)
        colour = polish.mix(polish.darker(hue, 0.6), polish.lighter(hue, 0.2),
                            lam)
        colour = self._fogged(colour, near, faded)
        try:
            self.drawn.append(pyglet.shapes.Polygon(
                *[(p[0], p[1]) for p in pts], color=colour + (150,),
                batch=self.batch, group=group))
        except Exception:
            pass

    def _tube(self, pa, pb, hue, scale, faded, glow, group):
        d, batch = self.drawn, self.batch
        near = (pa[3] + pb[3]) / 2
        colour = self._fogged(polish.mix(polish.darker(hue, 0.45),
                                         polish.lighter(hue, 0.25), near),
                              near, faded)
        thick = max(2.0, scale * (0.03 + 0.05 * near))
        if glow:
            d.append(pyglet.shapes.Line(
                pa[0], pa[1], pb[0], pb[1], thickness=thick * 3.2,
                color=tuple(hue) + (60,), batch=batch, group=group))
        d.append(pyglet.shapes.Line(
            pa[0], pa[1], pb[0], pb[1], thickness=thick * 1.6,
            color=polish.darker(colour, 0.55) + (230,), batch=batch,
            group=group))
        d.append(pyglet.shapes.Line(pa[0], pa[1], pb[0], pb[1],
                                    thickness=thick, color=colour,
                                    batch=batch, group=group))
        fine = thick >= 3.5
        if fine:
            off = thick * 0.22
            d.append(pyglet.shapes.Line(
                pa[0] - off, pa[1] + off, pb[0] - off, pb[1] + off,
                thickness=max(1.0, thick * 0.3),
                color=polish.lighter(colour, 0.55) + (200,), batch=batch,
                group=group))
        for q in (pa, pb):
            d.append(pyglet.shapes.Circle(q[0], q[1], thick * 0.8,
                                          color=colour, batch=batch,
                                          group=group,
                                          segments=12 if fine else 6))
            if fine:
                d.append(pyglet.shapes.Circle(
                    q[0] - thick * 0.25, q[1] + thick * 0.25, thick * 0.25,
                    color=polish.lighter(colour, 0.6), batch=batch,
                    group=group, segments=6))

    # --- places: a turntable, a floor, a platform -------------------------------

    def _turntable(self, form, view, cx, cy, size, hues, upto=None,
                   wobble=0.0, seed=0, faded=False, group=None):
        cam = self._orbit_cam(view, cx, cy, size)
        floor = cy - size * 1.25

        def shadow(p):
            sx, sy, _d, _n, _c = cam(p)
            return sx, floor + (sy - cy) * 0.12
        return self._form(form, cam, hues, size, upto, wobble, seed, faded,
                          shadow=shadow, group=group)

    def _floor_box(self, x, y, w, h):
        """Horizon height and focal length for a floor view in a box."""
        return y + h * 0.62, min(w, h) * 0.9

    def _floor(self, x, y, w, h):
        """A floor running off to the horizon, ruled so distance shows."""
        d, batch = self.drawn, self.batch
        hy, focal = self._floor_box(x, y, w, h)
        cx = x + w / 2
        polish.gradient(d, batch, x + 2, hy, w - 4, y + h - hy - 2,
                        (60, 40, 100), (24, 16, 50), bands=6,
                        group=PLACE_FILL)
        d.append(pyglet.shapes.Rectangle(x + 2, y + 2, w - 4, hy - y - 2,
                                         color=(30, 24, 58), batch=batch,
                                         group=PLACE_FILL))
        eye = model.FLOOR_EYE
        for z in (1.5, 2.0, 2.7, 3.6, 5.0, 7.0, 10.0):
            sy = hy - focal * eye / z
            if sy < y + 2:
                continue
            fade = int(170 - 12 * z)
            d.append(pyglet.shapes.Line(x + 2, sy, x + w - 2, sy,
                                        thickness=1,
                                        color=(90, 200, 255, max(40, fade)),
                                        batch=batch, group=PLACE_LINE))
        for k in range(-6, 7):
            xs = k * 0.9
            z1, z2 = 1.2, 14.0
            a = (cx + focal * xs / z1, hy - focal * eye / z1)
            b = (cx + focal * xs / z2, hy - focal * eye / z2)
            if a[1] < y + 2:
                share = (y + 2 - b[1]) / (a[1] - b[1])
                a = (b[0] + (a[0] - b[0]) * share, y + 2)
            if not (x - 50 < b[0] < x + w + 50):
                continue
            a = (max(x + 2, min(x + w - 2, a[0])), a[1])
            d.append(pyglet.shapes.Line(a[0], a[1], b[0], b[1], thickness=1,
                                        color=(200, 90, 255, 90), batch=batch,
                                        group=PLACE_LINE))
        d.append(pyglet.shapes.Line(x + 2, hy, x + w - 2, hy, thickness=2,
                                    color=(255, 150, 220, 160), batch=batch,
                                    group=PLACE_LINE))

    def _on_floor(self, form, view, size, side, depth, x, y, w, h, hues,
                  upto=None, wobble=0.0, seed=0, faded=False):
        hy, focal = self._floor_box(x, y, w, h)
        cx = x + w / 2
        g, lift = model.rest(form, view, 1.0)
        lift *= size
        cam = self._floor_cam(cx, hy, focal, view, size, side, depth, lift)

        def shadow(p):
            q = model.apply(view, p)
            gx, gz = q[0] * size + side, q[2] * size + depth
            gz = max(0.3, gz) + 0.15
            return (cx + focal * (gx + 0.12) / gz,
                    hy - focal * model.FLOOR_EYE / gz)
        return self._form(form, cam, hues, focal / depth * size * 0.9, upto,
                          wobble, seed, faded, shadow=shadow)

    def _platform(self, look, cx, cy, focal, t, glow_beacon=True):
        """The round platform, its rings and the beacon by its edge."""
        d, batch = self.drawn, self.batch

        def scr(w):
            c = model.seen_from(look, w)
            z = max(0.5, c[2])
            return cx + focal * c[0] / z, cy + focal * c[1] / z
        angles = [2 * math.pi * k / 28 for k in range(28)]
        rim = [scr((model.PLATFORM * math.cos(a), 0.0,
                    model.PLATFORM * math.sin(a))) for a in angles]
        under = [scr((model.PLATFORM * math.cos(a), -0.35,
                      model.PLATFORM * math.sin(a))) for a in angles]
        try:
            d.append(pyglet.shapes.Polygon(*under, color=(40, 24, 70),
                                           batch=batch, group=PLACE_FILL))
            d.append(pyglet.shapes.Polygon(*rim, color=(70, 50, 120),
                                           batch=batch, group=PLACE_LINE))
        except Exception:
            pass
        for share, colour in ((1.0, (120, 220, 255, 200)),
                              (0.55, (200, 120, 255, 110))):
            ring = [scr((model.PLATFORM * share * math.cos(a), 0.0,
                         model.PLATFORM * share * math.sin(a)))
                    for a in angles + [0.0]]
            for p, q in zip(ring, ring[1:]):
                d.append(pyglet.shapes.Line(p[0], p[1], q[0], q[1],
                                            thickness=2 if share == 1 else 1,
                                            color=colour, batch=batch,
                                            group=PLACE_LINE))
        # The beacon: a striped mast with a lamp, always at the same spot.
        bx = model.PLATFORM - 0.1
        base, top = scr((bx, 0.0, 0.0)), scr((bx, 1.9, 0.0))
        depth = model.seen_from(look, (bx, 0.9, 0.0))[2]
        thick = max(3.0, focal * 0.12 / depth)
        for k in range(6):
            a = (base[0] + (top[0] - base[0]) * k / 6,
                 base[1] + (top[1] - base[1]) * k / 6)
            b = (base[0] + (top[0] - base[0]) * (k + 1) / 6,
                 base[1] + (top[1] - base[1]) * (k + 1) / 6)
            d.append(pyglet.shapes.Line(
                a[0], a[1], b[0], b[1], thickness=thick,
                color=(250, 250, 250) if k % 2 else (240, 70, 70),
                batch=batch, group=PLACE_LINE))
        if glow_beacon:
            polish.glow(d, batch, top[0], top[1], thick * 3,
                        (255, 240, 150), strength=120, group=PLACE_LINE)
        d.append(pyglet.shapes.Circle(top[0], top[1], thick * 0.9,
                                      color=(255, 245, 180), batch=batch,
                                      group=self.text_group))
        return depth

    def _scene(self, p, layout, look, x, y, w, h, t, show=None, faded=False,
               wobble=0.0, seed=0):
        """A platform with things standing on it, seen from *look*.
        *show*, when given, is the set of things to draw (the rest have
        not sung yet)."""
        cx, cy = x + w / 2, y + h * 0.42
        focal = min(w, h) * 1.25
        self._platform(look, cx, cy, focal, t)
        order = []
        for i, x0, z0 in layout:
            th = p.things[i]
            if show is not None and th.tint not in show:
                continue
            _g, lift = model.rest(th.form, th.turn, model.OBJECT)
            c = model.seen_from(look, (x0, lift, z0))
            order.append((c[2], th, x0, z0, lift))
        order.sort(key=lambda o: -o[0])
        singing = self.run.singing_thing() if show is not None else None
        for depth, th, x0, z0, lift in order:
            cam = self._scene_cam(cx, cy, focal, look, th.turn, x0, z0, lift)

            def shadow(q, th=th, x0=x0, z0=z0):
                r = model.apply(th.turn, q)
                g = model.seen_from(look, (r[0] * model.OBJECT + x0, 0.0,
                                           r[2] * model.OBJECT + z0))
                z = max(0.5, g[2])
                return cx + focal * g[0] / z, cy + focal * g[1] / z
            scale = focal * model.OBJECT / depth
            if singing is not None and th.tint == singing:
                sx, sy, _d, _n, _c = cam((0.0, 0.0, 0.0))
                polish.glow(self.drawn, self.batch, sx, sy, scale * 2.2,
                            self._hue(p.hues, th.tint), strength=110,
                            group=PLACE_LINE)
            self._form(th.form, cam, p.hues, scale, wobble=wobble,
                       seed=seed, faded=faded, shadow=shadow)

    # --- the frame -----------------------------------------------------------

    def _sway(self, view, t, k=0):
        return model.matmul(model.axis_turn((0, 1, 0),
                                            0.12 * math.sin(t * 0.9 + k)),
                            view)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self._scenery_fresh(self._area())
        p = run.puzzle
        level = p.level
        d, batch = self.drawn, self.batch
        t = run.t
        o = level.overload
        if o:
            self._storm(left, bottom, width, height, t, o)
        self._time_bar(left, bottom, width, height, run)
        self._ears(left, bottom, width, height, t,
                   p.mode not in ('see', 'scene'))
        if not run.choosing:
            self._show(p, run, left, bottom, width, height, t, o)
            return
        if not self.message.startswith(_('Which')):
            n = len(p.candidates)
            if p.scene:
                ask = _('Which is the same place, seen from elsewhere?  1-%d')
                if p.mode == 'hear_scene':
                    ask = _('Which place did you hear?  1-%d')
            elif p.floor:
                ask = _('Which is the same shape, the same size?  1-%d')
            else:
                ask = {'sing': _('Which sound is the shape?  1-%d'),
                       'echo': _('Which is the same tune?  1-%d'),
                       }.get(p.mode, _('Which is the same shape?  1-%d'))
            self.message = ask % n
        if self._panel():
            kx = left + width * 0.03
            kw = width * 0.22
            ky, kh = bottom + height * 0.2, height * 0.6
            polish.card(d, batch, kx, ky, kw, kh, (36, 28, 70), radius=12,
                        edge=(120, 90, 200), shade=(0, 0, 0, 80),
                        group=self.card_group)
            self._text(_('the shape'), kx + kw / 2, ky + kh - 18, 14,
                       bold=True, colour=(220, 210, 255, 230))
            self._turntable(p.form, self._sway(p.view, t), kx + kw / 2,
                            ky + kh * 0.48, min(kw, kh) * 0.34, p.hues)
        judged = run.result is not None
        singing = run.sounding()
        for k, (x, y, w, h) in enumerate(self._cells()):
            c = p.candidates[k]
            shake = random.Random(int(t * 15) * 31 + k)
            if o:
                x += shake.uniform(-1, 1) * o * w * 0.04
                y += shake.uniform(-1, 1) * o * h * 0.04
            edge = (110, 90, 180)
            if singing == k:
                edge = (255, 230, 120)
                polish.glow(d, batch, x + w / 2, y + h / 2, w * 0.62,
                            (255, 220, 120), strength=70,
                            group=self.back_group)
            if judged and k == p.answer:
                edge = (90, 230, 120)
            elif judged and k == run.choice:
                edge = (255, 80, 80)
            polish.card(d, batch, x, y, w, h, (32, 24, 62), radius=12,
                        edge=edge, shade=(0, 0, 0, 80), group=self.card_group)
            faded = judged and k != p.answer
            hues = p.hues
            if o and shake.random() < 0.15 * o:
                hues = tuple(shake.randrange(12) for _h in p.hues)
            wob = 0.012 * o
            if p.sound_cards and not judged:
                self._sound_card(k, x, y, w, h, t, singing == k)
            elif p.scene:
                self._scene(p, c.layout, c.look, x, y, w, h, t,
                            faded=faded, wobble=wob, seed=int(t * 20) + k)
            elif p.floor:
                self._floor(x, y, w, h)
                view = c.view
                if level.tumble:
                    view = model.matmul(model.axis_turn(c.spin, t * 0.6),
                                        c.view)
                self._on_floor(c.form, view, c.size, c.side, c.depth,
                               x, y, w, h, hues, wobble=wob,
                               seed=int(t * 20) + k, faded=faded)
            else:
                view = c.view
                if level.tumble and any(c.spin):
                    view = model.matmul(model.axis_turn(c.spin, t * 0.7),
                                        c.view)
                elif not p.sound_cards:
                    view = self._sway(c.view, t, k)
                self._turntable(c.form, view, x + w / 2, y + h * 0.52,
                                min(w, h) * 0.4, hues, wobble=wob,
                                seed=int(t * 20) + k, faded=faded)
            badge = min(w, h) * 0.09
            polish.disc(d, batch, x + badge * 1.4, y + h - badge * 1.4,
                        badge, (250, 220, 90), group=self.top_group)
            self._text(str(k + 1), x + badge * 1.4, y + h - badge * 1.4,
                       badge * 0.95, bold=True, colour=(40, 20, 60, 255),
                       group=BADGE)
            if run.result is None:
                self.hits.append((x, y, w, h,
                                  lambda k=k: self.steer(k)))

    def _show(self, p, run, left, bottom, width, height, t, o) -> None:
        """The trial before the cards: the turtle drawing, a place, or
        only a sound."""
        cx, cy = left + width / 2, bottom + height * 0.5
        size = min(width, height) * 0.3
        if p.heard:
            self._speaker(cx, cy, size, t)
            return
        if p.scene:
            w, h = min(width * 0.7, height * 1.6), height * 0.9
            sung = {i for i, a, _b in p.parts if a <= t}
            self._scene(p, p.layout, p.look, cx - w / 2, bottom, w, h, t,
                        show=sung, wobble=0.01 * o, seed=int(t * 20))
            return
        hue = self._hue(p.hues, p.form.tints[min(len(p.form.tints) - 1,
                                                 int(run.strokes()))])
        if p.floor:
            w, h = min(width * 0.75, height * 1.7), height * 0.92
            x, y = cx - w / 2, bottom + height * 0.02
            polish.card(self.drawn, self.batch, x, y, w, h, (32, 24, 62),
                        radius=14, edge=(120, 90, 200), shade=None,
                        group=self.card_group)
            self._floor(x, y, w, h)
            pen = self._on_floor(p.form, self._sway(p.view, t), 1.0, 0.0,
                                 model.SHOW_DEPTH, x, y, w, h, p.hues,
                                 upto=run.strokes(), wobble=0.01 * o,
                                 seed=int(t * 20))
            scale = min(w, h) * 0.9 / model.SHOW_DEPTH
        else:
            pen = self._turntable(p.form, self._sway(p.view, t), cx, cy,
                                  size, p.hues, upto=run.strokes(),
                                  wobble=0.01 * o, seed=int(t * 20))
            scale = size
        if pen is not None and run.strokes() < len(p.shape):
            self._turtle(pen, scale, t, hue, p.mode != 'sing')

    def _turtle(self, pen, size, t, hue, sounding=True) -> None:
        d, batch = self.drawn, self.batch
        x, y = pen
        pulse = 0.5 + 0.5 * math.sin(t * 12)
        polish.glow(d, batch, x, y, size * 0.16, hue, strength=120,
                    group=self.body_group)
        r = size * 0.06 * (1 + 0.15 * pulse)
        d.append(pyglet.shapes.Star(x, y, r * 1.6, r * 0.7, 5,
                                    rotation=t * 90,
                                    color=(255, 255, 230), batch=batch,
                                    group=self.top_group))
        # Ripples from the note now sounding.
        for k in range(3 if sounding else 0):
            share = ((t * 1.6) + k / 3.0) % 1.0
            d.append(pyglet.shapes.Arc(
                x, y, size * (0.08 + 0.3 * share), thickness=2,
                color=tuple(hue) + (int(200 * (1 - share)),), batch=batch,
                group=self.body_group))

    def _speaker(self, cx, cy, size, t) -> None:
        """What the screen shows while the shape is only heard: how loud,
        never where or how high."""
        d, batch = self.drawn, self.batch
        loud = sum(n.gain for n in self.run.puzzle.notes
                   if n.t <= t <= n.t + n.dur and (n.who == -1 or n.who <= -10))
        polish.glow(d, batch, cx, cy, size * (0.5 + 0.3 * min(1, loud)),
                    (120, 200, 255), strength=90, group=self.body_group)
        polish.disc(d, batch, cx, cy, size * 0.25, (60, 70, 140),
                    group=self.text_group)
        polish.disc(d, batch, cx, cy, size * 0.12 * (1 + 0.4 * min(1, loud)),
                    (200, 220, 255), group=self.top_group)
        for k in range(4):
            share = ((t * 0.9) + k / 4.0) % 1.0
            d.append(pyglet.shapes.Arc(
                cx, cy, size * (0.3 + 0.6 * share), thickness=3,
                color=(140, 210, 255, int(220 * (1 - share) * min(1, loud
                                                                  + 0.2))),
                batch=batch, group=self.body_group))
        self._text(_('listen'), cx, cy - size * 0.95, 14, bold=True,
                   colour=(190, 220, 255, 230))

    def _sound_card(self, k, x, y, w, h, t, playing) -> None:
        """A card that is a sound: a speaker that pulses while it plays.
        It shows how loud, never where or how high."""
        d, batch = self.drawn, self.batch
        cx, cy = x + w / 2, y + h * 0.5
        r = min(w, h) * 0.16
        loud = 0.0
        if playing:
            loud = min(1.0, sum(n.gain for n in self.run.puzzle.notes
                                if n.who == k and n.t <= t <= n.t + n.dur))
        hue = (255, 210, 110) if playing else (120, 110, 170)
        if playing:
            polish.glow(d, batch, cx, cy, r * (2.2 + loud), hue,
                        strength=80, group=self.body_group)
            for j in range(3):
                share = ((t * 1.4) + j / 3.0) % 1.0
                d.append(pyglet.shapes.Arc(
                    cx, cy, r * (1.1 + 1.3 * share), thickness=3,
                    color=hue + (int(230 * (1 - share)),), batch=batch,
                    group=self.text_group))
        # The speaker: a box and a cone.
        d.append(pyglet.shapes.Rectangle(cx - r * 0.9, cy - r * 0.35,
                                         r * 0.5, r * 0.7, color=hue,
                                         batch=batch, group=self.text_group))
        d.append(pyglet.shapes.Polygon(
            (cx - r * 0.4, cy - r * 0.35), (cx + r * 0.3, cy - r * 0.9),
            (cx + r * 0.3, cy + r * 0.9), (cx - r * 0.4, cy + r * 0.35),
            color=hue, batch=batch, group=self.text_group))

    def _ears(self, left, bottom, width, height, t, heard) -> None:
        """Left and right level meters: where the sound sits."""
        if heard:
            return
        d, batch = self.drawn, self.batch
        lv = rv = 0.0
        for n in self.run.puzzle.notes:
            if n.t <= t <= n.t + n.dur:
                a = (n.pan + 1) * math.pi / 4
                lv += n.gain * math.cos(a)
                rv += n.gain * math.sin(a)
        bw, bh = width * 0.018, height * 0.62
        by = bottom + height * 0.15
        for x, level, word in ((left + width * 0.012, lv, _('L')),
                               (left + width * 0.97, rv, _('R'))):
            polish.rounded(d, batch, x, by, bw, bh, (40, 30, 70),
                           radius=bw / 2, group=self.card_group)
            fill = min(1.0, level)
            if fill > 0.02:
                polish.rounded(d, batch, x, by, bw, bh * fill,
                               polish.mix((80, 220, 255), (255, 90, 200),
                                          fill),
                               radius=bw / 2, group=self.body_group)
            self._text(word, x + bw / 2, by - 12, 10, bold=True,
                       colour=(200, 190, 255, 220))

    def _time_bar(self, left, bottom, width, height, run) -> None:
        d, batch = self.drawn, self.batch
        p = run.puzzle
        y = bottom + height * 0.955
        h = height * 0.025
        polish.rounded(d, batch, left + width * 0.05, y, width * 0.9, h,
                       (50, 40, 80), radius=h / 2, group=self.card_group)
        if run.choosing:
            share = max(0.0, 1.0 - (run.t - p.show_end) / p.choose)
            colour = polish.mix((255, 80, 90), (90, 230, 160),
                                min(1.0, share * 1.6))
        else:
            share = min(1.0, run.t / p.show_end)
            colour = (160, 120, 255)
        if share > 0.01:
            polish.rounded(d, batch, left + width * 0.05, y,
                           width * 0.9 * share, h, colour, radius=h / 2,
                           group=self.body_group)

    def _storm(self, left, bottom, width, height, t, o) -> None:
        """Sensory overload: sparks, streaks and flicker."""
        d, batch = self.drawn, self.batch
        g = self.back_group
        n = int(30 + 150 * o)
        for k in range(n):
            rnd = random.Random(k * 7919)
            sx = (rnd.random() + t * rnd.uniform(-0.2, 0.2)) % 1.0
            sy = (rnd.random() + t * rnd.uniform(0.05, 0.3)) % 1.0
            c = HUES[(k + int(t * 3)) % len(HUES)]
            d.append(pyglet.shapes.Circle(
                left + sx * width, bottom + sy * height,
                rnd.uniform(1.0, 3.5), color=tuple(c) + (
                    int(80 + 120 * o * (0.5 + 0.5 * math.sin(t * 9 + k))),),
                batch=batch, group=g))
        flick = random.Random(int(t * 12))
        if flick.random() < 0.35 * o:
            c = HUES[flick.randrange(len(HUES))]
            x = left + flick.random() * width * 0.8
            y = bottom + flick.random() * height * 0.8
            d.append(pyglet.shapes.Rectangle(
                x, y, width * flick.uniform(0.1, 0.3),
                height * flick.uniform(0.05, 0.2),
                color=tuple(c) + (int(40 + 60 * o),), batch=batch, group=g))
        for k in range(int(6 * o)):
            rnd = random.Random(int(t * 4) * 13 + k)
            y = bottom + rnd.random() * height
            d.append(pyglet.shapes.Line(
                left, y, left + width, y + rnd.uniform(-20, 20),
                thickness=1, color=HUES[rnd.randrange(len(HUES))] + (90,),
                batch=batch, group=g))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        p = self.run.puzzle
        what = _('choosing') if self.run.choosing else (
            _('listening') if p.heard else _('watching'))
        if p.scene:
            return _('rung %d  %d/%d   %d places   %s') % (
                self.rung, self.trial, self.total_trials, len(p.candidates),
                what)
        return _('rung %d  %d/%d   %d candidates   %s') % (
            self.rung, self.trial, self.total_trials, len(p.candidates),
            what)
