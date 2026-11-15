# -*- coding: utf-8 -*-
"""Spreadsheet: a table of orders, a question, and the tools to answer it.

The screen is a small spreadsheet: a filter bar of categories along the
top, column headers that sort the table when clicked, rows that scroll,
a row of sum buttons under the numeric columns that put the visible
rows' sum, count and largest value in a status bar, and on the right an
answer box with a keypad and Submit. The question is answered with a
number -- a value, a row's ID, a sum or a count -- and Submit takes
only one try. Clicks count, keypad presses included; moving the
pointer and scrolling are free.

* rungs 1-3: eight to twelve rows: **look up** a row's total;
* rungs 4-6: twenty rows; or which row has the **highest** total --
  sorting helps;
* rungs 7-9: **sum** the totals of one category -- filter, then sum;
* rungs 10-12: **count** a category's rows over a quantity -- filter,
  sort, count;
* rungs 13-15: one row's total is not its quantity times its price:
  **find** it;
* rungs 16-19: forty rows, any of those;
* from rung 20 sixty rows, and the wrong total must be **corrected**.

Par is the clicks the reference spends -- the tools it uses and the
digits it types -- plus room for slips: eight in ten of those at rung
one, falling to a fifth from rung twenty, and never fewer than three.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

SCREEN_W, SCREEN_H = 1000, 640
CATEGORIES = ('Office', 'Kitchen', 'Garden', 'Travel', 'Tools')
WORDS = ('Brava', 'Corvo', 'Delta', 'Ember', 'Fable', 'Gilda', 'Halo',
         'Iris', 'Juno', 'Kite', 'Lumen', 'Mira', 'Nova', 'Orla', 'Pico',
         'Quill', 'Rhea', 'Sol', 'Tova', 'Umbra', 'Vela', 'Wren', 'Yara',
         'Zeno')
THINGS = {'Office': ('stapler', 'lamp', 'chair', 'binder', 'desk'),
          'Kitchen': ('kettle', 'pan', 'mixer', 'toaster', 'knife'),
          'Garden': ('hose', 'rake', 'planter', 'shears', 'bench'),
          'Travel': ('suitcase', 'pillow', 'adapter', 'bag', 'flask'),
          'Tools': ('drill', 'saw', 'hammer', 'level', 'clamp')}

#: (key, label, width); x positions follow.
COLUMNS = (('id', 'ID', 70), ('item', 'Item', 230), ('category', 'Category',
                                                     140),
           ('qty', 'Qty', 90), ('price', 'Price', 110),
           ('total', 'Total', 120))
NUMERIC = ('qty', 'price', 'total')
LEFT = 10
FILTER_Y, FILTER_H = 10, 34
HEAD_Y, HEAD_H = 54, 32
ROWS_Y, ROW_H, VISIBLE = 90, 30, 13
SUM_Y, SUM_H = 486, 30
STATUS_Y = 526
PANEL_X = 790
ANSWER = (PANEL_X, 70, 200, 44)
KEY_W, KEY_H, KEY_GAP = 60, 50, 10
KEYPAD_Y = 130
SUBMIT = (PANEL_X, KEYPAD_Y + 4 * (KEY_H + KEY_GAP), 200, 50)


def column_x() -> Dict[str, Tuple[float, float]]:
    out, x = {}, LEFT
    for key, _label, w in COLUMNS:
        out[key] = (x, w)
        x += w
    return out


def keypad() -> List[Tuple[str, Tuple[float, float, float, float]]]:
    labels = ('1', '2', '3', '4', '5', '6', '7', '8', '9', 'del', '0', '')
    out = []
    for i, label in enumerate(labels):
        if not label:
            continue
        r, c = divmod(i, 3)
        out.append((label, (PANEL_X + c * (KEY_W + KEY_GAP),
                            KEYPAD_Y + r * (KEY_H + KEY_GAP), KEY_W,
                            KEY_H)))
    return out


def chips(categories) -> List[Tuple[str, Tuple[float, float, float,
                                                float]]]:
    out = []
    x = LEFT
    for name in ('All',) + tuple(categories):
        w = 100 if name == 'All' else 120
        out.append((name, (x, FILTER_Y, w - 6, FILTER_H)))
        x += w
    return out


def sum_buttons() -> List[Tuple[str, Tuple[float, float, float, float]]]:
    xs = column_x()
    return [(key, (xs[key][0] + 4, SUM_Y, xs[key][1] - 8, SUM_H))
            for key in NUMERIC]


class Grade(NamedTuple):
    rung: int
    rows: int
    kinds: Tuple[str, ...]
    categories: int
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        rows, kinds = 8 + 2 * (r - 1), ('lookup',)
    elif r < 7:
        rows, kinds = 20, ('lookup', 'max')
    elif r < 10:
        rows, kinds = 24, ('sum',)
    elif r < 13:
        rows, kinds = 30, ('count',)
    elif r < 16:
        rows, kinds = 30, ('wrong',)
    elif r < 20:
        rows, kinds = 40, ('lookup', 'max', 'sum', 'count', 'wrong')
    else:
        rows, kinds = 60, ('sum', 'count', 'wrong', 'fix')
    slack = (0.4 - 0.3 * (r - 1) / 19.0) if r <= 20 else 0.1
    return Grade(r, rows, kinds, 3 if r < 7 else (4 if r < 16 else 5),
                 slack)


class Row(NamedTuple):
    id: int
    item: str
    category: str
    qty: int
    price: int
    total: int


class Puzzle(NamedTuple):
    rung: int
    rows: Tuple[Row, ...]
    categories: Tuple[str, ...]
    kind: str
    question: str
    answer: int
    #: The reference's tool clicks, in order (before typing).
    tools: Tuple[Tuple, ...]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    cats = tuple(draw.sample(CATEGORIES, level.categories))
    names = set()
    rows = []
    ids = draw.sample(range(101, 999), level.rows)
    for k in range(level.rows):
        cat = draw.choice(cats)
        while True:
            name = '%s %s' % (draw.choice(WORDS), draw.choice(THINGS[cat]))
            if name not in names:
                names.add(name)
                break
        qty = draw.randint(1, 12)
        price = draw.randint(2, 99)
        rows.append(Row(ids[k], name, cat, qty, price, qty * price))
    kind = draw.choice(level.kinds)
    tools: Tuple[Tuple, ...] = ()
    if kind in ('wrong', 'fix'):
        k = draw.randrange(len(rows))
        r = rows[k]
        off = draw.choice((-1, 1)) * draw.choice((1, 2, 5, 10, r.price))
        rows[k] = r._replace(total=max(1, r.total + off))
    if kind == 'lookup':
        r = draw.choice(rows)
        question = _('What is the Total for the %s?') % r.item
        answer = r.total
    elif kind == 'max':
        best = max(rows, key=lambda r: r.total)
        if sum(1 for r in rows if r.total == best.total) > 1:
            return deal(rung, seed + 1)
        question = _('Which row has the highest Total? Type its ID.')
        answer = best.id
        tools = (('sort', 'total'), ('sort', 'total'))
    elif kind == 'sum':
        cat = draw.choice(cats)
        question = _('What do the Totals of the %s rows add up to?') % cat
        answer = sum(r.total for r in rows if r.category == cat)
        tools = (('filter', cat), ('sum', 'total'))
    elif kind == 'count':
        cat = draw.choice(cats)
        bar = draw.randint(3, 9)
        question = _('How many %s rows have a Qty over %d?') % (cat, bar)
        answer = sum(1 for r in rows if r.category == cat and r.qty > bar)
        tools = (('filter', cat), ('sort', 'qty'))
    elif kind == 'wrong':
        bad = next(r for r in rows if r.total != r.qty * r.price)
        question = _('One row\'s Total is not Qty times Price. Type its ID.')
        answer = bad.id
    else:
        bad = next(r for r in rows if r.total != r.qty * r.price)
        question = _('One row\'s Total is not Qty times Price. Type the '
                     'Total it should have.')
        answer = bad.qty * bad.price
    return Puzzle(level.rung, tuple(rows), cats, kind, question, answer,
                  tools)


def fewest(puzzle: Puzzle) -> int:
    return len(puzzle.tools) + len(str(puzzle.answer)) + 1


def par(puzzle: Puzzle) -> int:
    best = fewest(puzzle)
    return best + max(3, int(round(grade(puzzle.rung).slack * best * 2)))


class Sheet:
    """The spreadsheet's state: filter, sort, scroll, stats, answer."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.filter = 'All'
        self.sort: Optional[Tuple[str, bool]] = None   # (column, descending)
        self.scroll = 0
        self.stat: Optional[str] = None
        self.typed = ''
        self.clicks = 0
        self.pointer = [SCREEN_W / 2.0, SCREEN_H / 2.0]
        self.submitted: Optional[int] = None

    # --- what is on screen -------------------------------------------

    def visible_rows(self) -> List[Row]:
        rows = [r for r in self.puzzle.rows
                if self.filter == 'All' or r.category == self.filter]
        if self.sort:
            col, down = self.sort
            rows.sort(key=lambda r: getattr(r, col), reverse=down)
        return rows

    def shown(self) -> List[Row]:
        return self.visible_rows()[self.scroll:self.scroll + VISIBLE]

    def max_scroll(self) -> int:
        return max(0, len(self.visible_rows()) - VISIBLE)

    def stats(self) -> Optional[Tuple[int, int, int]]:
        if self.stat is None:
            return None
        values = [getattr(r, self.stat) for r in self.visible_rows()]
        return (sum(values), len(values), max(values) if values else 0)

    def targets(self) -> List[Tuple[Tuple, Tuple[float, float, float,
                                                   float]]]:
        out = [(('filter', name), rect)
               for name, rect in chips(self.puzzle.categories)]
        xs = column_x()
        for key, _label, _w in COLUMNS:
            x, w = xs[key]
            out.append((('sort', key), (x, HEAD_Y, w, HEAD_H)))
        out += [(('sum', key), rect) for key, rect in sum_buttons()]
        out += [(('key', label), rect) for label, rect in keypad()]
        out.append((('submit',), SUBMIT))
        return out

    def target_at(self, x: float, y: float) -> Optional[Tuple]:
        for action, (rx, ry, w, h) in self.targets():
            if rx <= x <= rx + w and ry <= y <= ry + h:
                return action
        return None

    # --- acting --------------------------------------------------------

    def move(self, dx: float, dy: float) -> None:
        self.pointer[0] = max(0.0, min(SCREEN_W, self.pointer[0] + dx))
        self.pointer[1] = max(0.0, min(SCREEN_H, self.pointer[1] + dy))

    def wheel(self, way: int) -> None:
        self.scroll = max(0, min(self.max_scroll(), self.scroll + 3 * way))

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        if x is not None:
            self.pointer = [x, y]
        self.clicks += 1
        action = self.target_at(*self.pointer)
        if action is not None:
            self.do(action)

    def do(self, action: Tuple) -> None:
        kind = action[0]
        if kind == 'filter':
            self.filter = action[1]
            self.scroll = 0
        elif kind == 'sort':
            col = action[1]
            if self.sort and self.sort[0] == col:
                self.sort = (col, not self.sort[1])
            else:
                self.sort = (col, False)
            self.scroll = 0
        elif kind == 'sum':
            self.stat = action[1]
        elif kind == 'key':
            if action[1] == 'del':
                self.typed = self.typed[:-1]
            elif len(self.typed) < 7:
                self.typed += action[1]
        elif kind == 'submit' and self.typed:
            self.submitted = int(self.typed)


def plan(puzzle: Puzzle) -> List[Tuple]:
    """The reference's clicks: its tools, the digits, Submit."""
    return list(puzzle.tools) + [('key', d) for d in str(puzzle.answer)] + \
        [('submit',)]
