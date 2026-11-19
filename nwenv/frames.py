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


def scaled_size(width: int, height: int, scale: float) -> Tuple[int, int]:
    """The size a frame of *width* by *height* is captured at under
    *scale*: each side times *scale*, rounded, and never below one."""
    if scale == 1.0:
        return width, height
    return (max(1, int(round(width * scale))),
            max(1, int(round(height * scale))))


def sample_rgba(rgba: bytes, width: int, height: int, out_w: int,
                out_h: int) -> bytes:
    """A smaller frame made by taking one pixel of each block: for output
    pixel (x, y), the source pixel nearest the block's centre.

    Taking pixels rather than averaging them keeps every colour on the
    small frame one that was drawn, so the verdict label's saturated
    green, red and blue stay what the verdict reader looks for.
    """
    if (out_w, out_h) == (width, height):
        return rgba
    row = width * 4
    xs = [min(width - 1, int((x + 0.5) * width / out_w)) * 4
          for x in range(out_w)]
    out = bytearray(out_w * out_h * 4)
    at = 0
    view = memoryview(rgba)
    for y in range(out_h):
        src = min(height - 1, int((y + 0.5) * height / out_h)) * row
        line = view[src:src + row]
        for off in xs:
            out[at:at + 4] = line[off:off + 4]
            at += 4
    return bytes(out)


#: The small framebuffers frames are shrunk into on the GPU, by size.
_SHRINK: dict = {}


def _shrink_on_gpu(width: int, height: int, out_w: int,
                   out_h: int) -> Any:
    """Copy the back buffer into a small framebuffer by nearest-pixel
    sampling, and read that; None where the GPU will not."""
    from pyglet import gl
    try:
        samples = gl.GLint(0)
        gl.glGetIntegerv(gl.GL_SAMPLE_BUFFERS, samples)
        if samples.value:
            return None                  # a multisampled buffer: no blit
        key = (out_w, out_h)
        if key not in _SHRINK:
            fbo, rbo = gl.GLuint(0), gl.GLuint(0)
            gl.glGenFramebuffers(1, fbo)
            gl.glGenRenderbuffers(1, rbo)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, rbo)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA8,
                                     out_w, out_h)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER,
                                         gl.GL_COLOR_ATTACHMENT0,
                                         gl.GL_RENDERBUFFER, rbo)
            ok = (gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
                  == gl.GL_FRAMEBUFFER_COMPLETE)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            if not ok:
                return None
            _SHRINK[key] = (fbo, rbo)
        fbo = _SHRINK[key][0]
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, fbo)
        gl.glBlitFramebuffer(0, 0, width, height, 0, 0, out_w, out_h,
                             gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, fbo)
        buf = (gl.GLubyte * (out_w * out_h * 4))()
        gl.glReadPixels(0, 0, out_w, out_h, gl.GL_RGBA,
                        gl.GL_UNSIGNED_BYTE, buf)
        return bytes(buf)
    except Exception:
        return None
    finally:
        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        except Exception:
            pass


def capture_rgba(window: Any, scale: float = 1.0) -> Tuple[int, int, bytes]:
    """Read the window's framebuffer as top-down RGBA bytes.

    The frame is pixels, not points — see
    :mod:`neural_workshop.geometry`, which owns that distinction.

    Under a *scale* below one the frame is drawn at full size, as ever,
    and captured smaller: one pixel of each block, sampled on the GPU
    where it can be and from a full readback where it cannot (see
    :func:`sample_rgba`). Nothing drawn changes; only what is read back.
    """
    from pyglet.gl import (GL_PACK_ALIGNMENT, GL_RGBA, GL_UNSIGNED_BYTE,
                           GLubyte, glPixelStorei, glReadPixels)
    from neural_workshop.geometry import framebuffer_size
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    width, height = framebuffer_size(window)
    count = width * height * 4
    if count <= 0:
        return width, height, b''
    out_w, out_h = scaled_size(width, height, scale)
    if (out_w, out_h) != (width, height):
        raw = _shrink_on_gpu(width, height, out_w, out_h)
        if raw is not None:
            return out_w, out_h, flip_rgba(raw, out_w, out_h)
    buf = (GLubyte * count)()
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, buf)
    rgba = flip_rgba(bytes(buf), width, height)
    if (out_w, out_h) != (width, height):
        rgba = sample_rgba(rgba, width, height, out_w, out_h)
    return out_w, out_h, rgba


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
