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
``frames_back_least``  where the wait is drawn anew each trial, the
                fewest frames back the answer may lie; ``frames_back`` is
                then the most.
``random``      in each rung's row: what a press at random earns, each
                time a press is called for -- at the question, at each
                job of a busy wait, at every press of a walk.
``no_memory``   in each rung's row: the best a player that keeps nothing
                from earlier frames earns -- for a question, the best
                player reading the frame it is put on; for a walk whose
                board shows the way, 1.0; for a walk from memory and
                Marker Walk, Shuffled, the best of the players counted.
``steps_at_10hz``  in each rung's row: at ten steps a second, how many
                steps the last one on which the earliest frame the answer
                needs still shows lies before the step the question is
                put on (for a walk from memory, the step the walk opens
                on); None where the answer is not in a shown frame.
``early_presses``  what a press before the question does: ignored, ends
                the trial unpaid, or must be the wait's jobs; ``none``
                where there is no wait.
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

# --- a wait of uneven length ---------------------------------------------

def _uneven(k: int) -> Dict:
    return {'frames_back': 3 * k + 1, 'frames_back_least': k + 1,
            'trials_back': None, 'presses': 1}


_put(('uneven_wait',), 0.25, rungs={k: _uneven(k) for k in RUNGS})

# --- several kept, one asked for ------------------------------------------

_put(('which_was_where',), 0.25,
     partial=(('answering with the last cue shown', 1 / 2, 1),
              ('answering with the last cue shown', 1 / 3, 2),
              ('answering with the last cue shown', 1 / 4, 3)),
     rungs=_rungs(lambda k: min(k, 3) + 3, _one))

# --- the newest counts, the first counts ----------------------------------

_put(('newest_counts',), 0.25,
     partial=(('pressing where the first cue was', 0.5, 1),
              ('pressing where the first cue was', 0.45, 2),
              ('pressing where the first cue was', 0.39, 3)),
     rungs=_rungs(lambda k: 2 * k + 2, _one))
_put(('first_counts',), 0.25,
     partial=(('pressing where the last cue was', 0.5, 1),
              ('pressing where the last cue was', 0.45, 2),
              ('pressing where the last cue was', 0.39, 3)),
     rungs=_rungs(lambda k: 2 * k + 2, _one))

# --- a rule held across trials --------------------------------------------

_put(('same_or_opposite',), 0.5,
     partial=(('pressing by one rule all run long', 0.5, 1),
              ('pressing by one rule all run long', 0.5, 3)),
     rungs=_rungs(_none, _one, lambda k: k - 1),
     note='the rule is shown at the start of each block of trials, a '
          'frame before the question of its first trial, and not again '
          'in the block; trials_back is the most it lies back')

# --- the walks -----------------------------------------------------------

_put(('long_way_round', 'push_and_pull', 'one_way_doors'), 1.0,
     rungs=_walk())
_put(('ice_floor',), 1.0, rungs=_walk(_ice))
_put(('fetch_and_carry', 'plate_and_gate'), 1.0, rungs=_walk(_plus_one))
_put(('gone_from_view',), 0.36, rung=1,
     partial=(('heading for the middle', 0.31, 1),
              ('heading for the middle', 0.06, 5)),
     rungs=_rungs(_same, _same))
_put(('in_that_order',), 0.13, rung=1,
     partial=(('heading for the middle', 0.09, 1),),
     rungs=_rungs(_plus_one, _plus_one))


# --- by rung: what presses at random and the best without memory earn,
# --- when presses count, and how far back the cue is at ten steps a second

#: task id: ((random, by rung 1 to 5), (no memory, by rung 1 to 5)),
#: counted over deals (``tests/test_cards.py`` counts them again).
_LEVELS: Dict[str, Tuple[Tuple[float, ...], Tuple[float, ...]]] = {
    'short_maze': ((0.246, 0.054, 0.018, 0.004, 0.002),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'short_tower': ((0.149, 0.032, 0.005, 0.001, 0.0),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'turned_tiles': ((0.127, 0.035, 0.013, 0.006, 0.0),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'short_push': ((0.25, 0.057, 0.014, 0.005, 0.002),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'short_maze_steps': ((0.246, 0.054, 0.018, 0.004, 0.002),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'marker_walk_shuffled': ((0.249, 0.099, 0.039, 0.015, 0.006),
        (0.249, 0.17, 0.127, 0.102, 0.079)),
    'match_shapes': ((0.508, 0.499, 0.502, 0.506, 0.511),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'match_tiles': ((0.492, 0.501, 0.498, 0.494, 0.489),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'odd_shape': ((0.322, 0.238, 0.206, 0.164, 0.144),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'next_shape': ((0.329, 0.339, 0.33, 0.323, 0.325),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'next_tile': ((0.329, 0.321, 0.336, 0.331, 0.339),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'in_the_loop': ((0.496, 0.504, 0.509, 0.482, 0.501),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'in_the_pen': ((0.507, 0.497, 0.497, 0.508, 0.486),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'shape_back': ((0.337, 0.335, 0.339, 0.331, 0.324),
        (0.5, 0.512, 0.487, 0.504, 0.512)),
    'hidden_cue': ((0.249, 0.249, 0.249, 0.249, 0.249),
        (0.258, 0.258, 0.258, 0.258, 0.258)),
    'sound_back': ((0.333, 0.344, 0.316, 0.344, 0.336),
        (0.49, 0.48, 0.514, 0.498, 0.495)),
    'which_rule': ((0.342, 0.343, 0.331, 0.334, 0.345),
        (0.5, 0.584, 0.578, 0.526, 0.52)),
    'changed_tile': ((0.249, 0.249, 0.249, 0.249, 0.249),
        (0.267, 0.267, 0.267, 0.267, 0.267)),
    'swapped_boxes': ((0.237, 0.261, 0.248, 0.261, 0.258),
        (0.263, 0.244, 0.265, 0.231, 0.236)),
    'which_moved': ((0.254, 0.254, 0.254, 0.254, 0.254),
        (0.255, 0.255, 0.255, 0.255, 0.255)),
    'moved_bead': ((0.244, 0.244, 0.244, 0.244, 0.244),
        (0.249, 0.249, 0.249, 0.249, 0.249)),
    'which_is_new': ((0.24, 0.24, 0.24, 0.24, 0.24),
        (0.24, 0.24, 0.24, 0.24, 0.24)),
    'new_bead': ((0.254, 0.254, 0.254, 0.254, 0.254),
        (0.255, 0.255, 0.255, 0.255, 0.255)),
    'which_is_gone': ((0.26, 0.26, 0.26, 0.26, 0.26),
        (0.247, 0.247, 0.247, 0.247, 0.247)),
    'gone_bead': ((0.24, 0.24, 0.24, 0.24, 0.24),
        (0.242, 0.242, 0.242, 0.242, 0.242)),
    'traded_places': ((0.202, 0.202, 0.202, 0.202, 0.202),
        (0.252, 0.252, 0.252, 0.252, 0.252)),
    'traded_beads': ((0.194, 0.194, 0.194, 0.194, 0.194),
        (0.252, 0.252, 0.252, 0.252, 0.252)),
    'running_count': ((0.26, 0.245, 0.245, 0.263, 0.25),
        (0.258, 0.248, 0.248, 0.253, 0.252)),
    'bead_pile': ((0.249, 0.251, 0.235, 0.242, 0.244),
        (0.258, 0.248, 0.248, 0.253, 0.252)),
    'chevron_walk': ((0.265, 0.249, 0.257, 0.259, 0.253),
        (0.236, 0.257, 0.243, 0.257, 0.249)),
    'next_in_turn': ((0.246, 0.249, 0.261, 0.25, 0.251),
        (0.246, 0.249, 0.261, 0.25, 0.251)),
    'stay_or_shift': ((0.263, 0.243, 0.244, 0.253, 0.25),
        (0.263, 0.265, 0.248, 0.256, 0.25)),
    'moving_prize': ((0.263, 0.243, 0.244, 0.253, 0.25),
        (0.263, 0.265, 0.248, 0.256, 0.25)),
    'the_marked_one': ((0.255, 0.249, 0.251, 0.252, 0.254),
        (0.245, 0.249, 0.27, 0.246, 0.248)),
    'flagged_bead': ((0.256, 0.256, 0.247, 0.237, 0.24),
        (0.242, 0.235, 0.248, 0.254, 0.242)),
    'changed_note': ((0.251, 0.251, 0.251, 0.251, 0.251),
        (0.249, 0.249, 0.249, 0.249, 0.249)),
    'changed_chime': ((0.245, 0.245, 0.245, 0.245, 0.245),
        (0.249, 0.249, 0.249, 0.249, 0.249)),
    'marked_tone': ((0.252, 0.248, 0.247, 0.251, 0.251),
        (0.234, 0.278, 0.247, 0.252, 0.234)),
    'other_voice': ((0.248, 0.251, 0.263, 0.25, 0.251),
        (0.234, 0.278, 0.247, 0.252, 0.234)),
    'long_way_round': ((0.455, 0.162, 0.059, 0.012, 0.007),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'push_and_pull': ((0.366, 0.116, 0.039, 0.018, 0.004),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'one_way_doors': ((0.431, 0.163, 0.056, 0.021, 0.004),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'ice_floor': ((0.443, 0.193, 0.091, 0.021, 0.005),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'gone_from_view': ((0.365, 0.162, 0.067, 0.036, 0.021),
        (0.365, 0.202, 0.141, 0.113, 0.066)),
    'in_that_order': ((0.117, 0.049, 0.021, 0.008, 0.009),
        (0.117, 0.049, 0.033, 0.025, 0.017)),
    'hands_off': ((0.246, 0.246, 0.246, 0.246, 0.246),
        (0.245, 0.245, 0.245, 0.245, 0.245)),
    'busy_wait': ((0.06, 0.018, 0.004, 0.001, 0.0),
        (0.239, 0.251, 0.248, 0.247, 0.259)),
    'uneven_wait': ((0.246, 0.248, 0.247, 0.253, 0.248),
        (0.251, 0.243, 0.25, 0.242, 0.248)),
    'which_was_where': ((0.249, 0.242, 0.247, 0.247, 0.247),
        (0.252, 0.238, 0.272, 0.272, 0.272)),
    'newest_counts': ((0.256, 0.26, 0.254, 0.256, 0.244),
        (0.262, 0.241, 0.237, 0.254, 0.248)),
    'first_counts': ((0.263, 0.26, 0.247, 0.257, 0.257),
        (0.249, 0.251, 0.234, 0.261, 0.242)),
    'same_or_opposite': ((0.251, 0.245, 0.253, 0.256, 0.246),
        (0.494, 0.506, 0.507, 0.503, 0.505)),
    'fetch_and_carry': ((0.121, 0.058, 0.021, 0.007, 0.004),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
    'plate_and_gate': ((0.13, 0.037, 0.019, 0.006, 0.003),
        (1.0, 1.0, 1.0, 1.0, 1.0)),
}

#: What a press before the question does.
IGNORED = 'ignored'
ENDS = 'ends the trial unpaid'
JOBS = ('must be the wait\'s jobs, each pressed once while its dot shows; '
        'any other press ends the trial unpaid')
NO_WAIT = 'none: there is no wait, every press counts as it comes'
WHILE_SHOWN = 'ignored while the goals show; then every press is a step'

_EARLY: Dict[str, str] = {}
for _family, _what in (('short walks', NO_WAIT),
                       ('payment for progress', NO_WAIT),
                       ('forgiving walks', NO_WAIT),
                       ('two-stage walks', NO_WAIT),
                       ('twins', NO_WAIT),
                       ('looking back', IGNORED), ('held in mind', IGNORED),
                       ('now and earlier', IGNORED),
                       ('carried through', IGNORED),
                       ('own presses', IGNORED), ('far cue', IGNORED),
                       ('heard back', IGNORED),
                       ('walks from memory', WHILE_SHOWN),
                       ('hands off', ENDS), ('uneven wait', ENDS),
                       ('several kept', ENDS), ('newest and first', ENDS),
                       ('rule held', ENDS)):
    _EARLY[_family] = _what
_EARLY_BY_ID = {'marker_walk_shuffled': NO_WAIT, 'which_rule': NO_WAIT,
                'busy_wait': JOBS}

#: The older looking-back tasks open their question a step later at ten
#: steps a second than the frame families do.
_OLDER = ('shape_back', 'hidden_cue', 'sound_back', 'changed_tile',
          'swapped_boxes')


def steps_at_10hz(task_id: str, back: Optional[int]) -> Optional[int]:
    """At ten steps a second, how many steps the last one on which the
    earliest frame the answer needs still shows lies before the step the
    question is put on; None where the answer is not in a shown frame.
    A frame is five steps, and shows for the first four."""
    if back is None or back == 0:
        return None
    if task_id in ('gone_from_view', 'in_that_order'):
        return 1
    return 5 * back - (2 if task_id in _OLDER else 3)


def measured(task_id: str) -> bool:
    """Whether *task_id*'s floors are on its card."""
    return task_id in _SPECS


def early_presses(task_id: str) -> str:
    """What a press before the question does on *task_id*."""
    if task_id in _EARLY_BY_ID:
        return _EARLY_BY_ID[task_id]
    from .catalog import family_of
    return _EARLY[family_of(task_id)]


def describe(task_id: str) -> Dict[str, Any]:
    """The measured part of an open task's card."""
    frame_only, rung, partial, rungs, note = _SPECS[task_id]
    rnd, bare = _LEVELS[task_id]
    out = {
        'measured': True,
        'frame_only': frame_only,
        'frame_only_rung': rung,
        'partial': [{'strategy': s, 'level': level, 'rung': r}
                    for s, level, r in partial],
        'rungs': {k: dict(v) for k, v in rungs.items()},
        'early_presses': early_presses(task_id),
    }
    for i, k in enumerate(RUNGS):
        row = out['rungs'][k]
        row['random'] = rnd[i]
        row['no_memory'] = bare[i]
        row['steps_at_10hz'] = steps_at_10hz(task_id, row['frames_back'])
        if 'frames_back_least' in row:
            row['steps_at_10hz_least'] = steps_at_10hz(
                task_id, row['frames_back_least'])
    if note:
        out['note'] = note
    return out
