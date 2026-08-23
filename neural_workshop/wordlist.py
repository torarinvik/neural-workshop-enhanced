# -*- coding: utf-8 -*-
"""English words, ranked by how common they are, with a clue apiece.

Two games need words: the crossword needs them with clues, and the
Scrabble rack needs them with a way of saying which are obscure. Both
needs are the same need — *how well known is this word* — and neither
is answerable from a word list alone. A dictionary says ``sourish`` is
a word. It does not say that nobody has met it.

A third caller needs neither. Syllogisms wants words to *name things
with*, which asks something the files never say outright: whether a
word is a singular common noun. :func:`nouns` reads that off the
definition, because a definition gives the part of speech away by its
shape even when it does not name it.

So the pool is two files from Hugging Face, and neither is here:

``Maximax67/English-Valid-Words`` (Unlicense) carries about 173,000
words with their count in Google's 1-grams, which is what a rank means
below: ``the`` is 1 and ``labdacus`` is 149,000-somethingth. That rank
is the whole ladder. It is not a measure of difficulty in the abstract
— it is a measure of exposure, which is the thing a word game is
actually testing.

``MongoDB/english-words-definitions`` (Apache 2.0) carries a definition
or two for 467,000 words, written by Claude 3.7 Sonnet rather than by a
lexicographer. That matters twice over and both are said out loud on
the crossword's options screen: a definition here can be wrong, and it
was not written to be a clue.

**Every one of those definitions gives the answer away.** Not most —
measured over the 172,767 that overlap the frequency list, 172,684 name
the word in their first sentence and the rest name a form of it. They
are glosses: "A zebra is a large African equine mammal". Used as
printed, the crossword would be a copying exercise.

That is repairable and :func:`clue_from` is the repair. The gloss opens
with the word and a copula, so the opening is cut; anything left that
shares the word's stem would still hand it over, so a definition with
one is thrown away rather than blanked, because a clue with a hole in
it tells you how long the answer is twice. What survives reads the way
a clue reads:

    zebra      large African equine mammal with black and white stripes
    quixotic   exceedingly idealistic, unrealistic, and impractical
    usury      practice of lending money at unreasonably high rates

144,000 of the 173,000 come through. What is thrown away is mostly
words whose definition is a sentence about the word rather than a
meaning, which are the ones that would have made poor clues anyway.

**What still leaks is proper nouns.** ``stephen``, ``anubis`` and
``bausch`` are in the frequency list because people write them.
:data:`PROPER` catches the ones whose clue opens by placing them — "a
town in New Haven County" — and :data:`NAMED` the ones that say
"surname" or "given name" anywhere, which between them are 5,200 of
the 149,000 that would otherwise have got through. What is left is
the ones that read as ordinary definitions: "ancient Egyptian god of
the dead", "historic county of Scotland". Sampled at eight a band,
the residue is roughly one clue in twelve above rank 30,000 and rarer
below it. A crossword with the occasional proper noun in it is a
normal crossword, so this is reported rather than chased.

Nothing here downloads on its own. A caller asks:

    python -m neural_workshop.wordlist

which fetches both files (5 MB and 95 MB) into the player's data
directory and distils them into one tab-separated index — word, rank,
clue — because reading 95 MB of JSON at every deal is not a thing a
game may do. Distilling takes about two seconds and leaves 144,000
rows; loading the index afterwards takes under a tenth of a second.

With nothing fetched there is still :data:`SEED`, 669 short common
words, which is enough for Scrabble to be played and for a test
to run and is *not* enough for a crossword, because it carries no
clues. The crossword says so on its own screen rather than dealing
something thin and pretending.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import csv
import json
import os
import re
import urllib.error
import urllib.request
from typing import (Callable, Dict, Iterable, List, NamedTuple, Optional,
                    Sequence, Tuple)

from . import runtime
from .paths import get_data_dir

#: Seconds to wait on any one request.
_TIMEOUT = 60

_HEADERS = {'User-Agent': 'neural-workshop'}

_FILE_URL = 'https://huggingface.co/datasets/%s/resolve/main/%s'

#: Called with (bytes so far, bytes expected) as a download proceeds.
Progress = Callable[[int, int], None]


class Source(NamedTuple):
    """One file in one Hugging Face dataset."""

    key: str
    repo: str
    path: str
    approx_bytes: int
    licence: str
    note: str


WORDS = Source(
    'words', 'Maximax67/English-Valid-Words',
    'valid_words_sorted_by_frequency.csv', 4_988_910, 'Unlicense',
    '173,000 words ranked by their count in Google 1-grams')

CLUES = Source(
    'clues', 'MongoDB/english-words-definitions', 'vocab.jsonl',
    94_702_548, 'Apache-2.0',
    'definitions for 467,000 words, written by a language model')

SOURCES: Dict[str, Source] = {WORDS.key: WORDS, CLUES.key: CLUES}

#: Words are lower-case and nothing else. The frequency list holds a
#: certain amount of scanner debris, and this is most of what keeps it
#: out.
_PLAIN = re.compile(r'^[a-z]+$')

#: The opening of a gloss: the word, a copula, and an article. The
#: article has to be followed by space or ``An`` eats the ``a`` of
#: ``anything`` and the clue starts mid-word.
LEAD = re.compile(r"^[^a-z]*[a-z'\- ]{1,30}?\s+(?:is|are|was|were|refers?\s+to|"
                  r"means|denotes|describes)\b[:,]?\s+(?:(?:an?|the)\s+)?",
                  re.IGNORECASE)

#: Clue openings that mean the entry is a place rather than a word.
PROPER = re.compile(r"^(a |an |the )?(sur)?name\b|^(given|male|female)\s+name|"
                    r"^(town|city|village|region|commune|municipality|province|"
                    r"county|district|river|island|surname|hamlet|borough|"
                    r"parish|census|locality|unincorporated)\b", re.IGNORECASE)

#: And anywhere in the clue, the phrasings that mean it is a person.
#: Separate from :data:`PROPER` because "German surname meaning bump"
#: and "masculine given name of Greek origin" do not *open* with the
#: word that gives them away, and an anchored pattern let both through.
NAMED = re.compile(r"\b(sur)?name\b|\bgiven name\b|\bfamily name\b",
                   re.IGNORECASE)

#: How short and how long a clue may be, in words. Three because two is
#: a synonym rather than a clue; twenty because the screen has one line.
CLUE_WORDS = (3, 20)


def stem_of(word: str) -> str:
    """The opening a related form would share. Deliberately blunt.

    ``running`` and ``runs`` share ``run``, and a stemmer that knew
    that would be a dependency. Taking all but the last two letters,
    floored at four, catches the plural, the participle and the
    comparative, which is what a clue actually leaks through.
    """
    return word[:max(4, len(word) - 2)]


def clue_from(word: str, definition: str) -> Optional[str]:
    """A clue for *word*, or ``None`` if this definition cannot be one.

    Refused rather than repaired when the word's own stem survives the
    opening cut: blanking it would say how long the answer is a second
    time, and there are 149,000 words that need no such help.
    """
    stem = stem_of(word)
    body = definition.strip()
    cut = LEAD.match(body)
    if cut and word in body[:cut.end()].lower():
        body = body[cut.end():]
    body = re.sub(r'\s+', ' ', body).strip()
    if not body[:1].isalpha() or PROPER.match(body) or NAMED.search(body):
        return None
    for token in re.findall(r"[A-Za-z']+", body):
        if token.lower().startswith(stem):
            return None
    if not CLUE_WORDS[0] <= len(body.split()) <= CLUE_WORDS[1]:
        return None
    return body


# --- words that can name a thing ------------------------------------------
#
# What Syllogisms wants is a word to *label* something with — "every X
# is a Y" — and for that it has to be a singular common noun. "every
# products is a similar" is not a premise, and "every peggy is a
# namibia" is a premise about two people who might be anybody.
#
# There is no part-of-speech tag anywhere in either file. What there
# is, is a definition, and a definition gives the part of speech away
# by its shape: a verb is glossed "to run", an adjective "having the
# quality of", an adverb "in a manner that", and a good half of the
# non-nouns simply say which they are. That is what these read.


#: What a clue says when the word it defines is not a singular common
#: noun. Two halves: an opening whose shape names the part of speech,
#: and a phrase anywhere that names it outright.
NOT_A_NOUN = re.compile(
    r"^(?:to|having|used|being|characterized|relating|pertaining|marked|"
    r"capable|able|expressing|denoting|indicating|describing|in|at|on|by|"
    r"with|of|for|from|very|extremely|capital|largest|official|plural|"
    r"something|someone|character|responsible|known|one|first|second|third|"
    r"ordinal|cardinal)\b|"
    r"\b(?:verb|adjective|adverb|preposition|conjunction|pronoun|determiner|"
    r"article|interjection|prefix|suffix|acronym|abbreviation|initialism|"
    r"contraction|past tense|past participle|present participle|"
    r"third-person|infinitive|imperative|comparative|superlative|"
    r"plural of|plural form|symbol for|variant spelling|"
    r"alternative spelling)\b", re.IGNORECASE)

#: Endings a word wears when it is a form of another word, and the
#: stem each one is worn over.
ENDINGS = (('ies', 'y'), ('es', ''), ('s', ''), ('est', ''), ('est', 'e'),
           ('ed', ''), ('ed', 'e'), ('ing', ''), ('ing', 'e'))

#: Endings that are an adjective far oftener than they are a noun.
#: ``-ic`` and ``-al`` are not here on purpose: music, logic, animal
#: and capital are all nouns and there are hundreds more of them.
ADJECTIVE = ('ous', 'ful', 'ish', 'able', 'ible', 'less')

#: What a definition says when the word it defines is one English
#: itself marks as coarse. A screen on the register rather than a list
#: of words: three entries in the band answer to it, and they are the
#: three anybody would have named. It says nothing about the
#: anatomical vocabulary, which is defined clinically and reads that
#: way.
COARSE = re.compile(r"\b(vulgar|obscene|profane|profanity|derogatory|"
                    r"epithet|expletive|offensive term|swear word|"
                    r"curse word)\b", re.IGNORECASE)


def countable(word: str, known: frozenset) -> bool:
    """Whether *word* has a plural, which is most of being a thing.

    The strongest single signal there is here, and it costs one set
    lookup. ``camel`` has ``camels`` and ``coastal`` has no
    ``coastals``; ``bacteria`` and ``formulae`` are already plural and
    have nothing past them; ``obesity`` and ``patience`` are mass
    nouns, which are things one cannot have two of and so cannot be
    "every X is a Y" either.

    Both endings are accepted rather than chosen between, because the
    choice is about sound: ``church`` takes ``churches`` and
    ``stomach`` takes ``stomachs``, and nothing here can hear which.
    """
    if word + 's' in known or word + 'es' in known:
        return True
    return word.endswith('y') and word[:-1] + 'ies' in known


def a_form_of(word: str, known: frozenset) -> bool:
    """Whether *word* is an inflection of some other word in *known*.

    Blunt on purpose, the same way :func:`stem_of` is: doubling is
    undone ("cropping" is "crop") and nothing else is. Throwing away
    a good noun costs one word out of thousands; keeping ``beauties``
    costs a premise that reads as two things at once.
    """
    if word.endswith('ly'):
        return True
    for tail, back in ENDINGS:
        if not word.endswith(tail) or len(word) - len(tail) < 3:
            continue
        stem = word[:-len(tail)] + back
        if stem in known:
            return True
        if len(stem) > 3 and stem[-1] == stem[-2] and stem[:-1] in known:
            return True
    return False


def noun_like(entry: Entry, known: frozenset) -> bool:
    """Whether *entry* can stand as the name of a thing.

    The clue is read four ways. Any capital letter in it and the word
    is a place, a person or a brand — that is the cheapest screen there
    is for the proper nouns :data:`PROPER` and :data:`NAMED` leave
    behind, and it is affordable because a name only has to be *a*
    noun, not any particular one. Then the register. Then the part of
    speech, as far as the gloss admits it. Then the head of the gloss:
    a clue that opens with a plural ("kidneys or kidney function") or
    with a participle ("possessing skill") is describing a quality
    rather than a thing, whatever the word looks like.

    And then the word itself is asked whether it has a plural, which
    is the one test that does not go through the definition at all.
    """
    if not entry.clue or any(one.isupper() for one in entry.clue):
        return False
    if COARSE.search(entry.clue) or NOT_A_NOUN.search(entry.clue):
        return False
    if entry.word.endswith(ADJECTIVE) or a_form_of(entry.word, known):
        return False
    if not countable(entry.word, known):
        return False
    head = re.match(r'[a-z]+', entry.clue)
    return head is not None and not a_form_of(head.group(), known)


# --- where the files live -------------------------------------------------


def words_dir() -> str:
    """Where the fetched word files live, outside the repository."""
    path = os.path.join(get_data_dir(), 'words')
    os.makedirs(path, exist_ok=True)
    return path


def local_path(source: Source) -> str:
    return os.path.join(words_dir(), os.path.basename(source.path))


def have(source: Source) -> bool:
    """Whether *source* is on disk and not obviously truncated."""
    path = local_path(source)
    return (os.path.exists(path)
            and os.path.getsize(path) > source.approx_bytes // 2)


def index_path() -> str:
    return os.path.join(words_dir(), 'lexicon.tsv')


def index_ready() -> bool:
    """Whether the distilled index exists and is newer than its sources."""
    index = index_path()
    if not os.path.exists(index):
        return False
    made = os.path.getmtime(index)
    return all(not os.path.exists(local_path(one))
               or os.path.getmtime(local_path(one)) <= made
               for one in SOURCES.values())


def missing_message(source: Source) -> str:
    """What to tell a player whose pool is not there."""
    return ('%s needs %s (%s, about %d MB) — run '
            'python -m neural_workshop.wordlist'
            % (source.key, source.repo, source.licence,
               source.approx_bytes // 1_000_000))


# --- fetching -------------------------------------------------------------


def _open(url: str, timeout: int = _TIMEOUT):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=_HEADERS), timeout=timeout)


def fetch(source: Source, progress: Optional[Progress] = None) -> bool:
    """Download *source* if it is not already here. Returns whether it is.

    Streamed rather than read whole: the definitions file is 95 MB and
    holding it twice — once as bytes and once on the way out — is a
    waste of a machine that may be doing something else. Written beside
    the target and renamed, so an interrupted download never leaves a
    half file that later parses as a short one.
    """
    if have(source):
        return True
    path = local_path(source)
    partial = path + '.part'
    try:
        with _open(_FILE_URL % (source.repo, source.path)) as response:
            expected = int(response.headers.get('Content-Length')
                           or source.approx_bytes)
            got = 0
            with open(partial, 'wb') as handle:
                while True:
                    chunk = response.read(1 << 18)
                    if not chunk:
                        break
                    handle.write(chunk)
                    got += len(chunk)
                    if progress:
                        progress(got, expected)
    except (urllib.error.URLError, OSError) as exc:
        runtime.debug_msg('%s: %s' % (source.key, exc))
        try:
            os.unlink(partial)
        except OSError:
            pass
        return False
    os.replace(partial, path)
    return True


# --- distilling -----------------------------------------------------------


def ranks() -> Dict[str, int]:
    """Word to frequency rank, read from the fetched CSV."""
    found: Dict[str, int] = {}
    path = local_path(WORDS)
    if not os.path.exists(path):
        return found
    with open(path, encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            word = (row.get('Word') or '').strip().lower()
            if _PLAIN.match(word) and word not in found:
                try:
                    found[word] = int(row['Rank'])
                except (KeyError, ValueError):
                    continue
    return found


def build_index(progress: Optional[Callable[[int], None]] = None) -> int:
    """Distil both files into one tab-separated index. Returns its rows.

    Written whole and renamed, for the reason every other download here
    is: an index truncated by a interrupted run parses fine and is
    quietly missing its second half.
    """
    ordered = ranks()
    if not ordered or not os.path.exists(local_path(CLUES)):
        return 0
    rows: List[Tuple[int, str, str]] = []
    with open(local_path(CLUES), encoding='utf-8') as handle:
        for count, line in enumerate(handle):
            if progress and not count % 20000:
                progress(count)
            try:
                row = json.loads(line)
            except ValueError:
                continue
            word = (row.get('term') or '').strip().lower()
            rank = ordered.get(word)
            if rank is None:
                continue
            for definition in row.get('definitions') or ():
                clue = clue_from(word, definition)
                if clue:
                    rows.append((rank, word, clue))
                    break
    rows.sort()
    partial = index_path() + '.part'
    with open(partial, 'w', encoding='utf-8') as handle:
        for rank, word, clue in rows:
            handle.write('%s\t%d\t%s\n' % (word, rank, clue.replace('\t', ' ')))
    os.replace(partial, index_path())
    return len(rows)


# --- the pool a game sees -------------------------------------------------


class Entry(NamedTuple):
    """One word: how it is spelt, how common it is, and its clue."""

    word: str
    #: 1 for ``the``. Small is common.
    rank: int
    #: Empty when the pool has no clues, which is what :data:`SEED` is.
    clue: str = ''


#: Short common words, so that a machine
#: that has fetched nothing can still deal a Scrabble rack. Ranked by
#: their position here, which is their frequency order, so the bands
#: below mean the same thing in miniature. Written as prose because
#: a tuple of 669 strings is not a thing to read past.
SEED_WORDS = (
    'the and that for with was not this are from which have his but you '
    'were they had all one has their will been can there other would her '
    'more may when its these new she such who time than any what some '
    'also about only into out two them him first said see state under '
    'should made could after then over between most your work where each '
    'many now like very upon must those own them well made great year '
    'much been being both because same water while long make even part '
    'right through years men general life form good national never little '
    'know down still last used place found high does day found number '
    'come during before small since against course three system without '
    'here another public thought given men might once name too took think '
    'often case group say early important several want become social '
    'possible order left area fact per second local though himself '
    'political power far country different result school less body process '
    'therefore human times money among control study whether best young '
    'family provide better order line free open change person real level '
    'question interest business late needs least true land probably '
    'special value light almost person effect white later study whole '
    'church problem present period service hand short major head large '
    'college table church death close view field house town along above '
    'south north west east black white green red blue brown gold silver '
    'earth stone river sea sky star sun moon fire wind rain snow ice '
    'tree wood leaf grass flower fruit seed root plant field farm garden '
    'horse dog cat bird fish cow pig sheep goat mouse rat bear wolf lion '
    'road path bridge wall door window roof floor room house home city '
    'food bread meat milk salt sugar wine beer tea coffee soup rice corn '
    'gold iron steel glass paper cloth wool cotton silk leather brick '
    'book page word line story song music voice sound noise silence '
    'hand foot arm leg head face eye ear nose mouth tooth hair skin bone '
    'heart blood brain mind soul dream sleep wake rest walk run jump '
    'hold give take send bring keep leave stop start move turn stand sit '
    'speak talk tell ask answer call name write read learn teach show '
    'build break cut burn melt freeze boil cook wash clean dry fill empty '
    'buy sell pay cost price trade market shop store money coin bill '
    'king queen lord lady child boy girl man woman friend enemy stranger '
    'north south winter summer spring autumn morning evening night noon '
    'week month year hour minute today tomorrow yesterday always never '
    'happy sad angry afraid brave proud kind cruel wise foolish clever '
    'quick slow early late soon often rarely quiet loud sharp dull heavy '
    'light dark bright warm cold cool hot wet dry hard soft rough smooth '
    'thick thin wide narrow deep shallow tall short round square flat '
    'clean dirty full empty rich poor strong weak young old new fresh '
    'true false right wrong good bad best worst more less most least '
    'first last next final single double triple half whole part piece '
    'north bank field river lake ocean island shore beach cliff hill '
    'mountain valley forest desert swamp cave rock sand mud clay dust '
    'storm cloud thunder lightning rainbow shadow flame smoke steam '
    'metal wire rope chain nail hammer knife spoon fork plate cup bowl '
    'chair bench desk shelf box bag basket bottle barrel bucket ladder '
    'train boat ship plane wheel engine motor pump valve gear spring '
    'letter number figure point angle circle line curve shape colour '
    'north sound smell taste touch sight hearing feeling thought memory '
    'reason cause effect result method system rule law order plan aim '
    'battle army enemy weapon sword shield arrow spear armour castle '
    'village market temple church tower gate wall tomb grave stone bone '
    'story truth lie secret promise oath gift prize reward blame fault '
    'health illness pain cure medicine doctor nurse patient hospital '
    'school teacher student lesson class exam grade paper pencil chalk '
    'music drum flute horn string song dance stage actor play scene '
    'paint brush colour canvas image picture photograph camera film '
    'north summer harvest seed plough field crop grain flour bread oven '
    'thread needle cloth coat shirt dress shoe hat glove belt button '
    'clock watch bell alarm signal flag mark sign symbol code message '
    'travel journey road map guide path route distance speed direction '
    'nation people tribe family parent mother father brother sister son '
    'daughter uncle aunt cousin nephew niece husband wife widow orphan '
).split()

SEED: Tuple[Entry, ...] = tuple(
    Entry(word, position + 1)
    for position, word in enumerate(dict.fromkeys(SEED_WORDS)))

#: Rank bands the ladders are built out of, and roughly what they mean
#: to a person. Measured on the index, not asserted: the counts are
#: three-to-eight-letter words with a clue, of which there are 82,000.
BANDS: Tuple[Tuple[str, int, int], ...] = (
    ('everyday', 1, 3000),           # 2,224 words
    ('common', 1, 10000),            # 6,486
    ('familiar', 1, 30000),          # 17,381
    ('bookish', 1, 80000),           # 40,963
    ('the whole list', 1, 1 << 30),  # 77,815
)


class Lexicon:
    """A pool of words, indexed the ways the two games ask for them."""

    def __init__(self, entries: Iterable[Entry]) -> None:
        self.entries: Tuple[Entry, ...] = tuple(
            sorted(entries, key=lambda one: one.rank))
        self.at: Dict[str, Entry] = {one.word: one for one in self.entries}
        self.words = frozenset(self.at)
        by_length: Dict[int, List[Entry]] = {}
        for one in self.entries:
            by_length.setdefault(len(one.word), []).append(one)
        self.by_length: Dict[int, Tuple[Entry, ...]] = {
            length: tuple(group) for length, group in by_length.items()}
        #: Every prefix of every word, so a fill or a Scrabble solver
        #: can abandon a dead branch instead of walking it to the end.
        self._prefixes: Dict[int, frozenset] = {}
        #: Answers to :meth:`fitting`, which a fill asks the same
        #: questions of over and over as it restarts.
        self._fits: Dict[str, Tuple[Entry, ...]] = {}
        #: Narrowed copies of this pool, so a task that deals the same
        #: rung twice does not rebuild the index twice.
        self._narrow: Dict[Tuple, 'Lexicon'] = {}

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def clued(self) -> bool:
        """Whether this pool can set a crossword at all."""
        return any(one.clue for one in self.entries[:64])

    def valid(self, word: str) -> bool:
        return word in self.words

    def rank(self, word: str) -> int:
        one = self.at.get(word)
        return one.rank if one else 0

    def clue(self, word: str) -> str:
        one = self.at.get(word)
        return one.clue if one else ''

    def prefixes(self, length: int = 0) -> frozenset:
        """Openings of words of exactly *length*, or of any word if ``0``.

        Kept per length, and that is not a refinement — it is most of
        the pruning. Pooled across lengths, ``ab`` counts as a live
        opening for a five-letter slot because ``abc`` exists, and a
        crossword fill following that advice walks to the bottom of
        every column before finding out. Split by length, a seven by
        seven that could not be dealt at all deals in a fifth of a
        second.
        """
        if length not in self._prefixes:
            found = set()
            for one in self.entries:
                if length and len(one.word) != length:
                    continue
                for cut in range(1, len(one.word)):
                    found.add(one.word[:cut])
            self._prefixes[length] = frozenset(found)
        return self._prefixes[length]

    def band(self, lo: int, hi: int,
             length: Optional[int] = None) -> Tuple[Entry, ...]:
        """Words ranked in ``[lo, hi)``, of *length* if one is given."""
        pool = (self.by_length.get(length, ())
                if length is not None else self.entries)
        return tuple(one for one in pool if lo <= one.rank < hi)

    def narrowed(self, lo: int = 1, hi: int = 1 << 30,
                 lengths: Sequence[int] = ()) -> 'Lexicon':
        """A smaller pool, so a solver walks a rung's words and no others.

        Cached on the pool it came from. The caching is not tidiness:
        a narrowed pool is where the prefix sets and the pattern
        answers live, and rebuilding it once a deal throws all of them
        away.
        """
        key = (lo, hi, tuple(sorted(set(lengths))))
        if key not in self._narrow:
            keep = set(lengths)
            self._narrow[key] = Lexicon(
                one for one in self.entries
                if lo <= one.rank < hi
                and (not keep or len(one.word) in keep))
        return self._narrow[key]

    def fitting(self, pattern: str) -> Tuple[Entry, ...]:
        """Words matching *pattern*, where ``.`` is any letter.

        Answers are kept, because a crossword fill asks the same
        question thousands of times: a restart with a different grid
        still opens with an all-blank row of the same width, and a
        linear walk of twenty thousand words to answer it again is
        most of what a deal was spending its time on.
        """
        if pattern in self._fits:
            return self._fits[pattern]
        pooled = self.by_length.get(len(pattern), ())
        if '.' not in pattern:
            one = self.at.get(pattern)
            found = (one,) if one is not None else ()
        else:
            wanted = [(at, ch) for at, ch in enumerate(pattern) if ch != '.']
            found = tuple(one for one in pooled
                          if all(one.word[at] == ch for at, ch in wanted))
        if len(self._fits) < _FIT_CACHE:
            self._fits[pattern] = found
        return found


#: Pattern answers a pool will remember. Big enough that a crossword
#: deal never evicts, small enough that a long session cannot grow it
#: without bound.
_FIT_CACHE = 200000

_POOLS: Dict[Tuple[int, int], Lexicon] = {}


def _read_index(limit: int) -> List[Entry]:
    found: List[Entry] = []
    try:
        with open(index_path(), encoding='utf-8') as handle:
            for line in handle:
                parts = line.rstrip('\n').split('\t')
                if len(parts) != 3:
                    continue
                rank = int(parts[1])
                if rank >= limit:
                    continue
                found.append(Entry(parts[0], rank, parts[2]))
    except (OSError, ValueError) as exc:
        runtime.debug_msg(exc)
    return found


def pool(max_rank: int = 1 << 30, max_length: int = 15) -> Lexicon:
    """The word pool, from the index if there is one and the seed if not.

    Cached per request, because the games ask for the same two or three
    pools over and over and reading 149,000 rows for each deal would be
    most of a rung's time.
    """
    key = (int(max_rank), int(max_length))
    if key in _POOLS:
        return _POOLS[key]
    rows = _read_index(int(max_rank)) if index_ready() else []
    if not rows:
        rows = [one for one in SEED if one.rank < max_rank]
    made = Lexicon(one for one in rows if len(one.word) <= max_length)
    _POOLS[key] = made
    return made


#: The default band for :func:`nouns`. Common enough that the word is
#: read rather than deciphered, which is the whole point of using real
#: ones: the difficulty is meant to be in the premises.
NOUN_RANK = 20000

_NOUNS: Dict[Tuple, Lexicon] = {}


def nouns(max_rank: int = NOUN_RANK,
          lengths: Tuple[int, int] = (3, 8)) -> Lexicon:
    """Words that can name a thing, drawn from the fetched index.

    Empty when nothing has been fetched — the seed list is function
    words and carries no clues, so there is nothing here to read. A
    caller that needs names either has this or makes them up.

    3,461 words come through at the default band, and they are not all
    nouns. Sampled sixty at a time, three or four are not: an
    adjective that also has a plural ("rough", "idle"), a spelling
    nobody writes ("tho"), the occasional proper noun that never once
    takes a capital. Call it one in fifteen, reported rather than
    chased: a name here is a label, and an adjective standing in for a
    noun reads oddly and means nothing else.
    """
    key = (int(max_rank), tuple(lengths))
    if key in _NOUNS:
        return _NOUNS[key]
    base = pool()
    # The widest list of English words on the machine, which is the
    # frequency file rather than the index: the index only holds words
    # that kept a clue, and it has ``nets`` in it but not ``net``, so
    # asked what ``nets`` is the plural of it would answer nothing.
    known = frozenset(ranks()) | base.words
    low, high = lengths
    seen: Dict[str, Entry] = {}
    for one in base.entries:
        if one.rank >= max_rank or not low <= len(one.word) <= high:
            continue
        if one.word in seen or not noun_like(one, known):
            continue
        seen[one.word] = one
    made = Lexicon(seen.values())
    _NOUNS[key] = made
    return made


def forget() -> None:
    """Drop the cached pools, for a test that changes what is on disk."""
    _POOLS.clear()
    _NOUNS.clear()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python -m neural_workshop.wordlist`` — fetch both, then distil."""
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    unknown = [one for one in args if one not in SOURCES]
    if unknown:
        print('Unknown source(s): %s' % ', '.join(unknown))
        print('Known: %s' % ', '.join('%s (%s, %s, %d MB)'
                                      % (key, one.note, one.licence,
                                         one.approx_bytes // 1_000_000)
                                      for key, one in sorted(SOURCES.items())))
        return 2
    for key in (args or sorted(SOURCES)):
        source = SOURCES[key]
        if have(source):
            print('%-6s already here' % key)
            continue
        print('%-6s %s, about %d MB' % (key, source.repo,
                                        source.approx_bytes // 1_000_000))

        def report(got: int, want: int) -> None:
            print('\r  %5.1f / %.1f MB' % (got / 1e6, want / 1e6),
                  end='', flush=True)

        print('\r  %s' % ('fetched' if fetch(source, report) else 'failed'))
    if have(WORDS) and have(CLUES) and not index_ready():
        print('distilling', end='', flush=True)
        rows = build_index(lambda seen: print('.', end='', flush=True))
        print('\r%d words with a usable clue, in %s' % (rows, index_path()))
    made = pool()
    print('%d words in the pool%s' % (len(made),
                                      '' if made.clued else ' (no clues)'))
    return 0


__all__ = ['ADJECTIVE', 'BANDS', 'CLUES', 'CLUE_WORDS', 'COARSE', 'ENDINGS',
           'Entry',
           'Lexicon', 'NAMED', 'NOT_A_NOUN', 'NOUN_RANK',
           'PROPER', 'Progress',
           'SEED', 'SOURCES', 'Source', 'WORDS', 'a_form_of', 'build_index',
           'clue_from', 'countable',
           'fetch', 'forget', 'have', 'index_path', 'index_ready',
           'local_path', 'main', 'missing_message', 'noun_like', 'nouns',
           'pool', 'ranks',
           'stem_of', 'words_dir']


if __name__ == '__main__':
    raise SystemExit(main())
