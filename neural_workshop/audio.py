# -*- coding: utf-8 -*-
"""Sound playback, and the capture player that replaces it when headless.

In a headless run no OpenAL source is ever opened. Queued sources are
decoded to raw PCM and appended to :data:`audio_capture` instead, which
is what the agent environment hands to a learner as the public audio
observation.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence, Union

import pyglet

from . import runtime, state
from .config import get_threshold_advance, get_threshold_fallback
from .constants import PREVENT_MUSIC_SKIPPING

#: Every PCM buffer queued since start-up, oldest first.
audio_capture: List[Dict[str, Any]] = []


def _capture_source_pcm(source: Any) -> Dict[str, Any]:
    """Decode *source* to raw PCM without touching an audio device."""
    record: Dict[str, Any] = {
        'duration': getattr(source, 'duration', None),
        'audio_format': getattr(source, 'audio_format', None),
        'pcm': b'',
    }
    data = getattr(source, '_data', None)
    if isinstance(data, (bytes, bytearray, memoryview)):
        record['pcm'] = bytes(data)
        return record

    getter = getattr(source, 'get_queue_source', None)
    queue_source = getter() if callable(getter) else source
    pull = getattr(queue_source, 'get_audio_data', None)
    if not callable(pull):
        return record

    chunks: List[bytes] = []
    try:
        while True:
            packet = pull(65536)
            if packet is None:
                break
            chunk = getattr(packet, 'data', None)
            if chunk:
                chunks.append(bytes(chunk))
    except Exception:
        pass
    record['pcm'] = b''.join(chunks)
    return record


class CapturePlayer:
    """Headless stand-in for ``pyglet.media.Player``: records, never plays."""

    def __init__(self) -> None:
        self.volume: float = 0.0
        self.min_distance: float = 1.0
        self.position: Sequence[float] = (0.0, 0.0, 0.0)
        self.playing: bool = False
        self._queue: List[Dict[str, Any]] = []

    def queue(self, source: Any) -> None:
        record = _capture_source_pcm(source)
        self._queue.append(record)
        audio_capture.append(record)

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def next_source(self) -> None:
        if self._queue:
            self._queue.pop(0)


Player = Union[CapturePlayer, 'pyglet.media.Player']


def get_pyglet_media_player() -> Player:
    """A player suitable for this run: capturing when headless."""
    if runtime.HEADLESS:
        return CapturePlayer()
    try:
        return pyglet.media.Player()
    except Exception as exc:
        runtime.debug_msg(exc)
        return pyglet.media.ManagedSoundPlayer()


#: Stimulus players. Two, so dual-audio modes can overlap.
player: Optional[Player] = None
player2: Optional[Player] = None

#: Reward players.
applause_player: Optional[Player] = None
music_player: Optional[Player] = None


def build_players() -> None:
    """Create the four long-lived players. Called once at start-up."""
    global player, player2, applause_player, music_player
    player = get_pyglet_media_player()
    player2 = get_pyglet_media_player()
    applause_player = get_pyglet_media_player()
    music_player = get_pyglet_media_player()


def play_applause() -> None:
    """Reward the player for finishing a session."""
    from . import resources
    if not resources.applause_sounds:
        return
    applause_player.queue(random.choice(resources.applause_sounds))
    applause_player.volume = state.cfg.SFX_VOLUME
    if runtime.DEBUG:
        print('Playing applause')
    applause_player.play()


def _music_folder_for(percent: float, folders: Dict[str, Any]) -> Optional[str]:
    """Which music folder a score of *percent* has earned."""
    advance = get_threshold_advance()
    fallback = get_threshold_fallback()
    if percent >= advance and 'advance' in folders:
        return 'advance'
    if percent >= (advance + fallback) // 2 and 'great' in folders:
        return 'great'
    if percent >= fallback and 'good' in folders:
        return 'good'
    return None


def play_music(percent: float) -> None:
    """Play the track this session's score has earned, if any."""
    from . import resources
    folders = resources.resourcepaths.get('music')
    if not folders:
        return
    if PREVENT_MUSIC_SKIPPING:
        pyglet.clock.tick(poll=True)
    folder = _music_folder_for(percent, folders)
    if folder is None:
        return
    music_player.queue(pyglet.media.load(
        random.choice(folders[folder]), streaming=True))
    music_player.volume = state.cfg.MUSIC_VOLUME
    if runtime.DEBUG:
        print('Playing music')
    music_player.play()


def sound_stop() -> None:
    """Silence the reward players immediately."""
    music_player.volume = 0
    applause_player.volume = 0


def _step_fade(volume: float) -> float:
    """One fade step: coarse at first, then fine, then silent."""
    if volume <= 0:
        return 0.0
    volume -= 0.02 if volume <= 0.1 else 0.1
    return 0.0 if volume <= 0.02 else volume


def fade_out(dt: float) -> None:
    """Scheduled fade of the reward players at the start of a session."""
    music_player.volume = _step_fade(music_player.volume)
    applause_player.volume = _step_fade(applause_player.volume)
    if (applause_player.volume == 0 and music_player.volume == 0) \
            or state.mode.trial_number == 3:
        pyglet.clock.unschedule(fade_out)
