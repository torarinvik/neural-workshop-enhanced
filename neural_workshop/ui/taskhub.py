# -*- coding: utf-8 -*-
"""The workshop task hub: categories of games, then a task list.

The n-back workshop stays one of the working-memory tasks. Other games
live in their own overlays and return here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from . import cursor
from ..i18n import _

#: Category id → display name, in tab order.
CATEGORIES: Sequence[Tuple[str, str]] = (
    ('working_memory', _('Working memory')),
    ('long_term_memory', _('Long-term memory')),
    ('attention', _('Attention')),
    ('perception', _('Perception')),
    ('reasoning', _('Reasoning')),
    ('planning', _('Planning')),
)

#: Category id → list of (task id, label).
TASKS: Dict[str, List[Tuple[str, str]]] = {
    'working_memory': [
        ('nback', _('N-Back')),
        ('monkey_ladder', _('Monkey Ladder')),
        ('in_the_dark', _('In the Dark')),
        ('fog_of_war', _('Fog of War')),
    ],
    'long_term_memory': [
        ('concentration', _('Concentration')),
        ('recognition', _('Seen It Before?')),
    ],
    'attention': [
        ('reflex', _('Reflex')),
        ('ncup_monte', _('N-Cup Monte')),
        ('moving_targets', _('Moving Targets')),
        ('lookout', _('Lookout')),
        ('pursuit', _('Pursuit')),
        ('out_of_sight', _('Out of Sight')),
    ],
    'perception': [
        ('count', _('Count')),
    ],
    'reasoning': [
        ('graph_mapping', _('Graph Mapping')),
        ('matrix_reasoning', _('Matrix Reasoning')),
        ('jigsaw', _('Jigsaw Puzzle')),
    ],
    'planning': [
        ('tower_of_hanoi', _('Tower of Hanoi')),
        ('salesman', _('Traveling Salesman')),
        ('sokoban', _('Sokoban')),
        ('maze', _('Maze')),
    ],
}


def tasks_for(category: str) -> List[Tuple[str, str]]:
    """Tasks shown when *category* is selected."""
    return list(TASKS.get(category, ()))


class TaskHub:
    """Full-screen category switcher that launches a workshop task."""

    instance: Optional['TaskHub'] = None

    def __init__(self, return_to_title: bool = False,
                 category: Optional[str] = None) -> None:
        if TaskHub.instance is not None:
            TaskHub.instance.close()
        window = state.window
        self.return_to_title = return_to_title
        self.category = category or getattr(state.mode, 'task_category',
                                            'working_memory')
        if self.category not in TASKS:
            self.category = 'working_memory'
        self.selected = 0
        self.shapes: List[object] = []
        self.tab_rects: List[Tuple[int, int, int, int, str]] = []
        self.task_rects: List[Tuple[int, int, int, int, str]] = []
        self.tab_labels: List[pyglet.text.Label] = []
        self.task_labels: List[pyglet.text.Label] = []
        self._build_chrome()
        window.push_handlers(self.on_key_press, self.on_text_motion,
                             self.on_mouse_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        TaskHub.instance = self
        state.mode.task_category = self.category

    def _build_chrome(self) -> None:
        """Create the batch, the colours and the fixed labels.

        Called when the hub opens and again after a window resize, so
        everything sized from the window is created here.
        """
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.bgcolor = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.accent = (64, 96, 255, 255)
        self.muted = (fg, fg, fg, 160)
        self.batch = pyglet.graphics.Batch()

        self.title = pyglet.text.Label(
            _('Choose a task'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(48),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.empty = pyglet.text.Label(
            '', font_size=calc_fontsize(16), color=self.muted,
            batch=self.batch, x=width_center(), y=from_top_edge(280),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: back     ← → category     ↑ ↓ task'
              '     C: options     Enter: start'),
            font_size=calc_fontsize(12), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_bottom_edge(36),
            anchor_x='center', anchor_y='center')
        self.tab_labels = []
        self.task_labels = []
        self.shapes = []
        self._rebuild()

    def relayout(self) -> None:
        """Rebuild at the window's current size, keeping the selection."""
        self._build_chrome()

    def _clear_shapes(self) -> None:
        for shape in self.shapes:
            try:
                shape.delete()
            except Exception:
                pass
        self.shapes = []

    def _rebuild(self) -> None:
        """Recreate tabs and the task list for the active category."""
        self._clear_shapes()
        for label in self.tab_labels + self.task_labels:
            label.delete()
        self.tab_labels = []
        self.task_labels = []
        self.tab_rects = []
        self.task_rects = []

        window = state.window
        tab_count = len(CATEGORIES)
        gutter = max(48, int(window.width * 0.08))
        gap = max(10, int(window.width * 0.012))
        tab_w = (window.width - 2 * gutter - gap * (tab_count - 1)) // tab_count
        tab_h = max(48, int(calc_fontsize(36)))
        # Shrink the label until the longest category name fits inside a tab.
        tab_font = calc_fontsize(15)
        names = [name for _, name in CATEGORIES]
        while tab_font > 11:
            probe = pyglet.text.Label(
                max(names, key=len), font_size=tab_font, weight='bold',
                font_name=FONTLIST)
            widest = probe.content_width
            probe.delete()
            if widest <= tab_w - 24:
                break
            tab_font -= 1
        total_w = tab_count * tab_w + (tab_count - 1) * gap
        start_x = (window.width - total_w) // 2
        tab_y = from_top_edge(128)
        track = pyglet.shapes.Rectangle(
            start_x - 8, tab_y - tab_h // 2 - 8,
            total_w + 16, tab_h + 16,
            color=((28, 30, 38, 255) if state.cfg.BLACK_BACKGROUND
                   else (214, 218, 226, 255)),
            batch=self.batch)
        self.shapes.append(track)

        for index, (cat_id, name) in enumerate(CATEGORIES):
            x = start_x + index * (tab_w + gap)
            active = cat_id == self.category
            fill = self.accent if active else (
                (48, 52, 64, 255) if state.cfg.BLACK_BACKGROUND
                else (244, 246, 250, 255))
            ink = (255, 255, 255, 255) if active else self.textcolor
            rect = pyglet.shapes.Rectangle(
                x, tab_y - tab_h // 2, tab_w, tab_h, color=fill,
                batch=self.batch)
            self.shapes.append(rect)
            label = pyglet.text.Label(
                name, font_size=tab_font, weight='bold',
                color=ink, batch=self.batch,
                x=x + tab_w // 2, y=tab_y,
                anchor_x='center', anchor_y='center', font_name=FONTLIST)
            self.tab_labels.append(label)
            self.tab_rects.append((x, tab_y - tab_h // 2, tab_w, tab_h, cat_id))

        tasks = tasks_for(self.category)
        self.selected = min(self.selected, max(0, len(tasks) - 1))
        if not tasks:
            self.empty.text = _('No tasks in this category yet.')
            return
        self.empty.text = ''
        card_w = min(int(window.width * 0.46), window.width - 2 * gutter)
        card_h = max(52, int(calc_fontsize(40)))
        card_x = (window.width - card_w) // 2
        top = from_top_edge(220)
        for index, (task_id, name) in enumerate(tasks):
            y = top - index * (card_h + 14)
            selected = index == self.selected
            fill = self.accent if selected else (
                (32, 36, 46, 255) if state.cfg.BLACK_BACKGROUND
                else (236, 239, 245, 255))
            ink = (255, 255, 255, 255) if selected else self.textcolor
            rect = pyglet.shapes.Rectangle(
                card_x, y - card_h // 2, card_w, card_h, color=fill,
                batch=self.batch)
            self.shapes.append(rect)
            label = pyglet.text.Label(
                name, font_size=calc_fontsize(16), weight='bold',
                color=ink, batch=self.batch,
                x=window.width // 2, y=y,
                anchor_x='center', anchor_y='center', font_name=FONTLIST)
            self.task_labels.append(label)
            self.task_rects.append(
                (card_x, y - card_h // 2, card_w, card_h, task_id))

    def set_category(self, category: str) -> None:
        if category not in TASKS or category == self.category:
            if category in TASKS:
                self.category = category
                state.mode.task_category = category
            return
        self.category = category
        self.selected = 0
        state.mode.task_category = category
        self._rebuild()

    def cycle_category(self, step: int) -> None:
        ids = [item[0] for item in CATEGORIES]
        index = ids.index(self.category)
        self.set_category(ids[(index + step) % len(ids)])

    def move_task(self, step: int) -> None:
        tasks = tasks_for(self.category)
        if not tasks:
            return
        self.selected = (self.selected + step) % len(tasks)
        self._rebuild()

    def selected_task(self) -> Optional[str]:
        """The task id under the highlight, if the category has any."""
        tasks = tasks_for(self.category)
        if not tasks:
            return None
        return tasks[min(self.selected, len(tasks) - 1)][0]

    def open_options(self, task_id: Optional[str] = None) -> None:
        """Open the settings screen of the highlighted task."""
        from .taskoptions import open_task_options
        task_id = task_id or self.selected_task()
        if task_id is not None:
            open_task_options(task_id)

    def launch(self, task_id: Optional[str] = None) -> None:
        task_id = task_id or self.selected_task()
        if task_id is None:
            return
        launch_task(task_id, from_hub=self)

    def close(self) -> None:
        if TaskHub.instance is not self:
            return
        self._clear_shapes()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_text_motion,
                                     self.on_mouse_press, self.on_draw)
        cursor.release()
        TaskHub.instance = None
        if self.return_to_title:
            state.mode.title_screen = True

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.close()
        elif symbol in (key.RETURN, key.ENTER, key.SPACE):
            self.launch()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_text_motion(self, motion: int) -> bool:
        """Arrow keys move the selection.

        All four arrows are handled here and nowhere else. pyglet
        dispatches ``on_key_press`` *and* ``on_text_motion`` for one
        press of an arrow, so handling them in both moves twice per
        press — which read as working while there were three
        categories, because two steps of three is one step back.
        """
        if motion == key.MOTION_LEFT:
            self.cycle_category(-1)
        elif motion == key.MOTION_RIGHT:
            self.cycle_category(1)
        elif motion == key.MOTION_UP:
            self.move_task(-1)
        elif motion == key.MOTION_DOWN:
            self.move_task(1)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        for left, bottom, width, height, cat_id in self.tab_rects:
            if left <= x <= left + width and bottom <= y <= bottom + height:
                self.set_category(cat_id)
                return pyglet.event.EVENT_HANDLED
        for left, bottom, width, height, task_id in self.task_rects:
            if left <= x <= left + width and bottom <= y <= bottom + height:
                self.launch(task_id)
                return pyglet.event.EVENT_HANDLED
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def launch_task(task_id: str, from_hub: Optional[TaskHub] = None) -> None:
    """Leave the hub (if open) and start *task_id*."""
    return_to_title = from_hub.return_to_title if from_hub else False
    category = from_hub.category if from_hub else 'working_memory'
    if from_hub is not None:
        from_hub.return_to_title = False
        from_hub.close()
    state.mode.title_screen = False
    state.mode.task_category = category
    if task_id == 'nback':
        return
    if task_id == 'monkey_ladder':
        from .monkeyladder import MonkeyLadder
        MonkeyLadder()
        return
    if task_id == 'in_the_dark':
        from .inthedark import InTheDark
        InTheDark()
        return
    if task_id == 'fog_of_war':
        from .fogofwar import FogOfWar
        FogOfWar()
        return
    if task_id == 'ncup_monte':
        from .ncupmonte import NCupMonte
        NCupMonte()
        return
    if task_id == 'concentration':
        from .concentration import Concentration
        Concentration()
        return
    if task_id == 'recognition':
        from .recognition import Recognition
        Recognition()
        return
    if task_id == 'reflex':
        from .reflex import Reflex
        Reflex()
        return
    if task_id == 'moving_targets':
        from .tracking import MovingTargets
        MovingTargets()
        return
    if task_id == 'lookout':
        from .lookout import Lookout
        Lookout()
        return
    if task_id == 'pursuit':
        from .pursuit import Pursuit
        Pursuit()
        return
    if task_id == 'out_of_sight':
        from .outofsight import OutOfSight
        OutOfSight()
        return
    if task_id == 'count':
        from .counting import Counting
        Counting()
        return
    if task_id == 'graph_mapping':
        from .graphmapping import GraphMapping
        GraphMapping()
        return
    if task_id == 'matrix_reasoning':
        from .ravens import MatrixReasoning
        MatrixReasoning()
        return
    if task_id == 'jigsaw':
        from .jigsaw import JigsawPuzzle
        JigsawPuzzle()
        return
    if task_id == 'tower_of_hanoi':
        from .hanoi import TowerOfHanoi
        TowerOfHanoi()
        return
    if task_id == 'salesman':
        from .salesman import TravelingSalesman
        TravelingSalesman()
        return
    if task_id == 'sokoban':
        from .sokoban import SokobanTask
        SokobanTask()
        return
    if task_id == 'maze':
        from .maze import MazeTask
        MazeTask()
        return
    # Unknown task: restore the hub rather than dropping the player.
    TaskHub(return_to_title=return_to_title, category=category)
