# -*- coding: utf-8 -*-
"""What Happens Next on screen: an opening above, the endings below.

The opening plays across the top; when it reaches its end it holds its
last frame and every option below plays at once, so each one is seen
following on from the moment the opening stopped. Then round again.
Click an option or press its number to choose it. When a choice is
judged, every option is labelled with what it was.

For the agent boundary: ports 0-5 choose options 1-6.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

import pyglet
from pyglet.window import key

from .. import datasets, media, videoclips, whatnext as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

#: Clips tried for one that makes a puzzle before giving up.
TRIES = 5

RIGHT = (60, 170, 90)
WRONG = (214, 64, 58)
CHOSEN = (40, 90, 220)
WIDTH, HEIGHT = videoclips.WIDTH, videoclips.HEIGHT


def _image(frame: bytes) -> pyglet.image.ImageData:
    return pyglet.image.ImageData(WIDTH, HEIGHT, 'RGB', frame,
                                  pitch=-WIDTH * 3)


class WhatNext(RungTask):
    """Pick the true continuation of a clip."""

    instance: Optional['WhatNext'] = None

    TITLE = 'What Happens Next'
    TASK_ID = 'what_next'
    PREFIX = 'WHAT_NEXT'
    CATEGORY = 'perception'
    PLAY = 'choosing'
    FEEDBACK = 3.0
    FOOTNOTE = _('click the stretch that really came next, or press 1-6'
                 '   Esc: menu')

    def __init__(self) -> None:
        self.puzzle: Optional[model.Puzzle] = None
        self.textures: List[pyglet.image.Texture] = []
        self.shown_at: List[int] = []
        self.chosen: Optional[int] = None
        self.pool = media.MediaPool(datasets.UCF101)
        self.rotation = media.Rotation(self.pool, 'seen_next.txt')
        super().__init__()
        self.pool.rng = self.rng

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.textures = []
        self.shown_at = []
        self.chosen = None

    # --- dealing ---------------------------------------------------------

    def _decode(self) -> Optional[List[bytes]]:
        path = self.rotation.take()
        if path is None:
            return None
        clip = videoclips.decode(path)
        return clip.frames if clip else None

    def _deal(self) -> bool:
        self._clear_trial()
        self.pool.rng = self.rng
        self.pool.reload()
        if not self.pool.paths:
            self.message = _('No video library yet — see the Readme')
            return False
        if not videoclips.have_ffmpeg():
            self.message = _('What Happens Next needs the ffmpeg program '
                             '— see the Readme')
            return False
        level = model.grade(self.rung)
        puzzle = None
        for _try in range(TRIES):
            frames = self._decode()
            if not frames:
                continue
            others = []
            if 'other' in level.kinds and len(self.pool.paths) > 1:
                # One more than the same-clip decoys leave room for, in
                # case one of those cannot be cut from this clip.
                same = len(level.kinds) - 1
                for _other in range(max(1, level.choices - same)):
                    more = self._decode()
                    if more:
                        others.append(more)
            puzzle = model.build(frames, others, level, self.rng)
            if puzzle is not None:
                break
        if puzzle is None:
            self.message = _('None of the downloaded clips would make a '
                             'puzzle')
            return False
        self.puzzle = puzzle
        self.textures = [_image(puzzle.opening[0]).get_texture()] + \
            [_image(option[0]).get_texture() for option in puzzle.options]
        self.shown_at = [0] * len(self.textures)
        self.message = _('Which of these is what happened next?')
        return True

    # --- playing ---------------------------------------------------------

    def _frames_now(self) -> List[int]:
        puzzle = self.puzzle
        opening = len(puzzle.opening)
        piece = len(puzzle.options[0])
        tick = int((self.clock() - self.started_at) * videoclips.FPS) \
            % (opening + piece)
        if tick < opening:
            return [tick] + [0] * len(puzzle.options)
        return [opening - 1] + [tick - opening] * len(puzzle.options)

    def _tick(self) -> None:
        if self.puzzle is None:
            return
        streams = [self.puzzle.opening] + list(self.puzzle.options)
        for index, at in enumerate(self._frames_now()):
            if at != self.shown_at[index]:
                self.shown_at[index] = at
                self.textures[index].blit_into(
                    _image(streams[index][at]), 0, 0, 0)

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.phase == 'judged':
            self._tick()

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        self.choose(port)

    def choose(self, index: int) -> None:
        if self.phase != self.PLAY or self.puzzle is None \
                or not 0 <= index < len(self.puzzle.options):
            return
        self.chosen = index
        right = index == self.puzzle.answer
        self._judge(right, _('Right: that is what happened') if right else
                    _('No — that was %s; option %d is what happened')
                    % (model.describe(self.puzzle.kinds[index]),
                       self.puzzle.answer + 1))

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._6:
            self.choose(symbol - key._1)

    # --- drawing ---------------------------------------------------------

    def _sprite(self, texture, x, y, w, h) -> None:
        sprite = pyglet.sprite.Sprite(texture, x=x, y=y, batch=self.batch,
                                      group=self.card_group)
        sprite.scale_x = w / float(texture.width)
        sprite.scale_y = h / float(texture.height)
        self.drawn.append(sprite)

    def _draw(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        if puzzle is None:
            return
        aspect = WIDTH / float(HEIGHT)
        size = calc_fontsize(12)
        # The opening, centred across the top half.
        oh = height * 0.46
        ow = min(width * 0.5, oh * aspect)
        oh = ow / aspect
        ox = left + (width - ow) / 2
        oy = bottom + height - oh
        self._sprite(self.textures[0], ox, oy, ow, oh)
        self._box(ox, oy, ow, oh, None, self.ink)
        self._text(_('how it starts'), ox - 12, oy + oh / 2, size,
                   anchor='right')
        # The options in one row.
        n = len(puzzle.options)
        gap = width * 0.015
        label_room = size * 2.6
        tw = min((width - gap * (n - 1)) / n,
                 (height - oh - label_room * 1.6) * aspect)
        th = tw / aspect
        x0 = left + (width - (n * tw + (n - 1) * gap)) / 2
        y = bottom + label_room
        for index in range(n):
            x = x0 + index * (tw + gap)
            self._sprite(self.textures[index + 1], x, y, tw, th)
            border, thick = self.ink, 2
            if self.phase == 'judged':
                if index == puzzle.answer:
                    border, thick = RIGHT, 5
                elif index == self.chosen:
                    border, thick = WRONG, 5
            self._box(x, y, tw, th, None, border, thickness=thick)
            self._text('%d' % (index + 1), x + tw / 2, y + th + size,
                       size * 1.2, bold=True)
            if self.phase == 'judged':
                self._text(model.describe(puzzle.kinds[index]),
                           x + tw / 2, y - size * 1.3, size * 0.9)
            self.hits.append((x, y, tw, th,
                              lambda i=index: self.choose(i)))

    def _facts(self) -> str:
        if self.puzzle is None:
            return ''
        return _('rung %d  %d/%d   %d options') % (
            self.rung, self.trial, self.total_trials,
            len(self.puzzle.options))
