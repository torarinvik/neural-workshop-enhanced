# -*- coding: utf-8 -*-
"""A small real-3D stage: meshes, a lit shader, shadows, and a place to put it.

Everything else drawn in this workshop is flat, and two screens that
call themselves three-dimensional — the 3D Maze and 3D Sokoban — are
ray casters painting columns of :class:`pyglet.shapes.Rectangle`. That
is the right tool for a corridor seen from inside it, where every
surface is vertical and the only question is how far away it is.

It is the wrong tool for a *tilting tray*, and the reason is the whole
of the Marble Maze: the control the player is learning is the tilt, and
a tilt is a rotation of a plane out of the screen. A ray caster cannot
draw one. So this module is a real perspective pipeline — a depth
buffer, a directional light, a shadow map, and materials that know
whether they are oak or steel.

**It is deliberately not a scene graph.** There is one shader with a
handful of material branches, meshes are plain vertex lists, and the
caller hands over a list of draws in the order it wants them. A tray,
its walls, its pits and four marbles is nine draw calls; anything
clever would cost more to read than it saves.

Three things here are less obvious than they look.

**Everything renders offscreen at 4x multisampling and is then blitted
into place.** Not for grandeur: the window's own framebuffer has no
multisample buffer, and this task is made of sphere silhouettes and
long straight wall edges, which are the two things that alias worst.
The blit also confines the whole 3D pass to a rectangle, which is how
the stage keeps clear of the strip the agent boundary reads for a
verdict — see :func:`neural_workshop.ui.verdict.above_the_band`.

**Holes are cut in the shader, and their rims are alpha-to-coverage.**
A hole is a circle in a wooden plane, and cutting circles out of a mesh
means either a stair-stepped edge or a triangulator. Discarding
fragments inside the circle is neither — but a plain discard is a hard
per-pixel edge, and the tray's holes are the roundest things on screen.

The tempting fix is per-sample shading, and it is a trap: measured on
the top rung at 1880x886, ``glMinSampleShading(1)`` costs **39.6ms a
frame against 3.8ms**, because it runs this entire shader — wood noise
and all — four times per pixel over the whole tray, to smooth an edge
that is a few thousand pixels long. Alpha-to-coverage gets the same
rim by handing the hardware a coverage fraction and letting it choose a
sample mask out of the multisampling that is already paid for.

**The GL state this leaves behind is restored by hand.** pyglet's 2D
drawing assumes depth testing off, culling off, alpha blending on, the
default framebuffer bound and the viewport covering it. A 3D pass
changes all five, and getting any of them back wrong does not fail
here — it fails in whatever label the task draws next.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import ctypes
import math
from typing import List, NamedTuple, Optional, Sequence, Tuple

import pyglet
from pyglet import gl
from pyglet.math import Mat4, Vec3

#: Material ids, matching the branches in :data:`FRAGMENT`.
OAK, STAIN, STEEL, PIT, CUP, BRASS = 0, 1, 2, 3, 4, 5

#: Shadow map edge, texels. 1024 is enough for a tray filling the frame;
#: the marble's contact shadow is the acid test and it holds.
SHADOW_SIZE = 1024

#: How many samples the offscreen colour buffer gets. Four is the knee:
#: eight costs about a third more for an edge nobody reports seeing.
SAMPLES = 4

#: The most holes the floor shader will cut. The ladder's top rung asks
#: for thirty-eight; the array is sized well past that because
#: overflowing it silently would leave real holes solid, and a solid
#: hole is a hazard the physics still applies and the player cannot see.
MAX_HOLES = 96


VERTEX = """#version 330 core
in vec3 position;
in vec3 normal;

uniform mat4 view_proj;
uniform mat4 model;
uniform vec3 normal_scale;
uniform mat4 light_matrix;

out vec3 v_world;
out vec3 v_normal;
out vec3 v_local;
out vec4 v_shadow;

void main() {
    vec4 world = model * vec4(position, 1.0);
    v_world = world.xyz;
    // model carries a non-uniform scale, so a normal needs the inverse
    // transpose. For an axis-aligned scale that is the reciprocal, and
    // pre-multiplying by the reciprocal squared lets the same matrix do
    // both jobs: model * (n / s^2) == R * (n / s).
    v_normal = mat3(model) * (normal * normal_scale);
    v_local = position;
    v_shadow = light_matrix * world;
    gl_Position = view_proj * world;
}
"""


FRAGMENT = """#version 330 core
in vec3 v_world;
in vec3 v_normal;
in vec3 v_local;
in vec4 v_shadow;

uniform int material;
uniform vec3 tint;
uniform vec3 eye;
uniform vec3 light_dir;      // pointing *from* the surface to the light
uniform vec3 light_colour;
uniform vec3 sky_colour;
uniform vec3 ground_colour;
// A plain sampler rather than a sampler2DShadow, and the comparison
// done by hand below. pyglet's shader reflection has no entry for
// GL_SAMPLER_2D_SHADOW and raises KeyError building the program, so
// hardware PCF is not reachable from here. It costs nothing: the
// filtering below is a 3x3 loop either way, and comparing in the
// shader is one operator per tap.
uniform sampler2D shadow_map;
uniform float shadow_texel;

//: The marble's own surface, baked out of the source asset by
//: tools/bake_marble_textures.py. `marble_maps` is nought when they
//: could not be loaded, and the shader falls back to procedural
//: mottling — a machine missing them should render a plainer marble,
//: not no marble.
uniform sampler2D marble_colour;
uniform sampler2D marble_rough;
uniform sampler2D marble_normal;
uniform int marble_maps;
uniform mat4 model;

uniform int hole_count;
uniform vec4 holes[%(MAX_HOLES)d];   // x, y, radius, 1 if it is the cup
uniform int cut_holes;
uniform float grain_seed;

out vec4 frag;

// --- a cheap value noise, enough for grain ---------------------------
float hash(vec3 p) {
    return fract(sin(dot(p, vec3(17.13, 91.7, 47.31))) * 43758.5453);
}

float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float n000 = hash(i + vec3(0, 0, 0));
    float n100 = hash(i + vec3(1, 0, 0));
    float n010 = hash(i + vec3(0, 1, 0));
    float n110 = hash(i + vec3(1, 1, 0));
    float n001 = hash(i + vec3(0, 0, 1));
    float n101 = hash(i + vec3(1, 0, 1));
    float n011 = hash(i + vec3(0, 1, 1));
    float n111 = hash(i + vec3(1, 1, 1));
    return mix(mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y),
               mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y), f.z);
}

float fbm(vec3 p) {
    return 0.5 * noise(p) + 0.25 * noise(p * 2.03)
         + 0.155 * noise(p * 4.01) + 0.075 * noise(p * 8.05);
}

// Growth rings are cylinders round the log's axis. Put the axis
// outside the board and the surface cuts those cylinders in arcs,
// which is the figure a sawn plank actually shows.
//
// Two things had to be got right here and neither is the ring
// frequency. The first is that the arcs have to *wander along the
// board*: rings taken straight off the radius give a set of perfectly
// parallel, perfectly even lines, and a tray drawn that way does not
// look like poor wood, it looks like corduroy. The wander is a
// domain warp — several rings' worth of low-frequency noise added to
// the radius before it is wrapped — and it is what turns stripes into
// cathedral figure. The second is that the early-to-late wood
// contrast is much gentler than a first guess: most of what tells the
// eye "this is timber" is the fine fibre, not the bands.
vec3 timber(vec3 base, vec3 dark) {
    vec3 p = v_local;
    vec2 about = vec2(p.x + 0.16 + grain_seed * 0.05, p.y + 0.19);
    float ring = length(about) * 190.0;
    ring += 9.0 * fbm(p * vec3(4.0, 4.0, 1.6))
          + 2.2 * fbm(p * vec3(17.0, 17.0, 6.0));
    float band = fract(ring);
    float grain = smoothstep(0.24, 0.44, band)
                * (1.0 - smoothstep(0.52, 0.80, band));
    float fibre = fbm(p * vec3(380.0, 380.0, 30.0)) - 0.5;
    float blotch = fbm(p * vec3(9.0, 9.0, 3.5)) - 0.5;
    vec3 wood = mix(base, dark,
                    clamp(grain * 0.52 + blotch * 0.24 + 0.09, 0.0, 1.0));
    return clamp(wood * (1.0 + fibre * 0.12), 0.0, 1.0);
}

float shadowed(vec3 n, vec3 l) {
    if (v_shadow.w <= 0.0) return 1.0;
    vec3 c = v_shadow.xyz / v_shadow.w;
    if (c.x < 0.0 || c.x > 1.0 || c.y < 0.0 || c.y > 1.0 || c.z > 1.0)
        return 1.0;
    // Slope-scaled: a surface edge-on to the light needs far more bias
    // than one facing it, and a single constant either acnes the floor
    // or unsticks the marble's own shadow from under it.
    float slope = clamp(1.0 - dot(n, l), 0.0, 1.0);
    float bias = 0.0009 + 0.0042 * slope * slope;
    float lit = 0.0;
    for (int j = -1; j <= 1; ++j) {
        for (int i = -1; i <= 1; ++i) {
            vec2 at = c.xy + vec2(float(i), float(j)) * shadow_texel;
            float nearest = texture(shadow_map, at).r;
            lit += (c.z - bias <= nearest) ? 1.0 : 0.0;
        }
    }
    return lit / 9.0;
}

// A stand-in room: bright above, the table below, and a *hard* line
// between them. The hardness is the point — what makes a sphere read as
// polished metal rather than as grey paint is the horizon of the room
// bent across it, and a soft gradient reads as neither.
vec3 environment(vec3 dir) {
    float up = dir.y;
    // Deliberately dim. A room reflected at full brightness clips the
    // whole upper hemisphere of a sphere to white, and a white circle
    // with a rim is a ping-pong ball. Chrome is mid-grey nearly
    // everywhere, dark underneath, with one small blazing spot where
    // the lamp is — and the lamp is added by the caller, not here.
    vec3 above = mix(sky_colour * 0.28, sky_colour * 0.78,
                     clamp(up * 1.8, 0.0, 1.0));
    vec3 below = ground_colour * (0.20 + 0.58 * clamp(-up * 2.4, 0.0, 1.0));
    return mix(below, above, smoothstep(-0.035, 0.035, up));
}

void main() {
    // How much of this fragment is board rather than hole. Positive
    // outside every hole, negative inside one, in metres.
    float coverage = 1.0;
    if (cut_holes == 1) {
        float edge = 1e9;
        for (int i = 0; i < hole_count; ++i) {
            edge = min(edge, length(v_local.xz - holes[i].xy) - holes[i].z);
        }
        float fade = max(fwidth(edge), 1e-6);
        coverage = clamp(edge / fade + 0.5, 0.0, 1.0);
        if (coverage <= 0.0) discard;
    }

    vec3 n = normalize(v_normal);
    vec3 view = normalize(eye - v_world);
    if (!gl_FrontFacing) n = -n;
    vec3 l = normalize(light_dir);
    vec3 half_way = normalize(l + view);

    float ndl = max(dot(n, l), 0.0);
    float lit = shadowed(n, l);
    // Hemisphere ambient rather than a flat term: the underside of a
    // wall picks up the tray, the top picks up the room.
    vec3 ambient = mix(ground_colour, sky_colour, n.y * 0.5 + 0.5);

    vec3 albedo = tint;
    float gloss = 24.0;
    float spec_strength = 0.10;
    float ambient_strength = 0.42;

    if (material == %(OAK)d) {
        albedo = timber(tint, tint * vec3(0.55, 0.44, 0.34));
        gloss = 40.0; spec_strength = 0.16;
    } else if (material == %(STAIN)d) {
        albedo = timber(tint, tint * vec3(0.42, 0.36, 0.32));
        gloss = 28.0; spec_strength = 0.11;
    } else if (material == %(CUP)d) {
        gloss = 60.0; spec_strength = 0.22; ambient_strength = 0.5;
    } else if (material == %(BRASS)d) {
        gloss = 96.0; spec_strength = 0.55; ambient_strength = 0.35;
    } else if (material == %(PIT)d) {
        // The inside of a hole is the board's own thickness, and it is
        // sawn timber like the rest of it — one side of the shaft
        // catches the lamp and the rest falls away into the dark.
        // Shading it as a flat dark disc instead is what makes holes
        // read as stickers on the tray rather than drops through it.
        float depth = clamp(1.0 + v_local.y * 26.0, 0.0, 1.0);
        float side = max(dot(n, l), 0.0);
        // A trace of bounce so the unlit side of a shaft is dark
        // rather than absent. At nought it reads as a sticker again.
        vec3 wall = tint * (0.05 + 0.10 * ambient + 0.92 * side)
                  * depth * depth;
        frag = vec4(clamp(wall, 0.0, 1.0), coverage);
        return;
    } else if (material == %(STEEL)d) {
        // Metal: no diffuse worth the name. What a ball bearing looks
        // like is a room bent round a sphere, with the lamp in it as a
        // small hard disc, and a rim that goes bright at grazing
        // angles because that is what Fresnel does to a conductor.
        //
        // The lamp is taken off the *reflection* vector rather than
        // off a Blinn-Phong half-vector: a half-vector highlight is a
        // soft blob that reads as varnish, and the difference between
        // varnish and chrome is entirely in how hard that edge is.
        // Micro-imperfection, and it is load-bearing rather than
        // decorative: a mathematically perfect sphere in a smooth room
        // shows no sign of turning at all, so a rolling marble sits
        // there looking painted on. Everything below is in the ball's
        // own space, so it turns with the ball and the roll becomes
        // something the eye can read.
        vec3 shine = tint;
        float polish = 1.0;
        vec3 bumped = n;
        if (marble_maps == 1) {
            // Equirectangular, worked out from the object-space
            // position rather than carried on the mesh. A UV sphere's
            // natural coordinates are exactly this, and computing them
            // here keeps the vertex format down to position and normal
            // for every other mesh on the stage.
            vec3 ball = normalize(v_local);
            vec2 uv = vec2(atan(ball.z, ball.x) * 0.1591549 + 0.5,
                           acos(clamp(ball.y, -1.0, 1.0)) * 0.3183099);
            // The map's *luminance*, not its colour. Multiplying the
            // hue in as well tips a neutral chrome ball towards the
            // blue-grey the asset was lit in, and a blue ball reads as
            // glass rather than as steel. What is wanted from it is
            // the variation, which is entirely in the brightness.
            float grain = dot(texture(marble_colour, uv).rgb,
                              vec3(0.299, 0.587, 0.114));
            shine = tint * (0.70 + 0.88 * grain);
            // glTF packs roughness in green and metalness in blue.
            polish = 1.0 - texture(marble_rough, uv).g;
            // Tangent frame built from the sphere itself: for a ball at
            // the origin the object normal *is* the position, and the
            // u direction is the horizontal perpendicular to it. No
            // tangent attribute needed, and none is uploaded.
            vec3 across = normalize(vec3(-ball.z, 0.0, ball.x)
                                    + vec3(1e-6, 0.0, 0.0));
            vec3 down = cross(ball, across);
            vec3 bump = texture(marble_normal, uv).xyz * 2.0 - 1.0;
            vec3 local = normalize(across * bump.x + down * bump.y
                                   + ball * bump.z);
            // Eased towards the true normal: the source map is for a
            // ball filling a render, and at thirty pixels across its
            // full strength is a sphere that reads as gravel.
            bumped = normalize(mat3(model) * mix(ball, local, 0.22));
        } else {
            float mottle = fbm(v_local * 640.0) - 0.5;
            shine = tint * (1.0 + mottle * 0.22);
        }

        vec3 bounce = reflect(-view, bumped);
        vec3 mirrored = environment(bounce);
        float tight = mix(26.0, 190.0, polish);
        float lamp = pow(max(dot(bounce, l), 0.0), tight);
        float sheen = pow(max(dot(bounce, l), 0.0), 9.0);
        float fresnel = 0.05 + 0.95
                      * pow(1.0 - max(dot(bumped, view), 0.0), 5.0);
        vec3 colour = shine * mirrored * (0.34 + 0.66 * lit)
                    + light_colour * lamp * (1.4 + 1.4 * polish) * lit
                    + light_colour * sheen * 0.14 * lit
                    + sky_colour * fresnel * 0.16;
        frag = vec4(clamp(colour, 0.0, 1.0), coverage);
        return;
    }

    float spec = pow(max(dot(n, half_way), 0.0), gloss) * spec_strength;
    vec3 colour = albedo * (ambient * ambient_strength
                            + light_colour * ndl * lit * 0.85)
                + light_colour * spec * lit;
    frag = vec4(clamp(colour, 0.0, 1.0), coverage);
}
""" % {'MAX_HOLES': MAX_HOLES, 'OAK': OAK, 'STAIN': STAIN, 'STEEL': STEEL,
       'PIT': PIT, 'CUP': CUP, 'BRASS': BRASS}


DEPTH_VERTEX = """#version 330 core
in vec3 position;
// The *unbiased* light clip matrix. The main shader's `light_matrix`
// carries a half-and-shift so its lookup lands in a [0,1] depth
// texture; rendering with that one instead squeezes the whole scene
// into the upper-right quadrant of the map and halves every depth,
// which does not look like a bug — it looks like shadows that are
// merely too faint to see.
uniform mat4 light_clip;
uniform mat4 model;
uniform int hole_count;
uniform vec4 holes[%(MAX_HOLES)d];
uniform int cut_holes;
out vec3 v_local;
void main() {
    v_local = position;
    gl_Position = light_clip * model * vec4(position, 1.0);
}
""" % {'MAX_HOLES': MAX_HOLES}


DEPTH_FRAGMENT = """#version 330 core
in vec3 v_local;
uniform int hole_count;
uniform vec4 holes[%(MAX_HOLES)d];
uniform int cut_holes;
void main() {
    // The floor casts too, and a floor that casts through its own holes
    // is a floor with no light coming up them. The cut has to happen in
    // both passes or the pits go black.
    if (cut_holes == 1) {
        for (int i = 0; i < hole_count; ++i) {
            if (length(v_local.xz - holes[i].xy) < holes[i].z) discard;
        }
    }
}
""" % {'MAX_HOLES': MAX_HOLES}


COMPOSITE_VERTEX = """#version 330 core
in vec2 position;
out vec2 v_uv;
void main() {
    v_uv = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
}
"""


COMPOSITE_FRAGMENT = """#version 330 core
in vec2 v_uv;
uniform sampler2D scene;
out vec4 frag;
void main() {
    frag = texture(scene, v_uv);
}
"""


class Mesh:
    """Positions, normals and indices, uploaded once and drawn many times."""

    def __init__(self, program, positions: Sequence[float],
                 normals: Sequence[float], indices: Sequence[int]) -> None:
        self.count = len(indices)
        self.vlist = program.vertex_list_indexed(
            len(positions) // 3, gl.GL_TRIANGLES, tuple(indices),
            position=('f', tuple(positions)),
            normal=('f', tuple(normals)))
        #: The same geometry registered against the depth-only program.
        self.shadow_vlist = None

    def attach_shadow(self, program, positions: Sequence[float],
                      indices: Sequence[int]) -> None:
        self.shadow_vlist = program.vertex_list_indexed(
            len(positions) // 3, gl.GL_TRIANGLES, tuple(indices),
            position=('f', tuple(positions)))

    def delete(self) -> None:
        for vlist in (self.vlist, self.shadow_vlist):
            if vlist is not None:
                try:
                    vlist.delete()
                except Exception:
                    pass
        self.vlist = self.shadow_vlist = None


class Builder:
    """Accumulates triangles, so many boxes become one mesh and one call."""

    def __init__(self) -> None:
        self.positions: List[float] = []
        self.normals: List[float] = []
        self.indices: List[int] = []

    @property
    def empty(self) -> bool:
        return not self.indices

    def _base(self) -> int:
        return len(self.positions) // 3

    def face(self, quad: Sequence[Tuple[float, float, float]],
             normal: Tuple[float, float, float]) -> None:
        base = self._base()
        for point in quad:
            self.positions.extend(point)
            self.normals.extend(normal)
        self.indices.extend((base, base + 1, base + 2,
                             base, base + 2, base + 3))

    def box(self, x0: float, y0: float, z0: float,
            x1: float, y1: float, z1: float) -> None:
        """An axis-aligned box, wound anticlockwise seen from outside."""
        self.face(((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)),
                  (0.0, 1.0, 0.0))
        self.face(((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
                  (0.0, -1.0, 0.0))
        self.face(((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
                  (0.0, 0.0, 1.0))
        self.face(((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)),
                  (0.0, 0.0, -1.0))
        self.face(((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)),
                  (1.0, 0.0, 0.0))
        self.face(((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
                  (-1.0, 0.0, 0.0))

    def quad_xz(self, x0: float, z0: float, x1: float, z1: float,
                y: float) -> None:
        self.face(((x0, y, z1), (x1, y, z1), (x1, y, z0), (x0, y, z0)),
                  (0.0, 1.0, 0.0))

    def tube(self, cx: float, cz: float, radius: float, top: float,
             bottom: float, segments: int = 22,
             floor_disc: bool = True) -> None:
        """The inside of a hole: a cylinder seen from within, and a base."""
        base = self._base()
        for step in range(segments):
            angle = 2.0 * math.pi * step / segments
            nx, nz = math.cos(angle), math.sin(angle)
            x, z = cx + nx * radius, cz + nz * radius
            # Normals point inwards; this surface is only ever seen from
            # inside the pit.
            self.positions.extend((x, top, z))
            self.normals.extend((-nx, 0.0, -nz))
            self.positions.extend((x, bottom, z))
            self.normals.extend((-nx, 0.0, -nz))
        for step in range(segments):
            a = base + step * 2
            b = base + ((step + 1) % segments) * 2
            self.indices.extend((a, b, b + 1, a, b + 1, a + 1))
        if floor_disc:
            centre = self._base()
            self.positions.extend((cx, bottom, cz))
            self.normals.extend((0.0, 1.0, 0.0))
            rim = self._base()
            for step in range(segments):
                angle = 2.0 * math.pi * step / segments
                self.positions.extend((cx + math.cos(angle) * radius, bottom,
                                       cz + math.sin(angle) * radius))
                self.normals.extend((0.0, 1.0, 0.0))
            for step in range(segments):
                self.indices.extend((centre, rim + step,
                                     rim + (step + 1) % segments))

    def ring(self, cx: float, cz: float, inner: float, outer: float,
             y: float, segments: int = 30) -> None:
        """A flat annulus, for the collar around the cup."""
        base = self._base()
        for step in range(segments):
            angle = 2.0 * math.pi * step / segments
            ca, sa = math.cos(angle), math.sin(angle)
            self.positions.extend((cx + ca * inner, y, cz + sa * inner))
            self.normals.extend((0.0, 1.0, 0.0))
            self.positions.extend((cx + ca * outer, y, cz + sa * outer))
            self.normals.extend((0.0, 1.0, 0.0))
        for step in range(segments):
            a = base + step * 2
            b = base + ((step + 1) % segments) * 2
            self.indices.extend((a, a + 1, b + 1, a, b + 1, b))

    def sphere(self, radius: float, rings: int = 26,
               segments: int = 34) -> None:
        """A UV sphere at the origin. The marble, and nothing else."""
        base = self._base()
        for ring in range(rings + 1):
            phi = math.pi * ring / rings
            y, r = math.cos(phi), math.sin(phi)
            for step in range(segments + 1):
                theta = 2.0 * math.pi * step / segments
                nx = r * math.cos(theta)
                nz = r * math.sin(theta)
                self.positions.extend((nx * radius, y * radius, nz * radius))
                self.normals.extend((nx, y, nz))
        for ring in range(rings):
            for step in range(segments):
                a = base + ring * (segments + 1) + step
                b = a + segments + 1
                self.indices.extend((a, b, b + 1, a, b + 1, a + 1))

    def build(self, program, depth_program=None) -> Mesh:
        mesh = Mesh(program, self.positions, self.normals, self.indices)
        if depth_program is not None:
            mesh.attach_shadow(depth_program, self.positions, self.indices)
        return mesh


class Draw(NamedTuple):
    """One mesh, placed and dressed."""

    mesh: Mesh
    model: Mat4
    #: Reciprocal-squared scale, for the normal transform.
    normal_scale: Tuple[float, float, float]
    material: int
    tint: Tuple[float, float, float]
    #: Whether the floor shader's hole cutter runs for this draw.
    cut_holes: bool = False
    #: Whether it casts into the shadow map.
    casts: bool = True


class Light(NamedTuple):
    #: Unit vector from the scene towards the light.
    direction: Tuple[float, float, float]
    colour: Tuple[float, float, float]
    sky: Tuple[float, float, float]
    ground: Tuple[float, float, float]
    #: Half-extent of the shadow map's orthographic box, metres.
    span: float


class Stage:
    """The offscreen 3D pass, and the blit that puts it on the window."""

    def __init__(self) -> None:
        self.program = None
        self.depth_program = None
        self.composite = None
        self.ok = False
        self._size: Tuple[int, int] = (0, 0)
        self._colour_fbo = self._colour_rb = self._depth_rb = None
        self._resolve_fbo = self._resolve_tex = None
        self._shadow_fbo = self._shadow_tex = None
        self._screen = None
        self._sample_shading = False
        self.grain_seed = 0.0
        self._hole_count = 0
        self._marble_tex: Tuple[gl.GLuint, ...] = ()
        #: Why the stage is unusable, when it is. Kept rather than
        #: dropped: a swallowed shader compile error is a black screen
        #: with no way back to the cause, and this one is read by the
        #: task's own status line and by :mod:`tests.test_ui_marblemaze`.
        self.trouble: Optional[str] = None
        try:
            self._build_programs()
            self._build_shadow_target()
            self.ok = True
        except Exception as exc:
            # A machine that cannot compile this has no business
            # crashing the workshop over it. The task checks `ok` and
            # says so on screen rather than opening a black window.
            self.trouble = '%s: %s' % (type(exc).__name__, exc)
            self.ok = False

    # --- setup -----------------------------------------------------------

    def _build_programs(self) -> None:
        from pyglet.graphics.shader import Shader, ShaderProgram
        self.program = ShaderProgram(Shader(VERTEX, 'vertex'),
                                     Shader(FRAGMENT, 'fragment'))
        self.depth_program = ShaderProgram(Shader(DEPTH_VERTEX, 'vertex'),
                                           Shader(DEPTH_FRAGMENT, 'fragment'))
        self.composite = ShaderProgram(
            Shader(COMPOSITE_VERTEX, 'vertex'),
            Shader(COMPOSITE_FRAGMENT, 'fragment'))
        self._screen = self.composite.vertex_list_indexed(
            4, gl.GL_TRIANGLES, (0, 1, 2, 0, 2, 3),
            position=('f', (-1., -1., 1., -1., 1., 1., -1., 1.)))

    def load_marble_maps(self, colour: str, rough: str, normal: str) -> bool:
        """Take the marble's baked surface maps, or go without them.

        Going without is a real path rather than a courtesy: the maps
        are baked out of an asset that is not in this repository, so a
        checkout can legitimately be missing them, and a missing
        texture must give a plainer marble rather than a black one.
        :data:`FRAGMENT` keeps the procedural mottling for exactly that
        case and ``marble_maps`` is what chooses between them.
        """
        if not self.ok:
            return False
        try:
            self._marble_tex = tuple(
                self._upload(path) for path in (colour, rough, normal))
        except Exception:
            self._marble_tex = ()
            return False
        return True

    @staticmethod
    def _upload(path: str) -> gl.GLuint:
        # Opened here and closed here. pyglet.image.load(path) leaves
        # the handle to the garbage collector, which on a task that is
        # opened and closed all through a test run is three descriptors
        # a time and a ResourceWarning apiece.
        with open(path, 'rb') as handle:
            picture = pyglet.image.load(path, file=handle)
            data = picture.get_image_data()
            rgba = data.get_data('RGBA', data.width * 4)
        handle = gl.GLuint(0)
        gl.glGenTextures(1, ctypes.byref(handle))
        gl.glBindTexture(gl.GL_TEXTURE_2D, handle)
        buf = (gl.GLubyte * len(rgba))(*rgba)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, data.width,
                        data.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER,
                           gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER,
                           gl.GL_LINEAR)
        # Wrapped round in u because the equirectangular seam meets
        # itself there, and clamped in v because the poles do not.
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S,
                           gl.GL_REPEAT)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T,
                           gl.GL_CLAMP_TO_EDGE)
        return handle

    def _build_shadow_target(self) -> None:
        self._shadow_tex = self._new_texture(
            SHADOW_SIZE, SHADOW_SIZE, gl.GL_DEPTH_COMPONENT24,
            gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._shadow_tex)
        # Nearest, and no compare mode: the fragment shader reads raw
        # depth and compares it itself, and a linear filter over depth
        # values averages distances rather than verdicts, which frays
        # every shadow edge into a band.
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER,
                           gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER,
                           gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S,
                           gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T,
                           gl.GL_CLAMP_TO_EDGE)
        self._shadow_fbo = self._new_fbo()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._shadow_fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT,
                                  gl.GL_TEXTURE_2D, self._shadow_tex, 0)
        gl.glDrawBuffer(gl.GL_NONE)
        gl.glReadBuffer(gl.GL_NONE)
        complete = (gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
                    == gl.GL_FRAMEBUFFER_COMPLETE)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        if not complete:
            raise RuntimeError('no shadow target')

    @staticmethod
    def _new_texture(width: int, height: int, internal, layout,
                     kind) -> gl.GLuint:
        handle = gl.GLuint(0)
        gl.glGenTextures(1, ctypes.byref(handle))
        gl.glBindTexture(gl.GL_TEXTURE_2D, handle)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal, width, height, 0,
                        layout, kind, None)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER,
                           gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER,
                           gl.GL_LINEAR)
        return handle

    @staticmethod
    def _new_fbo() -> gl.GLuint:
        handle = gl.GLuint(0)
        gl.glGenFramebuffers(1, ctypes.byref(handle))
        return handle

    @staticmethod
    def _new_renderbuffer() -> gl.GLuint:
        handle = gl.GLuint(0)
        gl.glGenRenderbuffers(1, ctypes.byref(handle))
        return handle

    def _ensure_size(self, width: int, height: int) -> bool:
        """(Re)allocate the offscreen targets for a stage this size."""
        width, height = max(16, int(width)), max(16, int(height))
        if (width, height) == self._size:
            return True
        self._drop_targets()
        try:
            self._colour_fbo = self._new_fbo()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._colour_fbo)
            self._colour_rb = self._new_renderbuffer()
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._colour_rb)
            gl.glRenderbufferStorageMultisample(
                gl.GL_RENDERBUFFER, SAMPLES, gl.GL_RGBA8, width, height)
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                gl.GL_RENDERBUFFER, self._colour_rb)
            self._depth_rb = self._new_renderbuffer()
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth_rb)
            gl.glRenderbufferStorageMultisample(
                gl.GL_RENDERBUFFER, SAMPLES, gl.GL_DEPTH_COMPONENT24,
                width, height)
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT,
                gl.GL_RENDERBUFFER, self._depth_rb)
            if (gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
                    != gl.GL_FRAMEBUFFER_COMPLETE):
                raise RuntimeError('no multisample target')

            self._resolve_fbo = self._new_fbo()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._resolve_fbo)
            self._resolve_tex = self._new_texture(
                width, height, gl.GL_RGBA8, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S,
                               gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T,
                               gl.GL_CLAMP_TO_EDGE)
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D, self._resolve_tex, 0)
            if (gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
                    != gl.GL_FRAMEBUFFER_COMPLETE):
                raise RuntimeError('no resolve target')
        except Exception:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            self._drop_targets()
            return False
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        self._size = (width, height)
        return True

    def _drop_targets(self) -> None:
        for fbo in (self._colour_fbo, self._resolve_fbo):
            if fbo is not None:
                try:
                    gl.glDeleteFramebuffers(1, ctypes.byref(fbo))
                except Exception:
                    pass
        for buf in (self._colour_rb, self._depth_rb):
            if buf is not None:
                try:
                    gl.glDeleteRenderbuffers(1, ctypes.byref(buf))
                except Exception:
                    pass
        if self._resolve_tex is not None:
            try:
                gl.glDeleteTextures(1, ctypes.byref(self._resolve_tex))
            except Exception:
                pass
        self._colour_fbo = self._resolve_fbo = None
        self._colour_rb = self._depth_rb = self._resolve_tex = None
        self._size = (0, 0)

    # --- what the floor cuts ---------------------------------------------

    def set_holes(self, holes: Sequence[Tuple[float, float, float, float]]
                  ) -> int:
        """Upload the holes the floor shader cuts. Once a tray, not a frame.

        They are constant for the whole of a tray — the tray tips, but
        it tips as one body and the holes tip with it — so uploading
        them per frame would be ninety-six needless GL calls sixty
        times a second.

        pyglet models ``vec4 holes[96]`` as a nested ctypes array, so a
        flat list of floats is refused and a whole-array assignment
        wants ninety-six four-tuples. Writing the live ones by index is
        both shorter and cheaper, and ``hole_count`` keeps the shader
        off the stale tail.
        """
        count = min(len(holes), MAX_HOLES)
        self._hole_count = count
        if not self.ok:
            return count
        for program in (self.program, self.depth_program):
            program.use()
            program['hole_count'] = count
            array = program['holes']
            for index in range(count):
                array[index] = tuple(holes[index])
        return count

    # --- drawing ---------------------------------------------------------

    def render(self, rect: Tuple[int, int, int, int], draws: Sequence[Draw],
               view_proj: Mat4, eye: Tuple[float, float, float],
               light: Light, centre: Tuple[float, float, float],
               holes: Sequence[Tuple[float, float, float, float]],
               background: Tuple[float, float, float]) -> bool:
        """Draw *draws* and blit the result into *rect*, in framebuffer pixels.

        Returns False if the stage could not be prepared, which is the
        caller's cue to paint something flat instead.
        """
        if not self.ok:
            return False
        left, bottom, width, height = rect
        if width < 8 or height < 8 or not self._ensure_size(width, height):
            return False
        light_clip, light_matrix = self._light_matrix(light, centre)
        try:
            self._shadow_pass(draws, light_clip)
            self._colour_pass(draws, view_proj, eye, light, light_matrix,
                              holes, background)
            self._blit(rect)
        finally:
            self._restore()
        return True

    @staticmethod
    def _light_matrix(light: Light, centre: Tuple[float, float, float]
                      ) -> Tuple[Mat4, Mat4]:
        """An orthographic box looking down the light, twice over.

        The first is what the depth pass renders with; the second is the
        same thing with the clip-space-to-texture bias folded in, which
        is what the colour pass looks the result up with. Two matrices
        rather than one because using the biased one to render is a
        quarter-sized shadow map in the corner of the texture.
        """
        span = light.span
        eye = Vec3(centre[0] + light.direction[0] * span * 2.2,
                   centre[1] + light.direction[1] * span * 2.2,
                   centre[2] + light.direction[2] * span * 2.2)
        straight_down = abs(light.direction[1]) > 0.98
        up = (0.0, 0.0, 1.0) if straight_down else (0.0, 1.0, 0.0)
        view = Mat4.look_at(eye, Vec3(*centre), Vec3(*up))
        proj = Mat4.orthogonal_projection(-span, span, -span, span,
                                          0.01, span * 5.0)
        # Clip space is [-1,1] and a depth texture is [0,1], so the
        # shadow lookup needs the half-and-shift built in. Composed from
        # the two constructors rather than written out as sixteen
        # numbers, because pyglet's Mat4 takes its elements unpacked and
        # a single tuple goes in as one element without complaining.
        bias = (Mat4.from_translation(Vec3(0.5, 0.5, 0.5))
                @ Mat4.from_scale(Vec3(0.5, 0.5, 0.5)))
        clip = proj @ view
        return clip, bias @ clip

    def _shadow_pass(self, draws: Sequence[Draw], light_clip: Mat4) -> None:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._shadow_fbo)
        gl.glViewport(0, 0, SHADOW_SIZE, SHADOW_SIZE)
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_BLEND)
        # No culling, so the depth written is the nearest surface
        # whichever way a triangle happens to be wound.
        #
        # Culling front faces is the usual cure for shadow acne and it
        # is wrong here. It records the *far* side of each caster, which
        # for a 15mm marble is 15mm past the near side — and the tray
        # under the marble is about 1mm beyond that along the light ray,
        # well inside the depth bias. The marble came out casting no
        # contact shadow at all, which does not read as a shadow bug: it
        # reads as a ball that is not quite touching the board, and the
        # contact shadow is most of what says it is.
        gl.glDisable(gl.GL_CULL_FACE)
        program = self.depth_program
        program.use()
        program['hole_count'] = self._hole_count
        program['light_clip'] = light_clip
        for draw in draws:
            if not draw.casts or draw.mesh.shadow_vlist is None:
                continue
            program['model'] = draw.model
            program['cut_holes'] = 1 if draw.cut_holes else 0
            draw.mesh.shadow_vlist.draw(gl.GL_TRIANGLES)

    def _colour_pass(self, draws: Sequence[Draw], view_proj: Mat4,
                     eye: Tuple[float, float, float], light: Light,
                     light_matrix: Mat4,
                     holes: Sequence[Tuple[float, float, float, float]],
                     background: Tuple[float, float, float]) -> None:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._colour_fbo)
        gl.glViewport(0, 0, self._size[0], self._size[1])
        gl.glClearColor(background[0], background[1], background[2], 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_BLEND)
        # No culling: the pits are seen from inside and the floor is a
        # single sheet, so both want their back faces.
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glEnable(gl.GL_MULTISAMPLE)
        # Alpha-to-coverage, so a hole's rim is antialiased by the
        # multisampling that is already there.
        #
        # The obvious way to smooth a discarded edge is per-sample
        # shading, and it works — at a measured 39.6ms a frame against
        # 3.8ms, because it runs this whole shader, wood noise and all,
        # four times per pixel over the entire tray. Alpha-to-coverage
        # gets the same rim by handing the hardware a coverage fraction
        # and letting it pick a sample mask, and costs nothing.
        gl.glEnable(gl.GL_SAMPLE_ALPHA_TO_COVERAGE)

        program = self.program
        program.use()
        program['view_proj'] = view_proj
        program['light_matrix'] = light_matrix
        program['eye'] = eye
        program['light_dir'] = light.direction
        program['light_colour'] = light.colour
        program['sky_colour'] = light.sky
        program['ground_colour'] = light.ground
        program['shadow_texel'] = 1.0 / float(SHADOW_SIZE)
        program['grain_seed'] = self.grain_seed
        program['hole_count'] = self._hole_count
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._shadow_tex)
        program['shadow_map'] = 0
        program['marble_maps'] = 1 if self._marble_tex else 0
        for unit, handle in enumerate(self._marble_tex, start=1):
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_2D, handle)
        if self._marble_tex:
            program['marble_colour'] = 1
            program['marble_rough'] = 2
            program['marble_normal'] = 3

        for draw in draws:
            program['model'] = draw.model
            program['normal_scale'] = draw.normal_scale
            program['material'] = int(draw.material)
            program['tint'] = draw.tint
            program['cut_holes'] = 1 if draw.cut_holes else 0
            draw.mesh.vlist.draw(gl.GL_TRIANGLES)
        gl.glDisable(gl.GL_SAMPLE_ALPHA_TO_COVERAGE)

    def _blit(self, rect: Tuple[int, int, int, int]) -> None:
        """Resolve the samples, then paste the result where it belongs."""
        left, bottom, width, height = rect
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._colour_fbo)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._resolve_fbo)
        gl.glBlitFramebuffer(0, 0, width, height, 0, 0, width, height,
                             gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glViewport(int(left), int(bottom), int(width), int(height))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        self.composite.use()
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._resolve_tex)
        self.composite['scene'] = 0
        self._screen.draw(gl.GL_TRIANGLES)

    def _restore(self) -> None:
        """Put back everything pyglet's 2D drawing takes for granted."""
        from ..geometry import framebuffer_size
        from .. import state
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        for unit in range(3, -1, -1):
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glDisable(gl.GL_SAMPLE_ALPHA_TO_COVERAGE)
        try:
            gl.glUseProgram(0)
            gl.glBindVertexArray(0)
        except Exception:
            pass
        width, height = framebuffer_size(state.window)
        gl.glViewport(0, 0, width, height)
        bg = 0.0 if state.cfg.BLACK_BACKGROUND else 1.0
        gl.glClearColor(bg, bg, bg, 1.0)

    def close(self) -> None:
        self._drop_targets()
        for handle in (self._shadow_fbo,):
            if handle is not None:
                try:
                    gl.glDeleteFramebuffers(1, ctypes.byref(handle))
                except Exception:
                    pass
        if self._shadow_tex is not None:
            try:
                gl.glDeleteTextures(1, ctypes.byref(self._shadow_tex))
            except Exception:
                pass
        self._shadow_fbo = self._shadow_tex = None
        for handle in self._marble_tex:
            try:
                gl.glDeleteTextures(1, ctypes.byref(handle))
            except Exception:
                pass
        self._marble_tex = ()
        if self._screen is not None:
            try:
                self._screen.delete()
            except Exception:
                pass
            self._screen = None
        self.ok = False


def placed(position: Tuple[float, float, float],
           scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
           spin: Optional[Mat4] = None,
           frame: Optional[Mat4] = None) -> Tuple[Mat4, Tuple[float, ...]]:
    """A model matrix and the normal scale that goes with it."""
    model = Mat4.from_translation(Vec3(*position))
    if spin is not None:
        model = model @ spin
    if scale != (1.0, 1.0, 1.0):
        model = model @ Mat4.from_scale(Vec3(*scale))
    if frame is not None:
        model = frame @ model
    return model, tuple(1.0 / (value * value) if value else 1.0
                        for value in scale)


__all__ = ['BRASS', 'Builder', 'CUP', 'Draw', 'Light', 'Mesh', 'OAK', 'PIT',
           'STAIN', 'STEEL', 'Stage', 'placed']
