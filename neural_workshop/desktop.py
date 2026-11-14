# -*- coding: utf-8 -*-
"""Desktop: a small computer to operate, from one button to a cluttered screen.

The workshop's other tasks hand the player controls with a fixed
meaning. This one hands them a pointer and a screen. Windows hold
controls -- switches, rows of choices, sliders with notches, dropdown
lists -- and a card beside the screen shows the settings to reach. The
player moves the pointer and clicks. Moving is free; every click costs
a point, whatever it does or fails to do, and the round passes if the
card's settings hold when Done is pressed and the clicks came in at or
under par.

What has to be learned is what operating any computer asks:

* **Widget grammars.** A switch flips; a row of choices takes the one
  clicked; a slider takes the notch; a dropdown opens a list and takes
  the item. The same handful of shapes, in every window.
* **Finding the control.** From rung five a window has tabs and only
  the open tab's controls are there; from six a long tab scrolls; from
  eight some settings live in dialogs opened from a menu bar, and a
  dialog's changes are kept only by OK -- Cancel throws them away.
* **Overlap.** From rung eleven windows overlap. Only what is on top
  takes a click, a click on a window brings it to the top, and a
  control under another window has to be uncovered first.
* **Prerequisites.** From rung fifteen a control can be greyed out,
  with a note saying which other setting it needs; from sixteen some
  windows keep changes pending until Apply is pressed.

**The reference is deliberately plain.** It works through the card in
the order the card lists it, one setting at a time, and sees each one
all the way home -- an OK for every dialog setting, an Apply for every
pending one -- before it looks at the next. It never reorders the card
to keep a dialog open or a tab showing, and it never saves an Apply.
Below rung twenty that is generous; past it the clicks have to come in
under the reference's, by more at every rung, and the only way there
is to plan the order of the work.

Everything is in logical units on a 1000 by 640 screen, origin at the
top left, so the model, the reference and the screen agree about where
everything is. Nothing here imports pyglet.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

SCREEN_W, SCREEN_H = 1000, 640
TASKBAR_H = 40
TITLE_H, MENU_H, TAB_H, ROW_H, APPLY_H = 30, 26, 28, 36, 38
WINDOW_W = 440
DIALOG_W = 400
#: Pointer steps, logical units: coarse, medium, fine.
STEPS = (80, 20, 5)
#: Every point the reference clicks is on this grid, which is the grid
#: the pointer moves on from its start, so the agent can reach it too.
GRID = 5
START = (500, 320)
DONE_RECT = (SCREEN_W - 130, SCREEN_H - TASKBAR_H + 6, 120, TASKBAR_H - 12)

KINDS = ('toggle', 'choice', 'slider', 'dropdown')

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
           'Fonts', 'Export')
WORDS = ('Off', 'Low', 'Mid', 'High', 'Auto', 'Max')


class Grade(NamedTuple):
    rung: int
    windows: int
    tabs: int
    #: Controls on each tab, and how many rows a window shows at once.
    per_tab: int
    rows: int
    kinds: Tuple[str, ...]
    #: Dialogs behind each window's menu bar.
    dialogs: int
    #: Greyed-out controls, and windows that keep changes until Apply.
    depends: int
    applies: int
    goals: int
    factor: float
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    per_tab = min(8, 1 + r // 2)
    return Grade(
        rung=r,
        windows=1 if r < 11 else min(6, 2 + (r - 11) // 3),
        tabs=1 if r < 5 else (2 if r < 10 else 3),
        per_tab=per_tab,
        rows=per_tab if r < 6 else (3 if r < 8 else 4),
        kinds=KINDS[:min(4, r)],
        dialogs=0 if r < 8 else (1 if r < 12 else 2),
        depends=0 if r < 15 else min(4, 1 + (r - 15) // 3),
        applies=0 if r < 16 else (1 if r < 19 else 2),
        goals=1 if r <= 2 else min(14, r // 2 + 1),
        factor=(max(1.0, 2.0 - (r - 1) / 11.0) if r <= 20
                else 1.0 / (1.0 + 0.04 * (r - 20))),
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
        if self.kind == 'slider':
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
        self.menu = 0


class Window:
    def __init__(self, ident: int, title: str, tabs: List[List[Control]],
                 rows: int, menus: List[Tuple[str, List[Dialog]]],
                 apply: bool) -> None:
        self.ident = ident
        self.title = title
        self.tabs = tabs
        self.rows = rows
        self.menus = menus
        self.apply = apply
        self.active = 0
        #: Rows scrolled past, per tab.
        self.scroll = [0] * len(tabs)
        self.x = self.y = 0
        self.w = WINDOW_W
        self.h = (TITLE_H + (MENU_H if menus else 0)
                  + (TAB_H if len(tabs) > 1 else 0) + rows * ROW_H
                  + (APPLY_H if apply else 0) + 8)

    @property
    def content_top(self) -> int:
        return (self.y + TITLE_H + (MENU_H if self.menus else 0)
                + (TAB_H if len(self.tabs) > 1 else 0))

    def scrolls(self, tab: int) -> bool:
        return len(self.tabs[tab]) > self.rows


Rect = Tuple[float, float, float, float]       # x, y, w, h; y down


def inside(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


# --- layout: where everything is, for the model and the screen alike --------

def title_rect(win: Window) -> Rect:
    return (win.x, win.y, win.w, TITLE_H)


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
    return ((x, top + 2, 24, 24),
            (x, top + win.rows * ROW_H - 26, 24, 24))


def apply_rect(win: Window) -> Rect:
    return (win.x + win.w - 104, win.content_top + win.rows * ROW_H + 4,
            92, APPLY_H - 8)


def widget_rect(left: float, top: float, width: float) -> Rect:
    """The part of a row the control itself takes."""
    return (left + width * 0.42, top + 5, width * 0.5 - 36, ROW_H - 10)


def parts(control: Control, rect: Rect) -> List[Rect]:
    """For each value, where clicking sets it -- or, for a switch and a
    dropdown, the one place to click."""
    x, y, w, h = rect
    if control.kind == 'toggle':
        return [(x, y, 56, h)]
    if control.kind == 'dropdown':
        return [(x, y, w * 0.7, h)]
    cell = w / control.count
    return [(x + i * cell, y, cell, h) for i in range(control.count)]


def dropdown_items(rect: Rect, control: Control) -> List[Rect]:
    x, y, w, h = parts(control, rect)[0]
    if y + h + control.count * 28 > SCREEN_H - TASKBAR_H:
        # No room below: the list opens upwards, as a real one does.
        return [(x, y - (control.count - i) * 28, w, 28)
                for i in range(control.count)]
    return [(x, y + h + i * 28, w, 28) for i in range(control.count)]


class Desktop:
    """One round's screen, for the player or the reference alike."""

    def __init__(self, dealt: 'Deal') -> None:
        self.level = dealt.level
        self.windows, self.controls = build(dealt)
        #: Bottom first.
        self.order: List[Window] = [self.windows[i] for i in dealt.order]
        self.goals: Tuple[Tuple[int, int], ...] = dealt.goals
        self.pointer = START
        self.clicks = 0
        self.dialog: Optional[Dialog] = None
        self.menu: Optional[Tuple[Window, int]] = None
        self.dropdown: Optional[Control] = None
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
        if win.active != control.tab:
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
        return ((SCREEN_W - DIALOG_W) / 2, (SCREEN_H - TASKBAR_H - h) / 2,
                DIALOG_W, h)

    def dialog_buttons(self) -> Tuple[Rect, Rect]:
        x, y, w, h = self.dialog_rect()
        return ((x + w - 200, y + h - 42, 88, 32),
                (x + w - 104, y + h - 42, 92, 32))

    def menu_items(self) -> List[Rect]:
        if self.menu is None:
            return []
        win, index = self.menu
        mx, my, _mw, mh = menu_rects(win)[index]
        return [(mx, my + mh + i * 30, 150, 30)
                for i in range(len(win.menus[index][1]))]

    def window_at(self, x: float, y: float) -> Optional[Window]:
        for win in reversed(self.order):
            if inside((win.x, win.y, win.w, win.h), x, y):
                return win
        return None

    def overlay_at(self, x: float, y: float) -> bool:
        """Whether a menu, a list or a dialog is over this point."""
        if self.dialog is not None and inside(self.dialog_rect(), x, y):
            return True
        if any(inside(r, x, y) for r in self.menu_items()):
            return True
        if self.dropdown is not None:
            rect = self.control_rect(self.dropdown)
            if rect and any(inside(r, x, y)
                            for r in dropdown_items(rect, self.dropdown)):
                return True
        return False

    def reachable(self, rect: Rect, win: Optional[Window]) -> Optional[
            Tuple[int, int]]:
        """A grid point in *rect* that a click would reach -- on *win*,
        not under anything -- nearest the rect's middle."""
        x, y, w, h = rect
        cx, cy = x + w / 2, y + h / 2
        best = None
        gx0 = int((x + GRID - 1) // GRID) * GRID
        gy0 = int((y + GRID - 1) // GRID) * GRID
        for gy in range(gy0, int(y + h), GRID):
            for gx in range(gx0, int(x + w), GRID):
                if not inside(rect, gx, gy):
                    continue
                if win is not None and (self.window_at(gx, gy) is not win
                                        or self.overlay_at(gx, gy)):
                    continue
                gap = (gx - cx) ** 2 + (gy - cy) ** 2
                if best is None or gap < best[0]:
                    best = (gap, (gx, gy))
        return None if best is None else best[1]

    # --- clicking --------------------------------------------------------

    def move(self, dx: float, dy: float) -> None:
        x, y = self.pointer
        self.pointer = (max(0, min(SCREEN_W - GRID, x + dx)),
                        max(0, min(SCREEN_H - GRID, y + dy)))

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        """A click at (x, y), or where the pointer is. Always a point."""
        if self.done:
            return
        if x is None:
            x, y = self.pointer
        else:
            self.pointer = (x, y)
        self.clicks += 1
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
        if self.menu is not None:
            win, index = self.menu
            self.menu = None
            for item, rect in enumerate(self.menu_items_of(win, index)):
                if inside(rect, x, y):
                    self._open(win.menus[index][1][item])
            return
        if inside(DONE_RECT, x, y):
            self.done = True
            return
        win = self.window_at(x, y)
        if win is None:
            return
        self.order.remove(win)
        self.order.append(win)
        for index, rect in enumerate(menu_rects(win)):
            if inside(rect, x, y):
                self.menu = (win, index)
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

    def menu_items_of(self, win: Window, index: int) -> List[Rect]:
        mx, my, _mw, mh = menu_rects(win)[index]
        return [(mx, my + mh + i * 30, 150, 30)
                for i in range(len(win.menus[index][1]))]

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
            else:
                self._set(control, value)
            return

    def _set(self, control: Control, value: int) -> None:
        control.shown = value
        if control.dialog is None and not control.window.apply:
            control.value = value

    # --- the verdict -----------------------------------------------------

    def met(self, goal: Tuple[int, int]) -> bool:
        ident, value = goal
        return self.controls[ident].value == value

    @property
    def solved(self) -> bool:
        return all(self.met(goal) for goal in self.goals)


# --- dealing a desktop ------------------------------------------------------

class Spec(NamedTuple):
    label: str
    kind: str
    count: int
    value: int
    words: Tuple[str, ...]


class Deal(NamedTuple):
    level: Grade
    #: Window titles, then each window's tabs of controls, its dialogs
    #: by menu, whether it waits for Apply, and where it stands.
    titles: Tuple[str, ...]
    tabs: Tuple[Tuple[Tuple[int, ...], ...], ...]
    menus: Tuple[Tuple[Tuple[str, Tuple[Tuple[str, Tuple[int, ...]], ...]],
                       ...], ...]
    applies: Tuple[bool, ...]
    places: Tuple[Tuple[int, int], ...]
    #: Bottom window first.
    order: Tuple[int, ...]
    specs: Tuple[Spec, ...]
    #: (control, (control it needs, value)), for greyed-out controls.
    requires: Tuple[Tuple[int, Tuple[int, int]], ...]
    #: (control, value), in the order the card lists them.
    goals: Tuple[Tuple[int, int], ...]


def build(dealt: Deal) -> Tuple[List[Window], List[Control]]:
    controls = [Control(i, s.label, s.kind, s.count, s.value, s.words)
                for i, s in enumerate(dealt.specs)]
    windows = []
    for index, title in enumerate(dealt.titles):
        tabs = [[controls[i] for i in page] for page in dealt.tabs[index]]
        menus = []
        for menu_index, (name, items) in enumerate(dealt.menus[index]):
            dialogs = []
            for dialog_title, members in items:
                dialog = Dialog(dialog_title, [controls[i] for i in members])
                dialog.menu = menu_index
                for row, control in enumerate(dialog.controls):
                    control.dialog = dialog
                    control.row = row
                dialogs.append(dialog)
            menus.append((name, dialogs))
        win = Window(index, title, tabs, dealt.level.rows, menus,
                     dealt.applies[index])
        win.x, win.y = dealt.places[index]
        for tab, page in enumerate(tabs):
            for row, control in enumerate(page):
                control.window, control.tab, control.row = win, tab, row
        for _name, dialogs in menus:
            for dialog in dialogs:
                dialog.window = win
                for control in dialog.controls:
                    control.window = win
        windows.append(win)
    for ident, (other, value) in dealt.requires:
        controls[ident].requires = (controls[other], value)
    return windows, controls


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    rng = rng or random.Random(seed)
    level = grade(rung)
    labels: List[str] = []
    specs: List[Spec] = []

    def make() -> int:
        kind = rng.choice(level.kinds)
        count = (2 if kind == 'toggle' else
                 rng.randint(3, 4) if kind == 'choice' else
                 rng.randint(4, 6) if kind == 'slider' else
                 rng.randint(3, 6))
        start = rng.randrange(6 - count + 1) if kind in (
            'choice', 'dropdown') else 0
        specs.append(Spec(labels.pop(), kind, count, rng.randrange(count),
                          WORDS[start:start + count]))
        return len(specs) - 1

    titles = rng.sample(TITLES, level.windows)
    dialog_titles = rng.sample(DIALOGS, level.windows * level.dialogs)
    tabs, menus = [], []
    for index in range(level.windows):
        # Names are unique within a window, which is all the card needs:
        # it names the window, or the dialog, with every setting.
        labels[:] = rng.sample(LABELS, len(LABELS))
        tabs.append(tuple(tuple(make() for _r in range(level.per_tab))
                          for _t in range(level.tabs)))
        items = []
        for _d in range(level.dialogs):
            items.append((dialog_titles.pop(),
                          tuple(make() for _r in range(3))))
        names = MENUS[:max(1, (len(items) + 1) // 2)] if items else ()
        menus.append(tuple((name, tuple(items[i::len(names)]))
                           for i, name in enumerate(names)))
    applies = [False] * level.windows
    for index in rng.sample(range(level.windows),
                            min(level.applies, level.windows)):
        applies[index] = True
    places = []
    if level.windows == 1:
        places.append(((SCREEN_W - WINDOW_W) // 2 // GRID * GRID, 60))
    else:
        for index in range(level.windows):
            places.append((40 + index * 90, 30 + index * 56))
    order = list(range(level.windows))
    rng.shuffle(order)
    # Goals: settings to change, across every window and dialog.
    on_windows = [i for page_set in tabs for page in page_set for i in page]
    in_dialogs = [i for window_menus in menus for _n, items in window_menus
                  for _t, members in items for i in members]
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
    return Deal(level, tuple(titles), tuple(tabs), tuple(menus),
                tuple(applies), tuple(places), tuple(order), tuple(specs),
                tuple(requires), tuple(goals))


# --- the reference -----------------------------------------------------------

def reference_click(desk: Desktop) -> Optional[Tuple[int, int]]:
    """Where the reference clicks next, or None when it would press Done.

    The first setting on the card that does not hold yet, taken all the
    way home before anything else is looked at.
    """
    for ident, value in desk.goals:
        if not desk.met((ident, value)):
            return _towards(desk, desk.controls[ident], value)
    return None


def _towards(desk: Desktop, control: Control, value: int
             ) -> Tuple[int, int]:
    if not control.enabled and control.value != value:
        other, wanted = control.requires
        if other.value != wanted:
            return _towards(desk, other, wanted)
    win = control.window
    if desk.dropdown is not None:
        if desk.dropdown is control and control.shown != value:
            rect = desk.control_rect(control)
            item = dropdown_items(rect, control)[value]
            return desk.reachable(item, None)
        return _anywhere_else(desk)
    if desk.menu is not None:
        menu_win, index = desk.menu
        if control.dialog is not None and menu_win is win \
                and control.dialog.menu == index:
            item = win.menus[index][1].index(control.dialog)
            return desk.reachable(desk.menu_items()[item], None)
        return _anywhere_else(desk)
    if desk.dialog is not None:
        cancel, ok = desk.dialog_buttons()
        if desk.dialog is control.dialog and control.shown != value:
            return _click_value(desk, control, value, None)
        return desk.reachable(ok, None)
    if control.dialog is not None:
        rect = menu_rects(win)[control.dialog.menu]
        return desk.reachable(rect, win) or _raise(desk, win)
    if control.shown == value:
        return desk.reachable(apply_rect(win), win) or _raise(desk, win)
    if win.active != control.tab:
        rect = tab_rects(win)[control.tab]
        return desk.reachable(rect, win) or _raise(desk, win)
    scroll = win.scroll[control.tab]
    if control.row < scroll:
        return desk.reachable(scroll_rects(win)[0], win) or _raise(desk, win)
    if control.row >= scroll + win.rows:
        return desk.reachable(scroll_rects(win)[1], win) or _raise(desk, win)
    return _click_value(desk, control, value, win) or _raise(desk, win)


def _click_value(desk: Desktop, control: Control, value: int,
                 win: Optional[Window]) -> Optional[Tuple[int, int]]:
    rect = desk.control_rect(control)
    regions = parts(control, rect)
    part = regions[0] if control.kind in ('toggle', 'dropdown') \
        else regions[value]
    return desk.reachable(part, win)


def _raise(desk: Desktop, win: Window) -> Tuple[int, int]:
    point = desk.reachable(title_rect(win), win)
    assert point is not None, 'every title bar shows'
    return point


def _anywhere_else(desk: Desktop) -> Tuple[int, int]:
    """A click that only closes what is open: the empty taskbar."""
    return (40, SCREEN_H - TASKBAR_H // 2 // GRID * GRID)


def reference_round(dealt: Deal) -> Desktop:
    desk = Desktop(dealt)
    for _step in range(2000):
        point = reference_click(desk)
        if point is None:
            break
        desk.click(*point)
    desk.done = True
    return desk


def par(dealt: Deal) -> float:
    """The clicks a round must come in at or under to pass."""
    level = dealt.level
    return reference_round(dealt).clicks * level.factor + level.slack


def budget(par_clicks: float) -> int:
    """Clicks allowed before the round ends on its own."""
    return int(par_clicks * 3) + 20


__all__ = ['Control', 'DONE_RECT', 'Deal', 'Desktop', 'Dialog', 'GRID',
           'Grade', 'KINDS', 'SCREEN_H', 'SCREEN_W', 'START', 'STEPS',
           'TASKBAR_H', 'Window', 'apply_rect', 'budget', 'deal',
           'dropdown_items', 'grade', 'inside', 'menu_rects', 'par',
           'parts', 'reference_click', 'reference_round', 'scroll_rects',
           'tab_rects', 'title_rect', 'widget_rect']
