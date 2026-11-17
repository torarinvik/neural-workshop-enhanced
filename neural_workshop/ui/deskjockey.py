# -*- coding: utf-8 -*-
"""Desk Jockey on screen: the rulebook on the left, the form on top of
the tray in the middle with whatever is attached to it, the tray on
the right, and the things that can be done with a form along the
bottom.

Click what is to be done, or press its key (1-9, then 0 and the
letters shown). A memo, when one arrives, is added under the rules
and stays there.

For the agent boundary: port 0 approves, 1 sends back, 2 holds, 3-5
forward to Finance, Purchasing and Personnel, and port 5 + n rejects
under rule n. Ports the book has no use for do nothing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import deskjockey as model
from ..geometry import calc_fontsize
from ..i18n import _
from .spacetask import ChoiceTask

KEYS = '1234567890QWERTY'
PAPER, CARD = (250, 247, 236), (232, 240, 250)
PAPER_DARK, CARD_DARK = (44, 42, 38), (36, 44, 56)
MEMO = (176, 96, 20)
GOOD, BAD = (40, 150, 80), (200, 60, 55)


class DeskJockey(ChoiceTask):
    """Deal with each form by the book."""

    instance: Optional['DeskJockey'] = None

    TITLE = 'Desk Jockey'
    TASK_ID = 'desk_jockey'
    PREFIX = 'DESKJOCKEY'
    CATEGORY = 'order'
    BUTTONS = 0
    FEEDBACK = 2.5
    FOOTNOTE = _('click what is to be done with the form, or press its key '
                 '  Esc: menu')

    def __init__(self) -> None:
        self.shift = None
        self.last: Optional[bool] = None
        super().__init__()

    def _clear_trial(self) -> None:
        super()._clear_trial()
        self.shift = None

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _deal(self) -> bool:
        ok = super()._deal()
        self.shift = model.Shift(self.puzzle)
        self.last = None
        return ok

    def choose(self, port: int) -> None:
        shift = self.shift
        if self.phase != self.PLAY or shift is None:
            return
        right = shift.act(port)
        if right is None:
            return
        self.last = right
        if shift.result is not None:
            self._judge(*shift.result)
        else:
            self._redraw()

    def _key(self, symbol: int, modifiers: int) -> None:
        if self.puzzle is None:
            return
        name = key.symbol_string(symbol).lstrip('_')
        if len(name) == 1 and name in KEYS:
            at = KEYS.index(name)
            if at < len(self.puzzle.buttons):
                self.choose(self.puzzle.buttons[at])

    # --- drawing ---------------------------------------------------------

    def _lines(self, lines, x, top, width, size) -> float:
        """Wrapped lines one under another; where the last one ends."""
        y = top
        for words, colour, bold in lines:
            label = self._text(words, x, y, size, anchor='left',
                               anchor_y='top', width=width, colour=colour,
                               bold=bold)
            y -= label.content_height + size * 0.55
        return y

    def _draw_scene(self, left, bottom, width, height) -> None:
        p, shift = self.puzzle, self.shift
        if shift is None:
            return
        ink = tuple(self.ink) + (255,)
        dim = (150, 150, 158, 255)
        paper = PAPER_DARK if self.dark else PAPER
        card = CARD_DARK if self.dark else CARD
        pad = width * 0.012
        bar = height * 0.2                   # the buttons' strip
        top = bottom + height
        body = height - bar - pad
        # The rulebook.
        bw = width * 0.44
        self._box(left, bottom + bar + pad, bw, body, paper, self.ink,
                  thickness=1.0)
        lines = [(model.say(p, rule), ink, False) for rule in p.rules]
        lines.append((model.say_order(p), ink, True))
        lines += [(model.say_memo(m), MEMO + (255,), True)
                  for m in shift.memos()]
        size = calc_fontsize(12)
        for _again in range(8):
            mark = len(self.drawn)
            self._text(_('THE BOOK'), left + pad, top - pad, size,
                       anchor='left', anchor_y='top', bold=True)
            end = self._lines(lines, left + pad, top - pad - size * 2.2,
                              bw - 2 * pad, size)
            if end >= bottom + bar + pad * 2 or size <= 6.5:
                break
            for item in self.drawn[mark:]:
                item.delete()
            del self.drawn[mark:]
            size *= 0.9
        # The form on top of the tray.
        fx, fw = left + bw + pad, width * 0.33
        self._box(fx, bottom + bar + pad, fw, body, paper, self.ink,
                  thickness=1.0)
        size = min(calc_fontsize(12), body / 37.0)
        if shift.top is not None:
            form = p.forms[shift.top]
            yes, no = _('yes'), _('NO')
            rows = [(_('FORM'), ink, True),
                    (_('Name: %s') % form.name, ink, False),
                    (_('For: %s') % model.KINDS[form.kind], ink, False),
                    (_('From: %s') % model.DEPTS[form.dept], ink, False),
                    (_('Day: %d') % form.day, ink, False),
                    (_('Amount: %d') % form.amount, ink, False),
                    (_('Signed: %s') % (yes if form.signed else no), ink,
                     False),
                    (_('Countersigned: %s') % (yes if form.counter
                                               else _('no')), ink, False)]
            y = self._lines(rows, fx + pad, top - pad, fw - 2 * pad, size)
            tests = {rule.test for rule in p.rules}
            if tests & {'no_card', 'name', 'expired'}:
                y -= size
                held = [(_('ID CARD'), ink, True)]
                if form.card is None:
                    held.append((_('none attached'), dim, False))
                else:
                    held += [(_('Name: %s') % form.card.name, ink, False),
                             (_('Good until day %d') % form.card.expires,
                              ink, False)]
                box_top = y
                y = self._lines(held, fx + pad * 2, y - pad, fw - 4 * pad,
                                size)
                self._box(fx + pad, y, fw - 2 * pad, box_top - y, card,
                          group=self.body_group)
            if tests & {'no_receipt', 'sum'}:
                y -= size
                held = [(_('RECEIPTS'), ink, True)]
                if form.receipts is None:
                    held.append((_('none attached'), dim, False))
                else:
                    held.append(('   '.join(str(v) for v in form.receipts),
                                 ink, False))
                box_top = y
                y = self._lines(held, fx + pad * 2, y - pad, fw - 4 * pad,
                                size)
                self._box(fx + pad, y, fw - 2 * pad, box_top - y, card,
                          group=self.body_group)
        # The tray.
        tx = fx + fw + pad
        tw = left + width - tx
        rows = [(_('TRAY'), ink, True)]
        for k, at in enumerate(shift.tray):
            form = p.forms[at]
            rows.append(('%s %s -- %s' % ('>' if k == 0 else ' ', form.name,
                                          model.KINDS[form.kind]),
                         ink if k == 0 else dim, k == 0))
        rows.append((_('done: %d') % len(shift.done), dim, False))
        self._lines(rows, tx, top - pad, tw, min(size, body / (
            4.3 * (len(rows) + 1))))
        # What can be done.
        n = len(p.buttons)
        cols = (n + 1) // 2 if n > 5 else n
        rows_n = (n + cols - 1) // cols
        bw2, bh = width / cols, bar / rows_n
        back = (46, 50, 58) if self.dark else (232, 235, 240)
        for k, port in enumerate(p.buttons):
            x = left + (k % cols) * bw2
            y = bottom + bar - (k // cols + 1) * bh
            border, thick = self.ink, 2
            if self.phase == 'judged' and shift.done:
                _at, did, want = shift.done[-1]
                if port == want:
                    border, thick = GOOD, 5
                elif port == did:
                    border, thick = BAD, 5
            self._box(x + 3, y + 3, bw2 - 6, bh - 6, back, border,
                      thickness=thick)
            label = self._text('%s  %s' % (KEYS[k], model.name_of(p, port)),
                               x + bw2 / 2, y + bh / 2,
                               min(calc_fontsize(13), bh * 0.3))
            if label.content_width > bw2 * 0.9:
                label.font_size *= bw2 * 0.9 / label.content_width
            self.hits.append((x, y, bw2, bh,
                              lambda c=port: self.choose(c)))

    def _facts(self) -> str:
        shift = self.shift
        if self.puzzle is None or shift is None:
            return ''
        said = _('rung %d  %d/%d   forms left %d') % (
            self.rung, self.trial, self.total_trials, len(shift.tray))
        if self.puzzle.level.slips:
            said += _('   slips %d of %d allowed') % (
                shift.slips, self.puzzle.level.slips)
        if shift.done and self.phase == self.PLAY:
            at, _did, want = shift.done[-1]
            said += '   ' + (_('last: right') if self.last else
                             _('last: wrong -- %s')
                             % model.name_of(self.puzzle, want))
        return said
