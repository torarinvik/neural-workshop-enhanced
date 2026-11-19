#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Task cards: every catalogued task has one, a held-out task's says
nothing beyond its ports, family and clock, and the floors on the
measured cards are what counting over deals gives.

Each floor is counted here from the models, with players written here,
not read from the card or the module that deals.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest
from collections import Counter

from memorysupport import best_from_view, drive, rate

from neural_workshop import (carried, farcue, framed, handsoff, heardback,
                             inmind, keptrule, newestfirst, severalcues,
                             twostage, unevenwait,
                             longwalk, lookback, memwalk, ministeps,
                             morewalks, nowthen, ownpress, ruleguess, twins)
from nwenv import cards, catalog

RUNGS = (1, 2, 3, 4, 5)
DELTA = 0.035


class Answer:
    """A walk's first right press, read as a question's answer."""

    def __init__(self, p, answer):
        self.p, self.answer = p, answer


# --- dealers: task id -> (deal(rung, rng), look) -------------------------

def _framed(module, kind, look):
    return lambda rung, rng: module.deal(kind, rung, rng, look=look)


DEALS = {}
for _kind, _ids in (('moved', ('which_moved', 'moved_bead')),
                    ('new', ('which_is_new', 'new_bead')),
                    ('gone', ('which_is_gone', 'gone_bead')),
                    ('traded', ('traded_places', 'traded_beads'))):
    for _look, _id in enumerate(_ids):
        DEALS[_id] = _framed(nowthen, _kind, _look)
DEALS['running_count'] = _framed(carried, 'count', 0)
DEALS['bead_pile'] = _framed(carried, 'count', 1)
DEALS['chevron_walk'] = _framed(carried, 'arrows', 1)
DEALS['the_marked_one'] = _framed(farcue, 'marked', 0)
DEALS['flagged_bead'] = _framed(farcue, 'marked', 1)
DEALS['changed_note'] = _framed(heardback, 'melody', 0)
DEALS['changed_chime'] = _framed(heardback, 'melody', 1)
DEALS['marked_tone'] = _framed(heardback, 'mark', 0)
DEALS['other_voice'] = _framed(heardback, 'mark', 1)
DEALS['hands_off'] = _framed(handsoff, 'still', 0)
DEALS['busy_wait'] = _framed(handsoff, 'busy', 0)
DEALS['uneven_wait'] = _framed(unevenwait, 'uneven', 0)
DEALS['which_was_where'] = _framed(severalcues, 'several', 0)
DEALS['newest_counts'] = _framed(newestfirst, 'newest', 0)
DEALS['first_counts'] = _framed(newestfirst, 'first', 0)
DEALS['shape_back'] = lambda rung, rng: lookback.deal('shape', rung, rng)
DEALS['hidden_cue'] = lambda rung, rng: lookback.deal('cue', rung, rng)
DEALS['sound_back'] = lambda rung, rng: lookback.deal('sound', rung, rng)
DEALS['changed_tile'] = lambda rung, rng: inmind.deal('changed', rung, rng)
DEALS['swapped_boxes'] = lambda rung, rng: inmind.deal('swapped', rung, rng)


def _cards(p, n=4):
    order = framed.port_order(p.data['look'], n)
    return tuple(p.data['cards'][order[port]] for port in range(n))


def _rank(p, note):
    base = heardback.PITCHES[p.data['look']]
    return min(range(4), key=lambda i: abs(math.log2(note.freq / base[i])))


def _last_note(p):
    return max(p.notes, key=lambda n: n.t)


#: What a player sees on the frame the question is put on.
VIEWS = {
    # The traded row is new every deal, so a table keyed on it learns
    # nothing; what it can tell a player is which place is marked.
    'nowthen': lambda p: (p.data['marked'] if p.kind == 'traded' else
                          (tuple(sorted(p.data['second'])), _cards(p))),
    'count': lambda p: (p.data['steps'][-1], p.data['cards']),
    'arrows': lambda p: p.data['arrows'][-1],
    'farcue': lambda p: _cards(p),
    'heardback': lambda p: _rank(p, _last_note(p)),
    'shape_back': lambda p: (p.frames[-1], tuple(p.data['cards'])),
    'sound_back': lambda p: p.frames[-1],
    'hidden_cue': lambda p: (p.data['layout'],),
    'changed_tile': lambda p: tuple(p.data['tiles'][1]),
    'swapped_boxes': lambda p: p.data['pairs'][-1],
    # The kept-cue families: the places, their layout and the question
    # mark, and the colour asked for where one is.
    'keptcue': lambda p: (p.data['layout'], p.data['asked']),
}


def view_for(task_id):
    if task_id in VIEWS:
        return VIEWS[task_id]
    family = catalog.family_of(task_id)
    return {'now and earlier': VIEWS['nowthen'],
            'carried through': (VIEWS['count'] if task_id in
                                ('running_count', 'bead_pile')
                                else VIEWS['arrows']),
            'far cue': VIEWS['farcue'],
            'heard back': VIEWS['heardback'],
            'hands off': VIEWS['keptcue'],
            'uneven wait': VIEWS['keptcue'],
            'several kept': VIEWS['keptcue'],
            'newest and first': VIEWS['keptcue']}[family]


# --- frame-only floors ---------------------------------------------------

def walk_floor(deal, solver, rungs=RUNGS, seeds=30):
    """The share of deals a player reading only the board finishes."""
    done = total = 0
    for rung in rungs:
        for seed in range(seeds):
            done += solver(deal(rung, random.Random(seed)))
            total += 1
    return done / total


def _walk_with(walk):
    while walk.result is None:
        walk.press(walk.good()[0])
    return walk.result[0]


def _short(kind):
    def solve(p):
        walk = ministeps.Walk(p)
        for port in ministeps.solve(p):
            walk.press(port)
        return walk.result is not None and walk.result[0]
    return (lambda rung, rng: ministeps.deal(kind, rung, rng)), solve


def _twin_solver(p):
    d = p.data
    if p.rule == 'same':
        same = list(d['one']) == list(d['two'])
        return (0 if same else 1) if p.look == 'a' else (1 if same else 0)
    if p.rule == 'odd':
        items = d['items']
        return next(k for k, i in enumerate(items) if items.count(i) == 1)
    if p.rule == 'next':
        seq = d['seq']
        q = next(q for q in range(1, len(seq))
                 if all(seq[i] == seq[i - q] for i in range(q, len(seq))))
        return d['cards'].index(seq[len(seq) - q])
    if p.look == 'a':
        x, y = d['dot']
        pts, inside = d['points'], False
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            if (y1 > y) != (y2 > y) and \
                    x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        return 0 if inside else 1
    return 1 if d['mark'] in d['cells'] else 0


TWIN_DEALS = {'match_shapes': ('same', 'a'), 'match_tiles': ('same', 'b'),
              'odd_shape': ('odd', 'a'), 'next_shape': ('next', 'a'),
              'next_tile': ('next', 'b'), 'in_the_loop': ('inside', 'a'),
              'in_the_pen': ('inside', 'b')}


def _as_pointed(p):
    """The port that would move the marker towards the mark if the
    ports went the way they point."""
    way = (p.data['goal'][0] - p.start[0], p.data['goal'][1] - p.start[1])
    return ministeps.STEPS.index(way)


def _shuffled_floor():
    """Marker Walk, Shuffled at rung 1, for a player who does not know
    this run's order: which port moves towards the mark."""
    def deal(rng):
        order = [0, 1, 2, 3]
        rng.shuffle(order)
        p = ministeps.deal('walk', 1, rng, order=tuple(order))
        return Answer(p, ministeps.good(p, p.start)[0])
    return best_from_view(deal, lambda a: (a.p.start, a.p.data['goal']))


def _rule_floor():
    """Which Rule at rung 1, for a player who keeps nothing of the run:
    the best card given the things on the table, over the rules the run
    may hold."""
    rng, total, n = random.Random(4), 0.0, 4000
    among = ruleguess.candidates(1)
    for _d in range(n):
        p = ruleguess.deal(ruleguess.draw_rule(1, rng), 1, rng)
        votes = Counter(ruleguess.pick(r, p.things) for r in among)
        total += max(votes.values()) / len(among)
    return total / n


def _memwalk_play(kind, rung, chooser, n=1500, seed=3):
    rng = random.Random(seed)
    won = 0
    for _d in range(n):
        p = memwalk.deal(kind, rung, rng)
        run = memwalk.Run(p)
        run.t = p.open_at
        while run.result is None:
            run.press(chooser(run, rng))
        won += run.result[0]
    return won / n


def _random_press(run, rng):
    return rng.randrange(4)


def _to_middle(run, rng):
    (x, y), _reached = run.state
    ways = [w for w, ok in ((3, x < 3), (2, x > 3), (0, y < 3), (1, y > 3))
            if ok]
    return rng.choice(ways) if ways else rng.randrange(4)


def _memwalk_floor(kind):
    """The best of the players without memory: pressing at random,
    heading for the middle, and one fixed direction."""
    players = [_random_press, _to_middle] + [
        (lambda r, g, w=w: w) for w in range(4)]
    return max(_memwalk_play(kind, 1, chooser) for chooser in players)


def _ownpress_floor(kind, look):
    """Whatever a player without memory of its own presses does, it is
    right as often as one pressing at random: counted for that player
    and for the best one reading the screen."""
    rng, ledger, right, n = random.Random(3), ownpress.Ledger(), 0, 4000
    puzzles = []
    for _t in range(n):
        p = ownpress.deal(kind, 1, rng, look=look, ledger=ledger)
        press = rng.randrange(4)
        ledger.record(press)
        right += press == p.answer
        puzzles.append(p)
    it = iter(puzzles)
    screen = best_from_view(lambda _rng: next(it),
                            lambda p: (p.data['layout'], p.data['hue']),
                            n=n)
    return max(right / n, screen)


def _rule_run(rung, n, seed=5):
    """A run of Same or Opposite, its blocks kept across the deals."""
    rng, ledger = random.Random(seed), keptrule.Ledger()
    return [keptrule.deal('rule', rung, rng, ledger=ledger)
            for _t in range(n)]


def frame_only(task_id):
    """The chance level for *task_id*, counted."""
    family = catalog.family_of(task_id)
    if family in ('short walks', 'payment for progress'):
        kind = {'short_maze': 'maze', 'short_tower': 'tower',
                'turned_tiles': 'tiles', 'short_push': 'push',
                'short_maze_steps': 'maze'}[task_id]
        return walk_floor(*_short(kind))
    if task_id == 'long_way_round':
        return walk_floor(lambda r, g: longwalk.deal('walk', r, g),
                          lambda p: _walk_with(longwalk.Walk(p)))
    if task_id in ('push_and_pull', 'one_way_doors', 'ice_floor'):
        kind = {'push_and_pull': 'pushpull', 'one_way_doors': 'oneway',
                'ice_floor': 'ice'}[task_id]
        return walk_floor(lambda r, g: morewalks.deal(kind, r, g),
                          lambda p: _walk_with(morewalks.Walk(p)))
    if task_id in ('fetch_and_carry', 'plate_and_gate'):
        kind = 'fetch' if task_id == 'fetch_and_carry' else 'plate'
        return walk_floor(lambda r, g: twostage.deal(kind, r, g),
                          lambda p: _walk_with(twostage.Walk(p)))
    if task_id in TWIN_DEALS:
        rule, look = TWIN_DEALS[task_id]
        return walk_floor(lambda r, g: twins.deal(rule, look, r, g),
                          lambda p: _twin_solver(p) == p.answer)
    if task_id == 'marker_walk_shuffled':
        return _shuffled_floor()
    if task_id == 'which_rule':
        return _rule_floor()
    if task_id == 'gone_from_view':
        return _memwalk_floor('one')
    if task_id == 'in_that_order':
        return _memwalk_floor('two')
    if task_id == 'same_or_opposite':
        run = _rule_run(1, 6000)
        it = iter(run)
        return best_from_view(lambda _rng: next(it),
                              lambda p: (p.data['cues'][0][1],
                                         p.data['layout']), n=len(run))
    if task_id in ('next_in_turn', 'stay_or_shift', 'moving_prize'):
        kind = 'cycle' if task_id == 'next_in_turn' else 'stay'
        return _ownpress_floor(kind, 1 if task_id == 'moving_prize' else 0)
    deal = DEALS[task_id]
    return best_from_view(lambda rng: deal(1, rng), view_for(task_id))


# --- partial strategies --------------------------------------------------

def _nowthen_partial(task_id, strategy):
    look = task_id in ('moved_bead', 'new_bead', 'gone_bead',
                       'traded_beads')
    kind = {'which_moved': 'moved', 'moved_bead': 'moved',
            'which_is_new': 'new', 'new_bead': 'new',
            'which_is_gone': 'gone', 'gone_bead': 'gone',
            'traded_places': 'traded', 'traded_beads': 'traded'}[task_id]
    deal = lambda rng: nowthen.deal(kind, 2, rng, look=int(look))  # noqa

    def moved(p, rng):
        thing, spot = rng.choice(p.data['first'])
        mine = _cards(p)
        if dict(p.data['second'])[thing] != spot:
            return mine.index(thing)
        return rng.choice([i for i in range(4) if mine[i] != thing])

    def traded(p, rng):
        first, second = p.data['first'], p.data['second']
        order = framed.port_order(p.data['look'], nowthen.ROW)
        place = rng.randrange(nowthen.ROW)
        now = second.index(first[place])
        if now == place:
            return order.index(rng.choice(
                [i for i in range(nowthen.ROW)
                 if i not in (place, p.data['marked'])]))
        return order.index(place if now == p.data['marked'] else now)

    def keeping(n):
        def player(p, rng):
            kept = [t for t, _s in rng.sample(p.data['first'], n)]
            return rng.choice([i for i, t in enumerate(_cards(p))
                               if t not in kept])
        return player

    def gone(p, rng):
        thing, _spot = rng.choice(p.data['first'])
        if thing not in dict(p.data['second']):
            return _cards(p).index(thing)
        return rng.randrange(4)

    player = {('moved', 'keeping where one thing was'): moved,
              ('traded', 'keeping where one thing was'): traded,
              ('new', 'keeping one old thing'): keeping(1),
              ('new', 'keeping two old things'): keeping(2),
              ('gone', 'keeping one of the first things'): gone}[
        kind, strategy]
    return rate(deal, player)


def partial(task_id, strategy, rung):
    """What *strategy* earns on *task_id* at *rung*, counted."""
    family = catalog.family_of(task_id)
    if family == 'now and earlier':
        return _nowthen_partial(task_id, strategy)
    if task_id in ('running_count', 'bead_pile'):
        look = 0 if task_id == 'running_count' else 1

        def keep_start(p, rng):
            reach = Counter({0: 1})
            for _step in p.data['steps']:
                nxt = Counter()
                for value, ways in reach.items():
                    for step in carried.STEPS:
                        nxt[value + step] += ways
                reach = nxt
            best = max(p.data['cards'],
                       key=lambda v: reach[v - p.data['start']])
            return framed.port_order(look, 4).index(
                p.data['cards'].index(best))
        return rate(lambda rng: carried.deal('count', rung, rng,
                                             look=look), keep_start)
    if task_id == 'chevron_walk':
        def marker(p, rng):
            order = framed.port_order(1, 4)
            if len(p.data['arrows']) % 2:
                return order.index(rng.choice(
                    [c for c in range(4) if c != p.data['start']]))
            return order.index(p.data['start'])
        return rate(lambda rng: carried.deal('arrows', rung, rng, look=1),
                    marker)
    if task_id in ('next_in_turn', 'stay_or_shift', 'moving_prize'):
        kind = 'cycle' if task_id == 'next_in_turn' else 'stay'
        look = 1 if task_id == 'moving_prize' else 0
        rng, mine = random.Random(3), random.Random(103)
        ledger, log = ownpress.Ledger(), []
        for _t in range(20000 if kind == 'stay' else 400):
            p = ownpress.deal(kind, rung, rng, look=look, ledger=ledger)
            if strategy.startswith('pressing round'):
                press = 0 if not log else (log[-1][1] + 1) % 4
            elif strategy.startswith('one port'):
                press = 2
            else:
                if not log:
                    press = 0
                else:
                    _p, last, ok = log[-1]
                    press = last if ok else (last + 1 + mine.randrange(3)) % 4
            ledger.record(press)
            log.append((p, press, press == p.answer))
        paid = [ok for _p, _press, ok in log[50:]]
        return sum(paid) / len(paid)
    if task_id in ('the_marked_one', 'flagged_bead'):
        look = 0 if task_id == 'the_marked_one' else 1
        deal = lambda rng: farcue.deal('marked', rung, rng, look=look)  # noqa
        if strategy.startswith('keeping the first frame'):
            return rate(deal, lambda p, rng: _cards(p).index(
                rng.choice(p.data['first'])))
        return rate(deal, lambda p, rng: p.data['marked'])
    if task_id in ('changed_note', 'changed_chime', 'marked_tone',
                   'other_voice'):
        look = 0 if task_id in ('changed_note', 'marked_tone') else 1
        order = framed.port_order(look, 4)
        if task_id in ('changed_note', 'changed_chime'):
            def player(p, rng):
                notes = sorted(p.notes, key=lambda n: n.t)
                if _rank(p, notes[3]) != _rank(p, notes[-1]):
                    return order.index(3)
                return order.index(rng.randrange(3))
            kind = 'melody'
        else:
            def player(p, rng):
                return order.index(_rank(p, _last_note(p)))
            kind = 'mark'
        return rate(lambda rng: heardback.deal(kind, rung, rng, look=look),
                    player, 3000)
    if task_id == 'shape_back':
        return rate(lambda rng: lookback.deal('shape', rung, rng),
                    lambda p, rng: rng.choice(
                        [i for i in range(3)
                         if p.data['cards'][i] != p.frames[-1]]))
    if task_id == 'sound_back':
        return rate(lambda rng: lookback.deal('sound', rung, rng),
                    lambda p, rng: rng.choice(
                        [i for i in range(3) if i != p.frames[-1]]))
    if task_id == 'swapped_boxes':
        return rate(lambda rng: inmind.deal('swapped', rung, rng),
                    lambda p, rng: p.frames[0])
    if task_id == 'which_rule':
        rng, right, n = random.Random(6), 0, 4000
        mine = ruleguess.candidates(rung)[0]
        for _d in range(n):
            p = ruleguess.deal(ruleguess.draw_rule(rung, rng), rung, rng)
            right += ruleguess.pick(mine, p.things) == p.answer
        return right / n
    if task_id == 'marker_walk_shuffled':
        rng, right, n = random.Random(8), 0, 4000
        for _d in range(n):
            order = [0, 1, 2, 3]
            rng.shuffle(order)
            p = ministeps.deal('walk', 1, rng, order=tuple(order))
            right += _as_pointed(p) in ministeps.good(p, p.start)
        return right / n
    if task_id in ('gone_from_view', 'in_that_order'):
        kind = 'one' if task_id == 'gone_from_view' else 'two'
        return _memwalk_play(kind, rung, _to_middle)
    if task_id == 'same_or_opposite':
        run = _rule_run(rung, 6000)
        return sum(p.data['cues'][0][1] == p.answer for p in run) / len(run)
    if task_id == 'which_was_where':
        def last(p, rng):
            place = p.data['cues'][-1][1]
            return place if p.data['look'] == 0 else 3 - place
        return rate(lambda rng: severalcues.deal('several', rung, rng), last)
    if task_id in ('newest_counts', 'first_counts'):
        kind = 'newest' if task_id == 'newest_counts' else 'first'

        def other(p, rng):
            place = p.data['cues'][0 if kind == 'newest' else -1][1]
            return place if p.data['look'] == 0 else 3 - place
        return rate(lambda rng: newestfirst.deal(kind, rung, rng), other)
    raise KeyError((task_id, strategy))


# --- by rung: presses at random, and the best without memory -------------

#: Tasks whose answer needs no memory: the board, or the frame, shows it.
SEEN = ('short walks', 'payment for progress', 'forgiving walks',
        'two-stage walks')
TWIN_IDS = tuple(TWIN_DEALS)


def _walk_random(make, rung, n=2000, seed=1):
    rng, won = random.Random(seed), 0
    for _d in range(n):
        walk = make(rung, rng)
        while walk.result is None:
            walk.press(rng.randrange(walk.puzzle.ports))
        won += walk.result[0]
    return won / n


def _walk_maker(task_id):
    """A fresh walk of *task_id* at a rung, or None for other tasks."""
    family = catalog.family_of(task_id)
    if family in ('short walks', 'payment for progress'):
        kind = {'short_maze': 'maze', 'short_tower': 'tower',
                'turned_tiles': 'tiles', 'short_push': 'push',
                'short_maze_steps': 'maze'}[task_id]
        return lambda r, g: ministeps.Walk(ministeps.deal(kind, r, g))
    if task_id == 'long_way_round':
        return lambda r, g: longwalk.Walk(longwalk.deal('walk', r, g))
    if task_id in ('push_and_pull', 'one_way_doors', 'ice_floor'):
        kind = {'push_and_pull': 'pushpull', 'one_way_doors': 'oneway',
                'ice_floor': 'ice'}[task_id]
        return lambda r, g: morewalks.Walk(morewalks.deal(kind, r, g))
    if task_id in WALK_DEALS:
        return WALK_DEALS[task_id]
    return None


#: Walks added since: task id -> a fresh walk at (rung, rng).
WALK_DEALS = {
    'fetch_and_carry': lambda r, g: twostage.Walk(
        twostage.deal('fetch', r, g)),
    'plate_and_gate': lambda r, g: twostage.Walk(
        twostage.deal('plate', r, g)),
}


def _shuffled_walk(rung, rng):
    order = [0, 1, 2, 3]
    rng.shuffle(order)
    return ministeps.Walk(ministeps.deal('walk', rung, rng,
                                         order=tuple(order)))


def _as_pointed_walk(rung, n=3000, seed=8):
    """Marker Walk, Shuffled, pressed as if the ports went the way they
    point."""
    rng, won = random.Random(seed), 0
    for _d in range(n):
        walk = _shuffled_walk(rung, rng)
        while walk.result is None:
            (x, y), goal = walk.state, walk.puzzle.data['goal']
            ways = [p for p, (dx, dy) in enumerate(ministeps.STEPS)
                    if abs(x + dx - goal[0]) + abs(y + dy - goal[1])
                    < abs(x - goal[0]) + abs(y - goal[1])]
            walk.press(ways[0])
        won += walk.result[0]
    return won / n


def _choices(p):
    return len(p.choices)


def _ownpress_levels(kind, look, rung, n=4000):
    """Random presses, and the best player reading the screen alone."""
    rng, ledger, right = random.Random(3), ownpress.Ledger(), 0
    puzzles = []
    for _t in range(n):
        p = ownpress.deal(kind, rung, rng, look=look, ledger=ledger)
        press = rng.randrange(4)
        ledger.record(press)
        right += press == p.answer
        puzzles.append(p)
    it = iter(puzzles)
    screen = best_from_view(lambda _rng: next(it),
                            lambda p: (p.data['layout'], p.data['hue']),
                            n=n)
    return right / n, max(right / n, screen)


def _rule_levels(rung, n=4000):
    rng, guess, by_one = random.Random(6), 0, 0
    among = ruleguess.candidates(rung)
    best = 0.0
    for _d in range(n):
        p = ruleguess.deal(ruleguess.draw_rule(rung, rng), rung, rng)
        guess += rng.randrange(_choices(p)) == p.answer
        votes = Counter(ruleguess.pick(r, p.things) for r in among)
        best += max(votes.values()) / len(among)
    return guess / n, best / n


def random_level(task_id, rung):
    """What a press at random earns, each time a press is called for:
    at each job and at the question; on a walk, at every press."""
    if task_id == 'marker_walk_shuffled':
        return _walk_random(_shuffled_walk, rung)
    make = _walk_maker(task_id)
    if make is not None:
        return _walk_random(make, rung)
    if task_id in ('gone_from_view', 'in_that_order'):
        kind = 'one' if task_id == 'gone_from_view' else 'two'
        return _memwalk_play(kind, rung, _random_press)
    if task_id in ('next_in_turn', 'stay_or_shift', 'moving_prize'):
        kind = 'cycle' if task_id == 'next_in_turn' else 'stay'
        return _ownpress_levels(kind, int(task_id == 'moving_prize'),
                                rung)[0]
    if task_id == 'which_rule':
        return _rule_levels(rung)[0]
    if task_id in TWIN_IDS:
        rule, look = TWIN_DEALS[task_id]
        return rate(lambda g: twins.deal(rule, look, rung, g),
                    lambda p, g: g.randrange(_choices(p)), 3000)
    if task_id in RUN_DEALS:
        run = RUN_DEALS[task_id](rung, 4000)
        rng = random.Random(4)
        return sum(rng.randrange(_choices(p)) == p.answer
                   for p in run) / len(run)
    deal = DEALS[task_id]

    def player(p, g):
        for _job in p.data.get('jobs', ()) if isinstance(p.data, dict) \
                else ():
            if g.randrange(4) != (_job[1] if p.data['look'] == 0
                                  else 3 - _job[1]):
                return -1
        return g.randrange(_choices(p))
    return rate(lambda g: deal(rung, g), player, 4000)


#: Tasks dealt as a run whose trials depend on each other: task id ->
#: (rung, n) -> the run's puzzles.
RUN_DEALS = {'same_or_opposite': _rule_run}


def no_memory_level(task_id, rung):
    """The best a player that keeps nothing from earlier frames earns:
    for a question, the best player reading the frame it is put on; for
    a walk from memory, the best of the players counted."""
    family = catalog.family_of(task_id)
    if family in SEEN or task_id in TWIN_IDS:
        return 1.0
    if task_id == 'marker_walk_shuffled':
        return max(_walk_random(_shuffled_walk, rung),
                   _as_pointed_walk(rung))
    if task_id in ('gone_from_view', 'in_that_order'):
        kind = 'one' if task_id == 'gone_from_view' else 'two'
        players = [_random_press, _to_middle] + [
            (lambda r, g, w=w: w) for w in range(4)]
        return max(_memwalk_play(kind, rung, chooser) for chooser in players)
    if task_id in ('next_in_turn', 'stay_or_shift', 'moving_prize'):
        kind = 'cycle' if task_id == 'next_in_turn' else 'stay'
        return _ownpress_levels(kind, int(task_id == 'moving_prize'),
                                rung)[1]
    if task_id == 'which_rule':
        return _rule_levels(rung)[1]
    if task_id in RUN_DEALS:
        run = RUN_DEALS[task_id](rung, 6000)
        it = iter(run)
        return best_from_view(lambda _g: next(it), RUN_VIEWS[task_id],
                              n=len(run))
    deal = DEALS[task_id]
    return best_from_view(lambda g: deal(rung, g), view_for(task_id),
                          n=4000)


#: What the frame the question is put on shows, for RUN_DEALS tasks.
RUN_VIEWS = {'same_or_opposite': lambda p: (p.data['cues'][0][1],
                                           p.data['layout'])}


# --- frames back ---------------------------------------------------------

def frames_back(task_id, rung, seed=None):
    """Shown frames from the one the question is put on back to the
    earliest the answer needs, from a deal; for a walk from memory, from
    the press that ends the shortest way, a press a frame, back to the
    last frame the goal showed."""
    if task_id in ('gone_from_view', 'in_that_order'):
        p = memwalk.deal('one' if task_id == 'gone_from_view' else 'two',
                         rung, random.Random(rung))
        opens = round(p.open_at / memwalk.FRAME)
        return opens + p.par - 1 - (memwalk.SHOWN - 1)
    p = DEALS[task_id](rung, random.Random(rung if seed is None else seed))
    return round(p.open_at / lookback.FRAME)


#: Presses the shortest way needs, where it is more than the answer:
#: a busy wait's jobs and its answer.
PRESSES = {'busy_wait': lambda rung: rung + 1}


class EveryTaskHasACard(unittest.TestCase):

    def test_every_catalogued_task(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            self.assertIn('ports', card)
            self.assertIn('clocked', card)
            self.assertIn('family', card)
            if task_id in catalog.HELD_OUT:
                self.assertEqual(set(card), {'ports', 'clocked', 'family'},
                                 task_id)
                continue
            self.assertIn('measured', card, task_id)

    def test_ports_and_clock_are_the_wrappers_own(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if card['ports'] is None:
                continue
            env = catalog.env_class(task_id)
            self.assertEqual(card['ports'], env.ports, task_id)
            self.assertEqual(card['clocked'], env.clocked, task_id)

    def test_every_open_family_task_is_measured(self):
        for family, members in catalog.FAMILIES.items():
            for task_id in members:
                if task_id in catalog.HELD_OUT:
                    self.assertFalse(cards.measured(task_id), task_id)
                    continue
                self.assertTrue(catalog.card(task_id)['measured'], task_id)

    def test_a_card_lists_rungs_one_to_five(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if card.get('measured'):
                self.assertEqual(sorted(card['rungs']), list(RUNGS))


class TheFloorsAreCounted(unittest.TestCase):

    def test_frame_only(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if not card.get('measured'):
                continue
            counted = frame_only(task_id)
            self.assertAlmostEqual(card['frame_only'], counted, delta=DELTA,
                                   msg=task_id)

    def test_partial_strategies(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            for row in card.get('partial', ()):
                counted = partial(task_id, row['strategy'], row['rung'])
                self.assertAlmostEqual(row['level'], counted, delta=DELTA,
                                       msg=(task_id, row))

    def test_frames_back(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if not card.get('measured'):
                continue
            for rung in RUNGS:
                said = card['rungs'][rung]['frames_back']
                if 'frames_back_least' in card['rungs'][rung]:
                    backs = {frames_back(task_id, rung, seed)
                             for seed in range(200)}
                    self.assertEqual(
                        (card['rungs'][rung]['frames_back_least'], said),
                        (min(backs), max(backs)), (task_id, rung))
                elif task_id in DEALS or task_id in ('gone_from_view',
                                                   'in_that_order'):
                    self.assertEqual(said, frames_back(task_id, rung),
                                     (task_id, rung))
                elif task_id == 'same_or_opposite':
                    self.assertIsNone(said, task_id)
                    run = _rule_run(rung, 60)
                    since = [p for p in run[:rung]]
                    self.assertIsNotNone(since[0].data['sign'])
                    self.assertTrue(all(p.data['sign'] is None
                                        for p in since[1:]))
                    self.assertEqual(card['rungs'][rung]['trials_back'],
                                     len(since) - 1, task_id)
                elif card['rungs'][rung]['trials_back'] is not None:
                    self.assertIsNone(said, task_id)
                    self.assertEqual(card['rungs'][rung]['trials_back'],
                                     rung, task_id)
                elif task_id in ('marker_walk_shuffled', 'which_rule'):
                    self.assertIsNone(said, task_id)
                else:
                    self.assertEqual(said, 0, (task_id, rung))

    def test_presses(self):
        walks = {'long_way_round': lambda r, g: longwalk.deal('walk', r, g)}
        for task_id, kind in (('push_and_pull', 'pushpull'),
                              ('one_way_doors', 'oneway'),
                              ('ice_floor', 'ice')):
            walks[task_id] = (lambda kind: lambda r, g:
                              morewalks.deal(kind, r, g))(kind)
        for task_id, kind in (('fetch_and_carry', 'fetch'),
                              ('plate_and_gate', 'plate')):
            walks[task_id] = (lambda kind: lambda r, g:
                              twostage.deal(kind, r, g))(kind)
        for task_id in ('gone_from_view', 'in_that_order'):
            walks[task_id] = (lambda kind: lambda r, g:
                              memwalk.deal(kind, r, g))(
                'one' if task_id == 'gone_from_view' else 'two')
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if not card.get('measured'):
                continue
            for rung in RUNGS:
                said = card['rungs'][rung]['presses']
                if task_id in walks:
                    p = walks[task_id](rung, random.Random(rung))
                    self.assertEqual(said, p.par, (task_id, rung))
                elif catalog.family_of(task_id) in (
                        'short walks', 'payment for progress') or \
                        task_id == 'marker_walk_shuffled':
                    self.assertEqual(said, rung, task_id)
                else:
                    self.assertEqual(said, PRESSES.get(
                        task_id, lambda r: 1)(rung), task_id)



class ByRung(unittest.TestCase):
    """The fields every measured card gives for rungs 1 to 5."""

    def test_random_and_no_memory_are_counted(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if not card.get('measured'):
                continue
            for rung in RUNGS:
                row = card['rungs'][rung]
                self.assertAlmostEqual(row['random'],
                                       random_level(task_id, rung),
                                       delta=DELTA, msg=(task_id, rung))
                self.assertAlmostEqual(row['no_memory'],
                                       no_memory_level(task_id, rung),
                                       delta=DELTA, msg=(task_id, rung))
                self.assertGreaterEqual(row['no_memory'] + DELTA,
                                        row['random'], (task_id, rung))

    def test_steps_at_ten_a_second(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if not card.get('measured'):
                continue
            for rung in (1, 2):
                row = card['rungs'][rung]
                said = row['steps_at_10hz']
                if row['frames_back'] in (None, 0):
                    self.assertIsNone(said, task_id)
                    continue
                if 'frames_back_least' in row:
                    seen = {steps_driven(task_id, rung, seed)
                            for seed in range(1, 9)}
                    self.assertLessEqual(max(seen), said, task_id)
                    self.assertGreaterEqual(min(seen),
                                            row['steps_at_10hz_least'])
                    continue
                self.assertEqual(said, steps_driven(task_id, rung),
                                 (task_id, rung))

    def test_early_presses(self):
        for task_id in catalog.task_ids():
            card = catalog.card(task_id)
            if not card.get('measured'):
                continue
            what = card['early_presses']
            if what not in (cards.IGNORED, cards.ENDS, cards.JOBS):
                continue
            # A press of each port before the question; then the answer.
            for early in range(card['ports']):
                got = drive(task_id, lambda t: t.puzzle.answer, 2,
                            early=early, frame_hz=10.0, steps=3000)
                self.assertEqual(got, [1.0] if what == cards.IGNORED
                                 else [-1.0], (task_id, early))


def _needed_showing(task, back):
    """Whether the earliest frame the answer needs shows now."""
    p, run = task.puzzle, task.run
    if hasattr(run, 'showing') and callable(run.showing):
        return run.showing() is not None
    if isinstance(p.data, dict) and 'cues' in p.data:
        want = p.data['cues'][0][0]
    else:
        want = round(p.open_at / framed.FRAME) - back
    clock = framed.frame_at if isinstance(run, framed.Run) \
        else lookback.frame_at
    f, showing = clock(p, run.t)
    return f == want and showing


def steps_driven(task_id, rung, seed=1):
    """Driven at ten steps a second: steps from the last on which the
    frame the card counts back to shows, to the one the question is put
    on."""
    from uisupport import close_overlays, reset_window
    back = catalog.card(task_id)['rungs'][rung]['frames_back']
    env = catalog.env_class(task_id)(seed=seed, rung=rung, trials=1,
                                     adaptive=False, frame_hz=10.0)
    last = None
    try:
        for i in range(4000):
            task = env.task
            port = None
            if task.phase == 'playing' and task.run is not None:
                if task.run.open:
                    return i - last
                if _needed_showing(task, back):
                    last = i
                if hasattr(task.run, 'job'):
                    port = _job(task)
            env.step(port)
    finally:
        env.close()
        close_overlays()
        reset_window()
    return None


def _job(task):
    run = task.run
    j = run.job()
    if j is None or j in run.done:
        return None
    place = task.puzzle.data['jobs'][j][1]
    return place if task.puzzle.data['look'] == 0 else 3 - place


if __name__ == '__main__':
    unittest.main()
