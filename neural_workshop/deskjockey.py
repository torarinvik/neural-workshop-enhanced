# -*- coding: utf-8 -*-
"""Desk Jockey: a rulebook, a tray of forms, and one right thing to do
with each.

A shift deals a new rulebook and a tray of forms, some with an ID card
or receipts attached. Each form in turn is approved, sent back for
something missing, forwarded to another office, rejected under the
rule that says so, or held until another form has been dealt with.
Everything needed is on the desk; nothing is known beforehand.

What the ladder adds: more rules; attachments to check against the
form; exceptions, and exceptions to those; an order of precedence
that is not the order the rules are written in; memos that change a
rule for forms from a date on; and forms that depend on other forms
in the tray.

Every rule is a test and what follows from it. For a form, the rules
are tried in their order of precedence and the first that applies
decides; if none does, the form is approved. So a form that breaks
two rules is rejected under the one that comes first, and rejecting
it under the other is wrong.

For the agent boundary: port 0 approves, 1 sends back, 2 holds, 3-5
forward to the offices in the order the desk lists them, and port
5 + n rejects under rule n.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

APPROVE, SEND_BACK, HOLD = 0, 1, 2
FORWARD = 3                      # ... 5: the offices
REJECT = 5                       # + n: under rule n
MOST_RULES = 9
PORTS = REJECT + MOST_RULES + 1

KINDS = (_('Travel claim'), _('Leave request'), _('Equipment order'),
         _('Parking permit'))
CLAIM, LEAVE = 0, 1
DEPTS = (_('Records'), _('Works'), _('Supply'), _('Transit'))
OFFICES = (_('Finance'), _('Purchasing'), _('Personnel'))
SURNAMES = ('Abbrin', 'Belcote', 'Corvane', 'Dunmere', 'Eskwith', 'Farlow',
            'Gantry', 'Hobbin', 'Ivelle', 'Jarrow', 'Kestle', 'Lumley',
            'Marrick', 'Nethan', 'Orrin', 'Pellow', 'Quillan', 'Rusk',
            'Sorrel', 'Tamsin')
INITIALS = 'ABCDEFGHJKLMNPRSTVW'


class Card(NamedTuple):
    name: str
    expires: int                 # the last day it is good


class Form(NamedTuple):
    name: str
    kind: int
    dept: int
    day: int
    amount: int
    signed: bool
    counter: bool                # countersigned by a supervisor
    card: Optional[Card]
    receipts: Optional[Tuple[int, ...]]      # None: none attached


class Rule(NamedTuple):
    n: int
    test: str                    # see _applies
    value: object
    then: int                    # a port: what follows
    unless: Optional[Tuple[str, object]] = None
    save: Optional[Tuple[str, object]] = None    # where 'unless' fails


class Memo(NamedTuple):
    day: int                     # for forms of this day and after
    n: int                       # the rule it changes
    limit: Optional[int]         # its new limit; None: the rule is withdrawn


class Grade(NamedTuple):
    rung: int
    rules: int
    forms: int
    checks: bool                 # attachments to check against the form
    unless: bool
    forwards: bool
    order: bool                  # precedence is not the written order
    memos: int
    needs: bool                  # forms that wait on other forms
    deep: bool                   # an exception to an exception
    slips: int                   # wrong ones a shift may carry


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        return Grade(r, 1, 3, False, False, False, False, 0, False, False, 0)
    if r < 7:
        return Grade(r, 3, 4, False, False, False, False, 0, False, False, 0)
    if r < 10:
        return Grade(r, 4, 5, True, False, False, False, 0, False, False, 0)
    if r < 13:
        return Grade(r, 5, 5, True, True, True, False, 0, False, False, 0)
    if r < 16:
        return Grade(r, 5, 6, True, True, True, True, 0, False, False, 1)
    if r < 19:
        return Grade(r, 6, 6, True, True, True, True, 1, False, False, 1)
    if r < 22:
        return Grade(r, 7, 7, True, True, True, True, 1, True, False, 1)
    return Grade(r, min(MOST_RULES, 8 + (r - 22) // 3),
                 min(12, 8 + (r - 22) // 2), True, True, True, True, 2, True,
                 True, 1)


class Puzzle(NamedTuple):
    level: Grade
    rules: Tuple[Rule, ...]      # as written, by number
    order: Tuple[int, ...]       # rule numbers, by precedence
    memos: Tuple[Memo, ...]
    forms: Tuple[Form, ...]      # the tray, top first
    buttons: Tuple[int, ...]     # the ports on offer
    choices: Tuple[str, ...]
    answer: int
    seed: int
    question: str


# --- the rules -------------------------------------------------------------

def _is(atom: Tuple[str, object], form: Form) -> bool:
    what, value = atom
    if what == 'counter':
        return form.counter
    if what == 'dept':
        return form.dept == value
    if what == 'kind':
        return form.kind == value
    return form.amount <= value          # 'under'


def limit_of(p: Puzzle, rule: Rule, form: Form) -> Optional[int]:
    """The rule's limit for this form, memos counted; None if the rule
    has been withdrawn for it."""
    limit = rule.value if rule.test in ('over', 'pass') else 0
    for memo in p.memos:
        if memo.n == rule.n and form.day >= memo.day:
            if memo.limit is None:
                return None
            limit = memo.limit
    return limit


def _applies(p: Puzzle, rule: Rule, form: Form) -> bool:
    limit = limit_of(p, rule, form)
    if limit is None:
        return False
    test = rule.test
    if test == 'unsigned':
        hit = not form.signed
    elif test == 'no_card':
        hit = form.card is None
    elif test == 'no_receipt':
        hit = form.receipts is None
    elif test == 'name':
        hit = form.card is not None and form.card.name != form.name
    elif test == 'expired':
        hit = form.card is not None and form.card.expires < form.day
    elif test == 'sum':
        hit = form.receipts is not None and sum(form.receipts) != form.amount
    elif test in ('over', 'pass'):
        hit = form.amount > limit
    elif test == 'kind':
        hit = form.kind == rule.value
    elif test == 'dept':
        hit = form.dept == rule.value
    else:
        raise ValueError(test)
    if hit and rule.unless is not None and _is(rule.unless, form) and not (
            rule.save is not None and _is(rule.save, form)):
        return False
    return hit


def _before(p: Puzzle, at: int) -> Optional[int]:
    """The same person's leave request, for a travel claim."""
    form = p.forms[at]
    for i, other in enumerate(p.forms):
        if i != at and other.kind == LEAVE and other.name == form.name:
            return i
    return None


def ruling(p: Puzzle, at: int, waiting=()) -> int:
    """What is to be done with form *at*, the forms in *waiting* being
    still in the tray."""
    form = p.forms[at]
    rules = {rule.n: rule for rule in p.rules}
    for n in p.order:
        rule = rules[n]
        if rule.test == 'needs':
            if form.kind != CLAIM or limit_of(p, rule, form) is None:
                continue
            first = _before(p, at)
            if first is not None and first in waiting:
                return HOLD
            if first is None or ruling(p, first) != APPROVE:
                return REJECT + n
        elif _applies(p, rule, form):
            return rule.then
    return APPROVE


def breaks(p: Puzzle, at: int) -> List[int]:
    """Every rule form *at* falls under, by number."""
    form = p.forms[at]
    return [rule.n for rule in p.rules
            if rule.test != 'needs' and _applies(p, rule, form)]


class Shift:
    """One tray worked through."""

    def __init__(self, p: Puzzle) -> None:
        self.p = p
        self.tray = list(range(len(p.forms)))
        self.done: List[Tuple[int, int, int]] = []   # form, port, right port
        self.slips = 0
        self.result: Optional[Tuple[bool, str]] = None

    @property
    def top(self) -> Optional[int]:
        return self.tray[0] if self.tray else None

    def right(self) -> Optional[int]:
        if self.result is not None or not self.tray:
            return None
        return ruling(self.p, self.tray[0], self.tray[1:])

    def memos(self) -> List[Memo]:
        """The memos that have reached the desk: each comes with the
        first form it could touch."""
        seen = [form for form, _port, _right in self.done] + self.tray[:1]
        latest = max((self.p.forms[i].day for i in seen), default=0)
        return [m for m in self.p.memos if m.day <= latest]

    def act(self, port: int) -> Optional[bool]:
        """Does *port* to the top form; whether that was right."""
        if self.result is not None or port not in self.p.buttons:
            return None
        want = self.right()
        at = self.tray.pop(0)
        right = port == want
        self.done.append((at, port, want))
        if right and port == HOLD:
            self.tray.append(at)
        if not right:
            self.slips += 1
        lv = self.p.level
        if self.slips > lv.slips:
            self.result = (False, _('No: form for %s -- %s')
                           % (self.p.forms[at].name, name_of(self.p, want)))
        elif not self.tray:
            self.result = (True, _('The tray is clear'))
        return right


def name_of(p: Puzzle, port: int) -> str:
    if port == APPROVE:
        return _('Approve')
    if port == SEND_BACK:
        return _('Send back')
    if port == HOLD:
        return _('Hold')
    if port <= REJECT:
        return _('Forward to %s') % OFFICES[port - FORWARD]
    return _('Reject: rule %d') % (port - REJECT)


def solve(p: Puzzle) -> List[int]:
    """The whole shift, done right."""
    shift = Shift(p)
    ports = []
    while shift.result is None:
        port = shift.right()
        ports.append(port)
        shift.act(port)
    return ports


# --- the words ---------------------------------------------------------------

def _aside(atom: Tuple[str, object]) -> str:
    what, value = atom
    if what == 'counter':
        return _('it is countersigned')
    if what == 'dept':
        return _('it comes from %s') % DEPTS[value]
    if what == 'kind':
        return _('it is a %s') % KINDS[value].lower()
    return _('the amount is %d or less') % value


def say(p: Puzzle, rule: Rule) -> str:
    """A rule as the book prints it."""
    test, value = rule.test, rule.value
    if rule.then > REJECT:
        then = _('Reject')
    elif rule.then == SEND_BACK:
        then = _('Send back')
    else:
        then = _('Forward to %s') % OFFICES[rule.then - FORWARD]
    what = {
        'unsigned': _('a form that is not signed'),
        'no_card': _('a form with no ID card attached'),
        'no_receipt': _('a form with no receipts attached'),
        'name': _('a form whose ID card is in another name'),
        'expired': _('a form whose ID card expired before the form\'s day'),
        'sum': _('a form whose receipts do not add up to its amount'),
    }.get(test)
    if test in ('over', 'pass'):
        what = _('any amount over %d') % value
    elif test == 'kind':
        what = _('every %s') % KINDS[value].lower()
    elif test == 'dept':
        what = _('every form from %s') % DEPTS[value]
    elif test == 'needs':
        return _('%d. A travel claim waits for the same person\'s leave '
                 'request: hold it while that is in the tray. Reject it if '
                 'that was not approved, or there is none.') % rule.n
    said = '%d. %s %s' % (rule.n, then, what)
    if rule.unless is not None:
        said += _(', unless %s') % _aside(rule.unless)
        if rule.save is not None:
            said += _(' -- but not if %s') % _aside(rule.save)
    return said + '.'


def say_memo(memo: Memo) -> str:
    if memo.limit is None:
        return _('MEMO  Rule %d is withdrawn for forms of day %d and '
                 'after.') % (memo.n, memo.day)
    return _('MEMO  In rule %d the amount is %d for forms of day %d and '
             'after.') % (memo.n, memo.limit, memo.day)


def say_order(p: Puzzle) -> str:
    if list(p.order) == sorted(p.order):
        return _('If more than one rule applies, the lowest number decides. '
                 'If none does, approve.')
    return _('If more than one rule applies, the first of these decides: '
             '%s. If none does, approve.') % ', '.join(str(n)
                                                       for n in p.order)


# --- the deal ----------------------------------------------------------------

def _book(draw: random.Random, lv: Grade) -> List[Rule]:
    """The rules, numbered as written."""
    made: List[Tuple] = [('unsigned', None, SEND_BACK)]
    pool: List[Tuple] = [('over', draw.choice((200, 300, 400, 500)), -1),
                         ('kind', draw.randrange(2, 4), -1),
                         ('no_receipt', None, SEND_BACK)]
    if lv.checks:
        pool += [('no_card', None, SEND_BACK), ('name', None, -1),
                 ('expired', None, -1), ('sum', None, -1)]
    if lv.forwards:
        pool += [('dept', draw.randrange(4), FORWARD + draw.randrange(3)),
                 ('pass', draw.choice((600, 700, 800)),
                  FORWARD + draw.randrange(3))]
    draw.shuffle(pool)
    if lv.rules > 1 and not any(t[0] == 'over' for t in pool[:lv.rules]):
        pool.sort(key=lambda t: t[0] != 'over')
    if lv.forwards and not any(t[2] >= FORWARD for t in pool[:lv.rules]):
        pool.sort(key=lambda t: t[2] < FORWARD)
    want = lv.rules - 1 - (1 if lv.needs else 0)
    made += pool[:want]
    if lv.needs:
        made.append(('needs', None, -1))
    draw.shuffle(made)
    rules = []
    for n, (test, value, then) in enumerate(made, 1):
        unless = save = None
        if lv.unless and test in ('over', 'kind', 'sum') \
                and draw.random() < 0.8:
            unless = draw.choice(
                [('counter', None), ('dept', draw.randrange(4))]
                + ([('under', 100)] if test != 'over' else []))
            if lv.deep and draw.random() < 0.7:
                save = draw.choice(
                    [a for a in (('dept', draw.randrange(4)),
                                 ('kind', draw.randrange(4)),
                                 ('counter', None))
                     if a[0] != unless[0]])
        rules.append(Rule(n, test, value, REJECT + n if then < 0 else then,
                          unless, save))
    return rules


def _tray(draw: random.Random, lv: Grade, rules: List[Rule]) -> List[Form]:
    tests = {rule.test for rule in rules}
    cards = bool(tests & {'no_card', 'name', 'expired'})
    slips = bool(tests & {'no_receipt', 'sum'})
    names = ['%s. %s' % (i, s) for i, s in zip(
        draw.sample(INITIALS, 16), draw.sample(SURNAMES, 16))]
    forms = []
    day = draw.randint(1, 4)
    for k in range(lv.forms):
        day = min(28, day + draw.randint(0, 3))
        name = names[k]
        kind = draw.randrange(4)
        if lv.needs and k and draw.random() < 0.45:
            # Someone already in the tray, with the other form of the two.
            other = draw.choice(forms)
            if other.kind in (CLAIM, LEAVE) and not any(
                    f.name == other.name and f is not other for f in forms):
                name, kind = other.name, CLAIM + LEAVE - other.kind
        amount = draw.choice((40, 60, 85, 120, 150, 180, 240, 260, 320, 350,
                              420, 480, 540, 620, 650, 720, 760, 850, 900))
        card = None
        if cards and draw.random() < 0.85:
            shown = name
            if draw.random() < 0.22:
                shown = draw.choice(names[lv.forms:]) if lv.rung < 16 \
                    else '%s. %s' % (draw.choice(
                        [c for c in INITIALS if c != name[0]]), name[3:])
            card = Card(shown, max(1, day - draw.randint(1, 6))
                        if draw.random() < 0.2 else day + draw.randint(0, 9))
        receipts = None
        if slips and draw.random() < 0.85:
            parts = draw.randint(1, 3)
            cuts = sorted(draw.sample(range(1, amount // 5), parts - 1)) \
                if parts > 1 else []
            edges = [0] + [c * 5 for c in cuts] + [amount]
            receipts = [b - a for a, b in zip(edges, edges[1:])]
            if draw.random() < 0.22:
                receipts[draw.randrange(parts)] += draw.choice((-20, -10,
                                                                 10, 20, 50))
            receipts = tuple(max(5, v) for v in receipts)
        forms.append(Form(name, kind, draw.randrange(4), day, amount,
                          draw.random() < 0.82, draw.random() < 0.35, card,
                          receipts))
    if lv.needs:
        # One claim, at least, that comes up before its leave request.
        free = [i for i, f in enumerate(forms)
                if sum(g.name == f.name for g in forms) == 1]
        if len(free) >= 2:
            a, b = sorted(draw.sample(free, 2))
            forms[a] = forms[a]._replace(kind=CLAIM)
            forms[b] = forms[b]._replace(kind=LEAVE, name=forms[a].name)
            if forms[b].card is not None and draw.random() < 0.8:
                forms[b] = forms[b]._replace(
                    card=forms[b].card._replace(name=forms[a].name))
    return forms


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    lv = grade(rung)
    draw = random.Random(seed)
    best, best_score = None, -1.0
    for _attempt in range(400):
        if _attempt >= 120 and best is not None:
            break
        rules = _book(draw, lv)
        order = [rule.n for rule in rules]
        if lv.order:
            while order == sorted(order):
                draw.shuffle(order)
        forms = _tray(draw, lv, rules)
        memos = []
        limited = [rule for rule in rules if rule.test in ('over', 'pass')]
        others = [rule for rule in rules
                  if rule.test not in ('over', 'pass', 'needs', 'unsigned')]
        days = sorted({f.day for f in forms[2:]})
        for k in range(min(lv.memos, len(days))):
            day = days[(k + 1) * len(days) // (lv.memos + 1)]
            if limited and (k == 0 or not others):
                rule = limited[0]
                memos.append(Memo(day, rule.n, draw.choice(
                    [v for v in (100, 200, 300, 400, 600, 800)
                     if v != rule.value])))
            elif others:
                memos.append(Memo(day, draw.choice(others).n, None))
        buttons = [APPROVE] + sorted(
            {rule.then for rule in rules if rule.test != 'needs'}
            | {REJECT + rule.n for rule in rules if rule.test == 'needs'}
            | ({HOLD} if lv.needs else set()))
        p = Puzzle(lv, tuple(rules), tuple(order), tuple(memos),
                   tuple(forms), tuple(buttons),
                   tuple(str(b) for b in buttons), 0, seed,
                   _('Deal with each form by the book'))
        score = _worth(p)
        if score > best_score:
            best, best_score = p, score
    if best is None or best_score < 0:
        raise RuntimeError('no shift for rung %d' % rung)
    return best._replace(choices=tuple(name_of(best, b)
                                       for b in best.buttons))


def _worth(p: Puzzle) -> float:
    """How well a tray shows its book at work; below nought, not at all."""
    lv = p.level
    ports = solve(p)
    if len(ports) > len(p.forms) + 3:
        return -1.0
    kinds = set(ports)
    if APPROVE not in kinds or len(kinds) < min(2 + (lv.rules > 1), 2):
        return -1.0
    if lv.rules > 1 and len(kinds) < 3:
        return -1.0
    score = float(len(kinds))
    plain = p._replace(memos=())
    if lv.memos:
        moved = sum(ruling(p, i) != ruling(plain, i)
                    for i in range(len(p.forms)))
        if not moved:
            return -1.0
        score += min(2, moved)
    if lv.needs:
        if HOLD not in kinds:
            return -1.0
        score += 1
    if lv.order:
        # A form that two rules claim, where the written order would
        # give the other answer.
        swapped = p._replace(order=tuple(sorted(p.order)))
        told = sum(ruling(p, i) != ruling(swapped, i)
                   for i in range(len(p.forms)))
        if not told:
            return -1.0
        score += 1
    if lv.unless:
        bare = p._replace(rules=tuple(r._replace(unless=None, save=None)
                                      for r in p.rules))
        saved = sum(ruling(p, i) != ruling(bare, i)
                    for i in range(len(p.forms)))
        if not saved:
            return -1.0
        score += 1
    score += 0.5 * sum(len(breaks(p, i)) > 1 for i in range(len(p.forms)))
    return score
