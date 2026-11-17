# -*- coding: utf-8 -*-
"""The Linguist: work out a language you have never seen, and use it.

Every trial deals a new language in a new script. A few sentences are
shown, each beside a picture of what it says -- shapes, their colour,
size and number, and who does what to whom -- and then one question:
which sentence says this picture, which picture this sentence says, or
(higher up) build the sentence yourself from word tiles. Nothing can
be remembered from one trial to the next; what carries over is how
languages are put together.

The languages are a family with these things free to vary:

* the words themselves, and the letters they are written in;
* word order: where the doer, the deed and the done-to go;
* whether the describing word comes before or after its thing;
* how "more than one" and "big" are marked on a word: a letter before
  it, a letter after it, or (for more than one) its own first or last
  letter said twice;
* whether the deed-word agrees in number with the doer, with the
  done-to, or with neither, and whether describing words agree;
* marking who is who on the word itself, with the order left free;
* clauses inside clauses -- "the square that pushes the circle that
  sees the star" -- with the inner clause before or after its thing,
  to any depth.

A trial is dealt only when the examples settle the answer: every
language of the family that accounts for all the examples gives the
same one. :func:`solve` is that learner, and reads nothing else.

For the agent boundary: ports 0-7 pick an answer; when a sentence is
to be built, ports 0-9 take a tile, port 10 takes the last one back
and port 11 says it is done.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import scenes
from .i18n import _

PORTS = 12
UNDO, DONE = 10, 11
STEM = 2                         # letters in a stem

SHAPES = ('circle', 'square', 'triangle', 'diamond', 'pentagon', 'star',
          'cross', 'bar')
COLOURS = ((214, 64, 58), (58, 110, 214), (60, 160, 90), (226, 180, 40))
PLAIN = (150, 150, 158)
ORDERS = ('SVO', 'SOV', 'VSO', 'VOS', 'OSV', 'OVS')

Word = Tuple[int, ...]
Sentence = Tuple[Word, ...]


class Thing(NamedTuple):
    shape: int
    colour: int = -1             # -1: none said
    plural: bool = False
    big: bool = False


class Scene(NamedTuple):
    """The things, and who does what to whom: the first deed is the
    main one, each later one is done by the one before's done-to."""
    things: Tuple[Thing, ...]
    deeds: Tuple[Tuple[int, int, int], ...] = ()     # doer, deed, done-to


class Tongue(NamedTuple):
    """How a language of the family is put together."""
    order: str = 'SVO'
    adj: int = 0                 # the describing word: 0 before, 1 after
    pl: str = 'suf'              # 'pre', 'suf', 'rf', 'rl'
    big: str = 'suf'             # 'pre', 'suf'
    agr: Optional[Tuple[str, str]] = None    # (whom 'S'/'O', 'pre'/'suf')
    adjagr: bool = False
    case: Optional[Tuple[str, str]] = None   # (whom, where); order is free
    rel: int = 0                 # the inner clause: 0 after, 1 before
    relorder: int = 0            # inside it: 0 deed first, 1 done-to first


class Slot(NamedTuple):
    pre: Tuple[str, ...]
    key: object                  # ('s', shape), ('c', colour), ('v', deed), 'rel'
    suf: Tuple[str, ...]
    twice: str = ''              # 'rf', 'rl': a letter of the stem again


class Grade(NamedTuple):
    rung: int
    kinds: Tuple[str, ...]
    has: Tuple[str, ...]         # what the family may vary
    depth: int                   # clauses inside clauses
    options: int
    letters: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    both = ('describe', 'read')
    all3 = ('describe', 'read', 'build')
    if r < 4:
        return Grade(r, ('match',), (), 0, 4, 6 + r)
    if r < 7:
        return Grade(r, both, ('colour',), 0, 4, 8)
    if r < 10:
        return Grade(r, both, ('colour', 'order'), 0, 4, 8)
    if r < 13:
        return Grade(r, all3, ('colour', 'order', 'plural', 'big'), 0, 4, 9)
    if r < 16:
        return Grade(r, all3, ('colour', 'order', 'plural', 'big', 'agr'),
                     0, 6, 9)
    if r < 19:
        return Grade(r, all3, ('colour', 'order', 'plural', 'big', 'agr',
                               'twice'), 0, 6, 10)
    if r < 22:
        return Grade(r, all3, ('colour', 'order', 'plural', 'big', 'agr',
                               'twice', 'case'), 0, 6, 10)
    return Grade(r, all3, ('colour', 'order', 'plural', 'big', 'agr',
                           'twice', 'case', 'rel'),
                 1 if r < 25 else 2 + (r - 25) // 3, 6, 10)


# --- saying ---------------------------------------------------------------

def _noun(h: Tongue, thing: Thing, case: bool) -> List[Slot]:
    pre: List[str] = []
    suf: List[str] = []
    twice = h.pl if thing.plural and h.pl in ('rf', 'rl') else ''
    if thing.big:
        (pre if h.big == 'pre' else suf).append('big')
    if thing.plural and h.pl in ('pre', 'suf'):
        (pre if h.pl == 'pre' else suf).append('pl')
    if case and h.case:
        (pre if h.case[1] == 'pre' else suf).append('case')
    out = [Slot(tuple(reversed(pre)), ('s', thing.shape), tuple(suf), twice)]
    if thing.colour >= 0:
        agree = h.adjagr and thing.plural
        a = Slot(('pl',) if agree and h.pl == 'pre' else (),
                 ('c', thing.colour),
                 ('pl',) if agree and h.pl == 'suf' else (),
                 h.pl if agree and h.pl in ('rf', 'rl') else '')
        out = out + [a] if h.adj else [a] + out
    return out


def _phrase(h: Tongue, scene: Scene, who: int, role: str,
            deed: int) -> List[Slot]:
    """A thing, with whatever it does next folded in behind it."""
    out = _noun(h, scene.things[who],
                bool(h.case) and h.case[0] == role)
    if deed < len(scene.deeds):
        a, v, p = scene.deeds[deed]
        verb = [_verb(h, scene, a, v, p)]
        done = _phrase(h, scene, p, 'O', deed + 1)
        inner = [Slot((), 'rel', ())] + (done + verb if h.relorder
                                         else verb + done)
        out = inner + out if h.rel else out + inner
    return out


def _verb(h: Tongue, scene: Scene, a: int, v: int, p: int) -> Slot:
    agree = h.agr is not None and \
        scene.things[a if h.agr[0] == 'S' else p].plural
    return Slot(('agr',) if agree and h.agr[1] == 'pre' else (), ('v', v),
                ('agr',) if agree and h.agr[1] == 'suf' else ())


def template(h: Tongue, scene: Scene,
             order: Optional[str] = None) -> List[Slot]:
    """The words of *scene* in a language built like *h*, as slots."""
    if not scene.deeds:
        return _noun(h, scene.things[0], False)
    a, v, p = scene.deeds[0]
    parts = {'S': _noun(h, scene.things[a],
                        bool(h.case) and h.case[0] == 'S'),
             'V': [_verb(h, scene, a, v, p)],
             'O': _phrase(h, scene, p, 'O', 1)}
    return [slot for part in (order or h.order) for slot in parts[part]]


def orders(h: Tongue, scene: Scene) -> Tuple[Optional[str], ...]:
    if not scene.deeds:
        return (None,)
    return ORDERS if h.case else (h.order,)


def realise(slots: List[Slot], words: Dict) -> Optional[Sentence]:
    """The sentence, or None if a word it needs is not known."""
    out = []
    for slot in slots:
        stem = words.get(slot.key)
        if stem is None:
            return None
        if slot.key == 'rel':
            out.append(stem)
            continue
        marks = [words.get(m) for m in slot.pre + slot.suf]
        if any(m is None for m in marks):
            return None
        n = len(slot.pre)
        out.append(tuple(m[0] for m in marks[:n])
                   + ((stem[0],) if slot.twice == 'rf' else ())
                   + stem
                   + ((stem[-1],) if slot.twice == 'rl' else ())
                   + tuple(m[0] for m in marks[n:]))
    return tuple(out)


def says(h: Tongue, words: Dict, scene: Scene) -> Optional[frozenset]:
    """Every way the language says *scene*; None if it lacks a word."""
    out = set()
    for order in orders(h, scene):
        s = realise(template(h, scene, order), words)
        if s is None:
            return None
        out.add(s)
    return frozenset(out)


# --- learning -------------------------------------------------------------

def _read(slots: List[Slot], sentence: Sentence, words: Dict
          ) -> Optional[Dict]:
    """What *sentence* teaches a learner who takes it to be *slots*:
    the words known so far and those it adds, or None if it cannot be."""
    if len(slots) != len(sentence):
        return None
    new = dict(words)

    def learn(key, value) -> bool:
        if key in new:
            return new[key] == value
        if isinstance(key, tuple) or key == 'rel':
            # Two things never share a word.
            if any(v == value for k, v in new.items()
                   if isinstance(k, tuple) or k == 'rel'):
                return False
        new[key] = value
        return True

    for slot, word in zip(slots, sentence):
        if slot.key == 'rel':
            if not learn('rel', word):
                return None
            continue
        a = len(slot.pre) + (slot.twice == 'rf')
        b = len(slot.suf) + (slot.twice == 'rl')
        if len(word) != a + STEM + b:
            return None
        stem = word[a:a + STEM]
        if not learn(slot.key, stem):
            return None
        if slot.twice == 'rf' and word[a - 1] != stem[0]:
            return None
        if slot.twice == 'rl' and word[a + STEM] != stem[-1]:
            return None
        for i, mark in enumerate(slot.pre):
            if not learn(mark, (word[i],)):
                return None
        for i, mark in enumerate(slot.suf):
            if not learn(mark, (word[len(word) - len(slot.suf) + i],)):
                return None
    return new


def family(level: Grade) -> List[Tongue]:
    """Every way a language of this rung may be put together."""
    has = level.has
    case = [(w, p) for w in 'SO' for p in ('pre', 'suf')] \
        if 'case' in has else [None]
    out = []
    for order, adj, pl, big, agr, adjagr, cs, rel, relorder in \
            itertools.product(
                ORDERS if 'order' in has and 'case' not in has else ('SVO',),
                (0, 1) if 'colour' in has else (0,),
                (('pre', 'suf', 'rf', 'rl') if 'twice' in has
                 else ('pre', 'suf')) if 'plural' in has else ('suf',),
                ('pre', 'suf') if 'big' in has else ('suf',),
                [None] + [(w, p) for w in 'SO' for p in ('pre', 'suf')]
                if 'agr' in has else [None],
                (False, True) if 'agr' in has else (False,),
                case,
                (0, 1) if 'rel' in has else (0,),
                (0, 1) if 'rel' in has else (0,)):
        out.append(Tongue(order, adj, pl, big, agr, adjagr, cs, rel,
                          relorder))
    return out


def learn(states, scene: Scene, sentence: Sentence):
    """The readings of everything so far that also take this in."""
    out, seen = [], set()
    for h, words in states:
        for order in orders(h, scene):
            new = _read(template(h, scene, order), sentence, words)
            if new is None:
                continue
            mark = (h, tuple(sorted(new.items(), key=repr)))
            if mark not in seen:
                seen.add(mark)
                out.append((h, new))
    return out


def _verdict(kind: str, states, scene: Scene, sentence, options):
    """What the readings left say the answer is: a set of options (or,
    to build, of sentences), or None while any of them is unsure."""
    answer = None
    for h, words in states:
        if kind == 'read':
            fits = []
            for i, other in enumerate(options):
                said = says(h, words, other)
                if said is None:
                    return None
                if sentence in said:
                    fits.append(i)
            mine = frozenset(fits)
        else:
            said = says(h, words, scene)
            if said is None:
                return None
            mine = said if kind == 'build' else frozenset(
                i for i, option in enumerate(options) if option in said)
        if answer is None:
            answer = mine
        elif answer != mine:
            return None
    return answer


# --- the deal ---------------------------------------------------------------

class Puzzle(NamedTuple):
    level: Grade
    kind: str                    # 'match', 'describe', 'read', 'build'
    glyphs: Tuple[Tuple, ...]    # each letter's strokes
    examples: Tuple[Tuple[Scene, Sentence], ...]
    scene: Optional[Scene]       # what is asked about
    sentence: Optional[Sentence]     # the sentence shown ('read', 'match')
    options: Tuple               # sentences, scenes or (to build) tiles
    choices: Tuple[str, ...]
    answer: int                  # -1 to build
    valid: frozenset             # the sentences that are right, to build
    truth: Optional[Sentence]
    said: str                    # how the language works, for afterwards
    seed: int
    question: str


def _glyphs(draw: random.Random, n: int) -> Tuple[Tuple, ...]:
    """*n* letters: three or four strokes each on a 3 x 3 lattice."""
    points = [(x, y) for x in range(3) for y in range(3)]
    out, seen = [], set()
    while len(out) < n:
        at = draw.choice(points)
        strokes = set()
        for _k in range(draw.choice((3, 3, 4))):
            to = draw.choice([p for p in points if p != at
                              and (abs(p[0] - at[0]) != 2
                                   or abs(p[1] - at[1]) != 2 or True)])
            strokes.add((min(at, to), max(at, to)))
            at = to
        mark = tuple(sorted(strokes))
        if len(mark) >= 3 and mark not in seen:
            seen.add(mark)
            out.append(mark)
    return tuple(out)


def _lexicon(draw: random.Random, level: Grade) -> Dict:
    letters = list(range(level.letters))
    stems = [tuple(p) for p in itertools.product(letters, repeat=STEM)]
    draw.shuffle(stems)
    words: Dict = {}
    for i in range(len(SHAPES)):
        words[('s', i)] = stems.pop()
    for i in range(len(COLOURS)):
        words[('c', i)] = stems.pop()
    for i in range(3):
        words[('v', i)] = stems.pop()
    words['rel'] = stems.pop()
    marks = draw.sample(letters, 4)
    for name, letter in zip(('pl', 'big', 'agr', 'case'), marks):
        words[name] = (letter,)
    return words


def _thing(draw: random.Random, level: Grade, shape: int, colours,
           plain: bool = False) -> Thing:
    has = level.has
    colour = draw.choice(colours) if 'colour' in has and not plain \
        and draw.random() < 0.6 else -1
    return Thing(shape, colour,
                 'plural' in has and not plain and draw.random() < 0.4,
                 'big' in has and not plain and draw.random() < 0.3)


def _scene(draw: random.Random, level: Grade, shapes, colours, verbs,
           depth: int, plain: bool = False) -> Scene:
    if 'order' not in level.has:
        return Scene((_thing(draw, level, draw.choice(shapes), colours,
                             plain)._replace(
            colour=-1 if plain else draw.choice(colours)),))
    picked = draw.sample(shapes, min(len(shapes), depth + 2))
    while len(picked) < depth + 2:
        picked.append(draw.choice(shapes))
    things = tuple(_thing(draw, level, s, colours, plain) for s in picked)
    deeds = tuple((k, draw.choice(verbs), k + 1) for k in range(depth + 1))
    return Scene(things, deeds)


def _pool(draw: random.Random, level: Grade, shapes, colours, verbs
          ) -> List[Scene]:
    """Scenes to teach from, the plainest first."""
    has = level.has
    out = [Scene((Thing(s),)) for s in shapes]
    out += [Scene((Thing(draw.choice(shapes), c),)) for c in colours]
    if 'order' in has:
        for v in verbs:
            a, b = draw.sample(shapes, 2)
            out.append(Scene((Thing(a), Thing(b)), ((0, v, 1),)))
    if 'plural' in has:
        a, b = draw.sample(shapes, 2)
        out += [Scene((Thing(a, plural=True),)),
                Scene((Thing(b, plural=True),)),
                Scene((Thing(a, draw.choice(colours), True),))]
    if 'big' in has:
        a, b = draw.sample(shapes, 2)
        out += [Scene((Thing(a, big=True),)),
                Scene((Thing(b, plural=True, big=True),))]
    if 'agr' in has:
        for one, two in ((True, False), (False, True)):
            a, b = draw.sample(shapes, 2)
            out.append(Scene((Thing(a, plural=one), Thing(b, plural=two)),
                             ((0, draw.choice(verbs), 1),)))
    if 'rel' in has:
        for _k in range(2):
            out.append(_scene(draw, level, shapes, colours, verbs, 1, True))
    for _k in range(14):
        out.append(_scene(draw, level, shapes, colours, verbs,
                          min(1, level.depth)))
    return out


def _turns(level: Grade, scene: Scene, h: Tongue, shapes, colours, verbs,
           draw: random.Random, pictures: bool) -> List:
    """The ways an answer can be made wrong: each a (scene, tongue)
    given the right pair. With *pictures* only what a picture shows."""
    has = level.has
    out = []
    n = len(scene.things)

    def thing(i, **change):
        def turn(s, t):
            things = list(s.things)
            things[i] = things[i]._replace(**{
                k: (v(things[i]) if callable(v) else v)
                for k, v in change.items()})
            return s._replace(things=tuple(things)), t
        return turn
    for i in range(n):
        spare = [s for s in shapes if all(s != t.shape for t in scene.things)]
        if spare:
            out.append(thing(i, shape=draw.choice(spare)))
        if scene.things[i].colour >= 0 and len(colours) > 1:
            other = draw.choice([c for c in colours
                                 if c != scene.things[i].colour])
            out.append(thing(i, colour=other))
        if 'plural' in has:
            out.append(thing(i, plural=lambda t: not t.plural))
        if 'big' in has:
            out.append(thing(i, big=lambda t: not t.big))
    if scene.deeds:
        def swap(s, t):
            things = list(s.things)
            things[0], things[1] = things[1], things[0]
            return s._replace(things=tuple(things)), t
        out.append(swap)
        if len(verbs) > 1:
            k = draw.randrange(len(scene.deeds))
            other = draw.choice([v for v in verbs if v != scene.deeds[k][1]])

            def deed(s, t):
                deeds = list(s.deeds)
                deeds[k] = (deeds[k][0], other, deeds[k][2])
                return s._replace(deeds=tuple(deeds)), t
            out.append(deed)
    if pictures:
        return out
    if any(t.colour >= 0 for t in scene.things):
        out.append(lambda s, t: (s, t._replace(adj=1 - t.adj)))
    if scene.deeds and not h.case:
        out.append(lambda s, t: (s, t._replace(
            order=t.order[1] + t.order[0] + t.order[2])))
    if 'plural' in has and any(t.plural for t in scene.things):
        flip = {'pre': 'suf', 'suf': 'pre', 'rf': 'rl', 'rl': 'rf'}
        out.append(lambda s, t: (s, t._replace(pl=flip[t.pl])))
    if h.agr is not None and scene.deeds:
        out.append(lambda s, t: (s, t._replace(
            agr=('O' if t.agr[0] == 'S' else 'S', t.agr[1]))))
    if h.case and scene.deeds:
        out.append(lambda s, t: (s, t._replace(
            case=('O' if t.case[0] == 'S' else 'S', t.case[1]))))
    if len(scene.deeds) > 1:
        out.append(lambda s, t: (s, t._replace(rel=1 - t.rel)))
    return out


def _corners(draw: random.Random, n: int) -> List[Tuple[int, ...]]:
    """Which turns each answer takes: the corners of a cube, so that
    each turn is taken by as many answers as leave it."""
    axes = 2 if n == 4 else 3
    corners = list(itertools.product((0, 1), repeat=axes))
    if n == 6:
        gone = draw.choice([c for c in corners if 0 < sum(c) < axes])
        corners = [c for c in corners
                   if c != gone and c != tuple(1 - v for v in gone)]
    return corners


def _describe(h: Tongue, level: Grade) -> str:
    said = []
    if 'order' not in level.has:
        pass
    elif h.case:
        said.append(_('order free, the %s marked')
                    % (_('doer') if h.case[0] == 'S' else _('done-to')))
    else:
        said.append(_('order %s') % '-'.join(
            {'S': _('doer'), 'V': _('deed'), 'O': _('done-to')}[c]
            for c in h.order))
    said.append(_('describing word %s') % (_('after') if h.adj
                                           else _('before')))
    if 'plural' in level.has:
        said.append(_('more-than-one: %s') % {
            'pre': _('a letter before'), 'suf': _('a letter after'),
            'rf': _('first letter twice'),
            'rl': _('last letter twice')}[h.pl])
    if h.agr:
        said.append(_('deed agrees with the %s')
                    % (_('doer') if h.agr[0] == 'S' else _('done-to')))
    return ';  '.join(said)


def _match(level: Grade, draw: random.Random, seed: int) -> Puzzle:
    glyphs = _glyphs(draw, level.letters)
    size = 2 + level.rung
    word = tuple(draw.randrange(level.letters) for _k in range(size))
    options = {word}
    while len(options) < level.options:
        other = list(word)
        if level.rung == 1:
            other = [draw.randrange(level.letters) for _k in range(size)]
        elif draw.random() < 0.5 and level.rung > 2:
            k = draw.randrange(size - 1)
            other[k], other[k + 1] = other[k + 1], other[k]
        else:
            other[draw.randrange(size)] = draw.randrange(level.letters)
        options.add(tuple(other))
    options = list(options)
    draw.shuffle(options)
    sentences = tuple((o,) for o in options)
    return Puzzle(level, 'match', glyphs, (), None, (word,), sentences,
                  tuple(str(i + 1) for i in range(len(options))),
                  options.index(word), frozenset(), (word,), '', seed,
                  _('Which is the same word?'))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    for attempt in range(400):
        draw = random.Random(seed * 1000 + attempt)
        if level.kinds == ('match',):
            return _match(level, draw, seed)
        made = _try(level, draw, seed)
        if made is not None:
            return made
    raise RuntimeError('no language for rung %d' % rung)


def _try(level: Grade, draw: random.Random, seed: int) -> Optional[Puzzle]:
    kind = draw.choice(level.kinds)
    hs = family(level)
    h = draw.choice(hs)
    words = _lexicon(draw, level)
    shapes = draw.sample(range(len(SHAPES)),
                         min(len(SHAPES), level.depth + 3))
    colours = draw.sample(range(len(COLOURS)), 2 if level.rung < 13 else 3)
    verbs = draw.sample(range(3), 2)
    scene = _scene(draw, level, shapes, colours, verbs, level.depth)
    # The question shows what its rung is about.
    has = level.has
    if 'plural' in has and not any(t.plural or t.big for t in scene.things):
        return None
    if 'agr' in has and not any(t.plural for t in scene.things):
        return None

    def say(s: Scene, t: Tongue = h) -> Optional[Sentence]:
        return realise(template(t, s, draw.choice(orders(t, s))), words)

    truth = say(scene)
    valid = says(h, words, scene)
    if kind == 'build' and not 3 <= len(truth) <= 8:
        kind = 'describe'
    turns = _turns(level, scene, h, shapes, colours, verbs, draw,
                   kind == 'read')
    options: List = []
    answer = -1
    if kind in ('describe', 'read'):
        corners = _corners(draw, level.options)
        axes = len(corners[0])
        if len(turns) < axes:
            return None
        for _again in range(30):
            picked = draw.sample(turns, axes)
            options = []
            for corner in corners:
                s, t = scene, h
                for turn, on in zip(picked, corner):
                    if on:
                        s, t = turn(s, t)
                options.append(s if kind == 'read' else say(s, t))
            wrong = [o for o, c in zip(options, corners) if any(c)]
            if len(set(options)) < len(options):
                continue
            if kind == 'describe' and any(o in valid for o in wrong):
                continue
            if kind == 'read' and any(truth in says(h, words, o)
                                      for o in wrong):
                continue
            break
        else:
            return None
        right = options[0]
        draw.shuffle(options)
        answer = options.index(right)
    else:
        s, t = draw.choice(turns)(scene, h)
        extra = [w for w in dict.fromkeys(say(s, t)) if w not in truth]
        tiles = list(truth) + extra[:max(0, min(3, 10 - len(truth)))]
        draw.shuffle(tiles)
        options = tiles
    # Teach until the answer is settled.
    states = [(t, {}) for t in hs]
    examples: List[Tuple[Scene, Sentence]] = []
    shown = {scene} | (set(options) if kind == 'read' else set())
    want = valid if kind == 'build' else frozenset((answer,))
    settled = False
    for lesson in _pool(draw, level, shapes, colours, verbs):
        if lesson in shown:
            continue
        sentence = say(lesson)
        if sentence == truth:
            continue
        after = learn(states, lesson, sentence)
        if len(after) == len(states) and all(
                len(a[1]) == len(b[1]) for a, b in zip(after, states)):
            continue                 # it taught nothing
        states = after
        shown.add(lesson)
        examples.append((lesson, sentence))
        if _verdict(kind, states, scene, truth, options) == want:
            settled = True
            break
    if not settled:
        return None
    # Then take back every example the answer does not hang on, the
    # last first: what was learnt before it need not be learnt again.
    before = [[(t, {}) for t in hs]]
    for shown_scene, sentence in examples[:-1]:
        before.append(learn(before[-1], shown_scene, sentence))
    kept: List[Tuple[Scene, Sentence]] = []      # of those after it
    for at in range(len(examples) - 1, -1, -1):
        states = before[at]
        for shown_scene, sentence in kept:
            states = learn(states, shown_scene, sentence)
        if _verdict(kind, states, scene, truth, options) != want:
            kept.insert(0, examples[at])
    examples = kept
    if len(examples) > 12:
        return None                  # more than the page holds
    n = len(options)
    question = {'describe': _('Which sentence says this picture?'),
                'read': _('Which picture does this sentence say?'),
                'build': _('Say this picture: take the words in order')}[kind]
    return Puzzle(level, kind, _glyphs(draw, level.letters), tuple(examples),
                  scene, truth, tuple(options),
                  tuple(str(i + 1) for i in range(n)), answer,
                  valid if kind == 'build' else frozenset(), truth,
                  _describe(h, level), seed, question)


def check(p: Puzzle, taken) -> bool:
    """Whether the tiles *taken*, in order, say the picture."""
    return tuple(p.options[i] for i in taken) in p.valid


def solve(p: Puzzle):
    """The answer worked out from what the trial shows and nothing
    else: an option, or the ports that build the sentence. None if the
    examples leave it open."""
    if p.kind == 'match':
        return p.options.index(p.sentence)
    states = [(t, {}) for t in family(p.level)]
    for scene, sentence in p.examples:
        states = learn(states, scene, sentence)
    found = _verdict(p.kind, states, p.scene, p.sentence, p.options)
    if not found:
        return None
    if p.kind != 'build':
        return next(iter(found)) if len(found) == 1 else None
    for sentence in sorted(found):
        left = list(range(len(p.options)))
        ports = []
        for word in sentence:
            at = next((i for i in left if p.options[i] == word), None)
            if at is None:
                break
            left.remove(at)
            ports.append(at)
        else:
            return ports + [DONE]
    return None


# --- the page ---------------------------------------------------------------

INK = scenes.INK
RIGHT, WRONG = (40, 150, 80), (200, 60, 55)
BOX = (236, 238, 244)


def _poly(shape: str, cx, cy, r):
    def ring(n, turn=0.0, inner=None):
        pts = []
        for k in range(n * (2 if inner else 1)):
            a = turn + 2 * math.pi * k / (n * (2 if inner else 1))
            q = r * (inner if inner and k % 2 else 1.0)
            pts.append((cx + q * math.sin(a), cy + q * math.cos(a)))
        return pts
    if shape == 'square':
        return ring(4, math.pi / 4)
    if shape == 'triangle':
        return ring(3)
    if shape == 'diamond':
        return [(cx, cy + r), (cx + r * 0.62, cy), (cx, cy - r),
                (cx - r * 0.62, cy)]
    if shape == 'pentagon':
        return ring(5)
    if shape == 'star':
        return ring(5, 0.0, 0.45)
    if shape == 'cross':
        a, b = r * 0.36, r
        return [(cx - a, cy + b), (cx + a, cy + b), (cx + a, cy + a),
                (cx + b, cy + a), (cx + b, cy - a), (cx + a, cy - a),
                (cx + a, cy - b), (cx - a, cy - b), (cx - a, cy - a),
                (cx - b, cy - a), (cx - b, cy + a), (cx - a, cy + a)]
    return [(cx - r, cy + r * 0.38), (cx + r, cy + r * 0.38),
            (cx + r, cy - r * 0.38), (cx - r, cy - r * 0.38)]      # bar


def _draw_thing(out: List, thing: Thing, cx, cy, r) -> None:
    colour = COLOURS[thing.colour] if thing.colour >= 0 else PLAIN
    r = r * (1.0 if thing.big else 0.6)
    spots = [(cx, cy)]
    if thing.plural:
        r *= 0.62
        spots = [(cx - r * 1.15, cy - r * 0.8), (cx + r * 1.15, cy - r * 0.8),
                 (cx, cy + r * 0.95)]
    for x, y in spots:
        if SHAPES[thing.shape] == 'circle':
            out.append(scenes.disc(x, y, r, colour))
        elif SHAPES[thing.shape] in ('cross',):
            a = r * 0.36
            out.append(scenes.rect(x - a, y - r, 2 * a, 2 * r, colour))
            out.append(scenes.rect(x - r, y - a, 2 * r, 2 * a, colour))
        else:
            out.append(scenes.poly(_poly(SHAPES[thing.shape], x, y, r),
                                   colour))


def picture(out: List, scene: Scene, x, y, w, h, back=BOX) -> None:
    """Who is there and who does what to whom."""
    out.append(scenes.rect(x, y, w, h, back))
    n = len(scene.things)
    order = list(range(n))
    scenes.stream(hash(scene) & 0xffffff).shuffle(order)
    r = min(h * (0.30 if scene.deeds else 0.36), w / n * 0.34)
    cy = y + h * (0.36 if scene.deeds else 0.5)
    at = {who: x + w * (slot + 0.5) / n for slot, who in enumerate(order)}
    for who, thing in enumerate(scene.things):
        _draw_thing(out, thing, at[who], cy, r)
    for k, (a, verb, p) in enumerate(scene.deeds):
        x0, x1 = at[a], at[p]
        y0 = cy + r * 1.15
        lift = min(h * 0.34, h * 0.16 + abs(x1 - x0) * 0.25) \
            + (k % 2) * h * 0.05
        pts = []
        for step in range(15):
            u = step / 14.0
            pts.append((x0 + (x1 - x0) * u, y0 + 4 * lift * u * (1 - u)))
        thick = max(0.004, h * 0.022)
        if verb == 1:                # dashed
            for step in range(0, 14, 2):
                out.append(scenes.line(*pts[step], *pts[step + 1], thick,
                                       INK))
        else:
            out += scenes.polyline(pts[:14], thick, INK)
            if verb == 2:            # doubled
                out += scenes.polyline([(px, py + thick * 2.6)
                                        for px, py in pts[1:13]], thick, INK)
        # The head, at the done-to.
        (ax, ay), (bx, by) = pts[12], pts[14]
        d = math.hypot(bx - ax, by - ay) or 1.0
        ux, uy = (bx - ax) / d, (by - ay) / d
        s = max(0.012, h * 0.075)
        out.append(scenes.poly([(bx, by),
                                (bx - ux * s - uy * s * 0.6,
                                 by - uy * s + ux * s * 0.6),
                                (bx - ux * s + uy * s * 0.6,
                                 by - uy * s - ux * s * 0.6)], INK))


def write(out: List, glyphs, sentence: Sentence, cx, cy, size, most,
          colour=INK) -> None:
    """A sentence in the trial's script, centred, shrunk to fit."""
    def width(s):
        return sum(len(w) for w in sentence) * s * 0.78 \
            + (len(sentence) - 1) * s * 0.95
    if width(size) > most:
        size *= most / width(size)
    x = cx - width(size) / 2
    cell = size * 0.6
    for word in sentence:
        for letter in word:
            for (ax, ay), (bx, by) in glyphs[letter]:
                out.append(scenes.line(
                    x + ax * cell / 2, cy - size / 2 + ay * size / 2,
                    x + bx * cell / 2, cy - size / 2 + by * size / 2,
                    max(0.0025, size * 0.085), colour))
            x += size * 0.78
        x += size * 0.95


def scene(p: Puzzle, taken=(), judged: bool = False) -> List:
    """The page: the examples above, the question below."""
    out: List = []
    W = scenes.W
    g = p.glyphs
    if p.kind == 'match':
        write(out, g, p.sentence, W / 2, 0.76, 0.16, W * 0.8)
        for i, option in enumerate(p.options):
            x, y = 0.12 + (i % 2) * 0.7, 0.34 - (i // 2) * 0.22
            out.append(scenes.rect(x, y, 0.66, 0.18, BOX))
            write(out, g, option, x + 0.35, y + 0.09, 0.09, 0.52)
            out.append(scenes.text(x + 0.035, y + 0.14, 0.035, str(i + 1)))
            out.append(scenes.hit(x, y, 0.66, 0.18, i))
        return out
    n = len(p.examples)
    cols = min(n, 4) if n <= 8 else (n + 2) // 3
    rows = (n + cols - 1) // cols
    top, low = 0.985, 0.455
    cw, ch = (W - 0.06) / cols, (top - low) / rows
    for i, (shown, sentence) in enumerate(p.examples):
        x = 0.03 + (i % cols) * cw
        y = top - (i // cols + 1) * ch
        picture(out, shown, x + cw * 0.04, y + ch * 0.34, cw * 0.92,
                ch * 0.62)
        write(out, g, sentence, x + cw / 2, y + ch * 0.17,
              min(0.05, ch * 0.2), cw * 0.9)
    out.append(scenes.line(0.03, 0.435, W - 0.03, 0.435, 0.004,
                           (150, 152, 162)))
    lx, ly, lw, lh = 0.03, 0.03, 0.5, 0.375
    if p.kind == 'read':
        out.append(scenes.rect(lx, ly + 0.1, lw, 0.17, (250, 244, 214)))
        write(out, g, p.sentence, lx + lw / 2, ly + 0.185, 0.06, lw * 0.92)
    else:
        picture(out, p.scene, lx, ly, lw, lh, (250, 244, 214))
    rx, rw = 0.57, W - 0.60
    if p.kind == 'build':
        out.append(scenes.rect(rx, 0.315, rw, 0.09, BOX))
        said = tuple(p.options[i] for i in taken)
        if judged:
            write(out, g, p.truth, rx + rw / 2, 0.36, 0.05, rw * 0.94,
                  RIGHT)
        elif said:
            write(out, g, said, rx + rw / 2, 0.36, 0.05, rw * 0.94)
        tw = rw / 5
        for i, word in enumerate(p.options):
            x, y = rx + (i % 5) * tw, 0.215 - (i // 5) * 0.095
            used = i in taken
            out.append(scenes.rect(x + 0.006, y, tw - 0.012, 0.085,
                                   (214, 216, 224) if used else BOX))
            write(out, g, (word,), x + tw / 2, y + 0.043, 0.042, tw * 0.8,
                  (170, 172, 182) if used else INK)
            out.append(scenes.hit(x + 0.006, y, tw - 0.012, 0.085, i))
        for port, words, x in ((UNDO, _('Back'), rx),
                               (DONE, _('Done'), rx + rw / 2)):
            out.append(scenes.rect(x + 0.006, 0.03, rw / 2 - 0.012, 0.075,
                                   BOX))
            out.append(scenes.text(x + rw / 4, 0.067, 0.036, words))
            out.append(scenes.hit(x + 0.006, 0.03, rw / 2 - 0.012, 0.075,
                                  port))
        return out
    m = len(p.options)
    if p.kind == 'read':
        cols = 2 if m <= 4 else 3
    else:
        cols = 1 if m <= 4 or len(p.truth) > 5 else 2
    rows = (m + cols - 1) // cols
    ow, oh = rw / cols, lh / rows
    for i, option in enumerate(p.options):
        x = rx + (i % cols) * ow
        y = ly + lh - (i // cols + 1) * oh
        if p.kind == 'read':
            picture(out, option, x + 0.006, y + 0.006, ow - 0.012,
                    oh - 0.012)
        else:
            out.append(scenes.rect(x + 0.006, y + 0.006, ow - 0.012,
                                   oh - 0.012, BOX))
            write(out, g, option, x + ow / 2 + 0.02, y + oh / 2,
                  min(0.05, oh * 0.42), ow - 0.11)
        out.append(scenes.text(x + 0.032, y + oh - 0.035, 0.03, str(i + 1)))
        out.append(scenes.hit(x + 0.006, y + 0.006, ow - 0.012, oh - 0.012,
                              i))
    return out
