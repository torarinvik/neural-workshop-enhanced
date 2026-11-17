# -*- coding: utf-8 -*-
"""The Artist on screen: the picture on the left, the canvas on the
right, a paint box below.

Drag on the canvas with the tool in hand. With the picker, a click on
the picture (or the canvas) takes the colour there; a right click
anywhere on the picture does the same with any tool. *Check* says how
alike the two are without ending the trial; *Done* ends it.

For the agent boundary, fifteen ports: 0-3 move the cursor a pixel
left, right, down, up and 4-7 an eighth of the canvas; 8 puts the pen
down or lifts it (a shape runs from where it went down to where it is
lifted); 9 the next tool; 10 the next palette colour; 11 takes the
colour of the picture under the cursor; 12 undo; 13 done; 14 the next
width.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional, Tuple

import pyglet
from pyglet import gl
from pyglet.window import key, mouse

from .. import artist as model
from .. import state
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

TOOL_NAMES = {'pencil': _('Pencil'), 'brush': _('Brush'), 'line': _('Line'),
              'box': _('Box'), 'block': _('Block'), 'round': _('Round'),
              'fill': _('Fill'), 'pick': _('Pick')}
BUTTON_LIGHT = (232, 235, 240)
BUTTON_DARK = (46, 50, 58)
CHOSEN = (60, 130, 220)


def _photo(size: int, draw: random.Random) -> Optional[bytes]:
    """A photograph from the libraries on disk, cropped square and
    brought down to size x size; None when there is none."""
    try:
        from .. import media
        for make in (media.jigsaw_pool, media.image_pool):
            pool = make(random.Random(0))
            if not pool.paths:
                continue
            paths = sorted(pool.paths)
            image = pool.item(paths[draw.randrange(len(paths))])
            if image is None:
                continue
            data = image.get_image_data()
            w, h = data.width, data.height
            raw = data.get_data('RGB', w * 3)
            side = min(w, h)
            x0, y0 = (w - side) // 2, (h - side) // 2
            out = bytearray(size * size * 3)
            for j in range(size):
                for i in range(size):
                    # Four samples to a pixel, so fine detail does not
                    # turn to speckle.
                    acc = [0, 0, 0]
                    for dx, dy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75),
                                   (0.75, 0.75)):
                        sx = x0 + int((i + dx) * side / size)
                        sy = y0 + int((j + dy) * side / size)
                        k = (sy * w + sx) * 3
                        acc[0] += raw[k]
                        acc[1] += raw[k + 1]
                        acc[2] += raw[k + 2]
                    k = (j * size + i) * 3
                    out[k:k + 3] = bytes(v // 4 for v in acc)
            return bytes(out)
    except Exception:
        return None
    return None


class Artist(RungTask):
    """Copy the picture with the paint box."""

    instance: Optional['Artist'] = None

    TITLE = 'The Artist'
    TASK_ID = 'the_artist'
    PREFIX = 'ARTIST'
    CATEGORY = 'perception'
    FOOTNOTE = _('drag to draw   Z: undo   K: check   Enter: done   '
                 'Esc: menu')

    def __init__(self) -> None:
        self.puzzle = None
        self.easel: Optional[model.Easel] = None
        self.checked: Optional[float] = None
        self._down = False
        self._canvas_at: Optional[Tuple[float, float, float]] = None
        self._picture_at: Optional[Tuple[float, float, float]] = None
        self._canvas_sprite = None
        super().__init__()
        state.window.push_handlers(self.on_mouse_drag, self.on_mouse_release)

    def close(self) -> None:
        if type(self).instance is self:
            state.window.remove_handlers(self.on_mouse_drag,
                                         self.on_mouse_release)
        super().close()

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.easel = None
        self.checked = None
        self._down = False

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.rung, rng=self.rng, photo=_photo)
        self.easel = model.Easel(self.puzzle)
        self.checked = None
        self._down = False
        self.message = self.puzzle.question
        return True

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY or self.easel is None:
            return
        if self.easel.act(port):
            self.done()
        else:
            self._redraw()

    def done(self) -> None:
        if self.phase != self.PLAY or self.easel is None:
            return
        self.easel.release()
        got = self.easel.alike()
        need = self.puzzle.level.need
        self.checked = got
        self._judge(got >= need, _('%d%% alike; the mark is %d%%')
                    % (max(0, round(got * 100)), round(need * 100)))

    def check(self) -> None:
        if self.phase == self.PLAY and self.easel is not None:
            self.checked = self.easel.alike()
            self._redraw()

    def _set(self, **what) -> None:
        if self.phase != self.PLAY or self.easel is None:
            return
        self.easel.release()
        for name, value in what.items():
            setattr(self.easel, name, value)
        self._redraw()

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol == key.Z:
            self.easel.undo()
            self._redraw()
        elif symbol in (key.RETURN, key.ENTER):
            self.done()
        elif symbol == key.K:
            self.check()
        elif key._1 <= symbol <= key._8:
            self._set(tool=model.TOOLS[symbol - key._1])
        elif symbol in (key.BRACKETLEFT, key.BRACKETRIGHT):
            k = model.WIDTHS.index(self.easel.width)
            k += 1 if symbol == key.BRACKETRIGHT else -1
            self._set(width=model.WIDTHS[max(0, min(len(model.WIDTHS) - 1, k))])

    # --- the mouse -------------------------------------------------------

    def _cell(self, at, x, y, clamp: bool = False):
        if at is None or self.easel is None:
            return None
        left, bottom, side = at
        n = self.easel.size
        cx, cy = int((x - left) * n // side), int((y - bottom) * n // side)
        if clamp:
            return max(0, min(n - 1, cx)), max(0, min(n - 1, cy))
        return (cx, cy) if 0 <= cx < n and 0 <= cy < n else None

    def _click(self, x: float, y: float, button: int) -> None:
        on_picture = self._cell(self._picture_at, x, y)
        if on_picture is not None and (button == mouse.RIGHT
                                       or self.easel.tool == 'pick'):
            self.easel.pick_from_picture(*on_picture)
            self._redraw()
            return
        if button != mouse.LEFT:
            return
        cell = self._cell(self._canvas_at, x, y)
        if cell is not None:
            self.easel.press(*cell)
            self.easel.cx, self.easel.cy = cell
            self._down = self.easel.anchor is not None
            self._redraw()
            return
        super()._click(x, y, button)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers) -> bool:
        if self._down and self.phase == self.PLAY and self.easel is not None:
            cell = self._cell(self._canvas_at, x, y, clamp=True)
            self.easel.drag(*cell)
            self.easel.cx, self.easel.cy = cell
            self._show_canvas()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x, y, button, modifiers) -> bool:
        if self._down and self.easel is not None:
            self._down = False
            if self.phase == self.PLAY:
                self.easel.release(*self._cell(self._canvas_at, x, y,
                                               clamp=True))
                self._redraw()
        return pyglet.event.EVENT_HANDLED

    # --- drawing ---------------------------------------------------------

    def _image(self, pix, size: int):
        data = pyglet.image.ImageData(size, size, 'RGB', bytes(pix),
                                      pitch=size * 3)
        texture = data.get_texture()
        # Pixels are pixels: no smoothing between them.
        gl.glBindTexture(texture.target, texture.id)
        gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MAG_FILTER,
                           gl.GL_NEAREST)
        gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MIN_FILTER,
                           gl.GL_NEAREST)
        return texture

    def _panel(self, pix, size, left, bottom, side):
        sprite = pyglet.sprite.Sprite(self._image(pix, size), left, bottom,
                                      batch=self.batch, group=self.body_group)
        sprite.scale = side / float(size)
        self.drawn.append(sprite)
        self.drawn.append(pyglet.shapes.Box(
            left - 2, bottom - 2, side + 4, side + 4, thickness=2,
            color=self.ink, batch=self.batch, group=self.text_group))
        return sprite

    def _show_canvas(self) -> None:
        """The canvas alone, mid-stroke: nothing else has changed."""
        if self._canvas_sprite is not None and self.easel is not None:
            self._canvas_sprite.image = self._image(self.easel.pix,
                                                    self.easel.size)

    def _button(self, words, x, y, w, h, action, chosen=False,
                colour=None) -> None:
        back = colour or (BUTTON_DARK if self.dark else BUTTON_LIGHT)
        self._box(x, y, w, h, back, CHOSEN if chosen else self.ink,
                  thickness=4 if chosen else 1)
        if words:
            label = self._text(words, x + w / 2, y + h / 2,
                               min(calc_fontsize(11), h * 0.42))
            if label.content_width > w * 0.92:
                label.font_size *= w * 0.92 / label.content_width
        self.hits.append((x, y, w, h, action))

    def _draw(self, left, bottom, width, height) -> None:
        p, e = self.puzzle, self.easel
        row = height * 0.085
        gap = height * 0.02
        side = min(height - 3 * row - 4 * gap, (width - gap * 3) / 2)
        top = bottom + height
        px = left + (width - 2 * side - gap * 3) / 2
        py = top - side - gap
        self._picture_at = (px, py, side)
        self._canvas_at = (px + side + gap * 3, py, side)
        self._panel(p.target, p.size, px, py, side)
        self._canvas_sprite = self._panel(e.pix, e.size, self._canvas_at[0],
                                          py, side)
        if self.phase == self.PLAY:
            # Where the cursor is, for whoever draws without a mouse.
            cell = side / e.size
            self.drawn.append(pyglet.shapes.Box(
                self._canvas_at[0] + e.cx * cell, py + e.cy * cell,
                max(3, cell), max(3, cell), thickness=1,
                color=(255, 60, 60) if e.pen else (120, 120, 130),
                batch=self.batch, group=self.top_group))
        # Tools, widths and the buttons that are not tools.
        y = py - gap - row
        things = [(TOOL_NAMES[t], (lambda t=t: self._set(tool=t)), e.tool == t)
                  for t in model.TOOLS]
        things += [(str(w), (lambda w=w: self._set(width=w)), e.width == w)
                   for w in model.WIDTHS]
        things += [(_('Undo'), self._undo, False),
                   (_('Clear'), self._wipe, False),
                   (_('Check'), self.check, False), (_('Done'), self.done, False)]
        bw = (width - gap * (len(things) - 1) * 0.4) / len(things)
        for k, (words, action, chosen) in enumerate(things):
            self._button(words, left + k * (bw + gap * 0.4), y, bw, row, action,
                         chosen)
        # The palette, with the colour in hand first.
        y -= gap + row
        self._button('', left, y, row * 1.6, row, lambda: None, True,
                     tuple(e.colour))
        n = len(p.palette)
        room = width - row * 1.6 - gap
        sw = min(row, room / n)
        for k, colour in enumerate(p.palette):
            self._button('', left + row * 1.6 + gap + k * sw, y, sw * 0.92, row,
                         (lambda c=colour: self._set(colour=c)),
                         tuple(colour) == tuple(e.colour), tuple(colour))

    def _undo(self) -> None:
        if self.phase == self.PLAY:
            self.easel.undo()
            self._redraw()

    def _wipe(self) -> None:
        if self.phase == self.PLAY:
            self.easel.clear()
            self._redraw()

    def _facts(self) -> str:
        if self.puzzle is None:
            return ''
        said = _('rung %d  %d/%d   %d by %d   the mark is %d%%') % (
            self.rung, self.trial, self.total_trials, self.puzzle.size,
            self.puzzle.size, round(self.puzzle.level.need * 100))
        if self.checked is not None:
            said += _('   now %d%% alike') % max(0, round(self.checked * 100))
        return said
