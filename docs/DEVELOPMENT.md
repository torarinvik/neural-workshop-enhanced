# Development notes

How the code is laid out, and technical notes on drawing, timing and the
native kernels.

## Code layout

`brainworkshop.py` is still the entry point (`python brainworkshop.py`)
and still the module the gym imports (`import brainworkshop as bw`), but
it is now a thin facade over three packages:

| Package | What lives there |
| --- | --- |
| `neural_workshop/` | the game — config, state, board, modes, scoring, session, events, and everything drawn on screen under `ui/` |
| `bwaccel/` | the accelerated kernels, dispatching to the `bwcore` C extension when it is built and to `bwaccel/fallback.py` when it is not |
| `nwenv/` | the agent boundary — frame capture, public outcomes and their verification, and the stepped environments |

Inside `neural_workshop`, `ravens/` is the odd one out: it is the
Matrix Reasoning puzzle generator, and it imports no pyglet and
touches no singleton, so a puzzle can be built and checked without a
window. `glyphs.py` is split the same way for the same reason, with
its drawing half under `ui/`, and so are `crossword.py`, `scrabble.py`,
the `wordlist.py` they and `syllogism.py` draw their words from, and
`tetris.py`, whose whole promise is a property of a generator that can
be run without a screen and is. Everything else on screen goes through
`ui/`.

Inside `neural_workshop`, the live singletons (`cfg`, `window`, `mode`,
`field`, the labels) live in `state.py` and are reached as `state.mode`
rather than imported by value, because switching user profile rebinds
some of them. `bootstrap.build_application()` populates that module in
the one order that works; nothing else touches a singleton before it has.

## Window size, full screen, and the two coordinate spaces

The window is resizable, and **F11** switches to and from full screen
on any screen. `WINDOW_FULLSCREEN` in `config.ini` decides which one
the game starts in.

Widgets are positioned from the window size when they are built and
there is no per-frame layout pass, so a size change rebuilds them.
Nothing has to remember to ask: `display.on_resize` is pushed onto the
window, `geometry.set_window_size` notifies its listeners, and every
`on_draw` calls `display.ensure_laid_out()` as a last check. Rebuilds
are coalesced, so dragging the window edge costs one rebuild when the
drag settles rather than one per event. The session, the level and the
stats live outside the widgets and are untouched; a stimulus on screen
mid-trial is put back.

A screen that pushes its own `on_draw` must call
`display.register_overlay(self)`, `display.unregister_overlay(self)`
when it closes, and provide `relayout()`. `tests/test_ui_units.py`
fails the build if one does not.

**Pixels are not points.** On a scaled display (Retina, Windows display
scaling) a window has a drawing surface in *pixels* — `window.width`,
the GL viewport, every widget coordinate — and a size in *points*,
which is what the OS API takes. `pixels = points * window.scale`, and
on an unscaled display the two are equal, which is why mixing them up
survives testing on one machine and doubles the window on another.
pyglet gets this wrong itself: `set_fullscreen` saves the windowed size
in pixels and restores it as points, so leaving full screen would
double the window on every toggle.

`neural_workshop/geometry.py` owns the distinction and every call into
pyglet's point-space API:

| Need | Use |
| --- | --- |
| lay something out | `window.width` / `window.height`, or the `from_*` helpers — pixels, as always |
| resize the window | `geometry.set_window_size(width, height)` — points, clamped, verified |
| the window in OS terms | `geometry.point_size()` |
| the buffer to read pixels from | `geometry.framebuffer_size(window)` |

Nothing else may call `set_size`, `get_size`, `get_framebuffer_size`,
`set_minimum_size`, or read `window.scale`; the same test enforces that
by scanning the source.

## The title logo

The splash is `res/misc/splash/logo.png`, and the one used when
`BLACK_BACKGROUND` is on is `res/misc/splash-black/logo_blk.png`. Both
are ordinary resource sets, so a folder holding several images gives a
different logo each launch — which also means a second file left in
beside the first is not a replacement, it is a coin toss.

The artwork is *fitted* to the window rather than drawn at whatever
resolution the file happens to be. `bootstrap._place_splash` scales it,
aspect ratio intact, into the gap between the version banner and the
key list, so a new logo cannot be clipped by the window, land on top of
the keys, or sit as a speck on a large screen. `tests/test_ui_screens.py`
holds it to that with artwork from 64x64 to 2000x500.

The dark copy is derived from the light one by `tools/unwhite.py`, which
reads every pixel as ink laid over white paper and undoes that
composite. The logo is then unchanged on white and becomes pencil on
black in the dark theme, instead of a bright card floating on it. Run it
again after changing the logo:

```bash
python tools/unwhite.py res/misc/splash/logo.png res/misc/splash-black/logo_blk.png
```

## Trial timing (milliseconds)

Human play still defaults to 100 ms ticks and ~3 s per trial. For faster
agent training you can set millisecond intervals:

```
./run --headless --tick-ms 1 --trial-ms 50
```

- `--trial-ms N` — length of one cell/trial in milliseconds
- `--tick-ms N` — scheduler quantum (use `1` for true ms control)
- `--stim-ms N` — requested stimulus visibility (scaled down if it
  cannot fit in the trial together with feedback)
- `--headless` — skip the title screen, hide the window, mute music,
  default to a 1 ms clock and 10 ms trials (override with `--trial-ms`)

Trials are a **state machine** (`stimulus` → optional `blank` →
`feedback`). If `stimulus + feedback > trial`, both phases are scaled
so they stay non-overlapping and still fit.

In game: **C** → *Trial interval (ms)*, or **F5** / **F6** in Manual mode.

## Grid size

The board is `GRID_SIZE` × `GRID_SIZE`. Squares, letters, and images
scale to fit a single cell. Default `3` is classic Dual N-Back (8 cells,
center empty). A 4×4 board uses all 16 cells. Change it in **C: Choose Game
Mode** (*Grid size*) or in `config.ini` (`GRID_SIZE = 10`). Allowed sizes
are `GRID_SIZE_MIN`–`GRID_SIZE_MAX` (defaults 2–32). Odd sizes skip
the center cell unless `GRID_INCLUDE_CENTER = True`.

## Native C kernels (recommended)

The heaviest game loops (Jaeggi/BT sequence construction, session scoring,
stats-file parsing, graph aggregation, variable n-back draws, and rounded-
rectangle vertices) live in a C extension, `bwcore`.

Build it once from the project root (needs a C compiler and Python headers):

```
python setup.py build_ext --inplace
```

The game still runs without the extension: the `bwaccel` package falls back to
equivalent Python. Sessions at high n-back are much faster with the C module,
because the old rejection sampler is replaced by an O(n) constructive
generator that still produces exactly 6 position matches, 6 audio matches,
and 2 dual matches.

The title screen and the workshop hub show a tiny `native: C` or
`native: Python` tag so you can see which path is live. Launch with
`--debug` to print the same tag on the console.

Windows release zips are frozen with `bwcore` already compiled in — players
do not need a C compiler. CI also publishes platform wheels as artifacts
(and attaches them to tagged releases).

## Procedurally distorted letters

`neural_workshop/glyphs.py` and `neural_workshop/ui/glyphs.py` are a
shared piece rather than a game: they turn a letter into a picture of a
letter that has never been seen in that shape before. No task uses them
yet.

A task that draws a letter in one of a handful of typefaces cannot tell
whether it is being read or remembered, and nothing in the picture says
which happened. So a letter here is drawn in one of the typefaces
already installed on the machine and then put through a warp sampled
from a rung: stretched, sheared, turned, tilted in perspective,
rippled, thickened or thinned, specked, partly hidden behind bars, and
faded toward its background. Every knob is sampled independently, so
the ten rungs are boxes to sample from rather than ten appearances.

Two axes are kept apart on purpose — what the letter *is*, which is a
task's own content, and what it *looks like*, which is this. They deal
from different seeds and neither reads the other, so a rung of visual
difficulty goes under any content difficulty a task already has and a
result can say which of the two moved.

The rules module imports no pyglet and touches no pixels, so a warp can
be checked without a window; the `ui/` half is the part that reads a
glyph's coverage off the card and hands back an `ImageData`.

Three things are worth knowing before using it.

**Split by family, not by file.** Georgia and Georgia Bold Italic are
one typeface in two files, and holding one out while training on the
other is a leak with a different filename. `families()` groups files by
the family name in the font's own `name` table and `split()` divides
those groups whole.

**Ask the font what it can draw.** Of the 198 families installed on this
Mac only 59 contain Latin capitals — most of the rest are Noto faces for
other scripts. Ask one of those 139 for a capital A and the platform
quietly substitutes one, and pyglet hands back a perfectly good letter
in a typeface nobody asked for. Every held-out family that is really the
fallback is the *training* typeface being scored as unseen, which was
two thirds of the pool. `families(must_draw=...)` reads the font's own
`cmap` and is not optional for anything being measured.

**Widen the pool before believing a held-out number.** 59 families is
not a sample of anything: the ten that came out held out were ten
particular typefaces, and another machine would have had a different
ten. `neural_workshop/fontlib.py` fetches Google Fonts from the
`Felix92/docTR-resource-collection` mirror on Hugging Face — 6,899
`.ttf` files across about 1,800 families, plus a 1,010-file subset the
mirror marks as covering English. Standard library only, resumable and
idempotent, and nothing downloads on its own: a caller asks, by number
of families rather than of files, and one already on disk is skipped.

```bash
PYTHONPATH=. .venv/bin/python -m neural_workshop.fontlib google 300  # about 120 MB
```

The files land in the player's data directory, not in this repository.
They are Google Fonts under the SIL Open Font License, Apache 2.0 or the
Ubuntu Font Licence depending on the family; the mirror is tagged
Apache 2.0. Two cautions carried in the module: the mirror's *filename*
is used only to spread a fetch across families rather than pull nine
weights of one face — the family a font is really in comes from its own
`name` table — and the mirror's "english" folder is its word, not a
measurement, so `covered()` still decides what can draw an alphabet.

**The ladder is measured, not asserted.** A nearest-template classifier
over an eight-by-eight ink grid, templates from 40 training families and
questions from 16 held-out ones, out of 366 Latin-capable families split
255/54/56, falls 0.90, 0.90, 0.77, 0.63, 0.45, 0.29, 0.22, 0.19, 0.15,
0.11 across the rungs against a floor of 0.04. The first rung is the
ceiling of the measurement rather than a score — these are typefaces the
templates have never seen — so what the column shows is the fall.
Switching each knob off in turn at rung six puts most of the cost in the
plain affine matrix (+0.21) and the speckle (+0.11), and finds that
thickening and contrast recover nothing at all: a signature counts
pixels above a fixed threshold, so it is blind to both by construction
and cannot price them. The elastic ripple, which is the knob that most
looks like difficulty, is worth +0.04.

Widening the pool six-fold, from 59 families to 366, barely moved that
column — mild evidence that its shape was not an artefact of whichever
typefaces happened to be installed.

```bash
cd tests && PYTHONPATH=.. ../.venv/bin/python bench_glyphs.py   # about a minute
```
