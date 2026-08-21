"""Does a task already paint the band the boundary reads?

ADDING_A_TASK.md's constraint: nothing in the bottom quarter of the frame
may be a saturated red, green or blue, or the shared reader in
:mod:`bwaccel.pixels` counts it as a verdict and the task's outcome becomes
whatever its furniture happens to look like.

This asks the reader itself rather than reasoning about the palette, on
every rung and in every phase a task passes through, because the band is a
property of what is on screen and a task's screen changes with its rung.

Run it before wrapping a task:

    PYTHONPATH=.. ../.venv/bin/python check_band.py

Anything but ``(0, 0, 0)`` before a verdict is painted is a task that cannot
use the shared deriver until its art moves out of the band.
"""
import random

import bwaccel
from uisupport import close_overlays, state

from neural_workshop import youarehere as Y
from nwenv.frames import capture_rgba

WORST = {}


def read(task_name, where):
    wide, tall, rgba = capture_rgba(state.window)
    runs = bwaccel.count_feedback_label_runs(rgba, wide, tall)
    if runs != (0, 0, 0):
        WORST.setdefault(task_name, []).append((where, runs))
    return runs


def band_rows():
    wide, tall, _rgba = capture_rgba(state.window)
    return bwaccel.default_band(tall) + (tall,)


def removals(rungs):
    from neural_workshop.ui.removals import Removals
    for rung in rungs:
        close_overlays()
        task = Removals()
        task.total_trials = 1
        task.adaptive = False
        task.start_rung = task.rung = rung
        task.rng.seed(11)
        task.start_run()
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
        read('Removals', 'rung %d scored' % rung)
        task.close()


def crossed(rungs):
    from neural_workshop.ui.crossedwires import CrossedWires
    for rung in rungs:
        close_overlays()
        task = CrossedWires()
        task.total_trials = 1
        task.adaptive = False
        task.start_rung = task.rung = rung
        task.rng.seed(11)
        task.start_run()
        task.on_draw()
        read('Crossed Wires', 'rung %d playing' % rung)
        rng = random.Random(3)
        while task.phase == 'playing':
            task.press(rng.randrange(task.grade().keys))
        task.on_draw()
        read('Crossed Wires', 'rung %d scored' % rung)
        task.close()


def here(rungs):
    from neural_workshop.ui.youarehere import YouAreHere
    for rung in rungs:
        close_overlays()
        task = YouAreHere()
        task.total_trials = 1
        task.adaptive = False
        task.start_rung = task.rung = rung
        task.rng.seed(404)
        task.start_run()
        task.on_draw()
        before = read('You Are Here', 'rung %d walking' % rung)
        for doing in Y.route(task.maze):
            task.walk(doing)
        task.on_draw()
        wide, tall, rgba = capture_rgba(state.window)
        after = bwaccel.count_feedback_label_runs(rgba, wide, tall)
        if before != (0, 0, 0) or after[0] != 1:
            WORST.setdefault('You Are Here', []).append(
                ('rung %d' % rung, (before, after)))
        task.close()


print('bwaccel backend:', bwaccel.backend())
close_overlays()
here([1])
low, high, tall = band_rows()
print('the band the reader looks at: rows %d-%d of %d\n' % (low, high, tall))

here(range(1, 8))
print('You Are Here   rungs 1-7   walking clean, solved reads +1')
removals(range(1, 13))
print('Removals       rungs 1-12  every phase')
crossed(range(1, 13))
print('Crossed Wires  rungs 1-12  every phase')

print()
if WORST:
    for task_name, spots in WORST.items():
        print('%s paints in the band:' % task_name)
        for where, runs in spots:
            print('   %-22s %s' % (where, runs))
else:
    print('nothing painted in the band anywhere: all three can use the '
          'shared deriver as they stand')
