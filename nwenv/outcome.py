# -*- coding: utf-8 -*-
"""The public outcome: what a learner is allowed to know about a trial.

The outcome is derived from pixels alone — the count of green versus
red/blue feedback *labels* in the bottom band of the frame — never from
game state. Counting labels rather than coloured pixels makes the value
invariant to caption wording, font and window size.

An outcome carries the digests of the frames it was derived from and the
id of the receipt for the action that produced it, so a third party can
re-derive it. :func:`verify_public_outcome` is the learner-facing check
and fails closed: an outcome naming a receipt is only accepted when both
the frame archive and the receipt ledger are supplied, and when the
receipt really is bound to this trial's evidence.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import bwaccel

from .frames import digest_rgba

#: The only keys a learner-facing outcome may contain.
PUBLIC_OUTCOME_KEYS: Tuple[str, ...] = (
    'scalar', 'evidence_digests', 'receipt_id', 'frame_seq', 'timestamp_ns',
)

#: Feedback colours the game actually paints, for reference.
FEEDBACK_POSITIVE = (64, 255, 64)   # correct
FEEDBACK_NEGATIVE = (255, 64, 64)   # incorrect
FEEDBACK_OOPS = (64, 64, 255)       # missed or too early


def _label_run_scalar(rgba: bytes, width: int, height: int
                      ) -> Tuple[int, int, Optional[float]]:
    """``(n_pos, n_neg, scalar)``, or ``(0, 0, None)`` if no labels."""
    if not rgba or width < 1 or height < 1:
        return 0, 0, None
    y0 = int(height * 0.75)
    n_pos, n_neg, n_oops = bwaccel.count_feedback_label_runs(
        rgba, width, height, y0, height)
    n_bad = n_neg + n_oops
    total = n_pos + n_bad
    if total == 0:
        return 0, 0, None
    return int(n_pos), int(n_bad), (n_pos - n_bad) / float(total)


def derive_public_outcome(rgba: bytes, width: int, height: int,
                          evidence_digests: Sequence[str],
                          receipt_id: Optional[int],
                          frame_seq: Optional[int] = None,
                          timestamp_ns: Optional[int] = None
                          ) -> Optional[Dict[str, Any]]:
    """The scalar for one trial, derived from feedback labels.

    Green counts +1, red and blue -1, and the scalar is
    ``(n_pos - n_neg) / (n_pos + n_neg)``. No labels yields ``None``,
    which is not the same as zero. The returned payload carries no label
    counts — that would leak more than the scalar.
    """
    _n_pos, _n_neg, scalar = _label_run_scalar(rgba, width, height)
    if scalar is None:
        return None
    outcome: Dict[str, Any] = {
        'scalar': scalar,
        'evidence_digests': list(evidence_digests),
        'receipt_id': receipt_id,
    }
    if frame_seq is not None:
        outcome['frame_seq'] = frame_seq
    if timestamp_ns is not None:
        outcome['timestamp_ns'] = timestamp_ns
    return outcome


def diagnose_public_outcome(rgba: bytes, width: int, height: int,
                            evidence_digests: Sequence[str],
                            receipt_id: Optional[int]
                            ) -> Optional[Dict[str, Any]]:
    """Diagnostics only: the public outcome plus the private label counts."""
    n_pos, n_neg, scalar = _label_run_scalar(rgba, width, height)
    if scalar is None:
        return None
    outcome = derive_public_outcome(rgba, width, height, evidence_digests,
                                    receipt_id)
    outcome['n_pos'] = n_pos
    outcome['n_neg'] = n_neg
    return outcome


def _receipt_bound_to_evidence(rec: Optional[Mapping[str, Any]],
                               evidence: Sequence[str]) -> bool:
    """True only if this ledger receipt owns this evidence sequence."""
    if not rec or not evidence:
        return False
    stimulus = rec.get('stimulus_digest')
    if not stimulus or stimulus != evidence[0]:
        return False
    bound = rec.get('evidence_digests')
    if bound is not None and list(bound) != list(evidence):
        return False
    feedback = rec.get('feedback_digest')
    if feedback is not None and feedback != evidence[-1]:
        return False
    trial_seq = rec.get('trial_seq')
    if trial_seq is not None and rec.get('receipt_id') not in (None, trial_seq):
        return False
    return True


def _pixels_match_outcome(outcome: Optional[Mapping[str, Any]], rgba: bytes,
                          width: int, height: int,
                          archive: Optional[Mapping[str, bytes]] = None
                          ) -> bool:
    """Re-derive the scalar from pixels. No receipt binding is checked."""
    if not outcome:
        return False
    if any(k not in PUBLIC_OUTCOME_KEYS for k in outcome):
        return False

    evidence = list(outcome.get('evidence_digests') or [])
    if not evidence:
        return False
    if evidence[-1] != digest_rgba(rgba):
        return False
    # Earlier frames can only be checked against an archive.
    if len(evidence) > 1 and archive is None:
        return False
    if archive is not None:
        for digest in evidence:
            stored = archive.get(digest)
            if stored is None or digest_rgba(stored) != digest:
                return False

    recomputed = derive_public_outcome(rgba, width, height, evidence,
                                       outcome.get('receipt_id'))
    if recomputed is None:
        return False
    return recomputed['scalar'] == outcome.get('scalar')


def verify_public_pixels(outcome: Optional[Mapping[str, Any]], rgba: bytes,
                         width: int, height: int,
                         archive: Optional[Mapping[str, bytes]] = None
                         ) -> bool:
    """Diagnostic pixel-only check. Not the learner-facing verifier."""
    return _pixels_match_outcome(outcome, rgba, width, height, archive)


def verify_public_outcome(outcome: Optional[Mapping[str, Any]], rgba: bytes,
                          width: int, height: int,
                          archive: Optional[Mapping[str, bytes]] = None,
                          receipt_ledger: Optional[Mapping[int, Any]] = None
                          ) -> bool:
    """Learner-facing verifier: archive, receipt binding and pixel scalar.

    An outcome that names a receipt fails closed unless both *archive*
    and *receipt_ledger* are supplied. The receipt must exist and be
    bound to this stimulus digest, trial sequence, action window and
    evidence list; a valid receipt from a different trial is rejected.
    """
    if not outcome:
        return False
    if outcome.get('receipt_id') is not None:
        if archive is None or receipt_ledger is None:
            return False
        evidence = list(outcome.get('evidence_digests') or [])
        rec = receipt_ledger.get(outcome.get('receipt_id'))
        if rec is None or not _receipt_bound_to_evidence(rec, evidence):
            return False
    return _pixels_match_outcome(outcome, rgba, width, height, archive)
