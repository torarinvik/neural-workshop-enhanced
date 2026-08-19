# -*- coding: utf-8 -*-
"""Deterministic agent boundary for Neural Workshop.

Public contract (learner-facing)
--------------------------------
=================  =========================================
``reset(seed)``    observation
``observe()``      observation
``act(ports)``     receipt, or a rejection
``advance()``      observation
``step(ports)``    (observation, events, done)
=================  =========================================

Constructor-owned gym knobs (do not poke ``bw.cfg`` from a learner):
``game_mode``, ``num_trials``, ``n_back``, ``grid_size``,
``active_cells``, ``mute_music``, ``mute_applause``, ``visible``. These
survive ``reset``.

Observation fields: ``frame_seq``, ``timestamp_ns``, ``width``,
``height``, ``rgba``, ``done``; optional public audio (``audio_pcm``,
``audio_rate``, ``audio_channels``, ``audio_sample_width``) when a
stimulus sound was queued; and an optional drain-once ``outcome``
(``scalar``, ``evidence_digests``, ``receipt_id``, ``frame_seq``,
``timestamp_ns``).

The audio is the played waveform, not a letter id. There are no cell
ids, modality names, phase names, scores or sequences. Actions are
opaque integer port indices.

The shared-memory export (``NW_SHM``) is a one-way framebuffer dump, not
a cross-process control protocol: no seqlock, no action channel, no
reset or config path, no ownership handshake.

``verify_public_outcome`` is the learner-facing verifier. An outcome
carrying a receipt id requires both the immutable frame archive and the
receipt ledger; omitting either fails closed. ``verify_public_pixels``
is a diagnostic pixel-only check and must not be used as the public
verifier.

Parity tests compare the step driver against the scheduled ``update()``
clock with the window hidden, so they prove stepped-versus-scheduled
parity rather than literal visible-window execution.

Modules
-------
``frames``       capturing and digesting the screen
``outcome``      deriving and verifying the public outcome
``export``       the optional shared-memory framebuffer dump
``accounting``   per-run counters
``env``          the environment itself
``diagnostics``  the privileged probe, for tests only

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys

# pyglet has to be configured before brainworkshop imports it.
os.environ.setdefault('NW_HEADLESS', '1')
_HEADLESS = os.environ.get('NW_HEADLESS', '1').lower() in (
    '1', 'true', 'yes', 'on')

import pyglet  # noqa: E402

if _HEADLESS:
    # Headless training uses the silent driver, so OpenAL never starts.
    # A visible gym session (NW_HEADLESS=0) keeps the normal audio path.
    pyglet.options['audio'] = ('silent',)
    if sys.platform.startswith('linux'):
        try:
            pyglet.options['headless'] = True
        except Exception:
            pass

from .accounting import Accounting, format_accounting  # noqa: E402
from .diagnostics import DiagnosticEnv, TestProbe  # noqa: E402
from .env import NeuralWorkshopEnv, make_env  # noqa: E402
from .export import FrameExport  # noqa: E402
from .frames import capture_rgba, digest_rgba, render_significant_frame  # noqa: E402
from .outcome import (derive_public_outcome, diagnose_public_outcome,  # noqa: E402
                      verify_public_outcome, verify_public_pixels)

__all__ = [
    'Accounting', 'DiagnosticEnv', 'FrameExport', 'NeuralWorkshopEnv',
    'TestProbe', 'capture_rgba', 'derive_public_outcome',
    'diagnose_public_outcome', 'digest_rgba', 'format_accounting',
    'make_env', 'render_significant_frame', 'verify_public_outcome',
    'verify_public_pixels',
]
