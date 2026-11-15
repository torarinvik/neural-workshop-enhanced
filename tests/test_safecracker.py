#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Safecracker: the dial, the word, the handle, the door, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import safecracker as M


def grab_dial(run):
    q = run.see(M.DIAL[0], M.DIAL[1] + 0.6)
    run.hand.to(q[0], q[1])
    run.press()


def sweep(run, numbers):
    """Drag round the dial by *numbers*, clockwise positive."""
    steps = max(1, int(abs(numbers) * M.PER / 3.0))
    for _k in range(steps):
        u, v = run.under()
        a = math.atan2(v - M.DIAL[1], u - M.DIAL[0]) - math.radians(
            numbers * M.PER / steps)
        q = run.see(M.DIAL[0] + 1.2 * math.cos(a),
                    M.DIAL[1] + 1.2 * math.sin(a))
        run.hand.to(q[0], q[1])
        run.step(1 / 120.0)


def type_word(run, word):
    for ch in word:
        M.act(run, M.LETTER + ord(ch) - ord('A'))


class TheLadder(unittest.TestCase):

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 20, 40)}
        self.assertTrue(g[1].glow and not g[4].glow)
        self.assertEqual((g[1].tumblers, g[4].tumblers, g[7].tumblers),
                         (1, 2, 3))
        self.assertTrue(g[7].drift and not g[4].drift)
        self.assertTrue(g[10].decoys and g[10].strict and not g[7].strict)
        self.assertTrue(g[13].swing and not g[10].swing)
        self.assertGreater(g[40].tumblers, g[20].tumblers)
        self.assertLess(g[40].mark, g[1].mark)

    def test_clues_have_the_answers_they_ask_for(self):
        for rung in (1, 4, 7, 10, 13, 16):
            for s in range(12):
                safe = M.deal(rung, seed=s)
                self.assertTrue(safe.answer.isalpha())
                if 'lamp on the left' in safe.clue and \
                        'backwards' not in safe.clue:
                    self.assertEqual(safe.answer, M.COLOURS[safe.lamps[0]])
                if 'bolts' in safe.clue:
                    self.assertEqual(safe.answer, M.COUNTS[safe.bolts])
                if safe.clue.startswith('Type the word '):
                    self.assertIn(safe.answer, safe.clue)

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22, 35):
            for s in range(2):
                safe = M.deal(rung, seed=s)
                self.assertTrue(M.play(safe)[0], (rung, s))
                self.assertFalse(M.play(safe, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(safe, lambda run: [
                    draw.randrange(M.PORTS)])[0])


class TheDial(unittest.TestCase):

    def test_dragging_round_it_turns_it_and_it_ticks(self):
        run = M.Run(M.deal(1, seed=1))
        grab_dial(run)
        sweep(run, 5.0)
        self.assertAlmostEqual(run.reading, 5.0, delta=0.3)
        ticks = [n for n in run.notes if n.voice == M.TICK]
        self.assertIn(len(ticks), (4, 5, 6))
        sweep(run, -8.0)
        self.assertAlmostEqual(run.reading, 37.0, delta=0.3)

    def test_the_thunk_comes_only_the_right_way_round(self):
        safe = M.deal(4, seed=1)
        run = M.Run(safe)
        grab_dial(run)
        back = (0 - safe.combo[0]) % M.NUMBERS
        sweep(run, -(back + 2.0))
        self.assertFalse([n for n in run.notes if n.voice == M.THUNK])
        run = M.Run(safe)
        grab_dial(run)
        sweep(run, safe.combo[0] + 2.0)
        self.assertEqual(len([n for n in run.notes if n.voice == M.THUNK]),
                         1)

    def test_letting_go_on_the_number_sets_the_tumbler(self):
        safe = M.deal(4, seed=1)
        run = M.Run(safe)
        grab_dial(run)
        sweep(run, safe.combo[0])
        run.release()
        self.assertEqual(run.set, 1)
        grab_dial(run)
        sweep(run, -((safe.combo[0] - safe.combo[1]) % M.NUMBERS))
        run.release()
        self.assertEqual(run.set, 2)

    def test_letting_go_elsewhere_is_a_strike_once_mistakes_count(self):
        easy = M.Run(M.deal(4, seed=1))
        grab_dial(easy)
        sweep(easy, (easy.safe.combo[0] + 5) % M.NUMBERS or 3)
        easy.release()
        self.assertEqual((easy.set, easy.strikes), (0, 0))
        hard = M.Run(M.deal(10, seed=1))
        for n in range(3):
            self.assertIsNone(hard.result)
            grab_dial(hard)
            sweep(hard, 3.0 if abs(M.between(
                (hard.reading + 3) % M.NUMBERS,
                hard.safe.combo[0])) > 2 else 6.0)
            hard.release()
            self.assertEqual(hard.strikes, n + 1)
        self.assertFalse(hard.result[0])

    def test_the_lamp_shows_the_number_only_at_the_bottom(self):
        safe = M.deal(1, seed=2)
        run = M.Run(safe)
        grab_dial(run)
        sweep(run, safe.combo[0])
        self.assertTrue(run.on_mark())
        self.assertTrue(run.level.glow)
        self.assertFalse(M.grade(4).glow)


class TheWordAndTheHandle(unittest.TestCase):

    def test_the_answer_sets_the_word_and_backspace_rubs_out(self):
        safe = M.deal(1, seed=3)
        run = M.Run(safe)
        type_word(run, 'Q')
        self.assertEqual(run.typed, 'Q')
        M.act(run, M.BACKSPACE)
        self.assertEqual(run.typed, '')
        type_word(run, safe.answer)
        self.assertTrue(run.worded)

    def test_a_wrong_word_is_a_strike_once_mistakes_count(self):
        safe = M.deal(10, seed=3)
        run = M.Run(safe)
        wrong = ''.join('Q' for _c in safe.answer)
        type_word(run, wrong)
        self.assertEqual((run.strikes, run.typed), (1, ''))

    def pull(self, run):
        ku, kv = run.knob()
        q = run.see(ku, kv)
        run.hand.to(q[0], q[1])
        run.press()
        for k in range(1, 12):
            q = run.see(ku, kv - 0.1 * k)
            run.hand.to(q[0], q[1])
            run.step(1 / 60.0)
            if run.result is not None:
                break

    def test_the_handle_rattles_until_both_locks_are_done(self):
        safe = M.deal(1, seed=3)
        run = M.Run(safe)
        self.pull(run)
        self.assertIsNone(run.result)
        self.assertLess(run.lever, 0.2)
        self.assertTrue(any(n.voice == M.RATTLE for n in run.notes))
        run.release()
        type_word(run, safe.answer)
        grab_dial(run)
        sweep(run, safe.combo[0])
        run.release()
        self.assertTrue(run.unlocked)
        self.pull(run)
        self.assertEqual(run.result[0], True)

    def test_the_door_swings_and_the_camera_drifts(self):
        still = M.Run(M.deal(1, seed=1))
        a = still.see(*M.HANDLE)
        for _k in range(60):
            still.step(1 / 30.0)
        self.assertEqual(a, still.see(*M.HANDLE))
        moving = M.Run(M.deal(14, seed=1))
        a = moving.see(*M.HANDLE)
        seen = set()
        for _k in range(90):
            moving.step(1 / 30.0)
            seen.add(round(moving.swing(), 2))
        self.assertGreater(len(seen), 5)
        self.assertNotEqual(a, moving.see(*M.HANDLE))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('safecracker', 7, pilot, seed=1, steps=4000),
                         [1.0])
        self.assertEqual(drive('safecracker', 1, lambda t: None, seed=1,
                               steps=3600), [-1.0])

    def test_the_agent_hears_the_dial(self):
        from nwenv import catalog
        env = catalog.env_class('safecracker')(seed=2, rung=4, trials=1,
                                               adaptive=False)
        try:
            heard = 0
            for _k in range(500):
                task = env.task
                port = None
                if task.phase == 'playing' and task.run is not None:
                    ports = M.autopilot(task.run)
                    port = ports[0] if ports else None
                env.step(port)
                chunk = env._public_audio
                if chunk:
                    heard += len(chunk['audio_pcm'])
            self.assertGreater(heard, 0)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
