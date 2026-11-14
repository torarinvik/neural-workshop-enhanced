# -*- coding: utf-8 -*-
"""Manual on screen: the panel on the left, the procedure on the right.

Lamps and the display along the top of the panel; under them a row of
switches (click to flip), a row of knobs (click the minus or plus under
one to turn it a step) and a row of buttons (click to press). Finish
(Enter) hands it in. :mod:`neural_workshop.manual` deals the panel and
the procedure and knows what following it leaves.

When a round is judged every control that is not where the procedure
leaves it is outlined in red.

For the agent boundary, the ports name places on the panel, not
controls, so from rung 17, when the labels are shuffled, a port still
means the same place and the label has to be read: ports 0-5 flip the
switches in the order they are drawn, ports 6-13 turn the knobs (two to
a knob: down, then up), ports 14-19 press the buttons, port 20 is
Finish.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import manual as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

KNOB = model.MOST_SWITCHES
BUTTON = KNOB + 2 * model.MOST_KNOBS
FINISH = BUTTON + model.MOST_BUTTONS
PORTS = FINISH + 1

FACE_LIGHT = (226, 229, 235)
FACE_DARK = (50, 54, 62)
LAMP = {'green': (60, 190, 90), 'red': (220, 60, 50), 'off': (90, 94, 102)}
ON = (60, 150, 230)
OFF = (150, 154, 162)
WRONG = (214, 64, 58)
DIGIT = (255, 170, 40)


class Manual(RungTask):
    """Follow a written procedure on a panel never seen before."""

    instance: Optional['Manual'] = None

    TITLE = 'Manual'
    TASK_ID = 'manual'
    PREFIX = 'MANUAL'
    CATEGORY = 'computer'
    FOOTNOTE = _('click switches, knob - and +, and buttons   '
                 'Enter: finish   Esc: menu')

    def __init__(self) -> None:
        self.deal: Optional[model.Deal] = None
        self.panel: Optional[model.Panel] = None
        self.wanted: Optional[model.Panel] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.deal = self.panel = self.wanted = None

    def _deal(self) -> bool:
        self.deal = model.deal(self.rung, rng=self.rng)
        self.panel = self.deal.panel()
        self.wanted = model.follow(self.deal)
        self.message = _('Follow the procedure, then press Finish')
        return True

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY:
            return
        switches, knobs, buttons = self.deal.layout
        if port < KNOB:
            if port < len(switches):
                self.flip(switches[port])
        elif port < BUTTON:
            slot, way = divmod(port - KNOB, 2)
            if slot < len(knobs):
                self.turn(knobs[slot], 1 if way else -1)
        elif port < FINISH:
            if port - BUTTON < len(buttons):
                self.press(buttons[port - BUTTON])
        else:
            self.finish()

    def flip(self, index: int) -> None:
        if self.phase == self.PLAY and self.panel.toggle(index):
            self._redraw()

    def turn(self, index: int, way: int) -> None:
        if self.phase == self.PLAY and self.panel.turn(index, way):
            self._redraw()

    def press(self, index: int) -> None:
        if self.phase == self.PLAY and self.panel.press(index):
            self._redraw()

    def finish(self) -> None:
        if self.phase != self.PLAY:
            return
        wrong = self.mistakes()
        if not wrong:
            self._judge(True, _('Done exactly as written'))
        else:
            self._judge(False, _('Not as written: %s') % ', '.join(wrong))

    def mistakes(self) -> List[str]:
        have, want = self.panel, self.wanted
        wrong = [model.switch_name(i) for i in range(len(have.switches))
                 if have.switches[i] != want.switches[i]]
        wrong += [model.knob_name(i) for i in range(len(have.knobs))
                  if have.knobs[i] != want.knobs[i]]
        wrong += [_('%s pressed %d times, not %d')
                  % (model.button_name(i), have.presses[i], want.presses[i])
                  for i in range(len(have.presses))
                  if have.presses[i] != want.presses[i]]
        return wrong

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in (key.RETURN, key.ENTER):
            self.finish()

    # --- drawing ---------------------------------------------------------

    def _circle(self, x, y, r, colour) -> None:
        self.drawn.append(pyglet.shapes.Circle(
            x, y, r, color=colour, batch=self.batch, group=self.body_group))

    def _draw(self, left, bottom, width, height) -> None:
        panel_w = width * 0.56
        face = FACE_DARK if self.dark else FACE_LIGHT
        self._box(left, bottom, panel_w, height, face, self.ink)
        self._draw_panel(left, bottom, panel_w, height)
        self._draw_steps(left + panel_w + width * 0.03, bottom,
                         width - panel_w - width * 0.03, height, face)

    def _rows(self) -> List[str]:
        level = self.deal.level
        rows = ['lamps', 'switches']
        if level.knobs:
            rows.append('knobs')
        if level.buttons:
            rows.append('buttons')
        return rows

    def _draw_panel(self, left, bottom, width, height) -> None:
        rows = self._rows()
        band = height / len(rows)
        size = min(calc_fontsize(12), band * 0.12)
        wrong = set()
        if self.phase == 'judged':
            have, want = self.panel, self.wanted
            wrong = ({('switch', i) for i in range(len(have.switches))
                      if have.switches[i] != want.switches[i]}
                     | {('knob', i) for i in range(len(have.knobs))
                        if have.knobs[i] != want.knobs[i]}
                     | {('button', i) for i in range(len(have.presses))
                        if have.presses[i] != want.presses[i]})
        for row_index, row in enumerate(rows):
            top = bottom + height - row_index * band
            getattr(self, '_row_' + row)(left, top - band, width, band,
                                         size, wrong)

    def _slots(self, left, width, count) -> List[float]:
        cell = width / max(count, 1)
        return [left + cell * (i + 0.5) for i in range(count)]

    def _row_lamps(self, left, bottom, width, band, size, wrong) -> None:
        panel = self.panel
        count = self.deal.level.lamps + 1
        xs = self._slots(left, width, count)
        r = min(band * 0.24, width / count * 0.25)
        cy = bottom + band * 0.55
        for i in range(self.deal.level.lamps):
            self._circle(xs[i], cy, r * 1.12, self.ink)
            self._circle(xs[i], cy, r, LAMP[panel.lamp(i)])
            self._text(model.lamp_name(i), xs[i], cy - r - size * 1.4, size)
        w, h = r * 2.4, r * 2.2
        x = xs[-1] - w / 2
        self._box(x, cy - h / 2, w, h, (20, 20, 24), self.ink)
        self._text('%d' % panel.display(), xs[-1], cy, r * 1.3,
                   bold=True, colour=(*DIGIT, 255))
        self._text(_('display'), xs[-1], cy - h / 2 - size * 1.4, size)

    def _row_switches(self, left, bottom, width, band, size, wrong) -> None:
        order = self.deal.layout[0]
        xs = self._slots(left, width, len(order))
        w = min(band * 0.4, width / len(order) * 0.5)
        h = band * 0.5
        for slot, index in enumerate(order):
            x, y = xs[slot] - w / 2, bottom + band * 0.32
            on = self.panel.switches[index]
            self._box(x, y, w, h, (30, 32, 38),
                      WRONG if ('switch', index) in wrong else self.ink,
                      thickness=4 if ('switch', index) in wrong else 2)
            knob_y = y + h * (0.55 if on else 0.05)
            self._box(x + 3, knob_y, w - 6, h * 0.4, ON if on else OFF)
            self._text(_('on') if on else _('off'), xs[slot],
                       y + h + size * 0.9, size * 0.9)
            self._text(model.switch_name(index), xs[slot],
                       y - size * 1.2, size, bold=True)
            self.hits.append((x, y, w, h, lambda i=index: self.flip(i)))

    def _row_knobs(self, left, bottom, width, band, size, wrong) -> None:
        order = self.deal.layout[1]
        xs = self._slots(left, width, len(order))
        r = min(band * 0.22, width / len(order) * 0.18)
        cy = bottom + band * 0.62
        for slot, index in enumerate(order):
            x = xs[slot]
            bad = ('knob', index) in wrong
            self._circle(x, cy, r * 1.1, WRONG if bad else self.ink)
            self._circle(x, cy, r, (70, 74, 84))
            at = self.panel.knobs[index]
            # 0 points left, TOP points right, over the top.
            angle = math.pi * (1 - at / float(model.TOP))
            self.drawn.append(pyglet.shapes.Line(
                x, cy, x + r * 0.9 * math.cos(angle),
                cy + r * 0.9 * math.sin(angle), thickness=max(2, r * 0.15),
                color=(255, 255, 255), batch=self.batch,
                group=self.text_group))
            for tick in range(model.TOP + 1):
                a = math.pi * (1 - tick / float(model.TOP))
                self._text('%d' % tick, x + r * 1.45 * math.cos(a),
                           cy + r * 1.45 * math.sin(a), size * 0.75)
            self._text(model.knob_name(index), x - r * 1.9, cy, size,
                       bold=True, anchor='right')
            bw, bh = r * 0.9, band * 0.2
            by = bottom + band * 0.06
            for way, words in ((-1, '-'), (1, '+')):
                bx = x - bw - 2 if way < 0 else x + 2
                self._box(bx, by, bw, bh, None, self.ink)
                self._text(words, bx + bw / 2, by + bh / 2, size * 1.3,
                           bold=True)
                self.hits.append((bx, by, bw, bh,
                                  lambda i=index, w=way: self.turn(i, w)))

    def _row_buttons(self, left, bottom, width, band, size, wrong) -> None:
        order = self.deal.layout[2]
        xs = self._slots(left, width, len(order))
        w = min(band * 0.55, width / len(order) * 0.6)
        for slot, index in enumerate(order):
            x, y = xs[slot] - w / 2, bottom + band * 0.3
            bad = ('button', index) in wrong
            self._box(x, y, w, w * 0.8, (180, 60, 60) if index % 2 else
                      (60, 90, 180), WRONG if bad else self.ink,
                      thickness=4 if bad else 2)
            self._text(model.button_name(index), xs[slot], y + w * 0.4,
                       size * 1.1, bold=True, colour=(255, 255, 255, 255))
            self.hits.append((x, y, w, w * 0.8,
                              lambda i=index: self.press(i)))

    def _draw_steps(self, left, bottom, width, height, face) -> None:
        size = calc_fontsize(13)
        words = '\n'.join('%d.  %s' % (n + 1, step.words)
                          for n, step in enumerate(self.deal.steps))
        fh = height * 0.12
        top = bottom + height
        label = self._text(words, left, top, size, anchor='left',
                           width=width, anchor_y='top')
        # Shrink until the procedure fits above Finish.
        while label.content_height > height - fh * 1.3 and size > 7:
            size *= 0.92
            label.font_size = size
        fw = width * 0.6
        fx = left + width - fw
        self._box(fx, bottom, fw, fh, face, self.ink)
        words = self._text(_('Finish (Enter)'), fx + fw / 2,
                           bottom + fh / 2,
                           min(calc_fontsize(14), fh * 0.35), bold=True)
        if words.content_width > fw * 0.9:
            words.font_size *= fw * 0.9 / words.content_width
        self.hits.append((fx, bottom, fw, fh, self.finish))

    def _facts(self) -> str:
        if self.deal is None:
            return ''
        return _('rung %d  %d/%d   %d steps') % (
            self.rung, self.trial, self.total_trials, len(self.deal.steps))


def reference_ports(task) -> List[int]:
    """The ports that carry out the whole procedure, then Finish: what a
    player who follows it exactly would press."""
    dealt = task.deal
    switches, knobs, buttons = dealt.layout
    ports = []
    for action in model.follow(dealt).log:
        if action[0] == 'switch':
            ports.append(switches.index(action[1]))
        elif action[0] == 'knob':
            ports.append(KNOB + 2 * knobs.index(action[1])
                         + (1 if action[2] > 0 else 0))
        else:
            ports.append(BUTTON + buttons.index(action[1]))
    return ports + [FINISH]
