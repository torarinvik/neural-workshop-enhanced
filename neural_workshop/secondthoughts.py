# -*- coding: utf-8 -*-
"""Second Thoughts: questions whose first answer is wrong.

Every question here has an answer that comes to mind at once, and it is
always among the choices; the right one takes a second look. They are
made here, with fresh numbers and names every time:

* **the race**: you overtake the runner in third place -- what place are
  you in? (third, not second);
* **the pond**: lily pads double every day and cover the pond in 48
  days -- when was it half covered? (day 47, not 24);
* **the coin**: heads six times in a row -- is tails now more likely?
  (no);
* **the bakers**: 5 bakers bake 5 cakes in 5 minutes -- how long do 100
  bakers take for 100 cakes? (5 minutes, not 100);
* **the price**: a bat and a ball cost 1.10 together, the bat 1.00 more
  than the ball -- what does the ball cost? (0.05, not 0.10);
* **the description**: someone who sounds like an activist -- is she
  more likely a bank teller, or a bank teller and an activist? (the
  first: two things are never likelier than one of them); asked the
  other way round as often, so the longer answer is right as often as
  the shorter;
* **the small hospital**: which sees more days with over 60% boys born,
  the big one or the small one? (the small one: small samples stray);
* **the test**: of those who test positive, how many are ill? First in
  counts of people, later in percentages, and at the top after two
  tests (the base rate matters, and the lure is the test's accuracy).

The ladder:

* rungs 1-3: the race, the pond, the coin, and the test in counts;
* rungs 4-6: those, and the bakers, the price and the description;
* rungs 7-9: those, and the hospital and the test in percentages;
* rungs 10-12: all of them, with less time;
* rungs 13 and up: the test after two positive results, and less time
  still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import NamedTuple, Optional, Sequence, Tuple

from . import feelings as F
from . import hand as H
from . import quiz as Q
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run

ORDINALS = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth',
            'seventh', 'eighth', 'ninth', 'tenth')
NAMES = ('Alex', 'Sam', 'Robin', 'Jamie', 'Kim', 'Noor', 'Mika', 'Ola',
         'Lee', 'Sasha', 'Toni', 'Ari')


class Puzzle(NamedTuple):
    text: str
    ask: str
    options: Tuple[str, ...]
    answer: int                    # index of the right one
    lure: int                      # index of the first-thought one


def _make(text, ask, right, lure, others: Sequence[str]) -> Optional[Puzzle]:
    opts = [right, lure] + [o for o in others if o not in (right, lure)]
    if len(set(opts)) != len(opts) or len(opts) < 3:
        return None
    return Puzzle(text, ask, tuple(opts[:4]), 0, 1)


def race(d: random.Random) -> Optional[Puzzle]:
    k = d.randrange(1, 7)              # 0-based place overtaken: 2nd..7th
    return _make(_('You are running a race and overtake the runner in %s '
                   'place.') % ORDINALS[k],
                 _('What place are you in now?'), ORDINALS[k],
                 ORDINALS[k - 1], [ORDINALS[k + 1],
                                   ORDINALS[k - 2] if k >= 2 else 'last'])


def pond(d: random.Random) -> Optional[Puzzle]:
    n = d.randrange(10, 60, 2)
    thing = d.choice((('lily pads', 'pond'), ('mould', 'loaf'),
                      ('algae', 'lake'), ('moss', 'stone')))
    return _make(_('A patch of %s doubles in size every day. It takes %d '
                   'days to cover the whole %s.') % (thing[0], n, thing[1]),
                 _('How many days did it take to cover half of it?'),
                 str(n - 1), str(n // 2), [str(n - 2), str(n // 4)])


def coin(d: random.Random) -> Optional[Puzzle]:
    k = d.randrange(4, 9)
    if d.random() < 0.5:
        return _make(_('A fair coin has landed heads %d times in a row.') % k,
                     _('On the next toss, which is more likely?'),
                     _('heads and tails are equally likely'), _('tails'),
                     [_('heads')])
    return _make(_('A fair die has not shown a six in its last %d rolls.')
                 % (3 * k), _('On the next roll, a six is...'),
                 _('as likely as ever'), _('more likely than usual'),
                 [_('less likely than usual')])


def bakers(d: random.Random) -> Optional[Puzzle]:
    who = d.choice((('bakers', 'bake', 'cakes'), ('machines', 'make',
                    'widgets'), ('painters', 'paint', 'fences'),
                    ('printers', 'print', 'posters')))
    n = d.randrange(3, 9)
    m = d.choice((5, 6, 8, 10, 12, 15))
    k = d.choice((60, 80, 100, 120, 200))
    return _make(_('%d %s %s %d %s in %d minutes.') % (n, who[0], who[1], n,
                                                       who[2], m),
                 _('How long do %d %s take to %s %d %s?') % (
                     k, who[0], who[1], k, who[2]),
                 _('%d minutes') % m, _('%d minutes') % k,
                 [_('%d minutes') % (m * k // n), _('%d minutes') % (k // n)])


def _money(cents: int) -> str:
    return '%d.%02d' % divmod(cents, 100)


def price(d: random.Random) -> Optional[Puzzle]:
    a, b = d.choice((('bat', 'ball'), ('pen', 'cap'), ('cup', 'saucer'),
                     ('book', 'bookmark'), ('lamp', 'bulb')))
    low = d.randrange(5, 50, 5)
    diff = d.randrange(100, 400, 50)
    total = 2 * low + diff
    return _make(_('A %s and a %s cost %s together. The %s costs %s more '
                   'than the %s.') % (a, b, _money(total), a, _money(diff), b),
                 _('How much does the %s cost?') % b,
                 _money(low), _money(total - diff),
                 [_money(total // 2), _money(diff // 2)])


PEOPLE = (
    ('is outspoken and cares a great deal about fairness; at university '
     'she marched against discrimination', 'a bank teller',
     'active in the feminist movement'),
    ('spends every weekend on long mountain hikes and talks about little '
     'but rock and rope', 'an accountant', 'a keen climber'),
    ('reads poetry on the train and fills notebooks with verses',
     'a nurse', 'writes poems'),
    ('could take a radio apart at nine and builds robots in the garage',
     'a teacher', 'an electronics hobbyist'),
    ('never misses a match and knows every player\'s statistics',
     'a dentist', 'a football fan'),
    ('grows tomatoes on the balcony and talks to every plant',
     'a lawyer', 'a keen gardener'),
)


def description(d: random.Random) -> Optional[Puzzle]:
    trait, job, extra = d.choice(PEOPLE)
    name = d.choice(NAMES)
    one = _('%s is %s') % (name, job)
    both = _('%s is %s and %s') % (name, job, extra)
    text = _('%s %s.') % (name, trait)
    same = _('both are equally likely')
    if d.random() < 0.5:
        return _make(text, _('Which is more likely?'), one, both, [same])
    return _make(text, _('Which is less likely?'), both, one, [same])


def hospital(d: random.Random) -> Optional[Puzzle]:
    small = d.randrange(10, 20)
    big = d.randrange(40, 70)
    names = d.sample(('North', 'South', 'East', 'West', 'Harbour', 'Hill'), 2)
    text = _('%s Hospital has about %d births a day, %s Hospital about %d. '
             'About half of all babies are boys. For a year, each hospital '
             'counted the days on which more than 60%% of the babies born '
             'were boys.') % (names[0], small, names[1], big)
    if d.random() < 0.5:
        return _make(text, _('Which hospital counted more such days?'),
                     names[0], _('about the same'), [names[1]])
    return _make(text, _('Which hospital counted fewer such days?'),
                 names[1], _('about the same'), [names[0]])


def test_counts(d: random.Random) -> Optional[Puzzle]:
    n = d.choice((100, 200, 1000))
    ill = d.choice((2, 4, 5, 10)) * n // 100
    if ill < 5:
        return None
    found = ill - d.randrange(0, max(1, ill // 5) + 1)
    false = d.choice((5, 8, 10, 15)) * (n - ill) // 100
    if false <= found:
        false = found + d.randrange(2, 10)
    text = _('Of %d people, %d have an illness. A test comes out positive '
             'for %d of those %d, and also for %d of the %d who are well.') % (
        n, ill, found, ill, false, n - ill)
    return _make(text, _('Of the people who test positive, how many have the '
                         'illness?'),
                 _('%d of %d') % (found, found + false),
                 _('%d of %d') % (found, ill),
                 [_('%d of %d') % (ill, n),
                  _('%d of %d') % (false, found + false)])


def _pct(x: float) -> str:
    if x < 0.01:
        return _('about %g%%') % round(100 * x, 1)
    return _('about %d%%') % int(round(100 * x))


def _posterior(prior: float, sens: float, fp: float, tests: int) -> float:
    a, b = prior, 1 - prior
    for _t in range(tests):
        a, b = a * sens, b * fp
    return a / (a + b)


def test_percent(d: random.Random, tests: int = 1) -> Optional[Puzzle]:
    prior = d.choice((0.01, 0.02, 0.05)) if tests == 1 else \
        d.choice((0.001, 0.002, 0.005))
    sens = d.choice((0.8, 0.9, 0.95))
    fp = d.choice((0.05, 0.1, 0.2)) if tests == 1 else d.choice((0.05, 0.1))
    post = _posterior(prior, sens, fp, tests)
    right, lure = _pct(post), _pct(sens)
    others = [_pct(x) for x in (prior, 1 - fp, _posterior(prior, sens, fp,
                                                          tests + 1))]
    if abs(post - sens) < 0.12:
        return None
    what = _('Someone tests positive.') if tests == 1 else \
        _('Someone tests positive, and positive again on a second, '
          'independent test of the same kind.')
    text = _('%s of people have an illness. A test finds it in %s of those '
             'who have it, and wrongly finds it in %s of those who do not. '
             '%s') % ('%g%%' % (100 * prior), '%g%%' % (100 * sens),
                      '%g%%' % (100 * fp), what)
    return _make(text, _('How likely is it that they have the illness?'),
                 right, lure, others)


KINDS = {'race': race, 'pond': pond, 'coin': coin, 'counts': test_counts,
         'bakers': bakers, 'price': price, 'description': description,
         'hospital': hospital, 'percent': test_percent,
         'two_tests': lambda d: test_percent(d, 2)}
TITLES = {'counts': _('A test'), 'percent': _('A test'),
          'two_tests': _('Two tests')}
LADDER = (('race', 'pond', 'coin', 'counts'),
          ('bakers', 'price', 'description'), ('hospital', 'percent'), (),
          ('two_tests',))


class Grade(NamedTuple):
    rung: int
    kinds: tuple
    pace: Q.Pace
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = sum(LADDER[:min(len(LADDER), 1 + (r - 1) // 3)], ())
    return Grade(r, kinds, Q.pace(r, slow=1.6, fast=3.2, base=8.0,
                                  floor=4.0), 10, 0.7)


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    def make(kind):
        pz = KINDS[kind](draw)
        if pz is None:
            return None
        st = Q.step(pz.ask, pz.options, pz.answer, draw)
        return Q.item(pz.text, [st], level.pace,
                      title=TITLES.get(kind, _('Think twice')))

    items = Q.mixed(level.kinds, level.items, draw, make)
    if len(items) < level.items:
        return None
    return Q.assemble(level, items, level.skill)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
