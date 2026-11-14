# -*- coding: utf-8 -*-
"""Video Sequence: put the pieces of a shuffled video clip back in order.

A short clip of somebody doing something — a jump, a throw, a stroke
of a paddle — is cut into a few equal stretches of time, and the
stretches are shown side by side in a shuffled order, all playing at
once on a loop. Clicking two swaps them; the puzzle is done when they
read left to right, top to bottom, in the order they happened.

The jigsaw asks where a piece goes in space; this asks where it goes
in time, and the evidence is different in kind. No edge of one piece
meets an edge of another. What there is instead is cause and
consequence: the ball is in the hand before it is in the air, the
diver is on the board before the water, the arm draws back before it
swings. Some of it is physics and some of it is knowing how the
action goes, and none of it is in any single frame.

The score is the jigsaw's: any shuffle has a knowable minimum number
of swaps, and the run reports how close each solution came to it.

The clips are UCF-101, fetched once (see the Readme), and decoded by
the ``ffmpeg`` tool; the task says so if either is missing. A clip
whose pieces look too alike to order — a static shot, a slow pan — is
passed over rather than dealt. As with the jigsaw, every clip in the
library is used before any is used again, across sessions.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import datasets, display, media, state, videoclips
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .jigsaw import minimum_swaps
from .verdict import VerdictLabel, above_the_band

#: How many pieces a clip may be cut into. Two is a coin toss; past
#: nine a piece is under half a second, too short to see what happens
#: in it.
FEWEST, MOST = 3, 9

#: The gap between pieces, in pixels.
SEAM = 6

#: As in the jigsaw: the efficiency a solve needs to add a piece, and
#: the one below which a piece is taken away.
GROW_AT, SHRINK_AT = 0.7, 0.45

#: Clips tried for one puzzle before settling for the liveliest of
#: them. Most UCF-101 clips pass at once; a library of static shots
#: should still deal something rather than nothing.
TRIES = 6


def shuffle(pieces: int, rng: random.Random) -> List[int]:
    """A shuffle of *pieces*, never the solved order.

    ``order[position]`` is the piece shown at *position*.
    """
    order = list(range(pieces))
    while all(piece == position for position, piece in enumerate(order)):
        rng.shuffle(order)
    return order


def best_columns(pieces: int, width: float, height: float,
                 aspect: float) -> int:
    """Columns that make the pieces biggest in a *width* by *height*
    room, for pieces *aspect* wide per unit of height."""
    best, best_size = 1, -1.0
    for columns in range(1, pieces + 1):
        rows = math.ceil(pieces / columns)
        across = (width - SEAM * (columns - 1)) / columns
        down = (height - SEAM * (rows - 1)) / rows
        size = min(across, down * aspect)
        if size > best_size:
            best, best_size = columns, size
    return best


class VideoSequence:
    """Show a clip in shuffled pieces, swap them by clicks, score it."""

    instance: Optional['VideoSequence'] = None

    def __init__(self) -> None:
        if VideoSequence.instance is not None:
            VideoSequence.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.pool = media.MediaPool(datasets.UCF101, self.rng)
        self.shown: List[str] = []
        self.pieces = FEWEST
        self.trial_pieces = FEWEST
        #: ``segments[piece][frame]``: textures, in time order.
        self.segments: List[List[pyglet.image.Texture]] = []
        self.fps = videoclips.FPS
        self.frame = -1
        self.order: List[int] = []
        self.picked: Optional[int] = None
        self.hovered: Optional[int] = None
        self.swaps = 0
        self.par = 0
        self.puzzle = 0
        self.started_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, float, float]] = []
        self.phase = 'ready'
        self.small_library = ''
        self.sprites: List[pyglet.sprite.Sprite] = []
        self.drawn: List[object] = []
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_mouse_motion, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        VideoSequence.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.VIDEO_SEQUENCE)
        self.start_pieces = int(opts['VIDEO_SEQUENCE_PIECES'])
        self.total_puzzles = int(opts['VIDEO_SEQUENCE_PUZZLES'])
        self.adaptive = bool(opts['VIDEO_SEQUENCE_ADAPTIVE'])
        self.mark_placed = bool(opts['VIDEO_SEQUENCE_MARK_PLACED'])
        self.pieces = self.clamped(self.start_pieces)

    @staticmethod
    def clamped(pieces: int) -> int:
        return max(FEWEST, min(MOST, pieces))

    def open_options(self) -> None:
        taskoptions.open_task_options('video_sequence',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.accent = (64, 96, 255, 255)
        self.rightcolor = (46, 160, 67, 255)
        self.batch = pyglet.graphics.Batch()
        self.tile_group = pyglet.graphics.Group(order=0)
        self.mark_group = pyglet.graphics.Group(order=1)
        self.title = pyglet.text.Label(
            _('Video Sequence'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     click two pieces to '
              'swap     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary; restored across a relayout so a
        # resize on the settling frame does not drop the outcome.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _canvas(self) -> Tuple[float, float, float, float]:
        """Left, bottom, width, height of the room the board may use."""
        window = state.window
        top = from_top_edge(96)
        bottom = above_the_band(from_bottom_edge(56))
        return (window.width * 0.04, bottom,
                window.width * 0.92, max(40.0, top - bottom))

    def _tile_rects(self) -> List[Tuple[float, float, float, float]]:
        """Left, bottom, width, height of each position, reading order.

        Positions are laid out in rows, and the last row is centred,
        so reading order is the only order the eye has to follow.
        """
        pieces = self.trial_pieces
        left, bottom, width, height = self._canvas()
        aspect = videoclips.WIDTH / float(videoclips.HEIGHT)
        columns = best_columns(pieces, width, height, aspect)
        rows = math.ceil(pieces / columns)
        across = min((width - SEAM * (columns - 1)) / columns,
                     (height - SEAM * (rows - 1)) / rows * aspect)
        down = across / aspect
        block = rows * down + SEAM * (rows - 1)
        top = bottom + (height + block) / 2
        rects = []
        for position in range(pieces):
            row, column = divmod(position, columns)
            in_row = min(columns, pieces - row * columns)
            span = in_row * across + SEAM * (in_row - 1)
            x = left + (width - span) / 2 + column * (across + SEAM)
            y = top - row * (down + SEAM) - down
            rects.append((x, y, across, down))
        return rects

    def relayout(self) -> None:
        self._build_chrome()

    # --- a puzzle --------------------------------------------------------

    def _reset(self) -> None:
        self.puzzle = 0
        self.results = []
        self.order = []
        self.segments = []
        self.picked = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self.shown = []
        self.pieces = self.clamped(self.start_pieces)
        self._next_puzzle()

    def _seen_file(self) -> str:
        return os.path.join(datasets.local_dir(self.pool.dataset),
                            'seen.txt')

    def _seen(self) -> List[str]:
        try:
            with open(self._seen_file()) as handle:
                return [line.strip() for line in handle if line.strip()]
        except OSError:
            return []

    def _take_fresh(self) -> Optional[str]:
        """A clip not played before, if one is left; the rotation is on
        disk, as the jigsaw's is, and starts over once exhausted."""
        paths = list(self.pool.paths)
        if not paths:
            return None
        seen = set(self._seen())
        unseen = [path for path in paths
                  if os.path.basename(path) not in seen]
        if not unseen:
            try:
                os.remove(self._seen_file())
            except OSError:
                pass
            unseen = [path for path in paths
                      if path not in self.shown] or paths
        path = self.rng.choice(unseen)
        self.shown.append(path)
        try:
            with open(self._seen_file(), 'a') as handle:
                handle.write(os.path.basename(path) + '\n')
        except OSError:
            pass
        return path

    def _deal_clip(self) -> Optional[List[List[bytes]]]:
        """Frames for the next puzzle, cut into this puzzle's pieces.

        Tries a few clips for one whose pieces can be told apart and
        settles for the liveliest otherwise. A clip that will not
        decode is skipped like a still one.
        """
        best: Optional[List[List[bytes]]] = None
        best_score = -1.0
        for _try in range(TRIES):
            path = self._take_fresh()
            if path is None:
                break
            clip = videoclips.decode(path)
            if clip is None:
                continue
            cut = videoclips.cut(clip.frames, self.trial_pieces)
            if not cut:
                continue
            if videoclips.lively(cut):
                return cut
            score = min(videoclips.difference(a[0], b[0])
                        for a, b in zip(cut, cut[1:]))
            if score > best_score:
                best, best_score = cut, score
        return best

    @staticmethod
    def _textures(frames: List[bytes]) -> List[pyglet.image.Texture]:
        width, height = videoclips.WIDTH, videoclips.HEIGHT
        return [pyglet.image.ImageData(width, height, 'RGB', frame,
                                       pitch=-width * 3).get_texture()
                for frame in frames]

    def _next_puzzle(self) -> None:
        if self.puzzle >= self.total_puzzles:
            self._finish()
            return
        self.pool.reload()
        if not self.pool.paths:
            self._stall(_('No video library yet — see the Readme'))
            return
        if not videoclips.have_ffmpeg():
            self._stall(_('Video Sequence needs the ffmpeg program — '
                          'see the Readme'))
            return
        self.trial_pieces = self.pieces
        cut = self._deal_clip()
        if cut is None:
            self._stall(_('None of the downloaded clips would decode'))
            return
        self.puzzle += 1
        stocked = len(self.pool.paths)
        self.small_library = (_('only %d clips downloaded — clips will '
                                'repeat; see the Readme') % stocked
                              if stocked < self.total_puzzles else '')
        self.segments = [self._textures(frames) for frames in cut]
        self.order = shuffle(self.trial_pieces, self.rng)
        self.par = minimum_swaps(self.order)
        self.swaps = 0
        self.picked = None
        self.frame = -1
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'solving'
        self.message = _('Put the pieces in the order they happened')
        self._redraw()

    def _stall(self, message: str) -> None:
        self.phase = 'ready'
        self.message = message
        self._redraw()

    def _pick(self, position: int) -> None:
        """First click marks a piece; the second swaps the two."""
        if self.phase != 'solving' or not 0 <= position < len(self.order):
            return
        if self.picked is None:
            self.picked = position
        elif self.picked == position:
            self.picked = None
        else:
            self.order[self.picked], self.order[position] = \
                self.order[position], self.order[self.picked]
            self.swaps += 1
            self.picked = None
            if all(piece == where for where, piece in enumerate(self.order)):
                self._solved()
        self._redraw()

    def _solved(self) -> None:
        took = self.clock() - self.started_at
        efficiency = self.par / max(self.par, self.swaps)
        self.results.append((self.trial_pieces, efficiency, took))
        if self.adaptive:
            if efficiency >= GROW_AT:
                self.pieces = self.clamped(self.pieces + 1)
            elif efficiency < SHRINK_AT:
                self.pieces = self.clamped(self.pieces - 1)
        self.phase = 'solved'
        self.feedback_until = self.clock() + 1.6
        self.message = (_('In order in %d swaps — the minimum was %d — '
                          'in %.0fs') % (self.swaps, self.par, took))
        self.verdict_shown = (self.swaps <= self.par, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.segments = []
        self.order = []
        tally = self.score()
        self.message = _('%d clips, %d%% swap efficiency, %.0fs each, '
                         'most pieces %d') % (
                             tally['puzzles'], tally['efficiency'],
                             tally['mean_seconds'], tally['most_pieces'])
        self._redraw()

    def score(self) -> Dict[str, float]:
        """Efficiency and time, as the jigsaw reports them."""
        puzzles = len(self.results)
        return {
            'puzzles': puzzles,
            'efficiency': int(round(100 * sum(eff for _p, eff, _t
                                              in self.results) / puzzles)
                              ) if puzzles else 0,
            'mean_seconds': (sum(took for _p, _e, took in self.results)
                             / puzzles) if puzzles else 0.0,
            'most_pieces': max((pieces for pieces, _e, _t in self.results),
                               default=0),
        }

    def _frame_now(self) -> int:
        """The frame every piece shows now. All pieces play in step,
        so no piece's phase says where it started."""
        if not self.segments:
            return 0
        length = len(self.segments[0])
        return int((self.clock() - self.started_at) * self.fps) % length

    def update(self, dt: float) -> None:
        if self.phase == 'solved' and self.clock() >= self.feedback_until:
            self._next_puzzle()
            return
        if self.phase in ('solving', 'solved') and self.sprites:
            frame = self._frame_now()
            if frame != self.frame:
                self.frame = frame
                for position, sprite in enumerate(self.sprites):
                    sprite.image = self.segments[self.order[position]][frame]

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for sprite in self.sprites:
            sprite.delete()
        self.sprites = []
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.phase in ('solving', 'solved') and self.segments:
            frame = self._frame_now()
            self.frame = frame
            for position, rect in enumerate(self._tile_rects()):
                left, bottom, across, _down = rect
                texture = self.segments[self.order[position]][frame]
                sprite = pyglet.sprite.Sprite(
                    texture, x=left, y=bottom, batch=self.batch,
                    group=self.tile_group)
                sprite.scale = across / float(texture.width)
                self.sprites.append(sprite)
                self._mark(position, rect)
        self._update_labels()

    def _mark(self, position: int,
              rect: Tuple[float, float, float, float]) -> None:
        left, bottom, across, down = rect
        color: Optional[Tuple[int, int, int, int]] = None
        thickness = 3.0
        if position == self.picked:
            color, thickness = self.accent, 5.0
        elif self.phase == 'solved':
            color = self.rightcolor
        elif position == self.hovered:
            color = self.accent
        elif self.mark_placed and self.order[position] == position:
            color = self.rightcolor
        if color is not None:
            self.drawn.append(pyglet.shapes.Box(
                left, bottom, across, down, thickness=thickness,
                color=color, batch=self.batch, group=self.mark_group))

    def _update_labels(self) -> None:
        parts = [self.message]
        if self.phase in ('solving', 'solved'):
            parts.append(_('clip %d of %d   swaps %d   minimum %d   '
                           'pieces %d')
                         % (self.puzzle, self.total_puzzles, self.swaps,
                            self.par, self.trial_pieces))
            if self.small_library:
                parts.append(self.small_library)
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if VideoSequence.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_mouse_motion, self.on_draw)
        self._clear_drawn()
        self.segments = []
        VideoSequence.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def _at(self, x: int, y: int) -> Optional[int]:
        for position, (left, bottom, across, down) in \
                enumerate(self._tile_rects()):
            if left <= x <= left + across and bottom <= y <= bottom + down:
                return position
        return None

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'solving':
            found = self._at(x, y)
            if found is not None:
                self._pick(found)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> bool:
        found = self._at(x, y) if self.phase == 'solving' else None
        if found != self.hovered:
            self.hovered = found
            self._redraw()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
