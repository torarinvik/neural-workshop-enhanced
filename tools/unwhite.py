#!/usr/bin/env python
"""Lift line art off the white paper it was drawn on.

Every pixel is read as ink laid over white paper --
``pixel = ink * a + 255 * (1 - a)`` -- with the coverage ``a`` taken from
the darkest channel. Undoing that composite recovers the ink's own colour
and how much of it there is, so the artwork looks exactly as before on a
white background and gains a real one on black.

Used to derive ``res/misc/splash-black/logo_blk.png`` from the splash
logo. Re-run it after changing the logo:

    python tools/unwhite.py res/misc/splash/logo.png \\
                            res/misc/splash-black/logo_blk.png

SPDX-License-Identifier: GPL-2.0-or-later
"""
import sys

import pyglet

#: At or above this in every channel the paper is bare, not drawn on.
CLEAR = 250


def unwhite(src, dst):
    """Write *src* to *dst* with its white background turned to alpha."""
    image = pyglet.image.load(src)
    width, height = image.width, image.height
    data = bytearray(image.get_image_data().get_data('RGBA', width * 4))
    inked = 0
    for i in range(0, len(data), 4):
        red, green, blue = data[i], data[i + 1], data[i + 2]
        darkest = min(red, green, blue)
        if darkest >= CLEAR:
            data[i + 3] = 0
            continue
        coverage = (255 - darkest) / 255.0
        for channel in range(3):
            ink = (data[i + channel] - 255.0 * (1.0 - coverage)) / coverage
            data[i + channel] = max(0, min(255, int(round(ink))))
        data[i + 3] = 255 - darkest
        inked += 1
    pyglet.image.ImageData(width, height, 'RGBA', bytes(data)).save(dst)
    print('%s -> %s: %dx%d, %d pixels of ink (%.0f%%)'
          % (src, dst, width, height, inked,
             100.0 * inked / (width * height)))


if __name__ == '__main__':
    unwhite(sys.argv[1], sys.argv[2])
