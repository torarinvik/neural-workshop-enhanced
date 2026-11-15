#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Index the ESC-50 clips for Tuner: each clip's class and where its
sound is.

A build step, run by hand with its output committed. Tuner picks its
stations by class -- three sounds from three walks of life on the first
rungs, two recordings of the same dog later -- and loops each clip's
sounding part, so before a trial is dealt it has to know, without
opening a single file, what every clip is and which stretch of it is
not silence. Many ESC-50 clips are a second of sound padded out to five
with zeros; looping those would be mostly quiet.

The labels come from the dataset's rows on Hugging Face (JSON only, no
audio); the spans from the clips already downloaded into the data
directory (``python -m neural_workshop.datasets esc50``). Output is
``res/misc/esc50/index.tsv``: row, class, start and end of the sounding
stretch in milliseconds, the share of that stretch that is sounding,
and its loudness in dB below full scale.

Usage::

    python tools/index_esc50.py [labels.json]

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from neural_workshop import datasets  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'res', 'misc', 'esc50',
                   'index.tsv')
WINDOW = 0.05                 # seconds per loudness window
QUIET = 0.08                  # a window this far below the peak is silence


def fetch_labels() -> list:
    rows = {}
    for offset in range(0, datasets.ESC50.rows, 100):
        url = (datasets._ROWS_URL % (datasets.ESC50.repo, 'default', 'train',
                                     offset, 100))
        for attempt in range(5):
            try:
                request = urllib.request.Request(url, headers=datasets._HEADERS)
                with urllib.request.urlopen(request, timeout=30) as reply:
                    page = json.load(reply)
                break
            except OSError:
                time.sleep(2 + 2 * attempt)
        else:
            raise SystemExit('could not fetch rows at %d' % offset)
        for row in page['rows']:
            rows[row['row_idx']] = row['row']['label']
    return [rows[k] for k in range(len(rows))]


def measure(path: str) -> tuple:
    with wave.open(path) as w:
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
        if w.getnchannels() > 1:
            pcm = pcm.reshape(-1, w.getnchannels()).mean(axis=1)
    x = pcm.astype(np.float64) / 32768.0
    step = int(rate * WINDOW)
    n = len(x) // step
    if n == 0:
        return 0, 0, 0.0, -99.0
    rms = np.sqrt((x[:n * step].reshape(n, step) ** 2).mean(axis=1))
    peak = rms.max()
    if peak < 1e-4:
        return 0, 0, 0.0, -99.0
    on = rms > peak * QUIET
    first = int(np.argmax(on))
    last = n - 1 - int(np.argmax(on[::-1]))
    share = float(on[first:last + 1].mean())
    level = float(np.sqrt((rms[first:last + 1] ** 2).mean()))
    ms = int(WINDOW * 1000)
    return (first * ms, (last + 1) * ms, share,
            20 * np.log10(max(level, 1e-6)))


def main(argv) -> int:
    if len(argv) > 1:
        with open(argv[1]) as handle:
            labels = [r[0] for r in json.load(handle)['rows']]
    else:
        labels = fetch_labels()
    files = datasets.local_files(datasets.ESC50)
    if len(files) != len(labels):
        raise SystemExit('found %d clips for %d labels: fetch the whole '
                         'library first' % (len(files), len(labels)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as out:
        out.write('# row\tclass\tstart_ms\tend_ms\tsounding\tdb\n')
        for k, path in enumerate(files):
            assert os.path.basename(path) == '%07d.wav' % k, path
            start, end, share, db = measure(path)
            out.write('%d\t%d\t%d\t%d\t%.2f\t%.1f\n'
                      % (k, labels[k], start, end, share, db))
    print('wrote', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
