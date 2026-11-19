# -*- coding: utf-8 -*-
"""Heard back, on screen: tones a frame at a time, which the screen
shows only as a pulse, and four cards.

For the agent boundary: Changed Note has four ports, one a place in
the four tones, first to fourth; its twin Changed Chime four, fourth
to first. Marked Tone has four, one a pitch, lowest to highest; its
twin Other Voice four, highest to lowest. The tones reach the agent
only as sound. Presses before the question is put are ignored.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import framed
from .. import heardback as model
from .framed import FrameTask


class HeardTask(FrameTask):
    """Tones, and a question about them."""

    FAMILY = model

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        look = p.data['look']
        _f, value = self._frame(t)
        colour = self._hue() if look == 0 else \
            framed.BEADS[(p.data['rim'] * 3 + 2) % framed.THINGS]
        sounding = value is not None and value >= 0 and \
            t - int(t / framed.FRAME + framed.GIVE) * framed.FRAME < \
            framed.SHOWN
        if look == 0:
            card = min(width * 0.16, height * 0.32)
            r = min(width, height - card * 1.4) * 0.16
            cx = left + width / 2
            cy = bottom + card * 1.4 + (height - card * 1.4) / 2
            x0 = left + (width - card * 4.6) / 2
            places = [(x0 + i * card * 1.2, bottom) for i in range(4)]
        else:
            card = min(height * 0.2, width * 0.13)
            r = min(width - card * 2, height) * 0.16
            cx = left + (width - card * 2) * 0.45
            cy = bottom + height / 2
            x = left + width - card * 1.25
            y0 = bottom + (height - card * 4.6) / 2
            places = [(x, y0 + i * card * 1.2) for i in range(4)]
        self.drawn.append(pyglet.shapes.Circle(
            cx, cy, r * (1.25 if sounding else 1.0), color=colour,
            batch=self.batch, group=self.body_group))
        order = framed.port_order(look, 4)
        for port in range(4):
            place = order[port]
            x, y = places[place]
            self._card(port, x, y, card, card)
            if self.KIND == 'melody':
                for i in range(4):
                    dot = pyglet.shapes.Circle(
                        x + card * (0.2 + 0.2 * i), y + card * 0.4,
                        card * 0.07, color=colour if i == place
                        else self.ink, batch=self.batch,
                        group=self.text_group)
                    if i != place:
                        dot.opacity = 90
                    self.drawn.append(dot)
            else:
                self.drawn.append(pyglet.shapes.Rectangle(
                    x + card * 0.36, y + card * 0.12, card * 0.28,
                    card * (0.18 + 0.17 * place), color=colour,
                    batch=self.batch, group=self.text_group))
        self._asked(left + width * 0.04, bottom + height * 0.75,
                    card * 0.4)


class ChangedNote(HeardTask):
    """Four tones, twice: which one changed?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Changed Note', 'changed_note', 'CHANGEDNOTE'
    KIND, LOOK = 'melody', 0


class ChangedChime(HeardTask):
    """Four chimes, twice: which one changed?"""
    instance = None
    TITLE, TASK_ID, PREFIX = ('Changed Chime', 'changed_chime',
                              'CHANGEDCHIME')
    KIND, LOOK = 'melody', 1


class MarkedTone(HeardTask):
    """A tone in its own voice, then look-alikes: which pitch was it?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Marked Tone', 'marked_tone', 'MARKEDTONE'
    KIND, LOOK = 'mark', 0


class OtherVoice(HeardTask):
    """A tone in another voice, then look-alikes: which pitch?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Other Voice', 'other_voice', 'OTHERVOICE'
    KIND, LOOK = 'mark', 1
