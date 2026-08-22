#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What a rung of visual difficulty is worth. Not a test — run it directly.

    PYTHONPATH=.. ../.venv/bin/python bench_glyphs.py

This is where the numbers in :mod:`neural_workshop.glyphs`' docstring
come from, and rerunning it is the way to find out whether they still
hold after a change to the ladder. It prints three things.

**The pool.** How many typefaces are reachable — this machine's, plus
anything :mod:`neural_workshop.fontlib` has fetched — how many of them
actually contain Latin capitals, and how the families were split. The
gap between those first two is the whole reason :func:`covered` exists:
ask a font with no Latin in it for a capital A and the platform hands
back somebody else's A without saying so.

Run it with only the machine's own fonts and the held-out set is ten
particular typefaces rather than a sample of anything. To widen it:

    python -m neural_workshop.fontlib google 300     # about 120 MB

**The column.** A nearest-template letter classifier over held-out
families, rung by rung. It is a weak recogniser and it is meant to be —
it knows only where the ink sits in an eight-by-eight grid — so read
the fall rather than the level, and read the first rung as the ceiling
rather than as a score.

**The ablation.** Each knob switched off in turn at one rung, which is
the only way to find out which of them is doing the work. Two of the
six recover nothing, and the reason is worth reading in the module
docstring before anybody "fixes" them.

The whole thing takes about a minute, almost all of it in the resampling
loop in :func:`neural_workshop.glyphs.stamp`.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import sys
import time

from uisupport import UI_IMPORT_ERROR

from neural_workshop import fontlib, glyphs as G

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

#: Families the templates are built from, and families the questions
#: come from. Both are capped rather than "all of them" because every
#: query is compared against every template: the pool went from 59
#: Latin families to 366 when the mirror was added, and uncapped that
#: would be an hour rather than a minute for no more signal.
TEMPLATE_FAMILIES = 40
ASK_FAMILIES = 16

#: The rung the knobs are switched off at. Middling on purpose: at the
#: top every knob is saturated and at the bottom none of them is doing
#: anything, and neither end tells you which one matters.
ABLATE_AT = 6


def pool(report=print):
    """Latin-capable families here, split by family and registered."""
    from neural_workshop.ui import glyphs as UG
    dirs = fontlib.font_dirs()
    every = G.families(dirs)
    latin = G.families(dirs, must_draw=LETTERS)
    mine = G.families(G.platform_dirs(), must_draw=LETTERS)
    names = [name for name in
             (UG.register(paths[0]) for paths in latin.values()) if name]
    train, val, test = G.split(names, seed=7)
    report('%d families, %d of them draw Latin capitals — %d from this '
           'machine and %d fetched' % (len(every), len(latin), len(mine),
                                       len(latin) - len(mine)))
    report('split %d / %d / %d  (train / validation / held out)'
           % (len(train), len(val), len(test)))
    train, test = train[:TEMPLATE_FAMILIES], test[:ASK_FAMILIES]
    report('using %d for templates and %d to ask with' % (len(train),
                                                          len(test)))
    report('asked in: %s' % ', '.join(sorted(test)))
    return train, test


def templates(train):
    from neural_workshop.ui import glyphs as UG
    return {letter: [G.signature(UG.coverage(family, letter))
                     for family in sorted(train)]
            for letter in LETTERS}


def score(test, shapes, rung, seed, change=None):
    """Share of held-out letters the recogniser still gets right."""
    from neural_workshop.ui import glyphs as UG
    right = asked = 0
    picks = random.Random(seed)
    for letter in LETTERS:
        for family in test:
            rng = random.Random(picks.randrange(10 ** 6))
            dealt = G.deal(rung, rng)
            if change is not None:
                dealt = change(dealt)
            cov = G.stamp(UG.coverage(family, letter), dealt, 64, rng)
            asked += 1
            if G.recognise(G.signature(cov), shapes) == letter:
                right += 1
    return right / float(asked)


OFF = {
    'matrix off': lambda d: d._replace(warp=G.Warp(G.IDENTITY,
                                                   d.warp.ripple)),
    'ripple off': lambda d: d._replace(warp=G.Warp(d.warp.inverse, ())),
    'thicken off': lambda d: d._replace(thickness=0.0),
    'speckle off': lambda d: d._replace(speckle=0.0),
    'occlusion off': lambda d: d._replace(bars=()),
    'contrast off': lambda d: d._replace(contrast=1.0),
    'all off': lambda d: G.Distortion(G.Warp.of(G.IDENTITY), 0.0, 0.0,
                                      (), 1.0),
}


def main():
    if UI_IMPORT_ERROR is not None:
        print('no GL context, so no typefaces to read: %s' % UI_IMPORT_ERROR)
        return 1
    began = time.perf_counter()
    train, test = pool()
    if len(train) < 8 or len(test) < 3:
        print('too few Latin typefaces on this machine to hold any out')
        return 1
    shapes = templates(train)
    asked = len(LETTERS) * len(test)
    print('\ntemplates from %d families; %d deals a rung, so a figure '
          'below is\nworth about %.2f either way\n'
          % (len(train), asked, (0.25 / asked) ** 0.5))

    for rung in range(1, len(G.GRADES) + 1):
        got = score(test, shapes, rung, 1000 + rung)
        print('rung %2d  %-22s %.2f' % (rung, G.grade_of(rung).name, got))

    print('\nknobs, at rung %d — the floor is %.2f\n'
          % (ABLATE_AT, 1.0 / len(LETTERS)))
    base = score(test, shapes, ABLATE_AT, 9000)
    print('  %-16s %.2f' % ('all on', base))
    for name, change in OFF.items():
        got = score(test, shapes, ABLATE_AT, 9000, change)
        print('  %-16s %.2f   (%+.2f)' % (name, got, got - base))

    print('\n%.0f seconds' % (time.perf_counter() - began))
    return 0


if __name__ == '__main__':
    sys.exit(main())
