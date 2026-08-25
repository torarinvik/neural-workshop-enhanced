# -*- coding: utf-8 -*-
"""A small perspective renderer with a real depth buffer.

The workshop's two other three-dimensional screens — the 3D Maze and 3D
Sokoban — are ray casters: one ray to a screen column, drawn as a
vertical strip. That is exactly right for a world made of unit cubes on
a grid seen from inside, and it is no use at all for a bent wire seen
from outside, which is a smooth curve in general position with a loop
threaded on it. So Buzz Wire gets this instead.

**It is not a second way of drawing; it is the same one, used harder.**
Everything here ends up in one ``pyglet.shapes`` vertex list, exactly as
:class:`neural_workshop.ui.ravens.Ribbon` does, for the reason that
module gives at length: a shape object per triangle is the readable way
and it is far too slow, and the expensive part was never the drawing but
the allocation.

Two things make it three-dimensional rather than a flat drawing that
happens to look deep.

* **The depth buffer is real.** pyglet's shape shader takes a
  ``zposition`` per vertex, the window is created with a 32-bit depth
  buffer, and ``window.clear()`` clears it. So this enables
  ``GL_DEPTH_TEST`` around its own draw, hands the hardware a depth per
  vertex and lets it work out what is in front — no painter's algorithm,
  no sorting, and no wrong answer where a loop threaded on a wire is in
  front of it and behind it at the same time, which is a case sorting
  cannot get right at any price.

  The depth handed over is ``near / z`` rather than ``z``, which is not
  a detail: ``1/z`` is the quantity that interpolates *linearly* across
  a triangle in screen space, so the value the rasteriser reconstructs
  in the middle of a face is the true depth there rather than a
  plausible one.

* **The geometry is real.** The wire is a swept tube on a
  rotation-minimising frame, the loop is a torus, and both are meshes
  with per-vertex normals shaded by Lambert and Blinn against a fixed
  key light. Nothing is a sprite and nothing is scaled by distance to
  fake perspective.

The division of labour that makes it fast enough to play: **the camera
never moves and neither does the wire**, so the five thousand triangles
of the scene — wire, board, posts, shadow, beads — are projected once
when the level is dealt and then left alone. What is rebuilt every
frame is the loop, its shadow and the slice of wire the sight view is
looking down: about seven hundred vertices between them, against a
scene of some three thousand. That ratio is the whole design.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import pyglet
from pyglet import gl

Vec = Tuple[float, float, float]
Colour = Tuple[int, int, int]

#: How far into the depth buffer the near plane sits. pyglet's default
#: projection clips ``zposition`` at +-8192 and larger is nearer, so this
#: leaves a wide margin at both ends for anything drawn without a depth
#: of its own -- every label and every flat shape, which sit at nought.
DEPTH_SPAN = 4000.0

#: Nothing closer than this to the eye is drawn. A triangle with a
#: vertex behind the eye projects to nonsense, and rather than clip it
#: properly -- which would mean splitting triangles every frame, for a
#: case that cannot arise with a camera framing the whole scene from
#: outside it -- such a triangle is simply dropped.
NEAR = 1.0


class Camera:
    """Eye, target and field of view; turns world points into pixels."""

    def __init__(self, eye: Vec, target: Vec, fov: float,
                 rect: Tuple[float, float, float, float],
                 up: Vec = (0.0, 1.0, 0.0)) -> None:
        self.eye = eye
        self.rect = rect
        forward = _unit(_sub(target, eye))
        right = _unit(_cross(forward, up))
        self.forward = forward
        self.right = right
        self.up = _cross(right, forward)
        left, bottom, width, height = rect
        self.centre = (left + width / 2.0, bottom + height / 2.0)
        self.focal = (height / 2.0) / math.tan(math.radians(fov) / 2.0)

    def view_of(self, point: Vec) -> Vec:
        """*point* in camera axes: right, up, and distance in front."""
        away = _sub(point, self.eye)
        return (_dot(away, self.right), _dot(away, self.up),
                _dot(away, self.forward))

    def project(self, point: Vec) -> Tuple[float, float, float]:
        """Screen pixels and a depth. Depth is ``NEAR/z``; nearer is more."""
        x, y, z = self.view_of(point)
        if z < NEAR:
            z = NEAR
        scale = self.focal / z
        return (self.centre[0] + x * scale, self.centre[1] + y * scale,
                DEPTH_SPAN * NEAR / z)

    def frames(self, points: Sequence[Vec], slack: float = 1.07
               ) -> Tuple[bool, float]:
        """Whether every one of *points* lands inside the rect, and by how
        much the field of view would have to grow to hold them."""
        left, bottom, width, height = self.rect
        worst = 1.0
        for point in points:
            x, y, _depth = self.project(point)
            span_x = max(abs(x - self.centre[0]) / (width / 2.0), 1e-6)
            span_y = max(abs(y - self.centre[1]) / (height / 2.0), 1e-6)
            worst = max(worst, span_x * slack, span_y * slack)
        return worst <= 1.0, worst


class Light:
    """A key light, an ambient floor, a highlight and a depth haze."""

    def __init__(self, towards: Vec = (-0.45, 0.78, 0.44),
                 ambient: float = 0.32, key: float = 0.78,
                 shine: float = 0.55, hardness: float = 26.0,
                 haze: Colour = (26, 28, 34), fades_at: float = 150.0
                 ) -> None:
        self.towards = _unit(towards)
        self.ambient, self.key = ambient, key
        self.shine, self.hardness = shine, hardness
        self.haze, self.fades_at = haze, fades_at


class Solid:
    """One mesh, held on the card, re-projected when it moves.

    ``vertices`` and ``normals`` are in the mesh's own axes; ``indices``
    never change, so the index buffer is uploaded once and only the
    per-vertex position, depth and colour are written again. That is the
    whole of why this is affordable in Python: a loop of a hundred and
    twenty vertices costs a hundred and twenty projections a frame, not
    the seven hundred a triangle-at-a-time build would cost.
    """

    def __init__(self, vertices: Sequence[Vec], normals: Sequence[Vec],
                 indices: Sequence[int], colour: Colour,
                 batch: pyglet.graphics.Batch,
                 group: Optional[pyglet.graphics.Group] = None,
                 shine: float = 1.0) -> None:
        self.vertices = list(vertices)
        self.normals = list(normals)
        self.colour = colour
        self.shine = shine
        count = len(self.vertices)
        program = pyglet.shapes.get_default_shader()
        self.list = program.vertex_list_indexed(
            count, gl.GL_TRIANGLES, list(indices), batch=batch, group=group,
            position=('f', [0.0] * (2 * count)),
            zposition=('f', [0.0] * count),
            colors=('f', [0.0] * (4 * count)),
            translation=('f', [0.0] * (2 * count)))

    def place(self, camera: Camera, light: Light,
              turn: Optional[Tuple[Vec, Vec, Vec]] = None,
              offset: Vec = (0.0, 0.0, 0.0),
              tint: Optional[Colour] = None) -> None:
        """Re-project this solid, optionally rotated by *turn* and moved.

        *turn* is three world vectors saying where the mesh's own x, y
        and z axes point. ``None`` leaves the mesh in world axes, which
        is what everything that never moves uses.
        """
        colour = tint if tint is not None else self.colour
        eye = camera.eye
        towards = light.towards
        ambient, key = light.ambient, light.key
        shine, hardness = light.shine * self.shine, light.hardness
        haze, fades = light.haze, light.fades_at
        base_r, base_g, base_b = colour
        cx, cy = camera.centre
        focal = camera.focal
        right, up, forward = camera.right, camera.up, camera.forward

        places: List[float] = []
        depths: List[float] = []
        colours: List[float] = []
        for point, normal in zip(self.vertices, self.normals):
            if turn is not None:
                one, two, three = turn
                point = (one[0] * point[0] + two[0] * point[1]
                         + three[0] * point[2] + offset[0],
                         one[1] * point[0] + two[1] * point[1]
                         + three[1] * point[2] + offset[1],
                         one[2] * point[0] + two[2] * point[1]
                         + three[2] * point[2] + offset[2])
                normal = (one[0] * normal[0] + two[0] * normal[1]
                          + three[0] * normal[2],
                          one[1] * normal[0] + two[1] * normal[1]
                          + three[1] * normal[2],
                          one[2] * normal[0] + two[2] * normal[1]
                          + three[2] * normal[2])
            elif offset != (0.0, 0.0, 0.0):
                point = (point[0] + offset[0], point[1] + offset[1],
                         point[2] + offset[2])

            away = (point[0] - eye[0], point[1] - eye[1], point[2] - eye[2])
            depth = (away[0] * forward[0] + away[1] * forward[1]
                     + away[2] * forward[2])
            if depth < NEAR:
                depth = NEAR
            scale = focal / depth
            places.append(cx + (away[0] * right[0] + away[1] * right[1]
                                + away[2] * right[2]) * scale)
            places.append(cy + (away[0] * up[0] + away[1] * up[1]
                                + away[2] * up[2]) * scale)
            depths.append(DEPTH_SPAN * NEAR / depth)

            lit = (normal[0] * towards[0] + normal[1] * towards[1]
                   + normal[2] * towards[2])
            lit = ambient + key * (lit if lit > 0.0 else 0.0)
            # Blinn's halfway vector: cheap, and on a curved metal
            # surface it is most of what says the surface is curved.
            far = math.sqrt(away[0] ** 2 + away[1] ** 2 + away[2] ** 2) or 1.0
            half = (towards[0] - away[0] / far, towards[1] - away[1] / far,
                    towards[2] - away[2] / far)
            size = math.sqrt(half[0] ** 2 + half[1] ** 2
                             + half[2] ** 2) or 1.0
            gloss = (normal[0] * half[0] + normal[1] * half[1]
                     + normal[2] * half[2]) / size
            gloss = shine * (gloss ** hardness) if gloss > 0.0 else 0.0
            mist = min(1.0, depth / fades) ** 2
            for channel, base in ((0, base_r), (1, base_g), (2, base_b)):
                value = base * lit + 255.0 * gloss
                value = value + (haze[channel] - value) * mist
                colours.append(min(1.0, max(0.0, value / 255.0)))
            colours.append(1.0)

        self.list.position[:] = places
        self.list.zposition[:] = depths
        self.list.colors[:] = colours

    def reshape(self, vertices: Sequence[Vec],
                normals: Sequence[Vec]) -> None:
        """Swap in new geometry of the same size, keeping the index buffer.

        For the one thing here whose *shape* changes rather than only its
        place: the slice of wire the sight view is looking down, which is
        a different piece of wire every frame. The vertex count is fixed
        by construction, so the list allocated when the level was dealt
        goes on being the list.
        """
        if len(vertices) != len(self.vertices):
            raise ValueError('reshape needs the same vertex count')
        self.vertices = list(vertices)
        self.normals = list(normals)

    def delete(self) -> None:
        try:
            self.list.delete()
        except Exception:
            pass


# --- meshes ---------------------------------------------------------------

def tube(points: Sequence[Vec], tangents: Sequence[Vec], radius: float,
         sides: int = 8, taper: int = 0) -> Tuple[List[Vec], List[Vec],
                                                  List[int]]:
    """A circle of radius *radius* swept along a polyline.

    The ring of vertices at each station is carried forward by
    **parallel transport** — each frame is the previous one rotated by
    the smallest rotation taking the old tangent onto the new — rather
    than rebuilt from a fixed world axis. The difference shows the
    moment a wire turns over: a frame taken from the world up-vector
    spins about the tube as the tangent passes vertical, and the seam of
    the mesh corkscrews visibly along a wire that is perfectly smooth.
    """
    verts: List[Vec] = []
    norms: List[Vec] = []
    frame = _perpendicular(tangents[0])
    last = len(points) - 1
    for station, (point, tangent) in enumerate(zip(points, tangents)):
        frame = _transported(frame, tangent)
        other = _cross(tangent, frame)
        # The last `taper` stations draw in to a point, so a tube that
        # runs out of geometry fades away instead of ending on the open
        # end of a pipe, which the eye reads as an object.
        thin = radius
        if taper and last - station < taper:
            thin = radius * (last - station) / float(taper)
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides
            normal = _unit(_add(_scale(frame, math.cos(angle)),
                                _scale(other, math.sin(angle))))
            norms.append(normal)
            verts.append(_add(point, _scale(normal, thin)))
    indices: List[int] = []
    for station in range(len(points) - 1):
        here, ahead = station * sides, (station + 1) * sides
        for side in range(sides):
            step = (side + 1) % sides
            indices += [here + side, ahead + side, ahead + step,
                        here + side, ahead + step, here + step]
    return verts, norms, indices


def torus(hole: float, thickness: float, around: int = 24,
          through: int = 8) -> Tuple[List[Vec], List[Vec], List[int]]:
    """The loop, in its own axes: hole in the xy plane, axis along z.

    *hole* is the radius of the opening the wire must pass through, and
    *thickness* the radius of the metal around it — so the loop's own
    ring runs at ``hole + thickness`` and the geometry agrees with what
    :func:`neural_workshop.buzzwire.crossing_contact` decides, which is
    the one thing about this mesh that has to be true rather than
    merely convincing.
    """
    middle = hole + thickness
    verts: List[Vec] = []
    norms: List[Vec] = []
    for major in range(around):
        phi = 2.0 * math.pi * major / around
        out = (math.cos(phi), math.sin(phi), 0.0)
        for minor in range(through):
            theta = 2.0 * math.pi * minor / through
            normal = (out[0] * math.cos(theta), out[1] * math.cos(theta),
                      math.sin(theta))
            norms.append(normal)
            verts.append((out[0] * middle + normal[0] * thickness,
                          out[1] * middle + normal[1] * thickness,
                          normal[2] * thickness))
    indices: List[int] = []
    for major in range(around):
        here = major * through
        ahead = ((major + 1) % around) * through
        for minor in range(through):
            step = (minor + 1) % through
            indices += [here + minor, ahead + minor, ahead + step,
                        here + minor, ahead + step, here + step]
    return verts, norms, indices


def rod(start: Vec, end: Vec, radius: float, sides: int = 8,
        capped: bool = True) -> Tuple[List[Vec], List[Vec], List[int]]:
    """A capped cylinder between two points. Posts, handles, feet."""
    along = _unit(_sub(end, start))
    frame = _perpendicular(along)
    other = _cross(along, frame)
    verts: List[Vec] = []
    norms: List[Vec] = []
    for point in (start, end):
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides
            normal = _add(_scale(frame, math.cos(angle)),
                          _scale(other, math.sin(angle)))
            norms.append(normal)
            verts.append(_add(point, _scale(normal, radius)))
    indices: List[int] = []
    for side in range(sides):
        step = (side + 1) % sides
        indices += [side, sides + side, sides + step,
                    side, sides + step, step]
    if capped:
        for point, facing, wind in ((start, _scale(along, -1.0), False),
                                    (end, along, True)):
            hub = len(verts)
            verts.append(point)
            norms.append(facing)
            first = 0 if point is start else sides
            for side in range(sides):
                step = (side + 1) % sides
                edge = (first + side, first + step)
                indices += [hub, edge[0], edge[1]] if wind else [
                    hub, edge[1], edge[0]]
    return verts, norms, indices


def slab(centre: Vec, half: Vec) -> Tuple[List[Vec], List[Vec], List[int]]:
    """An axis-aligned box. The board the whole thing is bolted to."""
    verts: List[Vec] = []
    norms: List[Vec] = []
    indices: List[int] = []
    faces = ((0, 1, 2, 1.0), (0, 2, 1, -1.0), (1, 2, 0, 1.0),
             (1, 0, 2, -1.0), (2, 0, 1, 1.0), (2, 1, 0, -1.0))
    for axis, first, second, way in faces:
        normal = [0.0, 0.0, 0.0]
        normal[axis] = way
        base = len(verts)
        for corner in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)):
            point = [0.0, 0.0, 0.0]
            point[axis] = way * half[axis]
            point[first] = corner[0] * half[first]
            point[second] = corner[1] * half[second]
            verts.append((centre[0] + point[0], centre[1] + point[1],
                          centre[2] + point[2]))
            norms.append(tuple(normal))
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]
    return verts, norms, indices


def merge(*meshes: Tuple[Sequence[Vec], Sequence[Vec], Sequence[int]]
          ) -> Tuple[List[Vec], List[Vec], List[int]]:
    """Join meshes into one, so one vertex list carries all of them."""
    verts: List[Vec] = []
    norms: List[Vec] = []
    indices: List[int] = []
    for mesh_verts, mesh_norms, mesh_indices in meshes:
        base = len(verts)
        verts.extend(mesh_verts)
        norms.extend(mesh_norms)
        indices.extend(index + base for index in mesh_indices)
    return verts, norms, indices


# --- drawing --------------------------------------------------------------

class DepthPass:
    """Draw a batch with the depth buffer on, and put GL back afterwards.

    The rest of the workshop draws flat, in the order things were added,
    and would be wrong if it were depth-tested — every label sits at zero
    and would fight whatever else did. So the test is switched on around
    this batch and off again, and nothing outside knows it happened.

    *inside* clips the draw to a rectangle. Two cameras looking at the
    same world into two panels of one screen is two batches, and a piece
    of geometry that runs off the edge of its panel would otherwise land
    in the other one — which is not a cosmetic problem here, because the
    other panel is the one the whole wire is drawn in.
    """

    def __init__(self, batch: pyglet.graphics.Batch,
                 inside: Optional[Tuple[float, float, float, float]] = None
                 ) -> None:
        self.batch = batch
        self.inside = inside

    def draw(self) -> None:
        gl.glEnable(gl.GL_DEPTH_TEST)
        clipping = False
        if self.inside is not None:
            left, bottom, width, height = self.inside
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(int(left), int(bottom), max(0, int(width)),
                         max(0, int(height)))
            clipping = True
        try:
            self.batch.draw()
        finally:
            if clipping:
                gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDisable(gl.GL_DEPTH_TEST)


# --- vector helpers -------------------------------------------------------

def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(a: Vec) -> Vec:
    size = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (1.0, 0.0, 0.0) if size < 1e-12 else (a[0] / size, a[1] / size,
                                                 a[2] / size)


def _perpendicular(along: Vec) -> Vec:
    """Any unit vector at right angles to *along*."""
    other = (0.0, 0.0, 1.0) if abs(along[1]) > 0.9 else (0.0, 1.0, 0.0)
    return _unit(_cross(other, along))


def _transported(frame: Vec, tangent: Vec) -> Vec:
    """*frame*, taken across to be perpendicular to *tangent* again."""
    return _unit(_sub(frame, _scale(tangent, _dot(frame, tangent))))


__all__ = ['Camera', 'Colour', 'DEPTH_SPAN', 'DepthPass', 'Light', 'NEAR',
           'Solid', 'Vec', 'merge', 'rod', 'slab', 'torus', 'tube']
