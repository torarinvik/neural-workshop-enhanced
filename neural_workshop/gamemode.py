# -*- coding: utf-8 -*-
"""Game modes and the mutable game state.

A mode is an integer whose low bits pick a base combination of
modalities and whose high bits switch on variants:

===========  ===========================================================
``| 128``    crab-back: each run of N stimuli is matched in reverse
``| 256*k``  multi-stim: k+1 simultaneous visual stimuli
``| 1024``   self-paced: the trial waits for an answer
===========  ===========================================================

:class:`Mode` derives every variant from the base tables at construction,
and also holds the live per-session state (trial number, current
stimulus, what the player pressed).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from . import runtime, state
from .i18n import _

#: Modalities that can be matched, in the order they appear on screen.
INPUT_MODALITIES: Sequence[str] = (
    'position1', 'position2', 'position3', 'position4',
    'color', 'image', 'vis1', 'vis2', 'vis3', 'vis4',
    'visvis', 'visaudio', 'audiovis', 'audio', 'audio2',
)

#: Every stimulus field carried in ``Mode.current_stim``.
STIMULUS_FIELDS: Sequence[str] = (
    'position1', 'position2', 'position3', 'position4', 'color',
    'vis',   # image or letter, single-stimulus modes
    'vis1', 'vis2', 'vis3', 'vis4',  # image or color, multi-stim modes
    'audio', 'audio2', 'number',
)

BASE_SHORT_NAMES: Dict[int, str] = {
    2: 'D', 3: 'PCA', 4: 'DC', 5: 'TC', 6: 'QC', 7: 'A', 8: 'DA', 9: 'TA',
    10: 'Po', 11: 'Au', 12: 'TCC',
    20: 'PC', 21: 'PI', 22: 'CA', 23: 'IA', 24: 'CI', 25: 'PCI', 26: 'PIA',
    27: 'CIA', 28: 'Q',
    100: 'AA', 101: 'PAA', 102: 'CAA', 103: 'IAA', 104: 'PCAA', 105: 'PIAA',
    106: 'CIAA', 107: 'P',
}

BASE_MODALITIES: Dict[int, List[str]] = {
    2: ['position1', 'audio'],
    3: ['position1', 'color', 'audio'],
    4: ['visvis', 'visaudio', 'audiovis', 'audio'],
    5: ['position1', 'visvis', 'visaudio', 'audiovis', 'audio'],
    6: ['position1', 'visvis', 'visaudio', 'color', 'audiovis', 'audio'],
    7: ['arithmetic'],
    8: ['position1', 'arithmetic'],
    9: ['position1', 'arithmetic', 'color'],
    10: ['position1'],
    11: ['audio'],
    12: ['visvis', 'visaudio', 'color', 'audiovis', 'audio'],
    20: ['position1', 'color'],
    21: ['position1', 'image'],
    22: ['color', 'audio'],
    23: ['image', 'audio'],
    24: ['color', 'image'],
    25: ['position1', 'color', 'image'],
    26: ['position1', 'image', 'audio'],
    27: ['color', 'image', 'audio'],
    28: ['position1', 'color', 'image', 'audio'],
    100: ['audio', 'audio2'],
    101: ['position1', 'audio', 'audio2'],
    102: ['color', 'audio', 'audio2'],
    103: ['image', 'audio', 'audio2'],
    104: ['position1', 'color', 'audio', 'audio2'],
    105: ['position1', 'image', 'audio', 'audio2'],
    106: ['color', 'image', 'audio', 'audio2'],
    107: ['position1', 'color', 'image', 'audio', 'audio2'],
}


def base_long_names() -> Dict[int, str]:
    """Translated display names for the base modes."""
    return {
        2: _('Dual'), 3: _('Position, Color, Sound'), 4: _('Dual Combination'),
        5: _('Tri Combination'), 6: _('Quad Combination'), 7: _('Arithmetic'),
        8: _('Dual Arithmetic'), 9: _('Triple Arithmetic'), 10: _('Position'),
        11: _('Sound'), 12: _('Tri Combination (Color)'),
        20: _('Position, Color'), 21: _('Position, Image'),
        22: _('Color, Sound'), 23: _('Image, Sound'), 24: _('Color, Image'),
        25: _('Position, Color, Image'), 26: _('Position, Image, Sound'),
        27: _('Color, Image, Sound'), 28: _('Quad'),
        100: _('Sound, Sound2'), 101: _('Position, Sound, Sound2'),
        102: _('Color, Sound, Sound2'), 103: _('Image, Sound, Sound2'),
        104: _('Position, Color, Sound, Sound2'),
        105: _('Position, Image, Sound, Sound2'),
        106: _('Color, Image, Sound, Sound2'), 107: _('Pentuple'),
    }


def get_color(color: int) -> Sequence[int]:
    """RGBA for stimulus colour *color*, honouring the dark theme."""
    if color in (4, 7) and state.cfg.BLACK_BACKGROUND:
        return state.cfg['COLOR_%i_BLK' % color]
    return state.cfg['COLOR_%i' % color]


# Luminance floor so every color-n-back hue stays readable on the dark cubes.
_3D_FACE_COLORS = {
    1: (56, 112, 255, 255),
    2: (0, 220, 230, 255),
    3: (46, 214, 82, 255),
    4: (232, 234, 240, 255),
    5: (232, 64, 214, 255),
    6: (240, 56, 56, 255),
    7: (198, 204, 214, 255),
    8: (250, 214, 40, 255),
}


def get_3d_color(color: int) -> Sequence[int]:
    """High-contrast RGBA for a 3D cube face, 1-based colour index."""
    try:
        index = ((int(color) - 1) % 8) + 1
    except Exception:
        index = 1
    return _3D_FACE_COLORS[index]


def default_nback_mode(mode: int) -> int:
    """Configured starting n-back level for *mode*."""
    if ('BACK_%i' % mode) in state.cfg:
        return state.cfg['BACK_%i' % mode]
    if mode > 127:  # fall back on the base mode for crab / multi variants
        return default_nback_mode(mode % 128)
    return state.cfg.BACK_DEFAULT


def default_ticks(mode: int) -> int:
    """Configured tick budget per trial for *mode*, plus variant bonuses."""
    cfg = state.cfg
    if ('TICKS_%i' % mode) in cfg:
        return cfg['TICKS_%i' % mode]
    if mode > 127:
        bonus = ((mode & 128) / 128) * cfg.BONUS_TICKS_CRAB
        if mode & 768:
            bonus += cfg['BONUS_TICKS_MULTI_%i' % ((mode & 768) / 256 + 1)]
        if runtime.DEBUG:
            print('Adding a bonus of %i ticks for mode %i' % (bonus, mode))
        return bonus + default_ticks(mode % 128)
    return cfg.TICKS_DEFAULT


class ModeTables:
    """The full mode tables: base modes plus every generated variant."""

    def __init__(self) -> None:
        self.short_names: Dict[int, str] = dict(BASE_SHORT_NAMES)
        self.long_names: Dict[int, str] = base_long_names()
        self.modalities: Dict[int, List[str]] = {
            k: list(v) for k, v in BASE_MODALITIES.items()}
        self.flags: Dict[int, Dict[str, int]] = {}
        self._generate_crab_modes()
        self._generate_multi_modes()
        self._generate_selfpaced_modes()

    def _generate_crab_modes(self) -> None:
        """Crab DNB = 2 | 128 = 130: match each run of N in reverse."""
        for m in list(self.short_names):
            variant = m | 128
            self.flags[m] = {'crab': 0, 'multi': 1, 'selfpaced': 0}
            self.flags[variant] = {'crab': 1, 'multi': 1, 'selfpaced': 0}
            self.short_names[variant] = 'C' + self.short_names[m]
            self.long_names[variant] = _('Crab ') + self.long_names[m]
            self.modalities[variant] = list(self.modalities[m])

    def _generate_multi_modes(self) -> None:
        """3xDNB = 2 | 512: several visual stimuli shown at once."""
        labels = [(2, _('Double-stim')), (3, _('Triple-stim')),
                  (4, _('Quadruple-stim'))]
        for m in list(self.short_names):
            modalities = self.modalities[m]
            # Combination and arithmetic modes have no room for extra stimuli.
            if {'color', 'image'}.issubset(modalities) \
                    or 'position1' not in modalities \
                    or {'visvis', 'arithmetic'} & set(modalities):
                continue
            for n, label in labels:
                variant = m | 256 * (n - 1)
                self.flags[variant] = dict(self.flags[m])
                self.flags[variant]['multi'] = n
                self.short_names[variant] = '%ix%s' % (n, self.short_names[m])
                self.long_names[variant] = '%s %s' % (label, self.long_names[m])
                derived = list(modalities)
                for i in range(2, n + 1):
                    derived.insert(i - 1, 'position%i' % i)
                if 'color' in modalities or 'image' in modalities:
                    for i in range(1, n + 1):
                        derived.insert(n + i - 1, 'vis%i' % i)
                for name in ('image', 'color'):
                    if name in derived:
                        derived.remove(name)
                self.modalities[variant] = derived

    def _generate_selfpaced_modes(self) -> None:
        """``| 1024``: the trial does not advance until the player answers."""
        for m in list(self.short_names):
            variant = m | 1024
            self.short_names[variant] = 'SP-' + self.short_names[m]
            self.long_names[variant] = 'Self-paced ' + self.long_names[m]
            self.modalities[variant] = list(self.modalities[m])
            self.flags[variant] = dict(self.flags[m])
            self.flags[variant]['selfpaced'] = 1


class Mode:
    """All mutable game state: which mode is selected and how it is going."""

    def __init__(self) -> None:
        cfg = state.cfg
        self.mode: int = cfg.GAME_MODE
        self.back: int = default_nback_mode(self.mode)
        self.ticks_per_trial: int = default_ticks(self.mode)
        self.num_trials: int = cfg.NUM_TRIALS
        self.num_trials_factor: int = cfg.NUM_TRIALS_FACTOR
        self.num_trials_exponent: int = cfg.NUM_TRIALS_EXPONENT
        self.num_trials_total: int = self.num_trials + self.num_trials_factor \
            * self.back ** self.num_trials_exponent

        tables = ModeTables()
        self.short_mode_names: Dict[int, str] = tables.short_names
        self.long_mode_names: Dict[int, str] = tables.long_names
        self.modalities: Dict[int, List[str]] = tables.modalities
        self.flags: Dict[int, Dict[str, int]] = tables.flags

        self.variable_list: List[int] = []
        self.manual: bool = cfg.MANUAL
        if not self.manual:
            self.enforce_standard_mode()

        #: Which match buttons are currently pressed, per modality.
        self.inputs: Dict[str, bool] = {k: False for k in INPUT_MODALITIES}
        #: Reaction time of each press, in seconds since the trial started.
        self.input_rts: Dict[str, float] = {k: 0. for k in INPUT_MODALITIES}
        self.hide_text: bool = cfg.HIDE_TEXT
        self.current_stim: Dict[str, int] = {k: 0 for k in STIMULUS_FIELDS}
        self.current_operation: str = 'none'

        self.started: bool = False
        self.paused: bool = False
        self.show_missed: bool = False
        self.sound_select: bool = False
        self.draw_graph: bool = False
        self.saccadic: bool = False
        self.title_screen: bool = not cfg.SKIP_TITLE_SCREEN
        #: Last task-hub category the player opened.
        self.task_category: str = 'working_memory'

        self.session_number: int = 0
        self.trial_number: int = 0
        #: Wall-clock start of the current trial, for reaction times.
        self.trial_starttime: float = 0.0
        self.tick: int = 0
        self.progress: int = 0
        self.phase: Optional[str] = None
        self.phase_elapsed: int = 0
        self.step_mode: bool = False
        self.frame_seq: int = 0
        self.session_done: bool = False

        self.sound_mode: str = 'none'
        self.sound2_mode: str = 'none'
        self.soundlist: List[object] = []
        self.soundlist2: List[object] = []
        self.bt_sequence: List[List[int]] = []

    def enforce_standard_mode(self) -> None:
        """Reset level and session length to the configured defaults."""
        cfg = state.cfg
        self.back = default_nback_mode(self.mode)
        self.ticks_per_trial = default_ticks(self.mode)
        self.num_trials = cfg.NUM_TRIALS
        self.num_trials_factor = cfg.NUM_TRIALS_FACTOR
        self.num_trials_exponent = cfg.NUM_TRIALS_EXPONENT
        self.num_trials_total = self.num_trials + self.num_trials_factor \
            * self.back ** self.num_trials_exponent
        self.session_number = 0

    def short_name(self, mode: Optional[int] = None,
                   back: Optional[int] = None) -> str:
        """Compact label such as ``D2B``, used in stats files."""
        if mode is None:
            mode = self.mode
        if back is None:
            back = self.back
        return '%s%iB' % (self.short_mode_names[mode], back)
