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
    ('self_control', _('Self-control')),
    ('decisions', _('Decision making')),
    ('computer', _('Computer use')),
    ('emotion', _('Emotion')),
    ('social', _('Social')),
    ('rationality', _('Rationality')),
    ('order', _('Accuracy and order')),
    ('first_steps', _('First steps')),
)

#: Category id → list of (task id, label).
TASKS: Dict[str, List[Tuple[str, str]]] = {
    'working_memory': [
        ('nback', _('N-Back')),
        ('monkey_ladder', _('Monkey Ladder')),
        ('in_the_dark', _('In the Dark')),
        ('fog_of_war', _('Fog of War')),
        ('removals', _('Removals')),
        ('chain_of_custody', _('Chain of Custody')),
    ],
    'long_term_memory': [
        ('concentration', _('Concentration')),
        ('recognition', _('Seen It Before?')),
        ('trivia', _('Trivia')),
        ('notebook', _('Notebook')),
        ('where_was_it', _('Where Was It?')),
    ],
    'attention': [
        ('reflex', _('Reflex')),
        ('ncup_monte', _('N-Cup Monte')),
        ('moving_targets', _('Moving Targets')),
        ('lookout', _('Lookout')),
        ('pursuit', _('Pursuit')),
        ('buzz_wire', _('Buzz Wire')),
        ('out_of_sight', _('Out of Sight')),
        ('donkey', _('Donkey')),
        ('two_hands', _('Two Hands')),
        ('overrun', _('Overrun')),
        ('marble_maze', _('Marble Maze')),
        ('lander', _('Lander')),
        ('juggler', _('Juggler')),
        ('balance', _('Balance')),
        ('crossings', _('Crossings')),
        ('keep_the_beat', _('Keep the Beat')),
        ('glider', _('Glider')),
        ('catch', _('Catch')),
        ('echo_cave', _('Echo Cave')),
        ('drone_hoops', _('Drone Hoops')),
        ('field_manual', _('Field Manual')),
        ('safecracker', _('Safecracker')),
        ('stagehand', _('Stagehand')),
        ('loading_dock', _('Loading Dock')),
        ('gunslinger', _('Gunslinger')),
        ('potters_wheel', _("Potter's Wheel")),
        ('conductor', _('Conductor')),
        ('tightrope', _('Tightrope')),
        ('sign_painter', _('Sign Painter')),
        ('bartender', _('Bartender')),
        ('lock_pick', _('Lock Pick')),
        ('air_hockey', _('Air Hockey')),
        ('semaphore', _('Semaphore')),
        ('shadow_puppets', _('Shadow Puppets')),
        ('night_watch', _('Night Watch')),
        ('kerbside', _('Kerbside')),
        ('steadicam', _('Steadicam')),
        ('free_kick', _('Free Kick')),
        ('glove', _('Glove')),
        ('brick_breaker_3d', _('3D Brick Breaker')),
    ],
    'perception': [
        ('count', _('Count')),
        ('mr_time', _('Mr. Time')),
        ('camera', _('Camera')),
        ('what_next', _('What Happens Next')),
        ('will_it_fall', _('Will It Fall?')),
        ('same_or_mirror', _('Same or Mirror?')),
        ('which_is_nearer', _('Which Is Nearer?')),
        ('shape_from_motion', _('Shape from Motion')),
        ('point_of_view', _('Point of View')),
        ('dr_shape', _('Dr Shape')),
        ('inside_or_out', _('Inside or Out?')),
        ('touching', _('Touching?')),
        ('time_it', _('Time It')),
        ('tuner', _('Tuner')),
        ('shadow_play', _('Shadow Play')),
        ('captcha', _('Captcha')),
        ('by_ear', _('By Ear')),
        ('piano_tuner', _('Piano Tuner')),
        ('cricket_hunt', _('Cricket Hunt')),
        ('claw_machine', _('Claw Machine')),
        ('symmetric', _('Symmetric?')),
        ('tangram', _('Tangram')),
        ('will_it_fit', _('Will It Fit?')),
        ('holds_more', _('Holds More')),
        ('more_or_less', _('More or Less')),
        ('spot_the_change', _('Spot the Change')),
        ('find_it', _('Find It')),
        ('longer_or_sooner', _('Longer or Sooner?')),
        ('behind_the_screen', _('Behind the Screen')),
        ('same_or_different', _('Same or Different?')),
        ('brighter', _('Brighter')),
        ('colour_match', _('Colour Match')),
        ('longer_line', _('Longer Line')),
        ('steeper', _('Steeper')),
        ('bigger_area', _('Bigger Area')),
        ('midpoint', _('Midpoint')),
        ('parallel', _('Parallel?')),
        ('hidden_figure', _('Hidden Figure')),
        ('contour', _('Contour')),
        ('same_line', _('Same Line?')),
        ('texture_edge', _('Texture Edge')),
        ('whats_behind', _('What Is Behind')),
        ('top_card', _('Top Card')),
        ('bump_or_dent', _('Bump or Dent')),
        ('far_size', _('Far Size')),
        ('reflection', _('Reflection')),
        ('gaze', _('Gaze')),
        ('which_way', _('Which Way')),
        ('faster', _('Faster')),
        ('walker', _('Walker')),
        ('collision_course', _('Collision Course')),
        ('heading', _('Heading')),
        ('number_line', _('Number Line')),
        ('what_share', _('What Share')),
        ('louder', _('Louder')),
        ('which_ear', _('Which Ear')),
        ('up_or_down', _('Up or Down')),
        ('how_many_beeps', _('How Many Beeps')),
        ('same_instrument', _('Same Instrument')),
        ('flash_and_beep', _('Flash and Beep')),
        ('the_artist', _('The Artist')),
        ('live_claw_machine', _('Live Claw Machine')),
        ('piano_man', _('Piano Man')),
    ],
    'reasoning': [
        ('graph_mapping', _('Graph Mapping')),
        ('matrix_reasoning', _('Matrix Reasoning')),
        ('matrix_3d', _('3D Matrix')),
        ('hidden_rule', _('Hidden Rule')),
        ('wiring', _('Hidden Wiring')),
        ('jigsaw', _('Jigsaw Puzzle')),
        ('video_jigsaw', _('Video Jigsaw')),
        ('video_sequence', _('Video Sequence')),
        ('sudoku', _('Sudoku')),
        ('go_winning_move', _('Find the Winning Move')),
        ('crossed_wires', _('Crossed Wires')),
        ('crossword', _('Crossword')),
        ('scrabble', _('Scrabble')),
        ('scramble', _('Scramble')),
        ('algebra', _('Algebra')),
        ('numberology', _('Numberology')),
        ('syllogism', _('Syllogisms')),
        ('chess', _('Winning Move')),
        ('verbal_reasoning', _('Verbal Reasoning')),
        ('signals', _('Signals')),
        ('fold_it', _('Fold It')),
        ('who_knows_what', _('Who Knows What?')),
        ('crazy_cog', _('Crazy Cog')),
        ('cipher_abyss', _('The Cipher Abyss')),
        ('proofreader', _('The Proofreader')),
        ('full_stop', _('Full Stop')),
        ('missing_word', _('The Missing Word')),
        ('figures_of_speech', _('Figures of Speech')),
        ('heavier', _('Heavier')),
        ('analogies', _('Analogies')),
        ('odd_one_out', _('Odd One Out')),
        ('which_side', _('Which Side?')),
        ('pecking_order', _('Pecking Order')),
        ('card_sort', _('Card Sort')),
        ('triples', _('Triples')),
        ('who_lives_where', _('Who Lives Where?')),
        ('which_urn', _('Which Urn?')),
        ('grid_change', _('Grid Change')),
        ('button_box', _('Button Box')),
        ('which_block', _('Which Block?')),
        ('the_linguist', _('The Linguist')),
    ],
    'planning': [
        ('tower_of_hanoi', _('Tower of Hanoi')),
        ('salesman', _('Traveling Salesman')),
        ('sokoban', _('Sokoban')),
        ('maze', _('Maze')),
        ('you_are_here', _('3D Maze')),
        ('sokoban_3d', _('3D Sokoban')),
        ('tetris', _('Freeform Tetris')),
        ('n_in_a_row', _('N-in-a-row')),
        ('rail_yard', _('Rail Yard')),
        ('air_traffic', _('Air Traffic')),
        ('escort', _('Escort')),
        ('sokoban_live', _('Sokoban Live')),
        ('kitchen', _('Kitchen')),
        ('crane', _('Crane')),
        ('ferry', _('Ferry')),
        ('docking', _('Docking')),
        ('rover', _('Rover')),
        ('unicycle', _('Unicycle')),
    ],
    # Not attention, and the difference is the point. Everything under
    # attention is about finding or following the right thing; this is
    # about not doing a thing you are already doing and want to keep
    # doing. Reflex would fail every rung of it by being fast.
    'self_control': [
        ('cookie_thief', _('Cookie Thief')),
        ('stop_and_switch', _('Stop & Switch')),
        ('delay', _('Delay')),
        ('hold_it', _('Hold It')),
        ('morning_round', _('Morning Round')),
    ],
    # Choosing under uncertainty: what to find out, when to stop finding
    # out and commit, what a wrong commitment costs, and what waiting
    # costs while the world moves.
    'decisions': [
        ('sonar', _('Sonar')),
        ('dispatch', _('Dispatch')),
        ('gamble', _('Gamble')),
        ('bluff', _('Bluff')),
        ('triage', _('Triage')),
        ('explore_exploit', _('Explore or Exploit')),
        ('firebreak', _('Firebreak')),
        ('crossroads', _('Crossroads')),
        ('dam_keeper', _('Dam Keeper')),
    ],
    # Operating an interface: a pointer, a screen, and controls that
    # have to be found, uncovered and understood before they can be used.
    'computer': [
        ('desktop', _('Desktop')),
        ('forms', _('Forms')),
        ('manual', _('Manual')),
        ('browser', _('Browser')),
        ('errands', _('Errands')),
        ('spreadsheet', _('Spreadsheet')),
    ],
    # Reading feeling: in a face, in what people write and say, and in
    # what a situation is bound to make someone feel.
    'emotion': [
        ('emotion', _('Emotion')),
        ('which_feeling', _('Which Feeling')),
        ('how_strongly', _('How Strongly')),
        ('reading_people', _('Reading People')),
        ('why_they_feel', _('Why They Feel')),
        ('tone_of_voice', _('Tone of Voice')),
    ],
    # Reading people past their words: what a reply implies, what a
    # situation leads to.
    'social': [
        ('between_the_lines', _('Between the Lines')),
        ('social_sense', _('Social Sense')),
    ],
    # Thinking twice: arguments that do not follow, and questions whose
    # first answer is wrong.
    'rationality': [
        ('bad_argument', _('Bad Argument')),
        ('second_thoughts', _('Second Thoughts')),
    ],
    # Getting it exactly right: rules applied to the letter, things
    # kept in their places.
    'order': [
        ('desk_jockey', _('Desk Jockey')),
    ],
    'first_steps': [
        ('short_maze', _('Short Maze')),
        ('short_tower', _('Short Tower')),
        ('turned_tiles', _('Turned Tiles')),
        ('short_push', _('Short Push')),
        ('short_maze_steps', _('Short Maze, Step by Step')),
        ('marker_walk', _('Marker Walk')),
        ('marker_walk_shuffled', _('Marker Walk, Shuffled')),
        ('match_shapes', _('Match Shapes')),
        ('match_tiles', _('Match Tiles')),
        ('odd_shape', _('Odd Shape')),
        ('odd_stripe', _('Odd Stripe')),
        ('next_shape', _('Next Shape')),
        ('next_tile', _('Next Tile')),
        ('in_the_loop', _('In the Loop')),
        ('in_the_pen', _('In the Pen')),
        ('shape_back', _('Shape Back')),
        ('hidden_cue', _('Hidden Cue')),
        ('sound_back', _('Sound Back')),
        ('in_the_window', _('In the Window')),
        ('which_rule', _('Which Rule?')),
        ('changed_tile', _('Changed Tile')),
        ('swapped_boxes', _('Swapped Boxes')),
        ('which_moved', _('Which Moved?')),
        ('moved_bead', _('Moved Bead')),
        ('which_is_new', _('Which Is New?')),
        ('new_bead', _('New Bead')),
        ('which_is_gone', _('Which Is Gone?')),
        ('gone_bead', _('Gone Bead')),
        ('traded_places', _('Traded Places')),
        ('traded_beads', _('Traded Beads')),
        ('running_count', _('Running Count')),
        ('bead_pile', _('Bead Pile')),
        ('arrow_walk', _('Arrow Walk')),
        ('chevron_walk', _('Chevron Walk')),
        ('next_in_turn', _('Next in Turn')),
        ('round_again', _('Round Again')),
        ('stay_or_shift', _('Stay or Shift')),
        ('moving_prize', _('Moving Prize')),
        ('the_marked_one', _('The Marked One')),
        ('flagged_bead', _('Flagged Bead')),
        ('changed_note', _('Changed Note')),
        ('changed_chime', _('Changed Chime')),
        ('marked_tone', _('Marked Tone')),
        ('other_voice', _('Other Voice')),
        ('long_way_round', _('Long Way Round')),
        ('key_and_door', _('Key and Door')),
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
        columns = 3
        rows = (len(tasks) + columns - 1) // columns
        grid_w = min(window.width - 2 * gutter, int(window.width * 0.68))
        card_gap_x = max(10, int(window.width * 0.012))
        card_w = (grid_w - card_gap_x * (columns - 1)) // columns
        grid_w = columns * card_w + (columns - 1) * card_gap_x
        grid_x = (window.width - grid_w) // 2

        # Size the rows from the space between the tabs and the footer.  The
        # largest category currently needs six rows at the default window
        # size, while a larger window gets the roomier cards in the mock-up.
        top = from_top_edge(215)
        bottom = from_bottom_edge(72)
        card_gap_y = max(8, min(18, int(window.height * 0.015)))
        available = max(1, top - bottom - card_gap_y * (rows - 1))
        preferred_h = max(52, min(100, int(window.height * 0.095)))
        card_h = max(36, min(preferred_h, available // rows))

        for index, (task_id, name) in enumerate(tasks):
            row, column = divmod(index, columns)
            card_x = grid_x + column * (card_w + card_gap_x)
            y = top - row * (card_h + card_gap_y)
            selected = index == self.selected
            fill = self.accent if selected else (
                (32, 36, 46, 255) if state.cfg.BLACK_BACKGROUND
                else (236, 239, 245, 255))
            ink = (255, 255, 255, 255) if selected else self.textcolor
            rect = pyglet.shapes.Rectangle(
                card_x, y - card_h // 2, card_w, card_h, color=fill,
                batch=self.batch)
            self.shapes.append(rect)

            card_font = calc_fontsize(16)
            while card_font > 10:
                probe = pyglet.text.Label(
                    name, font_size=card_font, weight='bold',
                    font_name=FONTLIST)
                fits = probe.content_width <= card_w - 24
                probe.delete()
                if fits:
                    break
                card_font -= 1
            label = pyglet.text.Label(
                name, font_size=card_font, weight='bold',
                color=ink, batch=self.batch,
                x=card_x + card_w // 2, y=y,
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
    if task_id == 'removals':
        from .removals import Removals
        Removals()
        return
    if task_id == 'you_are_here':
        from .youarehere import YouAreHere
        YouAreHere()
        return
    if task_id == 'sokoban_3d':
        from .sokoban3d import Sokoban3D
        Sokoban3D()
        return
    if task_id == 'chain_of_custody':
        from .custody import ChainOfCustody
        ChainOfCustody()
        return
    if task_id == 'sudoku':
        from .sudoku import Sudoku
        Sudoku()
        return
    if task_id == 'go_winning_move':
        from .go import GoWinningMove
        GoWinningMove()
        return
    if task_id == 'crossed_wires':
        from .crossedwires import CrossedWires
        CrossedWires()
        return
    if task_id == 'crossword':
        from .crossword import Crossword
        Crossword()
        return
    if task_id == 'scrabble':
        from .scrabble import Scrabble
        Scrabble()
        return
    if task_id == 'scramble':
        from .scramble import Scramble
        Scramble()
        return
    if task_id == 'overrun':
        from .overrun import Overrun
        Overrun()
        return
    if task_id == 'algebra':
        from .algebra import Algebra
        Algebra()
        return
    if task_id == 'numberology':
        from .numberology import Numberology
        Numberology()
        return
    if task_id == 'syllogism':
        from .syllogism import Syllogism
        Syllogism()
        return
    if task_id == 'chess':
        from .chess import Chess
        Chess()
        return
    if task_id == 'verbal_reasoning':
        from .verbal import VerbalReasoning
        VerbalReasoning()
        return
    if task_id == 'marble_maze':
        from .marblemaze import MarbleMaze
        MarbleMaze()
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
    if task_id == 'trivia':
        from .trivia import Trivia
        Trivia()
        return
    if task_id == 'reflex':
        from .reflex import Reflex
        Reflex()
        return
    if task_id == 'donkey':
        from .donkey import Donkey
        Donkey()
        return
    if task_id == 'two_hands':
        from .twohands import Twohands
        Twohands()
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
    if task_id == 'buzz_wire':
        from .buzzwire import BuzzWire
        BuzzWire()
        return
    if task_id == 'out_of_sight':
        from .outofsight import OutOfSight
        OutOfSight()
        return
    if task_id == 'count':
        from .counting import Counting
        Counting()
        return
    if task_id == 'mr_time':
        from .mrtime import MrTime
        MrTime()
        return
    if task_id == 'graph_mapping':
        from .graphmapping import GraphMapping
        GraphMapping()
        return
    if task_id == 'matrix_reasoning':
        from .ravens import MatrixReasoning
        MatrixReasoning()
        return
    if task_id == 'hidden_rule':
        from .hiddenrule import HiddenRule
        HiddenRule()
        return
    if task_id == 'jigsaw':
        from .jigsaw import JigsawPuzzle
        JigsawPuzzle()
        return
    if task_id == 'triage':
        from .triage import Triage
        Triage()
        return
    if task_id == 'what_next':
        from .whatnext import WhatNext
        WhatNext()
        return
    if task_id == 'manual':
        from .manual import Manual
        Manual()
        return
    if task_id == 'notebook':
        from .notebook import Notebook
        Notebook()
        return
    if task_id == 'browser':
        from .browser import Browser
        Browser()
        return
    if task_id == 'will_it_fall':
        from .falls import WillItFall
        WillItFall()
        return
    if task_id == 'signals':
        from .signals import Signals
        Signals()
        return
    if task_id == 'errands':
        from .errands import Errands
        Errands()
        return
    if task_id == 'same_or_mirror':
        from .mirror import SameOrMirror
        SameOrMirror()
        return
    if task_id == 'which_is_nearer':
        from .nearer import WhichIsNearer
        WhichIsNearer()
        return
    if task_id == 'shape_from_motion':
        from .sfm import ShapeFromMotion
        ShapeFromMotion()
        return
    if task_id == 'fold_it':
        from .fold import FoldIt
        FoldIt()
        return
    if task_id == 'point_of_view':
        from .pov import PointOfView
        PointOfView()
        return
    if task_id == 'who_knows_what':
        from .beliefs import WhoKnowsWhat
        WhoKnowsWhat()
        return
    if task_id == 'where_was_it':
        from .rooms import WhereWasIt
        WhereWasIt()
        return
    if task_id == 'stop_and_switch':
        from .stopswitch import StopAndSwitch
        StopAndSwitch()
        return
    if task_id == 'delay':
        from .delay import Delay
        Delay()
        return
    if task_id == 'explore_exploit':
        from .bandit import ExploreOrExploit
        ExploreOrExploit()
        return
    if task_id == 'lander':
        from .lander import Lander
        Lander()
        return
    if task_id == 'spreadsheet':
        from .sheet import Spreadsheet
        Spreadsheet()
        return
    if task_id == 'rail_yard':
        from .railyard import RailYard
        RailYard()
        return
    if task_id == 'air_traffic':
        from .airtraffic import AirTraffic
        AirTraffic()
        return
    if task_id == 'firebreak':
        from .firebreak import Firebreak
        Firebreak()
        return
    if task_id == 'escort':
        from .escort import Escort
        Escort()
        return
    if task_id == 'sokoban_live':
        from .sokobanlive import SokobanLive
        SokobanLive()
        return
    if task_id == 'kitchen':
        from .kitchen import Kitchen
        Kitchen()
        return
    if task_id == 'crane':
        from .crane import Crane
        Crane()
        return
    if task_id == 'ferry':
        from .ferry import Ferry
        Ferry()
        return
    if task_id == 'juggler':
        from .juggler import Juggler
        Juggler()
        return
    if task_id == 'balance':
        from .balance import Balance
        Balance()
        return
    if task_id == 'crossroads':
        from .crossroads import Crossroads
        Crossroads()
        return
    if task_id == 'dam_keeper':
        from .damkeeper import DamKeeper
        DamKeeper()
        return
    if task_id == 'dr_shape':
        from .drshape import DrShape
        DrShape()
        return
    if task_id == 'inside_or_out':
        from .inside import InsideOrOut
        InsideOrOut()
        return
    if task_id == 'touching':
        from .touching import Touching
        Touching()
        return
    if task_id == 'crossings':
        from .crossings import Crossings
        Crossings()
        return
    if task_id == 'keep_the_beat':
        from .beat import KeepTheBeat
        KeepTheBeat()
        return
    if task_id == 'time_it':
        from .timeit import TimeIt
        TimeIt()
        return
    if task_id == 'hold_it':
        from .holdit import HoldIt
        HoldIt()
        return
    if task_id == 'glider':
        from .glider import Glider
        Glider()
        return
    if task_id == 'tuner':
        from .tuner import Tuner
        Tuner()
        return
    if task_id == 'shadow_play':
        from .shadowplay import ShadowPlay
        ShadowPlay()
        return
    if task_id == 'catch':
        from .catch import Catch
        Catch()
        return
    if task_id == 'echo_cave':
        from .echocave import EchoCave
        EchoCave()
        return
    if task_id == 'captcha':
        from .captcha import Captcha
        Captcha()
        return
    if task_id == 'drone_hoops':
        from .dronehoops import DroneHoops
        DroneHoops()
        return
    if task_id == 'field_manual':
        from .fieldmanual import FieldManual
        FieldManual()
        return
    if task_id == 'safecracker':
        from .safecracker import Safecracker
        Safecracker()
        return
    if task_id == 'stagehand':
        from .stagehand import Stagehand
        Stagehand()
        return
    if task_id == 'loading_dock':
        from .loadingdock import LoadingDock
        LoadingDock()
        return
    if task_id == 'gunslinger':
        from .gunslinger import Gunslinger
        Gunslinger()
        return
    if task_id == 'potters_wheel':
        from .potter import PottersWheel
        PottersWheel()
        return
    if task_id == 'conductor':
        from .conductor import Conductor
        Conductor()
        return
    if task_id == 'tightrope':
        from .tightrope import Tightrope
        Tightrope()
        return
    if task_id == 'sign_painter':
        from .signpainter import SignPainter
        SignPainter()
        return
    if task_id == 'bartender':
        from .bartender import Bartender
        Bartender()
        return
    if task_id == 'lock_pick':
        from .lockpick import LockPick
        LockPick()
        return
    if task_id == 'air_hockey':
        from .airhockey import AirHockey
        AirHockey()
        return
    if task_id == 'semaphore':
        from .semaphore import Semaphore
        Semaphore()
        return
    if task_id == 'shadow_puppets':
        from .shadowpuppets import ShadowPuppets
        ShadowPuppets()
        return
    if task_id == 'night_watch':
        from .nightwatch import NightWatch
        NightWatch()
        return
    if task_id == 'crazy_cog':
        from .crazycog import CrazyCog
        CrazyCog()
        return
    if task_id == 'cipher_abyss':
        from .cipherabyss import CipherAbyss
        CipherAbyss()
        return
    if task_id == 'proofreader':
        from .proofreader import Proofreader
        Proofreader()
        return
    if task_id == 'full_stop':
        from .fullstop import FullStop
        FullStop()
        return
    if task_id == 'missing_word':
        from .missingword import MissingWord
        MissingWord()
        return
    if task_id == 'morning_round':
        from .morninground import MorningRound
        MorningRound()
        return
    if task_id == 'emotion':
        from .emotion import Emotion
        Emotion()
        return
    if task_id == 'which_feeling':
        from .whichfeeling import WhichFeeling
        WhichFeeling()
        return
    if task_id == 'how_strongly':
        from .howstrongly import HowStrongly
        HowStrongly()
        return
    if task_id == 'reading_people':
        from .readingpeople import ReadingPeople
        ReadingPeople()
        return
    if task_id == 'why_they_feel':
        from .whytheyfeel import WhyTheyFeel
        WhyTheyFeel()
        return
    if task_id == 'between_the_lines':
        from .betweenlines import BetweenTheLines
        BetweenTheLines()
        return
    if task_id == 'social_sense':
        from .socialsense import SocialSense
        SocialSense()
        return
    if task_id == 'figures_of_speech':
        from .figures import FiguresOfSpeech
        FiguresOfSpeech()
        return
    if task_id == 'bad_argument':
        from .badargument import BadArgument
        BadArgument()
        return
    if task_id == 'second_thoughts':
        from .secondthoughts import SecondThoughts
        SecondThoughts()
        return
    if task_id == 'tone_of_voice':
        from .toneofvoice import ToneOfVoice
        ToneOfVoice()
        return
    if task_id == 'by_ear':
        from .byear import ByEar
        ByEar()
        return
    if task_id == 'piano_tuner':
        from .pianotuner import PianoTuner
        PianoTuner()
        return
    if task_id == 'kerbside':
        from .kerbside import Kerbside
        Kerbside()
        return
    if task_id == 'cricket_hunt':
        from .crickethunt import CricketHunt
        CricketHunt()
        return
    if task_id == 'steadicam':
        from .steadicam import Steadicam
        Steadicam()
        return
    if task_id == 'claw_machine':
        from .clawmachine import ClawMachine
        ClawMachine()
        return
    if task_id == 'docking':
        from .docking import Docking
        Docking()
        return
    if task_id == 'rover':
        from .rover import Rover
        Rover()
        return
    if task_id == 'heavier':
        from .heavier import Heavier
        Heavier()
        return
    if task_id == 'free_kick':
        from .freekick import FreeKick
        FreeKick()
        return
    if task_id == 'unicycle':
        from .unicycle import Unicycle
        Unicycle()
        return
    if task_id == 'glove':
        from .glove import Glove
        Glove()
        return
    if task_id == 'analogies':
        from .analogy import Analogy
        Analogy()
        return
    if task_id == 'odd_one_out':
        from .oddoneout import OddOneOut
        OddOneOut()
        return
    if task_id == 'which_side':
        from .whichside import WhichSide
        WhichSide()
        return
    if task_id == 'pecking_order':
        from .peckingorder import PeckingOrder
        PeckingOrder()
        return
    if task_id == 'card_sort':
        from .cardsort import CardSort
        CardSort()
        return
    if task_id == 'triples':
        from .triples import Triples
        Triples()
        return
    if task_id == 'who_lives_where':
        from .zebra import Zebra
        Zebra()
        return
    if task_id == 'which_urn':
        from .urns import Urns
        Urns()
        return
    if task_id == 'grid_change':
        from .gridchange import GridChange
        GridChange()
        return
    if task_id == 'button_box':
        from .buttonbox import ButtonBox
        ButtonBox()
        return
    if task_id == 'which_block':
        from .blicket import Blicket
        Blicket()
        return
    if task_id == 'symmetric':
        from .symmetry import Symmetry
        Symmetry()
        return
    if task_id == 'tangram':
        from .tangram import Tangram
        Tangram()
        return
    if task_id == 'will_it_fit':
        from .willitfit import WillItFit
        WillItFit()
        return
    if task_id == 'holds_more':
        from .holdsmore import HoldsMore
        HoldsMore()
        return
    if task_id == 'more_or_less':
        from .moreorless import MoreOrLess
        MoreOrLess()
        return
    if task_id == 'spot_the_change':
        from .spotchange import SpotChange
        SpotChange()
        return
    if task_id == 'find_it':
        from .findit import FindIt
        FindIt()
        return
    if task_id == 'longer_or_sooner':
        from .howlong import HowLong
        HowLong()
        return
    if task_id == 'behind_the_screen':
        from .behindscreen import BehindScreen
        BehindScreen()
        return
    if task_id == 'same_or_different':
        from .samediff import SameDiff
        SameDiff()
        return
    if task_id == 'brighter':
        from .brighter import Brighter
        Brighter()
        return
    if task_id == 'colour_match':
        from .colourmatch import ColourMatch
        ColourMatch()
        return
    if task_id == 'longer_line':
        from .longerline import LongerLine
        LongerLine()
        return
    if task_id == 'steeper':
        from .steeper import Steeper
        Steeper()
        return
    if task_id == 'bigger_area':
        from .biggerarea import BiggerArea
        BiggerArea()
        return
    if task_id == 'midpoint':
        from .midpoint import Midpoint
        Midpoint()
        return
    if task_id == 'parallel':
        from .parallel import Parallel
        Parallel()
        return
    if task_id == 'hidden_figure':
        from .hiddenfigure import HiddenFigure
        HiddenFigure()
        return
    if task_id == 'contour':
        from .contour import Contour
        Contour()
        return
    if task_id == 'same_line':
        from .sameline import SameLine
        SameLine()
        return
    if task_id == 'texture_edge':
        from .textureedge import TextureEdge
        TextureEdge()
        return
    if task_id == 'whats_behind':
        from .whatsbehind import WhatsBehind
        WhatsBehind()
        return
    if task_id == 'top_card':
        from .topcard import TopCard
        TopCard()
        return
    if task_id == 'bump_or_dent':
        from .bumpdent import BumpDent
        BumpDent()
        return
    if task_id == 'far_size':
        from .farsize import FarSize
        FarSize()
        return
    if task_id == 'reflection':
        from .reflection import Reflection
        Reflection()
        return
    if task_id == 'gaze':
        from .gaze import Gaze
        Gaze()
        return
    if task_id == 'which_way':
        from .whichway import WhichWay
        WhichWay()
        return
    if task_id == 'faster':
        from .faster import Faster
        Faster()
        return
    if task_id == 'walker':
        from .walker import Walker
        Walker()
        return
    if task_id == 'collision_course':
        from .collision import Collision
        Collision()
        return
    if task_id == 'heading':
        from .heading import Heading
        Heading()
        return
    if task_id == 'number_line':
        from .numberline import NumberLine
        NumberLine()
        return
    if task_id == 'what_share':
        from .whatshare import WhatShare
        WhatShare()
        return
    if task_id == 'louder':
        from .louder import Louder
        Louder()
        return
    if task_id == 'which_ear':
        from .whichear import WhichEar
        WhichEar()
        return
    if task_id == 'up_or_down':
        from .upordown import UpOrDown
        UpOrDown()
        return
    if task_id == 'how_many_beeps':
        from .howmanybeeps import HowManyBeeps
        HowManyBeeps()
        return
    if task_id == 'same_instrument':
        from .sameinstrument import SameInstrument
        SameInstrument()
        return
    if task_id == 'flash_and_beep':
        from .flashbeep import FlashBeep
        FlashBeep()
        return
    if task_id == 'the_artist':
        from .artist import Artist
        Artist()
        return
    if task_id == 'live_claw_machine':
        from .liveclaw import LiveClaw
        LiveClaw()
        return
    if task_id == 'piano_man':
        from .pianoman import PianoMan
        PianoMan()
        return
    if task_id == 'matrix_3d':
        from .matrix3d import Matrix3D
        Matrix3D()
        return
    if task_id == 'brick_breaker_3d':
        from .brickbreaker import BrickBreaker
        BrickBreaker()
        return
    if task_id == 'the_linguist':
        from .linguist import Linguist
        Linguist()
        return
    if task_id == 'desk_jockey':
        from .deskjockey import DeskJockey
        DeskJockey()
        return
    if task_id == 'short_maze':
        from .ministeps import ShortMaze
        ShortMaze()
        return
    if task_id == 'short_tower':
        from .ministeps import ShortTower
        ShortTower()
        return
    if task_id == 'turned_tiles':
        from .ministeps import TurnedTiles
        TurnedTiles()
        return
    if task_id == 'short_push':
        from .ministeps import ShortPush
        ShortPush()
        return
    if task_id == 'short_maze_steps':
        from .ministeps import ShortMazeSteps
        ShortMazeSteps()
        return
    if task_id == 'marker_walk':
        from .ministeps import MarkerWalk
        MarkerWalk()
        return
    if task_id == 'marker_walk_shuffled':
        from .ministeps import MarkerWalkShuffled
        MarkerWalkShuffled()
        return
    if task_id == 'match_shapes':
        from .twins import MatchShapes
        MatchShapes()
        return
    if task_id == 'match_tiles':
        from .twins import MatchTiles
        MatchTiles()
        return
    if task_id == 'odd_shape':
        from .twins import OddShape
        OddShape()
        return
    if task_id == 'odd_stripe':
        from .twins import OddStripe
        OddStripe()
        return
    if task_id == 'next_shape':
        from .twins import NextShape
        NextShape()
        return
    if task_id == 'next_tile':
        from .twins import NextTile
        NextTile()
        return
    if task_id == 'in_the_loop':
        from .twins import InTheLoop
        InTheLoop()
        return
    if task_id == 'in_the_pen':
        from .twins import InThePen
        InThePen()
        return
    if task_id == 'shape_back':
        from .lookback import ShapeBack
        ShapeBack()
        return
    if task_id == 'hidden_cue':
        from .lookback import HiddenCue
        HiddenCue()
        return
    if task_id == 'sound_back':
        from .lookback import SoundBack
        SoundBack()
        return
    if task_id == 'in_the_window':
        from .inwindow import InTheWindow
        InTheWindow()
        return
    if task_id == 'which_rule':
        from .ruleguess import WhichRule
        WhichRule()
        return
    if task_id == 'changed_tile':
        from .inmind import ChangedTile
        ChangedTile()
        return
    if task_id == 'swapped_boxes':
        from .inmind import SwappedBoxes
        SwappedBoxes()
        return
    if task_id == 'which_moved':
        from .nowthen import WhichMoved
        WhichMoved()
        return
    if task_id == 'moved_bead':
        from .nowthen import MovedBead
        MovedBead()
        return
    if task_id == 'which_is_new':
        from .nowthen import WhichIsNew
        WhichIsNew()
        return
    if task_id == 'new_bead':
        from .nowthen import NewBead
        NewBead()
        return
    if task_id == 'which_is_gone':
        from .nowthen import WhichIsGone
        WhichIsGone()
        return
    if task_id == 'gone_bead':
        from .nowthen import GoneBead
        GoneBead()
        return
    if task_id == 'traded_places':
        from .nowthen import TradedPlaces
        TradedPlaces()
        return
    if task_id == 'traded_beads':
        from .nowthen import TradedBeads
        TradedBeads()
        return
    if task_id == 'running_count':
        from .carried import RunningCount
        RunningCount()
        return
    if task_id == 'bead_pile':
        from .carried import BeadPile
        BeadPile()
        return
    if task_id == 'arrow_walk':
        from .carried import ArrowWalk
        ArrowWalk()
        return
    if task_id == 'chevron_walk':
        from .carried import ChevronWalk
        ChevronWalk()
        return
    if task_id == 'next_in_turn':
        from .ownpress import NextInTurn
        NextInTurn()
        return
    if task_id == 'round_again':
        from .ownpress import RoundAgain
        RoundAgain()
        return
    if task_id == 'stay_or_shift':
        from .ownpress import StayOrShift
        StayOrShift()
        return
    if task_id == 'moving_prize':
        from .ownpress import MovingPrize
        MovingPrize()
        return
    if task_id == 'the_marked_one':
        from .farcue import TheMarkedOne
        TheMarkedOne()
        return
    if task_id == 'flagged_bead':
        from .farcue import FlaggedBead
        FlaggedBead()
        return
    if task_id == 'changed_note':
        from .heardback import ChangedNote
        ChangedNote()
        return
    if task_id == 'changed_chime':
        from .heardback import ChangedChime
        ChangedChime()
        return
    if task_id == 'marked_tone':
        from .heardback import MarkedTone
        MarkedTone()
        return
    if task_id == 'other_voice':
        from .heardback import OtherVoice
        OtherVoice()
        return
    if task_id == 'long_way_round':
        from .longwalk import LongWayRound
        LongWayRound()
        return
    if task_id == 'key_and_door':
        from .longwalk import KeyAndDoor
        KeyAndDoor()
        return
    if task_id == 'gamble':
        from .gamble import Gamble
        Gamble()
        return
    if task_id == 'wiring':
        from .wiring import Wiring
        Wiring()
        return
    if task_id == 'forms':
        from .forms import Forms
        Forms()
        return
    if task_id == 'bluff':
        from .bluff import Bluff
        Bluff()
        return
    if task_id == 'desktop':
        from .desktop import Desktop
        Desktop()
        return
    if task_id == 'dispatch':
        from .dispatch import Dispatch
        Dispatch()
        return
    if task_id == 'sonar':
        from .sonar import Sonar
        Sonar()
        return
    if task_id == 'camera':
        from .camera import CameraTask
        CameraTask()
        return
    if task_id == 'video_jigsaw':
        from .videojigsaw import VideoJigsaw
        VideoJigsaw()
        return
    if task_id == 'video_sequence':
        from .videosequence import VideoSequence
        VideoSequence()
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
    if task_id == 'tetris':
        from .tetris import FreeformTetris
        FreeformTetris()
        return
    if task_id == 'n_in_a_row':
        from .ninarow import NInARow
        NInARow()
        return
    if task_id == 'cookie_thief':
        from .cookiethief import CookieThief
        CookieThief()
        return
    # Unknown task: restore the hub rather than dropping the player.
    TaskHub(return_to_title=return_to_title, category=category)
