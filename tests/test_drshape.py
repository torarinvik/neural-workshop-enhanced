#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dr Shape: the turtle, the look-alikes, the song, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import array
import math
import random
import unittest

from spatialsupport import close_overlays, reset_window
from uisupport import needs_ui

from neural_workshop import drshape as M

RUNGS = (1, 3, 5, 8, 11, 14, 17, 20, 25, 30)
PURE = M.make_patch('sine', random.Random(0))


class TheTurtle(unittest.TestCase):

    def test_a_square_closes_and_is_one_unit_out(self):
        segs = M.trace([op for _k in range(4) for op in (('F', 1.0),
                                                           ('Y', 90))])
        self.assertEqual(len(segs), 4)
        self.assertEqual(len(M.points(segs)), 4)
        far = max(math.sqrt(M._dot(p, p)) for p in M.points(segs))
        self.assertAlmostEqual(far, 1.0, places=6)

    def test_turning_a_shape_keeps_its_signature(self):
        draw = random.Random(4)
        segs = M.trace(M.make_program('space', draw))
        spun = M.turned(M.random_turn(draw), segs)
        self.assertFalse(M.unlike(segs, spun, 1e-6))

    def test_a_mirror_keeps_the_signature_and_flips_the_hand(self):
        draw = random.Random(9)
        for _k in range(20):
            segs = M.trace(M.make_program('space', draw))
            if abs(M.handedness(segs)) > 0.1:
                break
        mirror = M.mirrored(segs)
        self.assertFalse(M.unlike(segs, mirror, 1e-6))
        self.assertAlmostEqual(M.handedness(mirror), -M.handedness(segs),
                               places=6)
        # No rotation undoes a mirror.
        self.assertAlmostEqual(
            M.handedness(M.turned(M.random_turn(draw), mirror)),
            M.handedness(mirror), places=6)

    def test_a_flat_shape_has_no_hand(self):
        segs = M.trace(M.make_program('star', random.Random(1)))
        self.assertAlmostEqual(M.handedness(segs), 0.0, places=6)

    def test_every_family_draws(self):
        for family in ('polygon', 'star', 'spiral', 'space', 'coil',
                       'branch'):
            segs = M.trace(M.make_program(family, random.Random(3)))
            self.assertGreaterEqual(len(segs), 3, family)


class TheLookAlikes(unittest.TestCase):

    def test_the_answer_is_the_shape_and_no_decoy_is(self):
        for rung in RUNGS:
            for seed in range(6):
                p = M.deal(rung, seed=seed)
                self.assertEqual(len(p.candidates), p.level.candidates)
                self.assertIs(p.candidates[p.answer].segs, p.shape)
                hand = M.handedness(p.shape)
                for k, c in enumerate(p.candidates):
                    if k == p.answer:
                        continue
                    if M.unlike(c.segs, p.shape):
                        continue
                    # Same distances: only a mirror of a handed shape.
                    self.assertGreater(abs(hand), 0.08, (rung, seed, k))
                    self.assertLess(M.handedness(c.segs) * hand, 0.0)

    def test_the_answer_moves_around(self):
        answers = {M.deal(5, seed=s).answer for s in range(30)}
        self.assertEqual(answers, set(range(4)))

    def test_the_ladder(self):
        self.assertTrue(M.grade(1).keep)
        self.assertFalse(M.grade(3).keep)
        self.assertTrue(M.grade(8).mirror)
        self.assertEqual(dict(M.grade(1).modes), {'see': 1.0})
        self.assertIn('echo', dict(M.grade(3).modes))
        self.assertIn('sing', dict(M.grade(5).modes))
        self.assertNotIn('see', dict(M.grade(15).modes))
        self.assertEqual(set(dict(M.grade(20).modes)), set(M.MODES))
        self.assertTrue(M.grade(17).chorus)
        self.assertEqual(M.grade(20).candidates, 6)
        self.assertLess(M.grade(21).overload, M.grade(28).overload)
        self.assertLess(M.grade(5).wild, M.grade(25).wild)

    def test_every_kind_deals_at_every_rung_it_appears(self):
        for rung in RUNGS:
            for mode in dict(M.grade(rung).modes):
                p = M.deal(rung, seed=5, mode=mode)
                self.assertEqual(p.mode, mode)
                self.assertTrue(M.play(p)[0], (rung, mode))

    def test_heard_shapes_and_sound_cards_share_the_view(self):
        for mode in ('hear', 'sing', 'echo'):
            p = M.deal(15, seed=2, mode=mode)
            for c in p.candidates:
                self.assertEqual(c.view, p.view)

    def test_sound_cards_all_sound_different(self):
        for rung in (5, 8, 11, 17, 25):
            for mode in ('sing', 'echo', 'hear'):
                for seed in range(4):
                    p = M.deal(rung, seed=seed, mode=mode)
                    tunes = {M.tune(c.segs, p.view) for c in p.candidates}
                    self.assertEqual(len(tunes), len(p.candidates),
                                     (rung, mode, seed))


class TheCards(unittest.TestCase):

    def test_a_sing_trial_is_silent_until_the_cards(self):
        p = M.deal(8, seed=3, mode='sing')
        self.assertTrue(all(n.who >= 0 for n in p.notes))
        self.assertTrue(all(n.t >= p.show_end for n in p.notes))

    def test_each_card_plays_its_shape_twice_in_turn(self):
        p = M.deal(8, seed=3, mode='sing')
        n = len(p.candidates)
        self.assertEqual([k for k, _a, _b in p.spans], list(range(n)) * 2)
        ends = [b for _k, _a, b in p.spans]
        self.assertLessEqual(ends[-1], p.show_end + p.choose)
        for k, a, b in p.spans:
            run = M.Run(p)
            run.t = (a + b) / 2
            self.assertEqual(run.sounding(), k)
            mine = [x for x in p.notes if x.who == k and a <= x.t < b]
            self.assertEqual(len(mine), len(p.candidates[k].segs))

    def test_the_right_card_sings_the_shape_note_for_note(self):
        p = M.deal(8, seed=3, mode='sing')
        k, a, b = p.spans[p.answer]
        card = [x for x in p.notes if x.who == k and a <= x.t < b]
        alone, _d, _e = M.sing(p.shape, p.view, 0.0)
        self.assertEqual([round(x.freq, 3) for x in card],
                         [round(x.freq, 3) for x in alone])
        self.assertEqual([round(x.pan, 3) for x in card],
                         [round(x.pan, 3) for x in alone])

    def test_an_echo_moves_key_and_instrument_but_keeps_the_tune(self):
        p = M.deal(12, seed=4, mode='echo')
        shape = [x for x in p.notes if x.who == -1]
        k, a, b = p.spans[p.answer]
        card = [x for x in p.notes if x.who == k and a <= x.t < b]
        steps = {round(12 * math.log2(c.freq / s.freq))
                 for s, c in zip(shape, card)}
        self.assertEqual(len(steps), 1)          # one shift for every note
        self.assertNotEqual(steps, {0})
        self.assertEqual({x.voice for x in card}, {1})
        self.assertNotEqual(p.patches[1].name, p.patches[0].name)
        self.assertEqual([round(x.pan, 3) for x in shape],
                         [round(x.pan, 3) for x in card])

    def test_early_echoes_are_the_same_sound(self):
        p = M.deal(3, seed=1, mode='echo')
        shape = [x for x in p.notes if x.who == -1]
        k, a, b = p.spans[p.answer]
        card = [x for x in p.notes if x.who == k and a <= x.t < b]
        self.assertEqual([x.freq for x in shape], [x.freq for x in card])
        self.assertEqual(p.patches[0], p.patches[1])


class TheSong(unittest.TestCase):

    def test_one_note_a_stroke_higher_strokes_higher_notes(self):
        low = [((-1.0, -0.8, 0.0), (1.0, -0.8, 0.0))]
        high = [((-1.0, 0.8, 0.0), (1.0, 0.8, 0.0))]
        (a,), _d, _e = M.sing(low, M.IDENTITY, 0.0)
        (b,), _d, _e = M.sing(high, M.IDENTITY, 0.0)
        self.assertGreater(b.freq, a.freq)

    def test_left_strokes_sound_left_and_near_strokes_louder(self):
        segs = [((-1.0, 0.0, -0.9), (-0.8, 0.0, -0.9)),
                ((0.8, 0.0, 0.9), (1.0, 0.0, 0.9))]
        notes, done, end = M.sing(segs, M.IDENTITY, 0.0)
        self.assertLess(notes[0].pan, 0.0)
        self.assertGreater(notes[1].pan, 0.0)
        self.assertGreater(notes[1].gain, notes[0].gain)
        self.assertEqual(len(done), 2)
        self.assertAlmostEqual(done[-1], end)

    def test_a_note_slides_between_the_ears_with_its_stroke(self):
        (n,), _d, _e = M.sing([((-0.9, 0.0, 0.0), (0.9, 0.0, 0.0))],
                              M.IDENTITY, 0.0)
        self.assertLess(n.pan, -0.5)
        self.assertGreater(n.pan2, 0.5)
        pcm = array.array('h', M.synth([n], 0.0, n.dur, [PURE]))
        half = len(pcm) // 4 * 2
        first = pcm[:half]
        last = pcm[half:]
        self.assertGreater(sum(map(abs, first[0::2])),
                           sum(map(abs, first[1::2])))
        self.assertGreater(sum(map(abs, last[1::2])),
                           sum(map(abs, last[0::2])))

    def test_the_synth_is_stereo_and_follows_the_pan(self):
        note = M.Note(0.0, 0.3, 440.0, -1.0, -1.0, 1.0, 1.0, 1.0, 0, 0, -1)
        pcm = array.array('h', M.synth([note], 0.0, 0.3, [PURE]))
        self.assertEqual(len(pcm), 2 * int(round(0.3 * M.RATE)))
        left = sum(abs(v) for v in pcm[0::2])
        right = sum(abs(v) for v in pcm[1::2])
        self.assertGreater(left, 10 * max(1, right))

    def test_windows_join_into_the_whole(self):
        for rung, mode in ((18, 'see'), (25, 'hear'), (12, 'echo')):
            p = M.deal(rung, seed=1, mode=mode)
            t0 = p.show_end - 0.6
            whole = M.synth(p.notes, t0, t0 + 1.0, p.patches)
            parts = b''.join(M.synth(p.notes, t0 + k / 10.0,
                                     t0 + (k + 1) / 10.0, p.patches)
                             for k in range(10))
            self.assertEqual(whole, parts, (rung, mode))

    def test_every_instrument_sounds_and_none_clips(self):
        draw = random.Random(2)
        note = M.Note(0.0, 0.4, 392.0, -0.5, 0.5, 1.0, 1.0, 1.0, 0, 3, -1)
        for name in M.ALL + ('hiss',):
            for wild in (0.0, 1.0):
                patch = M.make_patch(name, draw, wild)
                pcm = array.array('h', M.synth([note], 0.0, 0.6, [patch]))
                loud = max(map(abs, pcm))
                self.assertGreater(loud, 2000, (name, wild))
                self.assertLess(loud, 30001, (name, wild))

    def test_instruments_vary_trial_to_trial(self):
        names = {M.deal(25, seed=s).patches[0] for s in range(12)}
        self.assertGreater(len(names), 8)

    def test_overload_adds_noise(self):
        self.assertGreater(len(M.deal(30, seed=1).notes),
                           2 * len(M.deal(17, seed=1).notes))


class TheRun(unittest.TestCase):

    def test_no_pick_while_the_turtle_draws(self):
        run = M.Run(M.deal(5, seed=1))
        M.act(run, run.puzzle.answer)
        self.assertIsNone(run.result)
        self.assertLess(run.strokes(), 1.0)

    def test_right_and_wrong_and_too_late(self):
        p = M.deal(5, seed=1)
        self.assertTrue(M.play(p)[0])
        wrong = (p.answer + 1) % len(p.candidates)
        self.assertFalse(M.play(p, lambda run: [wrong] if run.choosing
                                else [])[0])
        self.assertFalse(M.play(p, lambda run: [])[0])

    def test_the_reference_passes_every_rung(self):
        for rung in RUNGS:
            self.assertTrue(M.play(M.deal(rung, seed=3))[0], rung)


@needs_ui
class TheBoundary(unittest.TestCase):

    def _drive(self, pick, steps=3000):
        from nwenv import catalog
        env = catalog.env_class('dr_shape')(seed=1, rung=17, trials=1,
                                            adaptive=False)
        scalars, sound = [], 0
        try:
            for _step in range(steps):
                task = env.task
                port = None
                if task.phase == 'playing' and task.run.choosing and \
                        task.run.t > task.run.puzzle.show_end + 1.0:
                    port = pick(task.run.puzzle)
                obs, events, done = env.step(port)
                if obs.get('audio_pcm'):
                    self.assertEqual(obs['audio_channels'], 2)
                    self.assertEqual(obs['audio_rate'], M.RATE)
                    sound += len(obs['audio_pcm'])
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
            close_overlays()
            reset_window()
        return scalars, sound

    def test_the_right_pick_passes_and_carries_sound(self):
        scalars, sound = self._drive(lambda p: p.answer)
        self.assertEqual(scalars, [1.0])
        self.assertGreater(sound, 4 * M.RATE)

    def test_a_wrong_pick_fails(self):
        scalars, _sound = self._drive(
            lambda p: (p.answer + 1) % len(p.candidates))
        self.assertEqual(scalars, [-1.0])


if __name__ == '__main__':
    unittest.main()
