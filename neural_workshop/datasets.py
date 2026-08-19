# -*- coding: utf-8 -*-
"""Media libraries downloaded from Hugging Face, for the memory games.

The long-term-memory games need far more material than the repository
should carry — the point of "have you seen this before?" is that you
have not seen it a hundred times already. So the material is fetched
once into the user's data directory and reused from there.

Everything here is standard library. Hugging Face's datasets-server
serves each row as JSON with a link to the decoded asset, so a plain
``urllib`` fetch gets a JPEG or a WAV without ``datasets``, ``pyarrow``
or ``pillow``. Those links are signed and expire, so a batch is
downloaded as soon as it is listed rather than saved for later.

Fetching is resumable and idempotent: files are named after their row
index, and a row already on disk is skipped. Nothing here downloads
anything on its own — a caller asks, so a player who never opens these
games never fetches anything.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import json
import os
import random
import threading
import urllib.error
import urllib.request
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import runtime
from .paths import get_data_dir

#: Rows the datasets-server returns per request.
_PAGE = 100

#: Seconds to wait on any one request before giving up on it.
_TIMEOUT = 30

#: Parallel downloads. Politeness against a public service, not speed.
_WORKERS = 8

_ROWS_URL = ('https://datasets-server.huggingface.co/rows'
             '?dataset=%s&config=%s&split=%s&offset=%d&length=%d')

_HEADERS = {'User-Agent': 'neural-workshop'}


class Dataset(NamedTuple):
    """A media library we know how to fetch and where to keep."""

    key: str            # our name for it, and its folder
    repo: str           # the Hugging Face dataset id
    split: str
    column: str         # the row field holding the asset
    kind: str           # 'image' or 'audio'
    suffix: str
    rows: int           # rows in the split, for picking random offsets
    approx_bytes: int   # per item, for reporting a download size
    config: str = 'default'


#: Photographs, 64x64. Recognisable, numerous, and none of them are
#: things the player has a name for on sight, which is the point.
TINY_IMAGENET = Dataset(
    key='tiny-imagenet', repo='thethinkmachine/tiny-imagenet',
    split='train', column='image', kind='image', suffix='.jpg',
    rows=100000, approx_bytes=2000)

#: Five-second environmental sounds, 50 classes.
ESC50 = Dataset(
    key='esc50', repo='renumics/esc50', split='train',
    column='audio', kind='audio', suffix='.wav',
    rows=2000, approx_bytes=386000)

#: Everything a game may ask for, by key.
CATALOGUE: Dict[str, Dataset] = {
    TINY_IMAGENET.key: TINY_IMAGENET,
    ESC50.key: ESC50,
}


#: Called with (fetched, wanted) as a download proceeds.
Progress = Callable[[int, int], None]


def datasets_dir() -> str:
    """Where downloaded media lives, outside the repository."""
    return os.path.join(get_data_dir(), 'datasets')


def local_dir(dataset: Dataset) -> str:
    """The folder holding *dataset*, created if need be."""
    path = os.path.join(datasets_dir(), dataset.key)
    os.makedirs(path, exist_ok=True)
    return path


def local_files(dataset: Dataset) -> List[str]:
    """Every item of *dataset* already on disk, in a stable order."""
    path = os.path.join(datasets_dir(), dataset.key)
    if not os.path.isdir(path):
        return []
    return sorted(os.path.join(path, name) for name in os.listdir(path)
                  if name.endswith(dataset.suffix))


def have(dataset: Dataset) -> int:
    """How many items of *dataset* are on disk."""
    return len(local_files(dataset))


def download_size(dataset: Dataset, count: int) -> int:
    """Rough bytes a fetch of *count* more items would pull."""
    return max(0, count - have(dataset)) * dataset.approx_bytes


def _get(url: str, timeout: int = _TIMEOUT) -> bytes:
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _asset_url(cell: object) -> Optional[str]:
    """The link to the asset in a row cell, whatever shape it takes.

    Image columns are an object; audio columns are a list of encodings.
    """
    if isinstance(cell, dict):
        src = cell.get('src')
        return src if isinstance(src, str) else None
    if isinstance(cell, list):
        for item in cell:
            url = _asset_url(item)
            if url:
                return url
    return None


def _list_rows(dataset: Dataset, offset: int,
               length: int) -> List[Tuple[int, str]]:
    """``(row index, asset url)`` for a page of rows."""
    url = _ROWS_URL % (dataset.repo, dataset.config, dataset.split,
                       offset, length)
    payload = json.loads(_get(url))
    found: List[Tuple[int, str]] = []
    for row in payload.get('rows', []):
        asset = _asset_url(row.get('row', {}).get(dataset.column))
        if asset:
            found.append((int(row['row_idx']), asset))
    return found


def _download_one(dataset: Dataset, row_idx: int, url: str) -> bool:
    """Save one asset. Returns whether a new file appeared."""
    path = os.path.join(local_dir(dataset), '%07d%s' % (row_idx,
                                                        dataset.suffix))
    if os.path.exists(path):
        return False
    try:
        data = _get(url)
    except (urllib.error.URLError, OSError) as exc:
        runtime.debug_msg('%s row %d: %s' % (dataset.key, row_idx, exc))
        return False
    if not data:
        return False
    # Write beside the target and rename, so an interrupted download
    # never leaves a half file that later looks complete.
    partial = path + '.part'
    with open(partial, 'wb') as handle:
        handle.write(data)
    os.replace(partial, path)
    return True


def _download_batch(dataset: Dataset,
                    items: Sequence[Tuple[int, str]]) -> int:
    """Fetch a page of assets in parallel. Returns how many were new."""
    saved = [0]
    lock = threading.Lock()
    queue = list(items)

    def worker() -> None:
        while True:
            with lock:
                if not queue:
                    return
                row_idx, url = queue.pop()
            if _download_one(dataset, row_idx, url):
                with lock:
                    saved[0] += 1

    threads = [threading.Thread(target=worker, daemon=True)
               for _ in range(min(_WORKERS, len(queue)))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return saved[0]


def fetch(dataset: Dataset, wanted: int,
          progress: Optional[Progress] = None,
          rng: Optional[random.Random] = None,
          should_stop: Optional[Callable[[], bool]] = None) -> int:
    """Top *dataset* up to *wanted* items on disk. Returns the total.

    Pages are taken from random offsets so a small library is spread
    across the whole split rather than being the first N rows, which in
    a sorted-by-class dataset would be a handful of classes.

    Stops early and keeps what it has if the network fails or
    *should_stop* returns True, so a cancelled or offline fetch still
    leaves a usable library behind.
    """
    rng = rng or random.Random()
    count = have(dataset)
    if count >= wanted:
        return count
    if progress:
        progress(count, wanted)

    span = max(1, dataset.rows - _PAGE)
    tried: set = set()
    stalled = 0
    while count < wanted and stalled < 5:
        if should_stop is not None and should_stop():
            break
        offset = rng.randrange(0, span)
        offset -= offset % _PAGE          # page-aligned, so retries collide
        if offset in tried:
            stalled += 1
            continue
        tried.add(offset)
        try:
            rows = _list_rows(dataset, offset,
                              min(_PAGE, wanted - count + _PAGE // 2))
        except Exception as exc:
            runtime.debug_msg('%s rows at %d: %s' % (dataset.key, offset, exc))
            stalled += 1
            continue
        if not rows:
            stalled += 1
            continue
        added = _download_batch(dataset, rows[:max(1, wanted - count)])
        stalled = 0 if added else stalled + 1
        count = have(dataset)
        if progress:
            progress(count, wanted)
    return count


def by_key(key: str) -> Optional[Dataset]:
    """Look a dataset up by name."""
    return CATALOGUE.get(key)


# --- command line ----------------------------------------------------------

#: What ``python -m neural_workshop.datasets`` fetches when asked for
#: everything. Enough for the games without being a large download.
DEFAULT_COUNTS: Dict[str, int] = {
    TINY_IMAGENET.key: 5000,
    ESC50.key: 500,
}


def _human(size: int) -> str:
    return '%.1f MB' % (size / 1e6) if size >= 1e6 else '%.0f kB' % (size / 1e3)


def _report(dataset: Dataset) -> Callable[[int, int], None]:
    def progress(got: int, want: int) -> None:
        print('\r  %-14s %5d / %d' % (dataset.key, got, want),
              end='', flush=True)
    return progress


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Fetch media libraries. ``-m neural_workshop.datasets [name] [count]``"""
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    names = [a for a in args if not a.isdigit()] or sorted(CATALOGUE)
    counts = [int(a) for a in args if a.isdigit()]

    unknown = [name for name in names if name not in CATALOGUE]
    if unknown:
        print('Unknown dataset(s): %s' % ', '.join(unknown))
        print('Known: %s' % ', '.join(sorted(CATALOGUE)))
        return 2

    for position, name in enumerate(names):
        dataset = CATALOGUE[name]
        wanted = (counts[position] if position < len(counts)
                  else DEFAULT_COUNTS.get(name, 500))
        pending = download_size(dataset, wanted)
        print('%s: have %d, want %d (about %s to download) from %s'
              % (name, have(dataset), wanted, _human(pending), dataset.repo))
        total = fetch(dataset, wanted, progress=_report(dataset))
        on_disk = sum(os.path.getsize(path) for path in local_files(dataset))
        print('\r  %-14s %5d items, %s in %s'
              % (name, total, _human(on_disk), local_dir(dataset)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
