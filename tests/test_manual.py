#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Manual: the panels, the procedures, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import manual as M


def kinds_of(dealt):
    """Which kinds of step a procedure holds, read off its words."""
    found = set()
    for step in dealt.steps:
        w = step.words
        if w.startswith('If the display'):
            found.add('skip')
        elif 'until it is' in w:
            found.add('until')
        elif w.startswith('If '):
            found.add('if')
        elif 'as many times as the display' in w:
            found.add('count')
        elif 'at the start' in w:
            found.add('recall')
        elif 'the same as' in w or 'where knob' in w:
            found.add('copy')
        else:
            found.add('plain')
    return found


class TheLadder(unittest.TestCase):

    def test_every_rung_asks_at_least_what_the_last_did(self):
        last = M.grade(1)
        for rung in range(2, 40):
            level = M.grade(rung)
            for field in ('switches', 'knobs', 'buttons', 'lamps', 'steps'):
                self.assertGreaterEqual(getattr(level, field),
                                        getattr(last, field), field)
            self.assertTrue(set(last.kinds) <= set(level.kinds))
            last = level

    def test_the_kinds_come_in_on_their_rungs(self):
        self.assertEqual(M.grade(1).kinds, ('set', 'flip'))
        self.assertIn('if', M.grade(5).kinds)
        self.assertIn('count', M.grade(9).kinds)
        self.assertIn('until', M.grade(13).kinds)
        self.assertIn('skip', M.grade(20).kinds)
        self.assertEqual((M.grade(16).shuffled, M.grade(17).shuffled),
                         (False, True))

    def test_a_rung_asks_for_what_it_adds(self):
        for rung, kind in ((5, 'if'), (13, 'until'), (20, 'skip')):
            for seed in range(15):
                dealt = M.deal(rung, seed=seed)
                found = kinds_of(dealt)
                newest = {'if', 'count', 'copy', 'until', 'recall',
                          'skip'} & set(M.grade(rung).kinds) - \
                    set(M.grade(rung - 4).kinds)
                self.assertTrue(found & newest, (rung, seed, found))


class ThePanels(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        one, two = M.deal(14, seed=8), M.deal(14, seed=8)
        self.assertEqual([s.words for s in one.steps],
                         [s.words for s in two.steps])
        self.assertEqual(M.follow(one).state(), M.follow(two).state())

    def test_lamps_and_display_answer_the_controls(self):
        dealt = M.deal(10, seed=1)
        panel = dealt.panel()
        before = [panel.lamp(i) for i in range(dealt.level.lamps)] + \
            [panel.display()]
        changed = False
        for i in range(dealt.level.switches):
            panel.toggle(i)
            after = [panel.lamp(j) for j in range(dealt.level.lamps)] + \
                [panel.display()]
            changed = changed or after != before
        self.assertTrue(changed)

    def test_knobs_stop_at_their_ends(self):
        panel = M.deal(6, seed=2).panel()
        panel.knobs[0] = M.TOP
        self.assertFalse(panel.turn(0, 1))
        panel.knobs[0] = 0
        self.assertFalse(panel.turn(0, -1))
        self.assertTrue(panel.turn(0, 1))

    def test_doing_nothing_is_never_right(self):
        for rung in range(1, 31):
            for seed in range(20):
                dealt = M.deal(rung, seed=seed)
                self.assertNotEqual(M.follow(dealt).state(),
                                    dealt.panel().state(), (rung, seed))

    def test_a_loop_stops_where_it_says(self):
        for seed in range(40):
            dealt = M.deal(15, seed=seed)
            for step in dealt.steps:
                if 'until it is' in step.words:
                    panel, start = dealt.panel(), dealt.panel()
                    step.run(panel, start)
                    lamp = int(step.words.split('lamp L')[1][0]) - 1
                    colour = step.words.split(' is not ')[1].split(',')[0]
                    self.assertEqual(panel.lamp(lamp), colour)

    def test_a_skip_skips(self):
        for seed in range(60):
            dealt = M.deal(22, seed=seed)
            words = [s.words for s in dealt.steps]
            if not words[0].startswith('If the display'):
                continue
            panel = dealt.panel()
            skipped = dealt.steps[0].run(panel, dealt.panel())
            even = 'even' in words[0]
            self.assertEqual(skipped, (panel.display() % 2 == 0) == even)
            return
        self.skipTest('no procedure opened with a skip')

    def test_shuffled_rows_still_hold_every_control(self):
        dealt = M.deal(18, seed=4)
        for order, count in zip(dealt.layout, (dealt.level.switches,
                                               dealt.level.knobs,
                                               dealt.level.buttons)):
            self.assertEqual(sorted(order), list(range(count)))
        self.assertTrue(any(list(order) != sorted(order)
                            for d in (M.deal(18, seed=s) for s in range(5))
                            for order in d.layout))


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, extra=(), seed=0, cut=None):
        from nwenv import catalog
        from neural_workshop.ui.manual import reference_ports
        env = catalog.env_class('manual')(seed=seed, rung=rung, trials=1,
                                          adaptive=False)
        scalars, plan = [], None
        try:
            for _step in range(500):
                task = env.task
                port = None
                if task.phase == 'playing':
                    if plan is None:
                        plan = reference_ports(task)
                        plan = plan[:-1] + list(extra) + plan[-1:]
                        if cut is not None:
                            plan = plan[cut:]
                    port = plan.pop(0) if plan else None
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_following_the_procedure_passes(self):
        self.assertEqual(self.drive(6), [1.0])

    def test_and_with_the_labels_shuffled(self):
        self.assertEqual(self.drive(18), [1.0])

    def test_and_at_the_top(self):
        self.assertEqual(self.drive(26), [1.0])

    def test_finishing_at_once_fails(self):
        from nwenv.manual import FINISH
        self.assertEqual(self.drive(3, cut=-1), [-1.0])
        self.assertEqual(FINISH, 20)

    def test_one_press_too_many_fails(self):
        from nwenv.manual import BUTTON
        self.assertEqual(self.drive(6, extra=[BUTTON]), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.manual import Manual
        close_overlays()
        self.task = Manual()
        self.task.rng = random.Random(5)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def press_hit(self, index):
        from pyglet.window import mouse
        x, y, w, h, _action = self.task.hits[index]
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)

    def test_clicks_work_every_kind_of_control(self):
        self.task.start_rung = 9
        self.task.start_run()
        panel = self.task.panel
        switches, knobs, buttons = self.task.deal.layout
        before = panel.state()
        self.press_hit(0)                         # first switch slot
        self.assertNotEqual(panel.switches[switches[0]],
                            before[0][switches[0]])
        n = len(switches)
        start = panel.knobs[knobs[0]]
        self.press_hit(n + (1 if start < M.TOP else 0))     # + or -
        self.assertNotEqual(panel.knobs[knobs[0]], start)
        self.press_hit(n + 2 * len(knobs))       # first button slot
        self.assertEqual(panel.presses[buttons[0]], 1)
        self.task.on_draw()

    def test_the_reference_is_green_and_climbs(self):
        from neural_workshop.ui.manual import reference_ports
        self.task.start_rung = 13
        self.task.start_run()
        for port in reference_ports(self.task):
            self.task.steer(port)
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 14)
        self.task.on_draw()

    def test_a_wrong_finish_names_what_is_wrong(self):
        from pyglet.window import key
        self.task.start_run()
        self.task.on_key_press(key.RETURN, 0)
        self.assertFalse(self.task.verdict_shown[0])
        self.assertTrue(self.task.mistakes())
        self.assertIn(self.task.mistakes()[0], self.task.message)
        self.task.on_draw()

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            self.task.finish()
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['trials'], 2)

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 26
        self.task.start_run()
        for size in ((1824, 1368), (1280, 720), (2560, 1080), (1024, 768)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            floor = above_the_band(from_bottom_edge(58)) - 0.5
            for x, y, w, h, _action in self.task.hits:
                self.assertGreaterEqual(y, floor, size)
                self.assertLessEqual(x + w, state.window.width, size)
            for line in (self.task.facts, self.task.footnote):
                self.assertLessEqual(line.content_width,
                                     state.window.width - 16, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.manual import Manual
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Manual.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_computer_use(self):
        self.assertIn('manual', [t for t, _l in TASKS['computer']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.manual import Manual
        launch_task('manual')
        self.assertIsNotNone(Manual.instance)
        Manual.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.manual_note({'MANUAL_RUNG': 20})
        self.assertIn('shuffled', note)
        self.assertIn('skip', note)


if __name__ == '__main__':
    unittest.main()
