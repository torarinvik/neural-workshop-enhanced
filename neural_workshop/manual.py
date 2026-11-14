# -*- coding: utf-8 -*-
"""Manual: a control panel never seen before, and a procedure to carry out.

Each round deals a panel -- switches, knobs that turn from 0 to 4,
buttons, coloured lamps and a one-digit display -- wired up at random,
and a short written procedure to follow on it. The lamps and display
answer the controls: each lamp shows green, red or nothing according to
a hidden sum of where the controls stand, and so does the display. The
wiring is never explained and need not be; what matters is that a step
like *if lamp L2 is red* asks about the panel as the earlier steps have
left it, so the procedure has to be done in order, really done, and
looked at as it goes.

When the procedure is finished the player presses Finish. The round
passes if every switch, knob and button count stands exactly where
following the procedure would have left it: a button pressed one time
too many fails it.

The ladder adds kinds of step:

* rung 1: one plain step -- turn a switch on or off, or flip it;
* from rung 2 knobs and buttons, and more steps;
* from rung 5 steps that depend on a lamp: *if L1 is green, ... ;
  otherwise ...*;
* from rung 9 steps that read the display (*press P2 as many times as
  the display shows*) and copy one control to another;
* from rung 13 steps that loop (*if L3 is not red, press P1 until it
  is*) and steps that refer to how a control stood at the start, which
  nothing on the panel still shows;
* from rung 17 the controls are laid out in shuffled order, so each one
  has to be found by its label rather than its place;
* from rung 20 steps that say to skip the step after them, on a
  condition;

and the panel and procedure grow throughout, to ten steps.

There is no par: following a procedure is right or it is not.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Callable, List, NamedTuple, Optional, Sequence, Tuple

from .i18n import _

MOST_SWITCHES, MOST_KNOBS, MOST_BUTTONS, MOST_LAMPS = 6, 4, 6, 4
TOP = 4                    # a knob turns from 0 to TOP
COLOURS = ('green', 'red', 'off')


class Grade(NamedTuple):
    rung: int
    switches: int
    knobs: int
    buttons: int
    lamps: int
    steps: int
    kinds: Tuple[str, ...]
    shuffled: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = ['set', 'flip']
    if r >= 2:
        kinds += ['knob', 'press']
    if r >= 5:
        kinds.append('if')
    if r >= 9:
        kinds += ['count', 'copy']
    if r >= 13:
        kinds += ['until', 'recall']
    if r >= 20:
        kinds.append('skip')
    return Grade(
        rung=r,
        switches=min(MOST_SWITCHES, 2 + r // 3),
        knobs=min(MOST_KNOBS, (r + 1) // 3),
        buttons=min(MOST_BUTTONS, 1 + r // 3),
        lamps=min(MOST_LAMPS, 1 + r // 4),
        steps=min(10, 1 + (r - 1) // 2),
        kinds=tuple(kinds),
        shuffled=r >= 17,
    )


class Wiring(NamedTuple):
    """How the lamps and display read the controls: a weight per control
    (switches, then knobs, then button presses) for each."""
    lamps: Tuple[Tuple[int, ...], ...]
    display: Tuple[int, ...]


class Panel:
    """Where every control stands, and what the lamps and display say."""

    def __init__(self, level: Grade, wiring: Wiring,
                 switches: Sequence[bool], knobs: Sequence[int]) -> None:
        self.level = level
        self.wiring = wiring
        self.switches = list(switches)
        self.knobs = list(knobs)
        self.presses = [0] * level.buttons
        #: Every action taken, as ('switch', i), ('knob', i, +-1) or
        #: ('press', i): what a reference would do with its hands.
        self.log: List[Tuple] = []

    def copy(self) -> 'Panel':
        other = Panel(self.level, self.wiring, self.switches, self.knobs)
        other.presses = list(self.presses)
        return other

    def vector(self) -> List[int]:
        return ([int(s) for s in self.switches] + list(self.knobs)
                + list(self.presses))

    def lamp(self, index: int) -> str:
        total = sum(w * x for w, x in zip(self.wiring.lamps[index],
                                          self.vector()))
        return COLOURS[total % 3]

    def display(self) -> int:
        return sum(w * x for w, x in zip(self.wiring.display,
                                         self.vector())) % 10

    def state(self) -> Tuple:
        return (tuple(self.switches), tuple(self.knobs),
                tuple(self.presses))

    # --- hands -----------------------------------------------------------

    def toggle(self, index: int) -> bool:
        if not 0 <= index < len(self.switches):
            return False
        self.switches[index] = not self.switches[index]
        self.log.append(('switch', index))
        return True

    def turn(self, index: int, way: int) -> bool:
        if not 0 <= index < len(self.knobs):
            return False
        to = self.knobs[index] + (1 if way > 0 else -1)
        if not 0 <= to <= TOP:
            return False
        self.knobs[index] = to
        self.log.append(('knob', index, 1 if way > 0 else -1))
        return True

    def press(self, index: int) -> bool:
        if not 0 <= index < len(self.presses):
            return False
        self.presses[index] += 1
        self.log.append(('press', index))
        return True

    # --- what a step asks for --------------------------------------------

    def set_switch(self, index: int, on: bool) -> None:
        if self.switches[index] != on:
            self.toggle(index)

    def set_knob(self, index: int, to: int) -> None:
        while self.knobs[index] != to:
            self.turn(index, 1 if to > self.knobs[index] else -1)


def switch_name(i: int) -> str:
    return 'S%d' % (i + 1)


def knob_name(i: int) -> str:
    return 'K%d' % (i + 1)


def button_name(i: int) -> str:
    return 'P%d' % (i + 1)


def lamp_name(i: int) -> str:
    return 'L%d' % (i + 1)


def colour_word(colour: str) -> str:
    return {'green': _('green'), 'red': _('red'), 'off': _('off')}[colour]


#: A step: its words, and what it does to a panel given the panel as it
#: stood at the start. It returns True when the step after it is skipped.
Run = Callable[[Panel, Panel], Optional[bool]]


class Step(NamedTuple):
    words: str
    run: Run


class Deal(NamedTuple):
    seed: int
    level: Grade
    wiring: Wiring
    switches: Tuple[bool, ...]
    knobs: Tuple[int, ...]
    steps: Tuple[Step, ...]
    #: Where each control is drawn: slot -> control, per kind.
    layout: Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[int, ...]]

    def panel(self) -> Panel:
        return Panel(self.level, self.wiring, self.switches, self.knobs)


def _plain(level: Grade, draw: random.Random, kinds: Sequence[str]
           ) -> Tuple[str, Run]:
    """A step that only moves a control."""
    choices = [k for k in kinds if k in ('set', 'flip')]
    if level.knobs:
        choices += [k for k in kinds if k == 'knob']
    if level.buttons:
        choices += [k for k in kinds if k == 'press']
    kind = draw.choice(choices)
    if kind == 'set':
        i, on = draw.randrange(level.switches), draw.random() < 0.5
        return (_('turn switch %s %s') % (switch_name(i),
                                          _('on') if on else _('off')),
                lambda p, s, i=i, on=on: p.set_switch(i, on))
    if kind == 'flip':
        i = draw.randrange(level.switches)
        return (_('flip switch %s') % switch_name(i),
                lambda p, s, i=i: p.toggle(i) and None)
    if kind == 'knob':
        i, to = draw.randrange(level.knobs), draw.randint(0, TOP)
        return (_('turn knob %s to %d') % (knob_name(i), to),
                lambda p, s, i=i, to=to: p.set_knob(i, to))
    i, n = draw.randrange(level.buttons), draw.randint(1, 3)
    words = (_('press button %s') % button_name(i) if n == 1 else
             _('press button %s %d times') % (button_name(i), n))

    def press(p, s, i=i, n=n):
        for _time in range(n):
            p.press(i)
    return words, press


def _sentence(words: str) -> str:
    return words[:1].upper() + words[1:] + '.'


def _step(kind: str, level: Grade, wiring: Wiring, draw: random.Random,
          plain_kinds: Sequence[str], last: bool) -> Optional[Step]:
    if kind in ('set', 'flip', 'knob', 'press'):
        if kind == 'knob' and not level.knobs:
            return None
        words, run = _plain(level, draw, [kind])
        return Step(_sentence(words), run)
    if kind == 'if':
        lamp = draw.randrange(level.lamps)
        colour = draw.choice(COLOURS)
        yes, run_yes = _plain(level, draw, plain_kinds)
        no, run_no = _plain(level, draw, plain_kinds)
        if yes == no:
            return None
        lamp_words = (_('lamp %s is off') % lamp_name(lamp)
                      if colour == 'off' else
                      _('lamp %s is %s') % (lamp_name(lamp),
                                            colour_word(colour)))

        def branch(p, s, lamp=lamp, colour=colour):
            (run_yes if p.lamp(lamp) == colour else run_no)(p, s)
        return Step(_('If %s, %s; otherwise %s.') % (lamp_words, yes, no),
                    branch)
    if kind == 'count':
        if not level.buttons:
            return None
        i = draw.randrange(level.buttons)

        def count(p, s, i=i):
            for _time in range(p.display()):
                p.press(i)
        return Step(_('Press button %s as many times as the display shows '
                      'now (none if it shows 0).') % button_name(i), count)
    if kind == 'copy':
        if level.knobs >= 2 and draw.random() < 0.5:
            a, b = draw.sample(range(level.knobs), 2)
            return Step(_('Turn knob %s to where knob %s points.')
                        % (knob_name(b), knob_name(a)),
                        lambda p, s, a=a, b=b: p.set_knob(b, p.knobs[a]))
        a, b = draw.sample(range(level.switches), 2)
        return Step(_('Set switch %s the same as switch %s.')
                    % (switch_name(b), switch_name(a)),
                    lambda p, s, a=a, b=b: p.set_switch(b, p.switches[a]))
    if kind == 'until':
        pairs = [(lamp, b) for lamp in range(level.lamps)
                 for b in range(level.buttons)
                 if wiring.lamps[lamp][level.switches + level.knobs + b]
                 % 3]
        if not pairs:
            return None
        lamp, b = draw.choice(pairs)
        colour = draw.choice(COLOURS)

        def until(p, s, lamp=lamp, b=b, colour=colour):
            while p.lamp(lamp) != colour:
                p.press(b)
        return Step(_('If lamp %s is not %s, press button %s until it is.')
                    % (lamp_name(lamp), colour_word(colour),
                       button_name(b)), until)
    if kind == 'recall':
        if level.knobs and draw.random() < 0.5:
            i = draw.randrange(level.knobs)
            return Step(_('Turn knob %s back to where it pointed at the '
                          'start.') % knob_name(i),
                        lambda p, s, i=i: p.set_knob(i, s.knobs[i]))
        i = draw.randrange(level.switches)
        return Step(_('Set switch %s back the way it was at the start.')
                    % switch_name(i),
                    lambda p, s, i=i: p.set_switch(i, s.switches[i]))
    if kind == 'skip':
        if last:
            return None
        even = draw.random() < 0.5
        return Step(_('If the display shows an %s number, skip the next '
                      'step.') % (_('even') if even else _('odd')),
                    lambda p, s, even=even: (p.display() % 2 == 0) == even)
    return None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    controls = level.switches + level.knobs + level.buttons
    for _attempt in range(200):
        lamps = tuple(tuple(draw.randint(0, 2) for _c in range(controls))
                      for _l in range(level.lamps))
        if all(any(row) for row in lamps):
            break
    wiring = Wiring(lamps, tuple(draw.randint(0, 9)
                                 for _c in range(controls)))
    switches = tuple(draw.random() < 0.5 for _s in range(level.switches))
    knobs = tuple(draw.randint(0, TOP) for _k in range(level.knobs))
    plain_kinds = [k for k in level.kinds
                   if k in ('set', 'flip', 'knob', 'press')]
    # The newest kinds of step are asked for more often than the old, and
    # at least once, so a rung tests what it adds.
    newest = [k for k in level.kinds if k not in grade(level.rung - 4).kinds] \
        if level.rung > 4 else []
    newest = [k for k in newest if k not in plain_kinds] or newest
    for _attempt in range(100):
        steps: List[Step] = []
        # Not the last step: a skip there would have nothing to skip.
        forced = (draw.randrange(max(1, level.steps - 1))
                  if newest else -1)
        tries = 0
        while len(steps) < level.steps:
            last = len(steps) == level.steps - 1
            tries += 1
            kind = (draw.choice(newest)
                    if len(steps) == forced and tries < 200 else
                    draw.choice(list(level.kinds) + newest * 2))
            step = _step(kind, level, wiring, draw, plain_kinds, last)
            if step is not None and all(step.words != s.words
                                        for s in steps):
                steps.append(step)
        trial = Deal(seed, level, wiring, switches, knobs, tuple(steps),
                     ((), (), ()))
        # Doing nothing must not already be right.
        if follow(trial).state() != trial.panel().state():
            break
    layout = []
    for count in (level.switches, level.knobs, level.buttons):
        order = list(range(count))
        if level.shuffled:
            draw.shuffle(order)
        layout.append(tuple(order))
    return trial._replace(layout=tuple(layout))


def follow(dealt: Deal) -> Panel:
    """The panel as the procedure leaves it, done exactly."""
    panel = dealt.panel()
    start = dealt.panel()
    skip = False
    for step in dealt.steps:
        if skip:
            skip = False
            continue
        skip = bool(step.run(panel, start))
    return panel
