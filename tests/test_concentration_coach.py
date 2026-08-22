#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Coach mode on Concentration: a turn, not a flip, decides anything.

The board is scored on lapses, and one scalar per board is the sparsest
reward on this boundary -- eight pairs is at least sixteen flips with
nothing paid in between.  Coach mode pays per completed turn instead:
green for a pair matched, red for a lapse, and nothing at all for the
half-turn or the honest miss.

The honest miss is the one that matters.  Missing on two cards you had
never seen is not a mistake, it is how the board is learned; paying it
would score the deal rather than the player, and would leave a loop of
flips with a return.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import UI_IMPORT_ERROR

if UI_IMPORT_ERROR is None:
    from neural_workshop import state
    from neural_workshop.ui.concentration import Concentration
    from nwenv.frames import capture_rgba
    from nwenv.outcome import derive_public_outcome


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class CoachPaysTurns(unittest.TestCase):

    def setUp(self):
        self.task = Concentration()
        self.task.coach = True
        self.task.pairs = 4
        self.task.peek_ms = 0
        self.task.deal()
        self.task.phase = 'playing'

    def tearDown(self):
        self.task.close()

    def scalar(self):
        window = state.window
        window.switch_to()
        window.dispatch_events()
        self.task.on_draw()
        width, height, rgba = capture_rgba(window)
        outcome = derive_public_outcome(rgba, width, height, ['x'], 1)
        return None if outcome is None else outcome['scalar']

    def pair(self):
        """Two cards that match, straight off the deal."""
        for one in self.task.cards:
            for two in self.task.cards:
                if one is not two and one.index == two.index:
                    return one, two
        self.fail('a dealt board held no pair')

    def test_half_a_turn_pays_nothing(self):
        one, _two = self.pair()
        self.task.flip(one)
        self.assertIsNone(self.scalar(),
                          'the first card of a turn painted a verdict')

    def test_a_matched_pair_reads_plus_one(self):
        one, two = self.pair()
        self.task.flip(one)
        self.task.flip(two)
        if self.task.phase != 'playing':
            self.skipTest('that pair cleared the board; nothing to assert')
        self.assertEqual(self.scalar(), 1.0)

    def test_an_honest_miss_pays_nothing(self):
        """Two cards never seen before that do not match: not a lapse."""
        first = self.task.cards[0]
        other = next(c for c in self.task.cards if c.index != first.index)
        self.task.flip(first)
        self.task.flip(other)
        self.assertEqual(self.task.lapses, 0, 'that miss was scored a lapse')
        self.assertIsNone(self.scalar(), 'an honest miss painted a verdict')

    def test_a_lapse_reads_minus_one(self):
        """Turning over a card whose partner you have already been shown.

        One honest turn sets it up: two strangers, no match, both now
        seen. Turning over the partner of one of them and then failing
        to take it is the lapse -- the board has shown where the pair
        is, and a player who forgot nothing would close it.
        """
        byindex = {}
        for card in self.task.cards:
            byindex.setdefault(card.index, []).append(card)
        pairs = [cards for cards in byindex.values() if len(cards) == 2]
        self.assertGreaterEqual(len(pairs), 3, 'need three pairs to set up')
        (a1, a2), (b1, _b2), (c1, _c2) = pairs[:3]

        self.task.flip(a1)
        self.task.flip(b1)             # two strangers: an honest miss
        self.assertEqual(self.task.lapses, 0, 'an honest miss was scored')
        self.assertIsNone(self.scalar(), 'an honest miss painted a verdict')

        self.task.flip(a2)             # its partner a1 has been shown
        self.task.flip(c1)             # ...and the pair is left on the table
        self.assertTrue(self.task.lapses, 'the known pair was not scored')
        self.assertEqual(self.scalar(), -1.0)


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class CoachOffIsThePlainGame(unittest.TestCase):

    def test_no_verdict_mid_board(self):
        task = Concentration()
        task.pairs = 4
        task.peek_ms = 0
        task.deal()
        task.phase = 'playing'
        try:
            self.assertFalse(task.coach)
            window = state.window
            for card in task.cards[:2]:
                task.flip(card)
                if task.phase != 'playing':
                    return
                window.switch_to()
                window.dispatch_events()
                task.on_draw()
                width, height, rgba = capture_rgba(window)
                self.assertIsNone(
                    derive_public_outcome(rgba, width, height, ['x'], 1),
                    'coach off, yet a verdict mid-board')
        finally:
            task.close()


if __name__ == '__main__':
    unittest.main()
