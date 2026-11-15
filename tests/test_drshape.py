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
                for mode in dict(M.grade(rung).modes):
                    if mode in M.SCENES:
                        continue
                    p = M.deal(rung, seed=seed, mode=mode)
                    self.assertEqual(len(p.candidates), p.level.candidates)
                    right = p.candidates[p.answer]
                    self.assertIs(right.form, p.form)
                    self.assertEqual(right.size, 1.0)
                    for k, c in enumerate(p.candidates):
                        if k != p.answer:
                            self.assertTrue(
                                M.distinct(p.form, c.form, 0.1, 1.0, c.size),
                                (rung, seed, mode, k))

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
        self.assertIn('scene', dict(M.grade(20).modes))
        self.assertEqual(set(dict(M.grade(23).modes)), set(M.MODES))
        self.assertEqual((M.grade(7).colours, M.grade(8).colours,
                          M.grade(11).colours), (1, 2, 3))
        self.assertIn('curve', M.grade(5).families)
        self.assertIn('solid', M.grade(11).families)
        self.assertFalse(M.grade(16).floor)
        self.assertTrue(M.grade(17).floor)
        self.assertTrue(M.grade(23).each_side)
        self.assertEqual(M.grade(23).candidates, 6)
        self.assertLess(M.grade(24).overload, M.grade(30).overload)
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
                    tunes = {M.tune(c.form, p.view) for c in p.candidates}
                    self.assertEqual(len(tunes), len(p.candidates),
                                     (rung, mode, seed))


class TheForms(unittest.TestCase):

    def test_every_family_builds_with_faces_where_it_should(self):
        draw = random.Random(1)
        for family in ('curve', 'prism', 'pyramid', 'solid', 'space'):
            for _k in range(5):
                f = M.build(family, M.draw_params(family, draw))
                self.assertGreaterEqual(len(f.segs), 3, family)
                far = max(math.sqrt(M._dot(p, p)) for p in M.points(f.segs))
                self.assertAlmostEqual(far, 1.0, places=6)
                if family in ('prism', 'pyramid', 'solid'):
                    self.assertTrue(f.faces, family)

    def test_a_nudge_changes_the_shape(self):
        draw = random.Random(2)
        for family in ('curve', 'prism', 'pyramid', 'solid'):
            for _k in range(6):
                params = M.draw_params(family, draw)
                a = M.build(family, params)
                b = M.build(family, M.nudge(family, params, draw))
                self.assertTrue(M.distinct(a, b, 0.02), (family, params))

    def test_turning_a_coloured_form_keeps_it_the_same(self):
        draw = random.Random(3)
        f = M.colour(M.build('prism', M.draw_params('prism', draw)), 3,
                     draw)
        g = M.turned_form(M.random_turn(draw), f)
        self.assertFalse(M.distinct(f, g))

    def test_moving_the_colours_makes_another_thing(self):
        draw = random.Random(4)
        moved = 0
        for _k in range(20):
            f = M.colour(M.build('space', M.draw_params('space', draw)), 2,
                         draw)
            g = M.recoloured(f, draw)
            if g.tints != f.tints and M.distinct(f, g):
                moved += 1
                self.assertFalse(M.unlike(f.segs, g.segs, 1e-6))
        self.assertGreater(moved, 10)

    def test_a_symmetric_recolouring_is_not_called_different(self):
        # A square with alternate colours swapped is the same square
        # turned a quarter: it must not be dealt as a look-alike.
        sq = M.form_of(M.trace([op for _k in range(4)
                                for op in (('F', 1.0), ('Y', 90))]),
                       [0, 1, 0, 1])
        swapped = M.Form(sq.segs, [1, 0, 1, 0], [])
        self.assertFalse(M.distinct(sq, swapped))

    def test_size_makes_another_thing(self):
        f = M.build('solid', M.draw_params('solid', random.Random(5)))
        self.assertTrue(M.distinct(f, f, 0.12, 1.0, 1.6))
        self.assertFalse(M.distinct(f, f, 0.12, 1.0, 1.1))

    def test_colour_look_alikes_appear_from_rung_8(self):
        kinds = 0
        for seed in range(20):
            p = M.deal(9, seed=seed, mode='see')
            for k, c in enumerate(p.candidates):
                if k != p.answer and not M.unlike(c.segs, p.shape, 1e-6) \
                        and c.form.tints != p.form.tints:
                    kinds += 1
        self.assertGreater(kinds, 5)


class TheFloor(unittest.TestCase):

    def test_sized_look_alikes_look_the_same_size(self):
        seen = 0
        for seed in range(20):
            p = M.deal(18, seed=seed, mode='see')
            self.assertTrue(p.floor)
            right = p.candidates[p.answer]
            self.assertGreater(right.depth, 0.0)
            for c in p.candidates:
                if c.size != 1.0:
                    seen += 1
                    self.assertFalse(M.unlike(c.segs, p.shape, 1e-6))
                    # How big it looks (size over distance) falls in the
                    # range the true-size cards cover.
                    looks = c.size / c.depth
                    self.assertTrue(1 / 4.4 - 1e-9 <= looks <= 1 / 2.3)
        self.assertGreater(seen, 10)

    def test_rest_puts_the_lowest_point_on_the_ground(self):
        f = M.build('pyramid', M.draw_params('pyramid', random.Random(1)))
        turn = M.random_turn(random.Random(2))
        g, lift = M.rest(f, turn, 0.7)
        low = min(min(a[1], b[1]) for a, b in g.segs)
        self.assertAlmostEqual(low + lift, 0.0, places=9)


class TheScenes(unittest.TestCase):

    def test_the_right_card_is_the_place_and_no_other_is(self):
        for rung in (20, 23, 28):
            for mode in ('scene', 'hear_scene'):
                if mode not in dict(M.grade(rung).modes):
                    continue
                for seed in range(6):
                    p = M.deal(rung, seed=seed, mode=mode)
                    self.assertTrue(p.scene)
                    lays = [c.layout for c in p.candidates]
                    self.assertEqual(lays[p.answer], p.layout)
                    for k, lay in enumerate(lays):
                        if k != p.answer:
                            self.assertFalse(M.same_layout(lay, p.layout))
                            for j in range(k):
                                self.assertFalse(M.same_layout(lay, lays[j]))

    def test_things_stand_apart_and_clear_of_the_beacon(self):
        for seed in range(10):
            p = M.deal(21, seed=seed, mode='scene')
            spots = [(x, z) for _t, x, z in p.layout] + \
                [(M.PLATFORM - 0.1, 0.0)]
            for i in range(len(spots)):
                self.assertLess(math.hypot(*spots[i]), M.PLATFORM)
                for j in range(i):
                    self.assertGreater(math.hypot(
                        spots[i][0] - spots[j][0],
                        spots[i][1] - spots[j][1]), 1.6)

    def test_seen_scenes_are_shown_from_elsewhere_heard_ones_not(self):
        p = M.deal(21, seed=1, mode='scene')
        for c in p.candidates:
            gap = abs((c.look - p.look + math.pi) % (2 * math.pi) - math.pi)
            self.assertGreater(gap, 0.85)
        self.assertEqual(len({c.look for c in p.candidates}), 1)
        q = M.deal(25, seed=1, mode='scene')
        self.assertGreater(len({c.look for c in q.candidates}), 1)
        h = M.deal(25, seed=1, mode='hear_scene')
        self.assertTrue(all(c.look == h.look for c in h.candidates))

    def test_each_thing_sings_from_where_it_stands(self):
        p = M.deal(21, seed=3, mode='scene')
        self.assertEqual([i for i, _a, _b in p.parts], [0, 1, 2])
        for i, x, z in p.layout:
            mine = [n for n in p.notes if n.who == -10 - i]
            self.assertTrue(mine)
            self.assertEqual({n.voice for n in mine}, {i})
            where = M.seen_from(p.look, (x, 0.0, z))
            pan = sum(n.pan + n.pan2 for n in mine) / (2 * len(mine))
            if abs(where[0] / where[2]) > 0.15:
                self.assertEqual(pan > 0, where[0] > 0)
            self.assertTrue(all(n.room > 0 for n in mine))

    def test_the_camera_looks_at_the_middle(self):
        for look in (0.0, 1.0, 2.5, 4.0):
            c = M.seen_from(look, (0.0, 0.0, 0.0))
            self.assertAlmostEqual(c[0], 0.0, places=9)
            self.assertAlmostEqual(c[1], 0.0, places=9)
            self.assertAlmostEqual(c[2], M.ORBIT, places=9)


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
        alone, _d, _e = M.sing(p.form, p.view, 0.0)
        self.assertEqual([(round(x.freq, 3), round(x.pan, 3), x.voice)
                          for x in card],
                         [(round(x.freq, 3), round(x.pan, 3), x.voice)
                          for x in alone])

    def test_colours_are_instruments(self):
        p = M.deal(12, seed=2, mode='see')
        shape = [x for x in p.notes if x.who == -1]
        self.assertEqual([x.voice for x in shape], p.form.tints)
        used = sorted(set(p.form.tints))
        names = [p.patches[t].name for t in used]
        self.assertEqual(len(set(names)), len(names))

    def test_an_echo_moves_key_and_instruments_but_keeps_the_tune(self):
        p = M.deal(12, seed=4, mode='echo')
        shape = [x for x in p.notes if x.who == -1]
        k, a, b = p.spans[p.answer]
        card = [x for x in p.notes if x.who == k and a <= x.t < b]
        steps = {round(12 * math.log2(c.freq / s.freq))
                 for s, c in zip(shape, card)}
        self.assertEqual(len(steps), 1)          # one shift for every note
        self.assertNotEqual(steps, {0})
        # Each colour moves to its own new instrument.
        self.assertEqual([x.voice - M.TINTS for x in card],
                         [x.voice for x in shape])
        for t in set(x.voice for x in shape):
            self.assertNotEqual(p.patches[t].name,
                                p.patches[t + M.TINTS].name)
        self.assertEqual([round(x.pan, 3) for x in shape],
                         [round(x.pan, 3) for x in card])

    def test_early_echoes_are_the_same_sound(self):
        p = M.deal(3, seed=1, mode='echo')
        shape = [x for x in p.notes if x.who == -1]
        k, a, b = p.spans[p.answer]
        card = [x for x in p.notes if x.who == k and a <= x.t < b]
        self.assertEqual([x.freq for x in shape], [x.freq for x in card])
        for x, y in zip(shape, card):
            self.assertEqual(p.patches[x.voice], p.patches[y.voice])


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

    def test_far_sounds_are_quieter_later_and_roomier(self):
        f = M.build('solid', M.draw_params('solid', random.Random(1)))
        near, _d, _e = M.sing(f, M.IDENTITY, 0.0, distance=2.0)
        far, _d, _e = M.sing(f, M.IDENTITY, 0.0, distance=8.0)
        self.assertGreater(near[0].gain, far[0].gain)
        self.assertGreater(far[0].t, near[0].t)
        self.assertGreater(far[0].room, near[0].room)
        self.assertGreaterEqual(near[0].bright, far[0].bright)

    def test_the_room_rings_on_after_the_note(self):
        dry = M.Note(0.0, 0.2, 440.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0, 0, -1)
        wet = dry._replace(room=0.8)
        tail = (0.5, 0.65)
        a = array.array('h', M.synth([dry], *tail, [PURE]))
        b = array.array('h', M.synth([wet], *tail, [PURE]))
        self.assertEqual(max(map(abs, a)), 0)
        self.assertGreater(max(map(abs, b)), 100)

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
