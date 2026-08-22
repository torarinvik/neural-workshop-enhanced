# -*- coding: utf-8 -*-
"""Typefaces fetched from Hugging Face, for the glyph distorter.

:mod:`neural_workshop.glyphs` reads whatever fonts the machine already
has. That is enough to run and not enough to measure: this Mac has 198
families and 59 of them draw Latin capitals, of which the ten that end
up held out are ten particular typefaces rather than a sample of
anything. A Linux box has a different 59, and a fresh container has
about four.

So the pool can be widened from a mirror. ``Felix92/docTR-resource-
collection`` carries Google Fonts as plain ``.ttf`` files — 6,899 of
them, about 3 GB, plus a 1,010-file subset the mirror marks as covering
English. Those are the two pools below.

Nothing here downloads on its own. A caller asks, by count, and gets
that many *families* rather than that many files; fetching is
idempotent and resumable, because files are named after their name in
the mirror and one already on disk is skipped.

    python -m neural_workshop.fontlib english 200

Two things about this that are easy to get wrong.

**The filename is not the family.** ``Cardo_italic.ttf`` and
``Cardo_700.ttf`` are one typeface, and the whole point of splitting by
family is that they cannot land on opposite sides of a held-out test.
The filename *is* used here, but only to spread a fetch across the
mirror rather than pulling nine weights of one face — and then
:func:`neural_workshop.glyphs.families` regroups everything that
arrived by the family name in the font's own ``name`` table, which is
the authoritative one. Where the two disagree the name table wins and
the split stays honest.

**"English" is the mirror's word, not a measurement.** The subset
contains ``Noto_Sans_Thai_Looped`` and ``Kanit``; what it means is that
those faces carry English as well, not that they are Latin faces. It is
a way to avoid downloading three gigabytes of CJK, and it is not a
substitute for :func:`neural_workshop.glyphs.covered`, which reads the
font's own ``cmap`` and is the only thing that should decide whether a
typeface can draw the alphabet a task is about to ask for.

Licensing: the files are Google Fonts, published under the SIL Open
Font License, Apache 2.0 or the Ubuntu Font Licence depending on the
family; the mirror is tagged Apache 2.0. Nothing is redistributed with
this repository — a fetch puts them in the player's own data directory,
the same way the media libraries in :mod:`neural_workshop.datasets` do.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import json
import os
import random
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import (Callable, Dict, List, NamedTuple, Optional, Sequence,
                    Tuple)

from . import runtime
from .glyphs import platform_dirs
from .paths import get_data_dir

#: Seconds to wait on any one request.
_TIMEOUT = 30

#: Files the tree endpoint returns per request.
_PAGE = 1000

#: Parallel downloads. Politeness against a public service, not speed.
_WORKERS = 8

_HEADERS = {'User-Agent': 'neural-workshop'}

_TREE_URL = 'https://huggingface.co/api/datasets/%s/tree/main/%s?limit=%d'
_FILE_URL = 'https://huggingface.co/datasets/%s/resolve/main/%s'


class Pool(NamedTuple):
    """One folder of font files in one mirror."""

    key: str
    repo: str
    folder: str
    #: What the mirror holds, for a caller deciding what to ask for.
    files: int
    approx_bytes: int
    note: str


POOLS: Dict[str, Pool] = {
    'english': Pool(
        'english', 'Felix92/docTR-resource-collection',
        'sorted_fonts/english', 1010, 390_000,
        'Google Fonts the mirror marks as covering English'),
    'google': Pool(
        'google', 'Felix92/docTR-resource-collection',
        'google_fonts', 6899, 440_000,
        'all of Google Fonts, every script'),
}

#: Called with (fetched, wanted) as a download proceeds.
Progress = Callable[[int, int], None]

#: ``<hash>_<rest>.ttf``. The hash is 32 or 64 hex characters, and
#: *rest* is not one shape: most of the mirror is ``Nova_Cut_regular``
#: but some of it is ``TH Sarabun New Regular`` or ``DejaVuSerif-Bold``.
_NAMED = re.compile(r'^[0-9a-f]{8,}_(?P<rest>.+)\.[to]tf$', re.IGNORECASE)

#: A trailing word that names a weight or a slant rather than a face.
_STYLE = re.compile(
    r'^(\d{3}italic|\d{3}|thin|extralight|ultralight|light|regular|normal|'
    r'book|medium|semibold|demibold|demi|bold|extrabold|ultrabold|black|'
    r'heavy|italic|oblique|condensed|expanded|semicondensed|'
    r'[a-z]*italic)$', re.IGNORECASE)


def fonts_dir() -> str:
    """Where fetched typefaces live, outside the repository."""
    return os.path.join(get_data_dir(), 'fonts')


def pool_dir(pool: Pool) -> str:
    """The folder holding *pool*, created if need be."""
    path = os.path.join(fonts_dir(), pool.key)
    os.makedirs(path, exist_ok=True)
    return path


def local_files(pool: Pool) -> List[str]:
    """Every font of *pool* already on disk, in a stable order."""
    path = os.path.join(fonts_dir(), pool.key)
    if not os.path.isdir(path):
        return []
    return sorted(os.path.join(path, name) for name in os.listdir(path)
                  if name.lower().endswith(('.ttf', '.otf')))


def have(pool: Pool) -> int:
    """How many fonts of *pool* are on disk."""
    return len(local_files(pool))


def _get(url: str, timeout: int = _TIMEOUT) -> bytes:
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _listing_path(pool: Pool) -> str:
    return os.path.join(pool_dir(pool), '_listing.json')


def listing(pool: Pool, refresh: bool = False) -> List[str]:
    """Every file the mirror holds in *pool*, cached beside the fonts.

    Cached because it is seven requests for the larger pool and it does
    not change, and because a caller asking for another fifty families
    next week should be spending its bytes on fonts.
    """
    cached = _listing_path(pool)
    if not refresh and os.path.exists(cached):
        try:
            with open(cached, encoding='utf-8') as handle:
                return list(json.load(handle))
        except (OSError, ValueError):
            pass
    names: List[str] = []
    cursor = None
    while True:
        url = _TREE_URL % (pool.repo, pool.folder, _PAGE)
        if cursor:
            url += '&cursor=' + cursor
        request = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            link = response.headers.get('Link') or ''
            rows = json.load(response)
        names.extend(row['path'] for row in rows
                     if row.get('type') == 'file'
                     and row['path'].lower().endswith(('.ttf', '.otf')))
        found = re.search(r'cursor=([^&>]+)', link)
        if not rows or not found:
            break
        cursor = found.group(1)
    names.sort()
    try:
        with open(cached, 'w', encoding='utf-8') as handle:
            json.dump(names, handle)
    except OSError as exc:                      # pragma: no cover - disk
        runtime.debug_msg(exc)
    return names


def guessed_family(path: str) -> str:
    """The family a mirror filename suggests. A planner, not an answer.

    ``..._Nova_Cut_regular.ttf`` reads as "Nova Cut" and
    ``..._DejaVuSerif-Bold.ttf`` as "DejaVuSerif", by taking trailing
    words that name a weight or a slant off the end. Used to spread a
    fetch across the mirror instead of pulling nine weights of one
    face; the family a font is actually *in* comes from its own name
    table, through :func:`neural_workshop.glyphs.families`.

    Wrong sometimes, and that is affordable: a face this splits in two
    costs a duplicate download, and a face it wrongly joins costs one
    fewer typeface in the fetch. Neither can put a family on both sides
    of a held-out split, because nothing downstream trusts this.
    """
    name = os.path.basename(path)
    found = _NAMED.match(name)
    rest = found.group('rest') if found else os.path.splitext(name)[0]
    rest = rest.replace('_', ' ')
    # Twice, for a "Bold Italic" that arrives as two words.
    for _pass in (0, 1):
        for cut in (' ', '-'):
            head, sep, tail = rest.rpartition(cut)
            if sep and head and _STYLE.match(tail):
                rest = head
                break
    return rest.strip() or os.path.splitext(name)[0]


def plan(names: Sequence[str], families: int, seed: int = 0) -> List[str]:
    """Pick one file each from *families* different-looking families.

    Sorted and then shuffled from *seed*, so the same request always
    picks the same fonts: a measurement that names a held-out family
    has to be repeatable on another machine, and it cannot be if the
    pool it drew from was different.
    """
    grouped: Dict[str, List[str]] = {}
    for name in sorted(names):
        grouped.setdefault(guessed_family(name), []).append(name)
    keys = sorted(grouped)
    random.Random(seed).shuffle(keys)
    return [grouped[key][0] for key in keys[:max(0, int(families))]]


def _download_one(pool: Pool, name: str) -> bool:
    """Save one font. Returns whether a new file appeared."""
    path = os.path.join(pool_dir(pool), os.path.basename(name))
    if os.path.exists(path):
        return False
    try:
        # Quoted: a few of the mirror's filenames carry spaces,
        # and http.client refuses a request line containing one.
        data = _get(_FILE_URL % (pool.repo, urllib.parse.quote(name)))
    except (urllib.error.URLError, OSError) as exc:
        runtime.debug_msg('%s: %s' % (name, exc))
        return False
    if not data:
        return False
    # Written beside the target and renamed, so an interrupted download
    # never leaves a half file that later looks complete — and a half
    # font is worse than none: it parses far enough to claim a family.
    partial = path + '.part'
    with open(partial, 'wb') as handle:
        handle.write(data)
    os.replace(partial, path)
    return True


def fetch(pool: Pool, families: int, seed: int = 0,
          progress: Optional[Progress] = None) -> int:
    """Fetch up to *families* fonts of *pool*. Returns how many are on disk."""
    from concurrent.futures import ThreadPoolExecutor
    pool_dir(pool)          # so an asked-for pool exists even if empty
    wanted = plan(listing(pool), families, seed)
    missing = [name for name in wanted
               if not os.path.exists(os.path.join(pool_dir(pool),
                                                  os.path.basename(name)))]
    done = len(wanted) - len(missing)
    if progress:
        progress(done, len(wanted))
    if missing:
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool_of_threads:
            for got in pool_of_threads.map(
                    lambda name: _download_one(pool, name), missing):
                done += 1 if got else 0
                if progress:
                    progress(done, len(wanted))
    return have(pool)


def font_dirs(pool: Optional[Pool] = None) -> Tuple[str, ...]:
    """Where to look for typefaces: this machine's, plus anything fetched.

    Pass this to :func:`neural_workshop.glyphs.families` instead of
    :func:`neural_workshop.glyphs.platform_dirs` to include the mirror.
    A pool with nothing downloaded contributes nothing, so this is safe
    to call before any fetch.
    """
    found = list(platform_dirs())
    pools = POOLS.values() if pool is None else [pool]
    for one in pools:
        path = os.path.join(fonts_dir(), one.key)
        if os.path.isdir(path):
            found.append(path)
    return tuple(found)


def _human(size: int) -> str:
    return '%.1f MB' % (size / 1e6) if size >= 1e6 else '%.0f kB' % (size / 1e3)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python -m neural_workshop.fontlib [pool] [families]``"""
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    names = [arg for arg in args if not arg.isdigit()] or ['english']
    counts = [int(arg) for arg in args if arg.isdigit()] or [200]

    unknown = [name for name in names if name not in POOLS]
    if unknown:
        print('Unknown pool(s): %s' % ', '.join(unknown))
        print('Known: %s' % ', '.join('%s (%s, %d files)'
                                      % (key, one.note, one.files)
                                      for key, one in sorted(POOLS.items())))
        return 2

    for position, name in enumerate(names):
        pool = POOLS[name]
        wanted = counts[position] if position < len(counts) else counts[-1]
        print('%s: have %d, want %d families (about %s) from %s/%s'
              % (name, have(pool), wanted,
                 _human(max(0, wanted - have(pool)) * pool.approx_bytes),
                 pool.repo, pool.folder))

        def report(got: int, want: int) -> None:
            print('\r  %-10s %5d / %d' % (name, got, want), end='', flush=True)

        total = fetch(pool, wanted, progress=report)
        on_disk = sum(os.path.getsize(path) for path in local_files(pool))
        print('\r  %-10s %5d fonts, %s in %s'
              % (name, total, _human(on_disk), pool_dir(pool)))
    return 0


__all__ = ['POOLS', 'Pool', 'Progress', 'fetch', 'font_dirs', 'fonts_dir',
           'guessed_family', 'have', 'listing', 'local_files', 'main', 'plan',
           'pool_dir']


if __name__ == '__main__':
    raise SystemExit(main())
