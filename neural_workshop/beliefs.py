# -*- coding: utf-8 -*-
"""Who Knows What?: a short story in a room, and a question about what
someone believes.

People put things into closed containers, go out, come back, move
things while others are away, phone one another, sometimes lie, and
sometimes peek. The story is told in panels; the question is where
someone will look -- or where someone thinks someone else will look.
The viewer sees everything; nobody in the story does.

Beliefs are tracked event by event, and a question is asked of the
tracker, never of the story's wording:

* a person present when a thing is moved learns where it went; one who
  is out does not, and keeps believing what they last knew;
* coming back in shows nothing -- the containers are closed;
* a phone call passes on what the caller believes (or, in a lie, what
  the caller knows is false); the one called believes it;
* peeking into the container that holds a thing shows where it is;
  peeking where one thought it was and finding it gone leaves one not
  knowing;
* what A thinks B believes changes only on what A could know: a move
  both saw, a call between them, a peek A saw while knowing the answer.

The ladder:

* rungs 1-2: two people, two containers -- the classic false belief:
  one puts a ball away and goes out, the other moves it;
* rungs 3-5: three containers, stories of four to six events;
* rungs 6-8: three people and two things;
* rungs 9-12: **second-order** questions: where does A think B will
  look?
* rungs 13-16: phone calls pass beliefs on;
* rungs 17-20: lies; four people, four containers;
* from rung 21 peeks, three things, and stories of a dozen events.

From rung 3 seven questions in ten have an answer that is *not* where
the thing really is, so "where it is" is a poor guess. A trial is right
or wrong.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

PEOPLE = ('Ann', 'Ben', 'Cleo', 'Dev', 'Esme')
CONTAINERS = ('basket', 'box', 'drawer', 'cupboard')
THINGS = ('ball', 'key', 'apple')
PERSON_COLOURS = ((214, 96, 80), (80, 140, 214), (96, 176, 104),
                  (176, 120, 210), (226, 160, 64))
CONTAINER_COLOURS = ((196, 150, 96), (120, 150, 190), (150, 120, 96),
                     (110, 170, 150))
THING_COLOURS = ((232, 70, 60), (230, 196, 60), (110, 200, 80))


class Grade(NamedTuple):
    rung: int
    people: int
    containers: int
    things: int
    events: Tuple[int, int]
    second: float          # share of second-order questions
    calls: bool
    lies: bool
    peeks: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        people=2 if r < 6 else (3 if r < 17 else 4),
        containers=2 if r < 3 else (3 if r < 17 else 4),
        things=1 if r < 6 else (2 if r < 21 else 3),
        events=(4, 4) if r < 3 else ((4, 6) if r < 6 else
                                     ((6, 8) if r < 13 else
                                      ((7, 10) if r < 21 else (10, 13)))),
        second=0.0 if r < 9 else 0.5,
        calls=r >= 13, lies=r >= 17, peeks=r >= 21)


class Event(NamedTuple):
    kind: str            # put, move, leave, enter, call, lie, peek
    who: int
    other: int = -1      # the one called
    thing: int = -1
    where: int = -1


class Tracker:
    """The truth, who is in the room, and every belief, event by event."""

    def __init__(self, people: int, things: int) -> None:
        self.people = people
        self.present = set(range(people))
        self.truth: Dict[int, int] = {}
        #: belief[a][thing]: where a thinks the thing is.
        self.belief = [dict() for _p in range(people)]
        #: second[a][b][thing]: where a thinks b thinks it is.
        self.second = [[dict() for _q in range(people)]
                       for _p in range(people)]

    def apply(self, e: Event) -> None:
        if e.kind in ('put', 'move'):
            self.truth[e.thing] = e.where
            for a in self.present:
                self.belief[a][e.thing] = e.where
                for b in self.present:
                    self.second[a][b][e.thing] = e.where
        elif e.kind == 'leave':
            self.present.discard(e.who)
        elif e.kind == 'enter':
            self.present.add(e.who)
        elif e.kind in ('call', 'lie'):
            self.belief[e.other][e.thing] = e.where
            self.second[e.who][e.other][e.thing] = e.where
            self.second[e.other][e.who][e.thing] = e.where
        elif e.kind == 'peek':
            if self.truth.get(e.thing) != e.where and \
                    self.belief[e.who].get(e.thing) == e.where:
                # Looked where they thought it was, and it was not there.
                self.belief[e.who].pop(e.thing, None)
            elif self.truth.get(e.thing) == e.where:
                self.belief[e.who][e.thing] = e.where
                for a in self.present:
                    if self.belief[a].get(e.thing) == e.where:
                        self.second[a][e.who][e.thing] = e.where


class Story(NamedTuple):
    rung: int
    people: Tuple[str, ...]
    containers: Tuple[str, ...]
    things: Tuple[str, ...]
    events: Tuple[Event, ...]
    #: Who is in the room, and where each thing is, after each event.
    present: Tuple[Tuple[int, ...], ...]
    places: Tuple[Tuple[Tuple[int, int], ...], ...]
    #: ('first', a, -1, thing) or ('second', a, b, thing).
    asked: Tuple[str, int, int, int]
    choices: Tuple[str, ...]
    answer: int
    question: str


def _caption(story_people, containers, things, e: Event) -> str:
    who = story_people[e.who]
    if e.kind == 'put':
        return _('%s puts the %s in the %s.') % (who, things[e.thing],
                                                 containers[e.where])
    if e.kind == 'move':
        return _('%s moves the %s to the %s.') % (who, things[e.thing],
                                                  containers[e.where])
    if e.kind == 'leave':
        return _('%s goes out.') % who
    if e.kind == 'enter':
        return _('%s comes back in.') % who
    if e.kind in ('call', 'lie'):
        return _('%s phones %s: "The %s is in the %s."') % (
            who, story_people[e.other], things[e.thing],
            containers[e.where])
    return _('%s peeks into the %s.') % (who, containers[e.where])


def caption(story: Story, k: int) -> str:
    return _caption(story.people, story.containers, story.things,
                    story.events[k])


def _events(draw: random.Random, level: Grade) -> List[Event]:
    """A random story that keeps to the rung's kinds of event."""
    t = Tracker(level.people, level.things)
    out: List[Event] = []
    for thing in range(level.things):
        e = Event('put', draw.randrange(level.people), thing=thing,
                  where=draw.randrange(level.containers))
        t.apply(e)
        out.append(e)
    length = draw.randint(*level.events)
    while len(out) < length + level.things - 1:
        options = []
        inside = sorted(t.present)
        outside = [p for p in range(level.people) if p not in t.present]
        if inside:
            options += ['move'] * 4
        if len(inside) > 1:
            options += ['leave'] * 3
        if outside:
            options += ['enter'] * 2
        if level.calls and outside and inside:
            options += ['call'] * 2
        if level.lies and outside and inside:
            options += ['lie']
        if level.peeks and outside:
            options += ['peek']
        kind = draw.choice(options)
        thing = draw.randrange(level.things)
        if kind == 'move':
            who = draw.choice(inside)
            where = draw.choice([c for c in range(level.containers)
                                 if c != t.truth[thing]])
            e = Event('move', who, thing=thing, where=where)
        elif kind == 'leave':
            e = Event('leave', draw.choice(inside))
        elif kind == 'enter':
            e = Event('enter', draw.choice(outside))
        elif kind == 'call':
            # Inside to out, or out to in: they cannot see each other.
            who, other = draw.choice(inside), draw.choice(outside)
            if draw.random() < 0.5:
                who, other = other, who
            where = t.belief[who].get(thing)
            if where is None:
                continue
            e = Event('call', who, other, thing, where)
        elif kind == 'lie':
            who, other = draw.choice(inside), draw.choice(outside)
            where = draw.choice([c for c in range(level.containers)
                                 if c != t.truth[thing]])
            e = Event('lie', who, other, thing, where)
        else:
            who = draw.choice(outside)
            e = Event('enter', who)
            t.apply(e)
            out.append(e)
            e = Event('peek', who, thing=thing, where=draw.choice(
                [t.truth[thing]] * 2 + list(range(level.containers))))
        t.apply(e)
        out.append(e)
    return out


def tell(people: int, things: int, events) -> Tracker:
    t = Tracker(people, things)
    for e in events:
        t.apply(e)
    return t


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Story:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    want_false = level.rung >= 3 and draw.random() < 0.7
    want_second = draw.random() < level.second
    for _try in range(2000):
        if level.rung < 3:
            # The classic: put, out, moved, back in.
            a, b = draw.sample(range(2), 2)
            first, second = draw.sample(range(2), 2)
            events = [Event('put', a, thing=0, where=first),
                      Event('leave', a),
                      Event('move', b, thing=0, where=second),
                      Event('enter', a)]
            t = tell(2, 1, events)
            asked = ('first', a, -1, 0) if draw.random() < 0.75 else \
                ('truth', -1, -1, 0)
        else:
            events = _events(draw, level)
            t = tell(level.people, level.things, events)
            thing = draw.randrange(level.things)
            a = draw.randrange(level.people)
            if want_second:
                b = draw.choice([p for p in range(level.people) if p != a])
                asked = ('second', a, b, thing)
            else:
                asked = ('first', a, -1, thing)
        kind, a, b, thing = asked
        if kind == 'truth':
            answer = t.truth[thing]
        elif kind == 'first':
            answer = t.belief[a].get(thing)
        else:
            answer = t.second[a][b].get(thing)
        if answer is None:
            continue
        if level.rung >= 3 and (answer != t.truth[thing]) != want_false:
            continue
        break
    names = list(PEOPLE)
    draw.shuffle(names)
    names = tuple(names[:level.people if level.rung >= 3 else 2])
    containers = tuple(CONTAINERS[:level.containers])
    things = THINGS[:level.things]
    present, places = [], []
    track = Tracker(len(names), len(things))
    for e in events:
        track.apply(e)
        present.append(tuple(sorted(track.present)))
        places.append(tuple(sorted(track.truth.items())))
    kind, a, b, thing = asked
    if kind == 'truth':
        question = _('Where is the %s really?') % things[thing]
    elif kind == 'first':
        question = _('Where will %s look for the %s?') % (names[a],
                                                          things[thing])
    else:
        question = _('Where does %s think %s will look for the %s?') % (
            names[a], names[b], things[thing])
    return Story(level.rung, names, containers, things, tuple(events),
                 tuple(present), tuple(places), asked,
                 tuple(_('the %s') % c for c in containers), answer,
                 question)
