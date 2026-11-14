#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forms: the fields, what a form can check, the reference, the screen.

Deals are held to being fixed by their seed and to asking what each rung
says it adds. The form is held to checking shape and not truth, to
sending a page back with the mistakes marked, to lists that complete
and pick on leaving, and to fields that appear only for some answers.
The reference typist is held to filling every form right first time;
the boundary to paying its keys through the forty-six ports and failing
a form sent with a wrong value.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import forms as F


def type_into(form, words):
    for char in words:
        form.press(char)


class TheLadder(unittest.TestCase):

    def test_every_rung_asks_at_least_what_the_last_did(self):
        last = F.grade(1)
        for rung in range(2, 40):
            level = F.grade(rung)
            self.assertTrue(set(last.kinds) <= set(level.kinds))
            self.assertGreaterEqual(level.fields, last.fields)
            self.assertGreaterEqual(level.pages, last.pages)
            self.assertLessEqual(level.factor, last.factor)
            last = level

    def test_each_rung_asks_what_it_adds(self):
        for rung, kind in ((4, 'date'), (5, 'digits'), (6, 'choice'),
                           (8, 'radio'), (8, 'check')):
            kinds = {f.kind for f in F.deal(rung, seed=0).fields}
            self.assertIn(kind, kinds, rung)
        self.assertTrue(any(f.shown_if for f in F.deal(10, seed=0).fields))
        self.assertEqual(F.deal(12, seed=0).level.pages, 2)

    def test_rung_one_is_one_field(self):
        self.assertEqual(len(F.deal(1, seed=0).fields), 1)


class TheForm(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(F.deal(14, seed=3), F.deal(14, seed=3))

    def test_tab_moves_and_typing_goes_in_the_field(self):
        form = F.Form(F.deal(2, seed=0))
        type_into(form, 'ab')
        form.press(F.TAB)
        type_into(form, 'c')
        self.assertEqual(form.values['first'], 'ab')
        self.assertEqual(form.values['last'], 'c')
        self.assertEqual(form.keys, 4)

    def test_a_bad_date_sends_the_page_back_marked(self):
        dealt = F.deal(4, seed=0)
        form = F.Form(dealt)
        for field in dealt.fields:
            if field.kind == 'date':
                type_into(form, '1 march')
            else:
                type_into(form, str(field.answer))
            form.press(F.TAB)
        form.press(F.ENTER)
        self.assertFalse(form.sent)
        self.assertEqual(form.marked, ['born'])
        self.assertEqual(form.bounced, 1)

    def test_a_form_cannot_tell_a_wrong_name(self):
        dealt = F.deal(2, seed=0)
        form = F.Form(dealt)
        type_into(form, 'zed')
        form.press(F.TAB)
        type_into(form, 'zed')
        form.press(F.ENTER)
        self.assertTrue(form.sent)
        self.assertEqual(len(form.wrong), 2)

    def test_a_list_completes_and_picks_on_leaving(self):
        dealt = F.deal(6, seed=0)
        form = F.Form(dealt)
        while form.field.kind != 'choice':
            form.press(F.TAB)
        type_into(form, 'no')
        names = [F.COUNTRIES[i] for i in form.choices(form.field)]
        self.assertEqual(names, ['Norway'])
        form.press(F.TAB)
        self.assertEqual(form.values['country'],
                         F.COUNTRIES.index('Norway'))

    def test_down_moves_along_the_matches(self):
        dealt = F.deal(6, seed=0)
        form = F.Form(dealt)
        while form.field.kind != 'choice':
            form.press(F.TAB)
        type_into(form, 'n')
        form.press(F.DOWN)
        form.press(F.TAB)
        self.assertEqual(F.COUNTRIES[form.values['country']], 'Netherlands')

    def test_a_field_appears_for_its_answer(self):
        dealt = F.deal(10, seed=1)
        form = F.Form(dealt)
        keys = [f.key for f in form.visible()]
        self.assertNotIn('company', keys)
        form.values['work'] = 1
        self.assertIn('company', [f.key for f in form.visible()])

    def test_the_shortest_list_prefix_is_used(self):
        dealt = F.deal(6, seed=0)
        form = F.Form(dealt)
        field = next(f for f in dealt.fields if f.kind == 'choice')
        keys = F.keys_for(form, field)
        name = F.COUNTRIES[field.answer].lower()
        self.assertLessEqual(len(keys), len(name))


class TheReference(unittest.TestCase):

    def test_it_fills_every_form_right_first_time(self):
        for rung in (1, 4, 6, 8, 10, 12, 16, 18, 24):
            for seed in range(6):
                form = F.reference_form(F.deal(rung, seed=seed))
                self.assertTrue(form.sent, (rung, seed))
                self.assertEqual(form.wrong, [], (rung, seed))
                self.assertEqual(form.bounced, 0, (rung, seed))

    def test_par_has_room_below_twenty_and_none_after(self):
        dealt = F.deal(6, seed=1)
        self.assertGreater(F.par(dealt), F.reference_form(dealt).keys)
        self.assertEqual(F.grade(25).factor, 1.0)


def reference_ports(task, _memory):
    from neural_workshop.ui.forms import KEYS
    return KEYS.index(F.reference_keys(task.form))


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, seed=0, policy=reference_ports):
        from nwenv import catalog
        env = catalog.env_class('forms')(seed=seed, rung=rung, trials=1,
                                         adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(4000):
                task = env.task
                port = (policy(task, memory)
                        if task.phase == 'filling' else None)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_s_keys_pass(self):
        self.assertEqual(self.drive(6), [1.0])

    def test_and_across_pages(self):
        self.assertEqual(self.drive(14), [1.0])

    def test_sending_it_empty_with_a_wrong_name_is_a_loss(self):
        from neural_workshop.ui.forms import KEYS

        def careless(task, _memory):
            if task.form.values.get('first') == '':
                return KEYS.index('z')
            return KEYS.index(F.ENTER)

        self.assertEqual(self.drive(1, policy=careless), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.forms import Forms
        close_overlays()
        self.task = Forms()
        self.task.rng = random.Random(7)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_typing_goes_in_and_tab_moves_on(self):
        from pyglet.window import key
        self.task.start_rung = 2
        self.task.start_run()
        self.task.on_text('Ab')
        self.task.on_key_press(key.TAB, 0)
        self.task.on_text('c')
        self.assertEqual(self.task.form.values['first'], 'Ab')
        self.assertEqual(self.task.form.values['last'], 'c')
        self.task.on_draw()

    def test_a_click_on_a_field_moves_there_for_a_key(self):
        from pyglet.window import mouse
        self.task.start_rung = 2
        self.task.start_run()
        x, y, w, h, _action = self.task.hits[1]
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertEqual(self.task.form.focus, 1)
        self.assertEqual(self.task.form.keys, 1)

    def test_the_reference_s_form_is_green_and_climbs(self):
        self.task.start_rung = 8
        self.task.start_run()
        while self.task.phase == 'filling':
            self.task.press(F.reference_keys(self.task.form))
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 9)
        self.task.on_draw()

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            while self.task.phase == 'filling':
                self.task.press(F.ENTER if self.task.form.values[
                    'first'] else 'x')
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 16
        self.task.start_run()
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            floor = above_the_band(from_bottom_edge(58)) - 0.5
            for x, y, w, h, _action in self.task.hits:
                self.assertGreaterEqual(y, floor, size)
            for line in (self.task.facts, self.task.footnote):
                self.assertLessEqual(line.content_width,
                                     state.window.width - 16, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.forms import Forms
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Forms.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_computer_use(self):
        self.assertIn('forms', [t for t, _l in TASKS['computer']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.forms import Forms
        launch_task('forms')
        self.assertIsNotNone(Forms.instance)
        Forms.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.forms_note({'FORMS_RUNG': 25})
        self.assertIn('letter', note)


if __name__ == '__main__':
    unittest.main()
