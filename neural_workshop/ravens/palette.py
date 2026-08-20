# -*- coding: utf-8 -*-
"""The fills a figure can be drawn in.

Carried over unchanged from the previous engine, because this part of
it was chosen by measurement rather than by taste and the measurements
still hold: see :data:`COLOUR_FILLS` for what was measured and why.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Fill:
    """A figure's interior: a colour laid over the paper."""

    name: str
    color: Tuple[int, int, int, int]


#: The greys, lightest first. Translucent, so a figure drawn over
#: another still lets it show through.
WHITE = Fill('white', (255, 255, 255, 0))
GREY_LIGHT = Fill('grey-light', (191, 191, 191, 102))
GREY_MID = Fill('grey-mid', (102, 102, 102, 128))
GREY_DARK = Fill('grey-dark', (26, 26, 26, 153))
BLACK = Fill('black', (0, 0, 0, 191))

GREY_FILLS: Tuple[Fill, ...] = (WHITE, GREY_LIGHT, GREY_MID, GREY_DARK, BLACK)

#: Colours, at the opacity of the darkest grey.
COLOUR_ALPHA = 200

YELLOW = Fill('yellow', (240, 228, 66, COLOUR_ALPHA))
SKY = Fill('sky', (86, 180, 233, COLOUR_ALPHA))
VERMILION = Fill('vermilion', (213, 94, 0, COLOUR_ALPHA))
BLUE = Fill('blue', (0, 114, 178, COLOUR_ALPHA))

#: The colours, lightest first.
#:
#: Four of the Okabe-Ito set, which exists to stay legible to
#: colour-blind eyes, chosen from it by measurement: every pair was
#: simulated for each kind of dichromacy and compared in CIELAB, and
#: this is the four leaving the largest worst case. That worst case is
#: a little over twice the grey ramp's own.
#:
#: The order is by lightness, and strictly: 100, 91, 76, 63, 57. So the
#: sequence is a lightness ramp as well as a colour one, and a player
#: who cannot separate the hues can still follow a colour rule by how
#: dark each step is.
COLOUR_FILLS: Tuple[Fill, ...] = (WHITE, YELLOW, SKY, VERMILION, BLUE)


@dataclass(frozen=True)
class Palette:
    """A set of fills, and what to call the thing they vary."""

    name: str
    fills: Tuple[Fill, ...]
    #: What a rule about these is called when a puzzle is explained.
    noun: str


GREYS = Palette('greys', GREY_FILLS, 'shade')
COLOURS = Palette('colours', COLOUR_FILLS, 'colour')

#: Both, for a run that wants colour in the mix.
PALETTES: Tuple[Palette, ...] = (GREYS, COLOURS)
