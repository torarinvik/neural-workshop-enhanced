# -*- coding: utf-8 -*-
"""Why They Feel: what would anyone feel, in their place?

Short stories made up here, each built so that one emotion follows from
it, by the appraisal theory of Ortony, Clore and Collins: an emotion
is how a person sees what happened -- good or bad for what they want,
certain or still to come, done by them or by someone else, praiseworthy
or not, to someone they like or someone they don't.

=================  ===========================================  ======
kind               the story                                    emotion
=================  ===========================================  ======
happened           what they wanted happened / did not          happy, sad
still to come      it is not known yet; the signs are good/bad  hopeful,
                                                                worried
turned out         feared, then it went well / hoped for, then  relieved,
                   it went badly                                disappointed
their own doing    they did something good / shameful / that    proud,
                   hurt a friend                                ashamed,
                                                                remorseful
someone else's     another did something good / bad / that      admiring,
                   helped them / that got in their way          disapproving,
                                                                grateful, angry
another's fortune  good or bad news for a friend / for someone  glad for them,
                   they can't stand                             sorry for them,
                                                                resentful,
                                                                gloating
=================  ===========================================  ======

The ladder:

* rungs 1-2: what happened, happy or sad;
* rungs 3-4: what is still to come; rungs 5-6: how it turned out;
* rungs 7-8: who did it; rungs 9-11: news for others;
* rungs 12+: people who want what others would not (who hope the
  match is rained off), so what happened and how they feel part ways;
* rungs 15+: what one person thinks another feels, when they have
  heard it wrong: "Cal thinks that Bo has heard that Ana failed. How does
  Cal think Bo thinks Ana feels?" -- one more level every five rungs;
* more answers to choose from up the ladder, and less time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import feelings as F
from . import hand as H
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run

WORD = {'joy': 'happy', 'distress': 'sad', 'hope': 'hopeful',
        'fear': 'worried', 'relief': 'relieved',
        'disappointment': 'disappointed', 'pride': 'proud',
        'shame': 'ashamed', 'remorse': 'remorseful',
        'admiration': 'admiring', 'reproach': 'disapproving',
        'gratitude': 'grateful', 'anger': 'angry',
        'happy_for': 'glad for them', 'pity': 'sorry for them',
        'resentment': 'resentful', 'gloating': 'gloating'}
KINDS = (('happened', 1, ('joy', 'distress')),
         ('to_come', 3, ('hope', 'fear')),
         ('turned_out', 5, ('relief', 'disappointment')),
         ('own_doing', 7, ('pride', 'shame', 'remorse')),
         ('others_doing', 7, ('admiration', 'reproach', 'gratitude',
                              'anger')),
         ('fortune', 9, ('happy_for', 'pity', 'resentment', 'gloating')))
GOOD = {'joy', 'hope', 'relief', 'pride', 'admiration', 'gratitude',
        'happy_for', 'gloating'}
#: Emotions that would also be a fair answer to a story built for the
#: other: someone relieved is happy too, someone remorseful ashamed. They
#: are never offered against each other.
_PAIRS = (('joy', 'relief'), ('joy', 'pride'), ('joy', 'gratitude'),
          ('joy', 'happy_for'), ('joy', 'gloating'),
          ('distress', 'disappointment'), ('distress', 'remorse'),
          ('distress', 'anger'), ('distress', 'pity'),
          ('distress', 'shame'), ('distress', 'resentment'),
          ('distress', 'fear'), ('shame', 'remorse'),
          ('gratitude', 'admiration'), ('anger', 'reproach'),
          ('anger', 'resentment'), ('reproach', 'resentment'))
COMPAT = {e: {b for a, b in _PAIRS if a == e} | {a for a, b in _PAIRS
                                                 if b == e}
          for e in WORD}
NAMES = ('Ana', 'Bo', 'Cal', 'Dee', 'Eli', 'Fen', 'Gus', 'Hana', 'Ivo',
         'Jun', 'Kit', 'Lev', 'Mira', 'Nico', 'Odi', 'Pia', 'Quin', 'Rae',
         'Sol', 'Tam')


class Goal(NamedTuple):
    want: str      # what P hoped for
    good: str      # it happens
    bad: str       # it does not
    wait: str      # not known yet
    sign_good: str
    sign_bad: str
    won: str       # short: "{P} got in"
    lost: str


GOALS = (
    Goal('{P} hoped to get a place at the art school.',
         'The letter came: {P} was in.', 'The letter came: {P} was not in.',
         'The letter has not come yet.',
         'A teacher said {P}\'s drawings were the best she had seen.',
         'A friend heard that every place was already taken.',
         '{P} got into the art school', '{P} was turned down by the art '
         'school'),
    Goal('{P} wanted the last cherry pie at the bakery.',
         '{P} got the last cherry pie.',
         'The man in front of {P} bought the last cherry pie.',
         'There is a long queue in front of {P}.',
         'Nobody in the queue seems to want cherry pie.',
         'Everyone in the queue is pointing at the cherry pies.',
         '{P} got the last cherry pie', '{P} missed the last cherry pie'),
    Goal('{P} had planned a picnic for Saturday.',
         'Saturday came bright and dry, and the picnic went ahead.',
         'It poured all Saturday and the picnic was called off.',
         'Saturday is two days away.', 'The forecast says sun all day.',
         'The forecast says heavy rain all day.',
         '{P}\'s picnic went ahead', '{P}\'s picnic was rained off'),
    Goal('{P} wanted to pass the driving test.', '{P} passed.',
         '{P} failed.', '{P} is in the waiting room before the test.',
         'In the practice drive {P} did not make a single mistake.',
         'In the practice drive {P} stalled three times.',
         '{P} passed the driving test', '{P} failed the driving test'),
    Goal('{P}\'s cat had been missing for two days.',
         'The cat walked in through the back door.',
         'A neighbour found the cat\'s collar by the road; it was gone for '
         'good.', 'There is still no sign of the cat.',
         'Someone saw a cat just like it two streets away.',
         'A fox has been seen in the gardens every night.',
         '{P}\'s cat came home', '{P}\'s cat was lost for good'),
    Goal('{P} had applied for the job at the museum.',
         '{P} got the job.', 'The museum gave the job to someone else.',
         'The museum will decide on Friday.',
         'The interviewers laughed at all of {P}\'s jokes.',
         'The interviewers kept checking their watches.',
         '{P} got the job at the museum', '{P} did not get the job at the '
         'museum'),
    Goal('{P} wanted to catch the last train home.',
         '{P} jumped on just as the doors closed.',
         'The train pulled out as {P} reached the platform.',
         '{P} is running for the station.',
         'The board says the train is five minutes late.',
         'The board says the train is on time, and it is two minutes away.',
         '{P} caught the last train', '{P} missed the last train'),
    Goal('{P}\'s old dog was having an operation.',
         'The vet rang: the operation went well.',
         'The vet rang: the dog did not wake up.',
         'The operation is still going on.',
         'The vet said the dog was strong for its age.',
         'The vet said the dog\'s heart was weak.',
         '{P}\'s dog came through the operation',
         '{P}\'s dog died in the operation'),
)

#: Goals where what a person wants is what others would not: the
#: event sounds bad and is good for them, or the other way round.
TWISTS = (
    Goal('{P} had not trained all week and quietly hoped the match would '
         'be called off.', 'A storm came in and the match was called off.',
         'The sky stayed clear and the match went ahead.',
         'The match is this afternoon.', 'Thunder is rolling in.',
         'There is not a cloud in the sky.',
         '{P}\'s match was called off', '{P}\'s match went ahead'),
    Goal('{P} dreaded giving the speech at the wedding.',
         'The microphone broke, and nobody gave any speeches.',
         'The host handed {P} the microphone.',
         'The speeches are after dinner.',
         'The best man wants to do all the speaking himself.',
         'The host keeps looking at {P}.',
         'the speeches were cancelled', '{P} had to give the speech'),
    Goal('{P} wanted to stay home and hoped the party would be cancelled.',
         'The host fell ill and cancelled the party.',
         'The party is on, and everyone is asking whether {P} is coming.',
         'The host will decide this evening.',
         'The host sounds very ill on the phone.',
         'The host sounds full of energy.',
         'the party was cancelled', 'the party is on'),
    Goal('{P} hoped to fail the trial for the choir, to have the evenings '
         'free.', 'The choir master said {P} was not needed.',
         'The choir master said {P} was perfect and must join.',
         'The choir master is deciding now.',
         'The choir master winced while {P} sang.',
         'The choir master was smiling while {P} sang.',
         '{P} was left out of the choir', '{P} was put in the choir'),
)

GOOD_ACTS = ('handed in a lost wallet with all the money still in it',
             'stayed late to help a stranger fix a flat tyre',
             'owned up to breaking the window',
             'gave a seat on the bus to a tired old man',
             'spent the weekend cleaning up the river bank')
BAD_ACTS = ('lied to the teacher to get a classmate in trouble',
            'kicked over a toddler\'s sandcastle for fun',
            'handed in a friend\'s homework as their own',
            'laughed at a boy who fell off his bike',
            'took money from the charity box')


class Grade(NamedTuple):
    rung: int
    kinds: Tuple[str, ...]
    twist: float               # share of stories with a twisted goal
    depth: int                 # levels of belief, 0 for none
    options: int
    seconds: float
    items: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = tuple(k for k, at, _e in KINDS if r >= at)
    options = 2 if r < 3 else 3 if r < 5 else 4 if r < 7 else \
        5 if r < 9 else 6 if r < 12 else 8
    depth = 0 if r < 15 else min(4, 1 + (r - 15) // 5)
    seconds = max(8.0, 30.0 - 1.0 * (r - 1))
    return Grade(r, kinds, 0.5 if r >= 12 else 0.0, depth, options,
                 seconds, 10)


def _fill(text: str, **names) -> str:
    return text.format(**names)


def story(kind: str, level: Grade, draw: random.Random
          ) -> Tuple[str, str, str]:
    """(text, who it asks about, emotion)."""
    p, q, b, c = draw.sample(NAMES, 4)
    g = draw.choice(TWISTS if draw.random() < level.twist else GOALS)
    good = draw.random() < 0.5

    def f(t, who=p):
        return _fill(t, P=who)
    if kind == 'happened':
        return ' '.join((f(g.want), f(g.good if good else g.bad))), p, \
            'joy' if good else 'distress'
    if kind == 'to_come':
        return ' '.join((f(g.want), f(g.wait),
                         f(g.sign_good if good else g.sign_bad))), p, \
            'hope' if good else 'fear'
    if kind == 'turned_out':
        if good:
            return ' '.join((f(g.want), _('For days it looked as if it '
                                          'would go wrong.'),
                             _('In the end:'), f(g.good))), p, 'relief'
        return ' '.join((f(g.want), _('For days it looked certain to go '
                                      'well.'), _('In the end:'),
                         f(g.bad))), p, 'disappointment'
    if kind == 'own_doing':
        e = draw.choice(('pride', 'shame', 'remorse'))
        if e == 'pride':
            return '%s %s.' % (p, draw.choice(GOOD_ACTS)), p, e
        if e == 'shame':
            return '%s %s, and everyone saw.' % (
                p, draw.choice(BAD_ACTS)), p, e
        return ('%s and %s are close friends. %s told a secret %s had '
                'trusted %s with, and now %s will not speak to anyone.' % (
                    p, q, p, q, p, q)), p, e
    if kind == 'others_doing':
        e = draw.choice(('admiration', 'reproach', 'gratitude', 'anger'))
        if e == 'admiration':
            return '%s read in the paper that a stranger %s.' % (
                p, draw.choice(GOOD_ACTS)), p, e
        if e == 'reproach':
            return '%s watched a stranger who %s.' % (
                p, draw.choice(BAD_ACTS)), p, e
        if e == 'gratitude':
            return ' '.join((f(g.want), _('%s went out of their way to '
                                          'help,') % q,
                             _('and because of that:'), f(g.good))), p, e
        return ' '.join((f(g.want), _('%s got in the way on purpose,') % q,
                         _('and because of that:'), f(g.bad))), p, e
    # another's fortune: the news is about q
    friend = draw.random() < 0.5
    tie = (_('%s and %s have been best friends since school.') % (p, q)
           if friend else
           _('%s cannot stand %s, who once spread lies about %s.') %
           (p, q, p))
    g2 = draw.choice(GOALS)
    news = _fill(g2.won if good else g2.lost, P=q)
    e = ('happy_for' if good else 'pity') if friend else \
        ('resentment' if good else 'gloating')
    return '%s %s heard that %s.' % (tie, p, news), p, e


def believed(level: Grade, draw: random.Random
             ) -> Tuple[str, str, str]:
    """A story of who has heard what about someone, and the question of
    what one thinks another thinks they feel."""
    people = draw.sample(NAMES, level.depth + 2)
    p = people[0]
    g = draw.choice(GOALS)
    true_good = draw.random() < 0.5
    lines = [_fill(g.want, P=p),
             _fill(g.good if true_good else g.bad, P=p)]
    chain = people[1:]
    # Statements at every depth, each with its own version of events.
    told = {}
    for d in range(1, level.depth + 1):
        good = draw.random() < 0.5
        told[d] = good
        heard = _fill(g.won if good else g.lost, P=p)
        who = chain[:d]
        clause = _('%s has heard that %s') % (who[0], heard)
        for w in who[1:]:
            clause = _('%s thinks that %s') % (w, clause)
        lines.append(clause[0].upper() + clause[1:] + '.')
    who = chain[:level.depth]
    inner = _('%s feels') % p
    for w in who[:-1]:
        inner = _('%s thinks %s') % (w, inner)
    question = _('What does %s think %s?') % (who[-1], inner)
    good = told[level.depth]
    return ' '.join(lines), question, 'joy' if good else 'distress'


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    pool = [e for k, _at, es in KINDS if k in level.kinds for e in es]
    items = []
    for _k in range(level.items):
        if level.depth and draw.random() < 0.5:
            text, question, e = believed(level, draw)
        else:
            kind = draw.choice(level.kinds)
            text, who, e = story(kind, level, draw)
            question = _('How does %s feel?') % who
        others = [x for x in pool if x != e and x not in COMPAT[e]]
        # The nearest wrong answers first: same side, then the rest.
        near = [x for x in others if (x in GOOD) == (e in GOOD)]
        far = [x for x in others if x not in near]
        draw.shuffle(near)
        draw.shuffle(far)
        pick = (near + far)[:level.options - 1] if level.rung >= 7 else \
            (far + near)[:level.options - 1]
        if len(pick) < level.options - 1:
            extra = [x for x in WORD if x != e and x not in COMPAT[e]
                     and x not in pick]
            draw.shuffle(extra)
            pick += extra[:level.options - 1 - len(pick)]
        opts = [WORD[x] for x in pick] + [WORD[e]]
        draw.shuffle(opts)
        items.append(F.Item(text, (F.Step(question, tuple(opts),
                                          opts.index(WORD[e])),),
                            level.seconds, truth=WORD[e],
                            title=_('A story')))
    need = max(F.need_for(level.items, 1.0 / level.options),
               int(math.ceil(0.8 * level.items)))
    return F.Round(level, tuple(items), need)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=20)
