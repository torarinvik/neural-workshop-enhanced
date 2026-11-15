#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Field Manual: the orders, the machine, the hand, the sound, the
boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import fieldmanual as M
from neural_workshop import hand as H


def job_with(rung, want, seeds=400):
    """A job whose first order satisfies *want*."""
    for s in range(seeds):
        job = M.deal(rung, seed=s)
        if want(job.steps[0]):
            return job
    raise AssertionError('no such job')


def face_it(run, i):
    yaw, pitch = M.FRONT[run.job.parts[i].face]
    run.yaw, run.pitch = (0.0 if yaw is None else yaw), pitch


def click(run, i):
    x, y, _r = run.spot(i)
    run.hand.to(x, y)
    run.press()
    run.step(1 / 60.0)
    run.release()


class TheOrders(unittest.TestCase):

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 20, 40)}
        self.assertEqual(g[1].faces, (0,))
        self.assertEqual(len(g[7].faces), 6)
        self.assertNotIn('dial', g[1].orders)
        self.assertIn('listen', g[10].orders)
        self.assertTrue(g[13].wait and not g[10].wait)
        self.assertTrue(g[16].spin and g[16].tones and not g[13].spin)
        self.assertTrue(g[20].show and not g[16].show)
        self.assertGreater(g[40].steps, g[20].steps)
        self.assertLess(g[40].pace, g[20].pace)

    def test_every_part_has_its_own_name(self):
        for rung in (1, 7, 30):
            job = M.deal(rung, seed=3)
            names = [M.name(p) for p in job.parts]
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(len(job.steps), job.level.steps)

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22, 35):
            for s in range(2):
                job = M.deal(rung, seed=s)
                self.assertTrue(M.play(job)[0], (rung, s))
                self.assertFalse(M.play(job, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(job, lambda run: [
                    draw.randrange(M.PORTS)])[0])


class TheMachine(unittest.TestCase):

    def test_a_part_on_the_back_is_out_of_reach_until_it_is_turned(self):
        for s in range(50):
            job = M.deal(7, seed=s)
            if any(p.face == 2 for p in job.parts):
                break
        i = next(k for k, p in enumerate(job.parts) if p.face == 2)
        run = M.Run(job)
        self.assertIsNone(run.spot(i))
        run.hand.to(60, 300)
        run.press()
        self.assertEqual(run.grab, 'turn')
        for _k in range(40):
            run.hand.to(run.hand.x + 10, 300)
            run.step(1 / 60.0)
        run.release()
        self.assertGreater(abs(M.wrap(run.yaw - 25.0)), 150.0)
        self.assertIsNotNone(run.spot(i))

    def test_the_right_button_passes_and_a_wrong_one_fails(self):
        job = job_with(1, lambda s: s.kind == 'press')
        run = M.Run(job)
        click(run, job.steps[0].targets[0])
        self.assertEqual(run.result[0], True)
        run = M.Run(job)
        other = next(k for k in range(len(job.parts))
                     if k not in job.steps[0].targets)
        click(run, other)
        self.assertEqual(run.result[0], False)

    def test_a_dial_turns_a_notch_at_a_time_and_is_judged_on_letting_go(self):
        job = job_with(4, lambda s: s.kind == 'dial')
        step = job.steps[0]
        i = step.targets[0]
        run = M.Run(job)
        face_it(run, i)
        x, y, _r = run.spot(i)
        run.hand.to(x, y)
        run.press()
        gap = (step.value - run.state[i]) % M.NOTCHES
        run.hand.to(x + gap * M.NOTCH, y)
        run.step(1 / 60.0)
        self.assertEqual(run.state[i], step.value)
        self.assertEqual(run.step_no, 0)
        run.release()
        self.assertEqual(run.step_no, 1)

    def test_a_slider_follows_the_pointer_along_its_track(self):
        job = job_with(4, lambda s: s.kind == 'slide')
        step = job.steps[0]
        i = step.targets[0]
        run = M.Run(job)
        face_it(run, i)
        x, y, _r = run.spot(i)
        run.hand.to(x, y)
        run.press()
        a, b = run.track(i)
        u = (0.0, 0.5, 1.0)[step.value]
        run.hand.to(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        run.step(1 / 60.0)
        self.assertAlmostEqual(run.state[i], u, delta=0.05)
        run.release()
        self.assertEqual(run.step_no, 1)

    def test_typing_takes_the_digits_in_order(self):
        job = job_with(4, lambda s: s.kind == 'type' and not s.targets)
        run = M.Run(job)
        for ch in job.steps[0].value:
            M.act(run, M.DIGIT + int(ch))
        self.assertEqual(run.step_no, 1)
        run = M.Run(job)
        M.act(run, M.DIGIT + (int(job.steps[0].value[0]) + 1) % 10)
        self.assertFalse(run.result[0])

    def test_shift_has_to_be_held(self):
        job = job_with(10, lambda s: s.shift)
        i = job.steps[0].targets[0]
        run = M.Run(job)
        face_it(run, i)
        click(run, i)
        self.assertFalse(run.result[0])
        run = M.Run(job)
        face_it(run, i)
        run.step(1 / 60.0, M.SHIFT)
        click(run, i)
        self.assertEqual(run.step_no, 1)

    def test_the_machine_turns_by_itself_from_rung_16(self):
        run = M.Run(M.deal(16, seed=2))
        yaw = run.yaw
        for _k in range(30):
            run.step(1 / 30.0)
        self.assertNotAlmostEqual(run.yaw, yaw, places=1)

    def test_orders_vanish_from_rung_20(self):
        run = M.Run(M.deal(22, seed=2))
        self.assertTrue(run.reading())
        while run.t < run.level.show + 0.2:
            run.step(1 / 30.0)
        self.assertEqual(run.reading(), '')


class TheSound(unittest.TestCase):

    def test_acting_before_the_beeps_is_too_soon(self):
        job = job_with(13, lambda s: s.wait)
        step = job.steps[0]
        i = step.targets[0]
        run = M.Run(job)
        face_it(run, i)
        click(run, i)
        self.assertFalse(run.result[0])
        run = M.Run(job)
        while run.counted() < step.wait:
            run.step(1 / 30.0)
        self.assertTrue(any(n.voice == M.BEEP for n in run.notes))
        face_it(run, i)
        click(run, i)
        self.assertEqual(run.step_no, 1)

    def test_the_hidden_notch_tocks_only_when_asked_for(self):
        job = job_with(10, lambda s: s.kind == 'listen')
        i = job.steps[0].targets[0]
        run = M.Run(job)
        face_it(run, i)
        x, y, _r = run.spot(i)
        run.hand.to(x, y)
        run.press()
        for k in range(1, M.NOTCHES + 1):
            run.hand.to(x + k * M.NOTCH, y)
            run.step(1 / 60.0)
        voices = [n.voice for n in run.notes]
        self.assertEqual(voices.count(M.TOCK), 1)
        self.assertEqual(voices.count(M.TICK), M.NOTCHES - 1)

    def test_a_dragged_slider_sings_and_the_hum_gives_the_pitch(self):
        job = job_with(13, lambda s: s.kind == 'match')
        step = job.steps[0]
        run = M.Run(job)
        for _k in range(40):
            run.step(1 / 30.0)
        hums = [n for n in run.notes if n.voice == M.HUM]
        self.assertTrue(hums)
        self.assertAlmostEqual(hums[0].freq, M.freq(step.value))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('field_manual', 7, pilot, seed=1, steps=3000),
                         [1.0])
        self.assertEqual(drive('field_manual', 1, lambda t: None, seed=1,
                               steps=3600), [-1.0])

    def test_the_agent_hears_the_machine(self):
        from nwenv import catalog
        env = catalog.env_class('field_manual')(seed=2, rung=4, trials=1,
                                                adaptive=False)
        try:
            heard = 0
            for _k in range(400):
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
