#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Piano Man: the scales, the ladder, the run's rules, the pilot, the
sound, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import pianoman as M

DT = 1 / 60.0


def play(run, pilot, seconds=120.0):
    for _k in range(int(seconds / DT)):
        for port in pilot(run):
            M.act(run, port)
        run.step(DT)
        if run.result is not None:
            break
    return run.result


class TheScales(unittest.TestCase):

    def test_they_are_real_scales(self):
        self.assertEqual(M.SCALES['major'], (0, 2, 4, 5, 7, 9, 11))
        self.assertEqual(M.SCALES['minor'], (0, 2, 3, 5, 7, 8, 10))
        self.assertEqual(M.SCALES['major pentatonic'], (0, 2, 4, 7, 9))
        for steps in M.SCALES.values():
            self.assertEqual(steps[0], 0)
            self.assertEqual(sorted(set(steps)), list(steps))
            self.assertLess(steps[-1], 12)

    def test_every_note_of_every_melody_is_in_its_scale(self):
        for rung in range(1, 61):
            for seed in range(25):
                p = M.deal(rung, seed=seed)
                self.assertIn(p.scale, p.level.scales)
                for k in p.melody:
                    self.assertTrue(M.in_scale(p, k), (rung, seed))
                    self.assertTrue(0 <= k < p.level.keys)

    def test_the_keyboard_starts_on_middle_c(self):
        self.assertAlmostEqual(M.freq(9), 440.0)
        self.assertAlmostEqual(M.freq(0), 261.63, places=1)
        self.assertEqual(M.name(0), 'C')
        self.assertTrue(M.is_black(1))
        self.assertFalse(M.is_black(4))


class TheLadder(unittest.TestCase):

    def test_it_starts_with_two_notes_and_grows(self):
        self.assertEqual(M.grade(1).notes, 2)
        last = 0
        for rung in range(1, 80):
            n = M.grade(rung).notes
            self.assertGreaterEqual(n, last)
            self.assertEqual(len(M.deal(rung, seed=rung).melody), n)
            last = n
        self.assertEqual(last, 24)

    def test_the_help_falls_away(self):
        self.assertTrue(M.grade(1).lights)
        self.assertFalse(M.grade(4).lights)
        self.assertTrue(M.grade(7).tinted)
        self.assertFalse(M.grade(10).tinted)
        self.assertEqual(M.grade(10).keys, 25)
        self.assertEqual(M.grade(16).mark, 'keynote')
        self.assertEqual(M.grade(30).listens, 0)

    def test_a_marked_first_note_is_the_first_note(self):
        for rung in (1, 4, 7, 10, 13):
            p = M.deal(rung, seed=3)
            self.assertEqual(p.mark, p.melody[0])
        p = M.deal(20, seed=3)
        self.assertEqual((M.LOW + p.mark) % 12, p.keynote)

    def test_longer_melodies_come_home(self):
        for seed in range(30):
            p = M.deal(18, seed=seed)
            self.assertEqual((M.LOW + p.melody[-1]) % 12, p.keynote)

    def test_a_seed_deals_the_same_melody(self):
        self.assertEqual(M.deal(12, seed=5), M.deal(12, seed=5))
        self.assertNotEqual(M.deal(12, seed=5).melody,
                            M.deal(12, seed=6).melody)

    def test_no_one_melody_is_worth_learning(self):
        for rung in (1, 4, 7):
            seen = collections.Counter(M.deal(rung, seed=s).melody
                                       for s in range(600))
            self.assertLess(seen.most_common(1)[0][1], 600 * 0.2, rung)


class TheRun(unittest.TestCase):

    def test_keys_do_not_count_while_it_plays(self):
        run = M.Run(M.deal(1, seed=1))
        self.assertTrue(run.playing)
        run.press(run.puzzle.melody[0])
        self.assertEqual(run.played, [])

    def test_the_keys_light_only_on_the_first_rungs(self):
        run = M.Run(M.deal(1, seed=1))
        lit = set()
        while run.playing:
            run.step(DT)
            lit.add(run.lit())
        self.assertEqual(lit - {None}, set(run.puzzle.melody))
        run = M.Run(M.deal(5, seed=1))
        while run.playing:
            run.step(DT)
            self.assertIsNone(run.lit())

    def test_playing_it_back_passes(self):
        for rung in (1, 4, 7, 10, 13, 16, 30, 60):
            for seed in range(10):
                run = M.Run(M.deal(rung, seed=seed))
                self.assertEqual(play(run, M.autopilot)[0], True, rung)
                self.assertEqual(run.played, M.solve(run.puzzle))

    def test_one_wrong_key_ends_it(self):
        run = M.Run(M.deal(7, seed=2))
        while run.playing:
            run.step(DT)
        m = run.puzzle.melody
        run.press(m[0])
        run.press((m[1] + 1) % run.puzzle.level.keys)
        self.assertEqual(run.result[0], False)
        run.press(m[1])
        self.assertEqual(len(run.played), 2)

    def test_hearing_it_again(self):
        run = M.Run(M.deal(1, seed=2))
        n = len(run.notes)
        run.listen()                         # still playing: ignored
        self.assertEqual(run.listens, 2)
        while run.playing:
            run.step(DT)
        run.listen()
        self.assertEqual(run.listens, 1)
        self.assertEqual(len(run.notes), 2 * n)
        self.assertTrue(run.playing)
        while run.playing:
            run.step(DT)
        run.press(run.puzzle.melody[0])
        run.listen()                         # not once it is begun
        self.assertEqual(run.listens, 1)
        run = M.Run(M.deal(30, seed=2))
        while run.playing:
            run.step(DT)
        run.listen()
        self.assertFalse(run.playing)

    def test_waiting_runs_out_of_time(self):
        run = M.Run(M.deal(1, seed=2))
        self.assertEqual(play(run, lambda r: [])[0], False)

    def test_the_melody_and_the_keys_both_sound(self):
        run = M.Run(M.deal(4, seed=2))
        p = run.puzzle
        self.assertEqual([round(n.freq, 3) for n in run.notes],
                         [round(M.freq(k), 3) for k in p.melody])
        play(run, M.autopilot)
        self.assertEqual(len(run.notes), 2 * len(p.melody))

    def test_random_and_fixed_play_seldom_pass(self):
        rng = random.Random(4)
        for rung in (1, 4):
            keys = M.grade(rung).keys
            wins = sum(play(M.Run(M.deal(rung, seed=s)),
                            lambda r: [] if r.playing
                            else [rng.randrange(keys)])[0]
                       for s in range(200))
            self.assertLess(wins, 12, rung)
            for fixed in ((0, 2), (4, 7), (7, 9), (12, 9)):
                def pilot(r, fixed=fixed):
                    return [] if r.playing else \
                        [fixed[len(r.played) % len(fixed)]]
                wins = sum(play(M.Run(M.deal(rung, seed=s)), pilot)[0]
                           for s in range(200))
                self.assertLess(wins, 40, (rung, fixed))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_pilot_passes_through_the_ports(self):
        for rung in (1, 7, 16):
            pilot = queued(M.autopilot, lambda task: task.run)
            self.assertEqual(drive('piano_man', rung, pilot, seed=3,
                                   steps=4000), [1.0], rung)

    def test_idle_and_a_wrong_key_fail(self):
        self.assertEqual(drive('piano_man', 1, lambda task: None, seed=3,
                               steps=4000), [-1.0])

        def off(task):
            run = task.run
            return None if run.playing else (run.puzzle.melody[0] + 1) % 13
        self.assertEqual(drive('piano_man', 1, off, seed=3, steps=4000),
                         [-1.0])

    def test_hearing_again_through_its_port(self):
        asked = []

        def policy(task):
            run = task.run
            if run.playing:
                return None
            if not asked:
                asked.append(1)
                return M.LISTEN
            return run.puzzle.melody[len(run.played)]
        self.assertEqual(drive('piano_man', 1, policy, seed=3, steps=4000),
                         [1.0])
        self.assertTrue(asked)

    def test_the_agent_hears_the_melody_and_its_own_keys(self):
        from nwenv import catalog
        env = catalog.env_class('piano_man')(seed=1, rung=1, trials=1,
                                             adaptive=False)

        def loud(steps, port=None):
            most = 0
            for k in range(steps):
                env.step(port if k == 0 else None)
                chunk = env._public_audio
                if chunk:
                    most = max([most] + [abs(v) for v in memoryview(
                        chunk['audio_pcm']).cast('h')])
            return most
        try:
            self.assertGreater(loud(150), 1000)
            run = env.task.run
            while run.playing:
                env.step(None)
            loud(40)                          # let it ring out
            self.assertLess(loud(20), 200)
            self.assertGreater(loud(30, run.puzzle.melody[0]), 1000)
        finally:
            env.close()

    def test_every_rung_draws_and_keys_can_be_clicked(self):
        from neural_workshop.ui.pianoman import PianoMan
        from uisupport import close_overlays, reset_window
        close_overlays()
        task = PianoMan()
        try:
            for rung in (1, 7, 12, 40):
                task.rng = random.Random(2)
                task.start_rung = rung
                task.total_trials = 1
                task.adaptive = False
                task.start_run()
                task.on_draw()
                self.assertEqual(len(task.hits) >= task.run.puzzle.level.keys,
                                 True, rung)
        finally:
            task.close()
            close_overlays()
            reset_window()


if __name__ == '__main__':
    unittest.main()
