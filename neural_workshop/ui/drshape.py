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

HUES = ((255, 92, 120), (255, 160, 60), (250, 220, 70), (140, 230, 90),
        (60, 220, 170), (60, 200, 250), (90, 140, 255), (160, 110, 255),
        (230, 100, 240), (255, 120, 190), (200, 240, 255), (255, 200, 150))
NUMBER_KEYS = {getattr(key, '_%d' % (k + 1)): k for k in range(model.MOST)}
NUMBER_KEYS.update({getattr(key, 'NUM_%d' % (k + 1)): k
                    for k in range(model.MOST)})
LENS = 3.4               # camera distance, in shape radii
BADGE = pyglet.graphics.Group(order=6)


class _Voice(pyglet.media.Source):
    """The trial's sound, synthesised as it is played."""

    def __init__(self, notes: Sequence[model.Note],
                 patches: Sequence[model.Patch], duration: float) -> None:
        from pyglet.media.codecs.base import AudioFormat
        self.audio_format = AudioFormat(channels=2, sample_size=16,
                                        sample_rate=model.RATE)
        self.video_format = None
        self._notes = list(notes)
        self._patches = list(patches)
        self._duration = duration
        self._t = 0.0

    def get_audio_data(self, num_bytes: int, compensation_time: float = 0.0):
        from pyglet.media.codecs.base import AudioData
        if self._t >= self._duration:
            return None
        t1 = min(self._duration, self._t + max(1, num_bytes // 4)
                 / float(model.RATE))
        data = model.synth(self._notes, self._t, t1, self._patches)
        t0, self._t = self._t, t1
        return AudioData(data, len(data), t0, t1 - t0, [])

    def seek(self, timestamp: float) -> None:
        self._t = max(0.0, min(self._duration, timestamp))

    def is_precise(self) -> bool:
        return True


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
        }[puzzle.mode]
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

    def _shape(self, segs, view, cx, cy, size, hue, upto=None,
               wobble=0.0, seed=0, faded=False, group=None) -> Optional[
                   Tuple[float, float]]:
        """Draw *segs* turned by *view*; return the pen's screen point when
        only *upto* strokes are drawn."""
        d, batch = self.drawn, self.batch
        group = group or self.text_group
        jig = random.Random(seed)
        proj = []
        full = len(segs) if upto is None else min(len(segs), upto)
        whole = int(math.floor(full))
        pen = None

        def at(p):
            x, y, z = model.apply(view, p)
            f = LENS / (LENS - z)
            jx = jig.uniform(-1, 1) * wobble * size
            jy = jig.uniform(-1, 1) * wobble * size
            return cx + x * size * f + jx, cy + y * size * f + jy, z

        for k, (a, b) in enumerate(segs):
            if k > whole or (k == whole and full - whole <= 0):
                break
            pa, pb = at(a), at(b)
            if k == whole:
                share = full - whole
                pb = (pa[0] + (pb[0] - pa[0]) * share,
                      pa[1] + (pb[1] - pa[1]) * share,
                      pa[2] + (pb[2] - pa[2]) * share)
            proj.append((pa, pb))
            pen = (pb[0], pb[1])
        # Shadows on the floor.
        floor = cy - size * 1.25
        for pa, pb in proj:
            d.append(pyglet.shapes.Line(
                pa[0], floor + (pa[1] - cy) * 0.12, pb[0],
                floor + (pb[1] - cy) * 0.12, thickness=max(2.0, size * 0.05),
                color=(0, 0, 0, 70), batch=batch, group=self.card_group))
        proj.sort(key=lambda s: s[0][2] + s[1][2])
        for pa, pb in proj:
            near = max(0.0, min(1.0, ((pa[2] + pb[2]) / 2 + 1) / 2))
            colour = polish.mix(polish.darker(hue, 0.55),
                                polish.lighter(hue, 0.35), near)
            if faded:
                colour = polish.mix(colour, (90, 90, 110), 0.6)
            thick = max(2.0, size * (0.035 + 0.05 * near))
            d.append(pyglet.shapes.Line(
                pa[0], pa[1], pb[0], pb[1], thickness=thick * 2.2,
                color=tuple(hue) + (45,), batch=batch, group=group))
            d.append(pyglet.shapes.Line(pa[0], pa[1], pb[0], pb[1],
                                        thickness=thick, color=colour,
                                        batch=batch, group=group))
            for q in (pa, pb):
                d.append(pyglet.shapes.Circle(
                    q[0], q[1], thick * 0.62, color=colour, batch=batch,
                    group=group))
        return pen

    # --- the frame -----------------------------------------------------------

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
        hue = HUES[p.candidates[p.answer].colour % len(HUES)]
        if o:
            self._storm(left, bottom, width, height, t, o)
        self._time_bar(left, bottom, width, height, run)
        self._ears(left, bottom, width, height, t, p.mode != 'see')
        if not run.choosing:
            cx, cy = left + width / 2, bottom + height * 0.5
            size = min(width, height) * 0.3
            if p.heard:
                self._speaker(cx, cy, size, t)
            else:
                sway = model.matmul(model.axis_turn((0, 1, 0),
                                                    0.12 * math.sin(t * 0.9)),
                                    p.view)
                pen = self._shape(p.shape, sway, cx, cy, size, hue,
                                  upto=run.strokes(), wobble=0.01 * o,
                                  seed=int(t * 20))
                if pen is not None and run.strokes() < len(p.shape):
                    self._turtle(pen, size, t, hue, p.mode != 'sing')
            return
        if not self.message.startswith(_('Which')):
            n = len(p.candidates)
            self.message = {
                'sing': _('Which sound is the shape?  1-%d'),
                'echo': _('Which is the same tune?  1-%d'),
            }.get(p.mode, _('Which is the same shape?  1-%d')) % n
        if self._panel():
            kx = left + width * 0.03
            kw = width * 0.22
            ky, kh = bottom + height * 0.2, height * 0.6
            polish.card(d, batch, kx, ky, kw, kh, (36, 28, 70), radius=12,
                        edge=(120, 90, 200), shade=(0, 0, 0, 80),
                        group=self.card_group)
            self._text(_('the shape'), kx + kw / 2, ky + kh - 18, 14,
                       bold=True,
                       colour=(220, 210, 255, 230))
            sway = model.matmul(model.axis_turn((0, 1, 0),
                                                0.12 * math.sin(t * 0.9)),
                                p.view)
            self._shape(p.shape, sway, kx + kw / 2, ky + kh * 0.48,
                        min(kw, kh) * 0.34, hue)
        cells = self._cells()
        judged = run.result is not None
        singing = run.sounding()
        for k, (x, y, w, h) in enumerate(cells):
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
            view = c.view
            if level.tumble:
                view = model.matmul(model.axis_turn(c.spin, t * 0.7), c.view)
            else:
                view = model.matmul(model.axis_turn(
                    (0, 1, 0), 0.12 * math.sin(t * 0.9 + k)), c.view)
            ch = HUES[c.colour % len(HUES)]
            if o and shake.random() < 0.15 * o:
                ch = HUES[shake.randrange(len(HUES))]
            if p.sound_cards and not judged:
                self._sound_card(k, x, y, w, h, t, singing == k)
            else:
                    self._shape(c.segs, view, x + w / 2, y + h * 0.52,
                            min(w, h) * 0.4, ch, wobble=0.012 * o,
                            seed=int(t * 20) + k,
                            faded=judged and k != p.answer)
            badge = min(w, h) * 0.09
            polish.disc(d, batch, x + badge * 1.4, y + h - badge * 1.4,
                        badge, (250, 220, 90), group=self.top_group)
            self._text(str(k + 1), x + badge * 1.4, y + h - badge * 1.4,
                       badge * 0.95, bold=True, colour=(40, 20, 60, 255),
                       group=BADGE)
            if run.result is None:
                self.hits.append((x, y, w, h,
                                  lambda k=k: self.steer(k)))

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
                   if n.t <= t <= n.t + n.dur and n.who == -1)
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
        return _('rung %d  %d/%d   %d candidates   %s') % (
            self.rung, self.trial, self.total_trials, len(p.candidates),
            what)
