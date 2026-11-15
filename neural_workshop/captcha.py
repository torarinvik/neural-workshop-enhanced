# -*- coding: utf-8 -*-
"""Captcha: type the characters in the picture.

A strip of characters, and a box to type them into. At the bottom of
the ladder it is four clean capitals in one typeface; up the ladder the
characters lean, wave, crowd and change typeface, colour and size from
one to the next, lines are struck through them, the background fills
with stripes, blobs and a confetti of stray glyphs, and decoy characters
stand among the real ones with a rule to tell them apart -- type only
the blue ones, leave out the small ones, leave out the upside-down ones.

Only characters no font or turn can confuse are used: no 0/O, 1/I/L,
2/Z, 5/S, 8/B, and no 6 or 9, which turn into each other.

The ladder:

* rungs 1-3: four clean capitals, one typeface, barely tilted;
* rungs 4-6: five, letters and digits, three typefaces, colours, tilts;
* rungs 7-9: any typeface, a wavy line, crowded, struck through;
* rungs 10-12: six, and decoys of other colours: type only one colour;
* rungs 13-15: small decoys to leave out; a cluttered background;
* rungs 16-19: seven, upside-down decoys to leave out; more of all;
* from rung 20: eight, any rule or two at once, more clutter, steeper
  tilts every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

ALPHABET = 'ACDEFGHJKMNPQRTUVWXY347'
BACKSPACE = len(ALPHABET)
SUBMIT = BACKSPACE + 1
PORTS = SUBMIT + 1
LONGEST = 12
W, H = 100.0, 36.0
#: Characters that look the same, or another character, turned over.
TURN_ALIKE = set('HNXMW')
COLOURS = (('red', (214, 44, 44)), ('blue', (36, 86, 214)),
           ('green', (24, 140, 60)), ('orange', (232, 128, 16)),
           ('purple', (132, 56, 186)), ('black', (28, 28, 34)))
#: Typeface slots; the screen maps each to a face this machine has.
FACES = 16


class Grade(NamedTuple):
    rung: int
    length: int
    faces: int
    tilt: float                # degrees either way
    colours: bool
    wave: float                # units of the wavy line
    crowd: float               # 1 apart .. 0.6 overlapping
    strikes: int
    noise: int                 # thin lines and arcs behind
    clutter: int               # stray glyphs in the background
    blobs: int
    rules: Tuple[str, ...]     # 'colour', 'small', 'upside'
    both: bool                 # two rules at once
    decoys: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    rules: Tuple[str, ...] = ()
    if 10 <= r < 13:
        rules = ('colour',)
    elif 13 <= r < 16:
        rules = ('small',)
    elif 16 <= r < 20:
        rules = ('upside',)
    elif r >= 20:
        rules = ('colour', 'small', 'upside')
    return Grade(
        rung=r,
        length=4 if r < 4 else 5 if r < 10 else 6 if r < 16 else 7
        if r < 20 else 8,
        faces=1 if r < 4 else 3 if r < 7 else FACES,
        tilt=(6.0 if r < 4 else 20.0 if r < 7 else 30.0 if r < 16
              else 40.0 if r < 20 else min(55.0, 40.0 + 2 * top)),
        colours=r >= 4,
        wave=0.0 if r < 7 else 3.0 if r < 16 else 4.5,
        crowd=1.0 if r < 7 else 0.82 if r < 13 else 0.75 if r < 20
        else max(0.6, 0.72 - 0.01 * top),
        strikes=0 if r < 7 else 1 if r < 13 else 2 if r < 20
        else min(5, 2 + top // 3),
        noise=0 if r < 4 else 3 if r < 7 else 8 if r < 13 else 14 if r < 20
        else min(40, 18 + 2 * top),
        clutter=0 if r < 13 else 30 if r < 16 else 60 if r < 20
        else min(160, 80 + 8 * top),
        blobs=0 if r < 7 else 3 if r < 13 else 6 if r < 20 else 9,
        rules=rules,
        both=r >= 24,
        decoys=0 if r < 10 else 2 if r < 16 else 3 if r < 20
        else min(6, 3 + top // 3))


class Glyph(NamedTuple):
    char: str
    x: float                   # centre
    y: float
    size: float                # height, units
    angle: float               # degrees, clockwise
    face: int
    colour: int                # index into COLOURS
    real: bool                 # part of the answer


class Mark(NamedTuple):
    kind: str                  # 'line', 'arc', 'blob', 'stray', 'strike'
    points: Tuple[float, ...]
    width: float
    colour: Tuple[int, ...]
    char: str = ''
    face: int = 0


class Puzzle(NamedTuple):
    level: Grade
    glyphs: List[Glyph]
    marks: List[Mark]
    answer: str
    rule: str                  # what to type, said in words
    paper: Tuple[Tuple[int, int, int], Tuple[int, int, int]]
    stripes: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    return _build(grade(rung), draw)


def _rule(level: Grade, draw: random.Random) -> Tuple[List[str], int]:
    rules = list(level.rules)
    if not rules:
        return [], 0
    if level.both:
        draw.shuffle(rules)
        return rules[:2], draw.randrange(len(COLOURS))
    return [draw.choice(rules)], draw.randrange(len(COLOURS))


def _build(level: Grade, draw: random.Random) -> Puzzle:
    rules, keep = _rule(level, draw)
    n = level.length
    answer = ''.join(draw.choice(ALPHABET) for _k in range(n))
    faces = draw.sample(range(FACES), level.faces)
    # Who is real and who a decoy, in reading order.
    slots = [True] * n + [False] * level.decoys
    draw.shuffle(slots)
    while slots and not slots[0] and level.decoys:   # start on a real one
        draw.shuffle(slots)
    total = len(slots)
    pitch = (W - 14.0) / total
    size = min(H * 0.5, pitch * 1.4 / level.crowd)
    x = 7.0 + pitch / 2
    phase = draw.uniform(0, 2 * math.pi)
    glyphs: List[Glyph] = []
    k = 0
    upright_tilt = min(level.tilt, 40.0) if 'upside' in rules else level.tilt
    for real in slots:
        if real:
            ch = answer[k]
            k += 1
        else:
            pool = ALPHABET
            if 'upside' in rules:
                pool = ''.join(c for c in ALPHABET if c not in TURN_ALIKE)
            ch = draw.choice(pool)
        s = size * draw.uniform(0.85, 1.12) if level.colours else size
        angle = draw.uniform(-upright_tilt, upright_tilt)
        colour = draw.randrange(len(COLOURS)) if level.colours else 5
        if 'colour' in rules:
            if real:
                colour = keep
            else:
                colour = draw.choice([c for c in range(len(COLOURS))
                                      if c != keep])
        if not real:
            # A decoy breaks at least one of the rules in force; the
            # others it keeps, so only that one gives it away.
            broken = draw.choice(rules)
            if 'colour' in rules and broken != 'colour':
                colour = keep
            if broken == 'small':
                s = size * draw.uniform(0.38, 0.47)
            if broken == 'upside':
                angle = 180.0 + draw.uniform(-15.0, 15.0)
        elif 'small' in rules:
            s = max(s, size * 0.85)
        y = H / 2 + level.wave * math.sin(phase + x / 9.0) + \
            draw.uniform(-1.0, 1.0) * (level.wave * 0.4)
        glyphs.append(Glyph(ch, x + draw.uniform(-0.15, 0.15) * pitch, y, s,
                            angle, draw.choice(faces), colour, real))
        x += pitch
    marks: List[Mark] = []
    tint = lambda: tuple(draw.randrange(90, 230) for _c in range(3))  # noqa
    for _k in range(level.blobs):
        r = draw.uniform(4, 10)
        marks.append(Mark('blob', (draw.uniform(r, W - r),
                                   draw.uniform(r * 0.6, H - r * 0.6), r),
                          0.0, tint() + (draw.randrange(40, 90),)))
    for _k in range(level.clutter):
        marks.append(Mark('stray', (draw.uniform(3, W - 3),
                                    draw.uniform(3, H - 3),
                                    draw.uniform(2.0, 5.0),
                                    draw.uniform(0, 360)), 0.0,
                          tint() + (draw.randrange(50, 110),),
                          draw.choice('abcdefghijkmnpqrstuvwxyz'
                                      '#@&%*?+=~'),
                          draw.randrange(FACES)))
    for _k in range(level.noise):
        if draw.random() < 0.5:
            marks.append(Mark('line', (draw.uniform(0, W), draw.uniform(0, H),
                                       draw.uniform(0, W), draw.uniform(0, H)),
                              draw.uniform(0.2, 0.6),
                              tint() + (draw.randrange(90, 170),)))
        else:
            r = draw.uniform(4, 15)
            marks.append(Mark('arc', (draw.uniform(r, W - r),
                                      draw.uniform(min(r, H / 2),
                                                   max(H - r, H / 2)),
                                      min(r, H / 2 - 0.5),
                                      draw.uniform(0, 360),
                                      draw.uniform(60, 220)),
                              draw.uniform(0.2, 0.6),
                              tint() + (draw.randrange(90, 170),)))
    for _k in range(level.strikes):
        y0 = H / 2 + draw.uniform(-6, 6)
        pts = []
        for j in range(9):
            pts += [W * j / 8, y0 + draw.uniform(-3, 3)]
        c = COLOURS[draw.randrange(len(COLOURS))][1]
        marks.append(Mark('strike', tuple(pts), draw.uniform(0.5, 0.9),
                          c + (220,)))
    light = tuple(draw.randrange(222, 252) for _c in range(3))
    other = tuple(draw.randrange(180, 240) for _c in range(3)) \
        if level.blobs else light
    rule = said(rules, keep)
    return Puzzle(level, glyphs, marks, answer, rule, (light, other),
                  0 if level.rung < 13 else draw.randrange(6, 16))


def said(rules: List[str], keep: int) -> str:
    """The rule in words."""
    leave = [w for r, w in (('small', _('small')),
                            ('upside', _('upside-down'))) if r in rules]
    if 'colour' in rules:
        head = _('Type only the %s characters') % _(COLOURS[keep][0])
    else:
        head = _('Type the characters')
    if not leave:
        return head
    return _('%s, but not the %s ones') % (head, _(' or ').join(leave))


def check(puzzle: Puzzle, typed: str) -> Tuple[bool, str]:
    if typed == puzzle.answer:
        return True, _('Right: %s') % puzzle.answer
    return False, _('It said %s') % puzzle.answer


def ports_for(text: str) -> List[int]:
    """The ports that type *text* and submit it."""
    return [ALPHABET.index(c) for c in text] + [SUBMIT]
