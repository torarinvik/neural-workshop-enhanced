# -*- coding: utf-8 -*-
"""What the Emotion tasks read: faces, comments, dialogues, stories.

Four public sources, each fetched once into the user's data directory
when asked (``python -m neural_workshop.emotiondata``) and never
bundled:

* **faces** -- FER-2013 (48 by 48 grey photographs of faces, from the
  ICML 2013 representation-learning challenge, as mirrored on Hugging
  Face by ``Aaryan333/fer2013_train_publicTest_privateTest``, which
  keeps the original order) with Microsoft's **FERPlus** labels (MIT):
  ten people voted on each face, so how far they agreed is known and
  the ladder can start on faces nearly everyone read the same way;
* **comments** -- GoEmotions (``google-research-datasets/go_emotions``,
  Apache 2.0): Reddit comments, each with the emotions raters agreed
  on, 27 of them and neutral;
* **dialogues** -- EQ-Bench (``pbevan11/EQ-Bench``, MIT): a dialogue,
  four emotions, and how strongly a character feels each at its end;
* **stories** -- EmoBench (``SahandSab/EmoBench``, MIT): a scenario, the
  emotion its subject feels and why, or the most helpful thing to do.

Without them each task still runs on what is written here: faces drawn
from a few lines, and a handful of comments, dialogues and stories.

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
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .paths import get_data_dir

#: FERPlus's order of emotions.
EMOTIONS = ('neutral', 'happiness', 'surprise', 'sadness', 'anger',
            'disgust', 'fear', 'contempt')
FACE_REPO = 'Aaryan333/fer2013_train_publicTest_privateTest'
FACE_SPLITS = (('train', 0), ('publicTest', 28709), ('privateTest', 32298))
FERPLUS_CSV = ('https://raw.githubusercontent.com/microsoft/FERPlus/'
               'master/fer2013new.csv')
GO_REPO = 'google-research-datasets/go_emotions'
EQ_REPO = 'pbevan11/EQ-Bench'
EMO_REPO = 'SahandSab/EmoBench'
GO_LABELS = ('admiration', 'amusement', 'anger', 'annoyance', 'approval',
             'caring', 'confusion', 'curiosity', 'desire',
             'disappointment', 'disapproval', 'disgust', 'embarrassment',
             'excitement', 'fear', 'gratitude', 'grief', 'joy', 'love',
             'nervousness', 'optimism', 'pride', 'realization', 'relief',
             'remorse', 'sadness', 'surprise', 'neutral')
_HEADERS = {'User-Agent': 'neural-workshop'}


def home() -> str:
    path = os.path.join(get_data_dir(), 'datasets', 'emotion')
    os.makedirs(path, exist_ok=True)
    return path


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _parquet_urls(repo: str, config: str, split: str) -> List[str]:
    got = json.loads(_get('https://datasets-server.huggingface.co/parquet'
                          '?dataset=%s' % repo))
    return [f['url'] for f in got.get('parquet_files', [])
            if f.get('config') == config and f.get('split') == split]


def _rows(repo: str, config: str, split: str) -> List[dict]:
    out, offset = [], 0
    while True:
        page = json.loads(_get(
            'https://datasets-server.huggingface.co/rows?dataset=%s&config=%s'
            '&split=%s&offset=%d&length=100' % (repo, config, split, offset)))
        rows = [r['row'] for r in page.get('rows', [])]
        out.extend(rows)
        offset += len(rows)
        if not rows or offset >= page.get('num_rows_total', 0):
            return out


# --- faces --------------------------------------------------------------------

class Face(NamedTuple):
    key: int                       # FER-2013 row, or -1 for a drawn face
    votes: Tuple[int, ...]         # one count per EMOTIONS
    path: str = ''                 # the photograph, if there is one
    drawn: Tuple[float, ...] = ()  # the parameters of a drawn face

    def total(self) -> int:
        return sum(self.votes)

    def ranked(self) -> List[int]:
        return sorted(range(len(EMOTIONS)), key=lambda k: -self.votes[k])

    def top(self) -> Optional[int]:
        r = self.ranked()
        if self.votes[r[0]] == self.votes[r[1]]:
            return None
        return r[0]

    def agreement(self) -> float:
        return max(self.votes) / max(1, self.total())


def faces_dir() -> str:
    return os.path.join(home(), 'faces')


def fetch_faces(progress=print) -> int:
    import pyarrow.parquet as pq
    folder = faces_dir()
    os.makedirs(folder, exist_ok=True)
    votes = list(csv.reader(io.StringIO(_get(FERPLUS_CSV).decode())))[1:]
    kept = []
    for split, offset in FACE_SPLITS:
        for url in _parquet_urls(FACE_REPO, 'default', split):
            scratch = os.path.join(folder, '_part.parquet')
            with open(scratch, 'wb') as fh:
                fh.write(_get(url, timeout=600))
            table = pq.read_table(scratch, columns=['image'])
            for i, cell in enumerate(table.column('image').to_pylist()):
                row = votes[offset + i]
                v = [int(x) for x in row[2:10]]
                unknown, nf = int(row[10]), int(row[11])
                if nf or unknown > 2 or sum(v) < 6:
                    continue
                key = offset + i
                path = os.path.join(folder, '%05d.png' % key)
                if not os.path.exists(path):
                    with open(path, 'wb') as fh:
                        fh.write(cell['bytes'])
                kept.append('%d\t%s' % (key, ' '.join(map(str, v))))
            os.remove(scratch)
            progress('faces: %s done, %d kept' % (split, len(kept)))
    with open(os.path.join(folder, 'votes.tsv'), 'w') as fh:
        fh.write('\n'.join(kept) + '\n')
    faces.cache_clear()
    return len(kept)


def _drawn_faces() -> List[Face]:
    """Faces drawn from a few lines, for when no photographs have been
    fetched: brows, eyes, mouth, set by the emotion and jittered."""
    draw = random.Random(7)
    shape = {   # brow tilt, brow height, eye open, mouth curve, mouth open, smirk
        'neutral': (0.0, 0.0, 0.5, 0.0, 0.0, 0.0),
        'happiness': (0.0, 0.1, 0.45, 0.9, 0.3, 0.0),
        'surprise': (0.0, 0.9, 1.0, 0.0, 0.9, 0.0),
        'sadness': (-0.7, 0.3, 0.35, -0.8, 0.0, 0.0),
        'anger': (0.9, -0.6, 0.4, -0.2, 0.1, 0.0),
        'disgust': (0.5, -0.4, 0.3, -0.5, 0.2, 0.3),
        'fear': (-0.5, 0.8, 0.95, -0.3, 0.6, 0.0),
        'contempt': (0.2, 0.0, 0.45, 0.2, 0.0, 0.9),
    }
    out = []
    for k, emo in enumerate(EMOTIONS):
        for j in range(30):
            base = shape[emo]
            strength = 0.55 + 0.45 * draw.random()
            params = tuple(b * strength + draw.gauss(0, 0.08) for b in base)
            agree = 0.95 - 0.5 * (1 - strength)
            main = max(4, int(round(10 * agree)))
            v = [0] * len(EMOTIONS)
            v[k] = main
            for _r in range(10 - main):
                other = draw.choice([e for e in range(len(EMOTIONS))
                                     if e != k])
                v[other] += 1
            out.append(Face(-1, tuple(v), '', params))
    return out


@functools.lru_cache(maxsize=1)
def faces() -> Tuple[Face, ...]:
    path = os.path.join(faces_dir(), 'votes.tsv')
    if os.path.exists(path):
        got = []
        with open(path) as fh:
            for line in fh:
                if not line.strip():
                    continue
                key, votes = line.split('\t')
                got.append(Face(int(key), tuple(int(x) for x in
                                                 votes.split()),
                                os.path.join(faces_dir(),
                                             '%05d.png' % int(key))))
        if got:
            return tuple(got)
    return tuple(_drawn_faces())


def photographs() -> bool:
    return bool(faces()) and faces()[0].key >= 0


# --- comments (GoEmotions) ------------------------------------------------------

class Comment(NamedTuple):
    text: str
    label: str


SEED_COMMENTS = (
    ('Thank you so much, this saved my whole afternoon.', 'gratitude'),
    ('I cannot believe they cancelled the show again. Ridiculous.',
     'annoyance'),
    ('Wait, so the butler was the father all along?', 'confusion'),
    ('That is the funniest thing I have read all week.', 'amusement'),
    ('I am so sorry for your loss. Thinking of you.', 'sadness'),
    ('My hands are shaking, the interview is in an hour.', 'nervousness'),
    ('You did an amazing job on that build, seriously.', 'admiration'),
    ('I really wish I had one of those.', 'desire'),
    ('Oh, now I get why the code kept failing.', 'realization'),
    ('Phew, the test came back negative.', 'relief'),
    ('I should never have said that to her.', 'remorse'),
    ('That is disgusting, who eats that?', 'disgust'),
    ('How did they even get the piano up there?', 'curiosity'),
    ('Things will get better next season, I am sure of it.', 'optimism'),
    ('I finished my first marathon today!', 'pride'),
    ('This is a scam and they knew it. Furious.', 'anger'),
    ('I love you guys, best community ever.', 'love'),
    ('That was so embarrassing, I tripped on stage.', 'embarrassment'),
    ('We won the cup!!! I am losing my mind!', 'excitement'),
    ('Honestly that would scare me to death.', 'fear'),
    ('I was hoping for more from the sequel.', 'disappointment'),
    ('I do not think that is fair to the players at all.', 'disapproval'),
    ('Yes, exactly, that is how it should be done.', 'approval'),
    ('Take care of yourself and drink some water.', 'caring'),
    ('So happy for you both!', 'joy'),
    ('Wow, I did not see that ending coming.', 'surprise'),
    ('My dog died this morning. He was fourteen.', 'grief'),
    ('The store opens at nine on weekdays.', 'neutral'),
)


def comments_path() -> str:
    return os.path.join(home(), 'goemotions.tsv')


def fetch_comments(progress=print) -> int:
    import pyarrow.parquet as pq
    out = []
    names = ('Sam', 'Alex', 'Jo', 'Robin', 'Kim', 'Chris', 'Pat', 'Lee')
    draw = random.Random(3)
    for url in _parquet_urls(GO_REPO, 'simplified', 'train'):
        scratch = os.path.join(home(), '_go.parquet')
        with open(scratch, 'wb') as fh:
            fh.write(_get(url, timeout=600))
        t = pq.read_table(scratch, columns=['text', 'labels'])
        for text, labels in zip(t.column('text').to_pylist(),
                                t.column('labels').to_pylist()):
            if len(labels) != 1:
                continue
            words = text.split()
            if not 4 <= len(words) <= 40 or '\t' in text or '\n' in text:
                continue
            text = re.sub(r'\[NAME\]', lambda m: draw.choice(names), text)
            text = text.replace('[RELIGION]', 'religion')
            out.append('%s\t%s' % (GO_LABELS[labels[0]], text))
        os.remove(scratch)
    with open(comments_path(), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')
    comments.cache_clear()
    progress('comments: %d kept' % len(out))
    return len(out)


@functools.lru_cache(maxsize=1)
def comments() -> Tuple[Comment, ...]:
    if os.path.exists(comments_path()):
        with open(comments_path(), encoding='utf-8') as fh:
            got = [Comment(*reversed(line.rstrip('\n').split('\t', 1)))
                   for line in fh if '\t' in line]
        if got:
            return tuple(got)
    return tuple(Comment(t, l) for t, l in SEED_COMMENTS)


# --- dialogues (EQ-Bench) -----------------------------------------------------

class Dialogue(NamedTuple):
    text: str                      # the dialogue
    who: str                       # whose feelings are asked
    emotions: Tuple[str, ...]      # four
    scores: Tuple[int, ...]        # 0-10 each, the reference


SEED_DIALOGUES = (
    Dialogue('Mara: I kept your seat for you all evening.\nTom: I told you '
             'I had to work late.\nMara: You told me after the play had '
             'started.\nTom: I said I was sorry.\nMara: You did. Twice.',
             'Mara', ('Hurt', 'Grateful', 'Amused', 'Resigned'),
             (7, 0, 0, 5)),
    Dialogue('Ivo: They picked my design for the new library.\nLena: Ivo! '
             'After three tries!\nIvo: I almost did not send it this '
             'time.\nLena: I am so glad you did.',
             'Ivo', ('Proud', 'Anxious', 'Relieved', 'Bored'),
             (8, 1, 6, 0)),
    Dialogue('Petra: Who moved my notes from the desk?\nKai: I tidied a '
             'bit. They are in the drawer.\nPetra: I had them in order '
             'for the exam tomorrow.\nKai: Oh. I did not know.',
             'Kai', ('Guilty', 'Annoyed', 'Embarrassed', 'Joyful'),
             (6, 1, 5, 0)),
)


def dialogues_path() -> str:
    return os.path.join(home(), 'eqbench.jsonl')


def _parse_eq(row: dict) -> Optional[Dialogue]:
    prompt = row['prompt']
    m = re.search(r'dialogue:\s*\n(.*?)\[End dialogue\]', prompt, re.S)
    w = re.search(r'At the end of this dialogue, (.+?) would feel', prompt)
    ref = row['reference_answer']
    if isinstance(ref, str):
        try:
            ref = json.loads(ref.replace("'", '"'))
        except ValueError:
            return None
    if not m or not w:
        return None
    try:
        emos = tuple(ref['emotion%d' % k] for k in range(1, 5))
        scores = tuple(int(ref['emotion%d_score' % k]) for k in range(1, 5))
    except (KeyError, ValueError, TypeError):
        return None
    return Dialogue(m.group(1).strip(), w.group(1).strip(), emos, scores)


def fetch_dialogues(progress=print) -> int:
    rows = _rows(EQ_REPO, 'default', 'validation')
    got = [d for d in (_parse_eq(r) for r in rows) if d is not None]
    with open(dialogues_path(), 'w', encoding='utf-8') as fh:
        for d in got:
            fh.write(json.dumps(d._asdict()) + '\n')
    dialogues.cache_clear()
    progress('dialogues: %d kept' % len(got))
    return len(got)


@functools.lru_cache(maxsize=1)
def dialogues() -> Tuple[Dialogue, ...]:
    if os.path.exists(dialogues_path()):
        with open(dialogues_path(), encoding='utf-8') as fh:
            got = []
            for line in fh:
                d = json.loads(line)
                got.append(Dialogue(d['text'], d['who'], tuple(d['emotions']),
                                    tuple(d['scores'])))
        if got:
            return tuple(got)
    return SEED_DIALOGUES


# --- stories (EmoBench) ---------------------------------------------------------

class Story(NamedTuple):
    kind: str                      # 'understand' or 'act'
    scenario: str
    subject: str
    choices: Tuple[str, ...]       # emotions, or actions
    answer: str
    causes: Tuple[str, ...] = ()   # why (understand only)
    cause: str = ''


SEED_STORIES = (
    Story('understand', 'Ana trained for months for the city race. On the '
          'day, she finished last, but her little brother ran to hug her '
          'at the line, holding a sign with her name.', 'Ana',
          ('Shame', 'Touched', 'Anger', 'Boredom'), 'Touched',
          ('She finished last', 'Her brother came to cheer for her',
           'The race was too long', 'She had trained for months'),
          'Her brother came to cheer for her'),
    Story('act', 'A new colleague of Omar\'s eats lunch alone every day and '
          'seems nervous in meetings.', 'Omar',
          ('Ignore it, it is not his business',
           'Invite the colleague to join his group for lunch',
           'Tell the manager the colleague is unsociable',
           'Joke about it in the next meeting'),
          'Invite the colleague to join his group for lunch'),
)


def stories_path() -> str:
    return os.path.join(home(), 'emobench.jsonl')


def fetch_stories(progress=print) -> int:
    out = []
    for r in _rows(EMO_REPO, 'emotional_understanding', 'train'):
        if r.get('language') != 'en':
            continue
        out.append(Story('understand', r['scenario'], r['subject'],
                         tuple(r['emotion_choices']), r['emotion_label'],
                         tuple(r['cause_choices']), r['cause_label']))
    for r in _rows(EMO_REPO, 'emotional_application', 'train'):
        if r.get('language') != 'en':
            continue
        out.append(Story('act', r['scenario'], r['subject'],
                         tuple(r['choices']), r['label']))
    out = [s for s in out if s.answer in s.choices and
           (s.kind == 'act' or s.cause in s.causes) and
           len(s.choices) <= 8 and len(s.causes) <= 8]
    with open(stories_path(), 'w', encoding='utf-8') as fh:
        for s in out:
            fh.write(json.dumps(s._asdict()) + '\n')
    stories.cache_clear()
    progress('stories: %d kept' % len(out))
    return len(out)


@functools.lru_cache(maxsize=1)
def stories() -> Tuple[Story, ...]:
    if os.path.exists(stories_path()):
        with open(stories_path(), encoding='utf-8') as fh:
            got = []
            for line in fh:
                d = json.loads(line)
                got.append(Story(d['kind'], d['scenario'], d['subject'],
                                 tuple(d['choices']), d['answer'],
                                 tuple(d.get('causes', ())),
                                 d.get('cause', '')))
        if got:
            return tuple(got)
    return SEED_STORIES


FETCHERS = {'faces': fetch_faces, 'comments': fetch_comments,
            'dialogues': fetch_dialogues, 'stories': fetch_stories}


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
