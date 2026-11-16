# -*- coding: utf-8 -*-
"""The Cipher Abyss on screen: a laboratory and its machine.

On the left is the machine, humming, with its intake row under it:
the input being built, slot by slot. Along the bottom is the palette
of symbols, each with its number (the machines count with them), and
the buttons: delete, run, and ready for the test. On the right is the
laboratory notebook: every experiment so far, what went in and what
came out, and in the test what was asked and what the machine gave.
Each symbol has a colour, a shape and a note, and the machine plays
its answer as a little tune.

Above the intake row is the hypothesis board: pick blocks from its menu
(only those that fit the next slot are offered) to write down a guess at
the rule, then Check runs it over the whole notebook, rows marked green
where it fits and red where it does not. From rung 10 Submit gives the
rule itself as the answer, judged by how it behaves. "Predict" makes you
say what the machine will give before each run.

Mouse: click a symbol to add it, a slot to take it out, then Run; click
a menu line to add that block, a notebook row to mark it.
Keys: 1-8 add a symbol, Backspace takes one out, Enter runs (or answers),
T starts the test; Up/Down move in the block menu, Space adds the block,
Z undoes one, C checks, S submits, P predicts; PageUp/PageDown scroll the
notebook, M marks the last row, N shows or hides numbers, O sorts.

For the agent boundary: ports 0-11 move the drawn pointer, 12 presses
and 13 lets go; 14-21 add symbols 0-7, 22 deletes, 23 runs or answers,
24 starts the test, 25/26 move in the block menu, 27 adds the block,
28 undoes one, 29 checks, 30 submits, 31 predicts, 32/33 scroll, 34
marks, 35 numbers, 36 sorts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import json
import math
import os
from typing import Optional

import pyglet
from pyglet.window import key

from .. import cipherabyss as model
from .. import runtime
from ..paths import get_data_dir
from ..i18n import _
from . import polish
from .handtask import HandTask

COLOURS = ((226, 72, 64), (64, 130, 230), (70, 190, 100), (240, 200, 60),
           (170, 90, 210), (245, 140, 50), (40, 190, 190), (240, 110, 170))


class CipherAbyss(HandTask):
    """Work out the hidden machine, then answer for it."""

    instance: Optional['CipherAbyss'] = None

    TITLE = 'The Cipher Abyss'
    TASK_ID = 'cipher_abyss'
    PREFIX = 'CIPHER'
    CATEGORY = 'reasoning'
    FEEDBACK = 9.0
    MODEL = model
    EVENT_KEYS = dict([(getattr(key, '_%d' % (i + 1)), model.SYM + i)
                       for i in range(model.SYMBOLS)]
                      + [(key.BACKSPACE, model.DELETE),
                         (key.RETURN, model.RUN), (key.ENTER, model.RUN),
                         (key.T, model.TEST), (key.DOWN, model.NEXT_BLOCK),
                         (key.UP, model.PREV_BLOCK),
                         (key.SPACE, model.ADD_BLOCK),
                         (key.Z, model.UNDO_BLOCK), (key.C, model.CHECK),
                         (key.S, model.SUBMIT), (key.P, model.PREDICT),
                         (key.PAGEUP, model.SCROLL_UP),
                         (key.PAGEDOWN, model.SCROLL_DOWN),
                         (key.M, model.MARK), (key.N, model.NUMBERS),
                         (key.O, model.SORT)])
    EXPORT_KEY = key.X
    BACK = (18, 20, 34)
    FOOTNOTE = _('1-8 symbols  Enter run  T test  Up/Down/Space blocks  '
                 'C check  S submit  P predict  Esc menu')
    SEEN = 'cipher_abyss_tutorial_seen'

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            name = dict((k + 1, n) for k, (_s, n) in
                        enumerate(model.STAGES))[self.run.level.stage]
            self.message = _('What does the machine do? (%s)') % _(name)
        return ok

    # --- pieces --------------------------------------------------------

    def sym(self, v: int, x: float, y: float, r: float, group,
            alpha: int = 255) -> None:
        c = COLOURS[v] + (alpha,)
        dark = polish.mix(COLOURS[v], (0, 0, 0), 0.4) + (alpha,)
        if v == 0:
            self.disc((x, y), r, dark, group)
            self.disc((x, y), r - 2, c, group)
        elif v == 1:
            self.rect(x - r, y - r, 2 * r, 2 * r, dark, group)
            self.rect(x - r + 2, y - r + 2, 2 * r - 4, 2 * r - 4, c, group)
        elif v == 6:                                  # a star
            pts = []
            for k in range(10):
                rr = r if k % 2 == 0 else r * 0.45
                a = math.pi / 2 + math.pi * k / 5
                pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
            for k in range(5):
                self.poly([(x, y), pts[2 * k], pts[2 * k + 1]], c, group)
                self.poly([(x, y), pts[2 * k + 1], pts[(2 * k + 2) % 10]],
                          c, group)
        elif v == 7:                                  # a cross
            w = r * 0.38
            self.rect(x - r, y - w, 2 * r, 2 * w, dark, group)
            self.rect(x - w, y - r, 2 * w, 2 * r, dark, group)
            self.rect(x - r + 2, y - w + 2, 2 * r - 4, 2 * w - 4, c, group)
            self.rect(x - w + 2, y - r + 2, 2 * w - 4, 2 * r - 4, c, group)
        else:
            sides = {2: 3, 3: 4, 4: 5, 5: 6}[v]
            turn = math.pi / 2 if sides != 4 else 0.0
            for rr, col in ((r + 1.5, dark), (r - 1.5, c)):
                self.poly([(x + rr * math.cos(turn + 2 * math.pi * k / sides),
                            y + rr * math.sin(turn + 2 * math.pi * k / sides))
                           for k in range(sides)], col, group)

    def row(self, seq, x: float, y: float, r: float, gap: float, group,
            alpha: int = 255) -> float:
        for i, v in enumerate(seq):
            self.sym(v, x + i * gap, y, r, group, alpha)
        return x + len(seq) * gap

    def button(self, x: float, label: str, on: bool, group) -> None:
        w = model.BUTTON_W
        base = (70, 80, 110) if on else (44, 46, 60)
        self.rect(x - w / 2, model.PAL_Y - 24, w, 48,
                  polish.mix(base, (0, 0, 0), 0.4), group)
        self.rect(x - w / 2 + 2, model.PAL_Y - 22, w - 4, 44, base, group)
        self.words(label, x, model.PAL_Y, 12, bold=True, group=group,
                   colour=(235, 235, 245, 255 if on else 120))

    # --- layers: each layer's words sit just above its shapes ---------

    def g(self):
        self.layer += 1
        self._tg = pyglet.graphics.Group(order=10 * self.layer + 5)
        return pyglet.graphics.Group(order=10 * self.layer)

    def words(self, text, x, y, size, group=None, **kw):
        return super().words(text, x, y, size,
                             group=group or getattr(self, '_tg', None), **kw)

    # --- what a player keeps (only in a visible session) ---------------

    @staticmethod
    def keeps() -> bool:
        return not runtime.wants_headless()

    def library(self) -> dict:
        if getattr(self, '_library', None) is None:
            self._library = {}
            if self.keeps():
                try:
                    with open(os.path.join(get_data_dir(),
                                           model.LIBRARY)) as handle:
                        self._library = json.load(handle)
                except (OSError, ValueError):
                    pass
        return self._library

    def _judge(self, passed: bool, message: str) -> None:
        run = self.run
        if run is not None and getattr(run, 'met', None) is None:
            run.met = model.remembered(self.library(), run.machine.rule,
                                       self.rung)
            if passed and self.keeps():
                self._library = model.learn(self.library(),
                                            run.machine.rule, self.rung)
                try:
                    with open(os.path.join(get_data_dir(), model.LIBRARY),
                              'w') as handle:
                        json.dump(self._library, handle, indent=1)
                except OSError:
                    pass
            if self.keeps():
                try:
                    with open(os.path.join(get_data_dir(),
                                           model.ROUNDS), 'a') as handle:
                        handle.write(json.dumps(model.metrics(run)) + '\n')
                except OSError:
                    pass
        # The machine itself is on the end screen: the verdict stays short.
        super()._judge(passed, message.split('. ')[0])

    def on_key_press(self, symbol, modifiers):
        if symbol == self.EXPORT_KEY and self.run is not None:
            self.export()
            return True
        return super().on_key_press(symbol, modifiers)

    def export(self) -> None:
        """X: the notebook as a text file in the data folder."""
        if not self.keeps():
            return
        path = os.path.join(get_data_dir(), 'cipher_abyss_notebook.txt')
        try:
            with open(path, 'w') as handle:
                handle.write(model.notebook_text(self.run))
            self.run.say(_('Notebook saved: %s') % path)
        except OSError:
            self.run.say(_('Could not save the notebook'))

    # --- the first round ever ------------------------------------------

    def _seen_path(self) -> str:
        return os.path.join(get_data_dir(), self.SEEN)

    def tutorial(self) -> bool:
        """Whether to show the first-time arrows (rung 1, never seen)."""
        if self.rung != 1 or not self.keeps():
            return False
        if getattr(self, '_seen', None) is None:
            try:
                self._seen = os.path.exists(self._seen_path())
            except OSError:
                self._seen = True
        return not self._seen

    def _saw_tutorial(self) -> None:
        self._seen = True
        if not self.keeps():
            return
        try:
            with open(self._seen_path(), 'w') as handle:
                handle.write('1\n')
        except OSError:
            pass

    # --- the scene -----------------------------------------------------

    def _scene(self, run, s: float) -> None:
        g = self.g()
        self.rect(0, 0, 1000, 124, (28, 30, 46), g)             # bench
        bx, by, bx1, by1 = model.BOARD
        self.rect(bx, by, bx1 - bx, by1 - by, (34, 38, 58), g)  # board
        nx, ny, nx1, ny1 = model.NOTE
        self.rect(nx, ny, nx1 - nx, ny1 - ny, (232, 226, 206), g)
        self.rect(nx, ny1 - 28, nx1 - nx, 28, (214, 206, 182), g)
        for k in range(model.NOTE_ROWS + 1):
            yy = model.note_y(k) + model.NOTE_ROW / 2
            self.line((nx + 8, yy), (nx1 - 8, yy), 1, (200, 196, 230), g)
        self._machine(run)
        self._intake(run)
        self._board(run)
        self._notebook(run)
        self._bench(run)
        if run.result is not None:
            self._end(run)
        elif self.tutorial():
            self._guide(run)
        if run.flash and run.t - run.flash_at < 2.5 and run.result is None:
            self.words(run.flash, 260, 176, 11, bold=True,
                       colour=(250, 220, 120, 255))

    def _machine(self, run) -> None:
        g = self.g()
        x0, y0, x1, y1 = 20, 452, 500, 632
        self.rect(x0, y0, x1 - x0, y1 - y0, (50, 56, 80), g)
        self.rect(x0 + 6, y0 + 6, x1 - x0 - 12, y1 - y0 - 12,
                  (70, 78, 108), g)
        busy = 0.0 <= run.t - run.shown_at < 0.16 * 8
        speed = 4.0 if busy else 1.0
        for k in range(3):                                      # gears
            a = run.t * speed * (1.2 if k % 2 else -1.0)
            cx, cy, r = 70 + 50 * k, 580 - 12 * (k % 2), 20 + 5 * (k % 2)
            for t in range(9):
                b = a + 2 * math.pi * t / 9
                self.disc((cx + r * math.cos(b), cy + r * math.sin(b)), 4,
                          (120, 128, 160), g)
            self.disc((cx, cy), r - 2, (96, 104, 140), g)
            self.disc((cx, cy), 4, (40, 44, 60), g)
        for k in range(5):                                      # lights
            on = int(run.t * (9 if busy else 3) + k * 1.7) % 4 == 0
            self.disc((50 + 30 * k, 480), 5,
                      (250, 220, 120) if on else (90, 80, 60), g)
        self.words(_('CIPHER MACHINE'), 120, 620, 9, bold=True,
                   colour=(200, 210, 240, 255))
        cx = 350
        q = run.question()
        if run.twins_q and run.result is None:
            self.words(_('A SECOND MACHINE:'), cx, 612, 11, bold=True,
                       colour=(250, 220, 120, 255))
            self.words(model.describe(run.machine.other), cx, 572, 9,
                       width=280, colour=(230, 235, 250, 255))
            self.words(_('The same as yours? S says so. If not, give an '
                         'input that tells them apart, then Enter'),
                       cx, 500, 8, width=280, colour=(220, 220, 240, 220))
        elif q is not None:
            invert = run.machine.kind == 'invert'
            self.words((_('TEST %d of %d: what input gives') if invert else
                        _('TEST %d of %d: what does it give for')) %
                       (run.test_no + 1, len(run.machine.tests)),
                       cx + 10, 612, 9.5, bold=True,
                       colour=(250, 220, 120, 255))
            gap = min(40, 260 / max(1, len(q)))
            self.row(q, cx - (len(q) - 1) * gap / 2, 575, min(14, gap / 2.8),
                     gap, g)
            if len(q) > run.level.length:
                self.words(_('a longer row than any experiment!'), cx, 520,
                           9, bold=True, colour=(250, 160, 120, 255))
            self.words(_('(the machine starts afresh for the test)'),
                       cx, 538, 8, colour=(220, 220, 240, 200))
            self.words(_('Answer in the row below, then Enter'), cx, 482,
                       9, colour=(220, 220, 240, 220))
        elif run.last is not None and run.result is None:
            x, y = run.last
            shown = int((run.t - run.shown_at) / 0.16) + 1
            gap = min(30, 130 / max(1, len(x), len(y)))
            r = min(10, gap / 2.8)
            self.row(x, 270, 590, r, gap, g)
            self.words(_('in'), 255 - r, 590, 8, anchor='right',
                       colour=(220, 220, 240, 200))
            self.row(y[:shown], 270, 556, r, gap, g)
            self.words(_('out'), 255 - r, 556, 8, anchor='right',
                       colour=(220, 220, 240, 200))
            self.words(_('%d experiments left') % run.left(), cx + 30, 500,
                       12, bold=True, colour=(220, 230, 250, 255))
        else:
            self.words(_('%d experiments left') % run.left(), cx, 560, 13,
                       bold=True, colour=(220, 230, 250, 255))
            self.words(_('Build an input below and run it'), cx, 520, 9,
                       colour=(220, 220, 240, 200))

    def _intake(self, run) -> None:
        g = self.g()
        n = run.want()
        for i in range(n):
            x = model.slot_x(i, n)
            h = min(24, 190 / max(1, n))
            self.rect(x - h, model.ROW_Y - 22, 2 * h, 44, (36, 40, 60), g)
            self.rect(x - h + 2, model.ROW_Y - 20, 2 * h - 4, 40,
                      (24, 26, 40), g)
            if i < len(run.entry):
                self.sym(run.entry[i], x, model.ROW_Y, min(16, h * 0.7), g)
                if run.numbers:
                    self.words('%d' % run.entry[i], x + h - 7,
                               model.ROW_Y - 14, 7,
                               colour=(230, 230, 240, 230))
        px, py = model.PREDICT_AT
        on = run.predicting
        self.rect(px - 52, py - 14, 104, 28,
                  (90, 120, 80) if on else (44, 46, 60), g)
        label = _('PREDICT: on') if on else _('PREDICT: off')
        if run.pending is not None:
            label = _('your guess')
        self.words(label, px, py, 9, bold=True,
                   colour=(235, 235, 245, 255))

    def _block_lines(self, board):
        """(depth, words) per block: the board as a little tree."""
        out, need = [], [0]
        for b in board:
            depth = need.pop() if need else 0
            out.append((depth, b))
            if b.kind == 'form':
                need.extend([depth + 1] * len(model.FORMS[b.value]))
        return out, need

    def _board(self, run) -> None:
        g = self.g()
        bx, by, bx1, by1 = model.BOARD
        self.words(_('HYPOTHESIS BOARD'), bx + 10, by1 - 14, 10, bold=True,
                   anchor='left', colour=(200, 210, 240, 255))
        for name, (x, y) in model.BOARD_BUTTONS.items():
            w = model.BOARD_BUTTON_W
            on = {'undo': bool(run.board),
                  'check': run.hypothesis() is not None,
                  'submit': run.hypothesis() is not None and
                  lv_ok(run)}[name]
            self.rect(x - w / 2, y - 12, w, 24,
                      (70, 80, 110) if on else (44, 46, 60), g)
            if name == 'submit' and run.twins_q:
                on = True
            self.words({'undo': _('UNDO'), 'check': _('CHECK'),
                        'submit': _('SAME') if run.twins_q
                        else _('SUBMIT')}[name], x, y, 9, bold=True,
                       colour=(235, 235, 245, 255 if on else 110))
        # The menu: blocks that fit the next slot.
        menu = run.menu()
        top = max(0, run.cursor - model.MENU_ROWS + 1)
        need = model.expecting(run.board)
        self.words(_('next: %s') % model.SLOT_WORDS[need[-1]] if need
                   else _('complete'), 232, by1 - 14, 8,
                   anchor='left', colour=(250, 220, 120, 255))
        for j, b in enumerate(menu[top:top + model.MENU_ROWS]):
            y = model.menu_y(j)
            if top + j == run.cursor:
                self.rect(model.MENU_X - 4, y - 10, 194, 20, (70, 80, 120), g)
            self.words(self._fit_text(b.label, 30), model.MENU_X, y, 8,
                       anchor='left', colour=(
                           (250, 220, 120, 255) if b.kind == 'form' else
                           (220, 225, 245, 255)))
        if len(menu) > top + model.MENU_ROWS:
            self.words(_('... more (Down)'), model.MENU_X,
                       model.menu_y(model.MENU_ROWS) + 4, 7, anchor='left',
                       colour=(160, 170, 200, 255))
        # The hypothesis itself, as a tree.
        x0 = 232
        self.line((x0 - 8, by + 30), (x0 - 8, by1 - 30), 1, (70, 80, 110), g)
        lines, depths = self._block_lines(run.board)
        rows = lines[-11:]
        for j, (depth, b) in enumerate(rows):
            y = by1 - 36 - 18 * j
            self.words(self._fit_text(b.label, 34 - 2 * depth),
                       x0 + 14 * depth, y, 8, anchor='left',
                       colour=(250, 220, 120, 255) if b.kind == 'form'
                       else (230, 235, 250, 255))
        if need and depths and run.board:
            y = by1 - 36 - 18 * len(rows)
            if y > by + 36:
                self.words('_ ' + model.SLOT_WORDS[need[-1]],
                           x0 + 14 * depths[-1], y, 8, anchor='left',
                           colour=(150, 160, 190, 255))
        if not run.board:
            self.words(_('Write your guess at the rule here'), x0 + 4,
                       by1 - 36, 8, anchor='left',
                       colour=(150, 160, 190, 255))
        if run.checked:
            good = sum(run.checked.values())
            self.words(run.check_text, 360, by + 46, 9, bold=True,
                       colour=((120, 220, 140, 255)
                               if good == len(run.checked)
                               else (240, 120, 100, 255)))

    @staticmethod
    def _fit_text(text: str, n: int) -> str:
        n = max(8, n)
        return text if len(text) <= n else text[:n - 1] + '…'

    def _notebook(self, run) -> None:
        under = self.g()
        g = self.g()
        nx, ny, nx1, ny1 = model.NOTE
        self.words(_('NOTEBOOK'), 870, ny1 - 14, 10, bold=True, colour=ink_())
        self.words(_('sort: %s') % (_('by time') if run.order == 'time'
                                    else _('by input')),
                   640, ny1 - 14, 8, colour=ink_())
        self.words(_('numbers: %s') % (_('on') if run.numbers else _('off')),
                   770, ny1 - 14, 8, colour=ink_())
        rows = run.visible()
        n = max([len(r[2]) for r in rows] + [len(r[3]) for r in rows] + [1])
        size = min(9.0, 160 / (2.3 * n + 2))
        gap = 2.2 * size + 3
        for j, (kind, i, x, y) in enumerate(reversed(rows)):
            yy = model.note_y(j)
            key_ = (kind, i)
            if key_ in run.marks:
                self.rect(nx + 2, yy - 17, nx1 - nx - 4, 34,
                          (250, 236, 150), under)
            if key_ in run.checked:
                self.rect(nx + 4, yy - 15, 6, 30,
                          (60, 170, 80) if run.checked[key_]
                          else (210, 60, 50), under)
            label = '%d' % (i + 1) if kind == 'run' else _('test')
            if kind == 'test':
                ok = run.answers[i][2]
                colour = (40, 140, 60, 255) if ok else (200, 50, 40, 255)
            else:
                colour = (90, 90, 110, 255)
            self.words(label, nx + 26, yy, 8, colour=colour)
            # the output appears symbol by symbol for the newest run
            newest = kind == 'run' and i == len(run.log) - 1
            shown = len(y)
            if newest:
                shown = int((run.t - run.shown_at) / 0.16) + 1
            x0 = nx + 52
            end = self.row(x, x0, yy, size, gap, g)
            if run.numbers:
                for p, v in enumerate(x):
                    self.words('%d' % v, x0 + p * gap, yy - size - 4, 6,
                               colour=(70, 70, 90, 255))
            self.poly([(end + 2, yy + 5), (end + 12, yy), (end + 2, yy - 5)],
                      (90, 90, 110), g)
            o0 = end + 22
            self.row(y[:shown], o0, yy, size, gap, g)
            for p, v in enumerate(y[:shown]):
                if run.numbers:
                    self.words('%d' % v, o0 + p * gap, yy - size - 4, 6,
                               colour=(70, 70, 90, 255))
                if p >= len(x) or x[p] != v:                # changed here
                    self.disc((o0 + p * gap, yy + size + 4), 1.8,
                              (200, 90, 60), g)
            guess = run.predictions.get(i) if kind == 'run' else None
            if guess is not None and shown >= len(y):
                self.words('✓' if guess == y else '✗', nx1 - 14, yy, 11,
                           bold=True, colour=((40, 140, 60, 255)
                                              if guess == y
                                              else (200, 50, 40, 255)))
        total = len(run.rows())
        if total > model.NOTE_ROWS:
            self.words(_('%d rows (PageUp/PageDown)') % total, 750, ny + 12,
                       7, colour=ink_())

    def _bench(self, run) -> None:
        g = self.g()
        lv = run.level
        for i in range(lv.k):
            x = model.pal_x(i)
            self.rect(x - 32, model.PAL_Y - 30, 64, 60, (44, 46, 60), g)
            self.sym(i, x, model.PAL_Y + 4, 17, g)
            self.words('%d' % i, x + 24, model.PAL_Y - 20, 9,
                       colour=(220, 220, 230, 230))
        n = run.want()
        self.button(model.DEL_X, _('DELETE'), bool(run.entry), g)
        self.button(model.RUN_X, _('ANSWER') if run.testing else _('RUN'),
                    len(run.entry) == n, g)
        self.button(model.TEST_X, _('TEST ME'), not run.testing, g)

    def _guide(self, run) -> None:
        """First-time arrows, at rung 1 only, until the first round ends."""
        g = self.g()
        tips = ((model.pal_x(1), 108, _('1. click symbols to build an '
                                        'input')),
                (model.RUN_X, 108, _('2. run it')),
                (750, 450, _('3. watch what comes out')),
                (model.TEST_X, 108, _('4. when you know, take the test')))
        if run.testing:
            step = 3
        elif len(run.entry) == run.want():
            step = 1
        elif run.log and not run.entry:
            step = 3 if len(run.log) >= 3 else 2
        else:
            step = 0
        x, y, text = tips[step]
        if step == 0:                        # beside the palette, pointing
            x = model.pal_x(run.level.k - 1) + 40
            self.poly([(x, model.PAL_Y), (x + 14, model.PAL_Y + 9),
                       (x + 14, model.PAL_Y - 9)], (250, 220, 120), g)
            self.rect(x + 14, model.PAL_Y - 12, 250, 24, (250, 220, 120), g)
            self.words(text, x + 139, model.PAL_Y, 9, bold=True,
                       colour=(30, 30, 40, 255))
            return
        x = max(140.0, min(860.0, x))
        self.poly([(x - 9, y + 16), (x + 9, y + 16), (x, y + 2)],
                  (250, 220, 120), g)
        self.rect(x - 130, y + 16, 260, 24, (250, 220, 120), g)
        self.words(text, x, y + 28, 9, bold=True, colour=(30, 30, 40, 255))

    def _end(self, run) -> None:
        """The end of a round: the rule, and what each experiment told."""
        if self.tutorial():
            self._saw_tutorial()
        info = getattr(run, 'summary', None)
        if info is None:
            info = run.summary = model.summary(run)
            model.end_tones(run, info['bits'])
        g = self.g()
        x0, y0, x1, y1 = 20, 124, 500, 450
        self.rect(x0, y0, x1 - x0, y1 - y0, (24, 26, 40), g)
        ok, words = run.result
        self.words(_('CRACKED') if ok else _('NOT CRACKED'), 260, y1 - 20,
                   14, bold=True, colour=((120, 220, 140, 255) if ok
                                          else (240, 120, 100, 255)))
        self.words(_('The machine: ') + info['words'], 260, y1 - 50, 9,
                   width=440, colour=(230, 235, 250, 255))
        self.words(info['code'], 260, y1 - 92, 8, width=440,
                   colour=(170, 190, 230, 255))
        met = getattr(run, 'met', None) or []
        if met:
            self.words(_('You met %s at rung %d') % (
                ', '.join(op for op, _r in met[:3]), min(r for _o, r in met)),
                260, y1 - 120, 8, colour=(250, 220, 120, 255))
        # what each experiment told, in bits
        bits = info['bits']
        self.words(_('What each experiment told (bits)'), 140, 300, 8,
                   colour=(220, 220, 240, 255))
        top = max(bits + [1.0])
        for i, b in enumerate(bits):
            h = 70 * b / top
            col = (250, 220, 120) if i == info['best'] else (110, 150, 220)
            self.rect(40 + 22 * i, 210, 16, max(1.0, h), col, g)
            self.words('%d' % (i + 1), 48 + 22 * i, 200, 7,
                       colour=(200, 200, 220, 255))
        if bits:
            self.words(_('%.1f bits per experiment') %
                       (sum(bits) / len(bits)), 140, 180, 8,
                       colour=(220, 220, 240, 255))
        self.words(_('%d experiments (a careful player: %d)   %.0f s') % (
            len(run.log), len(run.machine.plan), run.t), 260, 150, 8,
            colour=(200, 205, 230, 255))
        # what the reference would have run
        self.words(_('A careful experimenter ran'), 390, 300, 8,
                   colour=(220, 220, 240, 255))
        plan = info['reference'][:6]
        for j, x in enumerate(plan):
            gap = min(18, 160 / max(1, len(x)))
            self.row(x, 320, 278 - 18 * j, min(6, gap / 2.8), gap, g)


    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)


def ink_():
    return (60, 60, 90, 255)


def lv_ok(run) -> bool:
    """Whether the rung lets the rule itself be given as the answer."""
    return run.level.stage >= 4
