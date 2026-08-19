# -*- coding: utf-8 -*-
"""The stepped agent environment.

One trial is one action window. The window opens when a stimulus frame
is published and closes when the phase leaves ``stimulus``; exactly one
action may be finalized inside it, and that action gets a receipt. When
the feedback frame is published, its pixels are turned into a public
outcome bound to that receipt and to every frame of the trial.

Everything the learner receives is pixels, audio samples, and that
outcome. No cell ids, modality names, phase names or scores.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
from typing import (Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple,
                    Union)

import pyglet

import brainworkshop as bw
import bwaccel

from .accounting import Accounting
from .export import FrameExport
from .frames import digest_rgba, now_ns, render_significant_frame
from .outcome import PUBLIC_OUTCOME_KEYS, derive_public_outcome

Ports = Union[None, int, Mapping[int, bool], Iterable[int]]


class NeuralWorkshopEnv:
    """Deterministic, stepped view of one Neural Workshop session.

    Constructor arguments own the gym knobs; a learner must not reach
    into ``bw.cfg`` itself. They survive :meth:`reset`.
    """

    def __init__(self, seed: Optional[int] = None,
                 shm_name: Optional[str] = None, diagnostics: bool = False,
                 game_mode: Optional[int] = None,
                 num_trials: Optional[int] = None,
                 n_back: Optional[int] = None,
                 grid_size: Optional[int] = None,
                 active_cells: Optional[int] = None,
                 mute_music: bool = True, mute_applause: bool = True,
                 visible: bool = False) -> None:
        if diagnostics and os.environ.get('NW_DIAGNOSTICS') != '1':
            raise RuntimeError(
                'diagnostic construction rejected (set NW_DIAGNOSTICS=1)')

        self._game_mode = game_mode
        self._num_trials = num_trials
        self._n_back = n_back
        self._grid_size = grid_size
        self._active_cells = active_cells
        self._mute_music = bool(mute_music)
        self._mute_applause = bool(mute_applause)
        self._visible = bool(visible)

        # Drive the clock ourselves; nothing may advance behind our back.
        bw.mode.step_mode = True
        try:
            pyglet.clock.unschedule(bw.update)
        except Exception:
            pass
        self._set_window_visible()
        bw.cfg.SHOW_FEEDBACK = True
        bw.cfg.ANIMATE_SQUARES = False

        self._export = FrameExport(
            shm_name=shm_name or os.environ.get('NW_SHM'))
        self.accounting = Accounting()

        # Frame state.
        self._seq = 0
        self._timestamp_ns = 0
        self._width = 0
        self._height = 0
        self._rgba = b''
        self._digest = ''
        self._pending = False
        self._consumed = True
        self._phase: Optional[str] = None  # private; never published
        self._public_audio: Optional[Dict[str, Any]] = None

        # Trial state.
        self._trial_digests: List[str] = []
        self._trial_receipt: Optional[Dict[str, Any]] = None
        self._response_open = False
        self._receipt_seq = 0
        self._action_finalized = False
        self._receipt_ledger: Dict[int, Dict[str, Any]] = {}
        self._archive: Dict[str, bytes] = {}
        self._events: List[Dict[str, Any]] = []
        self._delivered: Set[Any] = set()
        self._cached_outcome: Optional[Dict[str, Any]] = None

        self._closed = False
        self.reset(0 if seed is None else seed)

    # --- public API -------------------------------------------------------

    @property
    def n_actions(self) -> int:
        """How many opaque action ports this mode offers."""
        return len(bw.action_button_names())

    def reset(self, seed: int = 0) -> Dict[str, Any]:
        """Start a fresh session under *seed* and return the first frame."""
        seed = int(seed)
        self._seed_everything(seed)

        if bw.mode.started:
            bw.end_session(cancelled=True)
        bw.mode.step_mode = True
        bw.mode.session_done = False
        bw.mode.phase = None
        bw.mode.session_number = 0
        bw.mode.progress = 0
        bw.mode.hide_text = False
        bw.cfg.SHOW_FEEDBACK = True
        bw.cfg.ANIMATE_SQUARES = False
        self._set_window_visible()

        self._apply_session_config()
        bw.new_session()
        # new_session() re-derives some of this, so pin it again.
        bw.mode.step_mode = True
        bw.mode.tick = 0
        bw.mode.phase = None
        bw.mode.session_number = 1
        self._apply_session_config()
        self._seed_everything(seed)

        self._clear_run_state()
        phase = bw.trial_advance_significant()
        self._publish(phase)
        if phase == 'stimulus':
            self._open_trial_window()
            self.accounting.logical_trials = 1
        return self.observe()

    def observe(self) -> Dict[str, Any]:
        """The current frame.

        The framebuffer may be re-read as often as wanted; the outcome
        is drain-once and disappears after the first observation.
        """
        obs = self._observation()
        self._cached_outcome = None
        self._consumed = True
        self._pending = False
        self._export.write(self._seq, self._timestamp_ns, self._width,
                           self._height, self._rgba, True)
        return obs

    def act(self, ports: Ports = None,
            logp: Optional[float] = None) -> Dict[str, Any]:
        """Finalize this trial's action. At most one per trial.

        *logp* is an optional policy log-propensity stored on the
        receipt so a runtime can map it back to this trial; it is not
        interpreted here. Returns a receipt, or a rejection when the
        window is closed or an action was already taken.
        """
        rejected = {
            'ok': False, 'receipt_id': None, 'frame_seq': self._seq,
            'timestamp_ns': now_ns(), 'ports': (), 'logp': None,
        }
        if not self._response_open or self._trial_receipt is None:
            return rejected
        if self._action_finalized:
            return rejected

        indices = self._decode_ports(ports)
        names = bw.action_button_names()
        bw.inject_match_action([names[i] for i in indices
                                if 0 <= i < len(names)])
        self._action_finalized = True

        held = self._trial_receipt
        self._trial_receipt = {
            'ok': True,
            'receipt_id': held['receipt_id'],
            'trial_seq': held.get('trial_seq', held['receipt_id']),
            'frame_seq': held['frame_seq'],
            'timestamp_ns': now_ns(),
            'ports': tuple(indices),
            'logp': logp,
            'stimulus_digest': held.get('stimulus_digest'),
            'window_open_ns': held.get('window_open_ns'),
        }
        self._receipt_ledger[self._trial_receipt['receipt_id']] = dict(
            self._trial_receipt)
        return dict(self._trial_receipt)

    def advance(self) -> Dict[str, Any]:
        """Run the game until the next significant frame, and return it."""
        if self._pending and not self._consumed:
            self.accounting.duplicate_frames += 1
            return self.observe()
        if bw.mode.session_done or bw.mode.phase == 'done':
            if self._phase != 'done':
                self._publish('done')
            return self.observe()

        previous = bw.mode.phase
        phase = bw.trial_advance_significant()
        if previous == 'stimulus' and phase != 'stimulus':
            self._response_open = False
        if phase == 'stimulus':
            self._trial_digests = []
            self.accounting.logical_trials += 1
        self._publish(phase)
        if phase == 'stimulus':
            self._open_trial_window()
        return self.observe()

    def step(self, ports: Ports = None
             ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
        """Act (if given ports), advance, and drain the pending events."""
        if ports is not None:
            self.act(ports)
        obs = self.advance()
        events = list(self._events)
        self._events = []
        return obs, events, bool(obs.get('done'))

    def close(self) -> None:
        """Cancel any running session and release the export block."""
        if self._closed:
            return
        self._closed = True
        if bw.mode.started:
            try:
                bw.end_session(cancelled=True)
            except Exception:
                pass
        self._export.close()

    # --- setup ------------------------------------------------------------

    @staticmethod
    def _seed_everything(seed: int) -> None:
        random.seed(seed)
        bwaccel.seed(seed)

    def _set_window_visible(self) -> None:
        try:
            bw.window.set_visible(self._visible)
        except Exception:
            pass

    def _clear_run_state(self) -> None:
        self.accounting.reset()
        self._events = []
        self._trial_digests = []
        self._trial_receipt = None
        self._response_open = False
        self._receipt_seq = 0
        self._pending = False
        self._consumed = True
        self._archive = {}
        self._action_finalized = False
        self._delivered = set()
        self._cached_outcome = None
        self._receipt_ledger = {}

    def _apply_session_config(self) -> None:
        """Push the constructor's gym knobs into the game's config."""
        if self._grid_size is not None:
            size = int(self._grid_size)
            if size < 1:
                raise ValueError('grid_size must be positive')
            bw.cfg.GRID_SIZE = size
        if self._active_cells is not None:
            cells = int(self._active_cells)
            if cells < 0:
                raise ValueError('active_cells cannot be negative')
            bw.cfg.ACTIVE_POSITION_CELLS = cells
            bw.cfg.POSITION_CELL_COUNT = cells
        if self._mute_music:
            bw.cfg.USE_MUSIC = False
        if self._mute_applause:
            bw.cfg.USE_APPLAUSE = False

        # Manual mode: the curriculum must not move the level under us.
        bw.cfg.MANUAL = True
        bw.mode.manual = True

        if self._game_mode is not None:
            bw.mode.mode = int(self._game_mode)
            bw.cfg.GAME_MODE = int(self._game_mode)
        if self._n_back is not None:
            depth = int(self._n_back)
            if depth < 1:
                raise ValueError('n_back must be positive')
            bw.mode.back = depth
        if self._num_trials is not None:
            count = int(self._num_trials)
            if count < 1:
                raise ValueError('num_trials must be positive')
            bw.mode.num_trials = count
            bw.mode.num_trials_factor = 0
            bw.mode.num_trials_total = count

    # --- trials -----------------------------------------------------------

    def _open_trial_window(self) -> None:
        """Open the action window and pre-register its receipt."""
        self._response_open = True
        self._action_finalized = False
        self._receipt_seq += 1
        now = now_ns()
        self._trial_receipt = {
            'ok': True,
            'receipt_id': self._receipt_seq,
            'trial_seq': self._receipt_seq,
            'frame_seq': self._seq,
            'timestamp_ns': now,
            'ports': (),
            'logp': None,
            'stimulus_digest': self._digest,
            'window_open_ns': now,
        }
        self._receipt_ledger[self._receipt_seq] = dict(self._trial_receipt)

    def _decode_ports(self, ports: Ports) -> List[int]:
        """Normalise an action to a list of valid integer port indices."""
        n = self.n_actions
        if ports is None:
            return []
        if isinstance(ports, int):
            return [ports] if 0 <= ports < n else []
        if isinstance(ports, dict):
            # Semantic names are refused; only integer keys are ports.
            return [k for k, v in ports.items()
                    if v and isinstance(k, int) and 0 <= k < n]
        return [p for p in ports if isinstance(p, int) and 0 <= p < n]

    # --- frames -----------------------------------------------------------

    def _observation(self) -> Dict[str, Any]:
        obs: Dict[str, Any] = {
            'frame_seq': self._seq,
            'timestamp_ns': self._timestamp_ns,
            'width': self._width,
            'height': self._height,
            'rgba': self._rgba,
            'done': self._phase == 'done',
        }
        if self._cached_outcome is not None:
            obs['outcome'] = self._cached_outcome
        if self._public_audio is not None:
            obs.update(self._public_audio)
        return obs

    def _snapshot_public_audio(self) -> None:
        """Publish the last queued waveform — samples, never a letter id."""
        captures = getattr(bw, 'audio_capture', None)
        if not captures:
            self._public_audio = None
            return
        record = captures[-1]
        pcm = record.get('pcm') or b''
        if not pcm:
            self._public_audio = None
            return
        fmt = record.get('audio_format')
        bits = int(getattr(fmt, 'sample_size', 16) or 16)
        self._public_audio = {
            'audio_pcm': pcm,
            'audio_rate': int(getattr(fmt, 'sample_rate', 0) or 0),
            'audio_channels': int(getattr(fmt, 'channels', 0) or 1),
            'audio_sample_width': max(bits // 8, 1),
        }

    def _emit_once(self, key: Any, event: Dict[str, Any]) -> bool:
        """Queue *event* unless something with this key already went out."""
        if key in self._delivered:
            return False
        self._delivered.add(key)
        self._events.append(event)
        return True

    def _bind_receipt_to_trial(self, receipt_id: Optional[int]) -> None:
        """Record which frames the trial's receipt is answerable for."""
        if receipt_id is None or receipt_id not in self._receipt_ledger:
            return
        bound = self._receipt_ledger[receipt_id]
        bound['evidence_digests'] = list(self._trial_digests)
        bound['feedback_digest'] = self._digest
        bound['feedback_frame_seq'] = self._seq

    def _publish_outcome(self, rgba: bytes, width: int, height: int) -> None:
        """Derive and emit the public outcome for the finished trial."""
        receipt_id = (self._trial_receipt or {}).get('receipt_id')
        self._bind_receipt_to_trial(receipt_id)

        key = ('outcome', receipt_id)
        if key in self._delivered:
            return
        outcome = derive_public_outcome(
            rgba, width, height, self._trial_digests, receipt_id,
            frame_seq=self._seq, timestamp_ns=self._timestamp_ns)
        if outcome is None:
            # No feedback labels on screen: nothing to answer for.
            self._delivered.add(key)
            return

        public = {k: outcome[k] for k in PUBLIC_OUTCOME_KEYS if k in outcome}
        self._cached_outcome = public
        self.accounting.authenticated_outcomes.add((
            public['receipt_id'], tuple(public['evidence_digests']),
            public['scalar']))
        emitted = self._emit_once(key, {
            'type': 'outcome',
            'scalar': public['scalar'],
            'evidence_digests': public['evidence_digests'],
            'receipt_id': public['receipt_id'],
            'frame_seq': public['frame_seq'],
            'timestamp_ns': public['timestamp_ns'],
        })
        if emitted and self._trial_receipt:
            self.accounting.action_to_outcome_ns.append(
                self._timestamp_ns - self._trial_receipt['timestamp_ns'])

    def _publish(self, phase: Optional[str]) -> None:
        """Render one significant frame and everything that follows from it."""
        if self._pending and not self._consumed:
            self.accounting.dropped_frames += 1

        width, height, rgba = render_significant_frame()
        self._seq += 1
        self._timestamp_ns = now_ns()
        self._width = width
        self._height = height
        self._rgba = rgba
        self._digest = digest_rgba(rgba)
        self._archive[self._digest] = bytes(rgba)
        self._phase = phase
        self._pending = True
        self._consumed = False
        self._trial_digests.append(self._digest)
        self.accounting.significant_frames += 1
        self._export.write(self._seq, self._timestamp_ns, width, height,
                           rgba, False)
        self._cached_outcome = None

        if phase == 'stimulus':
            self._snapshot_public_audio()
        else:
            self._public_audio = None
        if phase == 'feedback':
            self._publish_outcome(rgba, width, height)
        if phase == 'done':
            self._emit_once(('session_end',), {
                'type': 'session_end',
                'frame_seq': self._seq,
                'timestamp_ns': self._timestamp_ns,
            })


def make_env(seed: int = 0,
             shm_name: Optional[str] = None) -> NeuralWorkshopEnv:
    """A production environment: no probe, no diagnostics."""
    return NeuralWorkshopEnv(seed=seed, shm_name=shm_name)
