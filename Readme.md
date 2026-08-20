[![Build status](https://github.com/torarinvik/neural-workshop/actions/workflows/zip.yml/badge.svg?branch=master)](https://github.com/torarinvik/neural-workshop/actions/workflows/zip.yml)

# Neural Workshop 5
PS: If you appreciated this work, please star the repository. It helps others
find this repository

## What is this?
This is a fork of the popular brain training software BrainWorkshop

Since there has not been a release in 3 years, I decided to get it working on
Python 2+3 in additon to making many changes and improvements.

Version 5 is technically in Beta, although it is expected to be more
stable compared to the original project and work with modern Python and Pyglet

## Downloads

 * Windows: https://github.com/torarinvik/neural-workshop/releases

## New in this release:

* Elements on the screen scale depending on the window size, making it much more
  usable if you have a hidpi monitor.
* Using a widescreen resolution causes items on the screen to be placed/scale properly
* Fullscreen mode sets the resolution of the screen automatically
* Font size scales based on window size
  * Positioning of items also scales with window size
  * Window position and font size are determined with one function to do scaling,
    thereby making it easier in the future to make adjustments
* Set fonts differently for serif and for monospace fonts, eventually to allow
  them to be configurable.
* Now compatible with Python 3
  * Fixed issues with at least three modules not loading. This was due to
    being renamed or their semantics changing. Fixed in a way to maintain Python 2
    compatibility.
  * Fix alignment of the polygons/icons in the grid due to changes to division
    in Python 3
* Compatible with *both* Python 2 and Python 3!
* Fixed crash with text.Label not recognizing `halign`; use `align` instead since
  `halign` is deprecated. Though to avoid breaking anything, we try `align` first
  and if that fails we fall back to using `halign`
* Fix many more crashes and issues of Brain Workshop failing to launch


## Notes:
* You need pyglet installed for this to work.

### Code layout

`brainworkshop.py` is still the entry point (`python brainworkshop.py`)
and still the module the gym imports (`import brainworkshop as bw`), but
it is now a thin facade over three packages:

| Package | What lives there |
| --- | --- |
| `neural_workshop/` | the game — config, state, board, modes, scoring, session, events, and everything drawn on screen under `ui/` |
| `bwaccel/` | the accelerated kernels, dispatching to the `bwcore` C extension when it is built and to `bwaccel/fallback.py` when it is not |
| `nwenv/` | the agent boundary — frame capture, public outcomes and their verification, and the stepped environment |

Inside `neural_workshop`, `ravens/` is the odd one out: it is the
Matrix Reasoning puzzle generator, and it imports no pyglet and
touches no singleton, so a puzzle can be built and checked without a
window. Everything else on screen goes through `ui/`.

Inside `neural_workshop`, the live singletons (`cfg`, `window`, `mode`,
`field`, the labels) live in `state.py` and are reached as `state.mode`
rather than imported by value, because switching user profile rebinds
some of them. `bootstrap.build_application()` populates that module in
the one order that works; nothing else touches a singleton before it has.

### Long-term memory games and their media libraries

The task hub's *Long-term memory* category holds two games that work
on material you have not seen a hundred times already, so the material
is downloaded rather than shipped:

- **Concentration** — a board of face-down pairs, turned over two at a
  time. With `Cards show: sound` it deals five-second clips instead of
  photographs, which is a markedly harder game: a sound cannot be
  compared at a glance, it has to be held in mind while the second
  card plays.
- **Seen It Before?** — the old/new recognition task. A run presents a
  stream of items, some of them second showings from far enough back
  that rehearsal is no help. Scored on both halves — catching repeats
  and not claiming the new ones — so a single constant answer scores
  the repeat rate, never 100%.

Fetch the libraries once:

```bash
.venv/bin/python -m neural_workshop.datasets
```

That pulls 5,000 photographs from `thethinkmachine/tiny-imagenet` and
500 sound clips from `renumics/esc50` into `<data dir>/datasets/`.
Name one to fetch only that, and add a number for a different size —
the whole of either split, if you have the room:

```bash
.venv/bin/python -m neural_workshop.datasets tiny-imagenet 100000
.venv/bin/python -m neural_workshop.datasets esc50 2000
```

| Library | Full split | On disk |
| --- | --- | --- |
| `tiny-imagenet` | 100,000 photographs, 64x64 | ~194 MB |
| `esc50` | 2,000 clips, 5s, 50 classes | ~882 MB |

The full ESC-50 is worth having if you play the sound modes: it is 50
classes of 40 clips each, so a complete set gives many different
recordings *within* a class. That is what stops "have I heard this?"
being answerable from the category alone.

Fetching is resumable and idempotent — it skips what is already on
disk, so an interrupted download is finished by running it again.
Nothing downloads on its own; a game whose library is missing says so
and stays playable in the other medium.

`neural_workshop/datasets.py` needs only the standard library, going
through Hugging Face's datasets-server rather than `datasets` or
`pillow`. A large request additionally tries the dataset's parquet
files, which is one download instead of tens of thousands and turns an
hour into a couple of minutes; that path wants `pyarrow`, and falls
back to fetching item by item when it is absent or fails. The media
column holds encoded bytes, so files are written straight out and no
image or audio library is involved either way.

```bash
.venv/bin/python -m pip install pyarrow   # optional, for bulk fetches
```

### Attention

The *Attention* category holds **Reflex**: photographs appear at random
places and shrink from full size to nothing, and you click them before
they go. Several are on screen at once, each on its own clock, so the
work is choosing what to go for as much as pointing at it — the one
about to vanish is the one worth chasing, and a click on overlapping
targets is awarded to the smaller of them for that reason.

With *Speed up when you hit* the life of a target shortens as you hit
and lengthens as you miss, more quickly to ease off than to tighten,
so it settles near the edge of what you can manage. The floor is 0.3 s,
which is about human reaction time; reaching it means the task has
nothing harder left to offer.

It draws from the same photograph library as the long-term-memory
games, so `python -m neural_workshop.datasets tiny-imagenet` is all it
needs.

### Perception

The *Perception* category holds **Count**: a tangle of overlapping
outlines, and the question is how many there are. Type the number and
press Enter. Past four or five, counting stops being a glance and
becomes work — the eye has to keep track of what it has already
counted while the crossings actively mislead it.

*Shapes to count* picks lines, circles, triangles, rectangles or a
mixture. Lines run edge to edge so they cross rather than huddle,
which is what makes them hard to tell apart. *Hide the shapes after*
takes the tangle away once the time is up so the answer comes from
perception rather than from patiently ticking shapes off, and with
*Add a shape when right* the count follows how you do.

Nothing is downloaded for this one — the shapes are generated.

### Reasoning

The *Reasoning* category holds two tasks.

#### Graph Mapping

Two networks of dots
and lines, side by side, drawn differently. The question is whether
one is the other redrawn — whether every dot on the left can be
matched to a dot on the right with exactly the same connections.
Answer with **Y** / **N**, the arrow keys, or the two buttons.

Nothing is labelled, on purpose. Labels shared between the panels
would reduce the task to checking a list of pairs; without them there
is no way through but to find the correspondence. The two panels
always hold the same number of dots and the same number of lines, so
counting either can never answer a trial.

*Mismatches keep every connection count the same* decides how a
"different" pair differs, and it is the difference between two quite
separate tasks. With it off, one line has been moved somewhere else,
so the dots' connection counts no longer match up — tally them on both
sides and the answer falls out, mechanically. With it on, two lines
have been crossed over instead, which leaves every count exactly as it
was: the tallies agree, tell you nothing, and the structure has to be
walked.

That second kind runs out at the bottom of the range. At four dots —
and at five, once there are more than six lines — every profile of
connection counts describes exactly one network, so there is no second
one to cross lines into. Asking to keep the counts therefore holds the
size up to where such a network exists: six dots, or five when sparse.

You do not have to know that. The options screen carries a line under
the rows saying what the three of them add up to — how many dots and
lines each panel will really hold, and which kind of mismatch you are
asking for — and it follows the rows as you change them, so a size
that is about to be raised says so while you are still choosing it.
The waiting screen repeats it before you start.

Above that floor a partner always exists, but not for every starting
network — at six dots and a dense graph only four of the nine have
one — so a network that cannot be rewired is thrown away and another
drawn, rather than settled for. If that ever fails anyway the trial
becomes the easier kind of mismatch, never a match, and the summary
at the end of the run says how many did. It is never said during a
trial: knowing which kind a mismatch is would give away that it is
one.

*How many connections* sets the density, *Hide the graphs after* puts
the pair under time pressure, and with *Add a dot when right* the size
follows how you do. Nothing is downloaded for this one either — the
networks are generated.

#### Matrix Reasoning

A three-by-three grid of figures that follow rules you have to work
out, with the bottom-right panel missing and the candidates for it
beside the grid — four on the easy levels, eight otherwise. Answer
with **1**–**8** or by clicking a box. This is the shape of a Raven's
Progressive Matrices item, the standard test of reasoning that owes
nothing to language or to what you already know.

The puzzles are generated rather than drawn, and the generator is
built around the three things that make a matrix read as a designed
object rather than a heap:

**A layout.** Every panel of a puzzle uses the same arrangement — one
figure in the middle, two side by side, one above another, one inside
another, a lattice of two-by-two or three-by-three, or three abreast.
The layout is part of the puzzle's shape, not one of its variables, so
it is never something you have to work out. A layout carries up to
three *components* — the outer ring and the inner mark are two of them
— and each follows rules of its own, which is how a matrix asks
several questions at once without drawing the answers on top of each
other.

**Regular figures.** Triangle, square, pentagon, hexagon, circle, each
inscribed in a circle and sitting the way the eye expects: the
triangle on its base, the square square rather than diamond. Sizes
come off a five-step ladder that is *geometric* rather than evenly
spaced, because what the eye judges is the ratio between two sizes and
not the difference — an evenly spaced ladder is obvious at the small
end and guesswork at the large end.

**Rules along the rows.** Six of them. For the first five the same
rule governs all three rows, which is what makes the third row
answerable from the first two; the sixth breaks exactly that
expectation, on purpose, and is saved for the top of the ladder:

* *Constant* — the value holds, everywhere. Not merely along each row:
  an attribute that changes between rows is doing something, and a
  player is right to go looking for the rule behind it, so there had
  better be one. Anything that varies here varies because a rule says
  so.
* *Progression* — the value steps along its ladder by the same amount
  each time, up or down, by one or by two.
* *Distribute three* — three values, and every row holds all three in
  a different order. Laid out as a Latin square, so every column holds
  all three as well and the missing value can be read off either. This
  is the rule people picture when they picture a Raven's item.
* *Arithmetic* — the third value is the first plus or minus the
  second. Only ever applied to how many figures there are, where it is
  something a person can actually do in their head.
* *Logic* — on a lattice, the places holding a figure in the third
  panel follow from the first two: everything in either, only what is
  in both, or what is in exactly one. Nothing steps or repeats, so the
  rule cannot be spotted by watching one figure — it has to be
  inferred from what two whole panels have to do with a third. These
  are the items at the hard end of the real test, and they only
  appear at the hard end here.
* *Second order* — the rule itself changes between rows: row one
  holds its value, row two steps along the ladder, row three steps
  twice as far. No row's rule is the answer; what has to be inferred
  is the progression *of* rules, which means representing "how this
  row works" as a thing that can itself change. These are the items
  at the very top of the real test's advanced form, and like the
  logic rules they are kept out of the middle levels.

The attributes a rule can govern are which figure, its size, its
colour, how many there are, and — where it can be seen — which way it
faces. That last one takes its turns from the figure's own symmetry: a
fixed ladder of sixths of a turn would offer a triangle 0°, 120° and
240°, which are three names for the same triangle.

*Start at level* picks a rung of a twelve-step ladder, and the rungs
turn more dials than one. Level 1 is not a matrix at all but pattern
completion — every panel the same picture, find the matching piece
among four — which is the genuinely easy end of the real test,
answerable by a five-year-old. The early levels offer four candidates,
keep to a single rule drawn from a narrowed pool, and use a coarse
three-step size ladder so "bigger" is something you see rather than
judge. From there each level up adds rules, then more components to
carry them, then the logic rules, and at the top a seven-step size
ladder on which a rule you have *found* still takes care to apply.
Level 12 runs nine rules at once across three components, which is
more than a person tracks — deliberately so, so the ladder ends past
everyone. With *Go up a level when right* the run follows how you do.
*Name the rules after each answer* prints the rules behind the puzzle
once it has been answered, which turns a run into practice rather than
a test. Nothing is downloaded — a puzzle costs under a tenth of a
millisecond to build, so they are made as you play.

##### Colour

*Mix in coloured puzzles* alternates coloured grids with grey ones. A
puzzle is one or the other and never both: a candidate in the wrong
palette would stand out as wrong without any of the rules being read.

The four colours are not a matter of taste. Roughly one man in twelve
has some red-green deficiency, and a rule that turns on telling red
from green is not a hard puzzle for them but an unanswerable one. So
the palette was chosen by measurement: every pair was simulated for
each kind of dichromacy and compared in CIELAB, and these four leave
the largest worst case of any four in the Okabe-Ito set. That worst
case is a little over twice the grey ramp's own, so a rule about
colour is if anything easier to follow than a rule about shade.

They are also ordered by lightness, strictly — 100, 91, 76, 63, 57 —
so the sequence is a lightness ramp as well as a colour one. A player
who cannot separate the hues at all still sees each step get darker,
which is the same rule the grey puzzles ask for.

##### The wrong answers

A puzzle is only as good as the choices it offers, and the obvious
way to build them is a trap. Make each wrong answer "the right one
with a single thing changed" and the right answer agrees with every
wrong one on everything but its one change — it sits at the centre of
its own distractor set, and picking the most typical candidate solves
the puzzle without reading the matrix. An earlier version of this
generator had exactly that leak, and so did the RAVEN research
dataset, which a model solved from its answer lists alone.

So the wrong answers are *balanced*. A few of the puzzle's attributes
are targeted — the ones carrying live rules first — each is given one
wrong value, and the wrong answers are fixed combinations of those
wrong values swapped into the right answer, arranged so that every
targeted attribute is wrong in exactly half of the candidates offered.
A vote on any attribute is then a dead tie, and the only way in is the
rules. Every wrong answer is still rebuilt through the same machinery
as the puzzle, so it is always a panel the layout could have produced;
one that could not exist is answerable by noticing that it could not.

The tests measure this rather than trusting it. Two context-blind
solvers — pick the candidate most like the others, pick the one least
like them — run against the generator at easy, middle and top levels,
and neither may beat guessing. The "least like" solver is there
because balance can leak in reverse: a wider design that targeted
seven attributes kept every one of them balanced and still gave the
game away, because the all-correct answer agreed with the wrong ones
*less* than they agreed with each other.

##### Where this came from

The first version of this task was a port of the Sandia Generated
Matrix Tool, a Java research tool by Zachary Benz and Kevin Dixon
released by Sandia Corporation in 2010 under a three-clause BSD
licence. It generated sound puzzles that did not look like Raven's
items: it stacked layers of stretched ellipses and trapezoids at the
same centre and let them overlap, and it walked its rules along
diagonals and spirals rather than rows. Both are patterns a person can
eventually find, and neither is what the test is.

The engine here was rebuilt from the ground up around layouts,
regular figures and row-wise rules. What survives from the port is the
colour work above and the near-miss idea — which was itself a strategy
the Sandia tool declared, as `MODIFIED_CORRECT_ANSWER`, and never
wrote.

### Window size, full screen, and the two coordinate spaces

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

### The title logo

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

### Trial timing (milliseconds)

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

### Agent environment

`nwenv.NeuralWorkshopEnv` is a `reset → observe → act → advance` boundary
that shares the human game's stimulus, input, scoring, and renderer.

```python
from nwenv import NeuralWorkshopEnv
env = NeuralWorkshopEnv(seed=1)
obs = env.reset(1)            # RGBA + frame_seq + timestamp
receipt = env.act(0)                    # opaque port index, not a modality name
obs, events, done = env.step([])        # waits until the last frame was consumed
env.close()
```

- Each `advance`/`step` emits the next **significant** frame (stimulus,
  blank, or feedback) and will not move on until that frame is consumed.
- Observations never include cell IDs, match labels, scores, phase
  names, or the sequence. Outcomes are a pixel-derived scalar plus
  SHA-256 digests of the public frames used as evidence and the
  trial's action receipt. Missing/ambiguous feedback yields *no*
  outcome (not a zero reward).
- `verify_public_outcome` requires both the immutable frame archive and
  the receipt ledger whenever the outcome names a receipt. Omitting
  either fails closed. `verify_public_pixels` is diagnostic only.
- Actions are opaque integer port indices (`act(0)`, `act([0, 1])`).
- Headless / `NW_HEADLESS=1` uses pyglet's silent audio driver and a
  capture player (PCM is recorded, OpenAL is not started). Dual N-Back
  audio for training is the captured buffer, not physical playback.
- `NW_SHM=name` writes a one-way framebuffer dump (header + RGBA).
  It is **not** a complete IPC protocol (no seqlock, no action or
  reset channel, no ownership handshake).
- Parity tests compare the step driver to the scheduled `update()`
  clock with the window **hidden**. That is stepped-versus-scheduled
  parity, not literal visible-window execution.

Benchmark (reports trials/s, never “experiences/s”):

```
.venv/bin/python -m nwenv
```

`GRID_SIZE` is the visible board. `ACTIVE_POSITION_CELLS` (0 = all) is
an independent center-out curriculum. The session panel shows
`Grid 4×4 (8/16 cells)` when a subset is active.

Neural Workshop is the canonical training gym. Session difficulty belongs
on `NeuralWorkshopEnv`:

```
from nwenv import NeuralWorkshopEnv
env = NeuralWorkshopEnv(
    seed=17, game_mode=2, n_back=1, num_trials=60,
    grid_size=3, active_cells=8, visible=False,
)
```

`game_mode=2` is Dual (pixels + public PCM). `game_mode=10` is Position.
Do not train by patching a separate Brain Workshop or by poking `bw.cfg`.
A visible window (`visible=True` and `NW_HEADLESS=0`) is for watching the
gym; the learner still sees only the public observation.

### Grid size

The board is `GRID_SIZE` × `GRID_SIZE`. Squares, letters, and images
scale to fit a single cell. Default `3` is classic Dual N-Back (8 cells,
center empty). A 4×4 board uses all 16 cells. Change it in **C: Choose Game
Mode** (*Grid size*) or in `config.ini` (`GRID_SIZE = 10`). Allowed sizes
are `GRID_SIZE_MIN`–`GRID_SIZE_MAX` (defaults 2–32). Odd sizes skip
the center cell unless `GRID_INCLUDE_CENTER = True`.

### Native C kernels (recommended)

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

### Python 3
If you are having issues launching BrainWorkshop even if you have `pyglet`, `future`, `past` and
  `libfuturize` modules installed, follow these steps first:
1. Copy the following folders into the neural-workshop folder: past, future and
   libfuturize. You can get those here: https://github.com/PythonCharmers/python-future
2. Copy the pyglet module into a `pyglet` folder. You can get pyglet here: http://www.pyglet.org/

### Python 2
* You need pyglet, urllib3

# Start of Old Readme

Brain Workshop: a Dual N-Back game in Python

Thank you for downloading Brain Workshop.
Please visit the Brain Workshop web site for help & instructions!

From the main screen, press W to open the web site.
Pressing H will open the Help & Tutorial page.

Or visit:
   http://brainworkshop.sourceforge.net

Configuration options are available in the file 'config.ini'
in the data folder. This file is created when the program is
first launched. Windows users can access this file via the
'Configuration' item in the Brain Workshop group in the Start Menu.
Mac OS X users will need to right-click on the brainworkshop icon,
select "Show Package Contents", and browse to Contents/MacOS/data/.

Let us know if you have any comments or suggestions:

   plhosk@gmail.com
   jtoomim@jtoomim.org

Enjoy!

----------------------------------------------------------------------
*** NOTE TO LINUX AND SOURCE-CODE USERS: ***

Python 2.5 or later is required to run Brain Workshop on Linux. Python 2.4
may also work as long as the python-ctypes package is installed.
[Note: Windows versions and Mac OS X .app bundled versions of Brain
Workshop have python included.]

The latest version of python can be downloaded here:
      http://www.python.org/download/releases/

Music support requires AVBin (highly recommended!)
AVBin is included in binary distributions of Brain Workshop, but source
code users will want to download AVBin here:
      http://code.google.com/p/avbin/

Detailed instructions and links for Mac OS X, Linux and win32 source
installation are available on the Brain Workshop web site:

    http://brainworkshop.sourceforge.net

----------------------------------------------------------------------
Change Log:

4.8.1:
* Bugfix release.  Text shows up properly on Menu screens with
   BLACK_BACKGROUND=True.  Bug in graphing code fixed which caused some
   stats.txt files to not be graphable.  Option added to remove post-
   session feedback (requested by a researcher).  Daily session counter
   fixed.  Trials per session at startup fixed.

4.8:
* Changed config.ini file format.  Existing config.ini files will be
   renamed and replaced.  Users will have to migrate their
   customizations manually.
* Added Multi-stim modes, whereby objects appear in two to four places
   in the 3x3 grid at the same time.  Objects can be differentiated
   either by image or by color.
* Added Crab modes.  In crab modes, you have to reverse every N stimuli
   when matching, so that in 3-back, if the stimuli you saw were the
   first line below, then you would be matching them against the
   second line, like thus:
        ABCDEFGHIJKLMNO
        ---CBAFEDIHGLKJ
* Full support for multiple users and/or profiles.  This lets you
   easily keep separate statistics for different settings (for example,
   with different timings or with JAEGGI_SCORING in the config file) or
   for different users.
* Added an "interference" setting, whereby a certain percentage of the
   time Brain Workshop will generate trials designed to be particularly
   tricky, such as by making the current stimulus match the stimulus
   (n-1), (n+1), or (2n) trials ago, or (in multi-stim mode) by
   swapping the positions of the stimuli (n) trials ago.
* New mode-, sound-, and user-selection screens.
* Changed how often matches are generated for modes other than Dual
   N-back.
* Made Brain Workshop ask for donations, by default every 100 sessions.
   You should do as the program asks.  (This behavior can be
   changed in the config.ini file.)
* Trial-by-trial session data are now recorded to disk in Python's
   pickle format in the USERNAME-sessions.dat files.
* Changed how scores are calculated in graphing; the percentage of
   items correct now affects the exact score in addition to the
   N-back level.
* All of the music files and some of the other media files have been
   removed for copyright reasons and replaced with free alternatives.

4.7:
* Added Dual Audio n-back modes. Go to the Sound Selection screen to
   choose the sound set and channel (left, right, center) for each
   sound stimulus.
* Number of trials per session now increases automatically with higher
   n-back levels. The calculation can be adjusted from the config file.
* Timing resolution has been increased to 0.1 seconds, with a maximum
   speed of 0.3 seconds per trial.
* Toggling Manual Mode no longer reverts to default settings.
* Title screen graphic is now colored inversely when a black background is
   selected.
* Stats file may be specified on the command line with --statsfile,
   complementing the --configfile command line parameter.
* Comments may be added to the stats file on separate lines beginning
   with the # character.

4.5:
* First release with Quad N-Back and other new modes
* Includes various other improvements.

4.41:
* The size of the field with the FIELD_EXPAND option was decreased slightly.

4.4:
* Novice Mode was renamed to Jaeggi Mode.
* Jaeggi Mode will activate certain options to emulate the appearance
   of the software used in the original study. Two configuration options
   were added to control this behavior.
   [Note: to see the new config options, delete your current config
    file and relaunch Brain Workshop to generate a fresh config.]
* The data and res directories can now be specified on the command line
   using the --datadir and --resdir parameters
   (contributed by Timo Juhani Lindfors <timo.lindfors@iki.fi>).
* The daily rollover hour for stats can now be specified in the config file.
* A bug was fixed where certain trials would not show up in the list
   if the program was launched between midnight and 4 AM.
* A setting to skip the title screen was added to the config file.
* The grid lines and crosshairs can be toggled in the config file.
* A setting was added to select rounded or sharp corners for the
   solid-color squares.
* A setting was added to expand the size of the field to fill the screen.
* Arithmetic Mode: The acceptable decimal answers can be set in the
   config file.
* Three new music clips were added.
* The Clear Stats key (Control-C) is working again.

4.3:
* Variable n-back levels can be used with any game mode by pressing V
   in the Choose Game Mode screen.
* Sounds for the auditory n-back task can be selected by pressing S.
* Letter N-Back renamed to Combination N-Back.
* New Morse Code sounds can be used with any n-back mode.
   For the ultimate challenge try using Morse Code with Dual, Tri or
   Quad Combination N-Back. Press J to open a Morse Code reference page.
* Average n-back indicator will only count sessions specific to the
   current game mode.
* Progress graphs now start from 1.0 on the vertical axis to give a
   better overall picture.
* The cutoff for daily averages is is now 4:00 AM instead of midnight.
* Music and applause is stopped when entering the progress graph to
   avoid sound skipping. (The sound may not stop in Linux due to
   driver limitations.)
* Config file changes: The starting N-Back mode and game speed is
   now separately adjustable for each game mode, and some colors
   can be customized. Variable N-Back can also be set as default.
   [Note: to see the new config options, delete your current config
   file and relaunch Brain Workshop to generate a fresh config.]

4.22:
* There's a new title screen.
* Launching in Novice Mode will no longer cause a crash.
* Progress graph: date axis will no longer skip days.
* Progress graph: data points are now indicated with a dot.
* Num pad should now work properly with Arithmetic N-Back modes.
* Difficulty of Dual Variable N-Back has been increased slightly.

4.2:
* Added new mode to stretch working memory: Dual Variable N-Back.
   The n-back level is displayed in the center and changes
   randomly every 3 seconds.
* Added single-task n-back modes: Position N-Back and Audio N-Back.
* Default config file is no longer packaged with the download
   so upgrading to this version won't overwrite existing
   configuration settings. The config file config.ini will be
   created if necessary when BW is launched for the first time.
* OpenAL is now the default sound driver in Linux if available.
   If you're having sound problems, it may help to install the
   python-openal package.
* There's no longer any need to install pyglet on Mac OS X or Linux.
   It's now included with the source distribution.

4.12:
* Fixed level increase threshold in Novice mode
* Novice mode now generates 4 visual matches, 4 audio matches
   and 2 simultaneous matches, matching the formula used in the
   original study.

4.11:
* Fixed level decrease threshold in Novice mode
* Added a configuration option to use the pre-4.1 flat squares
* Two changes to Novice Mode to eliminate the last of the differences
  compared to the original study protocol:
     1. Exactly 6 position and 6 audio matches are now generated each
           session
     2. The score for the session is set as the lowest of the two
           individual modality scores (visual & audio).

4.1:
* The squares in Dual & Triple N-Back have a new look.
* Individual scores for each input category (position, sound, etc)
   are shown in the graph screen.
* The number of sessions below 50% required to trigger a
   level decrease has been changed from 1 to 3.
* New piano sounds are available in the config file to test your
   tonal memory.
* Pressing the ESC key during a session will return you to the
   main screen instead of quitting the program.

4.04:
- Added the division operation to the Arithmetic N-Back modes.
   Use the period key '.' to insert a decimal point.
   Each of the operations (add, subtract, multiply, divide)
   can be turned off or on in any combination in the config file.
- Fixed a bug where if you had just advanced to a new level and
   quit BW, the next time you restarted you would be back at
   the previous level.
- Added config option to play music in Manual mode.

4.03:
- Added new number sounds (0-13). Either the letters or the numbers
   will be chosen randomly at the start of each session.
- The female voice sounds are now selected by default.
- Added two new game modes, Dual Arithmetic N-Back and Triple
   Arithmetic N-Back. Press N from the main screen to access
   the extra game modes.

4.02:
- Fixed sound driver selection in Linux.
- A few minor changes related to Arithmetic N-Back mode.

4.0:
- New game mode: Arithmetic N-Back (see tutorial for details)
- Optional Novice mode (aka BT mode) emulates the original study
  protocol.
- New NATO Phonetic Alphabet sounds (alpha, bravo, charlie, etc).
   The old sounds are still available as an option.
- Keep track of your daily progress with the new graphing feature.
- Export your history of daily n-back averages to a text file
  for easy pasting into a spreadsheet.
- Adaptive level-changing model ensures you're always playing
   at the right level.
- Keyboard keys can now be redefined.
- Feedback for missed cues is displayed.
- Feedback can be turned off in the config file if desired.
- Text can be hidden during gameplay to reduce distractions.
- Optional full-screen mode for a larger, distraction-free
   playing field.
- Optional black background reduces eye strain.
- Easy config file provides access to configuration options.

3.1:
- Enabled high performance VBO (vertex buffer object). If you get a
   MissingFunctionException, use the --novbo command line parameter
   to launch Brain Workshop.
- Changed preferred sound driver to ALSA on Linux.
- Converted letter sounds to 44.1 KHz to alleviate crackling problem
   on certain sound hardware.

3.01:
- When first loading, if the last session completed was in Standard
   mode, Brain Workshop will start at the same n-back level.
- Only today's sessions are loaded in the history chart.

3.0:
- Three consecutive scores of >=80% are now required to advance levels,
   as indicated by the grey/green squares in the top left corner.
   A grey square will turn green if a >=80% score is achieved and a
   green square (if any) will turn grey if the score is below 80%.
   Once both squares are green and another 80% is achieved, the level
   increases. A 100% score will cause an instant advancing.
- The entries on the session history chart will turn green if
   the session is >= 80%. The chart now displays in a variable-width
   font.
- Added the time.sleep() workaround to reduce CPU usage on OS X.
   Disabled Vsync to eliminate an error message on certain machines.
- New columns have been added to the stats.txt file, including
   individual percentage scores for the six input types. Please see
   Readme-stats.txt in the data directory for details.

2.7:
- Added a new column in the stats file:
	0 = Standard mode, 1 = Training mode
- one new music clip added
- Added an encouraging message if you get below 40%

2.64:
- Lowered level advance threshold to 80%.
- Added a workaround for pyglet.gl.lib.MissingFunctionException
  which occurs on certain video cards.

2.63:
- Fixed a bug causing 100% CPU utilization.
- Fixed a crash caused by the music clip feature.
- Reduced startup time and memory footprint.

2.62:
- Contribution to the n-back average is now calculated like so:
	(nback - 1) + percentage / 100
   This means the average n-back level for a single 4-back session
   with a score of 50 percent will now be 3.5 instead of 2.

- Fixed a bug in the input feedback that would show correct responses
   as incorrect (this did not affect stats).
- Added more music clips and adjusted the length and volumes of the
   existing ones.

2.6:
- Added color feedback on input. The input labels ('A: position' etc)
   will turn red for incorrect, green for correct and blue if
   there haven't been enough trials yet.

2.5:
- Fixed bug where a bogus stats entry would be created under
   certain conditions when switching from Standard to Training mode.
- Removed the need for Tkinter on Linux and OS X.

2.4:
Added music clips which play when certain scores are achieved.

2.3:
- Added a Sessions Today indicator which shows the total number of
   sessions completed this calendar day. Useful for tracking progress
   on your 20 session per day training quota.
- Added possibility of different stats files on the command line.
     Give each person in your family a separate desktop icon!
        example: brainworkshop.exe --statsfile fred.txt
                 brainworkshop.exe --statsfile mary.txt
- Brain Workshop now starts in Standard mode. This enforces
  certain settings for number of trials and time per trial,
  making it easier to compare scores. Currently these are
  specified as follows:
	All modes are 20 trials per session.
            Dual N-Back: starts with 2-back, 3 seconds
          Triple N-Back: starts with 2-back, 3 seconds
     Dual Letter N-Back: starts with 1-back, 3 seconds
      Tri Letter N-Back: starts with 1-back, 4 seconds
     Quad Letter N-Back: starts with 1-back, 4 seconds
- Fixed a bug in the average n-back calculation
- Changed stats file format from tab-separated to comma-separated.
   Old stats files will still load successfully.

2.2:
   - Session stats are now output to the file data\stats.txt
   - Previous stats are loaded upon launch.
   - Added an option to clear stats (this does not affect stats.txt)
   - Average N-Back level is calculated for the last 20 sessions.
        The contribution of a particular session is calculated:
           Contribution = (N-back level) * (Percentage score) / 100
        Average is calculated as:
           Average = (sum of contributions) / (number of sessions)

2.1:
   - Added three new challenging game modes:
      Dual Letter N-Back, Tri Letter N-Back, Quad Letter N-Back
   - Adjusted level advance threshold from 100% to 90%
   - Adjusted "applause" threshold from 80% to 70%

2.0:
   - Applause sound now plays when a score of 80% is achieved
   - Version check is now performed on launch
   - Added a workaround for the pyglet.gl.ContextException error
      which occurs on certain video cards
   - Added a more descriptive error message in case an old version
      of pyglet is installed
   - Fixed cosmetic issue with the session history label on Linux
