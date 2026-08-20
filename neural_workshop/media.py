# -*- coding: utf-8 -*-
"""Loading downloaded media, and handing games a supply of it.

:mod:`neural_workshop.datasets` puts files on disk; this turns them
into pyglet objects and rations them out. A :class:`MediaPool` is the
supply a game draws from: it knows what is available, hands out items
nobody has seen this session, and caches what it has decoded.

Loading is lazy and forgiving. A library that was never downloaded, or
a file that turns out to be corrupt, leaves the pool smaller rather
than raising — a game asks :meth:`MediaPool.ready` first and says so
in its own words.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
from typing import Any, Dict, List, Optional, Sequence

import pyglet

from . import datasets, runtime
from .datasets import Dataset

#: Decoded items, keyed by path, shared by every pool on that dataset.
#: Textures and sound sources are expensive and immutable, so two games
#: open at once should not each hold their own copy.
_cache: Dict[str, Any] = {}

#: How many decoded items to keep. Images are small; sounds are not.
_CACHE_LIMIT = 512


def clear_cache() -> None:
    """Drop every decoded item. Used by tests and on profile switch."""
    _cache.clear()


def _load_image(path: str) -> Optional[pyglet.image.AbstractImage]:
    try:
        with open(path, 'rb') as handle:
            return pyglet.image.load(filename=path, file=handle)
    except Exception as exc:
        runtime.debug_msg('could not load image %s: %s' % (path, exc))
        return None


def _load_sound(path: str) -> Optional[Any]:
    try:
        return pyglet.media.load(path, streaming=False)
    except Exception as exc:
        runtime.debug_msg('could not load sound %s: %s' % (path, exc))
        return None


def load(dataset: Dataset, path: str) -> Optional[Any]:
    """Decode one file, or ``None`` if it will not load."""
    if path in _cache:
        return _cache[path]
    item = (_load_image(path) if dataset.kind == 'image'
            else _load_sound(path))
    if item is None:
        return None
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[path] = item
    return item


class MediaPool:
    """A game's supply of items from one dataset.

    *seen* is the session's history: :meth:`take` never returns the
    same item twice, so "have you seen this before?" means what it
    says. :meth:`recall` deliberately returns something already given
    out, which is the other half of that game.
    """

    def __init__(self, dataset: Dataset,
                 rng: Optional[random.Random] = None) -> None:
        self.dataset = dataset
        self.rng = rng or random.Random()
        self.paths: List[str] = []
        self.order: List[str] = []
        self.given: List[str] = []
        self.reload()

    # --- what is available ----------------------------------------------

    def reload(self) -> None:
        """Re-read the library from disk and reshuffle it."""
        self.paths = datasets.local_files(self.dataset)
        self.order = list(self.paths)
        self.rng.shuffle(self.order)
        self.given = []

    def ready(self, needed: int = 1) -> bool:
        """True when the library holds at least *needed* items."""
        return len(self.paths) >= max(1, needed)

    def missing_message(self, needed: int) -> str:
        """What to tell a player whose library is too small."""
        return ('%s needs %d items, found %d in %s'
                % (self.dataset.key, needed, len(self.paths),
                   os.path.join(datasets.datasets_dir(), self.dataset.key)))

    # --- drawing items --------------------------------------------------

    def take(self) -> Optional[str]:
        """A path nobody has been given this session, or ``None``."""
        while self.order:
            path = self.order.pop()
            self.given.append(path)
            return path
        return None

    def take_many(self, count: int) -> List[str]:
        """Up to *count* fresh paths."""
        taken = []
        for _ in range(count):
            path = self.take()
            if path is None:
                break
            taken.append(path)
        return taken

    def recall(self, exclude: Sequence[str] = ()) -> Optional[str]:
        """A path already handed out, for a repeat trial."""
        pool = [path for path in self.given if path not in exclude]
        return self.rng.choice(pool) if pool else None

    def item(self, path: str) -> Optional[Any]:
        """The decoded image or sound at *path*."""
        return load(self.dataset, path)


def image_pool(rng: Optional[random.Random] = None) -> MediaPool:
    """The photograph library."""
    return MediaPool(datasets.TINY_IMAGENET, rng)


def jigsaw_pool(rng: Optional[random.Random] = None) -> MediaPool:
    """The 2K photograph library the jigsaw puzzles are cut from."""
    return MediaPool(datasets.DIV2K, rng)


def sound_pool(rng: Optional[random.Random] = None) -> MediaPool:
    """The environmental-sound library."""
    return MediaPool(datasets.ESC50, rng)


def pool_for(medium: str, rng: Optional[random.Random] = None) -> MediaPool:
    """The library for ``'sound'`` or anything else, which means images."""
    return sound_pool(rng) if medium == 'sound' else image_pool(rng)
