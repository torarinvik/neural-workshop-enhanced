#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Verbal Reasoning screen and its pixel-only boundary."""
from __future__ import annotations

import unittest

from uisupport import (UI_IMPORT_ERROR, close_overlays, key, needs_ui,
                       reset_window)

if UI_IMPORT_ERROR is None:
    from neural_workshop.verbal import Question
    from neural_workshop.ui import verbal as screen
    from neural_workshop.ui.verbal import VerbalReasoning
    from nwenv.verbal import VerbalReasoningEnv


class FakeBank:
    def __init__(self, *args, **kwargs):
        self.opened = False

    def draw(self, rng):
        self.opened = True
        return Question(
            'Every cedar is a tree. Which conclusion follows?',
            ('No cedar is a tree.', 'Every cedar is a tree.',
             'No tree is a cedar.'),
            1, 'Every cedar is a tree.',
            'The answer repeats the stated universal premise.',
            'deductive_logic')


@needs_ui
class VerbalScreenTests(unittest.TestCase):

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_opening_the_screen_does_not_open_the_corpus(self):
        task = VerbalReasoning()
        self.assertFalse(task.bank.opened)
        self.assertEqual(task.phase, 'ready')

    def test_start_answer_and_explanation(self):
        task = VerbalReasoning()
        task.bank = FakeBank()
        task.start_run()
        self.assertTrue(task.bank.opened)
        self.assertEqual(task.phase, 'asking')
        task.choose(1)
        self.assertEqual(task.phase, 'judged')
        self.assertEqual(task.score()['right'], 1)
        self.assertIn('universal premise', task.note.text)

    def test_unused_answer_ports_do_nothing(self):
        task = VerbalReasoning()
        task.bank = FakeBank()
        task.start_run()
        task.choose(4)
        self.assertEqual(task.phase, 'asking')
        self.assertEqual(task.results, [])

    def test_keyboard_walks_and_answers(self):
        task = VerbalReasoning()
        task.bank = FakeBank()
        task.start_run()
        task.on_key_press(key.DOWN, 0)
        task.on_key_press(key.RETURN, 0)
        self.assertEqual(task.phase, 'judged')
        self.assertEqual(task.score()['right'], 1)

    def test_agent_outcome_is_read_from_the_verdict_pixels(self):
        real = screen.QuestionBank
        screen.QuestionBank = FakeBank
        try:
            env = VerbalReasoningEnv(seed=1, trials=1)
            try:
                _observation, events, _done = env.step(1)
                scalars = [event['scalar'] for event in events
                           if event.get('type') == 'outcome']
                self.assertEqual(scalars, [1.0])
            finally:
                env.close()
        finally:
            screen.QuestionBank = real


if __name__ == '__main__':
    unittest.main()
