# -*- coding: utf-8 -*-
"""Video Jigsaw: a jigsaw puzzle whose picture is moving.

A short clip is cut into a grid of tiles -- two, or a dozen, or
hundreds -- and the tiles are shuffled. Every tile goes on playing its
own part of the picture, all of them in step, and two clicks swap two
of them, exactly as in :mod:`neural_workshop.ui.jigsaw`; the puzzle is
done when the clip is whole again.

What it adds to the still jigsaw is a second kind of evidence. An edge
of one tile still has to meet an edge of another, but now things also
cross those edges: an arm leaves one tile and has to arrive in the one
beside it on the same frame, a ball's arc runs through three of them,
a camera pan drags every tile's texture the same way at once. A tile
of plain wall that no still frame could place is placed by the shadow
that sweeps through it. Read the other way, a learner that only ever
looks at one frame is solving the photograph jigsaw with a worse
photograph.

Video Sequence cuts a clip in time and asks for the order things
happened in; this cuts it in space and leaves time alone.

The clips are UCF-101, fetched once (see the Readme) and decoded by the
``ffmpeg`` tool; the task says so if either is missing. The rotation is
its own, so a clip ordered in Video Sequence is still new here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

import pyglet

from .. import datasets, media, videoclips
from ..i18n import _
from .jigsaw import JigsawPuzzle

#: The size clips are decoded to: UCF-101's own, so a tile of a large
#: grid still has pixels in it.
WIDTH, HEIGHT = 320, 240

#: How many clips are tried for one that moves before settling.
TRIES = 4


class VideoJigsaw(JigsawPuzzle):
    """The jigsaw, with a playing clip for its picture."""

    instance: Optional['VideoJigsaw'] = None

    TITLE = 'Video Jigsaw'
    TASK_ID = 'video_jigsaw'
    PREFIX = 'VIDEO_JIGSAW'
    CATEGORY = 'reasoning'
    ASPECT = WIDTH / float(HEIGHT)
    FPS = videoclips.FPS
    SEEN = 'seen_jigsaw.txt'

    def __init__(self) -> None:
        #: The clip's frames, as raw rows; one texture shows them all.
        self.clip: List[bytes] = []
        self.frame = 0
        super().__init__()

    def _make_pool(self):
        return media.MediaPool(datasets.UCF101, self.rng)

    def _reset(self) -> None:
        super()._reset()
        self.clip = []

    def _finish(self) -> None:
        self.clip = []
        super()._finish()

    def _decode(self) -> Optional[List[bytes]]:
        """A clip's frames: the first tried that moves, else the last
        that decoded at all."""
        found: Optional[List[bytes]] = None
        for _try in range(TRIES):
            path = self._take_fresh()
            if path is None:
                break
            clip = videoclips.decode(path, width=WIDTH, height=HEIGHT)
            if clip is None or len(clip.frames) < 2:
                continue
            found = clip.frames
            if videoclips.lively(videoclips.cut(clip.frames, 3)):
                break
        return found

    @staticmethod
    def _data(frame: bytes) -> pyglet.image.ImageData:
        return pyglet.image.ImageData(WIDTH, HEIGHT, 'RGB', frame,
                                      pitch=-WIDTH * 3)

    def _load_picture(self) -> Optional[pyglet.image.AbstractImage]:
        self.pool.reload()
        if not self.pool.paths:
            self.message = _('No video library yet — see the Readme')
            return None
        if not videoclips.have_ffmpeg():
            self.message = _('Video Jigsaw needs the ffmpeg program — '
                             'see the Readme')
            return None
        frames = self._decode()
        if not frames:
            self.message = _('None of the downloaded clips would decode')
            return None
        self.clip = frames
        self.frame = 0
        # One texture for the whole puzzle. The tiles are regions of
        # it, and playing the clip is pouring each frame into it: a
        # thousand tiles move for the price of one upload.
        return self._data(frames[0])

    def _library_note(self) -> str:
        stocked = len(self.pool.paths)
        return (_('only %d clips downloaded — clips will repeat; see '
                  'the Readme') % stocked
                if stocked < self.total_puzzles else '')

    def _frame_now(self) -> int:
        if len(self.clip) < 2:
            return 0
        return int((self.clock() - self.started_at) * self.FPS) \
            % len(self.clip)

    def _play(self) -> None:
        frame = self._frame_now()
        if frame == self.frame or self.image is None or not self.clip:
            return
        self.frame = frame
        self.image.blit_into(self._data(self.clip[frame]), 0, 0, 0)
