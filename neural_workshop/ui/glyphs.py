# -*- coding: utf-8 -*-
"""Turning a typeface on this machine into a distorted letter to draw.

The rules live in :mod:`neural_workshop.glyphs` and touch no pixels and
no pyglet. This is the other half: it gets the coverage of a letter out
of a real typeface, hands it to those rules, and hands back something a
task can draw.

Getting the coverage is the only interesting part. pyglet renders a
glyph into a texture atlas, so the letter is already on the card before
anybody asks for it, and reading it back is a ``glReadPixels`` of the
region — about a fifth of a millisecond a letter, which is why this
does not try to be cleverer than that. It does mean a GL context has to
exist, so a caller with no window gets an exception rather than a
picture, and it is why every measurement of the *rules* in the test
suite is written to run without one.

What is expensive is the warp, not the letter: resampling a stamp is
one Python loop iteration per output pixel. At the default 64 pixels
square that is four thousand of them, about eleven milliseconds, and it
scales with the square of the size. So a task that wants stamps at
sixty frames a second should deal them ahead of a trial rather than
during it — :func:`stamp_image` is cached for exactly this reason, but
the cache only helps the second time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, Optional, Tuple

import pyglet

from .. import runtime
from ..glyphs import Coverage, Distortion, deal, face_name, stamp

#: Points to render a letter at before it is warped. Big enough that
#: thinning by a couple of pixels is wear rather than amputation, and
#: small enough that reading it back is not worth caching.
SOURCE_SIZE: int = 72

#: Side of a dealt stamp, in pixels.
STAMP_SIZE: int = 64

#: Families whose files have been handed to pyglet already.
_registered: Dict[str, str] = {}

#: Dealt stamps, keyed by everything that decides one.
_stamps: Dict[Tuple, pyglet.image.ImageData] = {}

#: Above this many, the oldest are dropped. A stamp is 16 KB at the
#: default size, so this is a few megabytes rather than a policy.
_CACHE_LIMIT = 512


def register(path: str) -> Optional[str]:
    """Hand a font file to pyglet; returns the family name it registered.

    Returns None for a file pyglet or the ``name`` table would not take,
    rather than raising: a caller sweeping a system font directory will
    meet a few of those on any machine and should skip them, not stop.
    """
    named = face_name(path)
    if named is None:
        return None
    family = named[0]
    if family in _registered:
        return family
    try:
        pyglet.font.add_file(path)
    except Exception as exc:            # pragma: no cover - platform dependent
        runtime.debug_msg(exc)
        return None
    if not pyglet.font.have_font(family):
        return None
    _registered[family] = path
    return family


def coverage(family: str, letter: str, size: int = SOURCE_SIZE) -> Coverage:
    """The alpha of one letter in one typeface, top row first.

    Only the alpha: a glyph's colour channels are the text colour, and
    the colour a task wants is decided later, so the shape is all that
    is carried forward.
    """
    font = pyglet.font.load(family, size)
    glyphs, _positions = font.get_glyphs(letter)
    if not glyphs:
        return Coverage(1, 1)
    glyph = glyphs[0]
    data = glyph.get_image_data()
    width, height = data.width, data.height
    if width < 1 or height < 1:
        return Coverage(1, 1)
    raw = data.get_data('RGBA', width * 4)
    alpha = bytearray(width * height)
    for row in range(height):
        # pyglet's rows run bottom-up; a Coverage's run top-down.
        base = (height - 1 - row) * width * 4
        out = row * width
        for col in range(width):
            alpha[out + col] = raw[base + col * 4 + 3]
    return Coverage(width, height, alpha)


def image_of(cov: Coverage,
             ink: Tuple[int, int, int] = (0, 0, 0),
             paper: Optional[Tuple[int, int, int]] = None
             ) -> pyglet.image.ImageData:
    """A coverage as something drawable.

    With no *paper* the result is *ink* carried by the coverage's own
    alpha, which is what a task wants when the letter goes on top of
    whatever is already there. With *paper* the result is opaque and
    the coverage has been mixed into it, which is what a task wants
    when the letter is a card of its own — and the difference matters
    to a low-contrast deal, because "faint against this background" is
    only a well-defined thing to ask for once there is a background.
    """
    width, height = cov.width, cov.height
    out = bytearray(width * height * 4)
    red, green, blue = ink
    for row in range(height):
        # Back to bottom-up on the way out.
        source = (height - 1 - row) * width
        base = row * width * 4
        for col in range(width):
            value = cov.alpha[source + col]
            at = base + col * 4
            if paper is None:
                out[at] = red
                out[at + 1] = green
                out[at + 2] = blue
                out[at + 3] = value
            else:
                share = value / 255.0
                out[at] = int(paper[0] + (red - paper[0]) * share)
                out[at + 1] = int(paper[1] + (green - paper[1]) * share)
                out[at + 2] = int(paper[2] + (blue - paper[2]) * share)
                out[at + 3] = 255
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(out))


def dealt(family: str, letter: str, rung: int, seed: int,
          size: int = STAMP_SIZE) -> Coverage:
    """One letter, one typeface, one appearance dealt from *rung*.

    The same four arguments always give the same picture: the deal and
    the speckling run off one seeded generator and nothing else is
    random. That is what lets a trial be replayed, and what lets a
    held-out font test be repeated exactly.
    """
    rng = random.Random(seed)
    distortion: Distortion = deal(rung, rng)
    return stamp(coverage(family, letter), distortion, size, rng)


def stamp_image(family: str, letter: str, rung: int, seed: int,
                size: int = STAMP_SIZE,
                ink: Tuple[int, int, int] = (0, 0, 0),
                paper: Optional[Tuple[int, int, int]] = None
                ) -> pyglet.image.ImageData:
    """:func:`dealt`, drawable, and remembered.

    Cached because the cost is the resampling loop rather than the
    typeface, and because a task that shows the same letter twice in a
    trial — a word with two of one letter, a choice repeated among
    distractors — would otherwise pay for it twice.
    """
    key = (family, letter, int(rung), int(seed), int(size), ink, paper)
    found = _stamps.get(key)
    if found is not None:
        return found
    made = image_of(dealt(family, letter, rung, seed, size), ink, paper)
    if len(_stamps) >= _CACHE_LIMIT:
        _stamps.clear()
    _stamps[key] = made
    return made


def forget() -> None:
    """Drop the stamp cache. For tests and for a change of theme."""
    _stamps.clear()


__all__ = ['SOURCE_SIZE', 'STAMP_SIZE', 'coverage', 'dealt', 'forget',
           'image_of', 'register', 'stamp_image']
