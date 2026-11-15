# -*- coding: utf-8 -*-
"""Tuner: find the station playing the sound you just heard.

A sound plays once -- a dog, a kettle, a train -- and stops. Then an
old radio comes on: hiss across the dial, and here and there a
station, each playing its own recording over and over. Turn the dial
-- drag it, click along it, or hold the arrow keys (Shift for fine) --
until the station playing that sound comes in, and press Space to lock
on. Locking takes a moment of staying on the station; locking onto the
wrong one loses the trial. R plays the sound again, at the cost of the
time it takes.

The sounds are real recordings from ESC-50 (see
:mod:`neural_workshop.soundbank`) when that library has been
downloaded, and little synthesised tunes when it has not; the ladder
is the same either way. Nothing on the screen says which station is
which: a needle and a signal meter show how strong a station is, never
what it plays.

The ladder:

* rungs 1-3: three stations with lamps on the dial, each a different
  kind of sound (an animal, the weather, a machine...);
* rungs 4-6: no lamps, four stations, narrower;
* rungs 7-9: every station the same walk of life -- all animals, say;
* rungs 10-12: the sound you hear first is played faster or slower
  than the station plays it, and one station plays it backwards;
* rungs 13-15: stations drift along the dial: hold on while locking;
* rungs 16-19: stations fade in and out, and one plays another
  recording of the same kind of sound -- a different dog;
* from rung 20: more stations, narrower, faster drift every rung, and
  from rung 24 two other recordings of the same kind.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import bisect
import math
import random
from array import array
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from . import soundbank
from .drshape import RATE, Note, make_patch, synth
from .i18n import _

DOWN, UP, FINE_DOWN, FINE_UP, LOCK, REPLAY = range(6)
PORTS = 6
EVENTS = (LOCK, REPLAY)
DIAL = 100.0
COARSE = 22.0                  # dial units a second
FINE = 4.0
GAP = 0.35                     # silence between a station's loops
LEAD = 0.2                     # the first hearing starts this late
QUIET = 0.15                   # the radio's level while the sound replays
# The fallback bank: little tunes.
BEAT = 0.2
MAJOR = (0, 2, 4, 5, 7, 9, 11, 12, 14)
RHYTHMS = ((1, 1, 1, 1, 2), (2, 1, 1, 2, 1), (1, 1, 2, 1, 1),
           (1, 2, 1, 1, 2), (2, 2, 1, 1, 1), (1, 1, 1, 2, 2))
VOICES = ('flute', 'organ', 'clarinet', 'pluck', 'bell', 'brass', 'glass',
          'square')
TAIL = 0.3                     # a tune's last note rings this long


class Grade(NamedTuple):
    rung: int
    stations: int
    width: float
    lamps: bool
    same_group: bool           # every station one walk of life
    shifted: bool              # the sound heard faster or slower
    backward: bool             # one station plays the sound backwards
    drift: float
    fade: bool
    near_miss: int             # other recordings of the same kind
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
        same_group=r >= 7,
        shifted=r >= 10,
        backward=r >= 10,
        drift=(0.0 if r < 13 else 4.0 if r < 20 else min(8.0, 4.5 + 0.3 * top)),
        fade=r >= 16,
        near_miss=0 if r < 16 else 1 if r < 24 else 2,
        seconds=40.0 if r < 20 else max(25.0, 38.0 - top),
        hold=1.0 if r < 13 else 2.0)


class Sound(NamedTuple):
    """One recording as a station or the first hearing plays it."""
    bank: str                  # 'esc50' or 'tune'
    ref: Tuple                 # (row,) or (degrees, rhythm, root, voice)
    label: int                 # the kind of sound
    group: int                 # its walk of life
    speed: float = 1.0         # played faster (pitch and pace together)
    backward: bool = False


class Station(NamedTuple):
    at: float                  # where on the dial, before drifting
    sound: Sound
    phase: float               # seconds into its loop at t = 0
    sway: Tuple[float, float]  # drift rate, drift phase
    fade: Tuple[float, float]  # fade rate, fade phase


class Radio(NamedTuple):
    level: Grade
    stations: List[Station]
    target: int
    heard: Sound               # the sound as first played
    listen: float              # seconds before the radio comes on
    start: float               # where the dial starts
    seed: int                  # for the hiss


# --- the sounds -------------------------------------------------------------

_clips: Dict[int, soundbank.Clip] = {}


def _clip(row: int) -> soundbank.Clip:
    if row not in _clips:
        _clips.update((c.row, c) for c in soundbank.bank())
    return _clips[row]


def length(sound: Sound) -> float:
    """Seconds the sound lasts, without opening it."""
    if sound.bank == 'esc50':
        c = _clip(sound.ref[0])
        raw = min(c.end - c.start, soundbank.LONGEST)
    else:
        raw = sum(sound.ref[1]) * BEAT + TAIL
    return raw / sound.speed


def loop(s: Station) -> float:
    return length(s.sound) + GAP


_waves: Dict[Sound, array] = {}
_WAVES_KEPT = 48


def _tune_wave(sound: Sound) -> array:
    degrees, rhythm, root, voice = sound.ref
    patch = make_patch(voice, random.Random(VOICES.index(voice)))
    notes, t = [], 0.0
    for k, (d, beats) in enumerate(zip(degrees, rhythm)):
        f = root * 2 ** (MAJOR[d] / 12.0)
        notes.append(Note(t, beats * BEAT * 0.9, f, 0.0, 0.0, 0.8, 0.8, 0.8,
                          0, k, -1, 0.0))
        t += beats * BEAT
    pcm = array('h')
    pcm.frombytes(synth(notes, 0.0, t + TAIL, [patch]))
    out = array('f', (v / 32768.0 for v in pcm[::2]))
    level = math.sqrt(sum(v * v for v in out) / max(1, len(out)))
    if level > 1e-5:
        g = soundbank.LOUDNESS / level
        for i in range(len(out)):
            out[i] = max(-1.0, min(1.0, out[i] * g))
    return out


def wave(sound: Sound) -> array:
    """The sound as mono floats at :data:`RATE`, as it is played."""
    got = _waves.get(sound)
    if got is not None:
        return got
    base = soundbank.samples(_clip(sound.ref[0])) if sound.bank == 'esc50' \
        else _tune_wave(sound)
    if sound.speed != 1.0:
        n = int(len(base) / sound.speed)
        last = len(base) - 1
        out = array('f', bytes(4 * n))
        for i in range(n):
            x = i * sound.speed
            j = int(x)
            f = x - j
            out[i] = base[j] * (1 - f) + base[min(last, j + 1)] * f
        base = out
    if sound.backward:
        base = array('f', reversed(base))
    if len(_waves) >= _WAVES_KEPT:
        _waves.pop(next(iter(_waves)))
    _waves[sound] = base
    return base


def same(a: Sound, b: Sound) -> bool:
    """The same recording, the same way round (speed aside)."""
    return a.bank == b.bank and a.ref == b.ref and a.backward == b.backward


def describe(sound: Sound) -> str:
    """For tests and logs, never the screen."""
    if sound.bank == 'esc50':
        name = '%s #%d' % (soundbank.CLASSES[sound.label], sound.ref[0])
    else:
        name = 'tune %s on %s' % (''.join(map(str, sound.ref[0])),
                                  sound.ref[3])
    if sound.backward:
        name += ' backwards'
    if sound.speed != 1.0:
        name += ' x%.2f' % sound.speed
    return name


# --- dealing ----------------------------------------------------------------

def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None,
         bank: Optional[str] = None) -> Radio:
    """A radio for *rung*. The sounds come from *bank* -- 'esc50' or
    'tune' -- or from ESC-50 whenever it has been downloaded."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    if bank is None:
        bank = 'esc50' if soundbank.ready() else 'tune'
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        radio = _build(level, draw, bank)
        best = best or radio
        if play(radio)[0]:
            return radio
    return best


def _esc_sounds(level: Grade, draw: random.Random
                ) -> Tuple[List[Sound], int]:
    by_label: Dict[int, List[int]] = {}
    for c in soundbank.bank():
        by_label.setdefault(c.label, []).append(c.row)
    n = level.stations
    groups = list(range(len(soundbank.GROUPS)))
    draw.shuffle(groups)
    kinds = {g: [lb for lb in sorted(by_label) if lb // 10 == g]
             for g in groups}
    if level.same_group:
        # The walk of life with the most kinds on disk, if none has enough.
        g = next((g for g in groups if len(kinds[g]) >= n),
                 max(groups, key=lambda g: len(kinds[g])))
        labels = list(kinds[g])
        draw.shuffle(labels)
        labels = labels[:n]
    else:
        labels = []
        while len(labels) < min(n, len(by_label)):
            for g in groups:
                choice = [lb for lb in kinds[g] if lb not in labels]
                if choice and len(labels) < n:
                    labels.append(draw.choice(choice))
    n = len(labels)
    target = draw.randrange(n)
    sounds = [Sound('esc50', (draw.choice(by_label[lb]),), lb, lb // 10)
              for lb in labels]
    t = sounds[target]
    kin = [r for r in by_label[t.label] if r != t.ref[0]]
    draw.shuffle(kin)
    twins = [Sound('esc50', (r,), t.label, t.group)
             for r in kin[:level.near_miss]]
    return _decoys(level, draw, sounds, target, twins), target


def _tune(draw: random.Random) -> Tuple[int, ...]:
    while True:
        d = [draw.randrange(0, 8)]
        for _k in range(4):
            d.append(max(0, min(8, d[-1] + draw.choice((-3, -2, -1, 1, 2,
                                                         3, 4)))))
        if len(set(d)) >= 4:
            return tuple(d)


def _tune_sounds(level: Grade, draw: random.Random
                 ) -> Tuple[List[Sound], int]:
    n = level.stations
    voices = list(VOICES)
    draw.shuffle(voices)
    rhythms = list(RHYTHMS)
    draw.shuffle(rhythms)
    sounds: List[Sound] = []
    seen = set()
    for k in range(n):
        tune = _tune(draw)
        while tune in seen:
            tune = _tune(draw)
        seen.add(tune)
        g = 0 if level.same_group else k
        root = 220.0 * 2 ** (draw.randrange(0, 7) / 12.0)
        sounds.append(Sound('tune', (tune, rhythms[k % len(rhythms)], root,
                                     voices[g % len(voices)]), k, g))
    target = draw.randrange(n)
    t = sounds[target]
    twins = []
    for _k in range(level.near_miss):
        miss = list(t.ref[0])
        while tuple(miss) in seen:
            i = draw.randrange(5)
            miss[i] = max(0, min(8, miss[i] + draw.choice((-2, -1, 1, 2))))
        seen.add(tuple(miss))
        twins.append(t._replace(ref=(tuple(miss),) + t.ref[1:]))
    return _decoys(level, draw, sounds, target, twins), target


def _decoys(level: Grade, draw: random.Random, sounds: List[Sound],
            target: int, twins: List[Sound]) -> List[Sound]:
    """Put the target's look-alikes on some of the other stations."""
    others = [k for k in range(len(sounds)) if k != target]
    draw.shuffle(others)
    alike = ([sounds[target]._replace(backward=True)]
             if level.backward else []) + twins
    for k, sound in zip(others, alike):
        sounds[k] = sound
    return sounds


def _build(level: Grade, draw: random.Random, bank: str) -> Radio:
    if bank == 'esc50':
        sounds, target = _esc_sounds(level, draw)
    else:
        sounds, target = _tune_sounds(level, draw)
    n = len(sounds)
    spacing = (DIAL - 16.0) / n
    stations: List[Station] = []
    for k, sound in enumerate(sounds):
        at = 8.0 + spacing * (k + 0.5) + draw.uniform(-0.2, 0.2) * spacing
        stations.append(Station(at, sound, draw.uniform(0, 2.0),
                                (draw.uniform(0.18, 0.32),
                                 draw.uniform(0, 2 * math.pi)),
                                (draw.uniform(0.25, 0.45),
                                 draw.uniform(0, 2 * math.pi))))
    heard = sounds[target]
    if level.shifted:
        heard = heard._replace(speed=round(draw.choice(
            (draw.uniform(0.78, 0.88), draw.uniform(1.14, 1.28))), 3))
    listen = LEAD + length(heard) + 0.5
    start = draw.uniform(4.0, DIAL - 4.0)
    while abs(start - stations[target].at) < 20:
        start = draw.uniform(4.0, DIAL - 4.0)
    return Radio(level, stations, target, heard, listen, start,
                 draw.randrange(1 << 20))


def _on(control) -> Set[int]:
    if control is None:
        return set()
    if isinstance(control, int):
        return {control}
    return set(control)


# --- the run ------------------------------------------------------------------

class Run:
    def __init__(self, radio: Radio) -> None:
        self.radio = radio
        self.level = radio.level
        self.t = 0.0
        self.dial = radio.start
        self.lock_since: Optional[float] = None
        self.replay_until = LEAD + length(radio.heard)
        self.said = ''
        self.result: Optional[Tuple[bool, str]] = None
        self.end = radio.listen + self.level.seconds
        # What the radio sounds like, for mixing afterwards: when the
        # sound was played from the start, and each station's level
        # (and last, the hiss's) at every step.
        self.plays: List[float] = [LEAD]
        n = len(radio.stations)
        self.times: List[float] = [0.0]
        self.gains: List[Tuple[float, ...]] = [(0.0,) * (n + 1)]

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
            self.result = (False, _('That station plays another sound'))
            return
        self.lock_since = self.t
        self.said = _('Locking on -- stay with it')

    def replay(self) -> None:
        if self.result is not None or self.t < self.replay_until or \
                not self.on():
            return
        self.plays.append(self.t + 0.05)
        self.replay_until = self.t + 0.05 + length(self.radio.heard)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
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
        self._log()
        if self.lock_since is not None:
            k = self.radio.target
            if abs(self.dial - self.where(k)) > self.level.width * 0.8:
                self.lock_since = None
                self.said = _('Lost it -- find it and lock again')
            elif self.t - self.lock_since >= self.level.hold:
                self.result = (True, _('Locked on to the sound'))
                return
        if self.t >= self.end:
            self.result = (False, _('Out of time'))

    def _log(self) -> None:
        n = len(self.radio.stations)
        if not self.on():
            levels = (0.0,) * (n + 1)
        else:
            quiet = QUIET if self.t < self.replay_until else 1.0
            each = [self.strength(k) for k in range(n)]
            hiss = 0.05 + 0.4 * max(0.0, 1.0 - sum(each))
            levels = tuple(g * quiet for g in each) + (hiss * quiet,)
        # Gains before times: a reader on another thread sees a time
        # only once its gains are there.
        self.gains.append(levels)
        self.times.append(self.t)


# --- the sound of the run ---------------------------------------------------

_hiss: Dict[int, array] = {}


def _hiss_wave(seed: int) -> array:
    got = _hiss.get(seed)
    if got is None:
        draw = random.Random(seed)
        got, last = array('f'), 0.0
        for _i in range(RATE):
            last = 0.6 * last + 0.4 * draw.uniform(-1.0, 1.0)
            got.append(last * 0.5)
        if len(_hiss) > 8:
            _hiss.clear()
        _hiss[seed] = got
    return got


def mix(run: Run, t0: float, t1: float) -> bytes:
    """What the radio played from *t0* to *t1*: stereo 16-bit PCM at
    :data:`RATE`. Station levels follow the run's log, smoothly between
    its steps; past the end of the log they hold."""
    frames = max(0, int(round((t1 - t0) * RATE)))
    if frames == 0:
        return b''
    out = [0.0] * frames
    radio = run.radio
    heard = wave(radio.heard)
    for at in list(run.plays):
        a = int(round((at - t0) * RATE))
        lo, hi = max(0, a), min(frames, a + len(heard))
        for i in range(lo, hi):
            out[i] += heard[i - a]
    times, gains = run.times, run.gains
    count = min(len(times), len(gains))
    first = max(0, bisect.bisect_right(times, t0, 0, count) - 1)
    waves = [wave(s.sound) for s in radio.stations]
    noise = _hiss_wave(radio.seed)
    gap = int(GAP * RATE)
    hiss = len(waves)
    start = int(round(t0 * RATE))
    j = first
    while True:
        ta, ga = times[j], gains[j]
        if j + 1 < count:
            tb, gb = times[j + 1], gains[j + 1]
        else:
            tb, gb = max(t1, ta) + 1.0, ga
        lo = 0 if j == first else max(0, int(math.ceil((ta - t0) * RATE)))
        hi = min(frames, int(math.ceil((tb - t0) * RATE)))
        if hi > lo:
            span = max(1e-9, (tb - ta) * RATE)
            base = (ta - t0) * RATE
            for k in range(len(ga)):
                g0, g1 = ga[k], gb[k]
                if g0 < 0.004 and g1 < 0.004:
                    continue
                slope = (g1 - g0) / span
                if k == hiss:
                    src, period, skew = noise, len(noise), 0
                else:
                    src = waves[k]
                    period = len(src) + gap
                    skew = int(round(radio.stations[k].phase * RATE))
                size = len(src)
                at = start + skew
                for i in range(lo, hi):
                    p = (at + i) % period
                    if p < size:
                        g = g0 + slope * (i - base)
                        out[i] += src[p] * (g if g < 1.0 else 1.0)
        if j + 1 >= count or tb >= t1:
            break
        j += 1
    pcm = array('h', bytes(4 * frames))
    for i, v in enumerate(out):
        s = int((1.0 if v > 1.0 else -1.0 if v < -1.0 else v) * 32000)
        pcm[2 * i] = s
        pcm[2 * i + 1] = s
    return pcm.tobytes()


def warm(radio: Radio) -> None:
    """Open every sound the radio will play, so mixing never waits."""
    wave(radio.heard)
    for s in radio.stations:
        wave(s.sound)
    _hiss_wave(radio.seed)


def act(run: Run, port: int) -> None:
    if port == LOCK:
        run.press()
    elif port == REPLAY:
        run.replay()


def autopilot(run: Run) -> List[int]:
    """Go to the station that plays the sound -- the one the ear picks
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
