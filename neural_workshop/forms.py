# -*- coding: utf-8 -*-
"""Forms: fill a form from what a card says, with the keyboard alone.

A card on the right says who someone is -- name, birthday, email, phone,
country, the plan they want -- and a form on the left asks for it, field
by field. Tab moves to the next field; Enter sends the page. Every key
pressed costs one. A form checks only what a form can check -- that a
date is a date, that a phone number is digits, that nothing required is
empty -- and a page sent with such a mistake comes back with the
mistakes marked and costs the rung's penalty. What it cannot check is
whether the values are the right person's: those are checked when the
last page is sent, and one wrong value loses the round.

The ladder:

* one field, then several, with Tab between them;
* dates to rewrite into the form's format (rung 4) and phone numbers to
  strip to digits (rung 5);
* lists that complete as they are typed: type the start of a country,
  Down to the one meant, and it is chosen when Tab leaves the field
  (rung 6) -- the fewer keys the better;
* checkboxes (Space) and radio buttons (Up and Down) (rung 8);
* fields that appear only for some answers (rung 10);
* forms of two pages and then three (rung 12, 18);
* the card written as a letter instead of a list (rung 14), and then a
  letter that mentions other people's details too (rung 16).

Par is the keys a reference typist pressed on the identical form -- the
shortest prefix that picks a list item, no wasted keys, every page right
first time -- with room on the lower rungs and none from rung twenty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import re
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: What can be typed, besides letters and digits.
SYMBOLS = ' @.-/'
#: Keys that are not characters.
BACKSPACE, TAB, ENTER, UP, DOWN = 'backspace', 'tab', 'enter', 'up', 'down'

FIRST = ('Ada', 'Ben', 'Cleo', 'Dan', 'Eva', 'Finn', 'Gus', 'Hana', 'Ida',
         'Jon', 'Kai', 'Lena', 'Mia', 'Noor', 'Omar', 'Pia', 'Rex', 'Sara',
         'Tom', 'Una', 'Vic', 'Wes', 'Yara', 'Zoe')
LAST = ('Lee', 'Berg', 'Dahl', 'Moe', 'Holm', 'Lund', 'Ruiz', 'Sato',
        'Klein', 'Novak', 'Okafor', 'Park', 'Quist', 'Rossi', 'Stone',
        'Tran', 'Vega', 'West', 'Young', 'Zhou')
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December')
COUNTRIES = ('Argentina', 'Australia', 'Austria', 'Belgium', 'Brazil',
             'Canada', 'Chile', 'China', 'Colombia', 'Croatia', 'Denmark',
             'Egypt', 'Estonia', 'Finland', 'France', 'Germany', 'Ghana',
             'Greece', 'Iceland', 'India', 'Ireland', 'Italy', 'Japan',
             'Kenya', 'Mexico', 'Morocco', 'Nepal', 'Netherlands',
             'New Zealand', 'Nigeria', 'Norway', 'Peru', 'Poland',
             'Portugal', 'Spain', 'Sweden', 'Switzerland', 'Turkey',
             'Uganda', 'Uruguay')
CITIES = ('Oslo', 'Bergen', 'Lyon', 'Porto', 'Turin', 'Ghent', 'Cork',
          'Graz', 'Malmo', 'Turku', 'Split', 'Delft', 'Leeds', 'Basel')
PLANS = ('Basic', 'Plus', 'Pro', 'Team')
DOMAINS = ('mail.com', 'post.net', 'inbox.org', 'web.io')
COMPANIES = ('Acme', 'Brightside', 'Copperleaf', 'Dunmore', 'Everglow',
             'Fairway', 'Greystone')


class Grade(NamedTuple):
    rung: int
    #: Field kinds in play.
    kinds: Tuple[str, ...]
    fields: int
    pages: int
    #: The card as a letter instead of a list, and with other people.
    letter: bool
    decoys: bool
    #: Fields that only appear for some answers.
    conditional: bool
    penalty: int
    factor: float
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds: Tuple[str, ...] = ('text',)
    if r >= 4:
        kinds += ('date',)
    if r >= 5:
        kinds += ('digits',)
    if r >= 6:
        kinds += ('choice',)
    if r >= 8:
        kinds += ('check', 'radio')
    return Grade(
        rung=r,
        kinds=kinds,
        fields=min(12, 1 + r // 2),
        pages=1 if r < 12 else (2 if r < 18 else 3),
        letter=r >= 14,
        decoys=r >= 16,
        conditional=r >= 10,
        penalty=5 + r // 2,
        factor=max(1.0, 1.6 - 0.03 * (r - 1)),
        slack=4.0 if r < 12 else 2.0,
    )


class Field(NamedTuple):
    key: str
    label: str
    kind: str
    #: What must end up in it: text typed, a list item's index, a radio
    #: index, or 1/0 for a checkbox.
    answer: object
    #: The items of a list or the radio buttons.
    options: Tuple[str, ...] = ()
    page: int = 0
    #: Shown only while another field holds a value: (key, value).
    shown_if: Optional[Tuple[str, object]] = None
    hint: str = ''


class Deal(NamedTuple):
    level: Grade
    fields: Tuple[Field, ...]
    #: The card: lines of text.
    card: Tuple[str, ...]


# --- dealing ---------------------------------------------------------------

def _person(rng: random.Random) -> Dict[str, object]:
    first, last = rng.choice(FIRST), rng.choice(LAST)
    year = rng.randint(1950, 2005)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    phone = '%d%d' % (rng.randint(2, 9), rng.randint(1000000, 9999999))
    return {
        'first': first, 'last': last,
        'name': '%s %s' % (first, last),
        'day': day, 'month': month, 'year': year,
        'email': '%s.%s@%s' % (first.lower(), last.lower(),
                               rng.choice(DOMAINS)),
        'phone': phone,
        'country': rng.randrange(len(COUNTRIES)),
        'city': rng.choice(CITIES),
        'plan': rng.randrange(len(PLANS)),
        'news': rng.random() < 0.5,
        'company': rng.choice(COMPANIES) if rng.random() < 0.6 else '',
    }


def _spoken_date(p: Dict[str, object]) -> str:
    return '%d %s %d' % (p['day'], MONTHS[p['month'] - 1], p['year'])


def _spoken_phone(phone: str) -> str:
    return '+47 %s %s %s' % (phone[:3], phone[3:5], phone[5:])


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if rng is None:
        rng = random.Random(seed)
    level = grade(rung)
    p = _person(rng)
    # Every field a rung could ask for, in the order a form asks them.
    pool: List[Field] = [
        Field('first', 'First name', 'text', p['first']),
        Field('last', 'Last name', 'text', p['last']),
        Field('city', 'City', 'text', p['city']),
        Field('email', 'Email', 'text', p['email']),
    ]
    if 'date' in level.kinds:
        pool.append(Field('born', 'Date of birth', 'date',
                          '%02d/%02d/%04d' % (p['day'], p['month'],
                                              p['year']),
                          hint='DD/MM/YYYY'))
    if 'digits' in level.kinds:
        # The number as the card gives it, country code and all, with
        # the plus and the spaces taken out.
        pool.append(Field('phone', 'Phone', 'digits', '47' + p['phone'],
                          hint='digits only'))
    if 'choice' in level.kinds:
        pool.append(Field('country', 'Country', 'choice', p['country'],
                          options=COUNTRIES, hint='type to search'))
    if 'radio' in level.kinds:
        pool.append(Field('plan', 'Plan', 'radio', p['plan'],
                          options=PLANS))
        pool.append(Field('news', 'Send me the newsletter', 'check',
                          1 if p['news'] else 0))
    if level.conditional:
        has = 1 if p['company'] else 0
        pool.append(Field('work', 'I am signing up for a company',
                          'check', has))
        pool.append(Field('company', 'Company name', 'text',
                          p['company'] or '', shown_if=('work', 1)))
    # The rung's number of fields: the newest kinds first, so a rung
    # always asks what it adds; then in the order a form asks them.
    priority = ('first', 'work', 'company', 'country', 'plan', 'news',
                'phone', 'born', 'last', 'email', 'city')
    order = [f.key for f in pool]
    chosen = sorted(pool, key=lambda f: priority.index(f.key))
    chosen = chosen[:level.fields]
    keys = {f.key for f in chosen}
    # A conditional field comes with its condition, or not at all.
    chosen = [f for f in chosen
              if f.shown_if is None or f.shown_if[0] in keys]
    wanted = sorted(chosen, key=lambda f: order.index(f.key))
    if level.pages > 1:
        per = -(-len(wanted) // level.pages)
        paged = []
        for index, f in enumerate(wanted):
            page = min(level.pages - 1, index // per)
            if f.shown_if is not None:
                # A conditional field shares its condition's page.
                page = next(g.page for g in paged
                            if g.key == f.shown_if[0])
            paged.append(f._replace(page=page))
        wanted = paged
    card = _card(level, p, wanted, rng)
    return Deal(level, tuple(wanted), tuple(card))


def _card(level: Grade, p: Dict[str, object], fields: Sequence[Field],
          rng: random.Random) -> List[str]:
    asked = {f.key for f in fields}
    facts = []
    if not level.letter:
        if 'first' in asked or 'last' in asked:
            facts.append('Name: %s' % p['name'])
        if 'city' in asked:
            facts.append('City: %s' % p['city'])
        if 'email' in asked:
            facts.append('Email: %s' % p['email'])
        if 'born' in asked:
            facts.append('Born: %s' % _spoken_date(p))
        if 'phone' in asked:
            facts.append('Phone: %s' % _spoken_phone(p['phone']))
        if 'country' in asked:
            facts.append('Country: %s' % COUNTRIES[p['country']])
        if 'plan' in asked:
            facts.append('Plan: %s' % PLANS[p['plan']])
        if 'news' in asked:
            facts.append('Newsletter: %s' % ('yes' if p['news'] else 'no'))
        if 'work' in asked:
            facts.append('Company: %s' % (p['company'] or 'none, '
                                          'signing up for myself'))
        return facts
    lines = ['Hello! I am %s and I live in %s, %s.'
             % (p['name'], p['city'], COUNTRIES[p['country']])]
    if level.decoys:
        sister = _person(rng)
        lines.append('My sister %s was born on %s; her number is %s.'
                     % (sister['first'], _spoken_date(sister),
                        _spoken_phone(sister['phone'])))
    lines.append('I was born on %s. Call me on %s or write to %s.'
                 % (_spoken_date(p), _spoken_phone(p['phone']), p['email']))
    lines.append('I would like the %s plan, and %s.'
                 % (PLANS[p['plan']], 'yes, send me the newsletter'
                    if p['news'] else 'no newsletter, thanks'))
    if level.decoys:
        lines.append('(My sister wants the %s plan, but she will sign up '
                     'herself.)' % PLANS[(p['plan'] + 1) % len(PLANS)])
    lines.append('I work for %s and this is for the company.' % p['company']
                 if p['company'] else 'This is just for me, not a company.')
    # Wrap into short lines for the card.
    out: List[str] = []
    for line in lines:
        words, row = line.split(), ''
        for word in words:
            if len(row) + len(word) + 1 > 38:
                out.append(row)
                row = word
            else:
                row = (row + ' ' + word).strip()
        out.append(row)
    return out


# --- filling it in -----------------------------------------------------------

def _valid(field: Field, value: object) -> bool:
    """What a form can check: shape, not truth."""
    if field.kind in ('check', 'radio'):
        return True
    if field.kind == 'choice':
        return value is not None
    text = str(value or '')
    if not text:
        return False
    if field.kind == 'date':
        match = re.fullmatch(r'(\d\d)/(\d\d)/(\d{4})', text)
        return bool(match) and 1 <= int(match.group(1)) <= 31 \
            and 1 <= int(match.group(2)) <= 12
    if field.kind == 'digits':
        return text.isdigit() and 6 <= len(text) <= 12
    if field.key == 'email':
        return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', text))
    return True


def matches(options: Sequence[str], query: str) -> List[int]:
    """List items that start with what was typed, in list order."""
    q = query.lower()
    return [i for i, item in enumerate(options) if item.lower().startswith(q)]


class Form:
    """A form being filled in."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        self.values: Dict[str, object] = {}
        for f in dealt.fields:
            if f.kind in ('check', 'radio'):
                self.values[f.key] = 0
            elif f.kind == 'choice':
                self.values[f.key] = None
            else:
                self.values[f.key] = ''
        #: What has been typed into a list field, and the item lit.
        self.query: Dict[str, str] = {f.key: '' for f in dealt.fields
                                      if f.kind == 'choice'}
        self.lit: Dict[str, int] = {f.key: 0 for f in dealt.fields
                                    if f.kind == 'choice'}
        self.page = 0
        self.focus = 0
        self.keys = 0
        self.bounced = 0
        #: Fields marked wrong when a page came back.
        self.marked: List[str] = []
        self.sent = False

    # --- what is showing ----------------------------------------------------

    def visible(self, page: Optional[int] = None) -> List[Field]:
        page = self.page if page is None else page
        return [f for f in self.deal.fields if f.page == page
                and (f.shown_if is None
                     or self.values.get(f.shown_if[0]) == f.shown_if[1])]

    @property
    def field(self) -> Optional[Field]:
        shown = self.visible()
        if not shown:
            return None
        return shown[min(self.focus, len(shown) - 1)]

    def choices(self, field: Field) -> List[int]:
        return matches(field.options, self.query[field.key])

    # --- keys -----------------------------------------------------------------

    def press(self, key: str) -> None:
        """One key: a character, or one of the named keys."""
        if self.sent:
            return
        self.keys += 1
        field = self.field
        if key == TAB:
            self._leave()
            shown = self.visible()
            self.focus = (self.focus + 1) % max(1, len(shown))
            return
        if key == ENTER:
            self._leave()
            self._send()
            return
        if field is None:
            return
        kind = field.kind
        if key in (UP, DOWN):
            step = -1 if key == UP else 1
            if kind == 'radio':
                self.values[field.key] = (self.values[field.key] + step) \
                    % len(field.options)
            elif kind == 'choice':
                found = self.choices(field)
                if found:
                    self.lit[field.key] = max(0, min(
                        len(found) - 1, self.lit[field.key] + step))
            return
        if key == BACKSPACE:
            if kind == 'choice':
                self.query[field.key] = self.query[field.key][:-1]
                self.lit[field.key] = 0
                self.values[field.key] = None
            elif kind in ('text', 'date', 'digits'):
                self.values[field.key] = str(self.values[field.key])[:-1]
            return
        if len(key) != 1:
            return
        if kind == 'check':
            if key == ' ':
                self.values[field.key] = 1 - self.values[field.key]
            return
        if kind == 'radio':
            return
        if kind == 'choice':
            self.query[field.key] += key
            self.lit[field.key] = 0
            self.values[field.key] = None
            return
        self.values[field.key] = str(self.values[field.key]) + key

    def _leave(self) -> None:
        """Leaving a list field picks the item lit, if anything was
        typed."""
        field = self.field
        if field is None or field.kind != 'choice':
            return
        found = self.choices(field)
        if self.query[field.key] and found:
            self.values[field.key] = found[min(self.lit[field.key],
                                               len(found) - 1)]

    def _send(self) -> None:
        bad = [f.key for f in self.visible() if not _valid(f, self.values[
            f.key])]
        if bad:
            self.marked = bad
            self.bounced += 1
            return
        self.marked = []
        if self.page + 1 < self.level.pages and any(
                f.page > self.page for f in self.deal.fields):
            self.page += 1
            self.focus = 0
            return
        self.sent = True

    # --- the verdict ----------------------------------------------------------

    def right(self, field: Field) -> bool:
        value = self.values[field.key]
        if field.kind in ('text', 'date', 'digits'):
            return str(value).strip().lower() == str(field.answer).lower()
        return value == field.answer

    @property
    def wrong(self) -> List[Field]:
        return [f for f in self.deal.fields if self._showing(f)
                and not self.right(f)]

    def _showing(self, field: Field) -> bool:
        return field.shown_if is None or \
            self.values.get(field.shown_if[0]) == field.shown_if[1]

    @property
    def cost(self) -> float:
        return self.keys + self.level.penalty * self.bounced


# --- the reference -----------------------------------------------------------

def keys_for(form: Form, field: Field) -> List[str]:
    """The fewest keys that put *field*'s answer in, from empty."""
    if field.kind in ('text', 'date', 'digits'):
        return list(str(field.answer).lower())
    if field.kind == 'check':
        return [' '] if field.answer != form.values[field.key] else []
    if field.kind == 'radio':
        here = form.values[field.key]
        want = field.answer
        down = (want - here) % len(field.options)
        up = (here - want) % len(field.options)
        return [DOWN] * down if down <= up else [UP] * up
    # A list: the shortest start of the name that leaves it in reach,
    # then Down to it.
    name = field.options[field.answer].lower()
    best: Optional[List[str]] = None
    for size in range(1, len(name) + 1):
        found = matches(field.options, name[:size])
        steps = found.index(field.answer)
        keys = list(name[:size]) + [DOWN] * steps
        if best is None or len(keys) < len(best):
            best = keys
        if steps == 0:
            break
    return best


def reference_keys(form: Form) -> Optional[str]:
    """The reference's next key, or None when the form is sent."""
    if form.sent:
        return None
    field = form.field
    shown = form.visible()
    # The field in focus: finish it.
    if field is not None:
        current = form.values[field.key]
        done = form.right(field) if field.kind != 'choice' else (
            form.query[field.key] != '' and
            form.choices(field)[min(form.lit[field.key],
                                    len(form.choices(field)) - 1)]
            == field.answer if form.choices(field) else False)
        if field.kind == 'choice' and current == field.answer:
            done = True
        if not done:
            if field.kind in ('text', 'date', 'digits'):
                typed = str(current).lower()
                want = str(field.answer).lower()
                if not want.startswith(typed):
                    return BACKSPACE
                return want[len(typed)]
            if field.kind == 'choice':
                plan = keys_for(form, field)
                typed = form.query[field.key].lower()
                letters = [k for k in plan if k != DOWN]
                if typed != ''.join(letters)[:len(typed)] \
                        or len(typed) > len(letters):
                    return BACKSPACE
                if len(typed) < len(letters):
                    return letters[len(typed)]
                return DOWN
            return keys_for(form, field)[0]
    # Everything on this page right: send it; otherwise on to the next
    # field that is not.
    if all(form.right(f) for f in shown):
        return ENTER
    return TAB


def reference_form(dealt: Deal) -> Form:
    form = Form(dealt)
    for _step in range(2000):
        key = reference_keys(form)
        if key is None:
            break
        form.press(key)
    return form


def par(dealt: Deal) -> float:
    level = dealt.level
    return reference_form(dealt).keys * level.factor + level.slack


__all__ = ['BACKSPACE', 'COUNTRIES', 'DOWN', 'Deal', 'ENTER', 'Field',
           'Form', 'Grade', 'PLANS', 'SYMBOLS', 'TAB', 'UP', 'deal',
           'grade', 'keys_for', 'matches', 'par', 'reference_form',
           'reference_keys']
