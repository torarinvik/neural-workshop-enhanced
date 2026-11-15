# -*- coding: utf-8 -*-
"""Finishing touches shared by the task screens.

Rounded cards that sit on a soft shadow, a stage to put a task on,
vertical gradients, buttons with a lip, coins. Everything here only
draws: it adds pyglet shapes to a batch and to the caller's list of
drawn things, so the caller deletes them with the rest on a redraw.

The shadow, card and inset groups order below pyglet's default group,
so a screen that draws its content without groups still lands on top.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, NamedTuple, Optional, Sequence, Tuple

import pyglet
from pyglet.graphics import Group

Colour = Tuple[int, ...]

SHADOW = Group(order=-30)
STAGE = Group(order=-25)
CARD = Group(order=-20)
INSET = Group(order=-15)


class Palette(NamedTuple):
    stage: Colour
    card: Colour
    edge: Colour
    shadow: Colour
    ink: Colour
    muted: Colour
    accent: Colour
    good: Colour
    bad: Colour
    gold: Colour
    warm: Colour


LIGHT = Palette(stage=(236, 240, 246), card=(255, 255, 255),
                edge=(210, 216, 228), shadow=(24, 34, 60, 34),
                ink=(30, 36, 52), muted=(112, 120, 138),
                accent=(66, 112, 232), good=(36, 160, 96),
                bad=(222, 72, 62), gold=(244, 184, 44),
                warm=(250, 246, 236))
DARK = Palette(stage=(24, 27, 36), card=(38, 43, 56), edge=(66, 74, 92),
               shadow=(0, 0, 0, 110), ink=(232, 236, 244),
               muted=(150, 158, 176), accent=(110, 150, 255),
               good=(70, 200, 130), bad=(255, 110, 100),
               gold=(250, 196, 70), warm=(46, 44, 40))


def palette(dark: bool) -> Palette:
    return DARK if dark else LIGHT


def mix(a: Sequence[int], b: Sequence[int], t: float) -> Colour:
    """*a* moved a fraction *t* of the way to *b* (RGB)."""
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a[:3], b[:3]))


def lighter(c: Sequence[int], t: float = 0.25) -> Colour:
    return mix(c, (255, 255, 255), t)


def darker(c: Sequence[int], t: float = 0.25) -> Colour:
    return mix(c, (0, 0, 0), t)


def _rounded(x, y, w, h, r, colour, batch, group):
    w, h = max(1.0, w), max(1.0, h)
    r = max(0.0, min(r, w / 2.0 - 0.01, h / 2.0 - 0.01))
    if r < 1.0:
        return pyglet.shapes.Rectangle(x, y, w, h, color=colour,
                                       batch=batch, group=group)
    return pyglet.shapes.RoundedRectangle(x, y, w, h, r, color=colour,
                                          batch=batch, group=group)


def shadow(drawn: List, batch, x, y, w, h, radius=12.0, lift=4.0,
           colour: Colour = LIGHT.shadow, group: Group = SHADOW) -> None:
    """A soft shadow under a card at x, y, w, h: three widening layers,
    dropped by *lift*."""
    alpha = colour[3] if len(colour) > 3 else 40
    for spread, share in ((0.0, 0.5), (lift * 0.5, 0.3), (lift, 0.2)):
        drawn.append(_rounded(x - spread, y - lift - spread,
                              w + 2 * spread, h + 2 * spread,
                              radius + spread,
                              tuple(colour[:3]) + (int(alpha * share),),
                              batch, group))


def card(drawn: List, batch, x, y, w, h, fill: Colour, radius=12.0,
         edge: Optional[Colour] = None, lift=4.0, shade: Optional[Colour]
         = LIGHT.shadow, group: Group = CARD) -> None:
    """A rounded card on a soft shadow, with an optional hairline edge."""
    if shade is not None and lift > 0:
        shadow(drawn, batch, x, y, w, h, radius, lift, shade)
    if edge is not None:
        drawn.append(_rounded(x - 1, y - 1, w + 2, h + 2, radius + 1, edge,
                              batch, group))
        group = Group(order=group.order + 1)
    drawn.append(_rounded(x, y, w, h, radius, fill, batch, group))


def rounded(drawn: List, batch, x, y, w, h, fill: Colour, radius=8.0,
            group: Optional[Group] = None) -> None:
    """A plain rounded rectangle, no shadow."""
    drawn.append(_rounded(x, y, w, h, radius, fill, batch, group))


def gradient(drawn: List, batch, x, y, w, h, bottom: Colour, top: Colour,
             bands: int = 24, group: Group = STAGE) -> None:
    """A vertical gradient from *bottom* to *top*, in bands."""
    step = h / float(bands)
    for k in range(bands):
        drawn.append(pyglet.shapes.Rectangle(
            x, y + k * step, w, step + 1,
            color=mix(bottom, top, (k + 0.5) / bands), batch=batch,
            group=group))


def stage(drawn: List, batch, x, y, w, h, pal: Palette, radius=16.0,
          tint: Optional[Colour] = None) -> None:
    """The panel a task's play sits on: a large soft card."""
    fill = tint if tint is not None else pal.stage
    card(drawn, batch, x, y, w, h, fill, radius=radius, lift=6,
         shade=pal.shadow, group=STAGE)


def button(drawn: List, batch, x, y, w, h, fill: Colour, radius=10.0,
           pressed: bool = False, group: Group = CARD,
           shade: Optional[Colour] = LIGHT.shadow) -> None:
    """A raised button: a darker lip under a face, sunk when pressed."""
    lip = max(2.0, min(5.0, h * 0.08))
    if shade is not None and not pressed:
        shadow(drawn, batch, x, y, w, h, radius, lift=3, colour=shade)
    drawn.append(_rounded(x, y, w, h, radius, darker(fill, 0.18), batch,
                          group))
    top = Group(order=group.order + 1)
    sink = lip if pressed else 0.0
    drawn.append(_rounded(x, y + lip - sink * 0.6, w, h - lip, radius, fill,
                          batch, top))


def coin(drawn: List, batch, x, y, r, group: Optional[Group] = None,
         colour: Colour = LIGHT.gold) -> None:
    """A gold coin: rim, face and a glint."""
    g = group or Group(order=0)
    drawn.append(pyglet.shapes.Circle(x, y - r * 0.12, r,
                                      color=darker(colour, 0.35),
                                      batch=batch, group=g))
    face = Group(order=g.order + 1)
    drawn.append(pyglet.shapes.Circle(x, y, r, color=colour, batch=batch,
                                      group=face))
    inner = Group(order=g.order + 2)
    drawn.append(pyglet.shapes.Circle(x, y, r * 0.72,
                                      color=lighter(colour, 0.18),
                                      batch=batch, group=inner))
    drawn.append(pyglet.shapes.Circle(x - r * 0.3, y + r * 0.32, r * 0.18,
                                      color=(255, 255, 255, 170),
                                      batch=batch,
                                      group=Group(order=g.order + 3)))


def disc(drawn: List, batch, x, y, r, colour: Colour,
         group: Optional[Group] = None, glint: bool = True,
         ring: Optional[Colour] = None) -> None:
    """A filled circle with a darker rim and a glint: a bead, a lamp."""
    g = group or Group(order=0)
    drawn.append(pyglet.shapes.Circle(x, y, r, color=ring or darker(colour,
                                                                    0.3),
                                      batch=batch, group=g))
    drawn.append(pyglet.shapes.Circle(x, y + r * 0.04, r * 0.84,
                                      color=colour, batch=batch,
                                      group=Group(order=g.order + 1)))
    if glint:
        drawn.append(pyglet.shapes.Circle(
            x - r * 0.3, y + r * 0.3, r * 0.22, color=(255, 255, 255, 140),
            batch=batch, group=Group(order=g.order + 2)))


def glow(drawn: List, batch, x, y, r, colour: Colour, strength=90,
         group: Group = INSET) -> None:
    """A soft halo: rings of falling alpha."""
    for k, share in enumerate((0.15, 0.25, 0.35, 0.5)):
        rr = r * (1.0 - k * 0.2)
        drawn.append(pyglet.shapes.Circle(
            x, y, rr, color=tuple(colour[:3]) + (int(strength * share),),
            batch=batch, group=group))


#: Muted hues for things that need telling apart but must not shout:
#: machines, cards, lanes.
HUES = ((86, 118, 196), (52, 150, 140), (204, 122, 74), (140, 102, 188),
        (84, 150, 86), (196, 92, 128), (104, 124, 148), (184, 150, 52))


class Machine(NamedTuple):
    """Where a machine card put its parts: header and screen rects."""
    header: Tuple[float, float, float, float]
    screen: Tuple[float, float, float, float]


def machine(drawn: List, batch, x, y, w, h, pal: Palette, hue: Colour,
            lit: bool = False, lit_colour: Optional[Colour] = None,
            header_share: float = 0.18, screen_share: float = 0.6
            ) -> Machine:
    """A card drawn as a little machine: a coloured header across the
    top, a recessed screen under it and a plain body below.

    *lit* draws a thick ring round it in *lit_colour* (the accent by
    default), for the one last chosen.
    """
    radius = min(w, h) * 0.08
    body = mix(pal.card, hue, 0.08)
    if lit:
        ring = lit_colour or pal.accent
        pad = max(3.0, min(w, h) * 0.025)
        drawn.append(_rounded(x - pad, y - pad, w + 2 * pad, h + 2 * pad,
                              radius + pad, ring, batch, SHADOW))
    card(drawn, batch, x, y, w, h, body, radius=radius, edge=pal.edge,
         shade=None if lit else pal.shadow)
    hh = h * header_share
    hy = y + h - hh
    drawn.append(_rounded(x, hy, w, hh, radius, hue, batch, INSET))
    # Square off the header's lower corners.
    drawn.append(pyglet.shapes.Rectangle(x, hy, w, hh * 0.5, color=hue,
                                         batch=batch, group=INSET))
    margin = w * 0.08
    sh = h * screen_share
    sy = hy - margin * 0.7 - sh
    screen = mix(pal.stage, (0, 0, 0), 0.06) if pal is LIGHT \
        else darker(pal.card, 0.3)
    drawn.append(_rounded(x + margin, sy, w - 2 * margin, sh,
                          radius * 0.6, screen, batch, INSET))
    return Machine((x, hy, w, hh), (x + margin, sy, w - 2 * margin, sh))
