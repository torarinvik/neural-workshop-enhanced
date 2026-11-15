# -*- coding: utf-8 -*-
"""Sound for clocked tasks: a trial's notes, played and published.

A task that sounds deals its notes (Dr Shape's :class:`Note`, voiced by
its :class:`Patch` instruments) along with the trial and hands them to
:meth:`Tones._tones_start`. They are synthesised as they play -- through
the speakers when there are speakers, and to the agent boundary,
whatever has sounded since the last frame, through
:meth:`Tones.audio_window`.

A task whose sound answers what the player does -- an echo, a radio
dial -- hands over a list its model keeps appending to instead, through
:meth:`Tones._tones_live`. Notes join it at the model's own time, never
earlier than the last one, and the speakers play it a fixed
:data:`LAG` behind the run, so a note is never asked for before it is
made. The agent hears it exactly on time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional, Sequence

import pyglet

from .. import drshape as synth
from .. import runtime


#: Seconds the speakers trail a live run by.
LAG = 0.15
#: Longest a note rings past its end (release and echoes), for skipping.
RING = 4.0


def _live(notes: Sequence[synth.Note], t0: float, start: int) -> int:
    """Skip, from *start*, the notes that are over by *t0*; stop at the
    first that may still sound."""
    while start < len(notes) and \
            notes[start].t + notes[start].dur + RING < t0:
        start += 1
    return start


class Voice(pyglet.media.Source):
    """Notes synthesised as they are played."""

    def __init__(self, notes: Sequence[synth.Note],
                 patches: Sequence[synth.Patch], duration: float,
                 lag: float = 0.0, live: bool = False) -> None:
        from pyglet.media.codecs.base import AudioFormat
        self.audio_format = AudioFormat(channels=2, sample_size=16,
                                        sample_rate=synth.RATE)
        self.video_format = None
        self._notes = notes if live else list(notes)
        self._patches = list(patches)
        self._duration = duration
        self._lag = lag
        self._first = 0
        self._t = 0.0

    def get_audio_data(self, num_bytes: int, compensation_time: float = 0.0):
        from pyglet.media.codecs.base import AudioData
        if self._t >= self._duration:
            return None
        t1 = min(self._duration, self._t + max(1, num_bytes // 4)
                 / float(synth.RATE))
        a, b = self._t - self._lag, t1 - self._lag
        self._first = _live(self._notes, a, self._first)
        data = synth.synth(self._notes[self._first:], a, b, self._patches)
        t0, self._t = self._t, t1
        return AudioData(data, len(data), t0, t1 - t0, [])

    def seek(self, timestamp: float) -> None:
        self._t = max(0.0, min(self._duration, timestamp))

    def is_precise(self) -> bool:
        return True


class Tones:
    """Mix in before ClockedTask: a trial's notes on ``self.run.t``."""

    tone_notes: Sequence[synth.Note] = ()
    tone_patches: Sequence[synth.Patch] = ()
    tone_player = None
    heard_to = 0.0
    tone_first = 0

    def _tones_start(self, notes, patches, duration: float) -> None:
        self._tones_stop()
        self.tone_notes = list(notes)
        self.tone_patches = list(patches)
        self.heard_to = 0.0
        self.tone_first = 0
        if runtime.HEADLESS or not self.tone_notes:
            return
        self._tones_play(Voice(self.tone_notes, self.tone_patches, duration))

    def _tones_live(self, notes, patches, duration: float) -> None:
        """Play *notes*, a list the run goes on appending to."""
        self._tones_stop()
        self.tone_notes = notes
        self.tone_patches = list(patches)
        self.heard_to = 0.0
        self.tone_first = 0
        if runtime.HEADLESS:
            return
        self._tones_play(Voice(notes, self.tone_patches, duration + LAG,
                               lag=LAG, live=True))

    def _tones_play(self, voice: Voice) -> None:
        try:
            player = pyglet.media.Player()
            player.queue(voice)
            player.play()
            self.tone_player = player
        except Exception as exc:              # no audio device: silent
            runtime.debug_msg(exc)
            self.tone_player = None

    def _tones_stop(self) -> None:
        if self.tone_player is not None:
            try:
                self.tone_player.pause()
                self.tone_player.delete()
            except Exception:
                pass
        self.tone_player = None

    def _judge(self, passed: bool, message: str) -> None:
        self._tones_stop()
        super()._judge(passed, message)

    def _clear_trial(self) -> None:
        self._tones_stop()
        self.tone_notes = ()
        super()._clear_trial()

    def audio_window(self) -> Optional[dict]:
        """The sound made since the last call, for the agent boundary."""
        run = getattr(self, 'run', None)
        if run is None or not self.tone_notes or run.t <= self.heard_to:
            return None
        t0, self.heard_to = self.heard_to, run.t
        self.tone_first = _live(self.tone_notes, t0, self.tone_first)
        return {'pcm': synth.synth(self.tone_notes[self.tone_first:], t0,
                                   run.t, self.tone_patches),
                'rate': synth.RATE, 'channels': 2}


def note(t: float, dur: float, freq: float, pan: float = 0.0,
         gain: float = 0.8, voice: int = 0, seed: int = 0,
         bright: float = 0.8, room: float = 0.0) -> synth.Note:
    """One plain note, standing still between the ears."""
    return synth.Note(t, dur, freq, pan, pan, gain, gain, bright, voice,
                      seed, -1, room)


def patch(name: str, seed: int = 1) -> synth.Patch:
    import random
    return synth.make_patch(name, random.Random(seed))
