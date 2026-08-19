# -*- coding: utf-8 -*-
"""The generic menu widget and the value cyclers it displays.

A menu is a list of option keys plus a parallel mapping of values.
A value of ``None`` makes the option a command (selecting it calls
:meth:`Menu.choose`); a ``bool`` toggles; a :class:`Cycler` steps
through a fixed list.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import (Any, Callable, Dict, Iterable, List, Optional, Sequence,
                    Union)

import pyglet
from pyglet.window import key

from .. import display, state
from ..geometry import calc_fontsize, from_bottom_edge, width_center
from ..constants import FONTLIST
from ..i18n import _

#: Placeholder option that renders as an unselectable empty row.
BLANK_LINE = 'Blank line'


class Cycler:
    """A value that steps through a fixed list of choices."""

    def __init__(self, values: Sequence[Any], default: Any = 0) -> None:
        self.values = values
        if not isinstance(default, int) or default > len(values):
            default = values.index(default)
        self.i: int = default

    def choose(self, val: Any) -> None:
        if val in self.values:
            self.i = self.values.index(val)

    def nxt(self) -> Any:
        """Advance to the next value.

        Deliberately not called ``next``: a Cycler is not an iterator and
        naming it so would make ``for x in cycler`` hang.
        """
        self.i = (self.i + 1) % len(self.values)
        return self.value()

    def value(self) -> Any:
        return self.values[self.i]

    def __str__(self) -> str:
        return str(self.value())


class PercentCycler(Cycler):
    """A Cycler over fractions, shown as percentages."""

    def __str__(self) -> str:
        v = self.value()
        if isinstance(v, float) and (v < .1 or v > .9) and v not in (0., 1.):
            return '%2.2f%%' % (v * 100.)
        return '%2.1f%%' % (v * 100.)


class AllCycler(Cycler):
    """A Cycler where zero means "no limit"."""

    def __str__(self) -> str:
        v = self.value()
        return 'all' if v == 0 else str(v)


class Menu:
    """A scrolling list of options with editable values.

    Instantiating a Menu displays it and installs handlers for
    ``on_key_press``, ``on_text``, ``on_text_motion`` and ``on_draw``,
    none of which pass events further down the stack. Escape pops them
    off again.

    *actions* maps an option key to a callable returning that option's
    new value, for options that need a custom editor.
    """

    #: Set on the class so a live menu is reachable, and so pyglet's weak
    #: handler references do not let the instance be collected.
    instance: Optional['Menu'] = None

    def __init__(self, options: Union[Sequence[str], Dict[str, Any]],
                 values: Optional[Dict[str, Any]] = None,
                 actions: Optional[Dict[str, Callable[[str], Any]]] = None,
                 names: Optional[Dict[str, str]] = None,
                 title: str = '',
                 footnote: Optional[str] = None,
                 choose_once: bool = False,
                 default: int = 0) -> None:
        if footnote is None:
            footnote = _('Esc: cancel     Space: modify option     Enter: apply')
        self.footnote_text = footnote
        self.title_text = title

        if isinstance(options, dict):
            default_values: Dict[str, Any] = options
            self.options: List[str] = list(options)
        else:
            default_values = {op: None for op in options}
            self.options = list(options)
        self.values: Dict[str, Any] = values if values else default_values
        self.actions: Dict[str, Callable[[str], Any]] = actions or {}

        names = dict(names or {})
        for op in self.options:
            names.setdefault(op, op)
        self.names = names

        self.choose_once = choose_once
        self.disppos = 0    # index of the first option shown on screen
        self.selpos = default
        self.closed = False
        self.build_chrome()

        self.update_labels()
        state.window.push_handlers(self.on_key_press, self.on_text,
                                   self.on_text_motion, self.on_draw)
        display.register_overlay(self)
        Menu.instance = self

    def build_chrome(self) -> None:
        """Create the batch, the fonts and the labels, sized to the window.

        Called once when the menu opens and again whenever the window
        changes size, so everything it touches must be derived from the
        window rather than carried over.
        """
        window = state.window
        self.titlesize = calc_fontsize(18)
        self.choicesize = calc_fontsize(12)
        self.footnotesize = calc_fontsize(12)
        self.bgcolor = (255 * int(not state.cfg.BLACK_BACKGROUND),) * 3
        self.textcolor = (255 * int(state.cfg.BLACK_BACKGROUND),) * 3 + (255,)
        self.pagesize = max(1, int(min(len(self.options),
                                       (window.height * 6 / 10)
                                       / (self.choicesize * 3 / 2))))
        self.batch = pyglet.graphics.Batch()

        self.title = pyglet.text.Label(
            self.title_text, font_size=self.titlesize, weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=(window.height * 9) / 10,
            anchor_x='center', anchor_y='center')
        self.footnote = pyglet.text.Label(
            self.footnote_text, font_size=self.footnotesize, weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_bottom_edge(35),
            anchor_x='center', anchor_y='center')
        self.labels = [
            pyglet.text.Label(
                '', font_size=self.choicesize, weight='bold',
                color=self.textcolor, batch=self.batch,
                x=window.width / 8,
                y=(window.height * 8) / 10 - i * (self.choicesize * 3 / 2),
                anchor_x='left', anchor_y='center', font_name=FONTLIST)
            for i in range(self.pagesize)]
        self.marker = pyglet.shapes.Polygon((0, 0), (0, 0), (0, 0),
                                            color=[1] * 3, batch=self.batch)

    def relayout(self) -> None:
        """Rebuild at the window's current size, keeping the selection."""
        self.build_chrome()
        self.disppos = 0
        self.move_selection(self.selpos, relative=False)

    # --- display ---------------------------------------------------------

    def textify(self, x: Any) -> str:
        """Render a value for the right-hand column."""
        if isinstance(x, bool):
            return _('Yes') if x else _('No')
        return str(x)

    def _label_text(self, option: str) -> str:
        if option == BLANK_LINE:
            return ''
        value = self.values.get(option)
        if option in self.values and value is not None:
            return '%s: %7s' % (self.names[option].ljust(51),
                                self.textify(value))
        return self.names[option]

    def update_labels(self) -> None:
        """Refill the visible rows and reposition the selection marker."""
        for label in self.labels:
            label.text = ''

        markerpos = self.selpos - self.disppos
        i = 0
        if self.disppos != 0:
            self.labels[i].text = '...'
            i += 1
        ending = int(self.disppos + self.pagesize < len(self.options))
        while i < self.pagesize - ending and i + self.disppos < len(self.options):
            self.labels[i].text = self._label_text(self.options[i + self.disppos])
            i += 1
        if ending:
            self.labels[i].text = '...'

        w, h, cs = state.window.width, state.window.height, self.choicesize
        row_y = (h * 8) / 10 - markerpos * (cs * 3 / 2)
        self.marker = pyglet.shapes.Polygon(
            (w // 10, int(row_y + cs / 2)),
            (w // 9, int(row_y)),
            (w // 10, int(row_y - cs / 2)),
            color=(1, 1, 1), batch=self.batch)

    def move_selection(self, steps: int, relative: bool = True) -> None:
        """Move the highlight, scrolling and skipping blank rows."""
        if relative:
            self.selpos += steps
        else:
            self.selpos = steps
        self.selpos = min(len(self.options) - 1, max(0, self.selpos))

        if self.disppos >= self.selpos and self.disppos != 0:
            self.disppos = max(0, self.selpos - 1)
        if self.disppos <= self.selpos - self.pagesize + 1 \
                and self.disppos != len(self.options) - self.pagesize:
            self.disppos = max(0, min(len(self.options), self.selpos + 1)
                               - self.pagesize + 1)

        if self.selpos not in (0, len(self.options) - 1) \
                and self.options[self.selpos] == BLANK_LINE:
            self.move_selection(1 if steps > 0 else -1)
        self.update_labels()

    # --- behaviour -------------------------------------------------------

    def select(self) -> None:
        """Act on the highlighted option: toggle, cycle or choose."""
        k = self.options[self.selpos]
        if k == BLANK_LINE:
            pass
        elif k in self.actions:
            self.values[k] = self.actions[k](k)
        elif isinstance(self.values[k], bool):
            self.values[k] = not self.values[k]
        elif isinstance(self.values[k], Cycler):
            self.values[k].nxt()
        elif self.values[k] is None:
            self.choose(k, self.selpos)
            self.close()
        if self.choose_once:
            self.close()
        self.update_labels()

    def choose(self, k: str, i: int) -> None:
        """Called when a command option is picked. Override in subclasses."""

    def save(self) -> None:
        """Called when the menu is accepted. Override in subclasses."""

    def close(self) -> None:
        self.closed = True
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_text,
                                     self.on_text_motion, self.on_draw)

    # --- events ----------------------------------------------------------

    def on_key_press(self, sym: int, mod: int) -> bool:
        if sym == key.ESCAPE:
            self.close()
        elif sym in (key.RETURN, key.ENTER):
            self.save()
            self.close()
        elif sym == key.SPACE:
            self.select()
        elif sym == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_text_motion(self, evt: int) -> bool:
        if evt == key.MOTION_UP:
            self.move_selection(steps=-1)
        elif evt == key.MOTION_DOWN:
            self.move_selection(steps=1)
        elif evt == key.MOTION_PREVIOUS_PAGE:
            self.move_selection(steps=-self.pagesize)
        elif evt == key.MOTION_NEXT_PAGE:
            self.move_selection(steps=self.pagesize)
        return pyglet.event.EVENT_HANDLED

    def on_text(self, evt: str) -> bool:
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def blank_lines(count: int) -> Iterable[str]:
    """Convenience for building option lists with spacing."""
    return [BLANK_LINE] * count
