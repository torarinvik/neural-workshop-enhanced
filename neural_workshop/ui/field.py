# -*- coding: utf-8 -*-
"""The board and the stimuli drawn on it.

:class:`Field` owns the grid lines and the centre crosshair.
:class:`Visual` is one stimulus: a coloured square, a pictogram, a
letter or a number, positioned in one cell of the board.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

import pyglet

import bwaccel

from .. import state
from ..gamemode import get_color
from ..geometry import (from_height_center, height_center, scale_to_height,
                        width_center)
from ..grid import current_cell_px, current_grid_size, position_pixel_center
from ..paths import load_pyglet_image


class Field:
    """The square area the stimuli appear in."""

    def __init__(self) -> None:
        cfg = state.cfg
        self.size = int(state.window.height
                        * (0.85 if cfg.FIELD_EXPAND else 0.625))
        self.color: Tuple[int, int, int] = ((64, 64, 64) if cfg.BLACK_BACKGROUND
                                            else (192, 192, 192))
        self.color4 = self.color * 4
        self.color8 = self.color * 8

        self.center_x = width_center()
        self.center_y = (height_center() if cfg.FIELD_EXPAND
                         else from_height_center(20))
        self.x1 = int(self.center_x - self.size / 2)
        self.x2 = int(self.center_x + self.size / 2)
        self.x3 = int(self.center_x - self.size / 6)
        self.x4 = int(self.center_x + self.size / 6)
        self.y1 = int(self.center_y - self.size / 2)
        self.y2 = int(self.center_y + self.size / 2)
        self.y3 = int(self.center_y - self.size / 6)
        self.y4 = int(self.center_y + self.size / 6)

        self.v_lines: List[pyglet.shapes.Line] = []
        self.v_crosshair: List[pyglet.shapes.Line] = []
        self.crosshair_visible = False
        self.draw_grid()
        self.crosshair_update()

    # --- grid ------------------------------------------------------------

    def clear_grid(self) -> None:
        for line in self.v_lines:
            try:
                line.delete()
            except Exception:
                pass
        self.v_lines = []

    def draw_grid(self) -> None:
        """Rebuild the grid lines for the current board size."""
        self.clear_grid()
        if not state.cfg.GRIDLINES:
            return
        n = current_grid_size()
        for i in range(1, n):
            t = i / float(n)
            x = int(round(self.x1 + self.size * t))
            y = int(round(self.y1 + self.size * t))
            self.v_lines.append(pyglet.shapes.Line(
                x, self.y1, x, self.y2, color=self.color, batch=state.batch))
            self.v_lines.append(pyglet.shapes.Line(
                self.x1, y, self.x2, y, color=self.color, batch=state.batch))

    def rebuild_grid(self) -> None:
        self.draw_grid()
        self.crosshair_update()

    # --- crosshair -------------------------------------------------------

    def _crosshair_wanted(self) -> bool:
        return (not state.mode.paused
                and 'position1' in state.mode.modalities[state.mode.mode]
                and not state.cfg.VARIABLE_NBACK)

    def crosshair_update(self) -> None:
        """Show or hide the small cross marking the centre of the field."""
        if not state.cfg.CROSSHAIRS:
            return
        if self._crosshair_wanted():
            if self.crosshair_visible:
                return
            arm = scale_to_height(8)
            self.v_crosshair = [
                pyglet.shapes.Line(self.center_x - arm, self.center_y,
                                   self.center_x + arm, self.center_y,
                                   color=self.color, batch=state.batch),
                pyglet.shapes.Line(self.center_x, self.center_y - arm,
                                   self.center_x, self.center_y + arm,
                                   color=self.color, batch=state.batch)]
            self.crosshair_visible = True
        elif self.crosshair_visible:
            for line in self.v_crosshair:
                line.delete()
            self.v_crosshair = []
            self.crosshair_visible = False


class Visual:
    """One visual stimulus: square, pictogram, letter or number."""

    def __init__(self) -> None:
        from .. import resources
        self.visible = False
        #: Sound-set keys chosen for this session; set by ``new_session``.
        #: The combination (visvis) modes render them as on-screen letters.
        self.letters: List[str] = []
        self.letters2: List[str] = []
        self.position = 0
        self.vis = 0
        self.color: Sequence[int] = (0, 0, 0, 255)
        self.center_x = 0
        self.center_y = 0
        self.age = 0.0
        self.square: object = None
        self.square_size_scaled = 0

        font_size = state.field.size // 6
        self.label = pyglet.text.Label(
            '', font_size=font_size, weight='bold',
            anchor_x='center', anchor_y='center', batch=state.batch)
        self.variable_label = pyglet.text.Label(
            '', font_size=font_size, weight='bold',
            anchor_x='center', anchor_y='center', batch=state.batch)

        self.spr_square = [
            pyglet.sprite.Sprite(load_pyglet_image(path))
            for path in resources.resourcepaths['misc']['colored-squares']]
        self.spr_square_size = self.spr_square[0].width

        cfg = state.cfg
        self.size_factor = (0.9375 if (cfg.ANIMATE_SQUARES
                                       or cfg.OLD_STYLE_SQUARES) else 1.0)
        self.size = 0
        self.sync_size()
        self.image_set_index: Optional[str] = None
        self.image_set: List[pyglet.sprite.Sprite] = []
        self.image_set_size = 0
        self.image_indices: List[int] = []
        self.images: List[pyglet.sprite.Sprite] = []
        self.load_set()

    def sync_size(self) -> None:
        """Fit the square or icon to one cell of the current board."""
        cell = current_cell_px()
        self.size = max(4, int(cell * self.size_factor))
        cell_font = max(8, int(cell * 0.45))
        self.label.font_size = cell_font
        self.variable_label.font_size = cell_font

    # --- image sets ------------------------------------------------------

    def load_set(self, index: Optional[object] = None) -> None:
        """Load a sprite set by name, by config index, or at random."""
        from .. import resources
        if isinstance(index, int):
            index = state.cfg.IMAGE_SETS[index]
        if index is None:
            index = random.choice(state.cfg.IMAGE_SETS)
        if index == self.image_set_index:
            return
        self.image_set_index = index
        self.image_set = [
            pyglet.sprite.Sprite(load_pyglet_image(path))
            for path in resources.resourcepaths['sprites'][index]]
        self.image_set_size = self.image_set[0].width

    def choose_random_images(self, number: int) -> None:
        self.image_indices = random.sample(range(len(self.image_set)), number)
        self.images = random.sample(self.image_set, number)

    def choose_indicated_images(self, indices: Sequence[int]) -> None:
        self.image_indices = list(indices)
        self.images = [self.image_set[i] for i in indices]

    # --- drawing ---------------------------------------------------------

    def _modalities(self) -> Sequence[str]:
        return state.mode.modalities[state.mode.mode]

    def _is_pictogram_mode(self) -> bool:
        modalities = self._modalities()
        return ('image' in modalities or 'vis1' in modalities
                or (state.mode.flags[state.mode.mode]['multi'] > 1
                    and state.cfg.MULTI_MODE == 'image'))

    def _place_sprite(self, sprite: pyglet.sprite.Sprite,
                      source_size: int) -> None:
        sprite.opacity = 255
        sprite.x = self.center_x - self.size // 2
        sprite.y = self.center_y - self.size // 2
        sprite.scale = 1.0 * self.size / source_size
        self.square = sprite
        self.square_size_scaled = sprite.width
        sprite.batch = state.batch
        self.age = 0.0
        pyglet.clock.schedule_interval(self.animate_square, 1 / 60.)

    def _spawn_old_style_square(self) -> None:
        """The flat, sharp- or round-cornered square of the Jaeggi layout."""
        lx = self.center_x - self.size // 2 + 2
        rx = self.center_x + self.size // 2 - 2
        by = self.center_y - self.size // 2 + 2
        ty = self.center_y + self.size // 2 - 2
        if state.cfg.OLD_STYLE_SHARP_CORNERS:
            points = [(lx, by), (rx, by), (rx, ty), (lx, ty)]
        else:
            xy = bwaccel.rounded_rect_vertices(lx, rx, by, ty, self.size // 5)
            points = list(zip(xy[0::2], xy[1::2]))
        self.square = pyglet.shapes.Polygon(*points, color=tuple(self.color),
                                            batch=state.batch)

    def spawn(self, position: int = 0, color: int = 1, vis: int = 0,
              number: int = -1, operation: str = 'none',
              variable: int = 0) -> None:
        """Show this stimulus for the current trial."""
        self.position = position
        self.color = get_color(color)
        self.vis = vis
        self.sync_size()
        self.center_x, self.center_y = position_pixel_center(position)
        modalities = self._modalities()

        if self.vis == 0:
            if state.cfg.OLD_STYLE_SQUARES:
                self._spawn_old_style_square()
            else:
                self._place_sprite(self.spr_square[color - 1],
                                   self.spr_square_size)
        elif 'arithmetic' in modalities:
            self.label.text = str(number)
            self.label.x = self.center_x
            self.label.y = self.center_y + 4
            self.label.color = self.color
        elif 'visvis' in modalities:
            self.label.text = self.letters[vis - 1].upper()
            self.label.x = self.center_x
            self.label.y = self.center_y + 4
            self.label.color = self.color
        elif self._is_pictogram_mode():
            sprite = self.images[vis - 1]
            sprite.color = tuple(self.color[:3])
            self._place_sprite(sprite, self.image_set_size)

        if variable > 0:
            self.variable_label.text = str(variable)
            self.variable_label.x = state.field.center_x
            if 'position1' not in modalities:
                self.variable_label.y = (state.field.center_y
                                         - int(current_cell_px()) + 4)
            else:
                self.variable_label.y = state.field.center_y + 4
            self.variable_label.color = self.color

        self.visible = True

    def animate_square(self, dt: float) -> None:
        """Grow and fade the sprite over the stimulus phase."""
        self.age += dt
        if state.mode.paused or not state.cfg.ANIMATE_SQUARES:
            return

        fade_begin_time = 0.4
        fade_end_time = 0.5
        fade_end_transparency = 1.0  # 1 = fully transparent at the end

        self.square.scale += dt / 8
        offset = (self.square.width - self.square_size_scaled) // 2
        self.square.x = self.center_x - self.size // 2 - offset
        self.square.y = self.center_y - self.size // 2 - offset

        if self.age > fade_begin_time:
            factor = 1.0 - fade_end_transparency * (
                (self.age - fade_begin_time) / (fade_end_time - fade_begin_time))
            self.square.opacity = int(255 * min(1.0, max(0.0, factor)))

    def hide(self) -> None:
        """Remove this stimulus from the screen."""
        if not self.visible:
            return
        self.label.text = ''
        self.variable_label.text = ''
        if self._is_pictogram_mode():
            self.square.batch = None
            pyglet.clock.unschedule(self.animate_square)
        elif self.vis == 0:
            if state.cfg.OLD_STYLE_SQUARES:
                self.square.delete()
            else:
                self.square.batch = None
                pyglet.clock.unschedule(self.animate_square)
        self.visible = False
