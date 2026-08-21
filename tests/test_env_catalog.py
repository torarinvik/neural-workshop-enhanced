#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The catalogue, and the one thing it has to keep true.

Every task in the workshop is reachable by the learning agent. That is
a claim about a list, and a list is exactly the sort of thing that goes
quietly out of date: someone adds a task to the hub, nobody adds it to
the boundary, and the sweep that checks the tasks goes on saying
"clean" about the twenty-three it knows.

So the hub is the authority and this fails the build when the
catalogue does not cover it.

The rest is the shape each wrapper has to have. None of these open a
window: they read class attributes, which is deliberate — the shape
should be checkable without paying for a run, so that it is checked on
every run of the suite rather than on the slow tests.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import UI_IMPORT_ERROR

if UI_IMPORT_ERROR is None:
    from neural_workshop.ui import taskhub
    from nwenv import catalog
    from nwenv.taskenv import TaskEnv

needs_ui = unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))


@needs_ui
class TheCatalogueCoversTheHub(unittest.TestCase):
    """A task a person can play is a task the agent can play."""

    def hub_tasks(self):
        return [task_id
                for category, _label in taskhub.CATEGORIES
                for task_id, _name in taskhub.tasks_for(category)]

    def test_every_task_in_the_hub_is_wrapped(self):
        missing = sorted(set(self.hub_tasks()) - set(catalog.task_ids()))
        self.assertEqual(missing, [], 'these tasks have no agent boundary: '
                                      '%s. Add a row to nwenv/catalog.py '
                                      'and a wrapper beside it.' % missing)

    def test_the_catalogue_invents_no_tasks(self):
        stray = sorted(set(catalog.task_ids()) - set(self.hub_tasks()))
        self.assertEqual(stray, [])

    def test_the_catalogue_is_in_the_hub_order(self):
        """So the two read the same way when they are read side by side."""
        self.assertEqual(catalog.task_ids(), self.hub_tasks())

    def test_the_labels_agree_with_the_hub(self):
        labels = {task_id: name
                  for category, _label in taskhub.CATEGORIES
                  for task_id, name in taskhub.tasks_for(category)}
        for row in catalog.CATALOG:
            self.assertEqual(row.label, labels[row.task_id], row.task_id)


@needs_ui
class EveryWrapperHasTheRightShape(unittest.TestCase):
    """Checked off the classes, so it costs nothing to check often."""

    def envs(self):
        return [(row.task_id, catalog.env_class(row.task_id))
                for row in catalog.CATALOG]

    def test_they_are_all_environments(self):
        for task_id, env in self.envs():
            self.assertTrue(issubclass(env, TaskEnv)
                            or hasattr(env, 'step'), task_id)

    def test_every_one_offers_at_least_one_port(self):
        """Fixed on the class, or worked out per run — but not zero.

        The four wrappers written before :class:`TaskEnv` existed work
        it out: how many ports the n-back workshop offers depends on
        which modalities the mode is running, and the other three sized
        theirs the same way. They compute ``n_actions`` instead of
        declaring ``ports``, and that is allowed — what is not allowed
        is neither.
        """
        for task_id, env in self.envs():
            self.assertTrue(int(getattr(env, 'ports', 0)) > 0
                            or 'n_actions' in vars(env),
                            '%s declares no ports and computes none'
                            % task_id)

    def test_a_declared_action_table_is_as_wide_as_the_ports(self):
        """A short table would leave ports that silently do nothing.

        Which is fine when it is the *task* refusing them — a rung with
        four choices out of eight — and not fine when it is the
        wrapper, because then the port does nothing on every rung and
        the learner is searching a space part of which is furniture.
        """
        for task_id, env in self.envs():
            table = getattr(env, 'action_table', ())
            if table:
                self.assertEqual(len(table), env.ports, task_id)

    def test_every_declared_wrapper_says_where_its_task_lives(self):
        for task_id, env in self.envs():
            if getattr(env, 'action', '') or getattr(env, 'knobs', {}):
                self.assertTrue(getattr(env, 'task_class', ('', ''))[1],
                                task_id)

    def test_a_knob_names_an_attribute_the_task_actually_has(self):
        """The failure this catches is silent, so it is worth a test.

        Setting an attribute the task does not read is not an error in
        Python. A run started with a knob the task spells differently
        would open at the default difficulty and say nothing about it,
        and every number that came out of it would be about the wrong
        ladder.
        """
        for row in catalog.CATALOG:
            env = catalog.env_class(row.task_id)
            knobs = getattr(env, 'knobs', {})
            if not knobs or not row.ui_class:
                continue
            task = catalog.ui_class(row.task_id)
            attrs = set(dir(task))
            source = ''
            try:
                import inspect
                source = inspect.getsource(task)
            except Exception:
                pass
            for name, attr in sorted(knobs.items()):
                self.assertTrue(attr in attrs or ('self.%s' % attr) in source,
                                '%s: knob %r sets %r, which %s never holds'
                                % (row.task_id, name, attr, task.__name__))

    def test_required_settings_name_attributes_too(self):
        for row in catalog.CATALOG:
            env = catalog.env_class(row.task_id)
            if not getattr(env, 'requires', {}) or not row.ui_class:
                continue
            task = catalog.ui_class(row.task_id)
            import inspect
            source = inspect.getsource(task)
            for attr in sorted(env.requires):
                self.assertIn('self.%s' % attr, source,
                              '%s requires %r' % (row.task_id, attr))


if __name__ == '__main__':
    unittest.main()
