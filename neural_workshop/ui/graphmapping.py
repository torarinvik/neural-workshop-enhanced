# -*- coding: utf-8 -*-
"""Graph Mapping: are these two networks the same one, redrawn?

Two graphs, side by side, laid out differently. The question is
whether one can be mapped onto the other — every dot in the left
matching a dot in the right with exactly the same connections. This is
the structure-mapping problem: the surface looks nothing alike, so the
answer has to come from the relations rather than from the picture.

Nothing is labelled, on purpose. Labels shared between the panels would
turn the task into checking a list of pairs; without them there is no
way through but to find the correspondence.

The two ways a pair can differ are worth keeping apart, because they
ask for different work:

* Connection counts differ. Tally the lines meeting each dot on both
  sides and compare the tallies — mechanical, and always decisive.
* Connection counts match (``GRAPH_MAP_SUBTLE``). Every tally agrees
  and the networks are still not the same, so counting tells you
  nothing and the structure has to be walked.

Neither kind ever changes the number of dots or the number of lines,
so counting those can never answer a trial.

The second kind runs out at the bottom of the range. At four dots,
and at five once there are more than six lines, every profile of
connection counts describes exactly one network, so there is no second
one to reach — the option is not merely hard to satisfy there but
impossible. Rather than hand out the easier kind under the name of the
harder one, asking for it holds the size up to :data:`SUBTLE_FLOOR`,
where such a network exists.

Above that floor a partner always exists, though not for every base
graph: at six dots and a dense graph only four of the nine networks
have one. So a base that cannot be rewired is replaced rather than
settled for. If both ever fail anyway, the trial becomes an easier
mismatch — never a match, which would bend the run's balance between
the two answers — and the run says so at the end. It is never said
during a trial: which kind a mismatch is would give away that it is
one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from . import cursor, taskoptions
from ..i18n import _

#: The two answers.
SAME, DIFFERENT = 'same', 'different'

#: Most nodes a trial will ever show, however well the player does.
MAX_NODES = 10

#: Fewest, so a wrong answer cannot make the task trivial.
MIN_NODES = 4

#: Density name → lines per node.
DENSITY_FACTORS: Dict[str, float] = {
    'sparse': 1.1, 'medium': 1.4, 'dense': 1.8,
}

#: Never fill in more than this share of the connections a graph could
#: have. A nearly complete graph is both unreadable and almost always
#: isomorphic to any other, so there is nothing to decide.
MAX_FILL = 0.6

#: How hard to try before settling for an easier mismatch.
REWIRE_ATTEMPTS = 200

#: How many fresh base graphs to try before giving up on a mismatch.
#: Whether a mismatch of the kind asked for exists at all depends on
#: the base graph, not only on its size: at six dots and a dense graph
#: only four of the nine networks have a partner that keeps every
#: count. Trying one base and settling for the easier kind dropped out
#: of the count-keeping kind about half the time there; trying fresh
#: ones takes every reachable case to all of them.
BASE_ATTEMPTS = 20

#: Fewest dots that can carry a mismatch keeping every count, by
#: density. Below this there is no second network to reach: every
#: profile of connection counts describes exactly one network, so the
#: count-keeping mismatch is not merely hard to find but absent.
#:
#: Worked out by enumerating every connected graph of each size, and
#: re-derived from scratch by ``test_the_floor_is_where_the_networks
#: _run_out`` rather than trusted — change :data:`DENSITY_FACTORS` and
#: that test says so.
SUBTLE_FLOOR: Dict[str, int] = {'sparse': 5, 'medium': 6, 'dense': 6}


def subtle_floor(density: str) -> int:
    """Fewest dots at which a mismatch can keep every count."""
    return max(MIN_NODES, SUBTLE_FLOOR.get(density, 6))


class Pair(NamedTuple):
    """The two graphs a trial shows, and the truth about them."""

    first: 'Graph'
    second: 'Graph'
    #: Whether the two are the same network drawn differently.
    same: bool
    #: For a mismatch, whether it keeps every connection count — the
    #: kind tallying cannot answer. False for a match, which has no
    #: counts to keep, and for a mismatch that had to settle.
    subtle: bool


class Graph(NamedTuple):
    """A simple undirected graph: *size* nodes, numbered from zero.

    Edges are sorted ``(low, high)`` pairs, so two graphs holding the
    same connections compare equal whatever order they were built in.
    """

    size: int
    edges: Tuple[Tuple[int, int], ...]


# --- graph arithmetic -------------------------------------------------------
#
# Free functions rather than methods: they are the part worth testing
# on its own, and none of them touch the screen.


def edge(first: int, second: int) -> Tuple[int, int]:
    """The canonical form of the edge between two nodes."""
    return (first, second) if first < second else (second, first)


def adjacency(graph: Graph) -> List[Set[int]]:
    """Each node's neighbours."""
    neighbours: List[Set[int]] = [set() for _index in range(graph.size)]
    for first, second in graph.edges:
        neighbours[first].add(second)
        neighbours[second].add(first)
    return neighbours


def degrees(graph: Graph) -> List[int]:
    """How many lines meet each node, in node order."""
    return [len(near) for near in adjacency(graph)]


def connected(graph: Graph) -> bool:
    """True when every node can be reached from node zero."""
    if graph.size <= 1:
        return True
    neighbours = adjacency(graph)
    seen = {0}
    stack = [0]
    while stack:
        node = stack.pop()
        for other in neighbours[node]:
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return len(seen) == graph.size


def isomorphic(first: Graph, second: Graph) -> bool:
    """True when *first* can be relabelled into *second*.

    Cheap invariants first — node count, line count, then the sorted
    degrees — and only when those all agree does it search for an
    actual mapping. The search assigns the busiest nodes first and
    keeps every pair already assigned consistent, which settles the
    sizes this task uses long before the factorial matters.
    """
    if first.size != second.size or len(first.edges) != len(second.edges):
        return False
    left = adjacency(first)
    right = adjacency(second)
    if sorted(len(near) for near in left) != sorted(len(near)
                                                    for near in right):
        return False

    order = sorted(range(first.size), key=lambda node: -len(left[node]))
    mapping: Dict[int, int] = {}
    taken: Set[int] = set()

    def extend(index: int) -> bool:
        if index == len(order):
            return True
        node = order[index]
        for candidate in range(second.size):
            if candidate in taken:
                continue
            if len(right[candidate]) != len(left[node]):
                continue
            # Every node already placed must agree about this one.
            if any((other in left[node]) != (image in right[candidate])
                   for other, image in mapping.items()):
                continue
            mapping[node] = candidate
            taken.add(candidate)
            if extend(index + 1):
                return True
            del mapping[node]
            taken.discard(candidate)
        return False

    return extend(0)


def relabel(graph: Graph, naming: Sequence[int]) -> Graph:
    """*graph* with node ``i`` renamed to ``naming[i]``."""
    return Graph(graph.size,
                 tuple(sorted(edge(naming[first], naming[second])
                              for first, second in graph.edges)))


def shuffled(graph: Graph, rng: random.Random) -> Graph:
    """*graph* with its nodes renamed at random."""
    naming = list(range(graph.size))
    rng.shuffle(naming)
    return relabel(graph, naming)


def edge_count(size: int, density: str) -> int:
    """How many lines a graph of *size* nodes gets at *density*.

    Never fewer than it takes to connect every node, and never more
    than :data:`MAX_FILL` of the connections available.
    """
    tree = max(0, size - 1)
    room = size * (size - 1) // 2 - tree
    wanted = int(round(size * DENSITY_FACTORS.get(density, 1.4)))
    return max(tree, min(wanted, tree + int(room * MAX_FILL)))


def random_graph(size: int, lines: int, rng: random.Random) -> Graph:
    """A connected graph with *size* nodes and *lines* lines.

    Built as a random spanning tree plus extra connections, so it is
    connected by construction — a graph in loose pieces reads as a
    mistake rather than as a puzzle.
    """
    nodes = list(range(size))
    rng.shuffle(nodes)
    edges = {edge(nodes[index], nodes[rng.randrange(index)])
             for index in range(1, size)}
    spare = [edge(first, second)
             for first in range(size) for second in range(first + 1, size)
             if edge(first, second) not in edges]
    rng.shuffle(spare)
    edges.update(spare[:max(0, lines - len(edges))])
    return Graph(size, tuple(sorted(edges)))


def _swap_partners(graph: Graph, rng: random.Random) -> Optional[Graph]:
    """Cross two lines over, which leaves every node's count alone.

    Taking ``a—b`` and ``c—d`` to ``a—d`` and ``c—b`` moves connections
    around without changing how many meet any node, so the result can
    only be told from the original by its shape.
    """
    if len(graph.edges) < 2:
        return None
    present = set(graph.edges)
    going, leaving = rng.sample(graph.edges, 2)
    (first, second), (third, fourth) = going, leaving
    # Both ways of reconnecting the four ends are worth trying; only
    # the ends are swapped, never the edges being taken out, which are
    # removed by the canonical form they were stored under.
    if rng.random() < 0.5:
        third, fourth = fourth, third
    if len({first, second, third, fourth}) < 4:
        return None
    fresh = (edge(first, fourth), edge(third, second))
    if any(pair in present for pair in fresh):
        return None
    present.discard(going)
    present.discard(leaving)
    present.update(fresh)
    return Graph(graph.size, tuple(sorted(present)))


def _move_a_line(graph: Graph, rng: random.Random) -> Optional[Graph]:
    """Move one line somewhere else, which does change the counts.

    The number of lines stays put, so the two panels still cannot be
    told apart by counting them.
    """
    present = set(graph.edges)
    spare = [edge(first, second)
             for first in range(graph.size)
             for second in range(first + 1, graph.size)
             if edge(first, second) not in present]
    if not present or not spare:
        return None
    present.discard(rng.choice(sorted(present)))
    present.add(rng.choice(spare))
    return Graph(graph.size, tuple(sorted(present)))


def rewired(graph: Graph, rng: random.Random,
            keep_degrees: bool) -> Optional[Graph]:
    """A connected graph that is *not* the same network as *graph*.

    Returns ``None`` when no such graph could be reached — at four
    nodes there are few enough connected graphs that a rewiring which
    keeps the counts often has nowhere to go.
    """
    change = _swap_partners if keep_degrees else _move_a_line
    for _attempt in range(REWIRE_ATTEMPTS):
        other = change(graph, rng)
        if other is None or not connected(other):
            continue
        if not isomorphic(graph, other):
            return other
    return None


def build_pair(size: int, lines: int, same: bool, subtle: bool,
               rng: random.Random) -> Pair:
    """Two graphs to show, and the truth about them.

    The answer comes back rather than going in, because a mismatch is
    not always reachable: below :data:`SUBTLE_FLOOR` no second network
    shares its connection counts, and at four dots there is barely a
    second network at all.

    A mismatch that has to keep the counts is tried against fresh base
    graphs before settling for one that does not, because whether a
    partner exists depends on the base and not only on the size. Only
    when no base yields one does it drop to the easier kind — never to
    a match, which would quietly bend the run's balance between the
    two answers. The pair reports which kind it ended up being, so a
    run that had to settle can say so afterwards.
    """
    if same:
        base = random_graph(size, lines, rng)
        return Pair(base, shuffled(base, rng), True, False)
    for keep_degrees in ((True, False) if subtle else (False,)):
        for _attempt in range(BASE_ATTEMPTS):
            base = random_graph(size, lines, rng)
            other = rewired(base, rng, keep_degrees=keep_degrees)
            if other is not None:
                return Pair(base, shuffled(other, rng), False, keep_degrees)
    # No second network at all at this size and density.
    base = random_graph(size, lines, rng)
    return Pair(base, shuffled(base, rng), True, False)


def ring_positions(size: int, rng: random.Random,
                   ) -> Tuple[Tuple[float, float], ...]:
    """Node positions around a circle, in fractions of a panel.

    The nodes go round in a random order at a random turn, with the
    radius nudged a little, so the same network drawn twice makes two
    different pictures — which is the whole difficulty.
    """
    order = list(range(size))
    rng.shuffle(order)
    turn = rng.uniform(0.0, math.tau)
    spots: List[Tuple[float, float]] = []
    for node in range(size):
        angle = turn + order[node] * math.tau / max(1, size)
        reach = 0.44 * rng.uniform(0.86, 1.0)
        spots.append((0.5 + reach * math.cos(angle),
                      0.5 + reach * math.sin(angle)))
    return tuple(spots)


class GraphMapping:
    """Show two graphs, take same/different, say whether it was right."""

    instance: Optional['GraphMapping'] = None

    def __init__(self) -> None:
        if GraphMapping.instance is not None:
            GraphMapping.instance.close()
        self.rng = random.Random()
        self.graphs: List[Graph] = []
        self.spots: List[Tuple[Tuple[float, float], ...]] = []
        self.really_same = True
        self.nodes = MIN_NODES
        self.trial = 0
        self.correct = 0
        self.settled_for = 0
        self.asked_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[bool, bool, float]] = []
        self.phase = 'ready'
        self._deck: List[bool] = []
        self._read_options()
        # After the options, not before: the waiting message depends on
        # them, and entering the task is exactly when a size that had
        # to come up is worth saying.
        self.message = self._ready_message()
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        GraphMapping.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.GRAPH_MAPPING)
        self.start_nodes = int(opts['GRAPH_MAP_NODES'])
        self.density = str(opts['GRAPH_MAP_DENSITY'])
        self.total_trials = int(opts['GRAPH_MAP_TRIALS'])
        self.subtle = bool(opts['GRAPH_MAP_SUBTLE'])
        self.exposure_ms = int(opts['GRAPH_MAP_EXPOSURE_MS'])
        self.adaptive = bool(opts['GRAPH_MAP_ADAPTIVE'])
        self.feedback = bool(opts['GRAPH_MAP_FEEDBACK'])
        self.nodes = self.clamped(self.start_nodes)

    def floor(self) -> int:
        """Fewest dots this run will go down to.

        Asking for mismatches that keep the counts holds the size up
        to where such a mismatch exists — below that the option cannot
        be honoured, and quietly handing out the easier kind instead
        would be the option failing in silence.
        """
        return subtle_floor(self.density) if self.subtle else MIN_NODES

    def clamped(self, nodes: int) -> int:
        """*nodes*, kept inside what this run can actually show."""
        return max(self.floor(), min(MAX_NODES, nodes))

    def open_options(self) -> None:
        taskoptions.open_task_options('graph_mapping',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        """Create the batch, the colours and the fixed labels."""
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.inkcolor = (fg, fg, fg, 255)
        self.dividercolor = (fg, fg, fg, 70)
        self.accent = (64, 96, 255, 255)
        self.batch = pyglet.graphics.Batch()
        # Nodes sit on top of the lines they end.
        self.line_group = pyglet.graphics.Group(order=0)
        self.node_group = pyglet.graphics.Group(order=1)
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Graph Mapping'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     Y / N or ← →'
              '     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(30),
            anchor_x='center', anchor_y='center')
        self.buttons: List[pyglet.text.Label] = []
        self._redraw()

    def relayout(self) -> None:
        """Rebuild at the window's current size, keeping the same pair."""
        self._build_chrome()

    def canvas(self) -> Tuple[float, float, float, float]:
        """The rectangle both graphs are drawn in: left, bottom, w, h."""
        window = state.window
        width = window.width * 0.90
        height = window.height * 0.54
        return ((window.width - width) / 2,
                from_bottom_edge(150), width, height)

    def panels(self) -> List[Tuple[float, float, float]]:
        """Centre and side of the square each graph is drawn in."""
        left, bottom, width, height = self.canvas()
        gap = width * 0.05
        half = (width - gap) / 2
        side = min(half, height)
        return [(left + half / 2, bottom + height / 2, side),
                (left + half + gap + half / 2, bottom + height / 2, side)]

    def _to_pixels(self, panel: int,
                   point: Tuple[float, float]) -> Tuple[float, float]:
        centre_x, centre_y, side = self.panels()[panel]
        return (centre_x + (point[0] - 0.5) * side,
                centre_y + (point[1] - 0.5) * side)

    def _button_rects(self) -> List[Tuple[float, float, float, float, str]]:
        window = state.window
        width = min(window.width * 0.22, window.width / 3.2)
        height = max(40.0, window.height * 0.07)
        gap = window.width * 0.04
        bottom = from_bottom_edge(84)
        left = (window.width - (width * 2 + gap)) / 2
        return [(left, bottom, width, height, SAME),
                (left + width + gap, bottom, width, height, DIFFERENT)]

    # --- a trial ---------------------------------------------------------

    def _reset(self) -> None:
        self.graphs = []
        self.spots = []
        self.trial = 0
        self.correct = 0
        self.settled_for = 0
        self.results = []
        self._deck = []
        self.phase = 'ready'
        self.message = self._ready_message()

    def _ready_message(self) -> str:
        """The waiting message, saying so if the size had to come up."""
        if self.subtle and self.start_nodes < self.floor():
            return _('Press Space to start — keeping the counts '
                     'needs %d dots') % self.floor()
        return _('Press Space to start')

    def _draw_answer(self) -> bool:
        """Whether the next pair should match.

        Dealt from a shuffled block of three of each rather than from a
        coin, so a run cannot land six matching pairs in a row and read
        as broken.
        """
        if not self._deck:
            self._deck = [True] * 3 + [False] * 3
            self.rng.shuffle(self._deck)
        return self._deck.pop()

    def start_run(self) -> None:
        self._reset()
        self.nodes = self.clamped(self.start_nodes)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        lines = edge_count(self.nodes, self.density)
        pair = build_pair(self.nodes, lines, self._draw_answer(),
                          self.subtle, self.rng)
        if self.subtle and not pair.same and not pair.subtle:
            self.settled_for += 1
        self.graphs = [pair.first, pair.second]
        self.spots = [ring_positions(self.nodes, self.rng),
                      ring_positions(self.nodes, self.rng)]
        self.really_same = pair.same
        self.asked_at = time.time()
        self.phase = 'asking'
        self.message = _('The same network?')
        self._redraw()

    def answer(self, choice: str) -> None:
        """Take *choice* and score it."""
        if self.phase not in ('asking', 'hidden'):
            return
        said_same = choice == SAME
        right = said_same == self.really_same
        self.results.append((self.really_same, said_same,
                             time.time() - self.asked_at))
        if right:
            self.correct += 1
        self._adapt(right)
        if self.feedback:
            self.phase = 'feedback'
            self.feedback_until = time.time() + 0.9
            self.message = (_('Yes — the same network') if self.really_same
                            else _('No — not the same network'))
            self._redraw()
        else:
            self.message = _('Yes') if right else _('No')
            self._next_trial()

    def _adapt(self, right: bool) -> None:
        if not self.adaptive:
            return
        self.nodes = self.clamped(self.nodes + (1 if right else -1))

    def _finish(self) -> None:
        self.phase = 'done'
        self.graphs = []
        tally = self.score()
        self.message = _('%d%% — matches %d/%d, mismatches %d/%d, %.1fs each'
                         ) % (tally['accuracy'],
                              tally['same_right'], tally['same_total'],
                              tally['different_right'],
                              tally['different_total'],
                              tally['mean_seconds'])
        if self.settled_for:
            # Never said during a trial: which kind a mismatch is
            # would give away that it is one.
            self.message += _('     (%d had to differ by their counts)'
                              ) % self.settled_for
        self._redraw()

    def score(self) -> Dict[str, float]:
        """How the run went, with the two answers kept apart.

        Answering "different" to everything scores half, so matches and
        mismatches are reported separately: a run can be wrong in two
        quite different ways, and only one of them is a bias.
        """
        trials = len(self.results)
        same_total = sum(1 for was_same, _said, _took in self.results
                         if was_same)
        same_right = sum(1 for was_same, said, _took in self.results
                         if was_same and said)
        different_total = trials - same_total
        different_right = sum(1 for was_same, said, _took in self.results
                              if not was_same and not said)
        times = [took for _was, _said, took in self.results]
        return {
            'trials': trials,
            'correct': self.correct,
            'accuracy': int(round(100. * self.correct / trials)) if trials
                        else 0,
            'same_total': same_total, 'same_right': same_right,
            'different_total': different_total,
            'different_right': different_right,
            'mean_seconds': (sum(times) / len(times)) if times else 0.0,
        }

    def update(self, dt: float) -> None:
        now = time.time()
        if self.phase == 'feedback' and now >= self.feedback_until:
            self._next_trial()
        elif (self.phase == 'asking' and self.exposure_ms > 0
                and now - self.asked_at >= self.exposure_ms / 1000.):
            # Time is up; the graphs go, the question stays.
            self.phase = 'hidden'
            self._redraw()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []
        for label in self.buttons:
            label.delete()
        self.buttons = []

    def _draw_graph(self, panel: int) -> None:
        graph = self.graphs[panel]
        spots = self.spots[panel]
        _centre_x, _centre_y, side = self.panels()[panel]
        thickness = max(1.5, side * 0.005)
        radius = max(4.0, side * 0.025)
        for first, second in graph.edges:
            start = self._to_pixels(panel, spots[first])
            end = self._to_pixels(panel, spots[second])
            self.drawn.append(pyglet.shapes.Line(
                start[0], start[1], end[0], end[1], thickness=thickness,
                color=self.inkcolor, batch=self.batch,
                group=self.line_group))
        for node in range(graph.size):
            spot = self._to_pixels(panel, spots[node])
            self.drawn.append(pyglet.shapes.Circle(
                spot[0], spot[1], radius, color=self.inkcolor,
                batch=self.batch, group=self.node_group))

    def _draw_buttons(self) -> None:
        for left, bottom, width, height, choice in self._button_rects():
            self.drawn.append(pyglet.shapes.Rectangle(
                left, bottom, width, height, color=self.accent,
                batch=self.batch, group=self.line_group))
            self.buttons.append(pyglet.text.Label(
                _('Same') if choice == SAME else _('Different'),
                font_size=calc_fontsize(15), weight='bold',
                color=(255, 255, 255, 255), batch=self.batch,
                group=self.node_group,
                x=left + width / 2, y=bottom + height / 2,
                anchor_x='center', anchor_y='center', font_name=FONTLIST))

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.phase in ('asking', 'feedback') and self.graphs:
            left, bottom, width, height = self.canvas()
            self.drawn.append(pyglet.shapes.Line(
                left + width / 2, bottom, left + width / 2, bottom + height,
                thickness=1.0, color=self.dividercolor, batch=self.batch,
                group=self.line_group))
            for panel in range(len(self.graphs)):
                self._draw_graph(panel)
        if self.phase in ('asking', 'hidden'):
            self._draw_buttons()
        self._update_labels()

    def _update_labels(self) -> None:
        parts = [self.message]
        if self.phase in ('asking', 'hidden', 'feedback'):
            parts.append(_('%d of %d   right %d')
                         % (self.trial, self.total_trials, self.correct))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if GraphMapping.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        GraphMapping.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in (key.LEFT, key.Y, key.S):
            self.answer(SAME)
        elif symbol in (key.RIGHT, key.N, key.D):
            self.answer(DIFFERENT)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        for left, bottom, width, height, choice in self._button_rects():
            if left <= x <= left + width and bottom <= y <= bottom + height:
                self.answer(choice)
                break
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
