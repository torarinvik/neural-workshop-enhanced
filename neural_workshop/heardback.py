# -*- coding: utf-8 -*-
"""Heard back: the now-and-earlier and far-cue questions, in sound.

The tones reach the agent only as sound: the screen shows when a tone
plays, never which.

``melody``  four tones, one a frame, then k - 1 silent frames at rung
            k, then the four again with one of them at another pitch;
            the question is put on the last tone: press the place in
            the four, first to fourth, of the tone that changed.
``mark``    one tone in a voice of its own, then a run of look-alike
            tones in the ordinary voice, then a silent frame and the
            question: press the pitch, lowest to highest, of the tone
            in the other voice. Rung k puts 2**k look-alike tones
            between, 2 to 32; higher rungs play as rung 5.

Every tone is one of four pitches, drawn evenly, three or four
semitones apart, and the four move together by up to a semitone from
trial to trial, so no two can be taken for each other.

Chance from the frame the question is put on: one in four for both
(the last tone of ``melody`` is as likely any pitch whichever place
changed; ``mark`` asks on a silent frame). The cheap partial
strategies, which the tests count:

``melody``  keeping only the last tone of the first four: if the last
            tone now differs, the fourth changed, else one of the other
            three: 1/4 + 3/4 * 1/3 = 1/2.
``mark``    pressing the pitch of the last tone heard: one in four.

Two looks (see :mod:`framed`): in look 0 a flute, with an organ for
the marked tone, the ports from first to fourth or lowest to highest;
in look 1 a clarinet, with a plain sine for the marked tone, an octave
higher, the ports the other way round.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, showing
from .farcue import gap
from .i18n import _

KINDS = ('melody', 'mark')
PITCHES = {0: (262.0, 330.0, 392.0, 494.0),
           1: (523.0, 659.0, 784.0, 988.0)}
VOICES = {0: ('flute', 'organ'), 1: ('clarinet', 'sine')}
CARDS = 4
TONE = framed.SHOWN * 0.8


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    k = max(1, int(rung))
    bend = rng.uniform(-1.0, 1.0)
    seed = rng.randrange(1, 10 ** 6)
    plain, marker = VOICES[look]
    order = framed.port_order(look, CARDS)
    data = {'look': look, 'hue': rng.randrange(len(framed.HUES_A)),
            'rim': rng.randrange(len(framed.RIMS)),
            'place': (rng.random(), rng.random())}

    def tone(frame, pitch, voice=0, gain=0.8):
        return showing.note(frame * framed.FRAME, TONE,
                            showing.semitones(PITCHES[look][pitch], bend),
                            gain=gain, voice=voice)
    if kind == 'melody':
        first = [rng.randrange(CARDS) for _t in range(4)]
        where = rng.randrange(4)
        second = list(first)
        second[where] = rng.choice([p for p in range(CARDS)
                                    if p != first[where]])
        frames = tuple(range(4)) + (-1,) * (k - 1) + tuple(range(4, 8))
        played = first + second
        notes = []
        for f, v in enumerate(frames):
            if v >= 0:
                notes.append(tone(f, played[v]))
        data.update(first=tuple(first), second=tuple(second))
        patches = (showing.patch(plain, seed),)
        answer = order.index(where)
        question = _('Which of the four tones changed?')
    elif kind == 'mark':
        n = gap(k)
        pitch = rng.randrange(CARDS)
        fillers = tuple(rng.randrange(CARDS) for _f in range(n))
        frames = (0,) + (1,) * n + (-1,)
        notes = [tone(0, pitch, voice=1, gain=0.9)]
        notes += [tone(1 + i, p) for i, p in enumerate(fillers)]
        data.update(pitch=pitch, fillers=fillers)
        patches = (showing.patch(plain, seed),
                   showing.patch(marker, seed + 1))
        answer = order.index(pitch)
        question = _('Which pitch was the tone in the other voice?')
    else:
        raise ValueError(kind)
    choices = tuple(str(p + 1) for p in range(CARDS))
    return framed.puzzle(kind, k, frames, choices, answer, data, question,
                         notes=notes, patches=patches)


def place_of(puzzle: framed.Puzzle, port: int) -> int:
    """The tone's place (melody) or pitch (mark) *port* presses."""
    return framed.port_order(puzzle.data['look'], CARDS)[port]
