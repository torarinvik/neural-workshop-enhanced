# -*- coding: utf-8 -*-
"""What the tests of the kept-cue families share: a model of the four
places kept here, apart from the code under test, and a driver that
plays a trial through the agent boundary with a press policy for the
wait.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

FRAME = 0.5
JOB = 2


def port_for(look, place):
    """Look 0 numbers the places in reading order, look 1 the other way
    round."""
    return place if look == 0 else 3 - place


def jobs_due(puzzle):
    """Each job's window in seconds and the port it asks for."""
    look = puzzle.data['look']
    return [(first * FRAME, (first + JOB) * FRAME, port_for(look, place))
            for first, place in puzzle.data['jobs']]


def job_now(task):
    """The port the job showing asks for, once; None otherwise."""
    run = task.run
    for j, (start, end, port) in enumerate(jobs_due(task.puzzle)):
        if start - 1e-6 <= run.t < end - 1e-6 and j not in run.done:
            return port
    return None


def drive(name, pick, rung=1, wait=None, seed=1, frame_hz=60.0,
          steps=6000, trials=1, look=None):
    """Scalars paid: *wait(task)* presses (or not) before the question
    is put, *pick(task)* once it is. Plays *trials* trials."""
    from nwenv import catalog
    from uisupport import close_overlays, reset_window
    env = catalog.env_class(name)(seed=seed, rung=rung, trials=trials,
                                  adaptive=False, frame_hz=frame_hz)
    scalars = []
    try:
        for _step in range(steps):
            task = env.task
            port = None
            if task.phase == 'playing' and task.run is not None:
                if task.run.open:
                    port = pick(task)
                elif wait is not None:
                    port = wait(task)
            _obs, events, done = env.step(port)
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done or len(scalars) >= trials:
                break
    finally:
        env.close()
        close_overlays()
        reset_window()
    return scalars
