# -*- coding: utf-8 -*-
"""Sound that follows a run as it goes: engines that pass, strings being
tuned, a cricket heard as the head turns.

A :class:`Track` is one continuous sound -- a set of partials and some
noise -- whose pitch, loudness in each ear and brightness the run sets
once a step. Between two settings everything slides in a straight
line, and the phase is the integral of the pitch, so the sound is the
same whichever stretch of it is asked for, and however it is cut up:
the speaker and the agent's audio channel each ask for their own
stretches and hear the same thing.

A track may also be gated -- switched on and off in pulses, the way a
cricket chirps -- by a pattern fixed in advance.

Pure Python, by table lookup: a few tracks of a few partials play in
real time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import bisect
import math
import random
from array import array
from typing import List, Optional, Sequence, Tuple

from . import drshape as synth

RATE = synth.RATE
_TABLE = 4096
_MASK = _TABLE - 1
_SIN = array('f', [math.sin(2 * math.pi * i / _TABLE) for i in range(_TABLE)])
_NOISE = array('f', [random.Random(7).uniform(-1, 1) for _i in range(RATE)])
#: How long a track holds its last setting past the end of its log
#: before falling silent.
HOLD = 0.25


class Gate(object):
    """Pulses within bursts: on for *duty* of every pulse (*rate* a
    second), pulses only during the first *burst* seconds of every
    *every*; offset by *phase* seconds."""

    def __init__(self, rate: float, duty: float, burst: float, every: float,
                 phase: float = 0.0) -> None:
        self.rate, self.duty = rate, duty
        self.burst, self.every, self.phase = burst, every, phase

    def at(self, t: float) -> float:
        t += self.phase
        if self.every > 0 and (t % self.every) >= self.burst:
            return 0.0
        return 1.0 if (t * self.rate) % 1.0 < self.duty else 0.0


class Track(object):
    """One continuous sound, set step by step."""

    def __init__(self, partials: Sequence[Tuple[float, float]] = ((1, 1.0),),
                 noise: float = 0.0, gate: Optional[Gate] = None) -> None:
        self.partials = tuple(partials)
        self.noise = noise
        self.gate = gate
        self.t: List[float] = []
        self.f: List[float] = []
        self.l: List[float] = []
        self.r: List[float] = []
        self.b: List[float] = []
        self.ph: List[float] = []      # phase, in turns, at each setting

    def set(self, t: float, freq: float, left: float, right: float,
            bright: float = 1.0) -> None:
        """From *t* on: this pitch, these loudnesses, this brightness (0
        leaves the fundamental alone, 1 every partial at full)."""
        if self.t and t <= self.t[-1] + 1e-9:
            # the same moment set again: the last word stands
            self.f[-1], self.l[-1], self.r[-1], self.b[-1] = \
                freq, left, right, bright
            return
        ph = 0.0
        if self.t:
            ph = self.ph[-1] + 0.5 * (self.f[-1] + freq) * (t - self.t[-1])
        self.t.append(t)
        self.f.append(freq)
        self.l.append(left)
        self.r.append(right)
        self.b.append(bright)
        self.ph.append(ph)

    def render(self, out: List[float], t0: float, n: int) -> None:
        """Add samples *t0* .. *t0 + n/RATE* into *out* (stereo, two
        floats a frame)."""
        times = self.t
        if not times:
            return
        end = times[-1] + HOLD
        k = max(0, bisect.bisect_right(times, t0) - 1)
        i = max(0, int(math.ceil((times[0] - t0) * RATE)))
        partials, noise, gate = self.partials, self.noise, self.gate
        base = int(round(t0 * RATE))
        while i < n and k < len(times):
            ta = times[k]
            tb = times[k + 1] if k + 1 < len(times) else end
            stop = min(n, int(math.ceil((tb - t0) * RATE)))
            if stop <= i:
                k += 1
                continue
            span = max(1e-9, tb - ta)
            f0 = self.f[k]
            f1 = self.f[k + 1] if k + 1 < len(times) else f0
            l0, r0 = self.l[k], self.r[k]
            l1 = self.l[k + 1] if k + 1 < len(times) else 0.0
            r1 = self.r[k + 1] if k + 1 < len(times) else 0.0
            if k + 1 >= len(times):          # past the log: fade out
                l1 = r1 = 0.0
            if max(l0, l1, r0, r1) < 1e-4:   # silent all the way: skip
                i = stop
                k += 1
                continue
            bright = self.b[k]
            amps = [(m, a * (1.0 if j == 0 else bright))
                    for j, (m, a) in enumerate(partials)]
            ph0 = self.ph[k]
            slope = (f1 - f0) / span
            for j in range(i, stop):
                s = t0 + j / RATE - ta
                if s < 0:
                    continue
                w = s / span
                gl = l0 + (l1 - l0) * w
                gr = r0 + (r1 - r0) * w
                if gl <= 1e-5 and gr <= 1e-5:
                    continue
                if gate is not None and gate.at(ta + s) == 0.0:
                    continue
                turn = ph0 + f0 * s + 0.5 * slope * s * s
                v = 0.0
                for m, a in amps:
                    v += a * _SIN[int(turn * m * _TABLE) & _MASK]
                if noise:
                    v += noise * _NOISE[(base + j) % RATE]
                out[2 * j] += v * gl
                out[2 * j + 1] += v * gr
            i = stop
            k += 1


def pan(gain: float, side: float) -> Tuple[float, float]:
    """Left and right loudness for *gain* heard from *side* (-1 left, 1
    right), the total power kept."""
    a = (max(-1.0, min(1.0, side)) + 1) * math.pi / 4
    return gain * math.cos(a), gain * math.sin(a)


def mix(tracks: Sequence[Track], t0: float, t1: float,
        notes: Sequence = (), patches: Sequence = ()) -> bytes:
    """Stereo 16-bit PCM of *tracks* (and any synth *notes*) from *t0*
    to *t1*."""
    n = max(0, int(round((t1 - t0) * RATE)))
    if n == 0:
        return b''
    out = [0.0] * (2 * n)
    for tr in tracks:
        tr.render(out, t0, n)
    if notes:
        raw = array('h', synth.synth(notes, t0, t1, patches))
        for j in range(min(len(raw), 2 * n)):
            out[j] += raw[j] / 32768.0
    pcm = array('h', bytes(4 * n))
    for j, v in enumerate(out):
        pcm[j] = int((1.0 if v > 1.0 else -1.0 if v < -1.0 else v) * 30000)
    return pcm.tobytes()


def make_patches(names: Sequence[str]) -> list:
    return [synth.make_patch(p, random.Random(k + 1))
            for k, p in enumerate(names)]
