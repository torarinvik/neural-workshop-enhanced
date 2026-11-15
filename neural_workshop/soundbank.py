# -*- coding: utf-8 -*-
"""Recorded sounds for the listening tasks, ready to loop and mix.

The bank is ESC-50 -- two thousand five-second recordings of fifty
kinds of everyday sound, in five walks of life (animals, weather and
water, people, the home, the street) -- fetched from Hugging Face by
:mod:`neural_workshop.datasets` into the data directory. Which clip is
which, and which stretch of each actually sounds, is known beforehand
from ``res/misc/esc50/index.tsv`` (built by ``tools/index_esc50.py``),
so a task can choose its sounds by kind without opening a file: three
sounds from three walks of life, or two recordings of the same dog.

A clip is opened only when it is to be heard: the sounding stretch,
mono, at :data:`RATE`, brought to one loudness, with its ends faded so
it loops without a click. A player who never downloaded the library
gets an empty bank, and a task falls back on sounds it makes itself.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
import wave
from array import array
from typing import Dict, List, NamedTuple, Optional

from . import datasets, runtime
from .drshape import RATE
from .paths import get_res_dir

#: ESC-50's fifty classes in its own order; class // 10 is the group.
CLASSES = (
    'dog', 'rooster', 'pig', 'cow', 'frog', 'cat', 'hen', 'insects',
    'sheep', 'crow',
    'rain', 'sea waves', 'crackling fire', 'crickets', 'chirping birds',
    'water drops', 'wind', 'pouring water', 'toilet flush', 'thunderstorm',
    'crying baby', 'sneezing', 'clapping', 'breathing', 'coughing',
    'footsteps', 'laughing', 'brushing teeth', 'snoring', 'drinking',
    'door knock', 'mouse click', 'keyboard typing', 'door creaks',
    'can opening', 'washing machine', 'vacuum cleaner', 'clock alarm',
    'clock tick', 'glass breaking',
    'helicopter', 'chainsaw', 'siren', 'car horn', 'engine', 'train',
    'church bells', 'airplane', 'fireworks', 'hand saw')
GROUPS = ('animals', 'nature', 'people', 'home', 'street')

#: The longest stretch of a clip that is looped, in seconds.
LONGEST = 3.5
#: A clip shorter than this, or more silence than sound, is not used.
SHORTEST = 1.0
SOUNDING = 0.45
QUIETEST = -42.0             # dB below full scale
#: Every clip is brought to this loudness (RMS, full scale = 1).
LOUDNESS = 0.12
FADE = 0.012                 # seconds faded in and out at each end
#: Fewer usable clips than this and the bank counts as missing.
ENOUGH = 300


class Clip(NamedTuple):
    row: int
    label: int
    start: float              # seconds into the file
    end: float
    sounding: float
    db: float

    @property
    def group(self) -> int:
        return self.label // 10

    @property
    def name(self) -> str:
        return CLASSES[self.label]


_index: Optional[List[Clip]] = None
_waves: Dict[int, array] = {}
_WAVES_KEPT = 64


def index_path() -> str:
    return os.path.join(get_res_dir(), 'misc', 'esc50', 'index.tsv')


def _read_index() -> List[Clip]:
    clips = []
    try:
        with open(index_path()) as handle:
            for line in handle:
                if line.startswith('#') or not line.strip():
                    continue
                row, label, a, b, share, db = line.split('\t')
                clips.append(Clip(int(row), int(label), int(a) / 1000.0,
                                  int(b) / 1000.0, float(share), float(db)))
    except (OSError, ValueError) as exc:
        runtime.debug_msg('sound bank index: %s' % exc)
        return []
    return clips


def usable(clip: Clip) -> bool:
    return (clip.end - clip.start >= SHORTEST and clip.sounding >= SOUNDING
            and clip.db >= QUIETEST)


def bank() -> List[Clip]:
    """Every usable clip on disk, in row order; empty when the library
    was never downloaded."""
    global _index
    if not _index:                  # an empty bank is looked for again
        on_disk = set(os.path.basename(p) for p in
                      datasets.local_files(datasets.ESC50))
        found = [c for c in _read_index()
                 if usable(c) and '%07d.wav' % c.row in on_disk]
        _index = found if len(found) >= ENOUGH else []
    return _index


def ready() -> bool:
    return bool(bank())


def forget() -> None:
    """Drop what is known, for tests and after a download."""
    global _index
    _index = None
    _waves.clear()


def _path(row: int) -> str:
    return os.path.join(datasets.datasets_dir(), datasets.ESC50.key,
                        '%07d.wav' % row)


def samples(clip: Clip) -> array:
    """The clip's sounding stretch: mono floats at :data:`RATE`, at the
    bank's loudness, faded at both ends. Silence if it will not load."""
    got = _waves.get(clip.row)
    if got is not None:
        return got
    out = array('f')
    try:
        with wave.open(_path(clip.row)) as w:
            rate, chans = w.getframerate(), w.getnchannels()
            length = min(clip.end - clip.start, LONGEST)
            w.setpos(int(clip.start * rate))
            raw = array('h')
            raw.frombytes(w.readframes(int(length * rate)))
        if chans > 1:
            raw = array('h', raw[::chans])
        if rate == 2 * RATE:            # ESC-50: average pairs
            out = array('f', ((a + b) / 65536.0
                              for a, b in zip(raw[0::2], raw[1::2])))
        else:                           # box filter, then decimate
            step = rate / float(RATE)
            for i in range(int(len(raw) / step)):
                a = int(i * step)
                b = max(a + 1, int((i + 1) * step))
                out.append(sum(raw[a:b]) / (32768.0 * (b - a)))
    except (OSError, EOFError, wave.Error) as exc:
        runtime.debug_msg('sound bank row %d: %s' % (clip.row, exc))
        out = array('f', bytes(4 * int(RATE * SHORTEST)))
    level = math.sqrt(sum(v * v for v in out) / max(1, len(out)))
    gain = LOUDNESS / level if level > 1e-5 else 0.0
    fade = max(1, int(FADE * RATE))
    n = len(out)
    for i in range(n):
        g = gain
        if i < fade:
            g *= i / fade
        elif i >= n - fade:
            g *= (n - 1 - i) / fade
        out[i] = max(-1.0, min(1.0, out[i] * g))
    if len(_waves) >= _WAVES_KEPT:
        _waves.pop(next(iter(_waves)))
    _waves[clip.row] = out
    return out
