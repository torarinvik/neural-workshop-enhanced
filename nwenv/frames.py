# -*- coding: utf-8 -*-
"""Capturing what is on screen.

A "significant frame" is the picture at the moment the game's visual
phase changed. The capture has to read the *backbuffer* before the flip,
otherwise the learner sees the previous frame.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Tuple


def now_ns() -> int:
    """Monotonic timestamp, in nanoseconds."""
    return time.monotonic_ns()


def flip_rgba(raw: bytes, width: int, height: int) -> bytes:
    """Turn a bottom-up GL readback into a top-down image.

    One join over the rows taken back to front, rather than a loop
    assigning into a bytearray. Measured on a real 1824x1368 readback,
    best of five runs of twenty-five, that is 1.19ms against 1.69ms
    for byte-identical output — worth having because this is the last
    pure-Python pass over a whole frame in the capture path, the
    readback and the SHA-256 either side of it being native already.

    A buffer that is not exactly the size the geometry implies keeps
    the older, slower form. Such a readback is a bug somewhere else
    and this is not the place to start behaving differently about it.
    """
    row = width * 4
    if row <= 0 or height <= 0:
        return raw
    if len(raw) == row * height:
        return b''.join(raw[at:at + row]
                        for at in range(len(raw) - row, -1, -row))
    out = bytearray(len(raw))
    for y in range(height):
        src = (height - 1 - y) * row
        out[y * row:y * row + row] = raw[src:src + row]
    return bytes(out)


def capture_rgba(window: Any) -> Tuple[int, int, bytes]:
    """Read the window's framebuffer as top-down RGBA bytes.

    The frame is pixels, not points — see
    :mod:`neural_workshop.geometry`, which owns that distinction.
    """
    from pyglet.gl import (GL_PACK_ALIGNMENT, GL_RGBA, GL_UNSIGNED_BYTE,
                           GLubyte, glPixelStorei, glReadPixels)
    from neural_workshop.geometry import framebuffer_size
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    width, height = framebuffer_size(window)
    count = width * height * 4
    if count <= 0:
        return width, height, b''
    buf = (GLubyte * count)()
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, buf)
    return width, height, flip_rgba(bytes(buf), width, height)


def render_significant_frame() -> Tuple[int, int, bytes]:
    """Draw, read the backbuffer, then flip. Capture must precede flip."""
    import brainworkshop as bw
    window = bw.window
    window.switch_to()
    window.dispatch_events()
    bw.on_draw()
    captured = capture_rgba(window)
    window.flip()
    return captured


def digest_rgba(rgba: bytes) -> str:
    """SHA-256 of a frame, which is how frames are named in evidence."""
    return hashlib.sha256(rgba or b'').hexdigest()
