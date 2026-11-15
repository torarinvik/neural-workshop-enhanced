# -*- coding: utf-8 -*-
"""Kitchen: one cook, a row of stations, and orders coming in.

Orders arrive as tickets, each a dish of one to three parts -- a
chopped onion, a cooked tomato -- and each with its patience running
down. The cook carries one thing at a time and walks between
stations; sending the cook to a station does the obvious thing there:

* a **crate** hands over a raw ingredient (hands empty);
* a **board** takes a raw ingredient and the cook chops it, staying
  until it is done; with empty hands it hands back what is on it;
* a **stove** takes a chopped ingredient and cooks it on its own --
  done after a while, burnt a while after that;
* a **plate** takes a chopped or cooked part, hands the plate over to
  empty hands, or takes back a carried plate;
* the **pass** serves a carried plate that matches a ticket;
* the **bin** takes whatever is carried.

The ladder:

* rungs 1-3: one-part dishes, one stove, slow tickets;
* rungs 4-6: two stoves, some dishes only chopped;
* rungs 7-9: two-part dishes, two plates;
* rungs 10-12: pans burn sooner, more tickets;
* rungs 13-15: three-part dishes, a second board;
* from rung 16: three stoves, quicker tickets, less patience every rung.

A shift passes when every ticket is served (one may lapse below rung
10). Clocked: the pans cook and the tickets wait for no one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from collections import Counter
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

FOODS = ('tomato', 'onion', 'mushroom', 'fish')
COOKABLE = {'tomato': True, 'onion': True, 'mushroom': True, 'fish': True}
RAW, CHOPPED, COOKED, BURNT = 'raw', 'chopped', 'cooked', 'burnt'
CRATE, BOARD, STOVE, PLATE, PASS, BIN = (
    'crate', 'board', 'stove', 'plate', 'pass', 'bin')
#: Fixed port numbering: four crates, two boards, three stoves, two
#: plates, the pass and the bin.
SLOTS = ((CRATE, 0), (CRATE, 1), (CRATE, 2), (CRATE, 3), (BOARD, 0),
         (BOARD, 1), (STOVE, 0), (STOVE, 1), (STOVE, 2), (PLATE, 0),
         (PLATE, 1), (PASS, 0), (BIN, 0))
PORTS = len(SLOTS)
WALK = 6.0            # units a second
CHOP = 1.6            # seconds of chopping
COOK = 4.0            # seconds on the stove until done


class Grade(NamedTuple):
    rung: int
    parts: int           # most parts in a dish
    foods: int           # ingredients in play
    boards: int
    stoves: int
    plates: int
    tickets: int
    gap: float           # seconds between tickets
    patience: float      # seconds per ticket, plus per part
    hold: float          # seconds a done pan waits before it burns
    lapse: int           # tickets allowed to lapse
    chopped_only: float  # share of parts served chopped, not cooked


def grade(rung: int) -> Grade:
    rung = max(1, int(rung))
    top = max(0, rung - 16)
    parts = 1 if rung < 7 else 2 if rung < 13 else 3
    return Grade(
        rung, parts,
        foods=2 if rung < 4 else 3 if rung < 10 else 4,
        boards=1 if rung < 13 else 2,
        stoves=1 if rung < 4 else 2 if rung < 16 else 3,
        plates=1 if rung < 7 else 2,
        tickets=(3 if rung < 4 else 4 if rung < 10 else 5 if rung < 16
                 else 6 + top // 5),
        gap=max(11.0, (20.0 if rung < 7 else 24.0 if rung < 13 else 22.0)
                - 0.8 * top),
        patience=max(20.0, (44.0 if rung < 16 else 36.0) - 1.3 * top),
        hold=5.0 if rung < 10 else 3.5 if rung < 16 else max(2.2,
                                                             3.0 - 0.05 * top),
        lapse=1 if rung < 10 else 0,
        chopped_only=0.0 if rung < 4 else 0.3)


class Station(NamedTuple):
    kind: str
    index: int
    port: int
    x: float
    y: float
    food: Optional[str] = None     # crates only


class Ticket(NamedTuple):
    parts: Tuple[Tuple[str, str], ...]   # (food, stage), sorted
    due: float                           # arrival time
    patience: float


class Shift(NamedTuple):
    level: Grade
    stations: List[Station]
    tickets: List[Ticket]
    start: Tuple[float, float]


W, H = 12.0, 7.0      # the kitchen floor, in walking units


def layout(level: Grade, foods: List[str]) -> List[Station]:
    """Crates along the left wall, boards and stoves along the top,
    plates and the pass down the right, the bin bottom right."""
    out = []
    for k, food in enumerate(foods):
        out.append(Station(CRATE, k, k, 0.8, H - 1.0 - k * 1.55, food))
    tops = [(BOARD, k) for k in range(level.boards)] + \
        [(STOVE, k) for k in range(level.stoves)]
    for j, (kind, k) in enumerate(tops):
        x = 2.8 + j * (7.0 / max(1, len(tops) - 1) if len(tops) > 1 else 0)
        out.append(Station(kind, k, SLOTS.index((kind, k)), x, H - 0.75))
    for k in range(level.plates):
        out.append(Station(PLATE, k, SLOTS.index((PLATE, k)), W - 0.8,
                           H - 2.0 - k * 1.6))
    out.append(Station(PASS, 0, SLOTS.index((PASS, 0)), W - 0.8, 1.0))
    out.append(Station(BIN, 0, SLOTS.index((BIN, 0)), 5.5, 0.75))
    return out


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Shift:
    """A shift the reference cook gets through."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(25):
        shift = _build(level, draw)
        best = best or shift
        if play(shift)[0]:
            return shift
    return best


def _build(level: Grade, draw: random.Random) -> Shift:
    foods = draw.sample(FOODS, level.foods)
    stations = layout(level, sorted(foods, key=FOODS.index))
    tickets = []
    t = 2.0
    for k in range(level.tickets):
        n = draw.randint(max(1, level.parts - 1), level.parts)
        parts = []
        for _p in range(n):
            food = draw.choice(foods)
            stage = CHOPPED if draw.random() < level.chopped_only else COOKED
            parts.append((food, stage))
        tickets.append(Ticket(tuple(sorted(parts)), round(t, 1),
                              round(level.patience + 12 * n, 1)))
        t += draw.uniform(0.8, 1.2) * level.gap
    return Shift(level, stations, tickets, (W / 2, H / 2))


# --- the run ----------------------------------------------------------------------

class Pan(NamedTuple):
    food: str
    since: float          # when it went on


class Run:
    """One shift in motion."""

    def __init__(self, shift: Shift) -> None:
        self.shift = shift
        self.level = shift.level
        self.t = 0.0
        self.x, self.y = shift.start
        self.target: Optional[Station] = None
        self.held: Optional[object] = None    # (food, stage) or ('plate', [...])
        self.boards: Dict[int, Optional[List]] = {
            s.index: None for s in shift.stations if s.kind == BOARD}
        self.stoves: Dict[int, Optional[Pan]] = {
            s.index: None for s in shift.stations if s.kind == STOVE}
        self.plates: Dict[int, Optional[List[Tuple[str, str]]]] = {
            s.index: [] for s in shift.stations if s.kind == PLATE}
        self.open: List[int] = []         # ticket indices waiting
        self.served: List[int] = []
        self.lapsed: List[int] = []
        self.arrived = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.chopping: Optional[int] = None
        self.by_port = {s.port: s for s in shift.stations}
        self.flash: List[Tuple[float, str, float, float]] = []
        self.burnt = 0

    # --- the agent's one action
    def send(self, port: int) -> None:
        if self.result is None and port in self.by_port:
            self.target = self.by_port[port]
            self.chopping = None

    def station(self, kind: str, index: int = 0) -> Optional[Station]:
        for s in self.shift.stations:
            if s.kind == kind and s.index == index:
                return s
        return None

    def pan_stage(self, k: int, t: Optional[float] = None) -> Optional[str]:
        pan = self.stoves.get(k)
        if pan is None:
            return None
        t = self.t if t is None else t
        age = t - pan.since
        if age < COOK:
            return CHOPPED
        if age < COOK + self.level.hold:
            return COOKED
        return BURNT

    def ticket_left(self, k: int) -> float:
        tk = self.shift.tickets[k]
        return tk.due + tk.patience - self.t

    def step(self, dt: float) -> None:
        if self.result is not None:
            return
        self.t += dt
        tickets = self.shift.tickets
        while self.arrived < len(tickets) and tickets[self.arrived].due <= self.t:
            self.open.append(self.arrived)
            self.arrived += 1
        for k in list(self.open):
            if self.ticket_left(k) <= 0:
                self.open.remove(k)
                self.lapsed.append(k)
        for k, pan in self.stoves.items():
            if pan is not None and self.pan_stage(k) == BURNT and \
                    self.t - dt - pan.since < COOK + self.level.hold:
                self.burnt += 1
        # Walking.
        if self.target is not None:
            dx, dy = self.target.x - self.x, self.target.y - self.y
            dist = math.hypot(dx, dy)
            stride = WALK * dt
            if dist <= stride:
                self.x, self.y = self.target.x, self.target.y
                here, self.target = self.target, None
                self._use(here)
            else:
                self.x += dx / dist * stride
                self.y += dy / dist * stride
        # Chopping.
        if self.chopping is not None:
            board = self.boards[self.chopping]
            if board is not None and board[1] < CHOP:
                board[1] += dt
                if board[1] >= CHOP:
                    self.chopping = None
        if len(self.lapsed) > self.level.lapse:
            self.result = (False, _('A ticket ran out of patience'))
        elif len(self.served) + len(self.lapsed) == len(tickets):
            self.result = (True, _('Shift done: %d of %d served')
                           % (len(self.served), len(tickets)))

    def _note(self, words: str, at: Station) -> None:
        self.flash.append((self.t, words, at.x, at.y))
        del self.flash[:-6]

    def _use(self, at: Station) -> None:
        held = self.held
        if at.kind == CRATE:
            if held is None:
                self.held = (at.food, RAW)
        elif at.kind == BOARD:
            board = self.boards[at.index]
            if held is not None and held[0] != 'plate' and held[1] == RAW \
                    and board is None:
                self.boards[at.index] = [held[0], 0.0]
                self.held = None
                self.chopping = at.index
            elif held is None and board is not None:
                if board[1] >= CHOP:
                    self.held = (board[0], CHOPPED)
                    self.boards[at.index] = None
                else:
                    self.chopping = at.index
        elif at.kind == STOVE:
            pan = self.stoves[at.index]
            if held is not None and held[0] != 'plate' and \
                    held[1] == CHOPPED and pan is None:
                self.stoves[at.index] = Pan(held[0], self.t)
                self.held = None
            elif held is None and pan is not None:
                self.held = (pan.food, self.pan_stage(at.index))
                self.stoves[at.index] = None
        elif at.kind == PLATE:
            plate = self.plates[at.index]
            if held is None:
                if plate:
                    self.held = ('plate', tuple(plate))
                    self.plates[at.index] = []
            elif held[0] == 'plate':
                if not plate:
                    self.plates[at.index] = list(held[1])
                    self.held = None
            elif held[1] in (CHOPPED, COOKED) and len(plate) < 3:
                plate.append(held)
                self.held = None
        elif at.kind == PASS:
            if held is not None and held[0] == 'plate':
                dish = tuple(sorted(held[1]))
                match = [k for k in self.open
                         if self.shift.tickets[k].parts == dish]
                if match:
                    k = min(match, key=self.ticket_left)
                    self.open.remove(k)
                    self.served.append(k)
                    self.held = None
                    self._note(_('served!'), at)
                else:
                    self._note(_('no such ticket'), at)
        elif at.kind == BIN:
            if held is not None:
                self.held = None
                self._note(_('binned'), at)

    def walk_time(self, a: Tuple[float, float], s: Station) -> float:
        return math.hypot(s.x - a[0], s.y - a[1]) / WALK


# --- the reference cook -----------------------------------------------------------

def _plan_plates(run: Run) -> Dict[int, int]:
    """Plate index -> the ticket it is being built for."""
    out: Dict[int, int] = {}
    tickets = run.shift.tickets
    taken = set()
    plates = dict(run.plates)
    held = run.held
    for p, plate in sorted(plates.items()):
        have = Counter(plate)
        best = None
        for k in sorted(run.open, key=run.ticket_left):
            if k in taken:
                continue
            want = Counter(tickets[k].parts)
            if not have - want:
                best = k
                break
        if best is not None:
            out[p] = best
            taken.add(best)
    if held is not None and held[0] == 'plate':
        pass
    return out


def autopilot(run: Run) -> List[int]:
    """One station to walk to, when the cook is free to choose."""
    if run.result is not None or run.target is not None:
        return []
    if run.chopping is not None:
        board = run.boards[run.chopping]
        if board is not None and board[1] < CHOP and not _pan_urgent(run):
            return []
    port = _choose(run)
    return [] if port is None else [port]


def _pan_urgent(run: Run) -> bool:
    here = (run.x, run.y)
    for k, pan in run.stoves.items():
        if pan is None:
            continue
        left = pan.since + COOK + run.level.hold - run.t
        if left < run.walk_time(here, run.station(STOVE, k)) + 1.2:
            return True
    return False


def _needs(run: Run) -> Tuple[Counter, Dict[int, int]]:
    """Parts still wanted across the plates' tickets (and the next
    ticket for an empty plate), less what is already under way."""
    tickets = run.shift.tickets
    assign = _plan_plates(run)
    want: Counter = Counter()
    for p, k in assign.items():
        want += Counter(tickets[k].parts) - Counter(run.plates[p])
    # Under way: on boards, stoves, in hands.
    have: Counter = Counter()
    for b in run.boards.values():
        if b is not None:
            have[(b[0], CHOPPED)] += 1
            have[(b[0], COOKED)] += 1
    for k, pan in run.stoves.items():
        if pan is not None and run.pan_stage(k) != BURNT:
            have[(pan.food, COOKED)] += 1
    if run.held is not None and run.held[0] != 'plate':
        f, stage = run.held
        if stage in (RAW, CHOPPED):
            have[(f, CHOPPED)] += 1
            have[(f, COOKED)] += 1
        elif stage == COOKED:
            have[(f, COOKED)] += 1
    return want, assign


def _choose(run: Run) -> Optional[int]:
    tickets = run.shift.tickets
    held = run.held
    want, assign = _needs(run)
    S = run.station
    # A burning or done pan first, if the hands are free.
    if held is None:
        for k, pan in sorted(run.stoves.items()):
            if pan is None:
                continue
            stage = run.pan_stage(k)
            if stage == BURNT:
                return S(STOVE, k).port
            if stage == COOKED:
                return S(STOVE, k).port
    if held is not None and held[0] == 'plate':
        dish = tuple(sorted(held[1]))
        if any(tickets[k].parts == dish for k in run.open):
            return S(PASS).port
        return S(BIN).port
    if held is not None:
        food, stage = held
        if stage == BURNT:
            return S(BIN).port
        if stage == RAW:
            for k, b in sorted(run.boards.items()):
                if b is None:
                    return S(BOARD, k).port
            return None
        # Chopped or cooked: onto a plate that wants it, or on to cook.
        for p, k in sorted(assign.items()):
            missing = Counter(tickets[k].parts) - Counter(run.plates[p])
            if missing[(food, stage)] > 0:
                return S(PLATE, p).port
        if stage == CHOPPED:
            for k, pan in sorted(run.stoves.items()):
                if pan is None:
                    return S(STOVE, k).port
            return None
        return S(BIN).port
    # Hands empty. A finished plate to the pass.
    for p, k in sorted(assign.items()):
        if Counter(run.plates[p]) == Counter(tickets[k].parts) and \
                run.plates[p]:
            return S(PLATE, p).port
    # A chopped part waiting on a board.
    for k, b in sorted(run.boards.items()):
        if b is not None and b[1] >= CHOP:
            return S(BOARD, k).port
        if b is not None and b[1] < CHOP:
            return S(BOARD, k).port
    # Fetch what is wanted and not under way, earliest ticket first.
    gone = Counter()
    for bd in run.boards.values():
        if bd is not None:
            gone[bd[0]] += 1
    for k, pan in run.stoves.items():
        if pan is not None and run.pan_stage(k) != BURNT:
            gone[pan.food] += 1
    order = []
    for p, k in sorted(assign.items(), key=lambda pk: run.ticket_left(pk[1])):
        missing = Counter(tickets[k].parts) - Counter(run.plates[p])
        for (food, stage), n in missing.items():
            order += [(food, stage)] * n
    free_board = any(b is None for b in run.boards.values())
    for food, stage in order:
        if gone[food] > 0:
            gone[food] -= 1
            continue
        if not free_board:
            return None
        if stage == COOKED and all(p is not None for p in run.stoves.values()) \
                and sum(1 for b in run.boards.values() if b is not None):
            continue
        for s in run.shift.stations:
            if s.kind == CRATE and s.food == food:
                return s.port
    # A stale plate nobody wants: clear it.
    for p, plate in run.plates.items():
        if plate and p not in assign:
            return S(PLATE, p).port
    return None


def apply(run: Run, port: int) -> None:
    run.send(port)


def play(shift: Shift, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(shift)
    while run.result is None:
        for port in pilot(run):
            apply(run, port)
        run.step(dt)
        if run.t > 600:
            return False, 'stalled'
    return run.result
