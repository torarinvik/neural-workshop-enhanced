# -*- coding: utf-8 -*-
"""What :func:`nwenv.catalog.card` says about each task, without opening
its source.

A card holds, for an open task:

``frame_only``  how often the best player who sees only the frame
                showing is right -- the chance level for a learner with
                no memory. Where it changes with the rung it is given
                at rung 1, and ``frame_only_rung`` says so. 1.0 means
                the frame holds everything the answer needs.
``partial``     the cheap partial strategies and what each earns, as
                ``(strategy, level, rung)``.
``rungs``       for rungs 1 to 5: ``frames_back``, how many shown
                frames back from the one the question is put on the
                earliest frame the answer needs lies -- 0 when the frame
                showing holds it, as on a walk whose board shows the
                way; for a walk from memory, counted from the press that
                ends the shortest way, a press a frame, back to the last
                frame the goal showed; None when the answer lies in
                earlier trials, not frames. ``trials_back`` is how many
                trials back it lies, for those; and ``presses`` is how
                many presses the shortest way needs.
``note``        where the answer lies, when that is the run as a whole.

Only the first-steps families are measured. Every other catalogued task
gets a card with its ports, whether it is clocked and its family, and
``measured`` false. A held-out task's card says no more than that
either, measured or not.

The numbers here are tested against counting over deals in
``tests/test_cards.py``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

RUNGS = (1, 2, 3, 4, 5)


def _gap(k: int) -> int:
    """Look-alike frames between a far cue and its question."""
    return 2 ** min(5, k)


def _rungs(back: Callable[[int], Optional[int]],
           presses: Callable[[int], int],
           trials: Optional[Callable[[int], int]] = None) -> Dict:
    return {k: {'frames_back': back(k),
                'trials_back': trials(k) if trials else None,
                'presses': presses(k)} for k in RUNGS}


def _one(k: int) -> int:
    return 1


def _same(k: int) -> int:
    return k


def _none(k: int) -> None:
    return None


def _zero(k: int) -> int:
    return 0


def _walk(par: Callable[[int], int] = _same) -> Dict:
    return _rungs(_zero, par)


def _ice(k: int) -> int:
    return min(k, 10)


def _plus_one(k: int) -> int:
    return k + 1


#: task id: (frame_only, rung it is given at or None, partial, rungs,
#: note)
_SPECS: Dict[str, Tuple[float, Optional[int], tuple, Dict, str]] = {}


def _put(ids, frame_only, partial=(), rungs=None, rung=None,
         note='') -> None:
    for task_id in ids:
        _SPECS[task_id] = (frame_only, rung, tuple(partial), rungs, note)


#: Where the answer lies for the tasks whose answer is in the run.
_IN_THE_RUN = ('what holds lies in the run so far, not in a frame: it is '
               'dealt once a run and the earlier trials show it')


# --- the first families --------------------------------------------------

_put(('short_maze', 'short_tower', 'turned_tiles', 'short_push',
      'short_maze_steps'), 1.0, rungs=_walk())
_put(('marker_walk_shuffled',), 0.25, rung=1,
     partial=(('pressing the ports the way they point, ignoring the '
               'shuffle', 0.25, 1),), rungs=_rungs(_none, _same),
     note='which port moves which way ' + _IN_THE_RUN)
_put(('match_shapes', 'match_tiles', 'odd_shape', 'next_shape',
      'next_tile', 'in_the_loop', 'in_the_pen'), 1.0,
     rungs=_rungs(_zero, _one))
_put(('shape_back', 'sound_back'), 0.5,
     partial=(('pressing any answer but the one showing', 0.5, 1),),
     rungs=_rungs(_same, _one))
_put(('hidden_cue',), 0.25, rungs=_rungs(_plus_one, _one))
_put(('changed_tile',), 0.25, rungs=_rungs(_same, _one))
_put(('swapped_boxes',), 0.25,
     partial=(('keeping the lit box and ignoring the swaps', 0.5, 1),),
     rungs=_rungs(_same, _one))
_put(('which_rule',), 0.5, rung=1,
     partial=(('pressing by one rule all run long', 0.5, 1),),
     rungs=_rungs(_none, _one), note='the rule ' + _IN_THE_RUN)

# --- the memory families -------------------------------------------------

_put(('which_moved', 'moved_bead'), 0.25,
     partial=(('keeping where one thing was', 0.5, 1),),
     rungs=_rungs(_same, _one))
_put(('which_is_new', 'new_bead'), 0.25,
     partial=(('keeping one old thing', 1 / 3, 1),
              ('keeping two old things', 0.5, 1)),
     rungs=_rungs(_same, _one))
_put(('which_is_gone', 'gone_bead'), 0.25,
     partial=(('keeping one of the first things', 7 / 16, 1),),
     rungs=_rungs(_same, _one))
_put(('traded_places', 'traded_beads'), 0.25,
     partial=(('keeping where one thing was', 0.6, 1),),
     rungs=_rungs(_same, _one))
_put(('running_count', 'bead_pile'), 0.25,
     partial=(('keeping the start, dropping the steps', 0.5, 1),
              ('keeping the start, dropping the steps', 0.37, 3)),
     rungs=_rungs(_same, _one))
_put(('chevron_walk',), 0.25,
     partial=(('keeping the start, dropping the moves', 1 / 3, 1),
              ('keeping the start, dropping the moves', 1 / 3, 2)),
     rungs=_rungs(_same, _one))
_put(('next_in_turn',), 0.25,
     partial=(('pressing round the cycle without looking back', 1.0, 1),
              ('pressing round the cycle without looking back', 0.0, 2)),
     rungs=_rungs(_none, _one, _same))
_put(('stay_or_shift', 'moving_prize'), 0.25,
     partial=(('one port all run long', 0.25, 1),
              ('win-stay, lose-shift on the trial before', 0.5, 1),
              ('win-stay, lose-shift on the trial before', 0.29, 2)),
     rungs=_rungs(_none, _one, _same))
_put(('the_marked_one', 'flagged_bead'), 0.25,
     partial=(('keeping the first frame without the mark', 0.25, 1),
              ('keeping where the mark was, not what', 0.25, 1)),
     rungs=_rungs(lambda k: _gap(k) + 1, _one))
_put(('changed_note', 'changed_chime'), 0.25,
     partial=(('keeping the last of the first four tones', 0.5, 1),),
     rungs=_rungs(lambda k: k + 6, _one))
_put(('marked_tone', 'other_voice'), 0.25,
     partial=(('pressing the pitch last heard', 0.25, 1),),
     rungs=_rungs(lambda k: _gap(k) + 1, _one))

# --- the hands-off families ---------------------------------------------

_put(('hands_off',), 0.25, rungs=_rungs(_plus_one, _one))
_put(('busy_wait',), 0.25, rungs=_rungs(lambda k: 2 * k + 1, _plus_one))

# --- the walks -----------------------------------------------------------

_put(('long_way_round', 'push_and_pull', 'one_way_doors'), 1.0,
     rungs=_walk())
_put(('ice_floor',), 1.0, rungs=_walk(_ice))
_put(('gone_from_view',), 0.36, rung=1,
     partial=(('heading for the middle', 0.31, 1),
              ('heading for the middle', 0.06, 5)),
     rungs=_rungs(_same, _same))
_put(('in_that_order',), 0.13, rung=1,
     partial=(('heading for the middle', 0.09, 1),),
     rungs=_rungs(_plus_one, _plus_one))


def measured(task_id: str) -> bool:
    """Whether *task_id*'s floors are on its card."""
    return task_id in _SPECS


def describe(task_id: str) -> Dict[str, Any]:
    """The measured part of an open task's card."""
    frame_only, rung, partial, rungs, note = _SPECS[task_id]
    out = {
        'measured': True,
        'frame_only': frame_only,
        'frame_only_rung': rung,
        'partial': [{'strategy': s, 'level': level, 'rung': r}
                    for s, level, r in partial],
        'rungs': {k: dict(v) for k, v in rungs.items()},
    }
    if note:
        out['note'] = note
    return out
