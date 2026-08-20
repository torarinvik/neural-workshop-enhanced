# -*- coding: utf-8 -*-
"""Media libraries downloaded from Hugging Face, for the memory games.

The long-term-memory games need far more material than the repository
should carry — the point of "have you seen this before?" is that you
have not seen it a hundred times already. So the material is fetched
once into the user's data directory and reused from there.

Two routes, both standard library at heart. Item by item, Hugging
Face's datasets-server serves each row as JSON with a link to the
decoded asset, so a plain ``urllib`` fetch gets a JPEG or a WAV without
``datasets`` or ``pillow``; those links are signed and expire, so a
batch is downloaded as soon as it is listed. For a large request that
is tens of thousands of round trips, so the dataset's parquet files
are pulled instead when ``pyarrow`` is installed — one download, and
the media column already holds the encoded bytes. Neither route needs
an image or audio library, and the parquet route is optional: without
it everything still works, just slower.

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

_PARQUET_URL = 'https://datasets-server.huggingface.co/parquet?dataset=%s'

#: Above this many items, one parquet download beats thousands of
#: single-asset requests by a wide enough margin to be worth the extra
#: bytes it pulls for rows we may not keep.
_BULK_THRESHOLD = 2000

#: Asking for this share of a split means asking for the split, and
#: sampling pages at random is a poor way to collect all of them.
_BULK_SHARE = 0.4

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
    #: Zip archives holding the items, for datasets the
    #: datasets-server cannot serve item by item. When set,
    #: fetching goes through :func:`fetch_archives` instead of
    #: the row and parquet routes.
    archives: Tuple[str, ...] = ()


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

#: 2K-resolution photographs, for the jigsaw puzzles. This Hugging
#: Face dataset is a loading script over the original NTIRE challenge
#: archives rather than hosted rows — its columns are file paths on
#: the server, so the datasets-server cannot hand out the images one
#: by one and the parquet files hold strings. The archives themselves
#: are what there is, so this library is fetched by the zip route:
#: the validation archive first (100 images), the training archive
#: (800 more) only when more than a hundred are asked for.
DIV2K = Dataset(
    key='div2k', repo='eugenesiow/Div2k', split='train', column='hr',
    kind='image', suffix='.png', rows=900, approx_bytes=4400000,
    archives=(
        'https://data.vision.ee.ethz.ch/cvl/DIV2K/DIV2K_valid_HR.zip',
        'https://data.vision.ee.ethz.ch/cvl/DIV2K/DIV2K_train_HR.zip',
    ))

#: Everything a game may ask for, by key.
CATALOGUE: Dict[str, Dataset] = {
    TINY_IMAGENET.key: TINY_IMAGENET,
    ESC50.key: ESC50,
    DIV2K.key: DIV2K,
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


def parquet_parts(dataset: Dataset) -> List[Tuple[str, int]]:
    """``(url, bytes)`` for the parquet files behind *dataset*'s split."""
    payload = json.loads(_get(_PARQUET_URL % dataset.repo))
    parts = [(entry['url'], int(entry.get('size') or 0))
             for entry in payload.get('parquet_files', [])
             if entry.get('split') == dataset.split
             and entry.get('config') == dataset.config]
    return parts


def _stream_to_file(url: str, path: str,
                    progress: Optional[Callable[[int], None]] = None) -> None:
    """Download *url* to *path* without holding it all in memory."""
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        with open(path, 'wb') as handle:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                handle.write(chunk)
                if progress:
                    progress(len(chunk))


def fetch_bulk(dataset: Dataset, wanted: int,
               progress: Optional[Progress] = None,
               should_stop: Optional[Callable[[], bool]] = None) -> int:
    """Fill the library from the dataset's parquet files.

    One large download instead of one request per item, which for a
    whole split is the difference between minutes and an hour. The
    media column holds the encoded bytes already, so the files are
    written straight out — no image or audio library involved.

    Rows are numbered as the datasets-server numbers them, so the
    files land on exactly the names :func:`fetch` would have given
    them and the two routes can be mixed freely.

    Raises ImportError when pyarrow is absent; callers fall back.
    """
    import pyarrow.parquet as pq       # optional, see fetch()

    folder = local_dir(dataset)
    scratch = os.path.join(folder, '_download.parquet')
    count = have(dataset)
    row_base = 0
    try:
        for url, _size in parquet_parts(dataset):
            if count >= wanted or (should_stop is not None and should_stop()):
                break
            _stream_to_file(url, scratch)
            handle = pq.ParquetFile(scratch)
            for batch in handle.iter_batches(batch_size=256,
                                             columns=[dataset.column]):
                cells = batch.column(dataset.column).to_pylist()
                for offset, cell in enumerate(cells):
                    blob = cell.get('bytes') if isinstance(cell, dict) else None
                    if not blob:
                        continue
                    path = os.path.join(
                        folder, '%07d%s' % (row_base + offset, dataset.suffix))
                    if not os.path.exists(path):
                        partial = path + '.part'
                        with open(partial, 'wb') as out:
                            out.write(blob)
                        os.replace(partial, path)
                        count += 1
                row_base += len(cells)
                if progress:
                    progress(min(count, wanted), wanted)
                if count >= wanted:
                    break
                if should_stop is not None and should_stop():
                    break
            del handle
    finally:
        if os.path.exists(scratch):
            os.remove(scratch)
    return have(dataset)


def fetch(dataset: Dataset, wanted: int,
          progress: Optional[Progress] = None,
          rng: Optional[random.Random] = None,
          should_stop: Optional[Callable[[], bool]] = None) -> int:
    """Top *dataset* up to *wanted* items on disk. Returns the total.

    Pages are taken from random offsets so a small library is spread
    across the whole split rather than being the first N rows, which in
    a sorted-by-class dataset would be a handful of classes.

    A large request goes through :func:`fetch_bulk` when pyarrow is
    installed, which is far quicker for a whole split; without it, or
    if that fails, everything still works one item at a time.

    Stops early and keeps what it has if the network fails or
    *should_stop* returns True, so a cancelled or offline fetch still
    leaves a usable library behind.
    """
    if dataset.archives:
        return fetch_archives(dataset, wanted, progress=progress,
                              should_stop=should_stop)
    rng = rng or random.Random()
    count = have(dataset)
    if count >= wanted:
        return count
    if progress:
        progress(count, wanted)

    if (wanted - count >= _BULK_THRESHOLD
            or wanted >= dataset.rows * _BULK_SHARE):
        try:
            return fetch_bulk(dataset, wanted, progress, should_stop)
        except ImportError:
            runtime.debug_msg('pyarrow absent; fetching %s item by item'
                              % dataset.key)
        except Exception as exc:
            # A failed bulk pull leaves whatever it wrote; carry on
            # item by item rather than losing the whole request.
            runtime.debug_msg('bulk fetch of %s failed: %s'
                              % (dataset.key, exc))
        count = have(dataset)
        if count >= wanted:
            return count

    pages = max(1, (dataset.rows + _PAGE - 1) // _PAGE)
    tried: set = set()
    failures = 0
    while count < wanted and len(tried) < pages and failures < 5:
        if should_stop is not None and should_stop():
            break
        # Random pages, so a small library spans the whole split rather
        # than being its first few classes. Once a page has been taken,
        # walk on to the next untried one: re-drawing at random would
        # stall long before the split was covered, which is how asking
        # for all of something used to come back short.
        offset = (rng.randrange(0, pages) * _PAGE)
        while offset // _PAGE in tried:
            offset = ((offset // _PAGE + 1) % pages) * _PAGE
        tried.add(offset // _PAGE)
        try:
            rows = _list_rows(dataset, offset,
                              min(_PAGE, wanted - count + _PAGE // 2))
        except Exception as exc:
            runtime.debug_msg('%s rows at %d: %s' % (dataset.key, offset, exc))
            failures += 1
            continue
        if not rows:
            continue
        _download_batch(dataset, rows[:max(1, wanted - count)])
        failures = 0
        count = have(dataset)
        if progress:
            progress(count, wanted)
    return count


def _resume_to_file(url: str, path: str) -> None:
    """Download *url* to *path*, continuing a partial file if one is
    there. The archives here run to gigabytes, and a dropped
    connection at ninety per cent should not mean starting over."""
    got = os.path.getsize(path) if os.path.exists(path) else 0
    headers = dict(_HEADERS)
    if got:
        headers['Range'] = 'bytes=%d-' % got
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        resumed = got and getattr(response, 'status', 200) == 206
        with open(path, 'ab' if resumed else 'wb') as handle:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                handle.write(chunk)


def fetch_archives(dataset: Dataset, wanted: int,
                   progress: Optional[Progress] = None,
                   should_stop: Optional[Callable[[], bool]] = None) -> int:
    """Fill the library from the dataset's zip archives.

    Each archive is downloaded whole — that is the unit the source
    offers — and its images are unpacked to the same numbered names
    the other routes use, so :func:`local_files` and the pools need
    not know how anything arrived. Item numbering is the archive's
    position times ten thousand plus the entry's position in name
    order, which is stable across runs, so unpacking is idempotent
    and a later archive never collides with an earlier one.

    Archives are taken in order until *wanted* is met: asking for a
    hundred DIV2K images downloads the validation archive only, and
    asking for more pulls the training archive too.
    """
    import zipfile

    folder = local_dir(dataset)
    count = have(dataset)
    for position, url in enumerate(dataset.archives):
        if count >= wanted or (should_stop is not None and should_stop()):
            break
        base = position * 10000
        scratch = os.path.join(folder, '_archive%d.zip' % position)
        try:
            _resume_to_file(url, scratch)
            with zipfile.ZipFile(scratch) as archive:
                names = sorted(name for name in archive.namelist()
                               if name.lower().endswith(dataset.suffix))
                for offset, name in enumerate(names):
                    path = os.path.join(
                        folder, '%07d%s' % (base + offset, dataset.suffix))
                    if not os.path.exists(path):
                        partial = path + '.part'
                        with open(partial, 'wb') as out:
                            out.write(archive.read(name))
                        os.replace(partial, path)
                        count += 1
                    if progress:
                        progress(min(count, wanted), wanted)
                    if should_stop is not None and should_stop():
                        break
            os.remove(scratch)
        except (urllib.error.URLError, OSError,
                zipfile.BadZipFile) as exc:
            runtime.debug_msg('%s archive %s: %s' % (dataset.key, url, exc))
            # A bad or half zip cannot be resumed into sense.
            if (os.path.exists(scratch)
                    and isinstance(exc, zipfile.BadZipFile)):
                os.remove(scratch)
            break
    return have(dataset)


def by_key(key: str) -> Optional[Dataset]:
    """Look a dataset up by name."""
    return CATALOGUE.get(key)


# --- command line ----------------------------------------------------------

#: What ``python -m neural_workshop.datasets`` fetches when asked for
#: everything. Enough for the games without being a large download.
DEFAULT_COUNTS: Dict[str, int] = {
    TINY_IMAGENET.key: 5000,
    ESC50.key: 500,
    DIV2K.key: 100,
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
