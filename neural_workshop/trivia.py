# -*- coding: utf-8 -*-
"""General-knowledge questions, and the wrong answers that go with them.

The questions are TriviaQA's — ``mandarjoshi/trivia_qa``, 138,384 of
them in the ``rc`` training split, written by trivia enthusiasts rather
than by anyone with a model in mind. Only two of that split's columns
are wanted here, the question and its answer, so what is fetched is the
``rc.nocontext`` configuration: the same rows with the evidence
documents left off. Fetching ``rc`` itself would be tens of megabytes
of Wikipedia and web pages read one sentence at a time.

**TriviaQA is not multiple choice, and this is.** The dataset gives a
question and a free-text answer with its aliases; the screen has to
offer something to pick between, so the wrong answers are other
questions' right ones. That choice is the whole of the difficulty here,
and it is made in one place, :func:`distractors`:

* **A wrong answer has to be wrong.** ``Chicago`` and ``Chicago,
  Illinois`` are the same answer twice, and a question with two right
  options on it is not a question. So the alias lists are kept — that
  is what they are for — and a candidate is refused if either answer
  is in the other's aliases.

* **A wrong answer has to be the same *shape*.** ``1969`` against
  ``Portugal`` is not a question about the moon landing, it is a
  question about which option is a year, and a learner will find that
  out long before it finds out anything else. So the ladder's upper
  rungs draw only from answers of the same :func:`kind_of` — years
  against years, names against names — and the shape stops carrying
  any signal at all.

* **The shapes are shapes and not categories.** :func:`kind_of` reads
  capitalisation and digits. It cannot tell a person from a band, and
  it is not asked to: the claim is only that the options look alike
  enough that their looks are not the answer. A category would need a
  knowledge base, and one that was wrong a twentieth of the time would
  be worse than this, because its failures would land on the
  interesting questions rather than on random ones.

The ladder is those two dials — how many options, and whether they are
matched — and nothing else. It is deliberately not a ladder over the
*questions*: TriviaQA does not say which of its questions are hard, and
a measure of that read off the answer's length or its frequency would
be invented rather than measured.

Nothing here downloads on its own. A caller asks:

    python -m neural_workshop.trivia [count]

which pages the questions out of Hugging Face's datasets-server, a
hundred at a time, and distils them into one tab-separated index.
10,000 is the default and is about 11 MB of JSON on the way in and
under a megabyte on disk after. Pages already fetched are skipped, so
an interrupted run is resumed by running it again.

With nothing fetched there is still :data:`SEED`, a hundred-odd
questions written for this file, which is enough for the task to be
played and for a test to run and is *not* enough for a run of any
length to stay fresh. The screen says which pool it is dealing from
rather than letting a player wonder why the questions come round
again.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import json
import os
import random
import re
import urllib.error
import urllib.request
from typing import (Callable, Dict, FrozenSet, List, NamedTuple, Optional,
                    Sequence, Tuple)

from . import runtime
from .paths import get_data_dir

#: Seconds to wait on any one request.
_TIMEOUT = 60

_HEADERS = {'User-Agent': 'neural-workshop'}

#: The dataset, the configuration with the evidence left off, and the
#: split the dataset viewer opens on.
REPO = 'mandarjoshi/trivia_qa'
CONFIG = 'rc.nocontext'
SPLIT = 'train'
LICENCE = 'Apache-2.0'

#: Rows in ``rc.nocontext``'s training split, which is row for row the
#: same as ``rc``'s. Only used to say how much is left to fetch.
ROWS = 138384

#: Rows the datasets-server returns per request, and its ceiling.
PAGE = 100

#: How many questions ``python -m neural_workshop.trivia`` fetches when
#: it is not told. Enough that a run of fifteen a night takes two years
#: to come round, and small enough to be a minute's fetching.
DEFAULT_FETCH = 10000

_ROWS_URL = ('https://datasets-server.huggingface.co/rows'
             '?dataset=%s&config=%s&split=%s&offset=%d&length=%d'
             '&columns=question,answer')

#: Called with (rows so far, rows asked for) as a fetch runs.
Progress = Callable[[int, int], None]


# --- what a question is ---------------------------------------------------


class Question(NamedTuple):
    """One question, its answer as printed, and what else that answer is
    called."""

    asked: str
    answer: str
    #: What the answer looks like: see :func:`kind_of`.
    kind: str
    #: Normalised forms that mean the same thing, the answer's own
    #: included. Only ever used to keep a wrong option from being right.
    aliases: FrozenSet[str] = frozenset()


class Round(NamedTuple):
    """A question as it is put: the options, and which one is the answer."""

    question: Question
    options: Tuple[str, ...]
    answer: int
    rung: int

    @property
    def asked(self) -> str:
        return self.question.asked

    @property
    def shown_answer(self) -> str:
        return self.options[self.answer]


class Grade(NamedTuple):
    """One rung: how many options, and where the wrong ones come from."""

    name: str
    options: int
    #: Whether the wrong options must be the same shape as the right one.
    matched: bool


#: The ladder. Two dials, one of which only starts turning once the
#: other has run out of room: past four options a fifth wrong answer
#: drawn at random is a fifth free elimination rather than a harder
#: question, so the matching comes in first and the count goes on
#: climbing under it.
GRADES: Tuple[Grade, ...] = (
    Grade('one of two', 2, False),
    Grade('one of three', 3, False),
    Grade('one of four', 4, False),
    Grade('four alike', 4, True),
    Grade('five alike', 5, True),
    Grade('six alike', 6, True),
    Grade('eight alike', 8, True),
)

#: The widest a rung ever gets, which is the task's port count.
MOST_OPTIONS = max(grade.options for grade in GRADES)


def grade_at(rung: int) -> Grade:
    """The rung's grade, clamped to the ladder."""
    return GRADES[max(1, min(len(GRADES), int(rung))) - 1]


# --- normalising ----------------------------------------------------------

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_ARTICLE = re.compile(r'\b(?:a|an|the)\b')


def normalise(text: str) -> str:
    """TriviaQA's own comparison form: no case, no punctuation, no articles.

    Two answers that come out the same here are the same answer, and
    one of them must not be offered as the other's wrong option.
    """
    lowered = _PUNCT.sub(' ', text.lower())
    return ' '.join(_ARTICLE.sub(' ', lowered).split())


#: Words that sit uncapitalised inside a name without making it a phrase.
PARTICLES = frozenset(('da', 'de', 'del', 'della', 'der', 'di', 'du', 'la',
                       'le', 'van', 'von', 'y', 'bin', 'ibn', 'al', 'st',
                       'mc', 'and'))

_NUMBER = re.compile(r'^[0-9][0-9,. ]*(?:s|st|nd|rd|th|%)?$')
_YEAR = re.compile(r'^([0-9]{3,4})(?:s|$)')


def kind_of(answer: str) -> str:
    """What an answer *looks* like — never what it is about.

    Five shapes: ``year``, ``number``, ``name`` (two or more
    capitalised words), ``phrase`` (two or more words that are not all
    capitalised) and ``word``. A leading article is not part of the
    shape, so *the femur* is a word and *the Dead Sea* is a name.

    This is deliberately shallow. It exists so that a screen of options
    does not give its answer away by being the only date on it, and the
    moment it started trying to be a taxonomy it would start being
    wrong about the questions that are interesting.
    """
    body = answer.strip()
    if _NUMBER.match(body):
        found = _YEAR.match(body)
        if found and 1000 <= int(found.group(1)) <= 2100:
            return 'year'
        return 'number'
    words = [word for word in body.split() if word]
    if words and words[0].lower() in ('a', 'an', 'the'):
        words = words[1:]
    if len(words) <= 1:
        return 'word'
    for word in words:
        if not word[:1].isupper() and word.strip('.').lower() not in PARTICLES:
            return 'phrase'
    return 'name'


#: The shapes, for anything that wants to walk them in a fixed order.
KINDS: Tuple[str, ...] = ('year', 'number', 'name', 'phrase', 'word')


# --- distilling a row -----------------------------------------------------

#: A question shorter than this is not a trivia question, and one
#: longer than this does not fit on a screen above eight options.
QUESTION_CHARS = (16, 180)

#: An answer longer than this is a sentence rather than an option.
ANSWER_CHARS = 40

#: Aliases kept per answer. The dataset carries up to a few hundred —
#: every redirect Wikipedia has for the entity, in every language — and
#: all that is wanted is enough to catch another row offering the same
#: thing under another name.
ALIASES = 12

#: Answers that are not answers when they are on a list with three
#: others: half the options screen would be one of these two.
_YESNO = frozenset(('yes', 'no', 'true', 'false', 'none', 'unknown'))


def question_from(row: Dict) -> Optional[Question]:
    """One dataset row as a :class:`Question`, or ``None`` if it cannot be.

    Refused rather than repaired, and the refusal worth naming is the
    last one: a row that prints its own answer inside the question.
    *Which country's capital is Oslo?* answered by *Norway* is fine,
    but *In which year of the 1960s did the Beatles first play
    America?* answered by *1964* is a reading exercise, and the shape
    that catches the second catches little else.
    """
    asked = ' '.join(str(row.get('question') or '').split())
    answer_field = row.get('answer') or {}
    answer = ' '.join(str(answer_field.get('value') or '').split())
    if not asked or not answer:
        return None
    if not QUESTION_CHARS[0] <= len(asked) <= QUESTION_CHARS[1]:
        return None
    if len(answer) > ANSWER_CHARS or normalise(answer) in _YESNO:
        return None
    plain = normalise(answer)
    if not plain or plain in normalise(asked):
        return None
    names = [normalise(one) for one
             in ([answer] + list(answer_field.get('aliases') or ())[:ALIASES])]
    return Question(asked, answer, kind_of(answer),
                    frozenset(one for one in names if one))


# --- where the files live -------------------------------------------------


def trivia_dir() -> str:
    """Where the fetched pages and the index live, outside the repository."""
    path = os.path.join(get_data_dir(), 'trivia')
    os.makedirs(path, exist_ok=True)
    return path


def page_path(offset: int) -> str:
    """A page is named after the row it starts at, so a page already on
    disk is a page not fetched again."""
    return os.path.join(trivia_dir(), 'rows-%07d.json' % offset)


def pages_here() -> List[str]:
    """Every fetched page, in the order the rows came in."""
    try:
        found = sorted(one for one in os.listdir(trivia_dir())
                       if one.startswith('rows-') and one.endswith('.json'))
    except OSError:
        return []
    return [os.path.join(trivia_dir(), one) for one in found]


def index_path() -> str:
    return os.path.join(trivia_dir(), 'questions.tsv')


def index_ready() -> bool:
    """Whether the distilled index exists and is newer than every page."""
    index = index_path()
    if not os.path.exists(index):
        return False
    made = os.path.getmtime(index)
    return all(os.path.getmtime(one) <= made for one in pages_here())


def missing_message() -> str:
    """What to tell a player dealing from the seed."""
    return ('%d questions written into the game; %s (%s) has %d — run '
            'python -m neural_workshop.trivia'
            % (len(SEED), REPO, LICENCE, ROWS))


# --- fetching -------------------------------------------------------------


def _open(url: str, timeout: int = _TIMEOUT):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=_HEADERS), timeout=timeout)


def fetch(count: int = DEFAULT_FETCH,
          progress: Optional[Progress] = None) -> int:
    """Fetch enough pages to hold *count* rows. Returns the rows on disk.

    Pages are written whole and renamed, and named after their offset,
    so an interrupted fetch leaves the pages it finished and the next
    run starts where it stopped. A page that fails ends the run rather
    than leaving a hole in the middle: the offsets have to stay
    contiguous, or *how many rows are here* stops being a question the
    file names can answer.
    """
    want = max(0, min(int(count), ROWS))
    got = 0
    for offset in range(0, want, PAGE):
        length = min(PAGE, want - offset)
        path = page_path(offset)
        if os.path.exists(path):
            got += length
            if progress:
                progress(got, want)
            continue
        url = _ROWS_URL % (REPO.replace('/', '%2F'), CONFIG, SPLIT,
                           offset, length)
        try:
            with _open(url) as response:
                body = response.read()
            json.loads(body.decode('utf-8'))['rows']
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            runtime.debug_msg('trivia rows %d: %s' % (offset, exc))
            break
        partial = path + '.part'
        with open(partial, 'wb') as handle:
            handle.write(body)
        os.replace(partial, path)
        got += length
        if progress:
            progress(got, want)
    return got


# --- distilling -----------------------------------------------------------


def build_index(progress: Optional[Callable[[int], None]] = None) -> int:
    """Distil every fetched page into one tab-separated index.

    Written whole and renamed, for the same reason the pages are: an
    index truncated halfway parses fine and is quietly missing its
    second half.
    """
    rows: List[Question] = []
    seen = set()
    for count, path in enumerate(pages_here()):
        if progress:
            progress(count)
        try:
            with open(path, encoding='utf-8') as handle:
                page = json.load(handle)
        except (OSError, ValueError) as exc:
            runtime.debug_msg('%s: %s' % (path, exc))
            continue
        for row in page.get('rows') or ():
            made = question_from(row.get('row') or {})
            if made is None:
                continue
            key = normalise(made.asked)
            if key in seen:
                continue
            seen.add(key)
            rows.append(made)
    if not rows:
        return 0
    partial = index_path() + '.part'
    with open(partial, 'w', encoding='utf-8') as handle:
        for one in rows:
            handle.write('%s\t%s\t%s\t%s\n'
                         % (one.asked, one.answer, one.kind,
                            '|'.join(sorted(one.aliases))))
    os.replace(partial, index_path())
    return len(rows)


def _read_index() -> List[Question]:
    found: List[Question] = []
    try:
        with open(index_path(), encoding='utf-8') as handle:
            for line in handle:
                parts = line.rstrip('\n').split('\t')
                if len(parts) != 4:
                    continue
                found.append(Question(
                    parts[0], parts[1], parts[2],
                    frozenset(one for one in parts[3].split('|') if one)))
    except OSError as exc:
        runtime.debug_msg(exc)
    return found


# --- the pool a game sees -------------------------------------------------


class Bank:
    """A pool of questions, indexed the one way the deal asks for them."""

    def __init__(self, questions: Sequence[Question]) -> None:
        self.questions: Tuple[Question, ...] = tuple(questions)
        by_kind: Dict[str, List[Question]] = {}
        for one in self.questions:
            by_kind.setdefault(one.kind, []).append(one)
        self.by_kind: Dict[str, Tuple[Question, ...]] = {
            kind: tuple(group) for kind, group in by_kind.items()}

    def __len__(self) -> int:
        return len(self.questions)

    def alike(self, kind: str) -> Tuple[Question, ...]:
        """Every question whose answer has the same shape."""
        return self.by_kind.get(kind, ())

    def narrowest(self) -> int:
        """The most matched options the *thinnest* shape can fill.

        A shape the pool holds four of cannot fill eight matched
        options, and the deal falls back to another shape rather than
        offering the same answer twice. This is the number the options
        screen prints, so that a player choosing rung seven on the seed
        pool is told before the run rather than during it.
        """
        return min((len(group) for group in self.by_kind.values()), default=0)


_BANK: Dict[bool, Bank] = {}


def bank(fetched_only: bool = False) -> Bank:
    """The question pool: the fetched index if there is one, the seed if not.

    Cached, because a fifteen-question run asks for the same pool
    fifteen times and the index is thousands of rows.
    """
    key = bool(fetched_only)
    if key in _BANK:
        return _BANK[key]
    rows = _read_index() if index_ready() else []
    if not rows and not fetched_only:
        rows = list(SEED)
    made = Bank(rows)
    _BANK[key] = made
    return made


def fetched() -> bool:
    """Whether the pool being dealt from is the dataset's rather than the
    seed."""
    return len(bank(fetched_only=True)) > 0


def forget() -> None:
    """Drop the cached pool, for a test that changes what is on disk."""
    _BANK.clear()


# --- dealing --------------------------------------------------------------


def distractors(question: Question, pool: Bank, count: int, matched: bool,
                rng: random.Random) -> List[str]:
    """*count* wrong answers for *question*, drawn from *pool*.

    Matching is a preference and not a promise. A pool with three years
    in it cannot offer seven wrong ones of the same shape, and the
    honest fallback is a wrong answer of another shape rather than a
    question with fewer options than the rung says, or the same wrong
    answer written twice.
    """
    taken = set(question.aliases)
    asked = normalise(question.asked)
    found: List[str] = []

    def draw(source: Sequence[Question]) -> None:
        order = list(source)
        rng.shuffle(order)
        for other in order:
            if len(found) >= count:
                return
            plain = normalise(other.answer)
            # Either direction: the candidate may be an alias of this
            # answer, or this answer an alias of the candidate.
            if (not plain or plain in taken
                    or question.aliases & other.aliases
                    or plain in asked):
                continue
            taken.add(plain)
            taken.update(other.aliases)
            found.append(other.answer)

    if matched:
        draw(pool.alike(question.kind))
    draw(pool.questions)
    return found


def generate(rung: int, seed: Optional[int] = None,
             pool: Optional[Bank] = None) -> Optional[Round]:
    """One question at *rung*, or ``None`` when the pool cannot fill it.

    ``None`` means the pool holds nothing to ask, which is a thing the
    screen says out loud. A pool too thin for the rung's *width* is not
    that: it is dealt narrower, because a question with five options
    instead of six is still a question.
    """
    rng = random.Random(seed)
    grade = grade_at(rung)
    bench = pool if pool is not None else bank()
    if not len(bench):
        return None
    question = rng.choice(bench.questions)
    wrong = distractors(question, bench, grade.options - 1, grade.matched, rng)
    if not wrong:
        return None
    options = [question.answer] + wrong
    rng.shuffle(options)
    return Round(question, tuple(options), options.index(question.answer),
                 max(1, min(len(GRADES), int(rung))))


def correct(round_: Round, choice: int) -> bool:
    """Whether option *choice* is the one the dataset gives."""
    return int(choice) == round_.answer


# --- the questions there are with nothing fetched -------------------------
#
# Written for this file rather than taken from the dataset, so that a
# player who has fetched nothing is playing the same game rather than a
# sample of somebody else's corpus. They are spread across the five
# shapes on purpose: the thinnest shape holds fifteen, which is enough
# to fill the widest rung with matched options, so every rung of the
# ladder is a real rung on the seed pool and not a fallback.

SEED_ROWS = """\
In which year did the Berlin Wall fall?|1989
In which year did the Titanic sink?|1912
In which year did the First World War begin?|1914
In which year did the Second World War end in Europe?|1945
In which year did humans first land on the Moon?|1969
In which year was the American Declaration of Independence signed?|1776
In which year did the Chernobyl reactor explode?|1986
In which year was Magna Carta sealed at Runnymede?|1215
In which year did the French Revolution begin?|1789
In which year was the Soviet Union dissolved?|1991
In which year was the Battle of Hastings fought?|1066
In which year did Columbus first reach the Americas?|1492
In which year was Elizabeth II crowned?|1953
In which year did the Wright brothers first fly a powered aeroplane?|1903
In which year was the Universal Declaration of Human Rights adopted?|1948
In which year did the Great Fire of London break out?|1666
In which year was the first iPhone released?|2007
In which year did the Cuban Missile Crisis take place?|1962
In which year was Nelson Mandela released from prison?|1990
In which year did the airship Hindenburg burn at Lakehurst?|1937
How many strings does a standard violin have?|4
How many players from one side are on a football pitch at kick-off?|11
How many bones are there in the adult human body?|206
How many degrees are there in a circle?|360
How many keys does a standard piano have?|88
How many squares are there on a chessboard?|64
How many sides does a dodecagon have?|12
How many hearts does an octopus have?|3
How many time zones does Russia span?|11
How many books are there in the New Testament?|27
How many moons does Mars have?|2
At how many degrees Celsius does water boil at sea level?|100
How many stripes are there on the flag of the United States?|13
How many letters are there in the Greek alphabet?|24
How many players from one side are on a basketball court?|5
Who painted the Mona Lisa?|Leonardo da Vinci
Who wrote the play Hamlet?|William Shakespeare
Who was the first President of the United States?|George Washington
Who published the theory of general relativity?|Albert Einstein
Who wrote the novel Pride and Prejudice?|Jane Austen
Who was the first woman to win a Nobel Prize?|Marie Curie
Who composed the symphony that ends with the Ode to Joy?|Ludwig van Beethoven
Who led the Indian independence movement by non-violence?|Mahatma Gandhi
Who wrote the novel Nineteen Eighty-Four?|George Orwell
Who painted The Starry Night?|Vincent van Gogh
Who was the first person to walk on the Moon?|Neil Armstrong
Who wrote On the Origin of Species?|Charles Darwin
Who directed the 1960 film Psycho?|Alfred Hitchcock
Who was Prime Minister when Britain declared war on Germany in 1939?|Neville Chamberlain
Who was granted the American patent for the telephone in 1876?|Alexander Graham Bell
Who wrote the Harry Potter novels?|J. K. Rowling
Who was the first man in space?|Yuri Gagarin
Who wrote The Old Man and the Sea?|Ernest Hemingway
Who wrote the Divine Comedy?|Dante Alighieri
Who discovered penicillin?|Alexander Fleming
Who wrote the Sherlock Holmes stories?|Arthur Conan Doyle
Who gave the speech beginning "I have a dream"?|Martin Luther King
Who composed the opera The Magic Flute?|Wolfgang Amadeus Mozart
Who wrote War and Peace?|Leo Tolstoy
Who sculpted the David that stands in Florence?|Michelangelo Buonarroti
Who was the Macedonian king taught by Aristotle?|Alexander the Great
Which ocean lies between Africa and Australia?|the Indian Ocean
Which sea separates Europe from Africa?|the Mediterranean Sea
Which mountain range is taken as the border of Europe and Asia?|the Ural Mountains
Which mountain is the highest above sea level?|Mount Everest
Which American national park holds the geyser Old Faithful?|Yellowstone National Park
Which canal links the Mediterranean to the Red Sea?|the Suez Canal
Which structure runs for thousands of miles across northern China?|the Great Wall
Which tower was built for the Paris exhibition of 1889?|the Eiffel Tower
Which band released the album Abbey Road?|the Beatles
Which band released the album The Dark Side of the Moon?|Pink Floyd
Which ship carried the Pilgrims to America in 1620?|the Mayflower
Which war did the Treaty of Versailles bring to a formal end?|the First World War
Which newspaper broke the Watergate story?|the Washington Post
Which lake is the largest in the world by surface area?|the Caspian Sea
Which language has the most native speakers?|Mandarin Chinese
Which musical features the song Do-Re-Mi?|the Sound of Music
Which Tolkien novel opens in the Shire with an unexpected party?|the Hobbit
Which strait separates Spain from Morocco?|the Strait of Gibraltar
Which document begins "We the People"?|the Constitution of the United States
Which London palace houses the House of Commons?|the Palace of Westminster
Which Dickens novel opens "It was the best of times"?|A Tale of Two Cities
Which ancient wonder stood on the island of Pharos?|the Lighthouse of Alexandria
Which battle of 1815 ended the Napoleonic Wars?|the Battle of Waterloo
Which treaty of 1957 founded the European Economic Community?|the Treaty of Rome
Which Harper Lee novel is narrated by Scout Finch?|To Kill a Mockingbird
Which 1939 film ends with "there's no place like home"?|The Wizard of Oz
Which sea battle of 1805 cost Nelson his life?|the Battle of Trafalgar
Which Beckett play has two men waiting by a tree?|Waiting for Godot
Which American programme first landed people on the Moon?|the Apollo programme
Which court at The Hague settles disputes between states?|the International Court of Justice
Which children's book has a girl follow a white rabbit underground?|Alice's Adventures in Wonderland
Which chess piece may only move diagonally?|the bishop
Which bone of the human body is the longest?|the femur
Which organ of the human body makes insulin?|the pancreas
What is the capital of Australia?|Canberra
Which planet is known as the red planet?|Mars
Which metal is liquid at room temperature?|Mercury
Which country gave the Statue of Liberty to the United States?|France
Which is the largest planet of the Solar System?|Jupiter
Which naturally occurring substance is the hardest?|diamond
Which language is spoken in Brazil?|Portuguese
Which organ pumps blood around the body?|the heart
Which sport is played at Wimbledon?|tennis
On which continent is the Sahara?|Africa
In which city does the Colosseum stand?|Rome
Which sea creature has eight arms?|the octopus
What is the capital of Japan?|Tokyo
Which fruit is fermented to make wine?|grapes
Which country is the kangaroo native to?|Australia
Which element has atomic number 1?|hydrogen
Which instrument did Louis Armstrong play?|the trumpet
Which American state is nicknamed the Sunshine State?|Florida
Which mythical creature has a single horn?|the unicorn
Which part of a cell holds its DNA?|the nucleus
Which country's flag is a red circle on a white field?|Japan
What is the capital of Canada?|Ottawa
Which board game is won by checkmate?|chess
Which is the longest river in Africa?|the Nile
Which shape has three sides?|a triangle
"""


def _seed() -> Tuple[Question, ...]:
    made: List[Question] = []
    for line in SEED_ROWS.strip().splitlines():
        asked, _sep, answer = line.partition('|')
        made.append(Question(asked, answer, kind_of(answer),
                             frozenset((normalise(answer),))))
    return tuple(made)


SEED: Tuple[Question, ...] = _seed()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python -m neural_workshop.trivia [count]`` — fetch, then distil."""
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        want = int(args[0]) if args else DEFAULT_FETCH
    except ValueError:
        print('Usage: python -m neural_workshop.trivia [how many questions]')
        return 2
    print('%s (%s, %s), %d rows in the split' % (REPO, CONFIG, LICENCE, ROWS))

    def report(got: int, asked: int) -> None:
        print('\r  %6d / %d rows' % (got, asked), end='', flush=True)

    got = fetch(want, report)
    print('\r  %6d rows on disk%s'
          % (got, '' if got >= min(want, ROWS) else ' (fetch stopped early)'))
    if not index_ready():
        print('distilling', end='', flush=True)
        kept = build_index(lambda page: print('.', end='', flush=True))
        print('\r%d questions kept, in %s' % (kept, index_path()))
    forget()
    pool = bank()
    counts = ', '.join('%d %s' % (len(pool.alike(kind)), kind)
                       for kind in KINDS if pool.alike(kind))
    print('%d questions in the pool%s'
          % (len(pool), ' (%s)' % counts if counts else ''))
    if not fetched():
        print(missing_message())
    return 0


__all__ = ['ALIASES', 'ANSWER_CHARS', 'Bank', 'CONFIG', 'DEFAULT_FETCH',
           'GRADES', 'Grade', 'KINDS', 'LICENCE', 'MOST_OPTIONS', 'PAGE',
           'PARTICLES', 'QUESTION_CHARS', 'Progress', 'Question', 'REPO',
           'ROWS', 'Round', 'SEED', 'SEED_ROWS', 'SPLIT', 'bank',
           'build_index', 'correct', 'distractors', 'fetch', 'fetched',
           'forget', 'generate', 'grade_at', 'index_path', 'index_ready',
           'kind_of', 'main', 'missing_message', 'normalise', 'page_path',
           'pages_here', 'question_from', 'trivia_dir']


if __name__ == '__main__':
    raise SystemExit(main())
