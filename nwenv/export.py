# -*- coding: utf-8 -*-
"""Optional shared-memory framebuffer dump.

This is a one-way export for watching a run from another process. It is
deliberately *not* a control protocol: there is no seqlock, no action
channel, no reset or config path and no ownership handshake.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import struct
from typing import Optional

#: magic, version, sequence, timestamp, width, height, flags
HEADER = struct.Struct('<4sIQQIII')
MAGIC = b'NWFB'
VERSION = 1


class FrameExport:
    """Writes the latest frame into a named shared-memory block."""

    def __init__(self, shm_name: Optional[str] = None) -> None:
        self.shm_name = shm_name
        self._shm = None

    def write(self, seq: int, timestamp_ns: int, width: int, height: int,
              rgba: bytes, consumed: bool) -> None:
        """Publish one frame. A no-op when no block name was given."""
        if not self.shm_name:
            return
        blob = HEADER.pack(MAGIC, VERSION, int(seq), int(timestamp_ns),
                           int(width), int(height),
                           1 if consumed else 0) + (rgba or b'')
        try:
            from multiprocessing import shared_memory
        except ImportError:
            return

        size = len(blob)
        if self._shm is None or self._shm.size < size:
            self.close()
            try:
                self._shm = shared_memory.SharedMemory(
                    name=self.shm_name, create=True, size=size)
            except FileExistsError:
                # A stale block from an earlier run; take it over.
                old = shared_memory.SharedMemory(name=self.shm_name)
                old.close()
                old.unlink()
                self._shm = shared_memory.SharedMemory(
                    name=self.shm_name, create=True, size=size)
        self._shm.buf[:size] = blob

    def close(self) -> None:
        """Release and unlink the block, if one is open."""
        if self._shm is None:
            return
        try:
            self._shm.close()
            self._shm.unlink()
        except Exception:
            pass
        self._shm = None
