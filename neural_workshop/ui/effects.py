# -*- coding: utf-8 -*-
"""Two full-screen extras: the saccadic eye exercise and the donation plea.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import webbrowser
from typing import List, Sequence, Tuple

import pyglet
from pyglet.window import key

from .. import state
from ..constants import WEB_DONATE
from ..geometry import calc_fontsize, height_center, scale_to_height, width_center
from ..i18n import _


class Saccadic:
    """A square that jumps between the screen edges, to exercise the eyes."""

    def __init__(self) -> None:
        self.position = 'left'
        self.counter = 0
        self.radius = scale_to_height(10)
        self.color: Tuple[int, int, int, int] = (0, 0, 255, 255)
        self._shape: pyglet.shapes.Rectangle | None = None

    def tick(self, dt: float) -> None:
        self.counter += 1
        if self.counter == state.cfg.SACCADIC_REPETITIONS:
            self.stop()
        else:
            self.position = 'right' if self.position == 'left' else 'left'

    def start(self) -> None:
        self.position = 'left'
        state.mode.saccadic = True
        self.counter = 0
        pyglet.clock.schedule_interval(self.tick, state.cfg.SACCADIC_DELAY)

    def stop(self) -> None:
        pyglet.clock.unschedule(self.tick)
        state.mode.saccadic = False

    def draw(self) -> None:
        y = height_center()
        x = (self.radius if self.position == 'left'
             else state.window.width - self.radius)
        size = self.radius * 2
        pyglet.shapes.Rectangle(x - self.radius, y - self.radius, size, size,
                                color=self.color).draw()


def _panhandle_paragraphs(n: int) -> Sequence[str]:
    """The pool of appeal paragraphs, in weighting order."""
    return [
        _("""
You have completed %i sessions with Brain Workshop.  Your perseverance suggests \
that you are finding some benefit from using the program.  If you have been \
benefiting from Brain Workshop, don't you think Brain Workshop should \
benefit from you?
""") % n,
        _("""
Brain Workshop is and always will be 100% free.  Up until now, Brain Workshop \
as a project has succeeded because a very small number of people have each \
donated a huge amount of time to it.  It would be much better if the project \
were supported by small donations from a large number of people.  Do your \
part.  Donate.
"""),
        _("""
As of March 2010, Brain Workshop has been downloaded over 75,000 times in 20 \
months.  If each downloader donated an average of $1, we could afford to pay \
decent full- or part-time salaries (as appropriate) to all of our developers, \
and we would be able to buy advertising to help people learn about Brain \
Workshop.  With $2 per downloader, or with more downloaders, we could afford \
to fund controlled experiments and clinical trials on Brain Workshop and \
cognitive training.  Help us make that vision a reality.  Donate.
"""),
        _("""
The authors think it important that access to cognitive training \
technologies be available to everyone as freely as possible.  Like other \
forms of education, cognitive training should not be a luxury of the rich, \
since that would tend to exacerbate class disparity and conflict.  Charging \
money for cognitive training does exactly that.  The commercial competitors \
of Brain Workshop have two orders of magnitude more users than does Brain \
Workshop because they have far more resources for research, development, and \
marketing.  Help us bridge that gap and improve social equality of \
opportunity.  Donate.
"""),
        _("""
Brain Workshop has many known bugs and missing features.  The developers \
would like to fix these issues, but they also have to work in order to be \
able to pay for rent and food.  If you think the developers' time is better \
spent programming than serving coffee, then do something about it.  Donate.
"""),
        _("""
Press SPACE to continue, or press D to donate now.
"""),
    ]


class Panhandle:
    """The occasional request for a donation, after many sessions."""

    #: Relative weight per paragraph. Negative: always included. Zero:
    #: appended at the end and not counted towards the target length.
    CHANCES: Sequence[int] = (-1, 10, 10, 10, 10, 0)

    #: How many weighted paragraphs to show, besides the mandatory ones.
    TARGET_LENGTH = 3

    def __init__(self, n: int = -1) -> None:
        paragraphs = _panhandle_paragraphs(n)
        assert len(self.CHANCES) == len(paragraphs)

        chosen: List[int] = []
        pool: List[int] = []
        for i, chance in enumerate(self.CHANCES):
            if chance < 0:
                chosen.append(i)
            else:
                pool.extend([i] * chance)
        while len(chosen) < self.TARGET_LENGTH and pool:
            choice = random.choice(pool)
            pool = [i for i in pool if i != choice]
            chosen.append(choice)
        chosen.extend(i for i, chance in enumerate(self.CHANCES) if chance == 0)
        self.text = ''.join(paragraphs[i] for i in chosen)

        self.batch = pyglet.graphics.Batch()
        self.label = pyglet.text.Label(
            self.text, color=state.cfg.COLOR_TEXT, batch=self.batch,
            multiline=True, width=(4 * state.window.width) / 5,
            font_size=calc_fontsize(14), x=width_center(), y=height_center(),
            anchor_x='center', anchor_y='center')
        state.window.push_handlers(self.on_key_press, self.on_draw)
        self.on_draw()

    def on_key_press(self, sym: int, mod: int) -> bool:
        if sym in (key.ESCAPE, key.SPACE):
            self.close()
        elif sym in (key.RETURN, key.ENTER, key.D):
            self.select()
        return pyglet.event.EVENT_HANDLED

    def select(self) -> None:
        webbrowser.open_new_tab(WEB_DONATE)
        self.close()

    def close(self) -> None:
        state.window.remove_handlers(self.on_key_press, self.on_draw)

    def on_draw(self) -> bool:
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
