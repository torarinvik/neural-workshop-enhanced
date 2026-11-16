# -*- coding: utf-8 -*-
"""Morning Round on screen: a street from above, a bicycle, a rulebook.

The street runs up the screen; the bicycle stays near the bottom and
the houses come down past it. The rulebook on the left says which
houses take a paper. A thrown paper flies straight across to the lawns
and lands where the bicycle has got to by then, so throw a little
before a house comes level. A house that got its paper shows a tick, a
house that wanted none a cross, a subscriber missed an exclamation mark;
they are heard as a chime, a shout and a horn.

Keys: Left / Right (or A / D) steer, Up / Down (or W / S) pedal faster or
slower, Z throws to the left and X to the right.

For the agent boundary: ports 0 steer left, 1 steer right, 2 faster,
3 slower (each for one step), 4 throws left, 5 throws right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import morninground as model
from ..constants import FONTLIST
from ..i18n import _
from .handtask import HandTask

GRASS = (112, 168, 92)
GRASS2 = (100, 156, 84)
ROADC = (92, 94, 102)
WALK = (196, 196, 188)
DOOR = {'red': (210, 50, 44), 'blue': (50, 100, 220),
        'green': (40, 150, 70), 'yellow': (240, 200, 40)}
WALL = (236, 224, 200)
PEAK = (150, 70, 56)
FLAT = (170, 172, 178)
INK = (30, 30, 40, 255)
PANEL = (34, 38, 54)
PALE = (230, 232, 240, 255)
DIM = (150, 156, 176, 255)
LETTERS = 'ABCDEFGH'


class MorningRound(HandTask):
    """Deliver the papers by the rules of the day."""

    instance: Optional['MorningRound'] = None

    TITLE = 'Morning Round'
    TASK_ID = 'morning_round'
    PREFIX = 'ROUND'
    CATEGORY = 'self_control'
    FEEDBACK = 3.5
    MODEL = model
    SUBSTEP = 1 / 120.0
    DRAW_POINTER = False
    BACK = (54, 60, 74)
    EVENT_KEYS = {key.Z: model.THROW_L, key.X: model.THROW_R}
    FOOTNOTE = _('Left / Right: steer   Up / Down: faster / slower   '
                 'Z: throw left   X: throw right')

    def _held(self) -> Optional[int]:
        k = self.keys
        if k[key.LEFT] or k[key.A]:
            return model.LEFT
        if k[key.RIGHT] or k[key.D]:
            return model.RIGHT
        if k[key.UP] or k[key.W]:
            return model.FASTER
        if k[key.DOWN] or k[key.S]:
            return model.SLOWER
        return None

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        if run is not None:
            mode = run.level.mode
            self.message = {
                'marked': _('Throw a paper to every house with a star'),
                'told': _('Throw a paper to the houses the rulebook names'),
                'sign': _('Follow the rule the crossroads sign shows'),
                'hidden': _('The rule may change at a crossroads: listen'),
            }[mode]
        return ok

    # --- layers: each layer's words just above its shapes -------------

    def g(self):
        self.layer += 1
        self._tg = pyglet.graphics.Group(order=10 * self.layer + 5)
        return pyglet.graphics.Group(order=10 * self.layer)

    def words(self, text, x, y, size, group=None, **kw):
        return super().words(text, x, y, size,
                             group=group or getattr(self, '_tg', None), **kw)

    # --- the scene ---------------------------------------------------------

    def _y(self, run, d: float) -> float:
        return model.RIDER_Y + (d - run.s)

    def _scene(self, run, s: float) -> None:
        st = run.street
        g = self.g()
        self.rect(320, 0, 560, 640, GRASS, g)
        for k in range(12):                     # mown stripes
            y = (k * 120 - run.s) % 1440 - 120
            self.rect(320, y, 560, 60, GRASS2, g)
        self.rect(model.ROAD[0], 0, model.ROAD[1] - model.ROAD[0], 640,
                  ROADC, g)
        self.rect(model.LEFT_FRONT + 4, 0, 16, 640, WALK, g)
        self.rect(model.RIGHT_FRONT - 20, 0, 16, 640, WALK, g)
        mid = (model.ROAD[0] + model.ROAD[1]) / 2
        for k in range(10):
            y = (k * 80 - run.s) % 800 - 80
            self.rect(mid - 2, y, 4, 40, (230, 220, 150), g)
        self._crossroads(run)
        g = self.g()
        for h in st.houses:
            y = self._y(run, h.d)
            if -80 < y < 720:
                self._house(run, h, y, g)
        self._things(run)
        self._rider(run)
        self._panel(run)

    def _crossroads(self, run) -> None:
        st = run.street
        g = self.g()
        for b, (lo, hi) in enumerate(st.blocks):
            # the cross street after this block, and the landmark before it
            if b + 1 < len(st.blocks):
                cy = self._y(run, (hi + st.blocks[b + 1][0]) / 2)
                if -90 < cy < 730:
                    self.rect(320, cy - 45, 560, 90, ROADC, g)
                    for x in range(330, 870, 40):
                        if not model.ROAD[0] - 10 < x < model.ROAD[1] + 10:
                            self.rect(x, cy - 2, 22, 4, (230, 220, 150), g)
                    if run.level.mode == 'sign':
                        self._sign(run, cy - 70, st.active[b + 1], g)
            ly = self._y(run, lo - 20)
            if -60 < ly < 700:
                self._landmark(st.landmarks[b], ly, g)

    def _sign(self, run, y, k, g) -> None:
        x = model.ROAD[1] + 30
        self.rect(x - 2, y - 30, 4, 30, (80, 80, 80), g)
        self.rect(x - 22, y, 44, 34, (250, 250, 250), g)
        self.rect(x - 20, y + 2, 40, 30, (30, 90, 170), g)
        self.words(LETTERS[k], x, y + 17, 18, bold=True, colour=PALE)

    def _landmark(self, what, y, g) -> None:
        x = 352
        if what == 'church':
            self.rect(x - 16, y - 14, 32, 26, (200, 200, 210), g)
            self.rect(x - 2, y + 12, 4, 18, (80, 80, 90), g)
            self.rect(x - 8, y + 22, 16, 4, (80, 80, 90), g)
        elif what == 'shop':
            self.rect(x - 18, y - 12, 36, 24, (230, 150, 60), g)
            self.rect(x - 18, y + 6, 36, 6, (200, 60, 60), g)
        elif what == 'park':
            for dx, dy in ((-10, 0), (8, 6), (2, -10)):
                self.disc((x + dx, y + dy), 9, (60, 130, 60), g)
        else:
            self.rect(x - 18, y - 12, 36, 24, (190, 110, 90), g)
            self.rect(x - 3, y + 12, 6, 12, (90, 90, 90), g)
        if 10 < y - 24 < 630:
            self.words(_(what.upper()), x, y - 24, 8, bold=True,
                       colour=INK)

    def _house(self, run, h, y, g) -> None:
        left = h.side < 0
        x0, x1 = (340.0, 440.0) if left else (760.0, 860.0)
        half = (model.HOUSE_LEN - 16) / 2
        cx = (x0 + x1) / 2
        # walls and roof, seen from above
        self.rect(x0 - 3, y - half - 3, x1 - x0 + 6, 2 * half + 6, WALL, g)
        if h.pointed:
            self.rect(x0, y - half, x1 - x0, 2 * half, PEAK, g)
            ridge = (x0 + 18, y), (x1 - 18, y)
            self.line(*ridge, 3, (100, 40, 30), g)
            for ex, sx in ((x0, x0 + 18), (x1, x1 - 18)):
                self.line((ex, y - half), (sx, y), 2, (100, 40, 30), g)
                self.line((ex, y + half), (sx, y), 2, (100, 40, 30), g)
        else:
            self.rect(x0, y - half, x1 - x0, 2 * half, FLAT, g)
            self.rect(x0 + 6, y - half + 6, x1 - x0 - 12, 2 * half - 12,
                      (150, 152, 160), g)
        # the street side: windows either side of the door
        face = x1 if left else x0
        out = 1 if left else -1
        lit = (255, 252, 225) if h.lights else (36, 44, 70)
        for wy in (y - 28, y + 28):
            self.rect(face + (0 if left else -8), wy - 8, 8, 16, lit, g)
        self.rect(face + (0 if left else -13), y - 13, 13, 26,
                  DOOR[h.door], g)
        if h.cat:
            cxp = face + out * 18
            self.oval((cxp, y + 2), 7, 5, (120, 120, 130), g)
            self.poly([(cxp - 6, y + 6), (cxp - 3, y + 12), (cxp, y + 6)],
                      (120, 120, 130), g)
            self.poly([(cxp, y + 6), (cxp + 3, y + 12), (cxp + 6, y + 6)],
                      (120, 120, 130), g)
        if h.dog:
            dx = face + out * 34
            self.oval((dx, y - 30), 12, 7, (140, 90, 50), g)
            self.disc((dx + out * 12, y - 26), 6, (140, 90, 50), g)
        # mailbox and flag at the walk
        mx = (model.LEFT_FRONT - 6) if left else (model.RIGHT_FRONT + 6)
        self.rect(mx - 6, y + 30, 12, 10, (60, 60, 70), g)
        if h.flag:
            self.rect(mx + 4, y + 38, 4, 14, (220, 40, 40), g)
        else:
            self.rect(mx + 4, y + 30, 10, 3, (120, 120, 120), g)
        if 10 < y - 44 < 630:
            self.words(str(h.number), mx, y - 44, 10, bold=True, colour=INK)
        if h.sign:
            pts = [(cx + 16 * math.cos(math.pi / 2 + k * math.pi / 5) *
                    (1.0 if k % 2 == 0 else 0.45),
                    y + 16 * math.sin(math.pi / 2 + k * math.pi / 5) *
                    (1.0 if k % 2 == 0 else 0.45)) for k in range(10)]
            for k in range(10):
                self.poly([(cx, y), pts[k], pts[(k + 1) % 10]],
                          (255, 214, 40), g)
        got = run.got.get(h.i)
        if got == 'ok':
            self.line((cx - 12, y), (cx - 3, y - 10), 5, (60, 200, 90), g)
            self.line((cx - 3, y - 10), (cx + 14, y + 12), 5,
                      (60, 200, 90), g)
        elif got == 'wrong':
            self.line((cx - 12, y - 12), (cx + 12, y + 12), 5,
                      (230, 50, 40), g)
            self.line((cx - 12, y + 12), (cx + 12, y - 12), 5,
                      (230, 50, 40), g)
        elif got == 'missed':
            self.disc((cx, y), 14, (250, 150, 40), g)
            if 10 < y < 630:
                self.words('!', cx, y, 16, bold=True, colour=INK)

    def _things(self, run) -> None:
        g = self.g()
        for k, th in enumerate(run.street.things):
            if k in run.hit:
                continue
            y = self._y(run, run.thing_d(th))
            if not -60 < y < 700:
                continue
            if th.kind == 'cone':
                self.poly([(th.x - 11, y - 10), (th.x + 11, y - 10),
                           (th.x, y + 12)], (250, 130, 30), g)
            elif th.kind == 'bin':
                self.disc((th.x, y), th.r, (70, 110, 80), g)
                self.disc((th.x, y), th.r - 4, (90, 140, 100), g)
            elif th.kind == 'car':
                self.rect(th.x - 22, y - 36, 44, 72, (90, 120, 200), g)
                self.rect(th.x - 17, y - 14, 34, 28, (180, 210, 240), g)
            else:
                self.line((th.x, y - 14), (th.x, y + 14), 4, (40, 40, 40), g)
                self.disc((th.x, y - 2), 7, (200, 60, 160), g)

    def _rider(self, run) -> None:
        g = self.g()
        x, y = run.x, model.RIDER_Y
        down = run.t < run.down_until
        if down:
            self.line((x - 16, y - 8), (x + 16, y + 8), 4, (30, 30, 30), g)
            self.disc((x + 10, y - 10), 8, (250, 200, 160), g)
            return
        self.line((x, y - 18), (x, y + 18), 4, (30, 30, 30), g)
        self.line((x - 10, y + 10), (x + 10, y + 10), 3, (60, 60, 60), g)
        self.disc((x, y), 9, (230, 70, 60), g)
        self.disc((x, y + 4), 6, (250, 200, 160), g)
        bag = run.papers
        self.words(str(bag), x + 22, y - 14, 9, bold=True, colour=PALE)
        for p in run.flying:
            py = self._y(run, p.d)
            self.rect(p.x - 7, py - 3, 14, 6, (250, 250, 250), g)

    # --- the rulebook ----------------------------------------------------------

    def _panel(self, run) -> None:
        st, level = run.street, run.level
        g = self.g()
        self.rect(0, 0, 310, 640, PANEL, g)
        self.words(_('RULEBOOK'), 155, 612, 13, bold=True, colour=PALE)
        y = 580
        if not run.rulebook_open():
            self.words(_('Put away: ride from memory'), 155, y, 10,
                       colour=DIM)
            y -= 30
        elif level.mode == 'marked':
            self.words(_('Deliver to every house with a star in the '
                         'window.'), 16, y, 11, anchor='left', width=280,
                       anchor_y='top', colour=PALE)
            y -= 70
        else:
            if level.mode == 'told':
                self.words(_('Deliver to houses with:'), 16, y, 10,
                           anchor='left', colour=DIM)
                y -= 20
            now = self._rule_now(run)
            note = None
            if level.mode == 'sign':
                note = _('The sign at each crossroads says which rule holds '
                         'from there.')
            elif level.mode == 'hidden':
                note = _('Start with %s. At any crossroads the rule may '
                         'change without a word.') % LETTERS[st.active[0]]
            texts = [((LETTERS[k] + ':  ') if len(st.deck) > 1 else '') +
                     model.say(rule) for k, rule in enumerate(st.deck)]
            size = self._fit_size(texts, y - 20, 10.5)
            for k, text in enumerate(texts):
                lab = self.words(text, 16, y, size, anchor='left',
                                 width=280, anchor_y='top', colour=PALE)
                tall = lab.content_height / max(0.01, self.fit[2])
                if now == k and len(st.deck) > 1:
                    self.rect(8, y - tall - 4, 294, tall + 8,
                              (60, 70, 110), g)
                y -= tall + 0.9 * size
            if note:
                self.words(note, 16, y, min(9.0, size), anchor='left',
                           width=280, anchor_y='top', colour=DIM)
        if not run.riding():
            left = level.brief - run.t
            self.rect(500, 300, 200, 50, PANEL, g)
            self.words(_('Setting off in %d') % int(math.ceil(left)), 600,
                       325, 15, bold=True, colour=(255, 220, 120, 255))
        # the counters, in the margin on the right
        rows = ((_('papers'), str(run.papers), PALE),
                (_('mistakes'), '%d / %d' % (run.mistakes, level.slack),
                 (255, 150, 120, 255) if run.mistakes else PALE),
                (_('falls'), '%d / 3' % run.falls, PALE),
                (_('block'), '%d / %d' % (min(len(st.blocks),
                                              run.block_at(run.s) + 1),
                                          len(st.blocks)), PALE))
        for k, (name, value, colour) in enumerate(rows):
            y = 600 - k * 52
            self.words(name, 940, y, 9, colour=DIM)
            self.words(value, 940, y - 20, 13, bold=True, colour=colour)

    def _fit_size(self, texts, room: float, size: float) -> float:
        """The largest font size, at most *size*, at which *texts* fit in
        *room* units of height (worked out once for each rulebook)."""
        memo = self.__dict__.setdefault('_sizes', {})
        key_ = (tuple(texts), room, size, self.fit[2])
        if key_ not in memo:
            memo[key_] = self._measure(texts, room, size)
        return memo[key_]

    def _measure(self, texts, room: float, size: float) -> float:
        while size > 6.0:
            tall = 0.0
            for text in texts:
                lab = pyglet.text.Label(text, font_size=size * self.fit[2],
                                        width=int(280 * self.fit[2]),
                                        multiline=True, font_name=FONTLIST)
                tall += lab.content_height / max(0.01, self.fit[2]) + \
                    0.9 * size
            if tall <= room - 50:
                return size
            size -= 0.5
        return size

    def _rule_now(self, run) -> Optional[int]:
        """The rule the screen may say is in force: always when it is
        told, from the last sign passed when there are signs, the first
        one before any crossroads when it is hidden."""
        st, mode = run.street, run.level.mode
        if mode in ('marked', 'told'):
            return 0
        b = run.block_at(run.s)
        if mode == 'sign':
            return st.active[b]
        return st.active[0] if b == 0 else None

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
