#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Right is right: in every task drawn through the flat-shape lens, the
control called right moves, or turns, towards the screen's right.

These tasks lay their world out with x to the right of a viewer looking
along z; the lens by default takes the other hand, which once drew them
mirrored, so that steering right went left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import unittest

from uisupport import close_overlays, needs_ui, reset_window


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class Watch:
    """Keeps the last lens a screen made."""

    def __enter__(self):
        from neural_workshop.ui import lens
        self.cls = lens.Lens
        self.made = made = []
        self.old = old = lens.Lens.__init__

        def init(this, *args, **kw):
            old(this, *args, **kw)
            made.append(this)
        lens.Lens.__init__ = init
        return self

    def __exit__(self, *exc):
        self.cls.__init__ = self.old

    @property
    def last(self):
        return self.made[-1]


def session(task_id, rung=1, seed=1):
    from nwenv import catalog
    return catalog.env_class(task_id)(seed=seed, rung=rung, trials=1,
                                      adaptive=False)


@needs_ui
class RightIsRight(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def _turns_right(self, task_id, port, forward, warm=()):
        """Holding *port* swings the view's forward towards what was
        the screen's right."""
        with Watch() as watch:
            env = session(task_id)
            try:
                env.step(None)
                for p in warm:
                    env.step(p)
                env.step(None)
                before = watch.last
                f0 = forward(env.task.run)
                for _k in range(20):
                    env.step(port)
                f1 = forward(env.task.run)
            finally:
                env.close()
        self.assertGreater(_dot(f1, before.r), 0.01, task_id)
        self.assertLess(abs(_dot(f0, before.r)), 0.2, task_id)

    def test_rover(self):
        from neural_workshop import rover as M
        self._turns_right(
            'rover', M.RIGHT,
            lambda run: (math.sin(run.state.heading), 0.0,
                         math.cos(run.state.heading)),
            warm=[M.DRIVE] * 60)

    def test_cricket_hunt(self):
        from neural_workshop import crickethunt as M
        self._turns_right('cricket_hunt', M.RIGHT,
                          lambda run: M._look(run.yaw, 0.0))

    def test_steadicam(self):
        from neural_workshop import steadicam as M
        self._turns_right(
            'steadicam', M.PAN_R,
            lambda run: (math.sin(run.yaw), 0.0, math.cos(run.yaw)))

    def _moves_right(self, task_id, port, where):
        with Watch() as watch:
            env = session(task_id)
            try:
                env.step(None)
                x0 = where(env.task.run)
                for _k in range(15):
                    env.step(port)
                x1 = where(env.task.run)
                lens = watch.last
            finally:
                env.close()
        self.assertGreater(x1, x0 + 1e-3, task_id)
        self.assertGreater(_dot((1.0, 0.0, 0.0), lens.r), 0.5, task_id)

    def test_claw_machine(self):
        from neural_workshop import clawmachine as M
        self._moves_right('claw_machine', M.RIGHT, lambda run: run.x)

    def test_catch(self):
        from neural_workshop import catch as M
        self._moves_right('catch', M.RIGHT, lambda run: run.baskets[0][0])

    def test_docking(self):
        from neural_workshop import docking as M
        for port, what in ((M.RIGHT, 'vel'), (M.YAW_R, 'fwd')):
            with Watch() as watch:
                env = session('docking')
                try:
                    env.step(None)
                    before = watch.last
                    run = env.task.run
                    v0 = tuple(run.vel)
                    for _k in range(15):
                        env.step(port)
                    if what == 'vel':
                        moved = tuple(a - b for a, b in zip(run.vel, v0))
                    else:
                        moved = M.body_to_world((0, 0, 1), *run.att)
                finally:
                    env.close()
            self.assertGreater(_dot(moved, before.r), 1e-4, what)


class TheLens(unittest.TestCase):

    def test_x_right_turns_the_picture_round_and_nothing_else(self):
        from neural_workshop.ui.lens import Lens
        plain = Lens((0, 1, 0), (0, 1, 5), 100.0, 0.0, 0.0)
        turned = Lens((0, 1, 0), (0, 1, 5), 100.0, 0.0, 0.0, x_right=True)
        p = (1.0, 2.0, 4.0)
        a, b = plain.see(p), turned.see(p)
        self.assertLess(a[0], 0)
        self.assertAlmostEqual(b[0], -a[0])
        self.assertAlmostEqual(b[1], a[1])
        self.assertAlmostEqual(b[2], a[2])
        # A point on the screen still goes back to where it came from.
        back = turned.on_floor(b[0], b[1], y=2.0)
        self.assertAlmostEqual(back[0], 1.0)
        self.assertAlmostEqual(back[1], 4.0)


if __name__ == '__main__':
    unittest.main()
