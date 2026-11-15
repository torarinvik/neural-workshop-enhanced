# -*- coding: utf-8 -*-
"""Tuner: find the station playing the tune you just heard.

A tune plays once, twice, and stops. Then an old radio comes on: hiss
across the dial, and here and there a station, each playing its own
little tune over and over. Turn the dial -- drag it, click along it, or
hold the arrow keys (Shift for fine) -- until the station playing that
tune comes in, and press Space to lock on. Locking takes a moment of
staying on the station; locking onto the wrong one loses the trial.
R plays the tune again, at the cost of the time it takes.

Nothing on the screen says which station is which: a needle and a
signal meter show how strong a station is, never what it plays.

The ladder:

* rungs 1-3: three stations with lamps on the dial, each on its own
  instrument and in its own rhythm;
* rungs 4-6: no lamps, four stations, narrower;
* rungs 7-9: every station on the same instrument;
* rungs 10-12: the tune you hear first is in another key on another
  instrument, every station keeps the same rhythm, and one plays the
  same notes in another order;
* rungs 13-15: stations drift along the dial: hold on while locking;
* rungs 16-19: stations fade in and out, and one differs from the tune
  by a single note;
* from rung 20: more stations, narrower, faster drift every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Set, Tuple

from .drshape import Note, Patch, make_patch
from .i18n import _

DOWN, UP, FINE_DOWN, FINE_UP, LOCK, REPLAY = range(6)
PORTS = 6
EVENTS = (LOCK, REPLAY)
DIAL = 100.0
COARSE = 22.0                  # dial units a second
FINE = 4.0
BEAT = 0.2
MAJOR = (0, 2, 4, 5, 7, 9, 11, 12, 14)
RHYTHMS = ((1, 1, 1, 1, 2), (2, 1, 1, 2, 1), (1, 1, 2, 1, 1),
           (1, 2, 1, 1, 2), (2, 2, 1, 1, 1), (1, 1, 1, 2, 2))
VOICES = ('flute', 'organ', 'clarinet', 'pluck', 'bell', 'brass', 'glass',
          'square')
HISS_EVERY = 0.1


class Grade(NamedTuple):
    rung: int
    stations: int
    width: float
    lamps: bool
    one_voice: bool
    shifted: bool              # the tune heard in another key and voice
    drift: float
    fade: bool
    near_miss: bool
    seconds: float
    hold: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        stations=(3 if r < 4 else 4 if r < 7 else 5 if r < 16 else 6
                  if r < 20 else min(9, 6 + top // 3)),
        width=(3.5 if r < 4 else 2.5 if r < 10 else 2.0 if r < 20
               else max(1.3, 1.9 - 0.05 * top)),
        lamps=r < 4,
        one_voice=r >= 7,
        shifted=r >= 10,
        drift=(0.0 if r < 13 else 4.0 if r < 20 else min(8.0, 4.5 + 0.3 * top)),
        fade=r >= 16,
        near_miss=r >= 16,
        seconds=40.0 if r < 20 else max(25.0, 38.0 - top),
        hold=1.0 if r < 13 else 2.0)


class Station(NamedTuple):
    at: float                  # where on the dial, before drifting
    degrees: Tuple[int, ...]
    rhythm: Tuple[int, ...]
    root: float
    voice: int
    phase: float               # seconds into its loop at t = 0
    sway: Tuple[float, float]  # drift rate, drift phase
    fade: Tuple[float, float]  # fade rate, fade phase


class Radio(NamedTuple):
    level: Grade
    stations: List[Station]
    target: int
    heard: Station             # the tune as first played
    listen: float              # seconds of the first playing
    start: float               # where the dial starts
    patches: List[Patch]


def loop(s: Station) -> float:
    return (sum(s.rhythm) + 2) * BEAT


def pitches(s: Station) -> List[float]:
    return [s.root * 2 ** (MAJOR[d] / 12.0) for d in s.degrees]


def shape(s: Station) -> Tuple:
    """What makes a tune the same tune in any key: its steps and rhythm."""
    semis = [MAJOR[d] for d in s.degrees]
    return tuple(b - a for a, b in zip(semis, semis[1:])), s.rhythm


def exact(s: Station) -> Tuple:
    semis = [MAJOR[d] for d in s.degrees]
    return tuple(semis), s.rhythm, round(s.root, 1)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Radio:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        radio = _build(level, draw)
        if radio is None:
            continue
        best = best or radio
        if play(radio)[0]:
            return radio
    return best


def _tune(draw: random.Random) -> Tuple[int, ...]:
    while True:
        d = [draw.randrange(0, 8)]
        for _k in range(4):
            d.append(max(0, min(8, d[-1] + draw.choice((-3, -2, -1, 1, 2,
                                                         3, 4)))))
        if len(set(d)) >= 4:
            return tuple(d)


def _build(level: Grade, draw: random.Random) -> Optional[Radio]:
    n = level.stations
    names = list(VOICES)
    draw.shuffle(names)
    patches = [make_patch(name, draw) for name in names[:n]]
    one = names[0]
    rhythms = list(RHYTHMS)
    draw.shuffle(rhythms)
    target = draw.randrange(n)
    tunes: List[Tuple[int, ...]] = []
    target_tune = _tune(draw)
    for k in range(n):
        if k == target:
            tunes.append(target_tune)
            continue
        tunes.append(_tune(draw))
    others = [k for k in range(n) if k != target]
    draw.shuffle(others)
    if level.shifted and others:
        jumbled = list(target_tune)
        while tuple(jumbled) == target_tune:
            draw.shuffle(jumbled)
        tunes[others[0]] = tuple(jumbled)
    if level.near_miss and len(others) > 1:
        miss = list(target_tune)
        i = draw.randrange(5)
        miss[i] = max(0, min(8, miss[i] + draw.choice((-2, -1, 1, 2))))
        if tuple(miss) == target_tune:
            miss[i] = (miss[i] + 3) % 9
        tunes[others[1]] = tuple(miss)
    spacing = (DIAL - 16.0) / n
    stations: List[Station] = []
    for k in range(n):
        at = 8.0 + spacing * (k + 0.5) + draw.uniform(-0.2, 0.2) * spacing
        rhythm = rhythms[0] if level.shifted else rhythms[k % len(rhythms)]
        root = 220.0 * 2 ** (draw.randrange(0, 7) / 12.0)
        voice = 0 if level.one_voice else k
        stations.append(Station(at, tunes[k], rhythm, root, voice,
                                draw.uniform(0, 2.0),
                                (draw.uniform(0.18, 0.32),
                                 draw.uniform(0, 2 * math.pi)),
                                (draw.uniform(0.25, 0.45),
                                 draw.uniform(0, 2 * math.pi))))
    if level.one_voice:
        patches = [make_patch(one, draw)]
    # Every tune must be told from the target's by the ear.
    t_shape, t_exact = shape(stations[target]), exact(stations[target])
    for k in others:
        if level.shifted and shape(stations[k]) == t_shape:
            return None
        if exact(stations[k]) == t_exact:
            return None
    heard = stations[target]
    if level.shifted:
        other_voice = [nm for nm in VOICES if nm != one and
                       nm not in names[:n]] or [nm for nm in VOICES
                                                if nm != one]
        patches.append(make_patch(draw.choice(other_voice), draw))
        root = heard.root * 2 ** (draw.choice((-5, -4, -3, 3, 4, 5)) / 12.0)
        heard = heard._replace(root=root, voice=len(patches) - 1, phase=0.0)
    else:
        heard = heard._replace(phase=0.0)
    patches.append(make_patch('hiss', draw))
    listen = 2 * loop(heard) + 0.4
    start = draw.uniform(4.0, DIAL - 4.0)
    while abs(start - stations[target].at) < 20:
        start = draw.uniform(4.0, DIAL - 4.0)
    return Radio(level, stations, target, heard, listen, start, patches)


def _on(control) -> Set[int]:
    if control is None:
        return set()
    if isinstance(control, int):
        return {control}
    return set(control)


def play_tune(s: Station, t0: float, times: int, gain: float = 0.7,
              seed: int = 0) -> List[Note]:
    out = []
    t = t0
    for _r in range(times):
        for f, beats in zip(pitches(s), s.rhythm):
            out.append(Note(t, beats * BEAT * 0.9, f, 0.0, 0.0, gain, gain,
                            0.8, s.voice, seed, -1, 0.0))
            seed += 1
            t += beats * BEAT
        t += 2 * BEAT
    return out


class Run:
    def __init__(self, radio: Radio) -> None:
        self.radio = radio
        self.level = radio.level
        self.t = 0.0
        self.dial = radio.start
        self.lock_since: Optional[float] = None
        self.replay_until = 0.0
        self.said = ''
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = play_tune(radio.heard, 0.2, 2)
        self.hiss = len(radio.patches) - 1
        self.end = radio.listen + self.level.seconds
        self.seed = 1000

    # --- the radio
    def on(self) -> bool:
        return self.t >= self.radio.listen

    def where(self, k: int, t: Optional[float] = None) -> float:
        t = self.t if t is None else t
        s = self.radio.stations[k]
        if not self.level.drift:
            return s.at
        return s.at + self.level.drift * math.sin(s.sway[0] * t + s.sway[1])

    def strength(self, k: int, dial: Optional[float] = None,
                 t: Optional[float] = None) -> float:
        dial = self.dial if dial is None else dial
        t = self.t if t is None else t
        s = self.radio.stations[k]
        g = math.exp(-((dial - self.where(k, t)) / self.level.width) ** 2)
        if self.level.fade:
            g *= 0.55 + 0.45 * math.sin(s.fade[0] * t + s.fade[1])
        return g

    def signal(self) -> float:
        if not self.on():
            return 0.0
        return max(self.strength(k) for k in range(len(self.radio.stations)))

    def nearest(self) -> int:
        n = len(self.radio.stations)
        return min(range(n), key=lambda k: abs(self.dial - self.where(k)))

    # --- controls
    def press(self) -> None:
        if self.result is not None or not self.on() or \
                self.lock_since is not None:
            return
        k = self.nearest()
        if abs(self.dial - self.where(k)) > self.level.width:
            self.said = _('Nothing there to lock on to')
            return
        if k != self.radio.target:
            self.result = (False, _('That station plays another tune'))
            return
        self.lock_since = self.t
        self.said = _('Locking on -- stay with it')

    def replay(self) -> None:
        if self.result is not None or self.t < self.replay_until or \
                not self.on():
            return
        heard = self.radio.heard
        self.notes += play_tune(heard, self.t + 0.05, 1, seed=self.seed)
        self.seed += 10
        self.replay_until = self.t + 0.05 + loop(heard)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        t0 = self.t
        self.t += dt
        on = _on(control)
        move = 0.0
        if DOWN in on:
            move -= COARSE
        if UP in on:
            move += COARSE
        if FINE_DOWN in on:
            move -= FINE
        if FINE_UP in on:
            move += FINE
        self.dial = max(0.0, min(DIAL, self.dial + move * dt))
        self._sound(t0, self.t)
        if self.lock_since is not None:
            k = self.radio.target
            if abs(self.dial - self.where(k)) > self.level.width * 0.8:
                self.lock_since = None
                self.said = _('Lost it -- find it and lock again')
            elif self.t - self.lock_since >= self.level.hold:
                self.result = (True, _('Locked on to the tune'))
                return
        if self.t >= self.end:
            self.result = (False, _('Out of time'))

    def _sound(self, a: float, b: float) -> None:
        radio = self.radio
        listen = radio.listen
        if b <= listen:
            return
        a = max(a, listen)
        quiet = 0.15 if self.t < self.replay_until else 1.0
        total = 0.0
        for k, s in enumerate(radio.stations):
            g = self.strength(k)
            total += g
            if g * quiet < 0.03:
                continue
            p = loop(s)
            offsets, at = [], 0.0
            for beats in s.rhythm:
                offsets.append((at, beats))
                at += beats * BEAT
            freqs = pitches(s)
            for j, (off, beats) in enumerate(offsets):
                first = math.ceil((a - s.phase - off) / p)
                onset = s.phase + off + first * p
                if a <= onset < b:
                    self.seed += 1
                    gain = 0.75 * g * quiet
                    self.notes.append(Note(onset, beats * BEAT * 0.9,
                                           freqs[j], 0.0, 0.0, gain, gain,
                                           0.8, s.voice, self.seed, -1, 0.0))
        first = math.ceil(a / HISS_EVERY)
        onset = first * HISS_EVERY
        while onset < b:
            h = (0.05 + 0.3 * max(0.0, 1.0 - total)) * quiet
            self.seed += 1
            self.notes.append(Note(onset, HISS_EVERY, 440.0, 0.0, 0.0, h, h,
                                   0.5, self.hiss, self.seed, -2, 0.0))
            onset += HISS_EVERY


def act(run: Run, port: int) -> None:
    if port == LOCK:
        run.press()
    elif port == REPLAY:
        run.replay()


def autopilot(run: Run) -> List[int]:
    """Go to the station that plays the tune -- the one the ear picks
    out -- and lock on, then stay with it."""
    if not run.on():
        return []
    k = run.radio.target
    w = run.level.width
    d = run.where(k) - run.dial
    out = []
    if abs(d) > 2.5:
        out.append(UP if d > 0 else DOWN)
    elif abs(d) > 0.15 * w:
        out.append(FINE_UP if d > 0 else FINE_DOWN)
    if run.lock_since is None and abs(d) < 0.4 * w:
        out.append(LOCK)
    return out


def play(radio: Radio, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(radio)
    while run.result is None:
        ports = pilot(run)
        for port in ports:
            if port in EVENTS:
                act(run, port)
        run.step(dt, [p for p in ports if p not in EVENTS])
    return run.result
