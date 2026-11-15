#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tuner: the sounds, the dial, the locking, the mix, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import soundbank
from neural_workshop import tuner as M

BANKS = ('tune', 'esc50') if soundbank.ready() else ('tune',)


def go_to(run, k, then=()):
    run.dial = run.where(k)
    for port in then:
        M.act(run, port)


class TheSounds(unittest.TestCase):

    def test_only_the_target_plays_the_sound(self):
        for bank in BANKS:
            for rung in (1, 7, 10, 16, 24):
                for s in range(5):
                    radio = M.deal(rung, seed=s, bank=bank)
                    target = radio.stations[radio.target].sound
                    self.assertTrue(M.same(radio.heard, target))
                    for k, st in enumerate(radio.stations):
                        if k != radio.target:
                            self.assertFalse(M.same(st.sound, target),
                                             (bank, rung, s))

    def test_kinds_spread_then_gather(self):
        for bank in BANKS:
            radio = M.deal(2, seed=4, bank=bank)
            groups = [s.sound.group for s in radio.stations]
            self.assertEqual(len(set(groups)), len(groups))
            radio = M.deal(8, seed=4, bank=bank)
            self.assertEqual(len({s.sound.group for s in radio.stations}), 1)
            self.assertEqual(len({s.sound.label for s in radio.stations}),
                             len(radio.stations))

    def test_decoys_from_rung_10_16_and_24(self):
        for bank in BANKS:
            radio = M.deal(11, seed=2, bank=bank)
            target = radio.stations[radio.target].sound
            self.assertNotEqual(radio.heard.speed, 1.0)
            self.assertTrue(any(s.sound.backward and
                                s.sound.ref == target.ref
                                for s in radio.stations))
            for rung, twins in ((17, 1), (25, 2)):
                radio = M.deal(rung, seed=2, bank=bank)
                target = radio.stations[radio.target].sound
                kin = [s.sound for k, s in enumerate(radio.stations)
                       if k != radio.target and not s.sound.backward
                       and s.sound.label == target.label]
                self.assertEqual(len(kin), twins, (bank, rung))

    def test_sounds_are_open_and_sized(self):
        for bank in BANKS:
            radio = M.deal(12, seed=1, bank=bank)
            for sound in [radio.heard] + [s.sound for s in radio.stations]:
                w = M.wave(sound)
                self.assertAlmostEqual(len(w) / M.RATE, M.length(sound),
                                       delta=0.02)
                self.assertGreater(max(abs(v) for v in w), 0.05)


class TheDial(unittest.TestCase):

    def test_locking_on_the_target_and_holding_passes(self):
        radio = M.deal(4, seed=3)
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)
        go_to(run, radio.target, (M.LOCK,))
        self.assertIsNotNone(run.lock_since)
        while run.result is None:
            run.step(1 / 60.0)
        self.assertTrue(run.result[0])

    def test_locking_on_another_station_fails(self):
        radio = M.deal(4, seed=3)
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)
        go_to(run, (radio.target + 1) % len(radio.stations), (M.LOCK,))
        self.assertFalse(run.result[0])

    def test_locking_on_hiss_does_nothing_and_leaving_loses_the_lock(self):
        radio = M.deal(14, seed=3)
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)
        gaps = sorted(run.where(k) for k in range(len(radio.stations)))
        run.dial = (gaps[0] + gaps[1]) / 2
        M.act(run, M.LOCK)
        self.assertIsNone(run.result)
        self.assertIsNone(run.lock_since)
        go_to(run, radio.target, (M.LOCK,))
        run.dial += radio.level.width * 3
        run.step(1 / 60.0)
        self.assertIsNone(run.lock_since)
        self.assertIsNone(run.result)

    def test_the_radio_answers_the_dial(self):
        import array
        radio = M.deal(4, seed=5, bank='tune')
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)

        def loudness(t0, t1):
            pcm = array.array('h')
            pcm.frombytes(M.mix(run, t0, t1))
            return (sum(v * v for v in pcm) / max(1, len(pcm))) ** 0.5

        gaps = sorted(run.where(k) for k in range(len(radio.stations)))
        run.dial = (gaps[0] + gaps[1]) / 2
        a = run.t
        for _k in range(120):
            run.step(1 / 60.0)
        static = loudness(a, run.t)
        self.assertTrue(all(g[-1] > 0.3 for g in run.gains[-100:]))
        run.dial = run.where(radio.target)
        a = run.t
        for _k in range(120):
            run.step(1 / 60.0)
        self.assertGreater(run.gains[-1][radio.target], 0.9)
        self.assertLess(run.gains[-1][-1], 0.1)
        self.assertGreater(loudness(a, run.t), 0.0)
        self.assertGreater(static, 0.0)

    def test_mixing_in_pieces_is_mixing_at_once(self):
        radio = M.deal(14, seed=6, bank='tune')
        run = M.Run(radio)
        while run.t < radio.listen + 2.0:
            run.step(1 / 60.0, M.UP if run.t > radio.listen else None)
        whole = M.mix(run, 0.0, run.t)
        cut = radio.listen + 0.5
        pieces = M.mix(run, 0.0, cut) + M.mix(run, cut, run.t)
        self.assertLessEqual(abs(len(whole) - len(pieces)), 4)
        n = min(len(whole), len(pieces)) // 2 * 2
        self.assertGreater(sum(a == b for a, b in zip(whole[:n],
                                                      pieces[:n])) / n, 0.95)

    def test_the_reference_passes_and_idling_fails(self):
        for rung in (1, 7, 10, 13, 16, 22):
            for s in range(3):
                radio = M.deal(rung, seed=s, bank=BANKS[s % len(BANKS)])
                self.assertTrue(M.play(radio)[0], (rung, s))
                self.assertFalse(M.play(radio, lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('tuner', 1, pilot, seed=1, steps=1200),
                         [1.0])
        self.assertEqual(drive('tuner', 1, lambda t: None, seed=1,
                               steps=4000), [-1.0])

    def test_the_agent_hears_the_radio(self):
        from nwenv import catalog
        env = catalog.env_class('tuner')(seed=2, rung=4, trials=1,
                                         adaptive=False)
        try:
            heard = 0
            for _k in range(240):
                env.step(None)
                chunk = env._public_audio
                if chunk:
                    self.assertEqual(chunk['audio_rate'], M.RATE)
                    heard += len(chunk['audio_pcm'])
            self.assertGreater(heard, 4 * M.RATE)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
