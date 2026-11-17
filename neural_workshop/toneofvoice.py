# -*- coding: utf-8 -*-
"""Tone of Voice: hear how someone feels.

An actor says an ordinary sentence -- "It's eleven o'clock" -- angry,
disgusted, afraid, happy, sad or plainly; the words are the same
whatever the feeling, so only the voice tells. The clips are CREMA-D's
(see :mod:`neural_workshop.socialdata`), and only those that listeners
who heard them (and did not see the face) took for the emotion the
actor meant; how many of them agreed sets how plain a clip is. Each
clip plays twice.

* rung 1: two emotions to choose between, on clips nearly every listener
  heard the same way;
* rungs 2-3: three; rungs 4-6: four;
* rungs 7-9: all six, the plain voice among them;
* rungs 10-12: clips fewer listeners agreed on, and a hiss behind them;
* rungs 13 and up: only the first second of each clip, and a louder
  hiss; at 16, clips only a few more than half agreed on.

Without the clips (``python -m neural_workshop.socialdata voices``) the
voice is a hum made here: six syllables whose pitch, pace, loudness and
fall follow what is known of how each emotion sounds.

For the agent boundary: ports 0-7 pick the answer of that number; the
clip comes on the audio channel.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import math
import random
import wave
from array import array
from typing import List, NamedTuple, Optional, Tuple

from . import drshape as synth
from . import feelings as F
from . import hand as H
from . import socialdata as D
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot = F.act, F.autopilot
RATE = synth.RATE
GAP = 0.6                      # silence between the two hearings
LEAD = 0.4                     # silence before the first

EMOTIONS = tuple(n for _l, _c, n in D.VOICES)
NEUTRAL = EMOTIONS.index('neutral')
SAID = {'anger': _('angry'), 'disgust': _('disgusted'), 'fear': _('afraid'),
        'happiness': _('happy'), 'neutral': _('plain, no feeling'),
        'sadness': _('sad')}


class Grade(NamedTuple):
    rung: int
    choices: int               # emotions to choose among
    plain: bool                # the plain voice among them
    agree: float               # the least share of listeners agreeing
    hiss: float                # loudness of the hiss behind the voice
    cut: float                 # seconds of each clip kept (0: all)
    answer: float              # seconds to answer after the second hearing
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    choices = 2 if r == 1 else 3 if r < 4 else 4 if r < 7 else 6
    agree = 0.85 if r == 1 else 0.8 if r < 4 else 0.7 if r < 7 else \
        0.65 if r < 10 else 0.55 if r < 16 else 0.5
    hiss = 0.0 if r < 10 else 0.12 if r < 13 else 0.2 if r < 16 else 0.28
    cut = 0.0 if r < 13 else 1.2 if r < 16 else 0.9
    answer = max(2.5, 6.0 - 0.2 * (r - 1))
    return Grade(r, choices, r >= 7, agree, hiss, cut, answer,
                 20 if choices == 2 else 10, 0.7)


# --- the voices -------------------------------------------------------------------

class Heard(NamedTuple):
    """What an item plays: a clip, or a hum made here."""
    clip: str                  # CREMA-D name, or '' for a hum
    emotion: int
    seed: int


@functools.lru_cache(maxsize=64)
def _samples(h: Heard, cut: float) -> Tuple[float, ...]:
    """The voice as mono floats at :data:`RATE`, brought to one loudness."""
    if h.clip:
        try:
            with wave.open(D.voice_path(D.Voice(h.clip, h.emotion, '', 0))) \
                    as w:
                rate = w.getframerate()
                raw = array('h')
                raw.frombytes(w.readframes(w.getnframes()))
                if w.getnchannels() > 1:
                    raw = array('h', raw[::w.getnchannels()])
        except (OSError, EOFError, wave.Error):
            raw, rate = array('h'), RATE
        step = rate / float(RATE)
        out = [raw[int(i * step)] / 32768.0
               for i in range(int(len(raw) / step))]
    else:
        out = _hum(h.emotion, h.seed)
    if cut > 0:
        # from where the voice starts, not from the silence before it
        start = next((i for i, v in enumerate(out) if abs(v) > 0.02), 0)
        out = out[start:start + int(cut * RATE)]
    peak = max((abs(v) for v in out), default=0.0)
    g = 0.7 / peak if peak > 1e-6 else 0.0
    n = len(out)
    fade = int(0.02 * RATE)
    return tuple(v * g * min(1.0, i / fade, (n - 1 - i) / fade)
                 for i, v in enumerate(out))


#: For the hum: (pitch in Hz, pitch swing, syllables a second, loudness,
#: fall over the phrase, roughness).
HUM = {'anger': (190, 0.35, 5.0, 1.0, 0.25, 0.5),
       'disgust': (140, 0.15, 2.8, 0.6, 0.3, 0.3),
       'fear': (260, 0.25, 6.0, 0.5, -0.15, 0.1),
       'happiness': (240, 0.45, 4.5, 0.85, -0.05, 0.0),
       'neutral': (160, 0.08, 3.8, 0.6, 0.1, 0.0),
       'sadness': (130, 0.06, 2.4, 0.35, 0.35, 0.0)}


def _hum(emotion: int, seed: int) -> List[float]:
    pitch, swing, rate, loud, fall, rough = HUM[EMOTIONS[emotion]]
    d = random.Random(seed)
    pitch *= d.uniform(0.9, 1.1)
    out: List[float] = []
    for k in range(6):
        dur = d.uniform(0.75, 1.25) / rate
        f0 = pitch * (1 + swing * d.uniform(-1, 1)) * (1 - fall * k / 6)
        n = int(dur * RATE)
        ph = 0.0
        for i in range(n):
            env = math.sin(math.pi * i / n) ** 0.6
            f = f0 * (1 + 0.04 * math.sin(2 * math.pi * 5 * i / RATE))
            ph += 2 * math.pi * f / RATE
            v = (math.sin(ph) + 0.5 * math.sin(2 * ph) +
                 0.25 * math.sin(3 * ph))
            if rough:
                v += rough * d.uniform(-1, 1) * 0.6
            out.append(loud * env * v / 1.75)
        out.extend([0.0] * int(0.04 * RATE))
    return out


def pool(level: Grade) -> List[Heard]:
    got = [Heard(v.name, v.emotion, 0) for v in D.voices()
           if v.agreement >= level.agree]
    if len({h.emotion for h in got}) >= len(EMOTIONS):
        return got
    return [Heard('', e, s) for e in range(len(EMOTIONS)) for s in range(40)]


def length(h: Heard, cut: float) -> float:
    return len(_samples(h, cut)) / float(RATE)


# --- the round ---------------------------------------------------------------------

def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    voices = pool(level)
    allowed = [e for e in range(len(EMOTIONS))
               if level.plain or e != NEUTRAL]
    by = {e: [h for h in voices if h.emotion == e] for e in allowed}
    if any(not v for v in by.values()):
        return None
    order = [allowed[k % len(allowed)] for k in range(level.items)]
    draw.shuffle(order)
    items = []
    for e in order:
        h = draw.choice(by[e])
        others = [o for o in allowed if o != e]
        shown = sorted([e] + draw.sample(others, level.choices - 1))
        draw.shuffle(shown)
        st = F.Step(_('How does the speaker feel?'),
                    tuple(SAID[EMOTIONS[o]] for o in shown), shown.index(e))
        sentence = D.SENTENCES.get(h.clip.split('_')[1], '') if h.clip \
            else ''
        heard = LEAD + 2 * length(h, level.cut) + GAP
        items.append(F.Item(
            '“%s”' % sentence if sentence else _('(a hum)'),
            (st,), heard + level.answer, face=h, truth=SAID[EMOTIONS[e]],
            title=_('Listen')))
    need = max(F.need_for(level.items, 1.0 / level.choices,
                          0.01 if level.choices == 2 else 0.03),
               int(math.ceil(level.skill * level.items)))
    from .quiz import fixed_pass
    if fixed_pass(items, need):
        return None
    return F.Round(level, tuple(items), need)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)


class Run(F.Run):
    """A round that remembers when each item began, to play its voice."""

    def __init__(self, rnd: F.Round) -> None:
        super().__init__(rnd)
        self.starts: List[float] = [0.0]

    def step(self, dt: float, control=None) -> None:
        k = self.k
        super().step(dt, control)
        if self.k != k and self.k < len(self.round.items):
            self.starts.append(self.since)


def play(rnd: F.Round, pilot=autopilot, dt: float = 1 / 30.0):
    return H.play(Run(rnd), pilot, EVENTS, act, dt)


def _hiss(seed: int, n: int) -> List[float]:
    d = random.Random(seed)
    return [d.uniform(-1, 1) for _i in range(n)]


def mix(run: Run, t0: float, t1: float) -> bytes:
    """What was heard from *t0* to *t1*: each item's voice twice, the
    hiss behind it, and the notes; stereo 16-bit PCM at :data:`RATE`."""
    frames = max(0, int(round((t1 - t0) * RATE)))
    if frames == 0:
        return b''
    out = [0.0] * frames
    level = run.level
    for k, start in enumerate(run.starts):
        h = run.round.items[k].face
        src = _samples(h, level.cut)
        n = len(src)
        for at in (start + LEAD, start + LEAD + n / float(RATE) + GAP):
            a = int(round((at - t0) * RATE))
            lo, hi = max(0, a), min(frames, a + n)
            for i in range(lo, hi):
                out[i] += src[i - a]
            if level.hiss > 0 and hi > lo:
                noise = _hiss(k + 7 * len(run.starts), n)
                for i in range(lo, hi):
                    out[i] += level.hiss * noise[i - a]
    pcm = array('h', synth.synth(run.notes, t0, t1, [
        synth.make_patch(p, random.Random(j + 1))
        for j, p in enumerate(PATCHES)]))
    for i, v in enumerate(out):
        s = int((1.0 if v > 1.0 else -1.0 if v < -1.0 else v) * 30000)
        for c in (2 * i, 2 * i + 1):
            if c < len(pcm):
                pcm[c] = max(-32767, min(32767, pcm[c] + s))
    return pcm.tobytes()
