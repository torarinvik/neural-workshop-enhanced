# -*- coding: utf-8 -*-
"""Decoding video clips into frames, and cutting them into segments.

The video puzzle needs a clip as a short run of small RGB frames it
can upload as textures, and nothing more: no audio, no seeking while
it plays, no codec negotiation at draw time. So a clip is decoded once,
up front, by the ``ffmpeg`` command-line tool into raw ``rgb24`` bytes
at a fixed size and rate, and everything after that is slicing lists.

``ffmpeg`` rather than a Python binding because it is one binary the
player either has or does not, decodes every container UCF-101 ships
in, and keeps the repository's dependencies where they were. Without
it the task says so, as it does for a missing library.

Nothing here imports pyglet; the frames are plain bytes, rows top to
bottom, so the tests can check the cutting without a window.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import shutil
import subprocess
from typing import List, NamedTuple, Optional

#: Decoded frame size. UCF-101 is 320x240; half that is plenty for a
#: tile, and a few seconds of it is a few megabytes in memory.
WIDTH, HEIGHT = 160, 120

#: Frames per second the clip is resampled to. Smooth enough to read
#: motion, sparse enough that a clip is a hundred-odd textures.
FPS = 15

#: The longest stretch of a clip used. UCF-101 clips average about
#: seven seconds; a long one is trimmed rather than played slower.
LONGEST = 8.0

#: A decode that takes longer than this is abandoned.
_TIMEOUT = 30


class Clip(NamedTuple):
    """A decoded clip: frames of ``WIDTH*HEIGHT*3`` bytes, top row first."""

    frames: List[bytes]
    width: int
    height: int
    fps: int


def have_ffmpeg() -> bool:
    """Whether clips can be decoded on this machine."""
    return shutil.which('ffmpeg') is not None


def decode(path: str, width: int = WIDTH, height: int = HEIGHT,
           fps: int = FPS, longest: float = LONGEST) -> Optional[Clip]:
    """Decode *path* to frames, or ``None`` if it will not decode.

    The picture is scaled to cover *width* by *height* and centre
    cropped, so every clip tiles the same whatever its aspect.
    """
    binary = shutil.which('ffmpeg')
    if binary is None:
        return None
    command = [
        binary, '-v', 'error', '-nostdin', '-i', path, '-t', '%.2f' % longest,
        '-an', '-vf',
        ('fps=%d,scale=%d:%d:force_original_aspect_ratio=increase,'
         'crop=%d:%d' % (fps, width, height, width, height)),
        '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-']
    try:
        done = subprocess.run(command, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=_TIMEOUT,
                              check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    size = width * height * 3
    data = done.stdout
    frames = [data[at:at + size] for at in range(0, len(data) - size + 1,
                                                 size)]
    if not frames:
        return None
    return Clip(frames, width, height, fps)


def cut(frames: List[bytes], pieces: int) -> List[List[bytes]]:
    """*frames* in *pieces* contiguous runs of equal length.

    A remainder that does not divide is dropped from the end, so no
    segment is a frame longer than another — a length difference would
    say which piece was last without anyone looking at it.
    """
    if pieces < 1 or len(frames) < pieces:
        return []
    span = len(frames) // pieces
    return [frames[index * span:(index + 1) * span]
            for index in range(pieces)]


def difference(one: bytes, two: bytes, stride: int = 97) -> float:
    """Mean absolute difference of two frames, on a sample of bytes,
    from 0 (identical) to 255."""
    sample = range(0, min(len(one), len(two)), stride)
    if not sample:
        return 0.0
    return sum(abs(one[at] - two[at]) for at in sample) / len(sample)


#: Below this, neighbouring segments look alike enough that their order
#: is a guess: a static shot, a slow pan over sky. Measured on UCF-101,
#: a clip with visible action sits well above it.
STILL = 4.0


def lively(segments: List[List[bytes]], floor: float = STILL) -> bool:
    """Whether every segment visibly differs from the next.

    Compared across each cut — the last frame of one segment against
    the first of the next would be the *least* different pair, so the
    first frames of the two are compared instead. A clip whose order
    cannot be seen is not a puzzle, and is skipped rather than dealt.
    """
    if len(segments) < 2:
        return False
    return all(difference(this[0], following[0]) >= floor
               for this, following in zip(segments, segments[1:]))
