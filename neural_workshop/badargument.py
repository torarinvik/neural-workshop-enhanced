# -*- coding: utf-8 -*-
"""Bad Argument: does the conclusion follow from what is given?

The arguments are made here, so there is never a shortage and none has
been seen before. Each is one of a few forms, valid or not:

* *if p then q; p; so q* (valid), *if p then q; not q; so not p* (valid),
  *if p then q; q; so p* (affirming the consequent),
  *if p then q; not p; so not q* (denying the antecedent);
* *all M are P; all S are M; so all S are P* (valid), *no M are P; all S
  are M; so no S are P* (valid), *all S are P; all M are P; so all S are
  M* (an undistributed middle), *all S are M; so all M are S* (an "all"
  turned round);
* and, higher up, chains of three or four premises, whole or broken.

The ladder:

* rungs 1-3: made-up words ("If the stone is gimble, it is mimsy"), so
  only the form can tell; at rung 1 the invalid ones do not even stay
  on the subject;
* rungs 4-6: real things, and the trap: half of the valid arguments are
  about the world as it is not ("if the kettle is switched on, the water
  freezes"; "all birds are plants") and half of the invalid ones about
  the world as it is. Judging by whether it all sounds true gets half
  right, as guessing does;
* rungs 7-9: those, and arguments from BIG-bench's fallacy set;
* rungs 10-12: say what is wrong, not just that something is: it
  follows, affirming the consequent, denying the antecedent, an
  undistributed middle, or an "all" turned round;
* rungs 13 and up: longer chains, and BIG-bench's formal syllogisms with
  negations, with less time to read.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import feelings as F
from . import hand as H
from . import quiz as Q
from . import socialdata as D
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run

VALID = 'it follows'
FLAWS = {'mp': VALID, 'mt': VALID, 'barbara': VALID, 'celarent': VALID,
         'chain': VALID,
         'ac': 'affirming the consequent', 'da': 'denying the antecedent',
         'middle': 'an undistributed middle', 'broken': 'an undistributed middle',
         'convert': 'an "all" turned round', 'off': 'a change of subject'}
NAMES = (VALID, 'affirming the consequent', 'denying the antecedent',
         'an undistributed middle', 'an "all" turned round')
COND = ('mp', 'mt', 'ac', 'da')
CAT = ('barbara', 'celarent', 'middle', 'convert')

# --- content -------------------------------------------------------------------

NONSENSE_NOUNS = ('blickets', 'daxes', 'wugs', 'feps', 'toves', 'zorbs',
                  'glims', 'snarps', 'borogoves', 'tulgeys', 'mome raths',
                  'jubjubs')
NONSENSE_ADJ = ('gimble', 'mimsy', 'frumious', 'slithy', 'uffish', 'vorpal',
                'brillig', 'manxome', 'beamish', 'tulgey')
THINGS = ('stone', 'card', 'lamp', 'box', 'bell', 'coin', 'flag', 'door')

#: (S, M, P): every S is an M, every M a P. The P's never overlap.
CHAINS = (('sparrows', 'birds', 'animals'), ('salmon', 'fish', 'animals'),
          ('cats', 'mammals', 'animals'), ('roses', 'flowers', 'plants'),
          ('oaks', 'trees', 'plants'), ('ferns', 'green plants', 'plants'),
          ('trucks', 'vehicles', 'machines'),
          ('drills', 'power tools', 'machines'),
          ('violins', 'string instruments', 'instruments'),
          ('trumpets', 'brass instruments', 'instruments'))
#: Four-level chains, for the longest arguments.
LONG = (('robins', 'songbirds', 'birds', 'animals'),
        ('kittens', 'cats', 'mammals', 'animals'),
        ('tulips', 'flowers', 'plants', 'living things'),
        ('cellos', 'string instruments', 'instruments', 'things made by '
         'people'))

#: (if, then, not-if, not-then), true of the world.
RULES = (
    ('the glass falls onto the stone floor', 'it breaks',
     'the glass does not fall', 'it does not break'),
    ('the ice is left in the hot sun', 'it melts',
     'the ice is not left in the sun', 'it does not melt'),
    ('the kettle is switched on', 'the water gets hot',
     'the kettle is not switched on', 'the water does not get hot'),
    ('the plant gets no water for a month', 'it wilts',
     'the plant gets water', 'it does not wilt'),
    ('the phone battery runs out', 'the screen goes dark',
     'the battery does not run out', 'the screen does not go dark'),
    ('it rains on the field', 'the grass gets wet',
     'it does not rain on the field', 'the grass does not get wet'),
)
#: (if, then, ...), false of the world: what the first part does not do.
FALSE_RULES = (
    ('the glass falls onto the stone floor', 'it bounces back up whole',
     'the glass does not fall', 'it does not bounce back up whole'),
    ('the ice is left in the hot sun', 'it grows bigger',
     'the ice is not left in the sun', 'it does not grow bigger'),
    ('the kettle is switched on', 'the water freezes',
     'the kettle is not switched on', 'the water does not freeze'),
    ('the plant gets no water for a month', 'it grows twice as tall',
     'the plant gets water', 'it does not grow twice as tall'),
    ('the phone battery runs out', 'the screen gets brighter',
     'the battery does not run out', 'the screen does not get brighter'),
    ('it rains on the field', 'the grass catches fire',
     'it does not rain on the field', 'the grass does not catch fire'),
)


class Argument(NamedTuple):
    text: str
    form: str
    valid: bool
    believable: Optional[bool]     # is the conclusion true? None: no telling


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def conditional(form: str, rule: Tuple[str, str, str, str],
                believable: Optional[bool]) -> Argument:
    p, q, np_, nq = rule
    given, so = {'mp': (p, q), 'mt': (nq, np_), 'ac': (q, p),
                 'da': (np_, nq)}[form]
    text = '%s.\n%s.\nSo %s.' % (_cap('if %s, %s' % (p, q)), _cap(given), so)
    return Argument(text, form, form in ('mp', 'mt'), believable)


def categorical(form: str, s: str, m: str, p: str,
                believable: Optional[bool]) -> Argument:
    lines = {'barbara': ('All %s are %s' % (m, p), 'All %s are %s' % (s, m),
                         'all %s are %s' % (s, p)),
             'celarent': ('No %s are %s' % (m, p), 'All %s are %s' % (s, m),
                          'no %s are %s' % (s, p)),
             'middle': ('All %s are %s' % (s, p), 'All %s are %s' % (m, p),
                        'all %s are %s' % (s, m)),
             'convert': ('All %s are %s' % (s, m), None,
                         'all %s are %s' % (m, s))}[form]
    text = '\n'.join('%s.' % x for x in lines[:2] if x) + \
        '\nSo %s.' % lines[2]
    return Argument(text, form, form in ('barbara', 'celarent'), believable)


def nonsense(form: str, draw: random.Random) -> Argument:
    if form in COND or form == 'off':
        thing = draw.choice(THINGS)
        a, b, c = draw.sample(NONSENSE_ADJ, 3)
        rule = ('the %s is %s' % (thing, a), 'it is %s' % b,
                'the %s is not %s' % (thing, a), 'it is not %s' % b)
        if form == 'off':
            return Argument('%s.\n%s.\nSo it is %s.' % (
                _cap('if %s, %s' % rule[:2]), _cap(rule[0]), c),
                'off', False, None)
        return conditional(form, rule, None)
    s, m, p = draw.sample(NONSENSE_NOUNS, 3)
    return categorical(form, s, m, p, None)


def worldly(form: str, believable: bool, draw: random.Random
            ) -> Optional[Argument]:
    """An argument about real things whose conclusion is true of the
    world exactly when *believable*."""
    if form in COND:
        # with a true rule every conclusion here is plausible; with a
        # false one (a thing doing what it does not do) it is not
        rules = RULES if believable else FALSE_RULES
        return conditional(form, draw.choice(rules), believable)
    s, m, p = draw.choice(CHAINS)
    other = draw.choice([c for c in CHAINS if c[2] != p])
    if form == 'barbara':           # true: all S are P; false: all S are X
        return categorical(form, s, m, p if believable else other[2],
                           believable)
    if form == 'celarent':          # true: no S are X; false: no S are P
        return categorical(form, s, m, other[2] if believable else p,
                           believable)
    if form == 'middle':            # true: all S are M; false: all S are M'
        mid = m if believable else draw.choice(
            [c[1] for c in CHAINS if c[2] == p and c[1] != m] or [None])
        if mid is None:
            return None
        return categorical(form, s, mid, p, believable)
    if form == 'convert':           # all M are S: never true here
        if believable:
            return None
        return categorical(form, s, m, p, False)
    return None


def chain(valid: bool, draw: random.Random) -> Argument:
    terms = draw.choice(LONG)
    n = len(terms)
    premises = ['All %s are %s' % (terms[k], terms[k + 1])
                for k in range(n - 1)]
    form = 'chain'
    if not valid:
        # turn one link round: "all B are C" becomes "all C are B", and
        # nothing then carries the first term through to the last
        k = draw.randrange(n - 1)
        premises[k] = 'All %s are %s' % (terms[k + 1], terms[k])
        form = 'broken'
    draw.shuffle(premises)
    text = '\n'.join(p + '.' for p in premises) + \
        '\nSo all %s are %s.' % (terms[0], terms[-1])
    return Argument(text, form, valid, None)


# --- the ladder ------------------------------------------------------------------

class Grade(NamedTuple):
    rung: int
    kinds: tuple               # 'nonsense', 'world', 'fallacy', 'formal', 'chain'
    forms: tuple               # the generated forms in play
    name: bool                 # say what is wrong
    pace: Q.Pace
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        forms = ('mp', 'barbara', 'off')
    elif r < 4:
        forms = ('mp', 'ac', 'da', 'barbara', 'middle')
    else:
        forms = COND + CAT
    if r < 4:
        kinds = ('nonsense',)
    elif r < 7:
        kinds = ('world',)
    elif r < 13:
        kinds = ('world', 'world', 'fallacy')
    else:
        kinds = ('world', 'chain', 'fallacy', 'formal')
    return Grade(r, kinds, forms, 10 <= r < 13 or r >= 16,
                 Q.pace(r, slow=1.8, fast=3.5, base=6.0, floor=3.0),
                 20, 0.75)


def _ask(level: Grade, arg: Optional[Argument], draw) -> F.Step:
    if level.name and arg is not None:
        return Q.step(_('What is wrong with it?'), NAMES,
                      NAMES.index(FLAWS[arg.form]), draw)
    valid = arg.valid if arg is not None else None
    return Q.step(_('Does the conclusion follow?'),
                  (_('it follows'), _('it does not follow')),
                  0 if valid else 1, draw, keep_order=True)


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    cells = [(v, b) for v in (True, False) for b in (True, False)]
    turn = [0]
    # a source not fetched (and without written stand-ins) is left out
    kinds = tuple(k for k in level.kinds
                  if k not in ('fallacy', 'formal') or D.of(k))
    data = {k: Q.deck(D.of(k), draw) for k in ('fallacy', 'formal')
            if k in kinds}

    def make(kind):
        if kind in data:
            q = data[kind]()
            if q is None:
                return None
            st = Q.step(_('Does the conclusion follow?'),
                        (_('it follows'), _('it does not follow')),
                        q.answer, draw, keep_order=True)
            return Q.item(q.prompt, [st], level.pace, title=_('An argument'))
        if kind == 'chain':
            arg = chain(draw.random() < 0.5, draw)
        elif kind == 'nonsense':
            arg = nonsense(draw.choice(level.forms), draw)
        else:
            valid, believable = cells[turn[0] % 4]
            forms = [f for f in level.forms if
                     (f in ('mp', 'mt', 'barbara', 'celarent')) == valid]
            arg = worldly(draw.choice(forms), believable, draw)
            if arg is None:
                return None
            turn[0] += 1
        st = _ask(level, arg, draw)
        if level.name:
            truth = FLAWS[arg.form]
        else:
            truth = _('it follows') if arg.valid else _('it does not follow')
        return Q.item(arg.text, [st], level.pace, title=_('An argument'),
                      truth=truth)

    items = Q.mixed(kinds, level.items, draw, make)
    if len(items) < level.items:
        return None
    return Q.assemble(level, items, level.skill)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
