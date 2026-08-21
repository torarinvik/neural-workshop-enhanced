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

**It sweeps the catalogue rather than a list of its own.** The first
version had a hand-written driver per task, which meant a task nobody
remembered to add here was reported on by not being reported on. Now
every task in :mod:`nwenv.catalog` is opened and played through its own
wrapper, so a task that is wrapped is a task that is swept.

It has already earned itself twice. Sokoban drew its pusher in Okabe-Ito
vermillion, ``(213, 94, 0)`` — red at or above 180 with the other two at or
below 140, which is exactly the reader's pattern for a *negative verdict* —
and the board reaches into the band, so a pusher standing low on it was
1054 pixels of "this trial scored -1" on a level nobody had lost. Then the
Maze at its top rung read a negative run off the *anti-aliased edge* of
Okabe-Ito orange: the orange itself is clear at G=159, but its ramp towards
the background dips G below 140 while R stays above 180. Nothing about
either task looked wrong. The scalar was simply not the one the screen
meant.

The second one is why the rule is not "avoid three colours" — a blend
passes through them on its way to the background, and no palette can help
that. The rule is that the art stops above the band, which is what
:func:`neural_workshop.ui.verdict.above_the_band` is for.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import random
import sys

import bwaccel
from uisupport import close_overlays, state

from nwenv import catalog
from nwenv.frames import capture_rgba

WORST = {}

#: How many steps to play each task for. Long enough that a trial
#: settles on the fast tasks and that a slow one gets well into its
#: first round; the sweep is about what is on screen, not about
#: finishing runs.
STEPS = 700

#: How often to read the band while playing. Every frame would be
#: honest and slow; this is often enough to catch a token that has
#: wandered low without reading the same still frame forty times.
EVERY = 7


def read(task_name, where, obs, allow_verdict=False):
    """The band of *obs* as the shared reader sees it.

    Read off the observation the boundary handed the learner rather
    than off a fresh capture, because those are not always the same
    bytes: the driver draws, captures and then flips, so capturing
    again afterwards reads whatever is in the back buffer. The first
    version of this sweep did that and reported a phantom run on nine
    tasks at once, which is the sort of finding that is obviously
    wrong only because it was on nine.

    *allow_verdict* is for a frame where a trial really has settled and
    a label is meant to be up: one run, of one kind, is right there.
    Anywhere else — and any second run anywhere — is the task's own art
    being read as a score.
    """
    runs = bwaccel.count_feedback_label_runs(obs['rgba'], obs['width'],
                                             obs['height'])
    ok = sum(runs) <= 1 if allow_verdict else runs == (0, 0, 0)
    if not ok:
        WORST.setdefault(task_name, []).append((where, runs))
    return runs


def swept(row, steps=STEPS, seed=0):
    """Play one task through its wrapper, watching the band.

    Read through the wrapper rather than by driving the task by hand,
    because the wrapper is what a run will actually use: if a phase is
    reachable by a learner it is reachable here, and if it is not then
    the band there does not matter.
    """
    close_overlays()
    env = catalog.env_class(row.task_id)(seed=seed)
    rng = random.Random(seed)
    obs = env.observe()
    try:
        read(row.label, 'opening', obs)
        for step in range(steps):
            obs, _events, done = env.step(rng.randrange(env.n_actions))
            if step % EVERY == 0:
                # A verdict standing is the one run the reader is meant
                # to find, so it is allowed on every frame: which of
                # them a task settles on is its own business.
                read(row.label, 'playing', obs, allow_verdict=True)
            if done:
                break
        read(row.label, 'ending', obs, allow_verdict=True)
    finally:
        env.close()
    close_overlays()


def main(only=()):
    print('bwaccel backend:', bwaccel.backend())
    close_overlays()
    from neural_workshop.ui.maze import MazeTask
    task = MazeTask()
    _wide, tall, _rgba = capture_rgba(state.window)
    low, high = bwaccel.default_band(tall)
    task.close()
    close_overlays()
    print('the band the reader looks at: rows %d-%d of %d\n'
          % (low, high, tall))

    for row in catalog.overlays():
        if only and row.task_id not in only:
            continue
        swept(row)
        print('%-20s %s' % (row.label,
                            'paints in the band' if row.label in WORST
                            else 'clean'))

    print()
    if WORST:
        for task_name, spots in WORST.items():
            print('%s paints in the band:' % task_name)
            for where, runs in spots[:6]:
                print('   %-24s %s' % (where, runs))
            if len(spots) > 6:
                print('   ... and %d more' % (len(spots) - 6))
        return 1
    print('nothing painted in the band anywhere, on any task: every '
          'wrapped task can use the shared deriver as it stands')
    return 0


if __name__ == '__main__':
    sys.exit(main(tuple(sys.argv[1:])))
