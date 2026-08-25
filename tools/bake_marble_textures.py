#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bake the Marble Maze's material maps out of the source .glb assets.

A build step, run by hand and its output committed, which is why it
lives in ``tools/`` rather than being done at load time. Two things
make that the right shape.

The source assets are 99MB between them and almost all of that is
geometry the Workshop cannot use: the labyrinth is a single fused mesh
of a *fixed* maze — two million triangles with no separable walls or
holes — and this task generates its mazes, so the shapes have to come
from :mod:`neural_workshop.marblemaze` and be certified passable before
they are dealt. What the assets have that is worth keeping is their
*surfaces* — and in the event, only the marble's: see the note in
:func:`main` for why the labyrinth's atlas could not be used either.

And the maps only need to be small. The marble is about thirty
pixels across on screen, so a 4096-square source is a hundred times
more texture than any frame can show. Everything is boxed down to at
most :data:`EDGE` and written out as PNG, which turns 20MB of asset
into 640KB in ``res/``.

Usage::

    python tools/bake_marble_textures.py ~/Downloads/steel_marble.glb

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import io
import json
import os
import struct
import sys
from typing import Dict, Optional, Tuple

#: The largest edge any baked map gets. See the module docstring for
#: why this is far below the source: the tray is about 900 screen
#: pixels wide at most and the marble about thirty.
EDGE = 512

#: Where the baked maps go, relative to the repository root.
OUT = os.path.join('res', 'marblemaze')

#: glTF material slots worth taking, and what this task calls them.
WANTED = {
    'baseColorTexture': 'colour',
    'metallicRoughnessTexture': 'rough',
    'normalTexture': 'normal',
}


def read_glb(path: str) -> Tuple[dict, bytes]:
    """The JSON chunk and the binary chunk of a .glb."""
    with open(path, 'rb') as handle:
        magic, _version, _length = struct.unpack('<4sII', handle.read(12))
        if magic != b'glTF':
            raise SystemExit('%s is not a .glb' % path)
        doc: Optional[dict] = None
        binary = b''
        while True:
            head = handle.read(8)
            if len(head) < 8:
                break
            size, kind = struct.unpack('<I4s', head)
            payload = handle.read(size)
            if kind.strip(b'\x00') == b'JSON':
                doc = json.loads(payload)
            else:
                binary = payload
    if doc is None:
        raise SystemExit('%s has no JSON chunk' % path)
    return doc, binary


def image_bytes(doc: dict, binary: bytes, index: int) -> bytes:
    view = doc['bufferViews'][doc['images'][index]['bufferView']]
    start = view.get('byteOffset', 0)
    return binary[start:start + view['byteLength']]


def slots(doc: dict) -> Dict[str, int]:
    """Which image index sits in which material slot."""
    found: Dict[str, int] = {}
    for material in doc.get('materials', []):
        pbr = material.get('pbrMetallicRoughness', {})
        for holder in (pbr, material):
            for slot, name in WANTED.items():
                if slot in holder and name not in found:
                    texture = doc['textures'][holder[slot]['index']]
                    source = texture.get('source')
                    if source is not None:
                        found[name] = source
    return found


def boxed(data, width: int, height: int, edge: int):
    """Box-filter *data* (RGBA bytes) down so neither side passes *edge*.

    A box filter rather than nearest, and in pure Python because the
    Workshop has neither PIL nor numpy and is not about to grow a
    dependency for a step that runs once. Whole-number factors only,
    which every power-of-two source satisfies.
    """
    factor = 1
    while (width // (factor * 2)) >= edge or (height // (factor * 2)) >= edge:
        factor *= 2
    if factor == 1 and width <= edge and height <= edge:
        return data, width, height
    while width // factor > edge or height // factor > edge:
        factor *= 2
    out_w, out_h = max(1, width // factor), max(1, height // factor)
    out = bytearray(out_w * out_h * 4)
    taps = factor * factor
    for y in range(out_h):
        base_y = y * factor
        row = y * out_w * 4
        for x in range(out_w):
            base_x = x * factor
            r = g = b = a = 0
            for dy in range(factor):
                src = ((base_y + dy) * width + base_x) * 4
                for dx in range(factor):
                    at = src + dx * 4
                    r += data[at]
                    g += data[at + 1]
                    b += data[at + 2]
                    a += data[at + 3]
            at = row + x * 4
            out[at] = r // taps
            out[at + 1] = g // taps
            out[at + 2] = b // taps
            out[at + 3] = a // taps
    return bytes(out), out_w, out_h


def bake(path: str, prefix: str, keep: Tuple[str, ...]) -> None:
    import pyglet

    doc, binary = read_glb(path)
    found = slots(doc)
    if not found:
        print('  %s: no material maps found' % os.path.basename(path))
        return
    for name in keep:
        index = found.get(name)
        if index is None:
            print('  %-7s not in this asset' % name)
            continue
        raw = image_bytes(doc, binary, index)
        mime = doc['images'][index].get('mimeType', 'image/jpeg')
        suffix = '.png' if mime.endswith('png') else '.jpg'
        picture = pyglet.image.load('x' + suffix, file=io.BytesIO(raw))
        data = picture.get_image_data()
        rgba = data.get_data('RGBA', data.width * 4)
        small, width, height = boxed(rgba, data.width, data.height, EDGE)
        out = pyglet.image.ImageData(width, height, 'RGBA', small,
                                     pitch=width * 4)
        target = os.path.join(OUT, '%s_%s.png' % (prefix, name))
        out.save(target)
        print('  %-7s %4dx%-4d -> %3dx%-3d  %6.1f KB -> %5.1f KB  %s'
              % (name, data.width, data.height, width, height,
                 len(raw) / 1024.0, os.path.getsize(target) / 1024.0,
                 target))


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    os.makedirs(OUT, exist_ok=True)
    print('baking into %s at most %dpx a side' % (OUT, EDGE))
    # Nothing is taken from the labyrinth. Its base-colour map is a UV
    # *atlas* — islands of grain at every orientation, with decorative
    # bits scattered through it — and an atlas is only a surface
    # texture in company with the mesh it was unwrapped for. This task
    # generates its trays, so there is no such mesh.
    #
    # Six candidate squares were cropped out of it and mirror-tiled,
    # looking for a patch of clean continuous grain to use instead.
    # There is not one: every square that is large enough to tile also
    # contains the pale gaps between islands, and two of them contain
    # inlay decorations. The tray keeps the procedural timber in
    # neural_workshop/ui/render3d.py, which is better than any of them.
    print('marble, from %s:' % os.path.basename(argv[-1]))
    bake(argv[-1], 'marble', ('colour', 'rough', 'normal'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
