# -*- coding: utf-8 -*-
"""The board and the stimuli drawn on it.

:class:`Field` owns the grid lines and the centre crosshair.
:class:`Visual` is one stimulus: a coloured square, a pictogram, a
letter or a number, positioned in one cell of the board.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import math
from typing import List, Optional, Sequence, Tuple

import pyglet

import bwaccel

from .. import state
from ..gamemode import get_3d_color, get_color
from ..geometry import (from_height_center, height_center, scale_to_height,
                        width_center)
from ..grid import (current_3d_cube_count, current_cell_px, current_grid_3d,
                    current_grid_size, decode_3d_colors, decode_3d_pattern,
                    position_pixel_center)
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
        if current_grid_3d():
            self._draw_3d_cube(n)
            return
        for i in range(1, n):
            t = i / float(n)
            x = int(round(self.x1 + self.size * t))
            y = int(round(self.y1 + self.size * t))
            self.v_lines.append(pyglet.shapes.Line(
                x, self.y1, x, self.y2, color=self.color, batch=state.batch))
            self.v_lines.append(pyglet.shapes.Line(
                self.x1, y, self.x2, y, color=self.color, batch=state.batch))

    def _add_seg(self, p1: Tuple[int, int], p2: Tuple[int, int],
                 color: Sequence[int], width: float = 1.0) -> None:
        self.v_lines.append(pyglet.shapes.Line(
            p1[0], p1[1], p2[0], p2[1],
            thickness=width, color=tuple(color), batch=state.batch))

    def _draw_3d_cube(self, n: int) -> None:
        """Draw the stage shared by the complete multi-cube pattern."""
        room = ((7, 11, 20, 255) if not state.cfg.BLACK_BACKGROUND
                else (0, 0, 0, 255))
        self.v_lines.append(pyglet.shapes.Rectangle(
            self.x1, self.y1, self.size, self.size,
            color=room, batch=state.batch))
        # The double frame groups every cube into one matchable pattern.
        frame = (105, 135, 175, 210)
        inset = max(5, int(self.size * 0.015))
        for offset, width, alpha in ((0, 3.0, 220), (inset, 1.0, 100)):
            color = (*frame[:3], alpha)
            points = [
                (self.x1 + offset, self.y1 + offset),
                (self.x2 - offset, self.y1 + offset),
                (self.x2 - offset, self.y2 - offset),
                (self.x1 + offset, self.y2 - offset),
            ]
            for p1, p2 in zip(points, points[1:] + points[:1]):
                self._add_seg(p1, p2, color, width)

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
        if current_grid_3d():
            if self.crosshair_visible:
                for line in self.v_crosshair:
                    line.delete()
                self.v_crosshair = []
                self.crosshair_visible = False
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
        self.color_id = 1
        self.color: Sequence[int] = (0, 0, 0, 255)
        self.center_x = 0
        self.center_y = 0
        self.age = 0.0
        self.square: object = None
        self.square_size_scaled = 0
        self.poly_3d: List[object] = []
        self.poly_3d_pulse: List[object] = []

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

    def _spawn_3d_voxel(self, position: int) -> None:
        """Render the complete pattern of six-faced perspective cubes."""
        count = current_3d_cube_count()
        faces = decode_3d_pattern(position, count)
        colors = decode_3d_colors(self.color_id, count)
        color_only = position <= 0
        cols = int(math.ceil(math.sqrt(count)))
        rows = int(math.ceil(count / float(cols)))
        gap = max(10, int(state.field.size * 0.035))
        usable = state.field.size - gap * 2
        tile = min((usable - gap * (cols - 1)) / cols,
                   (usable - gap * (rows - 1)) / rows)
        total_w = cols * tile + (cols - 1) * gap
        total_h = rows * tile + (rows - 1) * gap
        start_x = state.field.center_x - total_w / 2
        start_y = state.field.center_y + total_h / 2

        self.poly_3d = []
        self.poly_3d_pulse = []
        for index, face in enumerate(faces):
            row, col = divmod(index, cols)
            # Centre the final incomplete row.
            row_count = min(cols, count - row * cols)
            row_offset = (cols - row_count) * (tile + gap) / 2
            cx = start_x + row_offset + col * (tile + gap) + tile / 2
            cy = start_y - row * (tile + gap) - tile / 2
            self._draw_pattern_cube(
                cx, cy, tile, None if color_only else face, colors[index])
        self.age = 0.0
        pyglet.clock.unschedule(self.animate_3d_pattern)
        if state.cfg.ANIMATE_SQUARES:
            pyglet.clock.schedule_interval(self.animate_3d_pattern, 1 / 60.)

    @staticmethod
    def _inset_polygon(points: Sequence[Tuple[float, float]],
                       amount: float) -> List[Tuple[float, float]]:
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        return [(x + (cx - x) * amount, y + (cy - y) * amount)
                for x, y in points]

    def _draw_pattern_cube(self, cx: float, cy: float, size: float,
                           highlighted: Optional[int],
                           color_id: int = 1) -> None:
        """Draw one six-faced cube card with an unmistakable active face."""
        half = size * 0.43
        inner = size * 0.17
        # A small offset avoids sterile symmetry and strengthens perspective.
        ix, iy = size * 0.025, size * 0.035
        outer = [
            (cx - half, cy + half), (cx + half, cy + half),
            (cx + half, cy - half), (cx - half, cy - half)]
        inside = [
            (cx - inner + ix, cy + inner + iy),
            (cx + inner + ix, cy + inner + iy),
            (cx + inner + ix, cy - inner + iy),
            (cx - inner + ix, cy - inner + iy)]
        face_points = [
            (outer[0], outer[1], inside[1], inside[0]),  # top
            (outer[1], outer[2], inside[2], inside[1]),  # right
            (outer[3], inside[3], inside[2], outer[2]),  # bottom
            (outer[0], inside[0], inside[3], outer[3]),  # left
        ]
        inactive = [
            (31, 47, 72, 255), (24, 38, 61, 255),
            (16, 28, 47, 255), (27, 42, 65, 255)]
        r, g, b = get_3d_color(color_id)[:3]
        # Keep saturated configured colours while adding enough white light
        # to reveal surface detail, especially for pure blue.
        face_lights = (0.18, 0.10, 0.04, 0.12, 0.22, 0.08)
        face_shades = (1.00, 0.82, 0.64, 0.88, 1.06, 0.56)

        def _lit(amount: float, shade: float = 1.0) -> Tuple[int, int, int]:
            lifted = tuple(min(255, int(c + (255 - c) * amount))
                           for c in (r, g, b))
            return tuple(max(0, min(255, int(c * shade))) for c in lifted)

        if highlighted is None:
            lit = _lit(0.16, 1.0)
        else:
            lit = _lit(face_lights[highlighted], face_shades[highlighted])

        # Shadow grounds each cube without obscuring neighbouring tiles.
        self.poly_3d.append(pyglet.shapes.Rectangle(
            cx - half + size * 0.025, cy - half - size * 0.035,
            half * 2, half * 2, color=(0, 0, 0, 95), batch=state.batch))
        for index, points in enumerate(face_points):
            if highlighted is None or index == highlighted:
                face_lit = (_lit(face_lights[index], face_shades[index])
                            if highlighted is None else lit)
                glow = pyglet.shapes.Polygon(
                    *points, color=(*face_lit, 105), batch=state.batch)
                self.poly_3d.append(glow)
                self.poly_3d_pulse.append(glow)
                inset = self._inset_polygon(points, 0.07)
                self.poly_3d.append(pyglet.shapes.Polygon(
                    *inset,
                    color=(*face_lit, 245),
                    batch=state.batch))
                specular = self._inset_polygon(points, 0.16)
                self.poly_3d.append(pyglet.shapes.Polygon(
                    *specular,
                    color=(min(255, face_lit[0] + 12),
                           min(255, face_lit[1] + 12),
                           min(255, face_lit[2] + 12), 70),
                    batch=state.batch))
            else:
                self.poly_3d.append(pyglet.shapes.Polygon(
                    *points, color=inactive[index], batch=state.batch))

        # Back is the recessed square; front is a translucent plane across
        # the opening. Their very different projected sizes remove ambiguity.
        if highlighted is None or highlighted == 5:
            back_lit = (_lit(face_lights[5], face_shades[5])
                        if highlighted is None else lit)
            glow = pyglet.shapes.Polygon(
                *inside, color=(*back_lit, 120), batch=state.batch)
            self.poly_3d.extend([
                glow,
                pyglet.shapes.Polygon(
                    *self._inset_polygon(inside, 0.08),
                    color=(*back_lit, 250), batch=state.batch),
            ])
            self.poly_3d_pulse.append(glow)
        else:
            self.poly_3d.append(pyglet.shapes.Polygon(
                *inside, color=(5, 9, 17, 255), batch=state.batch))

        if highlighted is None or highlighted == 4:
            front_lit = (_lit(face_lights[4], face_shades[4])
                         if highlighted is None else lit)
            glow = pyglet.shapes.Polygon(
                *outer, color=(*front_lit, 40), batch=state.batch)
            glass = pyglet.shapes.Polygon(
                *self._inset_polygon(outer, 0.045),
                color=(*front_lit, 70), batch=state.batch)
            self.poly_3d.extend([glow, glass])
            self.poly_3d_pulse.extend([glow, glass])

        edge = (225, 238, 255, 255)
        inner_edge = (145, 175, 210, 235)
        active_edge = (255, 255, 255, 255)
        for p1, p2 in zip(outer, outer[1:] + outer[:1]):
            self.poly_3d.append(pyglet.shapes.Line(
                *p1, *p2, thickness=max(3.0, size * 0.018),
                color=edge, batch=state.batch))
        for p1, p2 in zip(inside, inside[1:] + inside[:1]):
            self.poly_3d.append(pyglet.shapes.Line(
                *p1, *p2, thickness=max(2.0, size * 0.012),
                color=inner_edge, batch=state.batch))
        for p1, p2 in zip(outer, inside):
            self.poly_3d.append(pyglet.shapes.Line(
                *p1, *p2, thickness=max(1.5, size * 0.008),
                color=inner_edge, batch=state.batch))
        if highlighted is None:
            active_edges = list(zip(outer, outer[1:] + outer[:1]))
        else:
            active = (face_points[highlighted] if highlighted < 4
                      else outer if highlighted == 4 else inside)
            active_edges = list(zip(active, active[1:] + active[:1]))
        for p1, p2 in active_edges:
            line = pyglet.shapes.Line(
                *p1, *p2, thickness=max(4.0, size * 0.024),
                color=active_edge, batch=state.batch)
            self.poly_3d.append(line)
            self.poly_3d_pulse.append(line)

    def animate_3d_pattern(self, dt: float) -> None:
        """Ease the active-face glow in once, without continuous motion."""
        self.age += dt
        duration = 0.24
        progress = min(1.0, self.age / duration)
        # A single overshoot gives a tactile flash while keeping geometry still.
        pulse = 0.72 + 0.28 * math.sin(progress * math.pi)
        for shape in self.poly_3d_pulse:
            shape.opacity = int(255 * pulse)
        if progress >= 1.0:
            for shape in self.poly_3d_pulse:
                shape.opacity = 255
            pyglet.clock.unschedule(self.animate_3d_pattern)


    def spawn(self, position: int = 0, color: int = 1, vis: int = 0,
              number: int = -1, operation: str = 'none',
              variable: int = 0) -> None:
        """Show this stimulus for the current trial."""
        self.position = position
        self.color_id = color
        self.color = get_color(((int(color) - 1) % 8) + 1)
        self.vis = vis
        self.sync_size()
        self.center_x, self.center_y = position_pixel_center(position)
        modalities = self._modalities()

        if self.vis == 0:
            if current_grid_3d():
                self._spawn_3d_voxel(position)
            elif state.cfg.OLD_STYLE_SQUARES:
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
        if self.poly_3d:
            pyglet.clock.unschedule(self.animate_3d_pattern)
            for shape in self.poly_3d:
                try:
                    shape.delete()
                except Exception:
                    pass
            self.poly_3d = []
            self.poly_3d_pulse = []
        if self._is_pictogram_mode():
            self.square.batch = None
            pyglet.clock.unschedule(self.animate_square)
        elif self.vis == 0:
            if current_grid_3d():
                pass  # cleaned up via poly_3d
            elif state.cfg.OLD_STYLE_SQUARES:
                self.square.delete()
            else:
                self.square.batch = None
                pyglet.clock.unschedule(self.animate_square)
        self.visible = False
