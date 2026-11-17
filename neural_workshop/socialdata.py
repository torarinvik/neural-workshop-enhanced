# -*- coding: utf-8 -*-
"""What the Social, Rationality and verbal tasks read: questions with
known answers, and voices.

Three public sources, each fetched once into the user's data directory
when asked (``python -m neural_workshop.socialdata``) and never bundled:

* **bigbench** -- BIG-bench (``tasksource/bigbench`` on Hugging Face,
  Apache 2.0): what a reply implies, which remark is sarcastic, which
  sentence is ironic, what a metaphor says in plain words, the figure
  of speech a sentence uses, the moral of a fable, the odd metaphor out,
  and whether an argument is valid;
* **social** -- Social IQa (AI2, ``socialiqa-train-dev.zip``): a short
  everyday situation and a question about why someone did it, how they
  or others feel, what they need or will want next;
* **voices** -- CREMA-D (``CheyneyComputerScience/CREMA-D`` on GitHub,
  Open Database License): 91 actors saying twelve sentences in six
  emotions, each clip rated by listeners who only heard it. Only clips
  the listeners heard as the emotion the actor meant are kept, with how
  many of them agreed.

Without them each task still runs on a handful of questions written
here; Tone of Voice then has no voices and says so.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import csv
import functools
import io
import json
import os
import random
import re
import urllib.request
import zipfile
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .paths import get_data_dir

BIG_REPO = 'tasksource/bigbench'
SIQA_ZIP = ('https://storage.googleapis.com/ai2-mosaic/public/socialiqa/'
            'socialiqa-train-dev.zip')
CREMA = ('https://media.githubusercontent.com/media/CheyneyComputerScience/'
         'CREMA-D/master/')          # the clips, kept in Git LFS
CREMA_RAW = ('https://raw.githubusercontent.com/CheyneyComputerScience/'
             'CREMA-D/master/')      # the tables
#: CREMA-D's emotions, in its own letters.
VOICES = (('A', 'ANG', 'anger'), ('D', 'DIS', 'disgust'),
          ('F', 'FEA', 'fear'), ('H', 'HAP', 'happiness'),
          ('N', 'NEU', 'neutral'), ('S', 'SAD', 'sadness'))
#: The sentences the actors say.
SENTENCES = {
    'IEO': "It's eleven o'clock", 'TIE': "That is exactly what happened",
    'IOM': "I'm on my way to the meeting",
    'IWW': "I wonder what this is about",
    'TAI': "The airplane is almost full", 'MTI': "Maybe tomorrow it will be cold",
    'IWL': "I would like a new alarm clock",
    'ITH': "I think I have a doctor's appointment",
    'DFA': "Don't forget a jacket",
    'ITS': "I think I've seen this before",
    'TSI': "The surface is slick", 'WSI': "We'll stop in a couple of minutes",
}
PER_VOICE = 330                 # clips kept of each emotion, at most
_HEADERS = {'User-Agent': 'neural-workshop'}


def home() -> str:
    path = os.path.join(get_data_dir(), 'datasets', 'social')
    os.makedirs(path, exist_ok=True)
    return path


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _rows(repo: str, config: str, split: str, most: int = 100000
          ) -> List[dict]:
    out, offset = [], 0
    while offset < most:
        try:
            page = json.loads(_get(
                'https://datasets-server.huggingface.co/rows?dataset=%s'
                '&config=%s&split=%s&offset=%d&length=100' % (
                    repo, config, split, offset)))
        except OSError:
            return out
        rows = [r['row'] for r in page.get('rows', [])]
        out.extend(rows)
        offset += len(rows)
        if not rows or offset >= page.get('num_rows_total', 0):
            break
    return out


# --- questions ------------------------------------------------------------------

class Question(NamedTuple):
    kind: str                      # see KINDS
    prompt: str                    # what is read
    ask: str                       # the question under it
    options: Tuple[str, ...]
    answer: int


#: Every kind of question, and where it comes from.
KINDS = ('implicature', 'sarcasm', 'irony', 'metaphor', 'figure', 'fable',
         'odd_metaphor', 'fallacy', 'formal', 'social')

#: The BIG-bench subsets, the kind each becomes, and how many rows to
#: take of each split at most.
BIG = (('implicatures', 'implicature', 2000),
       ('snarks', 'sarcasm', 2000),
       ('irony_identification', 'irony', 2000),
       ('metaphor_understanding', 'metaphor', 2000),
       ('figure_of_speech_detection', 'figure', 2000),
       ('understanding_fables', 'fable', 2000),
       ('identify_odd_metaphor', 'odd_metaphor', 2000),
       ('logical_fallacy_detection', 'fallacy', 2400),
       ('formal_fallacies_syllogisms_negation', 'formal', 1500))


def _quote(s: str) -> str:
    return '\u201c%s\u201d' % s.strip()


def _middles(texts: Sequence[str]) -> Tuple[List[str], str, str]:
    """The words where *texts* differ, and the words they all share
    before and after."""
    split = [t.split() for t in texts]
    i = 0
    while all(len(w) > i for w in split) and \
            len({w[i] for w in split}) == 1:
        i += 1
    j = 0
    while all(len(w) > i + j for w in split) and \
            len({w[len(w) - 1 - j] for w in split}) == 1:
        j += 1
    mids = [' '.join(w[i:len(w) - j]) for w in split]
    return mids, ' '.join(split[0][:i]), ' '.join(split[0][len(split[0]) - j:])


def parse_big(kind: str, row: dict) -> Optional[Question]:
    """One BIG-bench row as a :class:`Question`, or ``None``."""
    text = row.get('inputs') or ''
    opts = tuple(o.strip() for o in row.get('multiple_choice_targets') or ())
    scores = list(row.get('multiple_choice_scores') or ())
    if not opts or scores.count(1) != 1:
        return None
    answer = scores.index(1)
    if kind == 'implicature':
        m = re.search(r"Speaker 1: '(.*)' Speaker 2: '(.*)'", text, re.S)
        if not m:
            return None
        return Question(kind, 'A: %s\nB: %s' % (_quote(m.group(1)),
                                                 _quote(m.group(2))),
                        'Does B mean yes or no?', opts, answer)
    if kind == 'sarcasm':
        m = re.search(r'\(a\)\s*(.*?)\s*\(b\)\s*(.*?)\s*(?:A:\s*)?$', text,
                      re.S)
        if not m or opts != ('(a)', '(b)'):
            return None
        return Question(kind, '1.  %s\n\n2.  %s' % (m.group(1).strip(),
                                                    m.group(2).strip()),
                        'Which one is sarcastic?',
                        ('the first', 'the second'), answer)
    if kind == 'irony':
        m = re.search(r'Example:\s*(.*?)\s*Ironic/Not ironic', text, re.S)
        if not m:
            return None
        return Question(kind, m.group(1), 'Ironic or not?', opts, answer)
    if kind == 'metaphor':
        m = re.search(r'Q:\s*(.*?)\s*option:', text, re.S)
        if not m:
            return None
        mids, head, tail = _middles(opts)
        if not all(mids) or max(len(x) for x in mids) > 44 or \
                len(set(mids)) != len(opts) or not (head or tail):
            return None
        plain = ' '.join(x for x in (head, '___', tail) if x)
        return Question(kind, '%s\n\nIn plain words:\n%s' % (
            m.group(1), plain), 'What fills the gap?', tuple(mids), answer)
    if kind == 'figure':
        m = re.search(r'Sentence:\s*(.*?)\s*Figure of speech', text, re.S)
        if not m:
            return None
        return Question(kind, m.group(1), 'Which figure of speech is it?',
                        opts, answer)
    if kind == 'fable':
        m = re.search(r'Q:\s*(.*?)\s*What is the moral of this story\?',
                      text, re.S)
        if not m or max(len(o) for o in opts) > 90:
            return None
        return Question(kind, m.group(1), 'What is the moral?', opts, answer)
    if kind == 'odd_metaphor':
        m = re.search(r'Q:\s*(.*?)\n', text)
        if not m or max(len(o) for o in opts) > 60:
            return None
        q = m.group(1).replace('Which of the following sentences', 'Which')
        return Question(kind, q, 'Which one is it?', opts, answer)
    if kind == 'fallacy':
        m = re.search(r"'Invalid'\?\s*(.*?)\s*A:\s*$", text, re.S)
        if not m:
            return None
        return Question(kind, m.group(1), 'Does the conclusion follow?',
                        ('valid', 'invalid'),
                        ('valid', 'invalid').index(opts[answer].lower()))
    if kind == 'formal':
        m = re.search(r'Q:\s*"(.*)"\s*Is the argument', text, re.S)
        if not m:
            return None
        body = m.group(1)
        lead = re.search(r'(?:pertains to this question|valid argument)'
                         r'\s*:\s*', body)
        if lead:
            body = body[lead.end():]
        return Question(kind, body, 'Does the conclusion follow?',
                        ('valid', 'invalid'),
                        ('valid', 'invalid').index(opts[answer].lower()))
    return None


#: Social IQa's questions, by what they ask.
SOCIAL_KINDS = (
    ('describe', r'^How would you describe'),
    ('feel', r'^How would (?!others)\w+ feel'),
    ('others_feel', r'^How would others feel'),
    ('want', r'want to do next'),
    ('need', r'need to do before'),
    ('why', r'^Why did'),
    ('happens', r'^What will happen to'),
    ('next', r'^What will (?!happen)'),
)


def social_kind(question: str) -> str:
    for name, pattern in SOCIAL_KINDS:
        if re.search(pattern, question, re.I):
            return name
    return 'other'


def questions_path() -> str:
    return os.path.join(home(), 'questions.jsonl')


def _save(qs: Sequence[Question], keep_kinds: Sequence[str]) -> None:
    """Rewrite the question file: *qs* replace the kinds they are of."""
    old = [q for q in _load() if q.kind.split(':')[0] not in keep_kinds]
    with open(questions_path(), 'w', encoding='utf-8') as fh:
        for q in old + list(qs):
            fh.write(json.dumps(q._asdict()) + '\n')
    questions.cache_clear()


def _parquet(repo: str, config: str, split: str, most: int) -> List[dict]:
    """The rows of one split, read from its parquet files: one request
    a file, where the row API would take one a hundred rows."""
    import pyarrow.parquet as pq
    listing = json.loads(_get('https://datasets-server.huggingface.co/'
                              'parquet?dataset=%s&config=%s' % (repo, config)))
    out: List[dict] = []
    for f in listing.get('parquet_files', []):
        if f.get('split') != split or len(out) >= most:
            continue
        table = pq.read_table(io.BytesIO(_get(f['url'], timeout=300)))
        out.extend(table.to_pylist()[:most - len(out)])
    return out


def fetch_bigbench(progress=print) -> int:
    got: List[Question] = []
    for config, kind, most in BIG:
        n = 0
        for split in ('train', 'validation'):
            for row in _parquet(BIG_REPO, config, split, most):
                q = parse_big(kind, row)
                if q is not None:
                    got.append(q)
                    n += 1
        progress('bigbench: %s %d kept' % (config, n))
    _save(got, [k for _c, k, _m in BIG])
    return len(got)


def fetch_social(progress=print) -> int:
    data = zipfile.ZipFile(io.BytesIO(_get(SIQA_ZIP, timeout=300)))
    got = []
    for split in ('train', 'dev'):
        rows = data.read('socialiqa-train-dev/%s.jsonl' % split
                         ).decode().splitlines()
        labels = data.read('socialiqa-train-dev/%s-labels.lst' % split
                           ).decode().split()
        for line, lab in zip(rows, labels):
            r = json.loads(line)
            opts = (r['answerA'].strip(), r['answerB'].strip(),
                    r['answerC'].strip())
            if len(set(o.lower() for o in opts)) < 3 or \
                    max(len(o) for o in opts) > 70:
                continue
            q = r['question'].strip()
            got.append(Question('social:' + social_kind(q),
                                r['context'].strip(), q, opts,
                                int(lab) - 1))
    _save(got, ['social'])
    progress('social: %d kept' % len(got))
    return len(got)


SEED = (
    Question('implicature', 'A: \u201cAre you coming to the party?\u201d\n'
             'B: \u201cI have an exam at eight the next morning.\u201d',
             'Does B mean yes or no?', ('yes', 'no'), 1),
    Question('implicature', 'A: \u201cDid you like the soup?\u201d\n'
             'B: \u201cI had a second bowl.\u201d',
             'Does B mean yes or no?', ('yes', 'no'), 0),
    Question('implicature', 'A: \u201cIs the shop still open?\u201d\n'
             'B: \u201cThe lights went off an hour ago.\u201d',
             'Does B mean yes or no?', ('yes', 'no'), 1),
    Question('implicature', 'A: \u201cCan you help me move on Saturday?\u201d\n'
             'B: \u201cI\u2019ll bring my van.\u201d',
             'Does B mean yes or no?', ('yes', 'no'), 0),
    Question('sarcasm', '1.  Great, another meeting that could have been '
             'an email. Just what I needed.\n\n2.  Great, the meeting was '
             'short and we decided everything we needed.',
             'Which one is sarcastic?', ('the first', 'the second'), 0),
    Question('sarcasm', '1.  I love it when the train is on time.\n\n'
             '2.  I just love standing on a cold platform for an hour.',
             'Which one is sarcastic?', ('the first', 'the second'), 1),
    Question('irony', 'The fire station burned down last night.',
             'Ironic or not?', ('ironic', 'not ironic'), 0),
    Question('irony', 'The bakery sold out of bread by noon.',
             'Ironic or not?', ('ironic', 'not ironic'), 1),
    Question('metaphor', 'Her words [cut him to the bone] and he left.',
             'What do the words in brackets mean here?',
             ('hurt him deeply', 'made him bleed', 'cooked for him',
              'measured him'), 0),
    Question('metaphor', 'The news [spread like wildfire] through town.',
             'What do the words in brackets mean here?',
             ('burned houses', 'travelled very fast', 'was hot',
              'stayed secret'), 1),
    Question('figure', 'The wind whispered through the trees.',
             'Which figure of speech is it?',
             ('Simile', 'Metaphor', 'Personification', 'Hyperbole'), 2),
    Question('figure', 'I have told you a million times.',
             'Which figure of speech is it?',
             ('Simile', 'Metaphor', 'Personification', 'Hyperbole'), 3),
    Question('figure', 'He runs like the wind.',
             'Which figure of speech is it?',
             ('Simile', 'Metaphor', 'Personification', 'Hyperbole'), 0),
    Question('fable', 'A crow found a pitcher with a little water at the '
             'bottom. It could not reach it, so it dropped pebbles in, one '
             'by one, until the water rose and it could drink.',
             'What is the moral?',
             ('Little by little does the trick.',
              'Look before you leap.',
              'Pride goes before a fall.',
              'Birds of a feather flock together.'), 0),
    Question('fable', 'A fox could not reach the grapes on a high vine. '
             'Walking away, it said they were surely sour anyway.',
             'What is the moral?',
             ('Slow and steady wins the race.',
              'It is easy to despise what you cannot have.',
              'A friend in need is a friend indeed.',
              'Do not count your chickens before they hatch.'), 1),
    Question('odd_metaphor', 'Which sentence about ideas does not speak '
             'of them as food?',
             'Which one is it?', ('That is food for thought.',
                                  'I cannot swallow that claim.',
                                  'Let me chew on it.',
                                  'The idea came in a flash.'), 3),
    Question('fallacy', 'All dogs are animals. Rex is a dog. Therefore Rex '
             'is an animal.', 'Does the conclusion follow?',
             ('valid', 'invalid'), 0),
    Question('fallacy', 'All dogs are animals. Tom is an animal. Therefore '
             'Tom is a dog.', 'Does the conclusion follow?',
             ('valid', 'invalid'), 1),
    Question('social:feel', 'Sam forgot his best friend\u2019s birthday and '
             'only remembered the day after.',
             'How would Sam feel afterwards?',
             ('guilty', 'proud', 'bored'), 0),
    Question('social:why', 'Sam forgot his best friend\u2019s birthday and '
             'only remembered the day after.',
             'What will Sam want to do next?',
             ('apologise to his friend', 'throw a party for himself',
              'forget it again'), 0),
    Question('social:need', 'Ana held the door open for the man carrying '
             'two heavy boxes.', 'What does Ana need to do before this?',
             ('see the man coming', 'carry the boxes', 'lock the door'), 0),
    Question('social:why', 'Ana held the door open for the man carrying '
             'two heavy boxes.', 'Why did Ana do this?',
             ('to be helpful', 'to keep him out', 'to cool the room'), 0),
    Question('social:want', 'Lee finished cooking a large dinner for the '
             'family.', 'What will Lee want to do next?',
             ('call everyone to the table', 'start cooking dinner',
              'buy the groceries'), 0),
    Question('social:need', 'Kim drove to the beach for the weekend.',
             'What does Kim need to do before this?',
             ('pack a bag', 'swim in the sea', 'drive home'), 0),
    Question('social:others_feel', 'Jo told the whole class the answer '
             'before the teacher could ask anyone.',
             'How would others feel as a result?',
             ('annoyed', 'grateful to Jo', 'sleepy'), 0),
    Question('social:describe', 'Max gave his lunch to a classmate who had '
             'forgotten his.', 'How would you describe Max?',
             ('generous', 'greedy', 'forgetful'), 0),
)


def _load() -> List[Question]:
    if not os.path.exists(questions_path()):
        return []
    out = []
    with open(questions_path(), encoding='utf-8') as fh:
        for line in fh:
            if line.strip():
                d = json.loads(line)
                out.append(Question(d['kind'], d['prompt'], d['ask'],
                                    tuple(d['options']), d['answer']))
    return out


@functools.lru_cache(maxsize=1)
def questions() -> Dict[str, Tuple[Question, ...]]:
    """Every question by kind (``social`` and ``social:<what>`` both);
    the questions written here stand in for any kind not fetched."""
    by: Dict[str, List[Question]] = {}
    for q in _load():
        by.setdefault(q.kind, []).append(q)
    have = {k.split(':')[0] for k in by}
    for q in SEED:
        if q.kind.split(':')[0] not in have:
            by.setdefault(q.kind, []).append(q)
    for k in list(by):
        if ':' in k:
            by.setdefault(k.split(':')[0], []).extend(by[k])
    return {k: tuple(v) for k, v in by.items()}


def of(kind: str) -> Tuple[Question, ...]:
    return questions().get(kind, ())


def fetched(kind: str) -> bool:
    return any(q not in SEED for q in of(kind))


# --- voices (CREMA-D) -------------------------------------------------------------

class Voice(NamedTuple):
    name: str                      # e.g. 1001_DFA_ANG_XX
    emotion: int                   # index into VOICES
    level: str                     # LO, MD, HI or XX (unspecified)
    agreement: float               # share of listeners who heard it so

    @property
    def sentence(self) -> str:
        return SENTENCES.get(self.name.split('_')[1], '')


def voices_dir() -> str:
    return os.path.join(home(), 'voices')


def fetch_voices(progress=print) -> int:
    folder = voices_dir()
    os.makedirs(folder, exist_ok=True)
    letter = {code: k for k, (_l, code, _n) in enumerate(VOICES)}
    votes = csv.DictReader(io.StringIO(_get(
        CREMA_RAW + 'processedResults/tabulatedVotes.csv', timeout=300
    ).decode()))
    clips = []
    for r in votes:
        if not r[''].startswith('1'):         # 1...: heard, not seen
            continue
        name = r['fileName']
        parts = name.split('_')
        if len(parts) != 4 or parts[2] not in letter:
            continue
        k = letter[parts[2]]
        if r['emoVote'] != VOICES[k][0]:
            continue
        clips.append(Voice(name, k, parts[3], float(r['agreement'])))
    draw = random.Random(11)
    draw.shuffle(clips)
    kept: List[Voice] = []
    for k in range(len(VOICES)):
        mine = sorted((c for c in clips if c.emotion == k),
                      key=lambda c: c.level == 'XX')   # levelled ones first
        kept.extend(mine[:PER_VOICE])
    done = []
    for i, c in enumerate(kept):
        path = os.path.join(folder, c.name + '.wav')
        if not os.path.exists(path):
            try:
                data = _get(CREMA + 'AudioWAV/%s.wav' % c.name)
            except OSError:
                continue
            with open(path, 'wb') as fh:
                fh.write(data)
        done.append(c)
        if i % 200 == 0:
            progress('voices: %d of %d' % (i, len(kept)))
    with open(os.path.join(folder, 'voices.tsv'), 'w') as fh:
        for c in done:
            fh.write('%s\t%d\t%s\t%.4f\n' % c)
    voices.cache_clear()
    progress('voices: %d kept' % len(done))
    return len(done)


@functools.lru_cache(maxsize=1)
def voices() -> Tuple[Voice, ...]:
    path = os.path.join(voices_dir(), 'voices.tsv')
    if not os.path.exists(path):
        return ()
    out = []
    with open(path) as fh:
        for line in fh:
            if line.strip():
                n, e, lv, a = line.split('\t')
                if os.path.exists(os.path.join(voices_dir(), n + '.wav')):
                    out.append(Voice(n, int(e), lv, float(a)))
    return tuple(out)


def voice_path(v: Voice) -> str:
    return os.path.join(voices_dir(), v.name + '.wav')


FETCHERS = {'bigbench': fetch_bigbench, 'social': fetch_social,
            'voices': fetch_voices}


def main(argv: Optional[Sequence[str]] = None) -> int:
    import sys
    which = list(argv if argv is not None else sys.argv[1:]) or \
        list(FETCHERS)
    for name in which:
        if name not in FETCHERS:
            print('unknown: %s (one of %s)' % (name, ', '.join(FETCHERS)))
            return 1
        FETCHERS[name]()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
