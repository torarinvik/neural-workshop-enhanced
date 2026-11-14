# -*- coding: utf-8 -*-
"""Desktop: a small computer to operate, from one button to a cluttered screen.

The workshop's other tasks hand the player controls with a fixed
meaning. This one hands them a pointer and a screen. Windows hold
controls -- switches, rows of choices, sliders with notches, dropdown
lists, colour swatches, steppers -- and a card beside the screen shows
the settings to reach. The player moves the pointer, clicks and drags.
Moving is free; every click and every drag costs a point, whatever it
does or fails to do, and the round passes if the card's settings hold
when Done is pressed and the clicks came in at or under par.

What has to be learned is what operating any computer asks:

* **Widget grammars.** A switch flips; a row of choices or colours
  takes the one clicked; a slider takes the notch; a dropdown opens a
  list and takes the item; a stepper goes up and down one at a time.
* **Finding the control.** Tabs, scrolling, menu bars whose items open
  dialogs -- kept by OK, thrown away by Cancel -- and from rung nineteen
  menus that cascade into submenus.
* **The window manager.** Windows overlap, and only what is on top
  takes a click. They can be raised, moved by their title bar, resized
  by their corner, minimised to the taskbar and closed; a closed one
  comes back from the Start menu, and closing it throws away whatever
  it had not applied. Some start minimised, some closed, some small,
  one hanging off the edge of the screen, and sticky notes sit on top
  of everything until they are moved or put away.
* **Prerequisites and interruptions.** Controls greyed out until some
  other setting holds; windows that keep changes until Apply; popups
  that arrive mid-task, take every click until they are answered, and
  offer a button that undoes a window's work next to one that does not.

**The reference is deliberately plain.** It works through the card in
the order the card lists it, one setting at a time, and sees each one
all the way home -- an OK for every dialog setting, an Apply for every
pending one -- before it looks at the next. It scrolls rather than
resizes, raises rather than rearranges, and never reorders the card.
Below rung twenty that is generous; past it the clicks have to come in
under the reference's, by more at every rung, and the only way there
is to plan the work.

**Everything that happens to the screen is fixed by the deal.** Where
the windows are, which start minimised or closed, and on which click a
popup arrives are dealt before the round starts, so the reference meets
the same desktop and the same interruptions on the same numbered click.

Everything is in logical units on a 1000 by 640 screen, origin at the
top left, so the model, the reference and the screen agree about where
everything is. Nothing here imports pyglet.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Sequence, Tuple, Union

SCREEN_W, SCREEN_H = 1000, 640
TASKBAR_H = 40
#: Where windows may be: everything above the taskbar.
WORK_H = SCREEN_H - TASKBAR_H
TITLE_H, MENU_H, TAB_H, ROW_H, APPLY_H = 30, 26, 28, 36, 38
WINDOW_W = 440
NOTE_W = 220
DIALOG_W = 400
ITEM_W, ITEM_H = 160, 30
#: Pointer steps, logical units: coarse, medium, fine.
STEPS = (80, 20, 5)
#: Every point the reference presses is on this grid, which is the grid
#: the pointer moves on from its start, so the agent can reach it too.
GRID = 5
START = (500, 320)
#: A press and release closer than this is a click, not a drag.
STILL = 3
DONE_RECT = (SCREEN_W - 130, WORK_H + 6, 120, TASKBAR_H - 12)
START_RECT = (6, WORK_H + 6, 70, TASKBAR_H - 12)
POPUP_RECT = (300, 180, 400, 150)
#: Where the card can be peeked at once it has hidden.
PEEK_RECT = (SCREEN_W - 216, WORK_H + 6, 80, TASKBAR_H - 12)

KINDS = ('toggle', 'choice', 'slider', 'dropdown', 'colour', 'stepper')

LABELS = ('Sound', 'Wi-Fi', 'Bluetooth', 'Night mode', 'Brightness',
          'Volume', 'Font', 'Theme', 'Sync', 'Backup', 'Alerts', 'Zoom',
          'Grid', 'Snap', 'Autosave', 'Contrast', 'Cursor', 'Speed',
          'Quality', 'Format', 'Privacy', 'Updates', 'Mouse', 'Keys',
          'Power', 'Sleep', 'Timer', 'Echo', 'Bass', 'Treble', 'Shadow',
          'Border', 'Margin', 'Spacing', 'Accent', 'Rulers', 'Hints',
          'Lock', 'Repeat', 'Shuffle', 'Captions', 'Filter', 'Tint',
          'Scale', 'Paper', 'Copies', 'Duplex', 'Layout', 'Corners',
          'Motion', 'Focus', 'Halo', 'Ink', 'Pitch', 'Tempo', 'Depth',
          'Glow', 'Hue', 'Grain', 'Blur')
TITLES = ('Settings', 'Audio', 'Display', 'Network', 'Editor', 'Printer',
          'Mail', 'Clock', 'Files', 'Camera', 'Music', 'Maps')
TABS = ('General', 'Advanced', 'Extra', 'View')
MENUS = ('Edit', 'Tools', 'View')
DIALOGS = ('Preferences', 'Options', 'Format', 'Filters', 'Colours',
           'Behaviour', 'Network', 'Storage', 'Startup', 'Privacy',
           'Fonts', 'Export', 'Sharing', 'Layout', 'Accounts', 'Sounds',
           'Shortcuts', 'Language')
WORDS = ('Off', 'Low', 'Mid', 'High', 'Auto', 'Max')
#: Colour swatches: a name each, for the card and for the screen.
COLOURS = (('red', (214, 64, 58)), ('orange', (236, 136, 40)),
           ('yellow', (236, 200, 40)), ('green', (60, 160, 80)),
           ('teal', (30, 150, 150)), ('blue', (52, 110, 220)),
           ('purple', (130, 80, 190)), ('pink', (226, 110, 170)))
NOTES = ('Call the bank', 'Milk, eggs', 'Meeting at 3', 'Back up photos',
         'Water plants', 'Pay rent')
SUBMENU = 'More'

#: The file explorer, its toolbar, and the places down its side. The
#: places are also the first seven folders of every file system, in
#: this order: Home, its five folders, and the Trash.
EXPLORER = 'Explorer'
EXPLORER_W, EXPLORER_H = 600, 400
TOOLS = ('Back', 'Up', 'Cut', 'Copy', 'Paste', 'Delete', 'View')
TOOL_W = (52, 40, 44, 48, 56, 62, 52)
#: A row of the explorer's list view.
LIST_H = 26
#: A right-click menu's width.
CONTEXT_W = 150
PLACES = ('Home', 'Desktop', 'Documents', 'Downloads', 'Music', 'Pictures',
          'Trash')
HOME, DESKTOP_DIR, DOCUMENTS, TRASH = 0, 1, 2, 6
#: Explorer tabs open at most.
MOST_TABS = 4
#: Icons per row of the explorer's grid.
COLUMNS = 5
FOLDERS = ('Work', 'Old', '2023', '2024', 'Trips', 'Taxes', 'Drafts',
           'Projects', 'School', 'Recipes', 'Archive', 'Family', 'Mixes',
           'Invoices', 'Backup', 'Ideas', 'Garden', 'Car', 'Clients',
           'Scans', 'Live', 'Covers', 'Notes', 'Misc')
FILE_WORDS = ('budget', 'report', 'notes', 'letter', 'plan', 'photo',
              'song', 'invoice', 'resume', 'draft', 'list', 'map', 'poster',
              'recipe', 'scan', 'memo', 'beach', 'party', 'demo', 'score',
              'lease', 'quote', 'agenda', 'cover', 'sketch', 'intro',
              'payslip', 'ticket', 'garden', 'minutes')
EXTENSIONS = {'doc': ('.txt', '.doc'), 'sheet': ('.xls',),
              'image': ('.png', '.jpg'), 'music': ('.mp3',)}
#: What a folder in each place mostly holds.
HOLDS = {2: ('doc', 'sheet'), 3: ('doc', 'sheet', 'image', 'music'),
         4: ('music',), 5: ('image',), 1: ('doc', 'image', 'sheet')}
#: Desktop icons, in columns down the left of the screen.
ICON_W, ICON_H = 84, 84
ICONS_PER_COLUMN = 6
#: The Start panel: pinned tiles, or the list of every app.
START_PANEL = (6, WORK_H - 330, 360, 330)
TILE_W, TILE_H = 104, 84


class Grade(NamedTuple):
    rung: int
    windows: int
    tabs: int
    #: Controls on each tab, and how many rows a window shows at once.
    per_tab: int
    rows: int
    kinds: Tuple[str, ...]
    #: Dialogs behind each window's menu bar, and whether some sit in
    #: a submenu.
    dialogs: int
    submenus: bool
    #: Greyed-out controls, and windows that keep changes until Apply.
    depends: int
    applies: int
    #: Popups that interrupt, windows that start minimised or closed,
    #: sticky notes, and windows hanging off the screen.
    popups: int
    minimised: int
    closed: int
    notes: int
    offscreen: int
    #: The file explorer; files to move, to delete, and to bring back
    #: from the Trash; how deep the folders go; files on the desktop;
    #: explorer tabs open at the start; apps pinned to Start; and
    #: whether the explorer starts closed.
    explorer: bool
    moves: int
    deletes: int
    restores: int
    depth: int
    desktop_files: int
    ex_tabs: int
    pinned: int
    explorer_closed: bool
    #: Files to copy, whether an explorer may open in list view, and
    #: whether the card hides after the first click (peeks cost one).
    copies: int
    list_view: bool
    hide_card: bool
    goals: int
    factor: float
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    per_tab = min(8, 1 + r // 2)
    windows = 1 if r < 11 else min(6, 2 + (r - 11) // 3)
    kinds = KINDS[:min(4, r)]
    if r >= 7:
        kinds += ('colour',)
    if r >= 9:
        kinds += ('stepper',)
    return Grade(
        rung=r,
        windows=windows,
        tabs=1 if r < 5 else (2 if r < 10 else 3),
        per_tab=per_tab,
        # From rung thirteen windows open small: scrolling still works,
        # and one drag of the corner can save a run of scroll clicks.
        rows=(per_tab if r < 6 else 3 if r < 8 else 4 if r < 13 else 2),
        kinds=kinds,
        dialogs=0 if r < 8 else (1 if r < 12 else 2 if r < 19 else 3),
        submenus=r >= 19,
        depends=0 if r < 15 else min(4, 1 + (r - 15) // 3),
        applies=0 if r < 16 else (1 if r < 19 else 2),
        popups=0 if r < 10 else min(4, 1 + (r - 10) // 5),
        minimised=0 if r < 12 else min(windows - 1, 1 + (r - 12) // 4),
        closed=0 if r < 18 else min(2, 1 + (r - 18) // 6),
        notes=0 if r < 14 else (1 if r < 20 else 2),
        offscreen=0 if r < 17 else 1,
        explorer=r >= 6,
        moves=0 if r < 6 else min(8, 1 + (r - 6) // 3),
        deletes=0 if r < 14 else min(3, 1 + (r - 14) // 6),
        restores=0 if r < 18 else min(3, 1 + (r - 18) // 8),
        # Folders nest deeper without end: the long horizon of the task.
        depth=1 if r < 9 else 2 if r < 16 else min(8, 3 + (r - 16) // 4),
        desktop_files=0 if r < 14 else 3,
        ex_tabs=1 if r < 12 else 2,
        pinned=5 if r < 18 else 2,
        explorer_closed=r >= 15,
        copies=0 if r < 10 else min(3, 1 + (r - 10) // 6),
        list_view=r >= 16,
        hide_card=r >= 24,
        goals=1 if r <= 2 else min(14, r // 2 + 1),
        factor=(max(1.0, 2.0 - (r - 1) / 11.0) if r <= 20
                # Gentler than the other tasks' four per cent: measured,
                # planners that resize, drag and take shorter routes
                # save two to seven per cent of the reference's clicks
                # once files are on the card, so the first rungs past
                # twenty are within reach of planning and the later
                # ones ask for more than any planner tried has found.
                else 1.0 / (1.0 + 0.01 * (r - 20))),
        slack=2.0 if r < 12 else 0.0,
    )


# --- the parts of a desktop --------------------------------------------------

class Control:
    def __init__(self, ident: int, label: str, kind: str, count: int,
                 value: int, words: Tuple[str, ...]) -> None:
        self.ident = ident
        self.label = label
        self.kind = kind
        self.count = count
        #: What holds, and what the screen shows. They differ only for
        #: a control in an open dialog or a window waiting for Apply.
        self.value = value
        self.shown = value
        self.start = value
        self.words = words
        #: (control, value) it needs to hold before this one works.
        self.requires: Optional[Tuple['Control', int]] = None
        #: Where it lives, set when it is placed.
        self.window: Optional['Window'] = None
        self.dialog: Optional['Dialog'] = None
        self.tab = 0
        self.row = 0

    def word(self, value: int) -> str:
        if self.kind == 'toggle':
            return ('off', 'on')[value]
        if self.kind in ('slider', 'stepper'):
            return str(value + 1)
        return self.words[value]

    @property
    def enabled(self) -> bool:
        if self.requires is None:
            return True
        other, wanted = self.requires
        return other.value == wanted


class Dialog:
    def __init__(self, title: str, controls: List[Control]) -> None:
        self.title = title
        self.controls = controls
        self.window: Optional['Window'] = None
        #: Which menu, which item in it, and which item of the submenu
        #: that item opens -- or None when the item opens it directly.
        self.menu = 0
        self.item = 0
        self.sub: Optional[int] = None


class Submenu:
    def __init__(self, name: str, dialogs: List[Dialog]) -> None:
        self.name = name
        self.dialogs = dialogs


Item = Union[Dialog, Submenu]


class Node:
    """A folder or a file."""

    def __init__(self, ident: int, name: str, folder: bool, kind: str,
                 parent: Optional['Node']) -> None:
        self.ident = ident
        self.name = name
        self.folder = folder
        self.kind = kind
        self.parent = parent
        self.children: List['Node'] = []
        #: Where it was before it went to the Trash.
        self.origin: Optional['Node'] = None

    def within(self, other: 'Node') -> bool:
        """Whether this is *other* or somewhere inside it."""
        node: Optional[Node] = self
        while node is not None:
            if node is other:
                return True
            node = node.parent
        return False

    def chain(self) -> List['Node']:
        """From the top folder down to this one."""
        found, node = [], self
        while node is not None:
            found.append(node)
            node = node.parent
        return found[::-1]

    def path(self) -> str:
        return ' › '.join(node.name for node in self.chain())

    def listing(self) -> List['Node']:
        """Folders first, then files, each by name."""
        return (sorted((c for c in self.children if c.folder),
                       key=lambda c: c.name)
                + sorted((c for c in self.children if not c.folder),
                         key=lambda c: c.name))


class Place:
    """One explorer tab: where it is, where it has been, what is picked."""

    def __init__(self, path: Node) -> None:
        self.path = path
        self.history: List[Node] = []
        self.scroll = 0
        self.selected: Optional[Node] = None


class Window:
    def __init__(self, ident: int, title: str, tabs: List[List[Control]],
                 rows: int, menus: List[Tuple[str, List[Item]]],
                 apply: bool, note: str = '') -> None:
        self.ident = ident
        self.title = title
        self.tabs = tabs
        self.rows = rows
        self.menus = menus
        self.apply = apply
        #: A sticky note: no controls, and always on top.
        self.note = note
        self.active = 0
        #: Rows scrolled past, per tab.
        self.scroll = [0] * len(tabs)
        self.x = self.y = 0
        self.w = NOTE_W if note else WINDOW_W
        self.minimised = False
        self.closed = False
        #: 'app', 'note' or 'explorer'.
        self.kind = 'note' if note else 'app'
        #: The explorer's tabs, and which is showing.
        self.places: List[Place] = []
        self.place = 0
        #: The explorer shows rows of names instead of a grid of icons.
        self.list_view = False

    @property
    def pinned(self) -> bool:
        return bool(self.note)

    @property
    def shown(self) -> bool:
        return not (self.minimised or self.closed)

    @property
    def chrome(self) -> int:
        """Height of everything but the rows."""
        return (TITLE_H + (MENU_H if self.menus else 0)
                + (TAB_H if len(self.tabs) > 1 else 0)
                + (APPLY_H if self.apply else 0) + 8)

    @property
    def h(self) -> int:
        if self.kind == 'explorer':
            return EXPLORER_H
        return self.chrome + self.rows * ROW_H

    @property
    def most_rows(self) -> int:
        """The most rows it can be resized to show."""
        longest = max(1, max(len(page) for page in self.tabs))
        room = (WORK_H - self.y - self.chrome) // ROW_H
        return max(1, min(longest, room))

    @property
    def content_top(self) -> int:
        return (self.y + TITLE_H + (MENU_H if self.menus else 0)
                + (TAB_H if len(self.tabs) > 1 else 0))

    def scrolls(self, tab: int) -> bool:
        return len(self.tabs[tab]) > self.rows

    def controls(self) -> List[Control]:
        found = [c for page in self.tabs for c in page]
        for _name, items in self.menus:
            for item in items:
                for dialog in (item.dialogs if isinstance(item, Submenu)
                               else [item]):
                    found += dialog.controls
        return found


Rect = Tuple[float, float, float, float]       # x, y, w, h; y down
Action = Tuple  # ('click', point) or ('drag', from, to)


def inside(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


def centre(rect: Rect) -> Tuple[float, float]:
    x, y, w, h = rect
    return x + w / 2, y + h / 2


# --- layout: where everything is, for the model and the screen alike --------

def title_rect(win: Window) -> Rect:
    return (win.x, win.y, win.w, TITLE_H)


def close_rect(win: Window) -> Rect:
    return (win.x + win.w - 30, win.y + 4, 24, TITLE_H - 8)


def minimise_rect(win: Window) -> Rect:
    return (win.x + win.w - 58, win.y + 4, 24, TITLE_H - 8)


def grip_rect(win: Window) -> Rect:
    return (win.x + win.w - 18, win.y + win.h - 18, 18, 18)


def menu_rects(win: Window) -> List[Rect]:
    return [(win.x + 8 + i * 72, win.y + TITLE_H, 68, MENU_H)
            for i in range(len(win.menus))]


def tab_rects(win: Window) -> List[Rect]:
    if len(win.tabs) < 2:
        return []
    top = win.y + TITLE_H + (MENU_H if win.menus else 0)
    return [(win.x + 8 + i * 104, top + 2, 100, TAB_H - 2)
            for i in range(len(win.tabs))]


def scroll_rects(win: Window) -> Tuple[Rect, Rect]:
    top = win.content_top
    x = win.x + win.w - 30
    if win.rows == 1:
        return ((x - 28, top + 6, 24, 24), (x, top + 6, 24, 24))
    return ((x, top + 2, 24, 24),
            (x, top + win.rows * ROW_H - 26, 24, 24))


def apply_rect(win: Window) -> Rect:
    return (win.x + win.w - 104, win.content_top + win.rows * ROW_H + 4,
            92, APPLY_H - 8)


def widget_rect(left: float, top: float, width: float) -> Rect:
    """The part of a row the control itself takes."""
    return (left + width * 0.42, top + 5, width * 0.5 - 36, ROW_H - 10)


def parts(control: Control, rect: Rect) -> List[Rect]:
    """Where clicking does something: for a row of choices, colours or
    notches one place per value; for a stepper its minus and its plus;
    for a switch and a dropdown the one place."""
    x, y, w, h = rect
    if control.kind == 'toggle':
        return [(x, y, 56, h)]
    if control.kind == 'dropdown':
        return [(x, y, w * 0.7, h)]
    if control.kind == 'stepper':
        return [(x, y, 28, h), (x + 84, y, 28, h)]
    cell = w / control.count
    return [(x + i * cell, y, cell, h) for i in range(control.count)]


def dropdown_items(rect: Rect, control: Control) -> List[Rect]:
    x, y, w, h = parts(control, rect)[0]
    if y + h + control.count * 28 > WORK_H:
        # No room below: the list opens upwards, as a real one does.
        return [(x, y - (control.count - i) * 28, w, 28)
                for i in range(control.count)]
    return [(x, y + h + i * 28, w, 28) for i in range(control.count)]


def tool_rects(win: Window) -> List[Tuple[str, Rect]]:
    found, x = [], win.x + 8
    for name, width in zip(TOOLS, TOOL_W):
        found.append((name, (x, win.y + TITLE_H + 3, width, 24)))
        x += width + 6
    return found


def place_tab_rects(win: Window) -> List[Rect]:
    return [(win.x + 8 + i * 124, win.y + TITLE_H + 31, 120, 26)
            for i in range(len(win.places))]


def plus_rect(win: Window) -> Rect:
    return (win.x + 8 + len(win.places) * 124, win.y + TITLE_H + 31, 26, 26)


def path_rect(win: Window) -> Rect:
    return (win.x + 136, win.y + TITLE_H + 60, win.w - 144, 22)


def sidebar_rects(win: Window) -> List[Rect]:
    return [(win.x + 8, win.y + TITLE_H + 86 + i * 30, 120, 28)
            for i in range(len(PLACES))]


def grid_area(win: Window) -> Rect:
    top = win.y + TITLE_H + 86
    return (win.x + 136, top, win.w - 136 - 36, win.y + win.h - 8 - top)


def cell_size(win: Window) -> float:
    return grid_area(win)[2] / COLUMNS


def ex_columns(win: Window) -> int:
    return 1 if win.list_view else COLUMNS


def cell_dims(win: Window) -> Tuple[float, float]:
    """Width and height of one icon's cell: a square in the grid, a
    full-width row in the list."""
    if win.list_view:
        return grid_area(win)[2], LIST_H
    size = cell_size(win)
    return size, size


def grid_rows(win: Window) -> int:
    return max(1, int(grid_area(win)[3] // cell_dims(win)[1]))


def ex_scroll_rects(win: Window) -> Tuple[Rect, Rect]:
    gx, gy, gw, gh = grid_area(win)
    x = win.x + win.w - 30
    return ((x, gy + 2, 24, 24), (x, gy + gh - 26, 24, 24))


def start_tiles() -> List[Rect]:
    px, py, _pw, _ph = START_PANEL
    return [(px + 12 + (i % 3) * (TILE_W + 8),
             py + 44 + (i // 3) * (TILE_H + 8), TILE_W, TILE_H)
            for i in range(6)]


def all_apps_rect() -> Rect:
    px, py, pw, _ph = START_PANEL
    return (px + pw - 130, py + 8, 120, 28)


def start_rows(count: int) -> List[Rect]:
    px, py, pw, _ph = START_PANEL
    return [(px + 10, py + 44 + i * ITEM_H, pw - 20, ITEM_H)
            for i in range(count)]


def desktop_icon_rect(index: int) -> Rect:
    column, row = divmod(index, ICONS_PER_COLUMN)
    return (8 + column * ICON_W, 8 + row * ICON_H, ICON_W - 4, ICON_H - 4)


def popup_buttons(safe_left: bool) -> Tuple[Rect, Rect]:
    """The safe button, then the one that resets the window."""
    x, y, w, h = POPUP_RECT
    left = (x + 40, y + h - 46, 140, 34)
    right = (x + w - 180, y + h - 46, 140, 34)
    return (left, right) if safe_left else (right, left)


class Popup(NamedTuple):
    #: The click after which it arrives.
    at: int
    window: int
    safe_left: bool


class Desktop:
    """One round's screen, for the player or the reference alike."""

    def __init__(self, dealt: 'Deal') -> None:
        self.level = dealt.level
        self.windows, self.notes, self.controls = build(dealt)
        self.nodes = build_files(dealt)
        #: The file explorer, if this rung has one.
        self.explorer: Optional[Window] = None
        if dealt.level.explorer:
            ex = Window(len(self.windows), EXPLORER, [[]], 1, [], False)
            ex.kind, ex.w = 'explorer', EXPLORER_W
            ex.x, ex.y = dealt.explorer_at
            ex.closed = dealt.level.explorer_closed
            ex.places = [Place(self.nodes[HOME])
                         for _t in range(dealt.level.ex_tabs)]
            if len(ex.places) > 1:
                ex.places[1].path = self.nodes[DOCUMENTS]
            self.explorer = ex
        #: Every app: the settings windows, then the explorer.
        self.apps: List[Window] = self.windows + (
            [self.explorer] if self.explorer else [])
        self.pinned: List[Window] = [self.windows[i] for i in dealt.pinned]
        if self.explorer:
            self.pinned.insert(0, self.explorer)
        self.shortcuts: List[Window] = [self.windows[i]
                                        for i in dealt.shortcuts]
        #: Bottom first; sticky notes always last.
        self.order: List[Window] = [self.apps[i] for i in dealt.order]
        self.order += self.notes
        #: (file, folder it has to end up in), in the order the card
        #: lists them.
        self.moves: List[Tuple[Node, Node]] = [
            (self.nodes[a], self.nodes[b]) for a, b in dealt.moves]
        self.clipboard: Optional[Node] = None
        #: Whether Paste copies what is on the clipboard or moves it.
        self.copying = False
        #: (file, folder a copy must be in, folder it must stay in).
        self.copies: List[Tuple[Node, Node, Node]] = [
            (self.nodes[a], self.nodes[b], self.nodes[a].parent)
            for a, b in dealt.copies]
        for node, dest in self.moves:
            if node.parent is self.nodes[TRASH]:
                node.origin = dest
        if self.explorer is not None:
            self.explorer.list_view = dealt.list_view
        #: A right-click menu: (what, node, window or None, x, y).
        self.context: Optional[Tuple] = None
        #: The card hides after the first click, if the rung says so;
        #: a peek shows it until the next click.
        self.hide_card = dealt.hide_card
        self.peeking = False
        #: What is picked on the desktop, and what the last click hit:
        #: a second click on the same icon right after the first opens it.
        self.picked: Optional[Tuple] = None
        self.last: Optional[Tuple] = None
        self.start_all = False
        self.goals: Tuple[Tuple[int, int], ...] = dealt.goals
        self.popups: Tuple[Popup, ...] = dealt.popups
        self.pointer = START
        self.clicks = 0
        self.dialog: Optional[Dialog] = None
        #: (window, menu, open submenu item or None).
        self.menu: Optional[Tuple[Window, int, Optional[int]]] = None
        self.dropdown: Optional[Control] = None
        self.start_open = False
        self.popup: Optional[Popup] = None
        self.next_popup = 0
        self.held: Optional[Tuple[float, float]] = None
        self.done = False

    # --- where things are ------------------------------------------------

    def row_rect(self, control: Control) -> Optional[Rect]:
        """Where *control*'s row is now, or None if it is not showing."""
        if control.dialog is not None:
            if self.dialog is not control.dialog:
                return None
            x, y, _w, _h = self.dialog_rect()
            return (x, y + TITLE_H + control.row * ROW_H, DIALOG_W, ROW_H)
        win = control.window
        if not win.shown or win.active != control.tab:
            return None
        shown = control.row - win.scroll[control.tab]
        if not 0 <= shown < win.rows:
            return None
        return (win.x, win.content_top + shown * ROW_H, win.w, ROW_H)

    def control_rect(self, control: Control) -> Optional[Rect]:
        row = self.row_rect(control)
        if row is None:
            return None
        width = DIALOG_W if control.dialog else control.window.w
        return widget_rect(row[0], row[1], width)

    def dialog_rect(self) -> Rect:
        rows = len(self.dialog.controls)
        h = TITLE_H + rows * ROW_H + 50
        return ((SCREEN_W - DIALOG_W) / 2, (WORK_H - h) / 2, DIALOG_W, h)

    def dialog_buttons(self) -> Tuple[Rect, Rect]:
        x, y, w, h = self.dialog_rect()
        return ((x + w - 200, y + h - 42, 88, 32),
                (x + w - 104, y + h - 42, 92, 32))

    def menu_items(self) -> List[Rect]:
        if self.menu is None:
            return []
        win, index, _sub = self.menu
        mx, my, _mw, mh = menu_rects(win)[index]
        return [(mx, my + mh + i * ITEM_H, ITEM_W, ITEM_H)
                for i in range(len(win.menus[index][1]))]

    def submenu_items(self) -> List[Rect]:
        if self.menu is None or self.menu[2] is None:
            return []
        win, index, sub = self.menu
        ix, iy, iw, _ih = self.menu_items()[sub]
        item = win.menus[index][1][sub]
        return [(ix + iw, iy + i * ITEM_H, ITEM_W, ITEM_H)
                for i in range(len(item.dialogs))]

    def taskbar_buttons(self) -> List[Tuple[Window, Rect]]:
        """A button for each window that is open, minimised or not."""
        found = []
        for win in self.apps:
            if not win.closed:
                found.append((win, (84 + len(found) * 100, WORK_H + 6, 94,
                                    TASKBAR_H - 12)))
        return found

    def start_items(self) -> List[Tuple[Window, Rect]]:
        """The Start panel's apps where they are: pinned tiles, or the
        list of every app by name once All apps is open."""
        if not self.start_open:
            return []
        if self.start_all:
            apps = sorted(self.apps, key=lambda w: w.title)
            return list(zip(apps, start_rows(len(apps))))
        return list(zip(self.pinned, start_tiles()))

    def desktop_icons(self) -> List[Tuple[Tuple, Rect]]:
        """What lies on the desktop: ('explorer',), ('trash',),
        ('app', window) for a shortcut, ('node', node) for a file or
        folder saved there."""
        items: List[Tuple] = []
        if self.explorer is not None:
            items += [('explorer',), ('trash',)]
            items += [('app', win) for win in self.shortcuts]
            items += [('node', node)
                      for node in self.nodes[DESKTOP_DIR].listing()]
        return [(item, desktop_icon_rect(i)) for i, item in enumerate(items)]

    def icon_at(self, x: float, y: float) -> Optional[Tuple]:
        if y >= WORK_H or self.window_at(x, y) is not None:
            return None
        for item, rect in self.desktop_icons():
            if inside(rect, x, y):
                return item
        return None

    def icon_rects(self, win: Window) -> List[Tuple[Node, Rect]]:
        """The explorer's icons that are showing, and where."""
        place = win.places[win.place]
        listing = place.path.listing()
        rows, columns = grid_rows(win), ex_columns(win)
        most = max(0, -(-len(listing) // columns) - rows)
        place.scroll = max(0, min(place.scroll, most))
        gx, gy, _gw, _gh = grid_area(win)
        cw, ch = cell_dims(win)
        found = []
        first = place.scroll * columns
        for index, node in enumerate(listing[first:first + rows * columns]):
            row, column = divmod(index, columns)
            found.append((node, (gx + column * cw, gy + row * ch, cw, ch)))
        return found

    def ex_scrolls(self, win: Window) -> bool:
        place = win.places[win.place]
        return (-(-len(place.path.listing()) // ex_columns(win))
                > grid_rows(win))

    def window_at(self, x: float, y: float) -> Optional[Window]:
        if y >= WORK_H:
            return None
        for win in reversed(self.order):
            if win.shown and inside((win.x, win.y, win.w, win.h), x, y):
                return win
        return None

    def overlay_at(self, x: float, y: float) -> bool:
        """Whether a popup, menu, list or dialog is over this point."""
        if self.popup is not None and inside(POPUP_RECT, x, y):
            return True
        if self.dialog is not None and inside(self.dialog_rect(), x, y):
            return True
        if any(inside(r, x, y) for r in
               self.menu_items() + self.submenu_items()):
            return True
        if self.start_open and inside(START_PANEL, x, y):
            return True
        if self.dropdown is not None:
            rect = self.control_rect(self.dropdown)
            if rect and any(inside(r, x, y)
                            for r in dropdown_items(rect, self.dropdown)):
                return True
        return False

    def reachable(self, rect: Rect, win: Optional[Window]
                  ) -> Optional[Tuple[int, int]]:
        """A grid point in *rect* that a click would reach -- on screen,
        on *win* and not under anything when *win* is given -- nearest
        the rect's middle."""
        x, y, w, h = rect
        cx, cy = x + w / 2, y + h / 2
        best = None
        gx0 = max(0, int((x + GRID - 1) // GRID) * GRID)
        gy0 = max(0, int((y + GRID - 1) // GRID) * GRID)
        for gy in range(gy0, int(min(y + h, SCREEN_H)), GRID):
            for gx in range(gx0, int(min(x + w, SCREEN_W)), GRID):
                if not inside(rect, gx, gy):
                    continue
                if win is not None and (self.window_at(gx, gy) is not win
                                        or self.overlay_at(gx, gy)):
                    continue
                gap = (gx - cx) ** 2 + (gy - cy) ** 2
                if best is None or gap < best[0]:
                    best = (gap, (gx, gy))
        return None if best is None else best[1]

    def raise_window(self, win: Window) -> None:
        self.order.remove(win)
        if win.pinned:
            self.order.append(win)
            return
        notes = [w for w in self.order if w.pinned]
        at = self.order.index(notes[0]) if notes else len(self.order)
        self.order.insert(at, win)

    # --- the pointer ------------------------------------------------------

    def move(self, dx: float, dy: float) -> None:
        x, y = self.pointer
        self.pointer = (max(0, min(SCREEN_W - GRID, x + dx)),
                        max(0, min(SCREEN_H - GRID, y + dy)))

    def press(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        if self.done:
            return
        if x is None:
            x, y = self.pointer
        self.pointer = (x, y)
        self.held = (x, y)
        self._select_on_press(x, y)

    def _select_on_press(self, x: float, y: float) -> None:
        """An icon is picked the moment the button goes down, as on a
        real desktop, so a drag shows what it carries before it moves."""
        if self._overlay_open() or y >= WORK_H:
            return
        win = self.window_at(x, y)
        if win is not None:
            if win.kind != 'explorer' or win is not self.order[-1]:
                return
            for node, rect in self.icon_rects(win):
                if inside(rect, x, y):
                    win.places[win.place].selected = node
            return
        item = self.icon_at(x, y)
        if item is not None:
            self.picked = _icon_key(item)

    def drag_preview(self) -> Optional[Tuple]:
        """What letting go here would do, while the button is held and
        the pointer has moved: ('icon', node, dest, rect) with the folder
        it would land in (None if it would not) and the target's rect;
        ('move', win, rect) or ('resize', win, rect) with the window's
        outline after. None for anything else."""
        if self.held is None or self._overlay_open():
            return None
        sx, sy = self.held
        x, y = self.pointer
        if abs(x - sx) <= STILL and abs(y - sy) <= STILL:
            return None
        if not self.draggable(sx, sy):
            return None
        win = self.window_at(sx, sy)
        node = None
        if win is None:
            item = self.icon_at(sx, sy)
            node = item[1]
        elif win.kind == 'explorer':
            node = next((n for n, r in self.icon_rects(win)
                         if inside(r, sx, sy)), None)
        if node is not None:
            dest, rect = self.drop_target(x, y)
            if dest is not None and (dest.within(node) or node.parent is dest
                                     or not dest.folder):
                dest = None
            return ('icon', node, dest, rect)
        dx = int(round((x - sx) / GRID)) * GRID
        dy = int(round((y - sy) / GRID)) * GRID
        if win.kind == 'app' and inside(grip_rect(win), sx, sy):
            rows = max(1, min(win.most_rows,
                              win.rows + int(round(dy / float(ROW_H)))))
            return ('resize', win, (win.x, win.y, win.w,
                                    win.h + (rows - win.rows) * ROW_H))
        nx = max(60 - win.w, min(SCREEN_W - 60, win.x + dx))
        ny = max(0, min(WORK_H - TITLE_H, win.y + dy))
        # A window dragged low keeps what fits, as letting go will.
        return ('move', win, (nx, ny, win.w, min(win.h, WORK_H - ny)))

    def release(self, x: Optional[float] = None,
                y: Optional[float] = None) -> None:
        """Let go: a click where it was pressed, or a drag to here.
        Either costs one."""
        if self.held is None or self.done:
            return
        if x is None:
            x, y = self.pointer
        self.pointer = (x, y)
        sx, sy = self.held
        self.held = None
        self.clicks += 1
        if abs(x - sx) <= STILL and abs(y - sy) <= STILL:
            self._click_at(sx, sy)
        elif self._overlay_open() or not self.draggable(sx, sy):
            # With anything open, or from something that does not move,
            # a drag is only a click where it began: a hand that slips a
            # little while clicking a switch still clicks it.
            self._click_at(sx, sy)
        else:
            self._drag(sx, sy, x, y)
        self._arrive()

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        """A click at (x, y), or where the pointer is. Always a point."""
        self.press(x, y)
        self.release()

    def act(self, action: Action) -> None:
        if action[0] == 'click':
            self.click(*action[1])
        else:
            self.press(*action[1])
            self.release(*action[2])

    def _overlay_open(self) -> bool:
        return (self.popup is not None or self.dialog is not None
                or self.menu is not None or self.dropdown is not None
                or self.start_open or self.context is not None)

    @property
    def card_shown(self) -> bool:
        return not self.hide_card or self.clicks == 0 or self.peeking

    # --- the right button --------------------------------------------------

    def right_click(self, x: Optional[float] = None,
                    y: Optional[float] = None) -> None:
        """The right button: a menu of what can be done to what is under
        the pointer. Costs one, like any click."""
        if self.done or self.held is not None:
            return
        if x is None:
            x, y = self.pointer
        self.pointer = (x, y)
        self.clicks += 1
        self._previous, self.last = self.last, None
        self.peeking = False
        if self.popup is None and self.dialog is None:
            self.menu = self.dropdown = None
            self.start_open = self.start_all = False
            self.context = self._context_for(x, y)
        self._arrive()

    def _context_for(self, x: float, y: float) -> Optional[Tuple]:
        if y >= WORK_H:
            return None
        win = self.window_at(x, y)
        if win is None:
            item = self.icon_at(x, y)
            if item is None:
                self.picked = None
                return ('folder', self.nodes[DESKTOP_DIR], None, x, y)
            self.picked = _icon_key(item)
            if item[0] == 'node':
                return ('node', item[1], None, x, y)
            return None
        self.raise_window(win)
        if win.kind != 'explorer':
            return None
        place = win.places[win.place]
        for node, rect in self.icon_rects(win):
            if inside(rect, x, y):
                place.selected = node
                return ('node', node, win, x, y)
        if inside(grid_area(win), x, y):
            place.selected = None
            return ('folder', place.path, win, x, y)
        return None

    def context_items(self) -> List[Tuple[str, Rect]]:
        """The right-click menu's items where they are."""
        if self.context is None:
            return []
        what, node, win, x, y = self.context
        trash = self.nodes[TRASH]
        if what == 'node':
            names = (['Open'] if node.folder else []) + ['Cut', 'Copy']
            if node.within(trash):
                if node.origin is not None and node.parent is trash:
                    names.append('Restore')
            else:
                names.append('Delete')
        else:
            names = (['Paste'] if self.clipboard is not None else [])
            if win is not None:
                names.append('View')
        if not names:
            return []
        h = len(names) * ITEM_H
        left = min(x, SCREEN_W - CONTEXT_W - 2)
        top = min(y, WORK_H - h - 2)
        return [(name, (left, top + i * ITEM_H, CONTEXT_W, ITEM_H))
                for i, name in enumerate(names)]

    def _click_context(self, x: float, y: float) -> None:
        what, node, win, _x, _y = self.context
        items = self.context_items()
        self.context = None
        for name, rect in items:
            if not inside(rect, x, y):
                continue
            if name == 'Open':
                if win is None:
                    self._open_icon(('node', node))
                else:
                    self.navigate(win.places[win.place], node)
            elif name in ('Cut', 'Copy'):
                self.clipboard, self.copying = node, name == 'Copy'
            elif name == 'Delete':
                self.move_file(node, self.nodes[TRASH])
            elif name == 'Restore':
                self.move_file(node, node.origin)
            elif name == 'Paste':
                self.paste(node)
            elif name == 'View':
                win.list_view = not win.list_view
                win.places[win.place].scroll = 0
            return

    def paste(self, dest: Node) -> None:
        if self.clipboard is None:
            return
        if self.copying:
            self.copy_file(self.clipboard, dest)
        elif self.move_file(self.clipboard, dest):
            self.clipboard = None

    def copy_file(self, node: Node, dest: Node) -> Optional[Node]:
        """A copy of *node* (and all inside it) in *dest*."""
        if not dest.folder or dest.within(node) \
                or dest.within(self.nodes[TRASH]):
            return None
        taken = {c.name for c in dest.children}
        name = node.name
        if name in taken:
            stem, dot, ext = name.rpartition('.')
            if not dot or node.folder:
                stem, ext = name, ''
            name = '%s - Copy%s' % (stem, '.' + ext if ext else '')
            number = 2
            while name in taken:
                name = '%s - Copy (%d)%s' % (stem, number,
                                             '.' + ext if ext else '')
                number += 1

        def clone(source: Node, parent: Node, called: str) -> Node:
            twin = Node(len(self.nodes), called, source.folder, source.kind,
                        parent)
            self.nodes.append(twin)
            parent.children.append(twin)
            for child in list(source.children):
                clone(child, twin, child.name)
            return twin
        return clone(node, dest, name)

    def copied(self, goal: Tuple[Node, Node, Node]) -> bool:
        node, dest, source = goal
        return node.parent is source and any(
            c is not node and c.name == node.name and c.folder == node.folder
            for c in dest.children)

    def _arrive(self) -> None:
        """A popup due by this click arrives now."""
        if self.popup is None and self.next_popup < len(self.popups) \
                and self.clicks >= self.popups[self.next_popup].at \
                and not self.done:
            self.popup = self.popups[self.next_popup]
            self.next_popup += 1
            self.menu = None
            self.dropdown = None
            self.context = None
            self.start_open = self.start_all = False

    # --- what a click does ----------------------------------------------

    def _click_at(self, x: float, y: float) -> None:
        self._previous, self.last = self.last, None
        peeked, self.peeking = self.peeking, False
        if self.popup is not None:
            safe, reset = popup_buttons(self.popup.safe_left)
            if inside(safe, x, y):
                self.popup = None
            elif inside(reset, x, y):
                for control in self.windows[self.popup.window].controls():
                    control.value = control.shown = control.start
                self.popup = None
            return
        if self.dropdown is not None:
            control, self.dropdown = self.dropdown, None
            rect = self.control_rect(control)
            for value, item in enumerate(dropdown_items(rect, control)):
                if inside(item, x, y):
                    self._set(control, value)
            return
        if self.dialog is not None:
            self._click_dialog(x, y)
            return
        if self.context is not None:
            self._click_context(x, y)
            return
        if self.menu is not None:
            self._click_menu(x, y)
            return
        if self.start_open:
            self._click_start(x, y)
            return
        if y >= WORK_H:
            if self.hide_card and inside(PEEK_RECT, x, y):
                self.peeking = not peeked
                return
            self._click_taskbar(x, y)
            return
        win = self.window_at(x, y)
        if win is None:
            self._click_desktop(x, y)
            return
        self.raise_window(win)
        if inside(close_rect(win), x, y):
            # Closing throws away whatever it had not applied.
            for control in win.controls():
                control.shown = control.value
            win.closed = True
            return
        if inside(minimise_rect(win), x, y):
            win.minimised = True
            return
        if win.kind == 'explorer':
            self._click_explorer(win, x, y)
            return
        for index, rect in enumerate(menu_rects(win)):
            if inside(rect, x, y):
                self.menu = (win, index, None)
                return
        for index, rect in enumerate(tab_rects(win)):
            if inside(rect, x, y):
                win.active = index
                return
        tab = win.active
        if win.scrolls(tab):
            up, down = scroll_rects(win)
            most = len(win.tabs[tab]) - win.rows
            if inside(up, x, y):
                win.scroll[tab] = max(0, win.scroll[tab] - 1)
                return
            if inside(down, x, y):
                win.scroll[tab] = min(most, win.scroll[tab] + 1)
                return
        if win.apply and inside(apply_rect(win), x, y):
            for page in win.tabs:
                for control in page:
                    control.value = control.shown
            return
        for control in win.tabs[tab]:
            self._click_control(control, x, y)

    def open_app(self, win: Window) -> None:
        win.closed = win.minimised = False
        self.raise_window(win)

    def _click_start(self, x: float, y: float) -> None:
        if inside(all_apps_rect(), x, y):
            self.start_all = not self.start_all
            return
        for win, rect in self.start_items():
            if inside(rect, x, y):
                self.open_app(win)
                self.start_open = self.start_all = False
                return
        if not inside(START_PANEL, x, y):
            self.start_open = self.start_all = False

    def _click_desktop(self, x: float, y: float) -> None:
        item = self.icon_at(x, y)
        if item is None:
            self.picked = None
            return
        key = _icon_key(item)
        if self.picked == key and self._previous == key:
            self._open_icon(item)
        self.picked = key
        self.last = key

    def _open_icon(self, item: Tuple) -> None:
        if item[0] == 'app':
            self.open_app(item[1])
            return
        ex = self.explorer
        if item[0] == 'node' and not item[1].folder:
            return
        self.open_app(ex)
        place = ex.places[ex.place]
        if item[0] == 'trash':
            self.navigate(place, self.nodes[TRASH])
        elif item[0] == 'node':
            self.navigate(place, item[1])

    def navigate(self, place: Place, node: Node) -> None:
        if place.path is node:
            return
        place.history.append(place.path)
        place.path = node
        place.scroll = 0
        place.selected = None

    def move_file(self, node: Node, dest: Node) -> bool:
        """Put *node* in *dest*, unless that is where it is or inside it."""
        if not dest.folder or dest.within(node) or node.parent is dest \
                or node.ident in (HOME, TRASH) or node.ident < len(PLACES):
            return False
        if dest is self.nodes[TRASH]:
            node.origin = node.parent
        node.parent.children.remove(node)
        dest.children.append(node)
        node.parent = dest
        if self.clipboard is node:
            self.clipboard = None
        if self.explorer is not None:
            for place in self.explorer.places:
                if place.selected is node:
                    place.selected = None
        return True

    def _click_explorer(self, win: Window, x: float, y: float) -> None:
        place = win.places[win.place]
        for name, rect in tool_rects(win):
            if not inside(rect, x, y):
                continue
            if name == 'Back' and place.history:
                place.path = place.history.pop()
                place.scroll, place.selected = 0, None
            elif name == 'Up' and place.path.parent is not None:
                self.navigate(place, place.path.parent)
            elif name in ('Cut', 'Copy') and place.selected is not None:
                self.clipboard = place.selected
                self.copying = name == 'Copy'
            elif name == 'Paste' and self.clipboard is not None:
                self.paste(place.path)
            elif name == 'View':
                win.list_view = not win.list_view
                place.scroll = 0
            elif name == 'Delete' and place.selected is not None \
                    and not place.selected.within(self.nodes[TRASH]):
                self.move_file(place.selected, self.nodes[TRASH])
            return
        for index, rect in enumerate(place_tab_rects(win)):
            if inside(rect, x, y):
                win.place = index
                return
        if len(win.places) < MOST_TABS and inside(plus_rect(win), x, y):
            win.places.append(Place(self.nodes[HOME]))
            win.place = len(win.places) - 1
            return
        for index, rect in enumerate(sidebar_rects(win)):
            if inside(rect, x, y):
                self.navigate(place, self.nodes[index])
                return
        if self.ex_scrolls(win):
            up, down = ex_scroll_rects(win)
            if inside(up, x, y):
                place.scroll = max(0, place.scroll - 1)
                return
            if inside(down, x, y):
                place.scroll += 1
                self.icon_rects(win)          # clamps it
                return
        for node, rect in self.icon_rects(win):
            if inside(rect, x, y):
                key = ('ex', node.ident)
                if place.selected is node and self._previous == key \
                        and node.folder:
                    self.navigate(place, node)
                else:
                    place.selected = node
                    self.last = key
                return
        if inside(grid_area(win), x, y):
            place.selected = None

    def _click_taskbar(self, x: float, y: float) -> None:
        if inside(DONE_RECT, x, y):
            self.done = True
            return
        if inside(START_RECT, x, y):
            self.start_open, self.start_all = True, False
            return
        for win, rect in self.taskbar_buttons():
            if inside(rect, x, y):
                win.minimised = False
                self.raise_window(win)
                return

    def _click_menu(self, x: float, y: float) -> None:
        win, index, sub = self.menu
        items = win.menus[index][1]
        for which, rect in enumerate(self.submenu_items()):
            if inside(rect, x, y):
                self.menu = None
                self._open(items[sub].dialogs[which])
                return
        for which, rect in enumerate(self.menu_items()):
            if inside(rect, x, y):
                if isinstance(items[which], Submenu):
                    self.menu = (win, index, which)
                else:
                    self.menu = None
                    self._open(items[which])
                return
        self.menu = None

    def _click_dialog(self, x: float, y: float) -> None:
        cancel, ok = self.dialog_buttons()
        if inside(ok, x, y):
            for control in self.dialog.controls:
                control.value = control.shown
            self.dialog = None
        elif inside(cancel, x, y):
            for control in self.dialog.controls:
                control.shown = control.value
            self.dialog = None
        else:
            for control in self.dialog.controls:
                self._click_control(control, x, y)

    def _open(self, dialog: Dialog) -> None:
        for control in dialog.controls:
            control.shown = control.value
        self.dialog = dialog

    def _click_control(self, control: Control, x: float, y: float) -> None:
        rect = self.control_rect(control)
        if rect is None or not control.enabled:
            return
        for value, part in enumerate(parts(control, rect)):
            if not inside(part, x, y):
                continue
            if control.kind == 'toggle':
                self._set(control, 1 - control.shown)
            elif control.kind == 'dropdown':
                self.dropdown = control
            elif control.kind == 'stepper':
                step = -1 if value == 0 else 1
                self._set(control, max(0, min(control.count - 1,
                                              control.shown + step)))
            else:
                self._set(control, value)
            return

    def _set(self, control: Control, value: int) -> None:
        control.shown = value
        if control.dialog is None and not control.window.apply:
            control.value = value

    def draggable(self, x: float, y: float) -> bool:
        """Whether a drag from (x, y) can move anything: a title bar
        (not its buttons), a window's corner, or a file or folder icon."""
        if y >= WORK_H:
            return False
        win = self.window_at(x, y)
        if win is None:
            item = self.icon_at(x, y)
            return item is not None and item[0] == 'node'
        if win.kind == 'explorer':
            if any(inside(rect, x, y) for _n, rect in self.icon_rects(win)):
                return True
        elif win.kind == 'app' and inside(grip_rect(win), x, y):
            return True
        return inside(title_rect(win), x, y) and not (
            inside(close_rect(win), x, y)
            or inside(minimise_rect(win), x, y))

    def _drag(self, sx: float, sy: float, x: float, y: float) -> None:
        if sy >= WORK_H:
            return
        source = self._dragged(sx, sy)
        if source is not None:
            dest = self._dropped_on(x, y)
            if dest is not None:
                self.move_file(source, dest)
            return
        win = self.window_at(sx, sy)
        if win is None:
            return
        self.raise_window(win)
        dx = int(round((x - sx) / GRID)) * GRID
        dy = int(round((y - sy) / GRID)) * GRID
        if win.kind == 'app' and inside(grip_rect(win), sx, sy):
            rows = win.rows + int(round(dy / float(ROW_H)))
            win.rows = max(1, min(win.most_rows, rows))
            for tab, page in enumerate(win.tabs):
                win.scroll[tab] = max(0, min(win.scroll[tab],
                                             len(page) - win.rows))
            return
        if inside(title_rect(win), sx, sy) and not (
                inside(close_rect(win), sx, sy)
                or inside(minimise_rect(win), sx, sy)):
            win.x = max(60 - win.w, min(SCREEN_W - 60, win.x + dx))
            win.y = max(0, min(WORK_H - TITLE_H, win.y + dy))
            if win.y + win.h > WORK_H:
                # A window dragged low keeps what fits.
                win.rows = max(1, (WORK_H - win.y - win.chrome) // ROW_H)
                for tab, page in enumerate(win.tabs):
                    win.scroll[tab] = max(0, min(win.scroll[tab],
                                                 len(page) - win.rows))

    def _dragged(self, x: float, y: float) -> Optional[Node]:
        """The file or folder an icon drag starts from, if any."""
        win = self.window_at(x, y)
        if win is not None and win.kind == 'explorer':
            for node, rect in self.icon_rects(win):
                if inside(rect, x, y):
                    self.raise_window(win)
                    return node
            return None
        item = self.icon_at(x, y)
        if item is not None and item[0] == 'node':
            return item[1]
        return None

    def _dropped_on(self, x: float, y: float) -> Optional[Node]:
        """The folder a drop at (x, y) puts things in, if any."""
        return self.drop_target(x, y)[0]

    def drop_target(self, x: float, y: float
                    ) -> Tuple[Optional[Node], Optional[Rect]]:
        """The folder a drop at (x, y) puts things in, if any, and the
        rect of what it was dropped on (the whole desktop for bare
        desktop)."""
        if y >= WORK_H:
            return None, None
        win = self.window_at(x, y)
        if win is not None:
            if win.kind != 'explorer':
                return None, None
            for node, rect in self.icon_rects(win):
                if inside(rect, x, y):
                    return (node if node.folder else None), rect
            for index, rect in enumerate(sidebar_rects(win)):
                if inside(rect, x, y):
                    return self.nodes[index], rect
            for index, rect in enumerate(place_tab_rects(win)):
                if inside(rect, x, y):
                    return win.places[index].path, rect
            if inside(grid_area(win), x, y):
                return win.places[win.place].path, grid_area(win)
            return None, None
        for item, rect in self.desktop_icons():
            if inside(rect, x, y):
                if item[0] == 'trash':
                    return self.nodes[TRASH], rect
                if item[0] == 'node' and item[1].folder:
                    return item[1], rect
                return None, rect
        return self.nodes[DESKTOP_DIR], (0, 0, SCREEN_W, WORK_H)

    # --- the verdict -----------------------------------------------------

    def met(self, goal: Tuple[int, int]) -> bool:
        ident, value = goal
        return self.controls[ident].value == value

    @property
    def solved(self) -> bool:
        return (all(self.met(goal) for goal in self.goals)
                and all(node.parent is dest for node, dest in self.moves)
                and all(self.copied(goal) for goal in self.copies))


# --- dealing a desktop ------------------------------------------------------

class Spec(NamedTuple):
    label: str
    kind: str
    count: int
    value: int
    words: Tuple[str, ...]


#: A menu entry: ('dialog', title, controls) or ('sub', name, dialogs).
MenuEntry = Tuple


class Deal(NamedTuple):
    level: Grade
    titles: Tuple[str, ...]
    tabs: Tuple[Tuple[Tuple[int, ...], ...], ...]
    menus: Tuple[Tuple[Tuple[str, Tuple[MenuEntry, ...]], ...], ...]
    applies: Tuple[bool, ...]
    places: Tuple[Tuple[int, int], ...]
    #: Bottom window first.
    order: Tuple[int, ...]
    minimised: Tuple[int, ...]
    closed: Tuple[int, ...]
    #: (text, x, y) for each sticky note.
    notes: Tuple[Tuple[str, int, int], ...]
    popups: Tuple[Popup, ...]
    specs: Tuple[Spec, ...]
    #: (control, (control it needs, value)), for greyed-out controls.
    requires: Tuple[Tuple[int, Tuple[int, int]], ...]
    #: (control, value), in the order the card lists them.
    goals: Tuple[Tuple[int, int], ...]
    #: Every folder and file: (name, folder, kind, parent index); the
    #: first seven are :data:`PLACES`.
    files: Tuple[Tuple[str, bool, str, int], ...]
    #: (file, folder it must end up in), in card order.
    moves: Tuple[Tuple[int, int], ...]
    explorer_at: Tuple[int, int]
    #: Apps pinned to Start besides the explorer, and apps with a
    #: shortcut on the desktop.
    pinned: Tuple[int, ...]
    shortcuts: Tuple[int, ...]
    #: (file, folder a copy of it must be in), in card order.
    copies: Tuple[Tuple[int, int], ...] = ()
    list_view: bool = False
    hide_card: bool = False


def build_files(dealt: Deal) -> List[Node]:
    nodes: List[Node] = []
    for ident, (name, folder, kind, parent) in enumerate(dealt.files):
        node = Node(ident, name, folder, kind,
                    nodes[parent] if parent >= 0 else None)
        if node.parent is not None:
            node.parent.children.append(node)
        nodes.append(node)
    return nodes


def _grow_files(level: Grade, rng: random.Random
                ) -> List[Tuple[str, bool, str, int]]:
    files: List[Tuple[str, bool, str, int]] = [
        (name, True, 'folder', -1 if name in ('Home', 'Trash') else HOME)
        for name in PLACES]
    if not level.explorer:
        return files
    used = set()

    def file_in(parent: int, kinds: Tuple[str, ...]) -> None:
        kind = rng.choice(kinds)
        ext = rng.choice(EXTENSIONS[kind])
        base = rng.choice(FILE_WORDS)
        name, number = base + ext, 2
        while name in used:
            name, number = '%s%d%s' % (base, number, ext), number + 1
        used.add(name)
        files.append((name, False, kind, parent))

    def grow(parent: int, depth: int, kinds: Tuple[str, ...]) -> None:
        for _f in range(rng.randint(1, 3)):
            file_in(parent, kinds)
        if depth > level.depth:
            return
        # Wide near the top, a single thread further down: deep enough
        # to be a long way, not so bushy that a round has thousands.
        count = (rng.randint(1, 3) if depth == 1 else
                 rng.randint(1, 2) if depth == 2 else
                 2 if rng.random() < 0.25 else 1)
        for name in rng.sample(FOLDERS, count):
            files.append((name, True, 'folder', parent))
            grow(len(files) - 1, depth + 1, kinds)

    for place in range(2, 6):
        grow(place, 1, HOLDS[place])
    for _f in range(level.desktop_files):
        file_in(DESKTOP_DIR, HOLDS[DESKTOP_DIR])
    return files


def build(dealt: Deal) -> Tuple[List[Window], List[Window], List[Control]]:
    controls = [Control(i, s.label, s.kind, s.count, s.value, s.words)
                for i, s in enumerate(dealt.specs)]

    def dialog_of(title, members, menu, item, sub=None):
        dialog = Dialog(title, [controls[i] for i in members])
        dialog.menu, dialog.item, dialog.sub = menu, item, sub
        for row, control in enumerate(dialog.controls):
            control.dialog, control.row = dialog, row
        return dialog

    windows = []
    for index, title in enumerate(dealt.titles):
        tabs = [[controls[i] for i in page] for page in dealt.tabs[index]]
        menus = []
        for menu_index, (name, entries) in enumerate(dealt.menus[index]):
            items: List[Item] = []
            for item_index, entry in enumerate(entries):
                if entry[0] == 'dialog':
                    items.append(dialog_of(entry[1], entry[2], menu_index,
                                           item_index))
                else:
                    items.append(Submenu(entry[1], [
                        dialog_of(t, m, menu_index, item_index, sub)
                        for sub, (t, m) in enumerate(entry[2])]))
            menus.append((name, items))
        win = Window(index, title, tabs, dealt.level.rows, menus,
                     dealt.applies[index])
        win.x, win.y = dealt.places[index]
        win.minimised = index in dealt.minimised
        win.closed = index in dealt.closed
        for tab, page in enumerate(tabs):
            for row, control in enumerate(page):
                control.window, control.tab, control.row = win, tab, row
        for control in win.controls():
            control.window = win
        for _name, items in menus:
            for item in items:
                for dialog in (item.dialogs if isinstance(item, Submenu)
                               else [item]):
                    dialog.window = win
        windows.append(win)
    notes = []
    for number, (text, x, y) in enumerate(dealt.notes):
        note = Window(len(windows) + number, 'Note', [[]], 2, [], False,
                      note=text)
        note.x, note.y = x, y
        notes.append(note)
    for ident, (other, value) in dealt.requires:
        controls[ident].requires = (controls[other], value)
    return windows, notes, controls


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    rng = rng or random.Random(seed)
    level = grade(rung)
    labels: List[str] = []
    specs: List[Spec] = []

    def make() -> int:
        kind = rng.choice(level.kinds)
        if kind == 'toggle':
            count, words = 2, ()
        elif kind in ('choice', 'dropdown'):
            count = rng.randint(3, 4) if kind == 'choice' \
                else rng.randint(3, 6)
            start = rng.randrange(len(WORDS) - count + 1)
            words = WORDS[start:start + count]
        elif kind == 'colour':
            count = rng.randint(4, 6)
            words = tuple(name for name, _rgb in
                          rng.sample(COLOURS, count))
        elif kind == 'slider':
            count, words = rng.randint(4, 6), ()
        else:
            count, words = rng.randint(5, 9), ()
        specs.append(Spec(labels.pop(), kind, count, rng.randrange(count),
                          words))
        return len(specs) - 1

    titles = rng.sample(TITLES, level.windows)
    dialog_titles = rng.sample(DIALOGS, level.windows * level.dialogs)
    tabs, menus = [], []
    for _index in range(level.windows):
        # Names are unique within a window, which is all the card needs:
        # it names the window, or the dialog, with every setting.
        labels[:] = rng.sample(LABELS, len(LABELS))
        tabs.append(tuple(tuple(make() for _r in range(level.per_tab))
                          for _t in range(level.tabs)))
        made = [(dialog_titles.pop(), tuple(make() for _r in range(3)))
                for _d in range(level.dialogs)]
        if not made:
            menus.append(())
        elif level.submenus:
            # The first dialog opens from the menu; the rest cascade
            # from its More item.
            menus.append(((MENUS[0], (('dialog',) + made[0],
                                      ('sub', SUBMENU,
                                       tuple(made[1:])))),))
        else:
            names = MENUS[:max(1, (len(made) + 1) // 2)]
            menus.append(tuple(
                (name, tuple(('dialog',) + d
                             for d in made[i::len(names)]))
                for i, name in enumerate(names)))
    applies = [False] * level.windows
    for index in rng.sample(range(level.windows),
                            min(level.applies, level.windows)):
        applies[index] = True
    places = []
    if level.windows == 1:
        # Left of middle when the explorer shares the screen, clear of
        # the desktop icons' first column either way.
        left = 100 if level.explorer else (SCREEN_W - WINDOW_W) // 2
        places.append((left // GRID * GRID, 60))
    else:
        for index in range(level.windows):
            places.append((100 + index * 80, 30 + index * 56))
    apps = level.windows + (1 if level.explorer else 0)
    order = list(range(apps))
    rng.shuffle(order)
    explorer_at = (SCREEN_W - EXPLORER_W - 10, 160)
    hidden = rng.sample(range(level.windows),
                        min(level.windows - 1,
                            level.minimised + level.closed))
    closed = tuple(sorted(hidden[:level.closed]))
    minimised = tuple(sorted(hidden[level.closed:]))
    for index in rng.sample([i for i in range(level.windows)
                             if i not in hidden],
                            min(level.offscreen,
                                level.windows - len(hidden))):
        # Hanging off the right edge: the far half of every row is out
        # of reach until the window is dragged back.
        places[index] = (SCREEN_W - 220, places[index][1])
    pinned = tuple(sorted(rng.sample(range(level.windows),
                                     min(level.pinned, level.windows))))
    shortcuts = tuple(sorted(rng.sample(range(level.windows),
                                        min(2, level.windows))))
    # Files to move, delete and bring back.
    files = _grow_files(level, rng)
    loose = [i for i, f in enumerate(files) if not f[1]]
    folders = [i for i, f in enumerate(files)
               if f[1] and i not in (HOME, TRASH)]
    rng.shuffle(loose)
    moves = []
    for _m in range(min(level.moves, len(loose))):
        node = loose.pop()
        dest = rng.choice([f for f in folders if f != files[node][3]])
        moves.append((node, dest))
    for _d in range(min(level.deletes, len(loose))):
        moves.append((loose.pop(), TRASH))
    for _r in range(min(level.restores, len(loose))):
        node = loose.pop()
        name, folder, kind, home = files[node]
        files[node] = (name, folder, kind, TRASH)
        moves.append((node, home))
    rng.shuffle(moves)
    # Goals: settings to change, across every window and dialog.
    on_windows = [i for page_set in tabs for page in page_set for i in page]
    in_dialogs = []
    for window_menus in menus:
        for _name, entries in window_menus:
            for entry in entries:
                found = [entry[1:]] if entry[0] == 'dialog' else entry[2]
                for _title, members in found:
                    in_dialogs += members
    pool = on_windows + in_dialogs
    chosen = rng.sample(pool, min(level.goals, len(pool)))
    goals = []
    for ident in chosen:
        spec = specs[ident]
        goals.append((ident, rng.choice([v for v in range(spec.count)
                                         if v != spec.value])))
    # Greyed-out controls: a goal on a window that needs a setting
    # nobody asked for, which starts out wrong.
    requires = []
    free = [i for i in pool if i not in chosen]
    rng.shuffle(free)
    for ident, _value in goals:
        if len(requires) >= level.depends or not free:
            break
        if ident in in_dialogs:
            continue
        other = free.pop()
        spec = specs[other]
        requires.append((ident, (other, rng.choice(
            [v for v in range(spec.count) if v != spec.value]))))
    # Sticky notes, over the middle of a window's rows.
    notes = []
    for number, index in enumerate(rng.sample(
            range(level.windows), min(level.notes, level.windows))):
        x, y = places[index]
        top = (y + TITLE_H + (MENU_H if menus[index] else 0)
               + (TAB_H if level.tabs > 1 else 0))
        notes.append((NOTES[rng.randrange(len(NOTES))],
                      min(SCREEN_W - NOTE_W, x + 150) // GRID * GRID,
                      top // GRID * GRID))
    popups = []
    at = 0
    for _p in range(level.popups):
        at += rng.randint(2, 3 + level.goals)
        popups.append(Popup(at, rng.randrange(level.windows),
                            rng.random() < 0.5))
    # Drawn last, so everything above deals as it always has.
    copies = []
    for _c in range(min(level.copies, len(loose))):
        node = loose.pop()
        copies.append((node, rng.choice(
            [f for f in folders if f not in (files[node][3], TRASH)])))
    list_view = level.list_view and rng.random() < 0.5
    return Deal(level, tuple(titles), tuple(tabs), tuple(menus),
                tuple(applies), tuple(places), tuple(order), minimised,
                closed, tuple(notes), tuple(popups), tuple(specs),
                tuple(requires), tuple(goals), tuple(files), tuple(moves),
                explorer_at, pinned, shortcuts, tuple(copies),
                list_view, level.hide_card)


# --- the reference -----------------------------------------------------------

def reference_action(desk: Desktop) -> Optional[Action]:
    """What the reference does next -- ('click', point) or ('drag', from,
    to) -- or None when it would press Done.

    The first setting on the card that does not hold yet, taken all the
    way home before anything else is looked at.
    """
    if desk.popup is not None:
        safe, _reset = popup_buttons(desk.popup.safe_left)
        return ('click', desk.reachable(safe, None))
    for ident, value in desk.goals:
        if not desk.met((ident, value)):
            return _towards(desk, desk.controls[ident], value)
    for node, dest in desk.moves:
        if node.parent is not dest:
            return _file_towards(desk, node, dest)
    for goal in desk.copies:
        if not desk.copied(goal):
            return _file_towards(desk, goal[0], goal[1], copy=True)
    return None


def _open_from_start(desk: Desktop, win: Window) -> Action:
    """With Start open: the app's tile, or All apps and then its row."""
    for owner, rect in desk.start_items():
        if owner is win:
            return ('click', desk.reachable(rect, None))
    return ('click', desk.reachable(all_apps_rect(), None))


def _file_towards(desk: Desktop, node: Node, dest: Node,
                  copy: bool = False) -> Action:
    """Plainly: open the folder it is in one level at a time, pick it,
    Cut, open the folder it goes to the same way, Paste. A file that is
    to go to the Trash is picked and Deleted instead."""
    ex = desk.explorer
    if desk.dropdown is not None or desk.menu is not None \
            or desk.context is not None:
        return ('click', _anywhere_else(desk))
    if desk.dialog is not None:
        return ('click', desk.reachable(desk.dialog_buttons()[1], None))
    if desk.start_open:
        if ex.closed:
            return _open_from_start(desk, ex)
        return ('click', _anywhere_else(desk))
    if ex.closed:
        return ('click', desk.reachable(START_RECT, None))
    if ex.minimised:
        rect = dict((id(w), r) for w, r in desk.taskbar_buttons())[id(ex)]
        return ('click', desk.reachable(rect, None))
    place = ex.places[ex.place]
    tools = dict(tool_rects(ex))
    if desk.clipboard is node and desk.copying == copy:
        if place.path is dest:
            return _ensure(desk, ex, tools['Paste'])
        return _navigate(desk, ex, place, dest)
    if place.path is not node.parent:
        return _navigate(desk, ex, place, node.parent)
    if place.selected is not node:
        return _show(desk, ex, place, node)
    if dest.ident == TRASH and not copy:
        return _ensure(desk, ex, tools['Delete'])
    return _ensure(desk, ex, tools['Copy' if copy else 'Cut'])


def _navigate(desk: Desktop, ex: Window, place: Place,
              target: Node) -> Action:
    chain = target.chain()
    if place.path in chain:
        return _show(desk, ex, place, chain[chain.index(place.path) + 1])
    # From the side: the place the target is under, then down.
    top = chain[1] if len(chain) > 1 and chain[0].ident == HOME else chain[0]
    return _ensure(desk, ex, sidebar_rects(ex)[top.ident])


def _show(desk: Desktop, ex: Window, place: Place, node: Node) -> Action:
    """Click *node*'s icon -- scrolling to it first if it is not showing.
    Clicking a folder that is already picked opens it."""
    index = place.path.listing().index(node)
    row = index // ex_columns(ex)
    up, down = ex_scroll_rects(ex)
    if row < place.scroll:
        return _ensure(desk, ex, up)
    if row >= place.scroll + grid_rows(ex):
        return _ensure(desk, ex, down)
    rect = dict((id(n), r) for n, r in desk.icon_rects(ex))[id(node)]
    return _ensure(desk, ex, rect)


def reference_click(desk: Desktop) -> Optional[Tuple[int, int]]:
    """The point of the reference's next action, for callers that only
    click -- None when it would press Done."""
    action = reference_action(desk)
    return None if action is None else action[1]


def _towards(desk: Desktop, control: Control, value: int) -> Action:
    if not control.enabled and control.value != value:
        other, wanted = control.requires
        if other.value != wanted:
            return _towards(desk, other, wanted)
    win = control.window
    if desk.dropdown is not None:
        if desk.dropdown is control and control.shown != value:
            rect = desk.control_rect(control)
            item = dropdown_items(rect, control)[value]
            return ('click', desk.reachable(item, None))
        return ('click', _anywhere_else(desk))
    if desk.start_open:
        if win.closed:
            return _open_from_start(desk, win)
        return ('click', _anywhere_else(desk))
    if desk.menu is not None:
        return _in_menu(desk, control)
    if desk.dialog is not None:
        _cancel, ok = desk.dialog_buttons()
        if desk.dialog is control.dialog and control.shown != value:
            return _click_value(desk, control, value, None)
        return ('click', desk.reachable(ok, None))
    if win.closed:
        return ('click', desk.reachable(START_RECT, None))
    if win.minimised:
        rect = dict((id(w), r) for w, r in desk.taskbar_buttons())[id(win)]
        return ('click', desk.reachable(rect, None))
    if control.dialog is not None:
        return _ensure(desk, win, menu_rects(win)[control.dialog.menu])
    if control.shown == value:
        return _ensure(desk, win, apply_rect(win))
    if win.active != control.tab:
        return _ensure(desk, win, tab_rects(win)[control.tab])
    scroll = win.scroll[control.tab]
    if control.row < scroll:
        return _ensure(desk, win, scroll_rects(win)[0])
    if control.row >= scroll + win.rows:
        return _ensure(desk, win, scroll_rects(win)[1])
    return _click_value(desk, control, value, win)


def _in_menu(desk: Desktop, control: Control) -> Action:
    win, index, sub = desk.menu
    dialog = control.dialog
    if dialog is None or dialog.window is not win or dialog.menu != index:
        return ('click', _anywhere_else(desk))
    if dialog.sub is None:
        return ('click', desk.reachable(desk.menu_items()[dialog.item],
                                        None))
    if sub == dialog.item:
        return ('click', desk.reachable(desk.submenu_items()[dialog.sub],
                                        None))
    return ('click', desk.reachable(desk.menu_items()[dialog.item], None))


def _click_value(desk: Desktop, control: Control, value: int,
                 win: Optional[Window]) -> Action:
    rect = desk.control_rect(control)
    regions = parts(control, rect)
    if control.kind in ('toggle', 'dropdown'):
        part = regions[0]
    elif control.kind == 'stepper':
        part = regions[1] if control.shown < value else regions[0]
    else:
        part = regions[value]
    if win is None:
        return ('click', desk.reachable(part, None))
    return _ensure(desk, win, part)


def _ensure(desk: Desktop, win: Window, rect: Rect) -> Action:
    """Click *rect* on *win* -- or first do what makes that possible."""
    point = desk.reachable(rect, win)
    if point is not None:
        return ('click', point)
    x, y, w, h = rect
    if x >= SCREEN_W - GRID:
        # Off the edge of the screen: drag the window back by its title.
        grip = _title_point(desk, win)
        tops = [w for w in desk.order if w.shown and not w.pinned]
        if grip is None and tops and tops[-1] is not win:
            for owner, button in desk.taskbar_buttons():
                if owner is win:
                    return ('click', desk.reachable(button, None))
        if grip is not None:
            shift = (win.x + win.w) - (SCREEN_W - 10)
            to = (max(0, grip[0] - (shift + GRID - 1) // GRID * GRID),
                  grip[1])
            return ('drag', grip, to)
    cx, cy = centre(rect)
    blocker = desk.window_at(min(cx, SCREEN_W - 1), cy)
    if blocker is not None and blocker.pinned:
        point = desk.reachable(minimise_rect(blocker), blocker)
        if point is not None:
            return ('click', point)
    grip = _title_point(desk, win)
    if grip is not None:
        return ('click', grip)
    # The title bar is buried: the taskbar raises it as well.
    tops = [w for w in desk.order if w.shown and not w.pinned]
    if tops and tops[-1] is not win:
        for owner, button in desk.taskbar_buttons():
            if owner is win:
                return ('click', desk.reachable(button, None))
    # What is in the way is a sticky note: put it away.
    for note in desk.notes:
        if note.shown:
            point = desk.reachable(minimise_rect(note), note)
            if point is not None:
                return ('click', point)
    raise AssertionError('nothing the reference can do')


def _title_point(desk: Desktop, win: Window) -> Optional[Tuple[int, int]]:
    """A point on the title bar, clear of its two buttons."""
    x, y, w, h = title_rect(win)
    return desk.reachable((x, y, w - 62, h), win)


def _icon_key(item: Tuple) -> Tuple:
    if item[0] in ('app', 'node'):
        return (item[0], item[1].ident)
    return item


def _anywhere_else(desk: Desktop) -> Tuple[int, int]:
    """A click that only closes what is open: the empty taskbar."""
    return (SCREEN_W - 200, WORK_H + TASKBAR_H // 2 // GRID * GRID)


def reference_round(dealt: Deal) -> Desktop:
    desk = Desktop(dealt)
    for _step in range(3000):
        action = reference_action(desk)
        if action is None:
            break
        desk.act(action)
    desk.done = True
    return desk


def par(dealt: Deal) -> float:
    """The clicks a round must come in at or under to pass."""
    level = dealt.level
    # Two peeks at a hidden card are allowed for; the reference needs
    # none, since it never forgets.
    peeks = 2 if level.hide_card else 0
    return (reference_round(dealt).clicks + peeks) * level.factor \
        + level.slack


def budget(par_clicks: float) -> int:
    """Clicks allowed before the round ends on its own."""
    return int(par_clicks * 3) + 20


def colour_of(name: str) -> Tuple[int, int, int]:
    return dict(COLOURS)[name]


__all__ = ['CONTEXT_W', 'LIST_H', 'PEEK_RECT', 'cell_dims', 'ex_columns',
           'EXPLORER', 'HOME', 'Node', 'PLACES', 'Place', 'START_PANEL',
           'TOOLS', 'TRASH', 'all_apps_rect', 'desktop_icon_rect',
           'ex_scroll_rects', 'grid_area', 'place_tab_rects', 'plus_rect',
           'sidebar_rects', 'start_rows', 'start_tiles', 'tool_rects',
           'COLOURS', 'Control', 'DONE_RECT', 'Deal', 'Desktop', 'Dialog',
           'GRID', 'Grade', 'KINDS', 'POPUP_RECT', 'Popup', 'SCREEN_H',
           'SCREEN_W', 'START', 'START_RECT', 'STEPS', 'Submenu',
           'TASKBAR_H', 'WORK_H', 'Window', 'apply_rect', 'budget',
           'centre', 'close_rect', 'colour_of', 'deal', 'dropdown_items',
           'grade', 'grip_rect', 'inside', 'menu_rects', 'minimise_rect',
           'par', 'parts', 'popup_buttons', 'reference_action',
           'reference_click', 'reference_round', 'scroll_rects',
           'tab_rects', 'title_rect', 'widget_rect']
