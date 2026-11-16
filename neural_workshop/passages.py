# -*- coding: utf-8 -*-
"""Short passages of plain English, sentences in their own order.

The Proofreader shuffles the sentences of a passage, so it needs what
:mod:`neural_workshop.sentences` throws away: which sentence came after
which. This keeps runs of two to six sentences that stood one after
another in the same paragraph of a Simple English Wikipedia article
(``juno-labs/simple_wikipedia``, CC BY-SA 3.0), read the same way and
from the same row group as the sentence bank.

A sentence is kept on the same terms as there with two differences:
names are allowed (a passage about a river names the river, and a name
is a clue to order, not a word anyone is asked to unscramble), and it
may be four to sixteen words. Nothing in it but letters and a full
stop at the end. Names are marked by their capital; the Proofreader
never corrupts a capitalised word but the first.

    python -m neural_workshop.passages

Without that there is :data:`SEED`: passages written here, plain
enough to need no word list.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import re
import urllib.error
from typing import List, Optional, Sequence, Tuple

from . import sentences as S
from .wordlist import index_ready, pool, words_dir

_BANK = 'passages.txt'
#: Sentence lengths kept, and how many sentences a passage may have.
WORDS = (4, 16)
RUN = (2, 6)
TARGET = 20000
WORD = re.compile(r'^[A-Za-z]+$')

Passage = Tuple[Tuple[str, ...], ...]

SEED: Tuple[str, ...] = (
    'The farmer got up before the sun. He fed the hens and milked the '
    'cow. Then he sat down to eat his breakfast.',
    'It began to rain in the afternoon. The children ran inside to keep '
    'dry. They played cards until the sky cleared.',
    'A small bird built a nest in the old tree. She laid three blue eggs '
    'in it. A few weeks later the chicks hatched.',
    'The baker mixes flour and water in a large bowl. He leaves the dough '
    'to rise for an hour. Then he shapes it and bakes it in the oven.',
    'Water boils when it gets hot enough. The steam rises from the pot. '
    'When the steam cools it turns back into water.',
    'The library opens at nine in the morning. People come to read and '
    'to borrow books. It closes again at six in the evening.',
    'Ice forms on the lake in the winter. When it is thick enough people '
    'skate on it. In the spring the ice melts and the boats come back.',
    'The cat sat by the door all morning. She was waiting for her owner '
    'to come home. When the door opened she ran to meet him.',
    'Plants need light to grow. They use it to make food from water and '
    'air. Without light most plants turn yellow and die.',
    'The train left the station on time. It stopped at four small towns '
    'on the way. Two hours later it reached the city.',
    'My grandmother keeps a garden behind her house. She grows beans and '
    'tomatoes there. Every summer she gives the extra food to her '
    'neighbours.',
    'The bridge was built over the river many years ago. At first only '
    'people on foot could use it. Later it was made wider for cars.',
    'A doctor listens to the heart of a patient. If the beat is strange '
    'she asks more questions. Sometimes she sends the patient for more '
    'tests.',
    'Bees fly from flower to flower in the summer. They collect a sweet '
    'liquid called nectar. Back at the hive they turn it into honey.',
    'The storm knocked down many trees in the night. In the morning the '
    'roads were closed. Workers spent the whole day clearing them.',
    'Tom wanted to learn to play the piano. He practised for an hour '
    'every day. After a year he could play his favourite song.',
    'The moon goes around the earth about once a month. It has no light '
    'of its own. We see it because it reflects the light of the sun.',
    'The shop sells fresh fruit and bread. Most people buy their food '
    'there on the way home from work. On Sundays the shop is closed.',
    'A fire needs heat and fuel and air. If one of them is taken away the '
    'fire goes out. That is why water can stop a fire.',
    'The children planted a tree at the school. They watered it every '
    'week. Ten years later it gave shade to the whole yard.',
    'Our team lost the first game of the season. The coach made us train '
    'harder. We won every game after that.',
    'Fish breathe through gills on the sides of their heads. Water flows '
    'in through the mouth. The gills take the air out of the water.',
    'The old man walked slowly up the hill. At the top he sat on a bench. '
    'From there he could see the whole town.',
    'Snow fell all night and covered the road. In the morning the bus '
    'could not get through. The school was closed for the day.',
    'The museum has a large collection of old coins. Some of them are more '
    'than two thousand years old. Visitors can look at them through '
    'glass.',
    'A spider spins a web to catch insects. The threads are thin but very '
    'strong. When an insect gets stuck the spider wraps it in silk.',
    'She opened the letter with shaking hands. It said that she had got '
    'the job. She called her mother to tell her the news.',
    'The river flows down from the mountains. It passes through farms and '
    'small villages. At last it reaches the sea.',
)


def bank_path() -> str:
    return os.path.join(words_dir(), _BANK)


def have() -> bool:
    path = bank_path()
    return os.path.exists(path) and os.path.getsize(path) > 4096


def split(text: str) -> Passage:
    """A passage as sentences of words, full stops dropped."""
    out = []
    for piece in S.BREAK.split(text.strip()):
        piece = piece.strip().rstrip('.')
        if piece:
            out.append(tuple(piece.split()))
    return tuple(out)


def keep(piece: str, known) -> Optional[Tuple[str, ...]]:
    """*piece* as words, or None: letters only, a full stop at the end,
    every word known or a name."""
    if not piece.endswith('.'):
        return None
    words = piece[:-1].split()
    if not WORDS[0] <= len(words) <= WORDS[1]:
        return None
    for k, w in enumerate(words):
        if not WORD.match(w) or len(w) > 13:
            return None
        low = w.lower() if k == 0 else w
        if low[:1].islower() and known.get(low, 1 << 30) > S.TOP_RANK:
            return None
    return tuple(words)


def fetch(target: int = TARGET) -> int:
    """Distil passages into the bank. Returns how many."""
    if not index_ready() or not S.can_fetch():
        return 0
    import io
    import pyarrow as pa
    import pyarrow.parquet as pq
    known = {entry.word: entry.rank for entry in pool().entries}
    kept: List[str] = []
    try:
        source = S._Ranged(S.PARQUET, S._size_of(S.PARQUET))
        table = pq.ParquetFile(
            pa.PythonFile(io.BufferedReader(source, buffer_size=S._CHUNK)))
        for batch in table.iter_batches(batch_size=400,
                                        columns=['content_no_link'],
                                        row_groups=[S.GROUP]):
            for body in batch.column('content_no_link').to_pylist():
                for block in (body or '').split('\n'):
                    block = S.MARKUP.sub('', block.strip())
                    if not block or block[0] in '#|*->':
                        continue
                    run: List[str] = []
                    for piece in S.BREAK.split(block) + ['']:
                        words = keep(piece.strip(), known) if piece else None
                        if words is not None and len(run) < RUN[1]:
                            run.append(' '.join(words) + '.')
                            continue
                        if len(run) >= RUN[0]:
                            kept.append(' '.join(run))
                        run = [' '.join(words) + '.'] if words else []
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


_LOADED: Optional[Tuple[Passage, ...]] = None


def bank() -> Tuple[Passage, ...]:
    """Every passage there is: fetched, or the seed ones."""
    global _LOADED
    if _LOADED is None:
        lines: Sequence[str] = SEED
        if have():
            with open(bank_path(), encoding='utf-8') as source:
                lines = [line.strip() for line in source if line.strip()]
        _LOADED = tuple(split(line) for line in lines)
    return _LOADED


def forget() -> None:
    global _LOADED
    _LOADED = None


def main(argv: Optional[Sequence[str]] = None) -> int:
    got = fetch()
    if not got:
        print('Nothing fetched: ' + S.missing_message())
        return 1
    print('%d passages in %s' % (got, bank_path()))
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
