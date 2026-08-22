#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Where a frame's milliseconds actually go. Not a test — run it directly.

    PYTHONPATH=.. ../.venv/bin/python bench_render.py

Written because "is the rendering efficient" is not a question worth
answering from the shape of the code. It breaks a step into the four
things that cost anything — building the shapes, drawing them, reading
the framebuffer back, and hashing it — so that any argument about
where to spend effort, in C or otherwise, starts from numbers.

Two warnings about reading the output.

``on_draw`` is the least trustworthy row here, and it is worth saying
why rather than quietly believing it. OpenGL is asynchronous, so what
this times is how long the call takes to *queue* the work — about
five hundredths of a millisecond for seven hundred shapes, and it
stays there even with a ``glReadPixels`` between every run, which is
the strongest check available from this side of the driver. It is not
a measurement of the GPU's time and should not be read as one. What it
does establish is that submission is not the constraint: whatever the
card spends, the Python side of drawing is a rounding error next to
building the shapes, reading them back, and hashing them.

And the hash row is worth looking at before anyone "optimises" it.
SHA-256 is not slow here because it is SHA-256; it is the fastest of
the four, because the platform has instructions for it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import hashlib
import time

import bwaccel
from uisupport import MazeTask, YouAreHere, close_overlays, state

from neural_workshop import youarehere as Y
from neural_workshop.geometry import framebuffer_size
from nwenv.frames import capture_rgba, digest_rgba, flip_rgba

RUNG = 12


def clocked(what, rounds=30):
    """Mean milliseconds over *rounds* goes."""
    clock = time.perf_counter
    start = clock()
    for _round in range(rounds):
        what()
    return (clock() - start) / rounds * 1000.0


def line(what, ms, note=''):
    print('   %-28s %7.2f ms  %s' % (what, ms, note))


def main() -> None:
    print('bwaccel backend: %s' % bwaccel.backend())
    close_overlays()
    task = YouAreHere()
    task.total_trials = 1
    task.adaptive = False
    task.start_rung = task.rung = RUNG
    task.rng.seed(404)

    start = time.perf_counter()
    task.start_run()
    dealt = (time.perf_counter() - start) * 1000.0
    task.on_draw()
    wide, tall = framebuffer_size(state.window)
    _w, _h, rgba = capture_rgba(state.window)

    print()
    print('3D Maze, rung %d — %dx%d maze, %d shapes, %dx%d frame'
          % (RUNG, task.maze.width, task.maze.height,
             len(task.drawn) + len(task.map_drawn) + len(task.strips),
             wide, tall))
    line('deal a maze (once a maze)', dealt, 'generate + par')
    line('par alone', clocked(lambda: Y.par(task.maze), rounds=3))
    line('look() (once an action)', clocked(
        lambda: Y.look(task.maze, task.pose, columns=Y.COLUMNS)))
    line('_redraw (once an action)', clocked(task._redraw))
    line('on_draw (submission only)', clocked(task.on_draw),
         'not the GPU\'s time — see the docstring')

    print()
    print('What an agent pays a step on top of that (%.1f MB frame)'
          % (len(rgba) / 1e6))
    line('capture_rgba', clocked(lambda: capture_rgba(state.window),
                                 rounds=15))
    line('  of which flip_rgba', clocked(
        lambda: flip_rgba(rgba, wide, tall), rounds=15))
    line('digest_rgba', clocked(lambda: digest_rgba(rgba), rounds=15))
    for named in ('sha256', 'sha1', 'blake2b', 'md5'):
        line('  %s' % named, clocked(
            lambda n=named: hashlib.new(n, rgba).hexdigest(), rounds=15))
    line('on_draw after a readback', clocked(task.on_draw),
         'still submission; the driver hides the rest')
    task.close()
    close_overlays()

    flat = MazeTask()
    flat.total_trials = 1
    flat.adaptive = False
    flat.start_rung = flat.rung = RUNG
    flat.start_run()
    flat.on_draw()
    print()
    print('The 2D Maze at the same rung, for scale — %d shapes, rebuilt '
          'every step' % len(flat.drawn))
    line('_redraw (once a step)', clocked(flat._redraw))
    flat.close()


if __name__ == '__main__':
    main()
