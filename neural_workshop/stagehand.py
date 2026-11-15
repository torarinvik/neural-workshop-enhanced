# -*- coding: utf-8 -*-
"""Stagehand: run the show from the script, a line at a time.

A small stage with props standing on marks -- a chair, a table, a lamp,
a crate, a plant, a barrel -- and an actor who wanders about. The
script comes up a line at a time and each line is a job:

* "Move the lamp behind the chair." -- drag the prop to the mark;
* "Put the spotlight on the barrel." -- click the prop;
* "Cue the lights." -- press the key the cue starts with: L lights,
  C curtain, M music, S smoke, T thunder.

Left, right, behind and in front are always as the audience sees them,
from the middle of the house. Some lines wait for something: "When the
bell rings twice, ...", "On the drum, ...", "When the actor reaches the
table, ...". Those have to be done in the moment after it happens --
not before, and not late.

The ladder:

* rungs 1-3: two lines, three props; moves and key cues that name
  their key;
* rungs 4-6: the spotlight; lines that wait for the bell;
* rungs 7-9: the camera cuts between seats in the house; lines that
  wait for the actor;
* rungs 10-12: bells that ring the wrong number of times first, and
  cues that no longer name their key;
* rungs 13-15: a camera backstage, where left and right are the other
  way round; the drum, and a whistle that is not the drum;
* rungs 16-19: quicker cuts, shorter moments;
* from rung 20: a line more every few rungs, and less time for each.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec
from .i18n import _

KEY = H.KEYS                   # ports 14-18: L, C, M, S, T
CUES = (_('lights'), _('curtain'), _('music'), _('smoke'), _('thunder'))
LETTERS = 'LCMST'
PORTS = H.KEYS + 5
EVENTS = tuple(range(PORTS))

PROPS = (_('chair'), _('table'), _('lamp'), _('crate'), _('plant'),
         _('barrel'))
COLS, ROWS, GAP = 5, 3, 2.2
RELS = {'left': (-1, 0), 'right': (1, 0), 'behind': (0, -1),
        'front': (0, 1)}
REL_WORDS = {'left': _('to the left of'), 'right': _('to the right of'),
             'behind': _('behind'), 'front': _('in front of')}
TIMES = (_('once'), _('twice'), _('three times'), _('four times'))
RING = 0.38                    # seconds between rings
REACH = 34.0                   # how near a prop the pointer has to be
LOOK: Vec = (0.0, 0.6, 0.0)
#: The seats: centre, left box, right box, balcony, and backstage.
CAMS: Tuple[Tuple[Vec, float], ...] = (
    ((0.0, 4.0, 12.0), 640.0), ((-9.0, 4.5, 8.0), 640.0),
    ((9.0, 4.5, 8.0), 640.0), ((0.0, 10.0, 7.5), 660.0),
    ((0.0, 4.5, -12.0), 640.0))
BELL, DRUM, WHISTLE, DONE, BUZZ, TUNE, STEP = range(7)
PATCHES = ('bell', 'growl', 'flute', 'glass', 'brass', 'pluck', 'wood')


class Grade(NamedTuple):
    rung: int
    lines: int
    props: int
    spot: bool
    waits: Tuple[str, ...]     # what a line may wait for
    decoy: bool
    named: bool                # key cues say which key
    cams: Tuple[int, ...]
    cut: float
    window: float              # how long the moment lasts
    pace: float                # seconds for a line that does not wait


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    waits = ()
    if r >= 4:
        waits += ('bell',)
    if r >= 7:
        waits += ('actor',)
    if r >= 13:
        waits += ('drum',)
    return Grade(
        rung=r,
        lines=(2 if r < 4 else 3 if r < 7 else 4 if r < 13 else 5 if r < 20
               else 6 + top // 3),
        props=3 if r < 4 else 4 if r < 7 else 5 if r < 13 else 6,
        spot=r >= 4, waits=waits, decoy=r >= 10, named=r < 10,
        cams=((0,) if r < 7 else (0, 1, 2, 3) if r < 13 else (0, 1, 2, 3, 4)),
        cut=(0.0 if r < 7 else 6.0 if r < 13 else 4.5 if r < 16 else 3.5
             if r < 20 else max(2.0, 3.2 - 0.05 * top)),
        window=(2.2 if r < 10 else 1.8 if r < 16 else 1.4 if r < 20
                else max(0.7, 1.3 - 0.03 * top)),
        pace=(14.0 if r < 4 else 12.0 if r < 10 else 10.0 if r < 20
              else max(5.0, 9.5 - 0.15 * top)))


class Line(NamedTuple):
    kind: str                  # 'move', 'spot' or 'key'
    text: str
    prop: int = -1
    mark: Tuple[int, int] = (0, 0)   # where a move ends
    key: int = -1
    wait: str = ''             # '', 'bell', 'drum' or 'actor'
    count: int = 0             # rings
    decoy: int = 0             # rings of a false bell first, or 1 for a whistle
    to: int = -1               # the prop the actor walks to
    via: int = -1              # ... after passing this one


class Show(NamedTuple):
    level: Grade
    props: Tuple[int, ...]     # which prop each one is
    marks: Tuple[Tuple[int, int], ...]
    lines: Tuple[Line, ...]
    cuts: Tuple[Tuple[float, int], ...]
    seconds: float
    seed: int


def _cap(words: str) -> str:
    return words[:1].upper() + words[1:]


def spot_of(mark: Tuple[float, float]) -> Tuple[float, float]:
    """The (x, z) of a mark; rows run from the back to the front."""
    return (mark[0] - (COLS - 1) / 2.0) * GAP, \
        (mark[1] - (ROWS - 1) / 2.0) * GAP


def _build(level: Grade, draw: random.Random) -> Optional[Show]:
    kinds = draw.sample(range(len(PROPS)), level.props)
    cells = draw.sample([(c, r) for c in range(COLS) for r in range(ROWS)],
                        level.props)
    at = list(cells)
    lines: List[Line] = []
    seconds = 0.0
    last = ''
    for _n in range(level.lines * 8):
        if len(lines) == level.lines:
            break
        options = ['move', 'move', 'key'] + (['spot'] if level.spot else [])
        kind = draw.choice([k for k in options if k != last] or options)
        wait, count, decoy, to, via = '', 0, 0, -1, -1
        if kind != 'move' and level.waits and draw.random() < 0.7:
            wait = draw.choice(level.waits)
        head = ''
        if wait == 'bell':
            count = draw.randint(1, 2 if level.rung < 10 else 3)
            if level.decoy and draw.random() < 0.7:
                decoy = draw.choice([n for n in (1, 2, 3) if n != count])
            head = _('When the bell rings %s, ') % TIMES[count - 1]
        elif wait == 'drum':
            decoy = 1 if draw.random() < 0.7 else 0
            head = _('On the drum, ')
        elif wait == 'actor':
            to = draw.randrange(level.props)
            others = [p for p in range(level.props) if p != to]
            via = draw.choice(others) if level.decoy else -1
            head = _('When the actor reaches the %s, ') % PROPS[kinds[to]]
        if kind == 'move':
            p = draw.randrange(level.props)
            picks = [(a, rel) for a in range(level.props) if a != p
                     for rel in RELS]
            draw.shuffle(picks)
            for a, rel in picks:
                d = RELS[rel]
                goal = (at[a][0] + d[0], at[a][1] + d[1])
                if 0 <= goal[0] < COLS and 0 <= goal[1] < ROWS and \
                        goal not in at:
                    break
            else:
                continue
            at[p] = goal
            body = _('move the %s %s the %s.') % (
                PROPS[kinds[p]], REL_WORDS[rel], PROPS[kinds[a]])
            line = Line('move', _cap(body), p, goal)
            seconds += level.pace
        elif kind == 'spot':
            p = draw.randrange(level.props)
            if wait == 'actor' and p == to:
                continue
            body = _('put the spotlight on the %s.') % PROPS[kinds[p]]
            line = Line('spot', head + body if head else _cap(body),
                        p, wait=wait, count=count, decoy=decoy, to=to,
                        via=via)
        else:
            k = draw.randrange(len(CUES))
            body = (_('cue the %s: press %s.') % (CUES[k], LETTERS[k])
                    if level.named else _('cue the %s.') % CUES[k])
            line = Line('key', head + body if head else _cap(body),
                        key=k, wait=wait, count=count, decoy=decoy, to=to,
                        via=via)
        if kind != 'move':
            seconds += level.pace if not wait else 14.0
        lines.append(line)
        last = kind
    if len(lines) < level.lines:
        return None
    cuts, t, cam = [], 0.0, 0
    while level.cut and t < seconds:
        t += level.cut * draw.uniform(0.8, 1.25)
        cam = draw.choice([c for c in level.cams if c != cam])
        cuts.append((t, cam))
    return Show(level, tuple(kinds), tuple(cells), tuple(lines), tuple(cuts),
                seconds, draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Show:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _try in range(60):
        show = _build(level, random.Random(draw.getrandbits(32)))
        if show is not None and play(show)[0]:
            return show
    raise RuntimeError('no show for rung %d' % rung)


class Run(H.HandRun):
    def __init__(self, show: Show) -> None:
        super().__init__(show.seconds)
        self.show, self.level = show, show.level
        self.at = list(show.marks)
        self.line_no = -1
        self.opens: Optional[float] = None    # when the moment starts
        self.due = 0.0                         # when the line is lost
        self.pending: List[Tuple[float, float, int, float, float]] = []
        self.drag: Optional[int] = None
        self.held_at = (0.0, 0.0)              # where a dragged prop is
        self.pressed = (0.0, 0.0)              # where the button went down
        self.lit: Optional[int] = None         # the prop in the spotlight
        self.on = [False] * len(CUES)
        self.actor = (-6.5, 2.0)
        self.path: List[Tuple[float, float]] = []
        self.walking = False                   # on the way to a cue
        self.idle = random.Random(show.seed)
        self.cut_no = 0
        self.cam = 0
        self._begin()

    # --- the picture
    def view(self):
        eye, focal = CAMS[self.cam]
        return H.lens(eye, LOOK, focal, 500.0, 285.0)

    def place(self, p: int) -> Tuple[float, float]:
        if self.drag == p:
            return self.held_at
        return spot_of(self.at[p])

    def body(self, p: int):
        x, z = self.place(p)
        return self.view().see((x, 0.7, z))

    def over(self) -> Optional[int]:
        """The prop under the pointer."""
        best, near = None, REACH
        for p in range(len(self.at)):
            q = self.body(p)
            if q is None:
                continue
            d = math.hypot(self.hand.x - q[0], self.hand.y - q[1])
            if d < near:
                best, near = p, d
        return best

    @property
    def line(self) -> Optional[Line]:
        lines = self.show.lines
        return lines[self.line_no] if 0 <= self.line_no < len(lines) \
            else None

    def open(self) -> bool:
        """Whether the current line may be done right now."""
        return self.opens is not None and self.t >= self.opens

    # --- lines
    def _begin(self) -> None:
        self.line_no += 1
        line = self.line
        if line is None:
            self.result = (True, _('The show went off without a hitch'))
            return
        t, level = self.t, self.level
        self.walking = False
        if not line.wait:
            self.opens, self.due = t, t + level.pace
        elif line.wait == 'bell':
            at = t + 1.2
            if line.decoy:
                for k in range(line.decoy):
                    self.pending.append((at + k * RING, 0.3, BELL, 988.0,
                                         0.55))
                at += line.decoy * RING + 1.4
            for k in range(line.count):
                self.pending.append((at + k * RING, 0.3, BELL, 988.0, 0.55))
            self.opens = at + (line.count - 1) * RING
            self.due = self.opens + max(level.window, RING + 0.6)
        elif line.wait == 'drum':
            at = t + 1.2
            if line.decoy:
                self.pending.append((at, 0.3, WHISTLE, 1568.0, 0.4))
                at += 1.3
            self.pending.append((at, 0.4, DRUM, 62.0, 0.7))
            self.opens, self.due = at, at + level.window
        else:
            self.path = []
            if line.via >= 0:
                self.path.append(self._beside(line.via))
            self.path.append(self._beside(line.to))
            self.walking = True
            self.opens, self.due = None, t + 60.0
        self.pending.sort()

    def _beside(self, p: int) -> Tuple[float, float]:
        x, z = spot_of(self.at[p])
        return x + 0.9, z + 0.35

    def _done(self) -> None:
        for j, semis in enumerate((0, 5)):
            self.note(0.2, 660.0 * 2 ** (semis / 12.0), DONE, 0.4,
                      at=self.t + 0.08 * j)
        self._begin()

    def _fail(self, why: str) -> None:
        self.note(0.4, 110.0, BUZZ, 0.5)
        self.result = (False, why)

    # --- the hand and the keys
    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        p = self.over()
        self.pressed = (self.hand.x, self.hand.y)
        if p is not None:
            self.drag = p
            self.held_at = spot_of(self.at[p])

    def release(self) -> None:
        if not self.hand.down:
            return
        self.hand.down = False
        p, self.drag = self.drag, None
        if self.result is not None or p is None:
            return
        line = self.line
        if math.hypot(self.hand.x - self.pressed[0],
                      self.hand.y - self.pressed[1]) < 8.0:
            # Let go where it was pressed: a click, so the spotlight.
            self.lit = p
            self.note(0.1, 1200.0, DONE, 0.3)
            if line.kind != 'spot':
                return
            if p != line.prop:
                return self._fail(_('The spotlight went on the wrong prop'))
            if not self.open():
                return self._fail(_('Too early'))
            return self._done()
        x, z = self.held_at
        mark = (int(round(x / GAP + (COLS - 1) / 2.0)),
                int(round(z / GAP + (ROWS - 1) / 2.0)))
        mx, mz = spot_of(mark)
        if not (0 <= mark[0] < COLS and 0 <= mark[1] < ROWS) or \
                mark in self.at or math.hypot(x - mx, z - mz) > 1.0:
            return                           # it goes back where it was
        self.at[p] = mark
        self.note(0.08, 200.0, STEP, 0.5)
        if line.kind == 'move' and self.at[line.prop] == line.mark:
            self._done()

    def key(self, k: int) -> None:
        line = self.line
        if self.result is not None or line is None:
            return
        self.on[k] = not self.on[k]
        if k == 4:
            self.note(0.9, 55.0, DRUM, 0.35)
        elif k == 2:
            for j, semis in enumerate((0, 4, 7, 12)):
                self.note(0.18, 392.0 * 2 ** (semis / 12.0), TUNE, 0.35,
                          at=self.t + 0.12 * j)
        if line.kind != 'key' or k != line.key:
            return self._fail(_('That was the wrong cue'))
        if not self.open():
            return self._fail(_('Too early'))
        self._done()

    # --- the clock
    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        cuts = self.show.cuts
        while self.cut_no < len(cuts) and cuts[self.cut_no][0] <= self.t:
            self.cam = cuts[self.cut_no][1]
            self.cut_no += 1
        while self.pending and self.pending[0][0] <= self.t:
            at, dur, voice, freq, gain = self.pending.pop(0)
            self.note(dur, freq, voice, gain)
        if self.drag is not None and math.hypot(
                self.hand.x - self.pressed[0],
                self.hand.y - self.pressed[1]) >= 8.0:
            spot = self.view().on_floor(self.hand.x, self.hand.y)
            if spot is not None:
                lim_x, lim_z = COLS * GAP / 2 + 1, ROWS * GAP / 2 + 1
                self.held_at = (max(-lim_x, min(lim_x, spot[0])),
                                max(-lim_z, min(lim_z, spot[1])))
        self._walk(dt)
        if self.result is None and self.t >= self.due:
            self._fail(_('Missed the cue'))

    def _walk(self, dt: float) -> None:
        if not self.path:
            if self.walking:
                if self.opens is None:
                    self.opens = self.t
                    self.due = self.t + self.level.window + 0.4
                return
            if self.level.rung < 4:
                return
            self.path.append((self.idle.uniform(-5, 5),
                              self.idle.uniform(-2.6, 3.0)))
        tx, tz = self.path[0]
        x, z = self.actor
        d = math.hypot(tx - x, tz - z)
        speed = 2.4 if self.walking else 1.2
        if d <= speed * dt:
            self.actor = (tx, tz)
            self.path.pop(0)
            if self.walking:
                self.note(0.05, 150.0, STEP, 0.3)
        else:
            self.actor = (x + (tx - x) / d * speed * dt,
                          z + (tz - z) / d * speed * dt)


def act(run: Run, port: int) -> None:
    if port < H.PRESS:
        run.hand.move(port)
    elif port == H.PRESS:
        run.press()
    elif port == H.RELEASE:
        run.release()
    elif port < PORTS:
        run.key(port - KEY)


def autopilot(run: Run) -> List[int]:
    """Do the current line, in its moment: one port a step."""
    line = run.line
    if run.result is not None or line is None:
        return []
    hand = run.hand
    if line.kind == 'key':
        if hand.down:
            return [H.RELEASE]
        return [KEY + line.key] if run.open() else []
    if hand.down and run.drag != line.prop:
        return [H.RELEASE]
    if not hand.down:
        q = run.body(line.prop)
        if q is None:
            return []
        move = H.toward(hand, q[0], q[1], tol=5.0)
        if move is not None:
            return [move]
        if run.over() != line.prop:
            return []
        if line.kind == 'spot' and not run.open():
            return []
        return [H.PRESS]
    if line.kind == 'spot':
        return [H.RELEASE]
    x, z = spot_of(line.mark)
    q = run.view().see((x, 0.0, z))
    if q is None:
        return []
    hx, hz = run.held_at
    if math.hypot(hx - x, hz - z) < 0.45:
        return [H.RELEASE]
    move = H.toward(hand, q[0], q[1], tol=2.6)
    return [move] if move is not None else [H.RELEASE]


def play(show: Show, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(show), pilot, EVENTS, act, dt)
