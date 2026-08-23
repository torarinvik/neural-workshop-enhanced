# -*- coding: utf-8 -*-
"""Plain English sentences, for a task that corrupts them and asks for them.

The Scramble task needs text, and the text has to be *ordinary*. A
sentence assembled from a grammar would work — better, in one way,
because a generator can guarantee that its corruption has exactly one
undoing — and it was the first thing written here. It was thrown away.
What a person brings to ``the hrose is balck`` is everything they know
about horses and about English, and a sentence built from a template
tests how quickly they learn the template. So the text is real text,
and the price of that is stated plainly at the bottom of this
docstring rather than hidden.

The source is ``juno-labs/simple_wikipedia`` (CC BY-SA 3.0), a weekly
snapshot of Simple English Wikipedia — 276,302 articles written under
a house style of short sentences and a limited vocabulary, which is
the closest thing to a corpus of *plain* English that is also free to
redistribute. Being Wikipedia, it is attributed on the task's own
options screen and not only here.

Nothing downloads on its own. A caller asks:

    python -m neural_workshop.sentences

**It reads 46 MB of a 439 MB file, and that is the whole trick.** The
dataset is one parquet file of nine row groups; one row group is
34,087 articles, which is four times more usable text than this needs.
So the fetch opens the file over HTTP range requests, reads the
footer, and pulls exactly one column of one row group. Measured: 46
MB and four seconds.

The first version of this did not do that. It walked Hugging Face's
rows endpoint, a hundred articles a request, no dependency beyond
``urllib`` — and it worked for about 250 requests before the server
started answering 429 to everything, having collected a sixth of what
it needed in twelve minutes. A bulk read of a static file is what the
CDN is for; a paging API is not, and it says so with a status code.

Reading parquet needs ``pyarrow``, which is **not** a requirement of
the Workshop and is not imported anywhere else. It is imported inside
:func:`fetch` and nowhere else, so a player without it can still play
every other task and gets told what to install if they want this one.
The distilled bank is a plain text file; playing never reads parquet.

**Most of Wikipedia is not usable here and that is the point.** A
sentence survives :func:`usable` only if it is six to fourteen words,
every word is alphabetic, every word is in the frequency list, and
every word after the first is lowercase in the original. That last
one is the important filter: it throws away every sentence containing
a proper noun. A scrambled ``eostn`` is solvable and a scrambled
``ntsoe`` that turns out to have been *Notestein* is not, so the
names go before the game starts rather than being apologised for
afterwards.

Measured over the row group: 402,602 sentences seen and 36,118 kept —
roughly one in eleven. Of what is thrown away, most goes on the shape
filters and about a quarter on the rank ceiling alone. The thinnest
rung of the ladder still has 3,902 lines to draw on.

With nothing fetched there is :data:`SEED_TEXT`, sentences written
here out of a vocabulary small enough to be in the repository. It is
enough for the task to run and for the tests to mean something. It is
not enough for a run to stop repeating itself, and the screen says so.

**What real text costs.** A generated sentence can be checked for
having exactly one reconstruction; a real one cannot, because the
thing that rules out the wrong readings is knowing English, and
nothing here knows English. So this task does not promise that its
hard rungs are solvable — it *measures* how much of the answer is
still on the page (see :mod:`neural_workshop.scramble`), and above
the middle of the ladder that measurement is the only guarantee
there is. That is a weaker claim than the crossword makes and it is
made deliberately: the alternative was a task about a template.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import importlib.util
import io
import os
import re
import urllib.error
import urllib.request
from typing import (Callable, Dict, List, NamedTuple, Optional, Sequence,
                    Tuple)

from .wordlist import index_ready, pool, words_dir

#: Where the sentences come from, and under what.
REPO = 'juno-labs/simple_wikipedia'
LICENCE = 'CC BY-SA 3.0'
#: The one file the dataset ships, served by the CDN and range-readable.
PARQUET = ('https://huggingface.co/datasets/' + REPO
           + '/resolve/main/data/train-00000-of-00001.parquet')
#: Which row group to read. Nine of them; one is four times enough.
GROUP = 0
#: What reading that row group's one column actually costs.
BYTES = 46_000_000
#: How many sentences to keep. The row group holds about 45,000 usable.
TARGET = 40000
#: Sentence lengths worth having. Below six there is no context to
#: reason from; above fourteen the answer is a paragraph to type.
WORDS = (6, 14)
#: The rarest word a kept sentence may hold. Everything above this is
#: a word most readers have not met, and a scrambled one is a lottery.
TOP_RANK = 60000

_BANK = 'sentences.txt'
_TIMEOUT = 120
_CHUNK = 1 << 22

#: Markdown left in ``content_no_link`` — emphasis and code.
MARKUP = re.compile(r'\*\*|__|`|_')
#: Sentence ends. Crude, and it does not need to be better: anything it
#: gets wrong fails :func:`usable` a moment later.
BREAK = re.compile(r'(?<=[.!?])\s+')
PLAIN = re.compile(r'^[a-z]+$')
#: Anything here means the sentence is a list, a citation or a number.
REFUSED = '.,;:()[]{}"\'—–-/\\|0123456789'


class Sentence(NamedTuple):
    """One sentence, with the rank of the rarest word in it."""

    words: Tuple[str, ...]
    #: Rank of the rarest word. The ladder's exposure axis, the same
    #: one the crossword and the Scrabble rack are graded on.
    hardest: int

    @property
    def text(self) -> str:
        return ' '.join(self.words)

    def __len__(self) -> int:
        return len(self.words)


# --- reading an article ---------------------------------------------------


def pieces(text: str):
    """Every candidate sentence in one article's markdown."""
    for block in text.split('\n'):
        block = block.strip()
        if not block or block[0] in '#|*->':
            continue
        block = MARKUP.sub('', block)
        for piece in BREAK.split(block):
            piece = piece.strip()
            if piece:
                yield piece


def usable(piece: str, known: Dict[str, int],
           span: Tuple[int, int] = WORDS,
           top_rank: int = TOP_RANK) -> Optional[Tuple[str, ...]]:
    """*piece* as a tuple of lowercase words, or ``None`` if it is not one.

    The lowercase test is done on the original: a word capitalised
    anywhere but the first position is a proper noun, and a scrambled
    proper noun is not a puzzle, it is a lottery.
    """
    if not piece.endswith('.'):
        return None
    body = piece[:-1]
    if any(character in body for character in REFUSED):
        return None
    words = body.split()
    if not span[0] <= len(words) <= span[1]:
        return None
    kept: List[str] = []
    for position, word in enumerate(words):
        if position == 0:
            word = word[:1].lower() + word[1:]
        if not PLAIN.match(word) or len(word) > 12:
            return None
        if known.get(word, 1 << 30) > top_rank:
            return None
        kept.append(word)
    return tuple(kept)


# --- the bank on disk -----------------------------------------------------


def bank_path() -> str:
    return os.path.join(words_dir(), _BANK)


def have() -> bool:
    """Whether a fetched bank is on disk with something in it."""
    path = bank_path()
    return os.path.exists(path) and os.path.getsize(path) > 4096


def can_fetch() -> bool:
    """Whether the parquet reader is installed."""
    try:
        return importlib.util.find_spec('pyarrow.parquet') is not None
    except (ImportError, ValueError):
        return False


def missing_message() -> str:
    """What to tell a player who has no sentences."""
    if not index_ready():
        return ('Scramble is on its seed sentences — for the whole word '
                'list run python -m neural_workshop.wordlist')
    if not can_fetch():
        return ('Scramble is on its seed sentences — reading %s needs '
                'pyarrow installed' % REPO)
    return ('Scramble is on its seed sentences — for %s (%s, %d MB) run '
            'python -m neural_workshop.sentences'
            % (REPO, LICENCE, BYTES // 1_000_000))


# --- fetching -------------------------------------------------------------


class _Ranged(io.RawIOBase):
    """A read-only file that lives on a web server.

    Parquet is laid out to be read this way — a footer that says where
    everything is, then column chunks that can be fetched one at a
    time — so a reader that can seek turns a 439 MB file into the 46
    MB of it we actually want.
    """

    def __init__(self, url: str, size: int) -> None:
        self.url, self.size, self.pos, self.got = url, size, 0, 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        self.pos = (offset if whence == os.SEEK_SET
                    else self.pos + offset if whence == os.SEEK_CUR
                    else self.size + offset)
        return self.pos

    def readinto(self, target) -> int:      # type: ignore[override]
        wanted = min(len(target), self.size - self.pos)
        if wanted <= 0:
            return 0
        ask = urllib.request.Request(self.url, headers={
            'Range': 'bytes=%d-%d' % (self.pos, self.pos + wanted - 1)})
        with urllib.request.urlopen(ask, timeout=_TIMEOUT) as answer:
            data = answer.read()
        target[:len(data)] = data
        self.pos += len(data)
        self.got += len(data)
        return len(data)


def _size_of(url: str) -> int:
    ask = urllib.request.Request(url, method='HEAD')
    with urllib.request.urlopen(ask, timeout=_TIMEOUT) as answer:
        return int(answer.headers['Content-Length'])


def fetch(progress: Optional[Callable[[int, int], None]] = None,
          target: int = TARGET) -> int:
    """Distil up to *target* sentences into the bank. Returns how many.

    Zero means it could not: no word list, no ``pyarrow``, or nothing
    on the other end. Each of those is a different message and
    :func:`missing_message` is where they are told apart.
    """
    if not index_ready() or not can_fetch():
        return 0
    import pyarrow as pa
    import pyarrow.parquet as pq

    known = {entry.word: entry.rank for entry in pool().entries}
    try:
        source = _Ranged(PARQUET, _size_of(PARQUET))
        table = pq.ParquetFile(
            pa.PythonFile(io.BufferedReader(source, buffer_size=_CHUNK)))
        batches = table.iter_batches(batch_size=400,
                                     columns=['content_no_link'],
                                     row_groups=[GROUP])
        seen: set = set()
        kept: List[str] = []
        for batch in batches:
            for body in batch.column('content_no_link').to_pylist():
                for piece in pieces(body or ''):
                    words = usable(piece, known)
                    if words is None:
                        continue
                    line = ' '.join(words)
                    if line not in seen:
                        seen.add(line)
                        kept.append(line)
            if progress is not None:
                progress(len(kept), target)
            if len(kept) >= target:
                break
    except (urllib.error.URLError, OSError, ValueError):
        return 0
    if not kept:
        return 0
    part = bank_path() + '.part'
    with open(part, 'w', encoding='utf-8') as out:
        out.write('\n'.join(kept) + '\n')
    os.replace(part, bank_path())
    forget()
    return len(kept)


# --- what the game reads --------------------------------------------------


#: Written here so that the task runs and the tests mean something with
#: nothing fetched. Short ones first, because the low rungs want short
#: sentences and a rung with one sentence in it is a rung that deals
#: the same puzzle every time.
SEED_TEXT = (
    'the black horse walked along the road',
    'a cat and a dog sat under the tree',
    'the river runs south through the green field',
    'she read the book for three hours',
    'the king had a long white beard',
    'we found a small stone house near the wood',
    'the child came home before the rain',
    'his brother works in a shop on the street',
    'the sun goes down behind the hill',
    'they built a bridge over the water',
    'a bird sang in the tree outside her window',
    'the doctor said that he should rest',
    'the wind was cold and the snow fell',
    'my friend wrote a long letter to his family',
    'the girl kept the key in her hand',
    'the fire burned in the room until morning',
    'the boat came into the town from the sea',
    'each part of the work took an hour',
    'the paper on the table had his name on it',
    'they walked through the garden to the door',
    'the horse and the cow stood in the field',
    'the young girl learned to read',
    'a white bird flew over the water',
    'the price of the land went up again',
    'he took the money out of his pocket',
    'the story of the town is very old',
    'the sheep were kept behind a stone wall',
    'she gave the letter to the man at the door',
    'the tree by the river lost all its leaves',
    'the school stands between the church and the market',
    'the food was good and the room was warm',
    'his voice was quiet but every word was clear',
    'the road turns left before it reaches the sea',
    'the little boy was afraid of the dark',
    'they sat by the fire and told stories',
    'the light of the moon fell across the floor',
    'the woman put the bread on the table',
    'a red flower grew between the grey stones',
    'the men worked in the field until dark',
    'we saw many people on the city street',
    'the young man became a doctor',
    'the wolf came down from the hills in winter',
    'she held the small bird in both hands',
    'the paper said that the war was over',
    'the water in the river was cold and clear',
    'he could not find the right word for it',
    'the house had a red roof and a green door',
    'the old book was full of pictures',
    'they left the city early in the morning',
    'the dog ran across the grass to the water',
    'her father was a farmer in the north',
    'the sound of music came from the window',
    'the wall of the church is made of stone',
    'a long line of people stood outside the shop',
    'the ice on the water was thick',
    'he asked the same question three times',
    'the leaves of the tree turned brown',
    'the queen sat still and said nothing',
    'the train left the station on time',
    'a heavy rain fell on the town all night',
    'the man carried the box up the stairs',
    'the old woman gave her name to the young man',
    'the boy put his hand on the cold glass',
    'there was a light in the window of the house',
    'the ship went down near the coast',
    'she opened the door and looked outside',
    'the horse would not cross the bridge',
    'they gave the child a book about birds',
    'the grass in the field was wet with rain',
    'his father built the house with his hands',
)

_LOADED: Optional[Tuple[Sentence, ...]] = None
_RANKS: Optional[Dict[str, int]] = None
_BUCKETS: Dict[Tuple[int, int, int], Tuple[Sentence, ...]] = {}
_VOCAB: Dict[int, Tuple[str, ...]] = {}


def ranks() -> Dict[str, int]:
    """Every word the task may consider, and how common it is.

    One place decides what words exist, because two would drift and
    the drift would be silent: a sentence graded against a vocabulary
    that does not hold its own words is a sentence no rung will ever
    deal, and nothing would say so.

    With the frequency list built this is that list. Without it, it is
    :data:`neural_workshop.wordlist.SEED` — which is a word list for
    Scrabble and so carries no ``a``, ``of``, ``to`` or ``is`` — with
    the words of :data:`SEED_TEXT` appended behind it. Offline, in
    other words, the vocabulary *is* the seed text, which makes the
    task easy rather than broken, and the screen says which one it has.
    """
    global _RANKS
    if _RANKS is None:
        known = {entry.word: entry.rank for entry in pool().entries}
        if not index_ready():
            following = len(known) + 1
            for line in SEED_TEXT:
                for word in line.split():
                    if word not in known:
                        known[word] = following
                        following += 1
        _RANKS = known
    return _RANKS


def vocabulary(top_rank: int) -> Tuple[str, ...]:
    """Words of rank *top_rank* or better, commonest first.

    This is what a solver may draw from, and it is the same list the
    sentences were filtered against.
    """
    if top_rank not in _VOCAB:
        got = sorted(((rank, word) for word, rank in ranks().items()
                      if rank <= top_rank))
        _VOCAB[top_rank] = tuple(word for _rank, word in got)
    return _VOCAB[top_rank]


def _graded(lines: Sequence[str]) -> Tuple[Sentence, ...]:
    known = ranks()
    made: List[Sentence] = []
    for line in lines:
        words = tuple(line.split())
        if words:
            made.append(Sentence(words, max(known.get(word, 1 << 30)
                                            for word in words)))
    return tuple(made)


def bank() -> Tuple[Sentence, ...]:
    """Every sentence available, fetched if there are any, seed if not."""
    global _LOADED
    if _LOADED is None:
        if have():
            with open(bank_path(), encoding='utf-8') as source:
                _LOADED = _graded([line.strip() for line in source
                                   if line.strip()])
        else:
            _LOADED = _graded(SEED_TEXT)
    return _LOADED


def choose(span: Tuple[int, int], top_rank: int) -> Tuple[Sentence, ...]:
    """Every sentence of a length in *span* whose rarest word fits.

    Cached, because a rung asks for the same band on every trial and
    walking forty thousand sentences a deal is a visible pause.
    """
    key = (span[0], span[1], top_rank)
    if key not in _BUCKETS:
        _BUCKETS[key] = tuple(
            one for one in bank()
            if span[0] <= len(one) <= span[1] and one.hardest <= top_rank)
    return _BUCKETS[key]


def forget() -> None:
    """Drop the cached bank. For the tests, and after a fetch."""
    global _LOADED, _RANKS
    _LOADED = None
    _RANKS = None
    _BUCKETS.clear()
    _VOCAB.clear()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python -m neural_workshop.sentences`` — fetch and distil."""
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    target = int(argv[0]) if argv and argv[0].isdigit() else TARGET
    if not index_ready():
        print('The word list is not built yet. Run '
              'python -m neural_workshop.wordlist first.')
        return 1
    if not can_fetch():
        print('Reading %s needs pyarrow, which the Workshop does not '
              'otherwise use:\n    pip install pyarrow' % REPO)
        return 1
    print('Reading one row group of %s (%s), about %d MB.'
          % (REPO, LICENCE, BYTES // 1_000_000))

    def report(got: int, want: int) -> None:
        print('  %d/%d' % (got, want), end='\r', flush=True)

    got = fetch(report, target)
    print()
    if not got:
        print('Nothing came back. The seed sentences still work.')
        return 1
    print('%d sentences in %s' % (got, bank_path()))
    return 0


__all__ = ['BYTES', 'GROUP', 'LICENCE', 'PARQUET', 'REPO', 'SEED_TEXT',
           'Sentence', 'TARGET', 'TOP_RANK', 'WORDS', 'bank', 'bank_path',
           'can_fetch', 'choose', 'fetch', 'forget', 'have', 'main',
           'missing_message', 'pieces', 'ranks', 'usable', 'vocabulary']


if __name__ == '__main__':
    raise SystemExit(main())
