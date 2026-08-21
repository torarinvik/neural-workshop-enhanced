"""Does a task paint the band the agent boundary reads?

ADDING_A_TASK.md's constraint: nothing in the bottom quarter of the frame
may be a saturated red, green or blue, or the shared reader in
:mod:`bwaccel.pixels` counts it as a verdict and the task's public outcome
becomes whatever its furniture happens to look like.

This asks the reader itself rather than reasoning about a palette, on every
rung and in every phase, because the band is a property of what is on screen
and what is on screen changes with the rung and with where a token has got
to.

Run it before wrapping a task, and again whenever a palette or a layout
moves:

    PYTHONPATH=.. ../.venv/bin/python check_band.py

It has already earned itself once. Sokoban drew its pusher in Okabe-Ito
vermillion, ``(213, 94, 0)`` — red at or above 180 with the other two at or
below 140, which is exactly the reader's pattern for a *negative verdict* —
and the board reaches into the band, so a pusher standing low on it was
1054 pixels of "this trial scored -1" on a level nobody had lost. Nothing
about the task looked wrong. The scalar was simply not the one the screen
meant.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import random

import bwaccel
from uisupport import close_overlays, state

from neural_workshop import youarehere as Y
from nwenv.frames import capture_rgba

WORST = {}
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def read(task_name, where, allow_verdict=False):
    """The band as the shared reader sees it.

    *allow_verdict* is for a frame where a trial really has settled and
    a label is meant to be up: one run, of one kind, is right there.
    Anywhere else — and any second run anywhere — is the task's own art
    being read as a score.
    """
    wide, tall, rgba = capture_rgba(state.window)
    runs = bwaccel.count_feedback_label_runs(rgba, wide, tall)
    ok = sum(runs) <= 1 if allow_verdict else runs == (0, 0, 0)
    if not ok:
        WORST.setdefault(task_name, []).append((where, runs))
    return runs


def opened(make, rung, seed=4):
    close_overlays()
    task = make()
    task.total_trials = 1
    task.adaptive = False
    task.start_rung = task.rung = rung
    task.rng.seed(seed)
    task.start_run()
    return task


def stepped(name, make, rungs, playing, act, cap=600):
    """Drive a turn-based task right through a trial, watching the band."""
    for rung in rungs:
        task = opened(make, rung)
        task.on_draw()
        read(name, 'rung %d opening' % rung)
        rng = random.Random(0)
        for turn in range(cap):
            if getattr(task, 'phase', None) != playing:
                break
            act(task, rng)
            if turn % 25 == 0:
                task.on_draw()
                read(name, 'rung %d playing' % rung)
        task.on_draw()
        read(name, 'rung %d settled' % rung, allow_verdict=True)
        task.close()


def removals(rungs):
    from neural_workshop.ui.removals import Removals
    for rung in rungs:
        task = opened(Removals, rung, seed=11)
        task.on_draw()
        read('Removals', 'rung %d moving' % rung)
        while task.phase == 'moving':
            task.until = -1e9
            task.update(0.0)
        task.on_draw()
        read('Removals', 'rung %d asking' % rung)
        for spot in range(len(task.round.asked)):
            task.answer(task.round.answers[spot])
        task.on_draw()
        read('Removals', 'rung %d scored' % rung, allow_verdict=True)
        task.close()


def in_the_dark(rungs):
    from neural_workshop.ui.inthedark import InTheDark
    for rung in rungs:
        task = opened(InTheDark, rung, seed=11)
        task.on_draw()
        read('In the Dark', 'rung %d walking' % rung)
        while task.phase == 'walking':
            task.until = -1e9
            task.update(0.0)
        task.on_draw()
        read('In the Dark', 'rung %d asking' % rung)
        for spot in range(len(task.round.asked)):
            task.answer(task.round.answers[spot])
        task.on_draw()
        read('In the Dark', 'rung %d scored' % rung, allow_verdict=True)
        task.close()


def crossed(rungs):
    from neural_workshop.ui.crossedwires import CrossedWires
    for rung in rungs:
        task = opened(CrossedWires, rung, seed=11)
        task.on_draw()
        read('Crossed Wires', 'rung %d playing' % rung)
        rng = random.Random(3)
        while task.phase == 'playing':
            task.press(rng.randrange(task.grade().keys))
        task.on_draw()
        read('Crossed Wires', 'rung %d scored' % rung, allow_verdict=True)
        task.close()


def here(rungs):
    from neural_workshop.ui.youarehere import YouAreHere
    for rung in rungs:
        task = opened(YouAreHere, rung, seed=404)
        task.on_draw()
        read('You Are Here', 'rung %d walking' % rung)
        for doing in Y.route(task.maze):
            task.walk(doing)
        task.on_draw()
        read('You Are Here', 'rung %d solved' % rung, allow_verdict=True)
        task.close()


def main():
    from neural_workshop.ui.maze import MazeTask
    from neural_workshop.ui.sokoban import SokobanTask
    print('bwaccel backend:', bwaccel.backend())
    close_overlays()
    task = opened(MazeTask, 1)
    wide, tall, _rgba = capture_rgba(state.window)
    low, high = bwaccel.default_band(tall)
    task.close()
    print('the band the reader looks at: rows %d-%d of %d\n' % (low, high,
                                                                tall))
    walk = (lambda t, rng: t.step(*STEPS[rng.randrange(4)]))
    here(range(1, 8))
    print('You Are Here   rungs 1-7')
    removals(range(1, 13))
    print('Removals       rungs 1-12')
    in_the_dark(range(1, 13))
    print('In the Dark    rungs 1-12')
    crossed(range(1, 13))
    print('Crossed Wires  rungs 1-12')
    stepped('Maze', MazeTask, range(1, 8), 'walking', walk)
    print('Maze           rungs 1-7')
    stepped('Sokoban', SokobanTask, range(1, 8), 'pushing', walk)
    print('Sokoban        rungs 1-7')

    print()
    if WORST:
        for task_name, spots in WORST.items():
            print('%s paints in the band:' % task_name)
            for where, runs in spots[:6]:
                print('   %-24s %s' % (where, runs))
            if len(spots) > 6:
                print('   ... and %d more' % (len(spots) - 6))
    else:
        print('nothing painted in the band anywhere, on any rung: every '
              'wrapped task can use the shared deriver as it stands')


if __name__ == '__main__':
    main()
