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
* You need pyglet installed for this to work, and mujoco for the Marble Maze's physics (`pip install mujoco`).

### Code layout

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

### Long-term memory games and their media libraries

The task hub's *Long-term memory* category holds three games that work
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
- **Trivia** — a general-knowledge question and a list of answers, from
  TriviaQA. The other two ask what you saw a minute ago; this one asks
  what you knew before you sat down. Its material is fetched by a
  command of its own, `python -m neural_workshop.trivia`, and it has a
  section [below](#trivia).

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
| `div2k` | 900 photographs, 2K resolution | ~4 GB |
| `ucf101` | 13,320 action clips, 320x240, a few seconds each | ~7 GB |

The `div2k` library feeds the jigsaw puzzles and comes by a different
route: the Hugging Face dataset (`eugenesiow/Div2k`) is a loading
script over the original NTIRE challenge archives rather than hosted
rows, so the fetch downloads those zip archives whole and unpacks
them. The default hundred images is the validation archive alone
(~430 MB); asking for more pulls the 3.5 GB training archive too. The
download resumes where it left off if interrupted. DIV2K is published
for academic research use; the images are collected from the Internet
and their copyright stays with their owners.

The `ucf101` library feeds Video Jigsaw, Video Sequence and What Happens
Next. Hugging Face holds it
(`quchenyuan/UCF101-ZIP`) as a single 7 GB zip, and the fetch never
downloads that whole: it reads the zip in place with HTTP range
requests and pulls only the clips it unpacks, spread across all 101
action classes. The default thousand clips is about half a gigabyte:

```bash
.venv/bin/python -m neural_workshop.datasets ucf101
```

Asking for all 13,320 tops out under 7 GB, and the library carries a
hard 50 GB ceiling that the fetch checks clip by clip. Playing the
clips needs the `ffmpeg` program on the path (`brew install ffmpeg`,
`apt install ffmpeg`). UCF-101 is published for research use by the
University of Central Florida; the clips come from YouTube and their
copyright stays with their owners.

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

### Notebook

More to remember than a head can hold, and a few lines of paper. A
round is a stream of cards: a fact card gives a code (*Gate Maple:
382*), and some cards later a question card asks for it among a few
codes. On any fact card, **Write** beside a notebook line copies the
card onto that line, over whatever was there. The notebook stays in
view, so a code written down is a code that can be read back. A round
passes when every question is answered right.

| Rung | What it adds |
| --- | --- |
| 1 | One code, asked at once; two lines. |
| 2+ | More codes, more of them waiting at once (up to eight), and longer between a code and its question. |
| 3+ | Four codes to choose from. |
| 6+ | Cards marked *not needed* that waste a line if written. |
| 8+ | **Updates**: *Gate Maple is now 517*, after which the old code is wrong -- and offered. |
| 16+ | **Fewer lines** than codes waiting, one fewer every second rung, so the rest is held in the head: by rung 30, all but one. |

What it measures is whether the paper gets used well -- what deserves a
line, which line to give up, when to rewrite one -- and, past rung
sixteen, how much is carried besides. A careful keeper that writes
everything needed onto a free or finished line passes every round up to
rung fifteen with the notebook alone and almost none after it without a
head as well. Thirteen agent ports: four answers, write onto lines one
to eight, Next. Turn-based, so it takes the think clock.

### Where Was It?

Rooms shown one after another -- a tiled floor and solids standing on
its squares -- for as long as you like; then one comes back with one
change. Click where: the thing that moved, the square a missing thing
stood on, either of two that swapped, or the thing that changed
colour. The other rooms, seen before and after the tested one, are
what makes it hard: memory for where, under interference.

| Rung | What it adds |
| --- | --- |
| 1 | One room, four things on a four-by-three floor; one moved or gone. |
| 4+ | Two rooms, then one of them. |
| 7+ | Three rooms, five things; two may swap, or one change colour. |
| 10+ | Every room holds **the same things**, only placed differently; five-by-four. |
| 13+ | Four rooms. |
| 16+ | The room comes back seen **from another side**, 25 to 45 degrees round. |
| 20+ | Five rooms of seven things on six-by-five, seen from anywhere round; a moved thing moves only to a neighbouring square. |

After the verdict the right squares are outlined. Thirty-one agent
ports: 0-29 click a floor square (counted across each row from the
front left corner as the room was first shown, then row by row away),
30 goes on to the next room. Turn-based, so it takes the think clock.

### Trivia

```
      Which American-born Sinclair won the Nobel Prize
                for Literature in 1930?

                 1. Julie Andrews
                 2. Nathanial Hawthorne
                 3. Sinclair Lewis
                 4. William Howard Taft
```

That is a rung-four deal as the game actually made it, and it shows
what the shape rule does and does not buy: four names, so being a name
says nothing, and three of them people rather than the only person on
a list of dates — but *Julie Andrews* is there because she is a name in
the pool, not because she is a plausible novelist.

The questions are [TriviaQA](https://huggingface.co/datasets/mandarjoshi/trivia_qa)'s
— 138,384 of them in the `rc` training split, written by trivia
enthusiasts. Only the question and its answer are wanted, so the fetch
takes the `rc.nocontext` configuration, which is the same rows with the
evidence documents left off:

```bash
.venv/bin/python -m neural_workshop.trivia          # 10,000 questions
.venv/bin/python -m neural_workshop.trivia 50000    # or more
```

It pages the datasets-server a hundred rows at a time into
`<data dir>/trivia/` and distils them into one tab-separated index.
Standard library only, resumable, and a page already on disk is skipped.
Until it is run the game deals from 120 questions written into
`neural_workshop/trivia.py`, which is enough to play and not enough to
stay fresh — the options screen says which pool you are on rather than
letting you wonder why a question came round again.

**TriviaQA is not multiple choice, and this is.** The dataset gives a
free-text answer with its aliases; the screen has to offer something to
pick between, so the wrong answers are other questions' right ones.
That choice is the whole of the difficulty, and it has two rules.

**A wrong answer has to be wrong.** *Chicago* and *Chicago, Illinois*
are the same answer twice, and a question with two right options on it
is marked wrong half the time while looking like a hard question. So
the alias lists are kept — that is what they are for — and a candidate
is refused if either answer is in the other's aliases, in both
directions.

**A wrong answer has to be the same shape.** `1969` against `Portugal`
is not a question about the moon landing, it is a question about which
option is a year. So the upper rungs draw only from answers of the same
shape: a year against years, a name against names, a number against
numbers. The shapes are read off capitalisation and digits and are
nothing more than that — the claim is only that the options look alike
enough that their looks are not the answer. A real category would need
a knowledge base, and one wrong a twentieth of the time would be worse
than this, because its failures would land on the interesting questions
rather than on random ones.

The seven-rung ladder is those two dials and nothing else: rungs one to
three widen from two options to four with the wrong ones drawn from
anywhere, rung four keeps four options and matches them by shape, and
rungs five to seven widen again to eight. **It is deliberately not a
ladder over the questions.** TriviaQA does not say which of its
questions are hard, and a measure of that read off an answer's length
or its frequency would be invented rather than measured. Measured on
the built-in pool: on rung one the right answer is the only one of its
shape more than 40% of the time, and on every matched rung under 5%.

**As an agent environment it is the one task that is not solvable from
its own frames**, and that is worth saying plainly. Everywhere else in
the workshop the premises, the board or the thing to remember are on
the page. *Which American-born Sinclair won the Nobel Prize for
Literature in 1930?* is not answerable from the pixels of that sentence
by anything that does not already know. It is a probe of what a learner
brought with it rather than of what it can work out, and a learning
curve drawn on it is a curve about a prior. Random play is paid, and at
rung one it is a coin: the free floor there is 50%, which is the
highest in the workshop and worth knowing before reading anything off
such a curve.

### Procedurally distorted letters

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

### Working memory

**In the Dark.** A row of lamps is lit behind you in colours you are
never shown. You walk through a string of rooms and each one does a
single thing to the lamps — paints one a colour, turns one on to the
next, swaps two over, copies one onto another — and at the end you are
asked what colour some of them ended up. Rooms are drawn in full. The
lamps never are.

The point is what the screen makes impossible. Nothing on it at any
moment says what colour any lamp is, and because a room is drawn from
its operation alone, two runs with different lamps behind them draw
*exactly the same pixels* and want different answers. A player reading
only what is in front of them is not handicapped, they are at chance,
and by construction rather than by measurement. The screen tests check
it the only way worth checking: render the same rooms over two
different hidden arrangements and compare the frame digests.

The floor is a proof rather than a benchmark. Walk a lamp's history
backwards — a copy moves which lamp you are following, a swap
exchanges it, a turn shifts the value, a paint fixes it and ends the
chain. Until the chain reaches a paint, the final colour is a
*bijection* applied to some lamp's unseen starting colour, and those
are uniform. So a player who remembers fewer than `needed` rooms holds
no information at all and scores exactly one in `colours` — measured
across every rung at 0.0000, not "near zero". `trace()` computes that
distance in one pass and `belief()` recomputes it by enumerating every
starting arrangement, so the fast derivation is held against the slow
one rather than trusted.

Dealing walks and keeping the deep ones does not work: the median walk
pins its weakest question four rooms from the end against a floor of
twenty, and seven deals in eight ask about a lamp no room ever pinned.
So a walk is laid *backwards*, refusing to paint a lamp a question is
still resting on until the floor is behind it. Both floors then hold
without searching, at a fifth of the cost.

The second axis exists because distance is not effort: a chain twenty
rooms long whose value merely sat there is a long wait, not a hard
question, so `work` counts only the rooms that actually moved or
changed the value being carried.

**Fog of War.** A braided grid of corridors, an avatar, and a
two-cell eye; everything further off is flat black. The dark is real
rather than decorative — the frame is drawn from the revealed set
alone, so changing an unseen cell moves no pixel, which the tests
check by changing one.

The screen is deliberately bare: no step counter, no coverage bar, no
bump flash, nothing that blinks. The frame is a pure function of where
the walker is and what it has revealed. Anything an agent could make
happen *without going somewhere new* is something it would learn to do
instead of exploring — an agent on a prediction-based intrinsic reward
elsewhere learned to bump walls rather than travel, at corr(payment,
bumping) +0.79 against corr(payment, coverage) −0.59, because bump
animations were cheaper to produce than distance. Measured here: 1196
bumps across ten worlds changed zero bytes.

It is filed under working memory rather than planning because the
planning category holds tasks that score against a computed optimum
and this one has none — and because with the map off, which is how it
ships, what it asks for is holding where you have been.

**Removals.** A yard of vans, a stack of boxes, and a pile of things
to pack. One move happens at a time and each is drawn in full — this
thing into that box, that box into another box, that one into a van,
these two swapped over — and at the end you are asked which van some
of the things ended up in. Where anything actually *is* is never
drawn.

That question is not "what did you just see". A thing is in a box,
that box is in another, that one is in a van, and no single move ever
said so: the answer is a *composition* of facts learned at three or
four separate moments, each of them ordinary at the time. It is a
different faculty from In the Dark next door, which asks you to carry
six values and update them; this asks you to carry a shape and then
walk it.

The floor is half proof and half measurement, and it is worth being
clear which half is which. The proof is that a short memory settles
nothing: every move is unconditional — a pack writes a constant into
one slot, a swap exchanges two, and neither reads a value to decide
what to do — so the resting map is a fixed function of the starting
one, and each entry is either a constant the walk wrote or, traced
back through the swaps, a slot it never touched. Fall off the chain
onto one of those and what is there was settled before anything you
saw. Measured: a player recalling the last `floor - 1` moves is
certain of exactly *none* of the questions, on every one of the twelve
rungs.

What the proof does not settle is what such a player should then
guess, since the state before the tail is the generator's doing rather
than a coin. So that half is measured: over three thousand rounds a
rung the van an answer lands in is even to within two standard
deviations on all twelve, and the best fixed guess beats chance by at
most 0.010. Between them the floor is one in `vans` and there is
nothing to be had below it.

Dealing walks and keeping the deep ones fails here for a sharper
reason than it did in In the Dark: a random walk almost never *nests*
anything, so the chain the whole task is about comes out one hop long
and the rung has nothing to grade. Chains are therefore designed first
— a thing, its box, that box's box, its van — and the walk is built
around them, with each chain given one link among the early moves so
its answer is pinned at least as far back as the rung promises. A
chain reuses a box already standing at the right depth under the right
holder about half the time, which is what lets the top rung ask for
five hops from ten boxes instead of twenty.

Three numbers grade a round because they are not the same number:
`needed` is how far back the memory must reach, `nest` is how many
hops the answer is composed of, and `churn` counts moves that touched
a chain and were then overridden. The middle one is the axis the task
exists for — a chain twenty moves back but one hop long is a long
wait, not a hard question.

One verb was designed and dropped. *Tip* — empty a box out onto the
floor — is the most natural move in a removal, and it is not here: its
effect depends on what is inside the box and so on the unseen start,
which makes an unpinned answer a restricted draw rather than a uniform
one and turns the floor from a proof into a bound. An exact floor is
worth more than a richer verb.

**Chain of Custody** asks Removals' question through motion instead of
containment. A carousel of boxes runs round a belt; one is ringed for a
moment at the start and then looks like all the rest. A claw slides
round the ring, picks a box up and puts it down, and the round is
scored on whether the box that reaches the bay is the box that was
ringed — in the state the bay asked for.

Everything on the belt is there because it affects that one box. The
charger clears the charge mark in a single pass and leaves the box too
hot, so the route is charger, then cooler, then bay, and cooling first
is simply wasted. The painter is not a service anybody asks for: it is
a hazard, and it moves the coat on of every box that rides past it, so
following a colour loses the thread on its own. Charge bleeds away on
the belt but not in the claw, which makes holding the box the safe
place to keep it and the belt the price of reaching a machine.

**A claw cannot chase a box.** Both move one slot a step, so a claw
behind a box stays behind it forever, and the way to pick something up
is to stand still and let the ring bring it to you. That is the first
thing the task teaches and it is deliberately not signposted.

The guessing floor is on the ladder rather than emergent, because
deriving it made the rungs get *easier*: with one coat per two boxes
the field is two boxes wide however many are on the belt, so a rung
that added boxes added nothing on the axis the task is named for.
Named instead, it climbs from one box in one at the bottom to one in
six at the top, and the run reports it beside the score — a run at rung
three is guessing one in two and a half and one at rung ten one in six,
so the same percentage is a different achievement.

The budget is a clock rather than an allowance: it is spent by the belt
rather than by the action, so a person waiting by not pressing anything
and an agent spending an action to let a beat pass are charged the same
beat. Every rung is winnable — a player who already knows which box is
the Core delivers it on 300 of 300 deals, using at most 28% of the
budget, which `tests/oracle_custody.py` measures and the suite checks.

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

**N-Cup Monte** hides a ball under one of several cups and shuffles
them; keep your eye on the right cup through the swaps and click it
when the music stops. The cup count and the number of swaps are both
yours to set, and the adaptive option adds cups as you keep finding
the ball.

**Moving Targets** is the classic multiple-object-tracking task: a
few balls flash a colour, then every ball looks the same and the
whole flock bounces around the screen. When the motion stops, click
the balls that flashed — nothing marks them any more, so the only way
to know is to have followed them the whole way round. You choose how
many balls are on screen and how many of them are yours to follow
(always at least one ball fewer than the flock, or the question would
answer itself), plus the speed and how long the motion lasts. The
balls deliberately pass through each other rather than colliding: two
identical balls crossing is exactly the moment tracking is hard, and
bouncing them apart would delete the difficulty in the name of
physics. With the adaptive option a perfect round asks you to follow
one more ball, and a miss asks for one fewer.

**Lookout** is a vigilance task: coloured shapes drift and bounce,
and each one changes its colour or its form every couple of seconds.
The HUD shows one coloured shape — say an orange triangle — and there
are two answer keys, the home-row pair every psychophysics lab uses:
**F** says "a triangle is on screen", **J** says "something orange is
on screen". The options choose which of the two channels is live:
just the colour, just the shape, or both at once. No channel is
satisfied at the moment the glyph is dealt; the churn brings the
match, and the scoring is honest signal detection per channel: a
press while that channel's match is up is a hit timed from the
moment it appeared, a match that churns away unpressed is a miss,
and a press over nothing is a false alarm. The channel choice is the
difficulty dial: a colour alone "pops out" and the eye finds it in
parallel, a shape is a little slower, and watching both at once is
divided attention — two independent signals through one churn, each
with its own key. The adaptive option adds a shape to the flock on a
hit and removes one on a mistake.

**Pursuit** is "keep your eye on the ball" with the hand made to
follow: one shape wanders the screen and the job is to hold the
mouse cursor on it. The shape does not move like a ball — it breaks
direction without warning, surges and dawdles, swells and shrinks,
and now and then becomes a different shape entirely, everything
aimed at the moment prediction fails and the hand has to catch up.
The score is continuous rather than hit-or-miss: the share of each
round the cursor spent on the shape, plus the average miss distance
in pixels — a dense signal fit for training real-time control, human
or artificial. The difficulty is six independent dials rather than
one: base speed, surge depth, how often the direction breaks, how
sharp the breaks are, size wobble, and shape shifting, with a zero
switching an axis off entirely. The adaptive option multiplies speed
and break rate together in five-per-cent steps — hold on 70% of a
round and it tightens, drop under 40% and it eases — so a run
settles onto a precise frontier, and the multiplier it settles at is
reported as part of the score.

**Out of Sight** starts where Moving Targets ends and then takes the
picture away. A few dots flash a colour among the rest, and two things
then make the frame on screen too little to answer from. Every so often
two dots are aimed at the point exactly between them, so they arrive
together, overlap as one and pass through — at that instant nothing
visible says which came from which side. And solid slabs are drawn over
the field, so a dot that goes behind one is simply not there for a
while; a slab that hangs over the wall lets a dot bounce while it is
hidden, and come back out somewhere the line it went in on never
reaches.

The question is asked *during* the motion rather than after it. Now and
then one dot is ringed and there are two keys — **J** for "that one is
mine", **F** for "it is not" — with a second and a half to answer while
everything keeps moving. The ring hunts the moments identity was just
at risk: the dot that has this second come out from behind a slab, or
the one that has just passed through another. Each question is a coin —
deliberately not an even split of the round, because an even split
would pay for counting answers rather than holding dots, and a coin
still leaves any fixed answer on fifty per cent. Asking at the end
would let a good guess in the last moment stand in for having held on
the whole way; asking in the middle cannot be answered that way.

Every difficulty here is one you can turn off and measure against: the
crossing rate, the number and width of the slabs, the dot count, how
many are yours, the speed. What none of the dials can do is make the
task unfair — the dots move in straight lines and bounce off walls, and
never change course while hidden, so a tracker that carries a position
and a velocity for each dot can follow every crossing and predict every
emergence exactly. Nothing is ever decided by a coin. That is also what
makes it a hard task for anything reading one frame at a time and a
fair one for anything carrying state, which is the whole point of it.
The adaptive option asks you to hold one more dot after a round that
comes back whole, and one fewer after any mistake.

**Donkey** is the 1981 original, which was four hundred lines of BASIC
and one idea: a car, a two-lane road, donkeys standing in it, and the
space bar to put you in the other lane. Hit one and the road is over.

The original's only difficulty was that the road got faster, and speed
here is a **dial** rather than a rung. That is the one place this
departs from it and it departs on purpose: one row is one step at the
agent boundary, so a rung that ran the road faster would be a rung a
person feels and a learner cannot, and the two would be playing
different ladders while reporting the same number.

What carries the ladder instead is **the swerve**. Crossing takes rows,
it cannot be called off, and while the car is across the middle a donkey
in *either* lane hits it — so the row a donkey arrives on is a row you
have to be clear of already. Press when you see it and you swerve into
it. Up to level five the crossing is one row wide and the press goes in
on the row before; from six it is two rows and from ten it is three.
That is the whole content: not *what* to do, which is obvious, but how
far ahead of the donkey to have already done it. Measured over two
hundred deals a rung, swerving on sight clears every road while the
crossing is one row wide and 6%, 3%, 3%, 1% and 6% of them on levels six
to ten.

**The road is finer than it looks.** A row is what the screen draws and
not the unit the rules work in: the road is cut into four sub-rows a
row, the car moves one of them a tick, and the car and the donkey each
have a *length*, so a hit is the two bodies overlapping. Resolved a row
at a time — which is how it shipped first — "did it hit" could only be
answered to within a whole row, and a round ended on the tick the car
entered the donkey's row rather than on the tick they touched, a car's
length early. The playfield is the same size and shows the same amount
of road; the whole of the cost is that the arrays are four times longer.

Two things about it are worth saying because they are the sort of thing
a task description usually leaves flattering. First, it has **no
planning depth**, and it was built expecting some: a road is laid a
sub-row at a time and a donkey goes down only where the set of surviving
car states stays non-empty, which guarantees every road has a line
through it and — measured — leaves nothing standing that a press aimed
at the swerve cannot handle. `tests/test_donkey.py` asserts that finding
rather than the hoped-for one, so a future generator that quietly
flattened or deepened the ladder fails a test instead of leaving the
prose lying. Second, the guessing floor is **zero**, on every level: a
press starts a crossing it cannot call off, so a coin a tick leaves the
car across the middle most of the way, and across the middle every
donkey in either lane is a donkey in yours. So "better than chance" is
not a bar worth clearing here, and a number from this task should be
read against the swerve-on-sight column instead.

Nothing is downloaded for this one — the road is generated.

**Two Hands** is that road stood up into three dimensions, with
everything the flat game left out and a sky over it. Three lanes rather
than two, nine kinds of thing standing in them, a jump, a throttle, a
deadline that makes the throttle matter, and targets drifting over the
horizon that are shot with the mouse. The name is the task rather than
the fiction: **one tick takes one action**, the wheel and the sights
come out of that one budget, and what is measured is how a player
splits an attention that cannot be divided.

Every rule in it is Donkey's rule about committing early, with the
distance you commit over now something you chose. The **swerve** takes
a fixed number of *ticks* and covers both lanes for all of them, so at
four sub-rows a tick you are across the middle for four times the road
you were in first gear. The **jump** clears anything flat, and only if
the car is off the ground for the whole overlap — which is `speed ×
hang` against a hazard's five sub-rows, so a single jump at a crawl
comes down inside a log. You can hop over one a piece at a time
instead, and every hop is a tick. So the throttle pulls both ways at
once: faster is worse for the swerve and better for the jump, and there
is no setting to leave it at.

The **deadline** is what stops the answer being "crawl". It is written
as a multiple of the road's *own* best line rather than as a pace —
1.70 of it at the bottom of the ladder down to 1.25 at the top — so
every deal at a rung asks the same thing of you rather than the hardest
deal setting the bar for all the others. Measured over forty deals a
rung, the same aimed dodge held in first gear clears **nothing at all**
on any rung, and it loses to the clock rather than to a truck: at the
bottom of the ladder it runs out of time on forty deals out of forty.

**The sky cannot touch the car**, and that is deliberate. It is a
second *task* rather than a second hazard, so what it costs the road is
attention and nothing else, and the cost comes out as one number. The
number is this. The same driver, three ways, over sixty deals a rung:

| | rung 1 | rung 5 | rung 10 |
|---|---|---|---|
| never looks up | 97% | 53% | 33% |
| shoots on spare ticks | 97% | 53% | 33% |
| shoots on sight | 90% | 7% | 0% |
| targets a road, spare | 0.8 | 4.3 | 6.0 |
| targets a road, on sight | 0.8 | 2.0 | 3.9 |

Taking the sky **only on the ticks the wheel had no use for** costs the
road nothing at all — not a little, nothing — and there are more such
ticks than there look to be, because the wheel is deaf for the whole of
a swerve or a jump and those ticks are the sights' for free. Taking it
the moment anything is up there loses most of the roads *and gets fewer
targets while it does it*, since the roads it is on end early. There is
no reading of that pair in which the greedy policy bought anything,
which is the finding: the cost of a second channel is not the channel,
it is taking it at the wrong moment. `tests/test_twohands.py` asserts
both halves, so a future generator that flattened the ladder or a
policy change that made spare ticks scarce fails a test instead of
leaving the prose lying.

The guessing floor here is **not** zero, unlike Donkey's, and it is
worth knowing the shape of it: five of the eleven ports do not touch
the wheel at all, so a uniform port is a hold five times in eleven and
the car spends most of a road going straight in first gear. That clears
about a fifth of the roads on the bottom rung and none at all from the
third. Anything read off the first two rungs is read against a fifth;
anything from the fourth up is read against zero.

Every road has a **clean line through it** — no crash, no clip, inside
the clock — and the line is produced rather than assumed. Donkey could
keep that true as it laid the road, because its car moved one sub-row a
tick and what survived was a function of the sub-row alone. Neither
holds here, so this one lays the road and then solves it with a forward
dynamic program over `(sub-row, lane, commitment, speed)` — a DAG,
because every tick moves the car — and a road the program cannot finish
has a hazard taken out of it and is solved again. The transitions in
that program are the game's own `roll`, not a copy of it, so the solver
cannot come to believe in a rule the game does not have.

Nothing is downloaded for this one either — the road and the sky are
generated.

#### Overrun

A sentence sits in a lane and slides at the right-hand margin. Type it
away and the line is hauled back a word at a time; let the end of it
cross and a life goes. Clear a whole sentence and a life comes back.
You start with three, and the run ends when the lives do or when the
sentences do.

The word being typed is always at the **left-hand end** of the line,
so the eye has one place to look and only the clock moves it: clearing
a word takes the front off the line and what is behind it moves up
into the same place. That is also what makes the game a tug of war
rather than a chase — the drift pushes the end of the line at the
margin and every word typed hauls it back by its own width.

**A wave starts with as much clear road ahead of it as it has
characters.** This is the rule the whole task turns on and it is worth
being explicit about, because the obvious layout — every line starting
at the left-hand end of the lane — is what was written first and it is
wrong. Under it the road ahead of a line is *the lane minus the line*,
so a long sentence gets less time and has more to type, and the two
effects multiply. Measured at the sixth rung:

| layout | words a minute asked for | range over the sentences |
|---|---|---|
| runway = the text | 37.9 | 34.7 to 40.4 |
| every wave from the left | 27.9 | 13.5 to 40.4 |

The spread on the top row is the sentences themselves — a line with
long words in it is more keys for the same number of cells — and it is
a few words a minute wide. The spread on the bottom row is a **factor
of three**: the same setting would have been two different tasks
depending on which sentence came up, and the number printed on the
options screen would have been an average over both.

**The level is the clock and nothing else.** Every rung deals from the
same sentences, of the same lengths, out of the same vocabulary. So
the ladder is a typing speed and can be read as one:

| rung | drift, chars/s | seconds a wave allows | words a minute |
|---|---|---|---|
| 1 | 1.9 | 19.3 | 19 |
| 4 | 2.9 | 12.6 | 29 |
| 6 | 3.8 | 9.7 | 38 |
| 8 | 4.9 | 7.5 | 49 |
| 10 | 6.4 | 5.7 | 64 |
| 12 | 8.4 | 4.4 | 84 |

which is the range between hunting for the keys and not needing to
look at them. Freeform Tetris makes the opposite promise for the same
reason — its ladder is shape and never speed — and both exist so that
a number taken off one rung can be compared with a number taken off
another.

**A mistyped letter stays until it is rubbed out**, drawn in vermillion
over the letter it should have been. Ignoring a wrong key is kinder and
it is what the first version did, and the cost of it is the entire
floor of the task. With wrong keys ignored a correct prefix can only
grow, so a walk hitting keys at random lands a letter every twenty-six
presses — 2.3 characters a second at sixty presses a second. The
arithmetic says that beats the bottom three rungs. Played out rather
than worked out, it is worse:

| rung | 1–5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|
| waves cleared, wrong key ignored | 1.00 | 0.95 | 0.82 | 0.53 | 0.37 | 0.13 | 0.02 | 0.00 |
| waves cleared, letter sticks | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Two thirds of the ladder, cleared by something that cannot read. The
mean rate is not the race: the deadline walks forward every time a word
goes, so a walk that gets lucky in its first two words carries the
slack down the rest of the line, and that is the part that had to be
measured rather than reasoned about.

Twenty-seven ports at the agent boundary — twenty-six letters and a
rub-out, no submit and no space — which is the smallest port set of the
four word games. Random play is paid on every wave and paid nothing but
red, and the reason is the clock rather than the ports: a wave ends on
its own whether or not anything was typed. Over 900 steps, three seeds
apiece: no outcomes at all at the first rung, one at the fourth, one at
the eighth, three at the twelfth. Zero at rung one is the wave lasting
1,157 ticks, which is longer than the budget — not a gap in the
wrapper.

The text is the same Simple English Wikipedia bank Scramble uses, cut
to the sentences that fit a lane with their own runway: 24 to 44
characters out of the 20,000 commonest words, which is 10,151 of the
36,118 in the bank and 58 of the 70 written into the source for a
machine that has fetched nothing.

```bash
cd tests && PYTHONPATH=.. ../.venv/bin/python bench_overrun.py
```

#### Buzz Wire

The fairground game, in three dimensions and with the physics done
properly. A bent wire runs between two posts, a metal loop is threaded
on it, and the loop has to get from one post to the other without the
two ever touching. It is the only task here whose difficulty is the
*precision of a continuous action* rather than the choice of a discrete
one — Pursuit is its nearest neighbour, and the contrast is worth
stating: Pursuit's quarry is built to break prediction, while a buzz
wire is completely predictable and completely visible from the first
frame, and is hard anyway.

**The loop is a hole, not a point.** Contact is decided exactly,
between a circle in space and a tube in space, and one consequence
falls out of that for free and turns out to be the whole top of the
ladder. A wire crossing the loop's plane at an angle cuts an
**ellipse** through it, stretched along the lean by one over the cosine
of the angle: square on, a wire needs a hole its own width; at fifty
degrees, half again; at sixty, twice. So a bend has to be *turned
into*, and turned into early, because at the bend it is already too
late. Nobody wrote that rule; it is what the geometry says, and from
the seventh rung the loop stops aiming itself and the wrist becomes the
player's problem. Turn it too far and the wire will not let you: the
hole stops admitting it at all and the loop jams.

**The arm is a physical object.** Mass, momentum, viscous drag, a
downward sag the hand never quite cancels, and a tremor that is a real
Ornstein-Uhlenbeck process rather than per-frame noise — it has a
correlation time of a tenth of a second or less, so it produces drifts
you have to catch rather than jitter that averages out. A tenth of a
second is inside anybody's reaction time. That is the honest statement
of what "superhuman" means at the top of this ladder: not a wire too
thin to see, but a disturbance nobody could answer in time and a
controller running at the frame rate could.

**The ladder was measured, not described.** `bench_buzzwire.py` flies
all twelve rungs with a reference pilot — a fixed-gain PD controller
that reads the true state and presses the same eleven ports a learner
has, one a tick. It flies the first nine clean, drops one wire in
twelve at the tenth, and cannot hold the eleventh or the twelfth at
all, buzzing ten and thirty times a metre on them. The gap runs from
ten and a half millimetres at the bottom to under two at the top; one
full press of a key is worth a sixteenth of the gap on the first rung
and a quarter of it on the last.

```bash
cd tests && PYTHONPATH=.. ../.venv/bin/python bench_buzzwire.py
```

The pilot is a yardstick and not a ceiling. It is deliberately *not*
allowed to read the tremor — that is a force inside the arm and nothing
on screen carries it — and an earlier version that did subtract it
cancelled the disturbance exactly and flew the whole ladder, which is a
measurement of the cheat rather than of the wire.

**The screen is a real renderer**, not a ray caster like the two 3D
screens next door: those draw a world of unit cubes on a grid seen from
inside, and this is a smooth curve in general position with a loop
threaded on it. So `neural_workshop.ui.scene3d` builds meshes — the
wire a swept tube on a rotation-minimising frame, the loop a torus,
both with per-vertex normals shaded by Lambert and Blinn — and hands
the hardware a depth per vertex through pyglet's shape shader, with
`GL_DEPTH_TEST` on around its own batch. A depth buffer rather than a
painter's algorithm, because a loop threaded on a wire is in front of
it and behind it at the same time and no sort gets that right. The
depth handed over is `near/z` rather than `z`, which is the quantity
that interpolates linearly across a triangle in screen space.

It stays inside a frame because of the division of labour: the camera
never moves and neither does the wire, so the five thousand triangles of
the scene are projected once when the level is dealt, and what is
rebuilt every frame is the loop, its shadow on the board and the slice
of wire the sight view looks down — about seven hundred vertices
between them.

The screen is split. On the left the whole wire, from a camera whose
angle is itself a difficulty dial — square to the run at the bottom of
the ladder, swung forty-four degrees round towards the wire's own axis
at the top, until a bend towards you and a bend away from you look
nearly alike and the board's shadow is the cue that is left. On the
right, the view down the wire from just behind the loop, and that panel
is not a luxury: a wire is forty centimetres of stage and the gap on
the top rung is under two millimetres, which drawn to scale is a fifth
of a pixel. Without it the one quantity the whole game is about would
not be in the picture, and a task whose answer is not in the frame is
not a task this workshop can wrap. What it does not show is the rest of
the wire, so when to start turning the wrist is still read off the left
panel.

The agent gets eleven opaque ports: six that shove the loop, four that
turn the wrist and one that braces the hand, with the four wrist ports
doing nothing below the seventh rung. Random play is paid and paid red
— eleven ports at random leave the loop wandering by the near post
until the clock runs out, and the clock running out is a verdict — so
the floor is the cost of getting nowhere rather than zero. The green
has to be flown for, and `tests/test_env_tasks.py` flies it with the
same pilot the ladder was measured with. Coach mode strings milestone
beads along the wire and pays the sign of the change in how many are
still ahead; the beads are spaced against the furthest one tick could
ever carry the loop, so one action moves the count by one at most and
the signal is a potential in the sense of Ng et al. rather than a hint.

### Perception

The *Perception* category holds two tasks. One asks about what is in
front of you; the other asks about something that is not on the screen
at all any more.

**Count** is a tangle of overlapping
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

**Mr. Time** shows a shape somewhere on the page, takes it away after
a moment, and then — after a gap drawn from anything between nothing at
all and the longest you allow — asks *how long ago did the shape
appear?* You type the answer in seconds and press Enter. Nothing on
screen was counting, which is the whole task: the interval has to have
been timed while it was happening, because by the time the question
arrives it is over.

That is the recall half. Set *Which half to play* to **produce** and
the question comes from the other end: the shape appears with a
duration written under it, and the task is to click it when that much
time has gone by. Space does the same thing as a click. Reading an
interval that has already happened and laying one down on cue are not
the same skill, and **both** shuffles the two so that neither can be
prepared for.

The ladder is precision, and it is what the name is about. Each rung
names a finer unit — seconds, deciseconds, centiseconds, milliseconds,
microseconds, nanoseconds — and tightens the band an answer has to
land in: 25% of the interval, then 10%, 4%, 1.5%, 0.5% and 0.2%. A
right answer asks for the next unit up; a wrong one gives one back.

**The band is a share of the interval rather than a fixed number of
milliseconds**, and that is the one design decision here worth
defending. Human interval timing follows Weber's law — repeated
estimates of a long interval scatter proportionally as widely as
repeated estimates of a short one — so a fixed window would make a
half-second trial and an eight-second trial two different tasks
wearing one name, and a run's score would mostly report which
intervals it happened to deal. With a proportional band every deal is
equally hard, and the number that comes out of a run is a Weber
fraction: the run summary reports it as *typically n% out*, which is
directly comparable between runs, between settings, and between a
person and a learner.

**The last two rungs cannot be climbed, and they are there anyway.**
Practised people land somewhere around 5-15% on this, which is rungs
two and three; rung four is very hard and rung five is past anything
the literature reports. Rung six asks for two parts in a thousand of a
three-second gap — six milliseconds — which is less than half of one
frame at sixty hertz, so it is past the *instrument* as well as past
the hand: an agent stepping the boundary sees time quantised to
16.7 ms and cannot express an answer that fine however well it has
learned. Nanoseconds are the ceiling of this ladder in the same way
0.3 s is Reflex's, kept so that reaching the rung below still means
something. The task reports which rung a run got to for that reason.

Two things the screen deliberately does not do. It never draws a
clock, and it never prints the tolerance before the answer is in — the
band is a fixed share of the interval, so a tolerance on the page is
the answer in different units. The options screen quotes the band
against the *longest* gap the settings allow, which leaks nothing
about the gap actually dealt.

Nothing is downloaded for this one — the shapes are generated, and
which shape it is carries nothing at all. It is a marker for an
instant, not a thing to remember.

#### Camera

You stand in a field of objects, and a photograph taken somewhere in
it is pinned in the corner of the screen. Walk there with WASD, look
around by dragging the mouse or with the arrow keys, rise and sink with
Q and E where the photo was taken off the ground, hold Shift for fine
movement and T to see the photograph full size, and press Enter when
your view is the photograph.

It is judged on the pose, not the picture: the match passes when your
eye is within the rung's distance of where the photographer stood and
your line of sight within its angle of theirs. The ladder has no top.
Every rung is a formula rather than a row in a table:

| Rung | Within | Objects | Field |
| --- | --- | --- | --- |
| 1 | 3 m, 30°, with a warmth meter | 4 | 14 m across |
| 5 | 81 cm, 10° | 14 | 28 m |
| 10 | 16 cm, 2.5°; photos taken off the ground, occluders | 29 | 49 m |
| 20 | 6 mm, 0.16° | 67 | 104 m |
| 40 | 8 µm, 0.0007° | 181 | 240 m |

Somewhere around rung twenty it is past any human hand, and the
tolerances keep halving every two rungs after that for as long as you
care to climb. The world grows with them — more objects, a larger
field, photographs from higher and lower and tilted further, blocks
that hide one part of the field from another, and objects that look
more and more alike until, at the top of the world's growth, there are
only three kinds. Then the world stops growing so a frame stays
drawable, and the tolerances carry on alone.

Every photograph is aimed at something, with at least one object close
enough to fix the distance by, so no rung is unfair for want of
anything to line up on. With *Climb a rung on a match* a match goes up
one rung and a miss comes down one.

The agent plays it through thirty-one ports: ten moves (walk four ways,
turn, look up and down, rise, sink) at three sizes each, and one that
says "this is it". The finest step is half the rung's own tolerance, so
every rung can be reached through the ports and what makes the top hard
is knowing where to stop. `tests/test_camera.py` proves it by driving a
policy that knows the answer to a paid match at rung 25, about a
millimetre. The task is turn-based, so it takes the think clock: study
the photograph longer, or start walking sooner.

### Reasoning

The *Reasoning* category holds ten tasks.

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

A grid of figures that follow rules you have to work out, with the
bottom-right panel missing and the candidates for it beside the grid
— four on the easy levels, eight otherwise. Answer with **1**–**8**
or by clicking a box. This is the shape of a Raven's Progressive
Matrices item, the standard test of reasoning that owes nothing to
language or to what you already know.

The grid itself is one of the difficulty dials: two-by-two at the
bottom — a rule shown in the least room it can be shown in, which is
what the easiest items of the real test are — three-by-three through
the middle, and four-by-four at the top, where the rules get room to
grow: four values distributed as a Latin square, three panels summed
into a fourth. Each rule declares what grid it needs, so a rule that
cannot show itself on a given grid is simply never dealt there.

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
* *Distribute* — a row's worth of values, and every row holds all of
  them in a different order. Laid out as a Latin square, so every
  column holds them all as well and the missing value can be read off
  either. This is the rule people picture when they picture a Raven's
  item; on a four-by-four grid it distributes four.
* *Arithmetic* — the last value is the first plus or minus those
  between. Only ever applied to how many figures there are, where it
  is something a person can actually do in their head.
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
keep to a two-by-two grid and a single rule drawn from a narrowed
pool, and use a coarse three-step size ladder so "bigger" is something
you see rather than judge. From there each level up adds rules, then
more components to carry them, then the logic rules, and at the top
the grid itself widens to four-by-four and the size ladder runs to
seven steps on which a rule you have *found* still takes care to
apply. Level 12 runs nine rules at once across three components on a
four-by-four grid, which is more than a person tracks — deliberately
so, so the ladder ends past everyone. (The second-order rule sits out
the four-by-four levels by its own arithmetic: its last row would
span nine rungs, and no ladder here is ten long.) With *Go up a level when right* the run follows how you do.
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

#### Hidden Rule

Matrix Reasoning asks which of eight pictures finishes a pattern; this
asks the player to find the pattern themselves, by experiment. A lamp
lights for some objects and not others, by a rule nobody states. An
object is a handful of properties — colour, shape, size, how many,
solid or hollow, underlined or not — and any object can be built and
put under the lamp. Each **test** costs a point. Two free examples
start the notebook, one lit and one dark. When you think you have the
rule, sit the **exam**: objects you have not tested come up one at a
time and each must be called lit (Y) or dark (N), with nothing said
until the last. Every wrong call costs the rung's penalty, which rises
with the rung. The round passes if tests plus penalties come in at or
under par. Afterwards the rule is printed.

Three skills nothing else in the workshop asks for together: keeping in
mind every rule the notebook still allows, choosing the test those
rules disagree about (and not the one you expect to light the lamp),
and knowing when you know enough to stop paying for tests.

| Rung | What the rule may be |
| --- | --- |
| 1–3 | Two or three properties of two values; the rule is one value ("blue"). |
| 4–5 | "Not" a value, where a property has three or more. |
| 6–7 | Two values that must both hold ("blue and round"). |
| 8–9 | Either of two ("blue or round"), found only by testing what should *not* light. |
| 10–11 | One but not both. |
| 12+ | **The lamp lies** on a share of tests, up to one in ten. One reading is no longer proof. |
| 13–15 | Three at once; any of three. Five properties. |
| 16–18 | Mixtures: at least two of three, (a and b) or c, (a or b) and c. Six properties, 384 objects. |
| 19+ | "Not" inside any rule; past rung 20 par is below the reference. |

Par is set by a Bayesian reference experimenter playing the identical
deal: the lamp lies on the same numbered tests whatever is tested, and
the exam is the same objects in the same order. It keeps every rule
the rung allows, weighted by how many readings each contradicts, tests
the object its rules are most evenly split on, and sits the exam once
what it expects to lose there is worth less than a test. It looks one
test ahead only. Measured over sixty deals a rung it pays about 2
tests at rung 4, 8 at rung 12 and 23 at rungs 16 and up, and from
rung 12 players who test at random pass at most a quarter of the time.
Par is twice the reference's cost at rung 1, the reference's cost by
rung 12, and less than it past rung 20, by more at every rung.

The agent plays through ten ports: six step one property each to its
next value (free), then Test, Exam, Lit and Dark. It is turn-based, so
it takes the think clock.

#### Hidden Wiring

A panel of switches and a row of lamps, wired through gates nobody
shows. Flipping a switch is free; **looking** at the lamps costs a
point and shows which are lit for the switches as they stand, and every
look goes into a notebook of switches and lamps. When the wiring seems
known, the exam shows lamp patterns -- lit, dark -- and asks for
switches that make each one. Nothing is said until the last answer,
and a wrong answer costs more than par ever allows, so one is always a
loss. Then the wiring is printed.

Hidden Rule asks for a rule about objects put in front of it. This asks
for a **mechanism** found by intervening on it -- which switch reaches
which lamp, through what gate -- and then used backwards, from the
effect wanted to the cause that makes it.

| Rung | What it adds |
| --- | --- |
| 1 | Two switches, one lamp that follows a switch, maybe backwards. |
| 3+ | AND and OR gates over two switches. |
| 5+ | Gates with an input inverted; more lamps every four rungs. |
| 7+ | XOR. |
| 12+ | Three-input gates: AND, OR, majority, parity. Up to eight switches and six lamps, some switches wired to nothing. |
| 16+ | On some looks a lamp **lies**, fixed by look number. |
| 21+ | Par is below the reference, by 4% more at every rung. |

Each lamp's wiring is a function of at most eight switches, so a
256-bit truth table: one Python integer. The reference keeps every
wiring each lamp could still have (where lamps lie, those that disagree
with the fewest looks), looks at the setting those wirings split on
most, and sits the exam once every question has a setting that works
under all of them. The exam only asks patterns that need a look to
answer. Eleven agent ports: flip switches one to eight, Look, Exam,
Answer. Turn-based, so it takes the think clock.

#### Jigsaw Puzzle

A photograph is cut into a grid of tiles and shuffled; click two
tiles to swap them (or walk the cursor with the arrow keys and press
Enter), and the puzzle is done when the picture is whole. The grid is
whatever size you ask for: *Pieces* runs from 2 — the picture cut in
half — up through the hundreds to 2500 on the options screen, and
`JIGSAW_PIECES` in the config file takes any whole number at all. The
only ceiling is the photograph's own pixels. The count dealt is the
nearest grid of near-square tiles holding at least what was asked, so
300 pieces of a square picture is 17 by 18. The photographs are the DIV2K set at 2K resolution — detailed
enough that a tile of sky and a tile of sea genuinely take looking at
— fetched once with:

```bash
.venv/bin/python -m neural_workshop.datasets div2k
```

Finishing is not the score. Any shuffle can be solved in a knowable
minimum number of swaps — one less than the length of each cycle of
the shuffle, summed — and the run reports how close each solution
came to that minimum. Swapping at random finishes eventually; seeing
where each tile belongs before touching it finishes at the minimum,
and the gap between the two is what is measured. With *Grow the grid*
a solve near the minimum takes the next puzzle up one grid size and a
loose one takes it down one, with no top to the ladder. The finished picture is shown beside the
board like the lid of the box; turn it off and the tiles are all
there is.

Every photograph in the library is used before any is used again, and
the rotation is remembered across sessions — a jigsaw of a picture
you have already assembled is a memory task, not a reasoning one. A
larger library therefore means longer before anything comes round
again; the default hundred images is a hundred fresh puzzles.

#### Video Jigsaw

The jigsaw with a moving picture. A short clip is cut into a grid of
tiles and shuffled, and every tile goes on playing its own part of the
picture, all of them in step, while you swap them back into place.
Everything else is the Jigsaw Puzzle's: two clicks to a swap, the
score against the knowable minimum, the grid that grows after a clean
solve, and the same range — from 2 pieces to as many as you like
(`VIDEO_JIGSAW_PIECES`), up to the clip's 320 by 240 pixels.

What moving adds is a second kind of evidence. An edge still has to
meet an edge, but things also cross the seams: an arm leaves one tile
and has to arrive in its neighbour on the same frame, and a tile of
blank wall that no still frame could place is placed by the shadow
that sweeps through it. The whole clip playing beside the board is off
by default, because with it on the puzzle is mostly matching.

The clips are the `ucf101` library and need `ffmpeg`, as Video
Sequence does, but the two keep separate rotations: a clip you have
put in order there is still new here.

#### Video Sequence

The jigsaw in time instead of space. A short clip of someone doing
something — a dive, a serve, a lift — is cut into equal stretches,
and the stretches are shown shuffled, all playing at once on a loop.
Click two to swap them; the puzzle is done when they read left to
right, top to bottom, in the order they happened. No edge of one piece
meets another, so the evidence is cause and consequence instead: the
ball is in the hand before it is in the air, the arm draws back before
it swings.

Scoring is the jigsaw's — swaps against the knowable minimum — and
with *Add a piece* a clean solve cuts the next clip one piece finer,
from three up to nine. Clips whose pieces look too alike to order are
passed over, and every clip is used before any comes round again. The
clips are the `ucf101` library above, and need `ffmpeg` to play.

#### What Happens Next

The opening of a short clip plays; then a few short stretches of video
play side by side, and one of them is what really came next. Click it.
The opening holds its last frame while the options play, so each is
seen following on from the moment the opening stopped.

| Rung | The decoys |
| --- | --- |
| 1 | A stretch of another clip. Two options. |
| 4+ | The true continuation **played backwards** -- the same frames, and only the direction of time to tell them apart. |
| 8+ | A stretch from **later** in the same clip, the end of the opening **again**, and a stretch from the **middle of the opening**. |
| 12+ | The continuation **skipping ahead** by half its length. |
| 16+ | No other clips: every option comes from the same clip. |
| 21+ | Less of the opening is shown, down to a quarter. |

Options grow from two to six, one every three rungs. A choice is right
or wrong, so there is no par: guessing is right a half of the time at
rung one and a sixth from rung thirteen. The clips are the `ucf101`
library and need `ffmpeg`, as Video Sequence does, with a rotation of
their own. Six agent ports, one per option. Clocked, because the
evidence is motion.

#### Will It Fall?

A small scene of plain rigid-body physics, a question, and a row of
answer buttons. Every answer is exact -- worked out from centres of
mass and the equations of a thrown ball -- so how close a call is can
be set to the millimetre.

| Rung | The question |
| --- | --- |
| 1 | A tower of blocks: *does it stand or fall?* |
| 4+ | A plank on a pivot with weights on it: *tips left, tips right, or stays level?* |
| 8+ | A ball rolls off a ledge: *which bin does it land in?* |
| 10+ | The plank's pivot is off its middle, so the plank's own weight counts. |
| 12+ | A taller tower: *which block is the first to topple*, or nothing? |
| 16+ | The ball bounces once, losing some speed: *where does it land the second time?* |

The margin -- how far a centre of mass sits from an edge, or a ball
from a bin wall -- shrinks from a third of a block at rung one to two
hundredths by rung twenty-one; blocks grow to seven, bins to six, and
past twenty the flight's dotted start shows fewer dots to read its
speed from. Answers are dealt evenly, so no button is a safe guess.
A trial is right or wrong. Eight agent ports, one per answer button.
Turn-based, so it takes the think clock. After the verdict the truth is
drawn in -- the block that topples outlined, the plank tilted, the
ball's whole path traced -- so a wrong answer shows why.

#### Same or Mirror?

Shepard and Metzler's mental rotation. Two figures of cubes, each cube
face to face with the next in straight arms at right angles: is the
second the same figure turned, or its mirror image? No figure is its
own mirror image, so no turn can make one into the other; only a turn
done in the head tells them apart. Press S or M, or click.

| Rung | What it adds |
| --- | --- |
| 1 | Turned about the **vertical**, by up to 40 degrees. |
| 2-6 | Still about the vertical, the most growing to a half turn by 6. |
| 7+ | About **any** axis, up to 60 degrees; a half turn from 10. |
| 13+ | A figure on top and a row below: **which is the same figure?** Three choices, the rest mirror images. |
| 16+ | Four choices, one of them the figure with one end cube moved. |
| 21+ | Five, every wrong one a cube away from the figure or its mirror. |
| 25+ | No shading: faces read only by their edges. |

Figures grow from seven cubes to eleven, all drawn at one scale. A
choice is right or wrong; for a pair, the verdict says how many degrees
apart the two views were. Five agent ports, one per answer. Turn-based, so it
takes the think clock.

#### Which Is Nearer?

A few solids in a scene: click the nearest. Depth is never given
straight -- the eye reads it from cues -- and every few rungs one cue
is taken away until a single one is left.

| Rung | The cue that is left |
| --- | --- |
| 1-6 | All of them: alike solids on a gridded floor, nearer ones bigger and lower. |
| 7-9 | Where each stands on the floor: sizes and kinds now differ, sized so size on the page says nothing. |
| 10-12 | A **shadow** on the floor under each floating solid. |
| 13-15 | Which **hides** which: no floor, the solids crowded together. |
| 16-19 | **Motion parallax**: spread out, nothing hidden, the eye sways side to side and nearer things slide farther. |
| 20+ | The same, and put **all** of them in order, nearest first. |

From two solids to six; the nearest is nearer than the next by a
factor of 1.6 at rung one, 1.1 by nineteen and 1.04 at thirty. Each
solid's button carries a swatch of its colour, since crowded solids
leave no room for numbers. Six agent ports, one per solid, counted
left to right. Clocked, because from rung 16 the evidence is motion.

#### Shape from Motion

Dots scattered over the surface of a solid that turns about the
vertical, seen straight on: every dot alike, no shading, no outline,
nothing hidden. While it turns the eye puts the dots back on a surface
-- the kinetic depth effect. Name the solid: a ball, cube, cylinder,
cone, ring, pyramid, saddle or spring.

| Rung | What it adds |
| --- | --- |
| 1 | Three very different solids to choose from, 300 dots that last. |
| 4+ | Four choices. |
| 7+ | Five, and each dot lives half a second before it jumps to a fresh spot -- none can be followed for long. |
| 10+ | A third of the trials ask **which way the front turns**. Seen straight on, a cloud and its depth reflection turning the other way give the same picture; a little perspective is the only tell, and it weakens up the ladder. |
| 12+ | Noise dots, 30 per cent, and wrong choices that look like the right one. |
| 16+ | 150 dots, half noise, quarter-second lives. |
| 20+ | Six choices, 90 dots, a slower turn; from 25, 50 dots and 60 per cent noise. |

At the low rungs a still frame can give some solids away by their
outline -- a spring especially; past rung 12 the noise and short lives
leave the motion as what decides. A trial is right or wrong. Six agent
ports, one per answer. Clocked: the evidence is motion.

#### Point of View

A map of a table from straight above -- each solid's footprint, and a
camera with the wedge it looks along -- and a row of pictures of the
table from different places. Which one does the camera take?

| Rung | What it adds |
| --- | --- |
| 1 | Two or three solids, the camera at the middle of a side; the wrong pictures are from the other sides. |
| 4+ | Up to four solids, four pictures. |
| 7+ | One wrong picture is the right one **mirrored**, left for right. |
| 10+ | Solids of different heights, so near ones hide far ones. |
| 13+ | The camera anywhere round the table; wrong pictures from 45 to 90 degrees round from it. |
| 16+ | Every solid one colour, told apart by shape and height; five pictures. |
| 20+ | The camera higher or lower; wrong pictures as little as 25 degrees round; up to six solids. |

Every wrong picture shows the solids in a different left-to-right
order from the right one, so the order alone can always decide. A
choice is right or wrong. Five agent ports, one per picture. Turn-
based, so it takes the think clock.

#### Winning Move

One legal chess position is dealt and the side to move has exactly one
checkmate in one. Click a piece and then its destination; legal destinations
are highlighted, illegal moves leave the puzzle open, and a legal move that
does not mate spends the attempt.

Positions are generated during play rather than selected from an answer
list. A small mating motif is reflected, rotated or colour-swapped, then
decoy material is added one piece at a time. After every change
`python-chess` enumerates the legal moves and the candidate is kept only when
exactly one of them ends in checkmate. Level one stays sparse; level ten adds
up to fourteen independently checked decoys and prefers positions with more
legal alternatives. The same seeded random source used by the agent boundary
drives generation, so a seed still reproduces the exact puzzle.

#### Sudoku

Twelve rungs, from a four by four that falls to naked singles up to a
sixteen by sixteen with a hundred and fifty-six blanks that still
needs hundreds of guesses once deduction is spent. Arrows move, digits
write, **N** pencils a candidate in, **O** opens the options — sixteens
run on 1-9 and then A-G, which costs **C** its usual job on the boards
that go that high.

Counting blanks is the obvious way to grade a sudoku and it is very
nearly worthless: measured over four hundred minimal nine-by-nines,
puzzles with the same number of givens ran from "naked singles all the
way" to "the whole technique stack runs out". So difficulty here is
what a puzzle actually *forces*. A rating solver runs a stack
cheapest-first — naked single, hidden single, locked candidates, naked
subset, hidden subset, fish — always applying the cheapest technique
that changes anything and going back to the top of the stack after
each, and reports the deepest it had to reach. Past that the puzzle is
graded by how many branch points a propagating search still has to
guess at.

The measured tier spread killed the obvious ladder design. Across
those four hundred puzzles the tiers came out 0.8, 43, 10, 8.8, 0.8,
0.2 and 36 per cent — so "at least tier two" is satisfied four times in
ten by a puzzle the logic cannot finish at all, and a rung asking for
*moderate* kept dealing *diabolical*. Rungs are bands instead, and the
gentle end is reached by digging less rather than by hoping for it,
since a puzzle dug to minimal is nearly always a hard one.

Two generator bugs the measurements caught, both invisible from the
outside. Filling a sixteen by blind backtracking took 216 seconds on
one seed in a handful where its neighbours took four thousandths of
one; propagating between placements and restarting past a node budget
put the worst of sixty seeds at 0.017s. And digging asked "does this
have exactly one solution", which means exhausting a tree to prove a
second does not exist — asking instead whether any particular digit
fits the blanked cell prunes on the pinned cell.

Where a band is missed — only *hard*, which asks for the 1.0% of
puzzles at tiers four to five — the fallback overshoots by
construction, so a rung's name stays a floor on the work: 25 deals
landed 16, 6 and 3 across tiers four, five and six, and none below.
The screen always reports the tier it actually got, never the one it
wanted.

#### Crossed Wires

Every other task in the workshop hands the player all the information
it is ever going to give and then asks what follows. This one does
not. A marker on a grid that wraps at every edge, a target to reach,
and four or eight keys whose directions have been quietly scrambled —
and nothing on screen ever says how. There is no legend, no readout of
what has been worked out, and no mark on the key just pressed. The
information does not exist until you go and make some.

Which is why it survives the agent environment's virtual clock, where
most control tasks do not. An agent gets unbounded thinking time
between presses, so anything whose difficulty is reaction speed is
free; here thinking buys nothing at all, because the answer is only
available to somebody willing to spend a move finding it out. Presses
are budgeted — the shortest trip plus a few spare — so probing every
key before committing costs more than the round can afford, and
committing without probing walks the wrong way. Neither pure exploring
nor pure exploiting clears a rung.

Four players measure what the rungs mean, and each number is measured
rather than claimed. Pressing at random reaches 1–4% of targets, which
is a real floor rather than a zero because a random walk on a torus
does stumble onto things. A greedy player who already knows the wiring
clears every rung — it misses about two targets in ten thousand on
the top two, and that is its greed and not the budget. A learner that
presses an unknown key when nothing known helps, and trusts what it
saw last, runs from 1.000 down to 0.23 across the twelve rungs, and
the space between it and the oracle is what a rung actually asks for.

The fourth is the foil. The senior rungs turn the whole wiring
silently every few presses, and let one key stop working partway
through, also silently — so a player that identifies the wiring once
and then trusts it forever is exactly wrong, and there is no notice
that it has become so. Frozen against fresh: 0.72 against 0.44, then
0.56 against 0.24, 0.36 against 0.10, 0.23 against 0.05. On the rungs
where nothing moves the two agree exactly, which is the check that the
separation is measuring drift rather than the relearning machinery.

The grid wraps deliberately. On a bounded arena a press into the wall
looks exactly like a press on a dead key, and an ambiguity between
"this key does nothing" and "this key does something I cannot do from
here" is a muddle rather than a difficulty. On a torus every press
moves, so every press is evidence. What is left of the budget is drawn
as a bar as well as a number, because an agent reads this screen as
pixels and a quantity it can only get by parsing a glyph is one it
effectively cannot see.

#### Crossword

Grids generated to order, filled from a word list fetched
rather than shipped, and clued from definitions the same fetch brings
down. Arrows move, letters write, **Tab** turns the cursor between
across and down. One clue is shown at a time — the clue for the entry
the cursor is facing — because a screen this size cannot hold a list
down the side and a clue you cannot read is not a clue.

The mouse does what the mouse does in every crossword: click a cell to
go to it, and click the cell you are already on to turn between across
and down. That second one is the convention every crossword on a
screen has used for thirty years, and a task that invented its own
would be teaching its own controls rather than testing anything.
Right-click turns from anywhere. The letters stay on the keyboard,
because they are letters.

Every grid is **fully checked**: each cell belongs to an across entry
and a down entry, both at least three letters, so every letter can be
reached two ways. That is the American convention and it is not a
matter of taste. A half-checked grid has cells only one clue reaches,
and a solver who does not know that clue has nothing to work with, so
the puzzle stops being solvable by reasoning and becomes a vocabulary
quiz with gaps in it.

The ladder moves two things. The first is how long an entry may be:
a grid capped at four has a crossing every few letters, and a grid
with no blocks at all is a word square, where every row and every
column is a word of the full width. Not every cap is reachable, and
that is geometry rather than search — a five by five cannot be brought
below five, because giving every row a shorter entry needs a block in
every row and so does every column, and there is no way to do both
without leaving a run of one or two. So a five by five is always a
word square, and the ladder uses it as one.

The second is the **rank band** the entries are drawn from. Words come
with their frequency in Google's 1-grams, so a rung says how obscure
its answers may be as well as how the grid is shaped. `usury` is rank
22,445 and `sourish` is rank 120,000-odd, and no amount of crossing
makes the second fair on a person.

Those two do not compose the way one would expect. A nine by nine
drawn from the 30,000 commonest words takes 2.3 seconds to deal and
one from the whole list takes 0.8 — the narrow band is the *harder*
grid to build, because there are fewer words to cross with, which is
exactly why it is the lower rung. A rung is not harder to solve
because it was harder to deal.

Two smaller dials finish it. Letters can be given away at the start,
which is the whole of the gentle end; and clues can be **withheld**,
which is the whole of the far end. An entry with no clue has to come
from its crossings alone, and the top rung is a five by five word
square from the whole list with two clues in five simply not given —
a constraint problem with a vocabulary prior, which is the point at
which "hard" stops meaning "knows more words".

Green means solved without ever writing a letter that was not the
answer's. Finishing is not the measure: a grid only settles once it is
full and right, so every solved grid finished. What separates them is
having deduced rather than run the alphabet.

#### Scrabble

One rack, one board, one play. There is no opponent and no
bag to draw from: a trial hands over a position and scores what you
lay against **the best play that existed**, worked out exactly. The
Traveling Salesman screen is scored the same way and for the same
reason — a rung cannot be passed by being told what good is.

The mouse plays the whole turn: click a square to go to it, click it
again to turn, click a tile in the rack to lay it, click a tile you
laid to take it back, and click **Play**. Arrows, `1`-`7`, `Tab`,
Backspace and Enter do the same things, which is the rule — the
pointer is a second way to reach the same actions and never a way to
reach a different set. The one exception is lifting a *particular*
tile rather than the last one, and it is not really an exception:
lifting the last one repeatedly and re-laying the keepers reaches the
same board, so it is a convenience for the hand and not a capability
the keyboard or the agent's ports lack.

The scoring is the real one, because a made-up one would be a
different puzzle: standard letter values and distribution, double and
triple letter and word squares, every word a play forms scored, word
premiums multiplying the crossing word as well as the main one, and
fifty for laying all seven. The premium squares are generated by the
same eightfold symmetry the real board has rather than copied, because
the boards here run from seven to fifteen and a fifteen is mostly
empty space when one word is on it. No blank tiles are dealt — a blank
multiplies the search by twenty-six and adds nothing a rung cannot get
by drawing from a wider band.

What makes a position hard is not the rack; seven tiles is seven tiles
at every rung. Three things move. How obscure the best play may be —
from the three thousand commonest words, where the best play is
something you know and the work is placing it, up to the whole list,
where it often is not. How much board there is to hook onto. And how
close to the best you have to come, which runs from half of it to the
whole of it.

That first one is measured rather than asserted, and the measurement
is what the ladder is built on. Take a player who knows only the three
thousand commonest words and who — unlike any person — always finds
the best play among them. Over twenty-five positions a rung, that
player scores this share of the optimum:

```
1.00  1.00  1.00  0.77  0.77  0.54  0.61  0.41  0.39  0.42
```

Perfect at the bottom, because down there the optimum *is* an everyday
word. Two fifths at the top, because up there it is not. Each rung's
passing share sits a little above what that player would get, so a
rung is passed by knowing more words or by placing them better and not
by either alone.

An illegal play is refused rather than scored. Tiles that spell
nothing, or that float free of the board, come back with a reason and
stay where they are; only a legal play settles the trial. A screen
that scored nonsense as zero would be paying for the difference
between a bad play and a misunderstanding of the rules.

The exhaustive solver is checked against a brute force in
`tests/test_scrabble.py` — every ordered subset of the rack into every
run of squares, scored the long way — because the whole task rests on
that one number, and a solver that quietly missed a play would flatter
every player by an unknown amount and never say so.

#### The word list behind both

Neither game ships its words. Two files come from Hugging Face on
request:

```bash
python -m neural_workshop.wordlist
```

`Maximax67/English-Valid-Words` (Unlicense, 5 MB) carries about
173,000 words with their count in Google's 1-grams, which is what a
rank means above. `MongoDB/english-words-definitions` (Apache 2.0,
95 MB) carries a definition or two for 467,000 words, written by
Claude 3.7 Sonnet rather than by a lexicographer — so a definition
here can be wrong, and the crossword's options screen says so.

**Every one of those definitions gives the answer away.** Not most:
measured over the 172,767 that overlap the frequency list, 172,684
name the word in their first sentence and the rest name a form of it.
They are glosses — "A zebra is a large African equine mammal" — and
printed as clues the crossword would be a copying exercise. So the
gloss's opening is cut, and a definition whose body still shares the
answer's stem is thrown away rather than blanked, because a clue with
a hole in it says how long the answer is a second time. What survives
reads the way a clue reads:

```
zebra      large African equine mammal with black and white stripes
quixotic   exceedingly idealistic, unrealistic, and impractical
usury      practice of lending money at unreasonably high rates
```

144,000 of the 173,000 come through, distilled once into a
tab-separated index that loads in under a tenth of a second. What is
thrown away is mostly words whose definition is a sentence about the
word rather than a meaning, which would have made poor clues anyway.
What still leaks is proper nouns whose clue reads as an ordinary
definition — "ancient Egyptian god of the dead" — at roughly one clue
in twelve above rank 30,000 and rarer below it. A crossword with the
occasional proper noun in it is a normal crossword, so that is
reported rather than chased.

**A third caller wants something neither file says.** Syllogisms
names the things it reasons about after words, and for "every X is a
Y" to be a premise rather than a typo the word has to be a singular
common noun. There is no part-of-speech tag anywhere in either file —
but there is a definition, and a definition gives the part of speech
away by its shape: a verb is glossed "to run", an adjective "having
the quality of", and a good half of the rest simply say which they
are. Reading that, plus refusing any clue with a capital letter in it
(the cheapest screen there is for the proper nouns that leak above),
any word that is an inflection of another, and any clue that marks
its word as coarse — which is a screen on the register rather than a
list of words, and three entries in the band answer to it.

**The strongest single test is the one that does not read the
definition at all: does the word have a plural?** `camels` is in the
frequency list and `coastals` is not; `bacteria` and `formulae` are
already plural and have nothing past them; `obesity` and `patience`
are mass nouns, which are things one cannot have two of and so cannot
be "every X is a Y" either. It costs one set lookup and it is what
takes the residue from one name in eight to one in fifteen. 3,461
words come through. Three or four in sixty are still not nouns — an
adjective that also has a plural, a spelling nobody writes — which is
reported rather than chased, because a name here is a label and an
adjective in the place of a noun reads oddly and means nothing else.

With nothing fetched there is still a 669-word seed list of common
short words in the repository, which is enough for Scrabble to be
played and for the tests to run, and is *not* enough for a crossword,
because it carries no clues, nor for Syllogisms, because they are
function words. The crossword says so on its own screen rather than
dealing something thin and pretending, and Syllogisms falls back to
made-up words.

Both ladders are rerunnable:

```bash
cd tests && PYTHONPATH=.. ../.venv/bin/python bench_words.py
```

#### Scramble

A sentence is corrupted and you type it back.

```
the balck hrose wlaked alnog the raod to the twon
```

That is level one, and the trick is the famous one: swap two letters
inside a word and people read straight through it. Level twelve is
the same sentence with every letter of every word free to move, one
letter of each thrown away, a stranger thrown in, one replaced by its
neighbour on the keyboard, the spaces taken out and the words
shuffled about.

Eight dials do it, and they do not all take the same thing away —
letters transposed, the middle of a word permuted, the whole word
permuted, letters dropped, letters inserted, letters substituted,
word boundaries moved or removed, words reordered inside a window.
Nothing partial is marked: a reading that is one letter out is a
different sentence.

**A rung is defined by how much of the answer is left on the page,
and that is counted rather than claimed.** For each corrupted word,
the candidate set is every word in the vocabulary whose letters are
within reach of the ones on show; the product of those set sizes is
how many readings survive the letters alone. Against it runs a reader
that knows no English at all — it answers each token with the
commonest word that fits, and where the gaps have moved it picks the
segmentation that makes the commonest words it can. What that reader
gets back is what the page still says outright. Everything above it
is what a reader has to bring.

| rung | | ambiguity | read back |
|---|---|---|---|
| 1 | two letters out | 0.3 | 0.98 |
| 4 | the ends move too | 1.0 | 0.98 |
| 5 | the gaps move | 1.3 | 0.82 |
| 7 | letters thrown in | 12.8 | 0.65 |
| 9 | wrong letters | 22.5 | 0.23 |
| 12 | everything at once | 27.3 | 0.04 |

Ambiguity is a base-ten log, so rung 9 leaves 10^22 readings standing.
Three things in that table were worth the measuring.

**The famous trick removes almost nothing.** Rungs one to four are
typoglycemia, and a reader that has never heard of English still
gets 98 words in a hundred back off the letters. An anagram of an
English word is nearly always an anagram of only that word, so
`hrose` determines `horse` outright. The effect people find
remarkable is about reading speed, not about information. Nothing is
actually taken away until rung five.

**Ambiguity and difficulty are not the same axis.** Rung 9 has the
worst ambiguity on the ladder and rungs 8, 10 and 11 read back within
a few points of it on a hundredth of that. Missing letters leave a huge candidate
set that context collapses easily; moving the gaps leaves a small one
that context cannot help with, because you cannot use a word's
neighbours before you know where the word ends. The two columns
disagree, and both are printed.

**Rungs 8 to 11 are one shelf to that reader** — 0.27, 0.23, 0.25,
0.23, which is noise. They are ordered by what is taken away, because
what separates them is the spaces and the word order and the reader is
blind to both by construction. The bench prints this rather than
leaving it to be noticed.

Unlike the crossword, this task cannot promise its sentence has one
reading. What rules out the wrong ones is knowing English, and nothing
here knows English. A generated sentence could carry that guarantee
and the first version of this did — it was thrown away, because what
a person brings to `the hrose is balck` is everything they know about
horses, and a sentence built from a template tests how fast they learn
the template.

#### The text behind Scramble

```bash
python -m neural_workshop.sentences
```

`juno-labs/simple_wikipedia` (CC BY-SA 3.0) is a weekly snapshot of
Simple English Wikipedia, 276,302 articles written under a house style
of short sentences and a limited vocabulary. **It reads 46 MB of a
439 MB file.** The dataset is one parquet file of nine row groups; one
row group is 34,087 articles, four times more than this needs, so the
fetch opens the file over HTTP range requests, reads the footer and
pulls one column of one row group. Four seconds.

The first version walked Hugging Face's rows endpoint instead — a
hundred articles a request, no dependency beyond `urllib` — and got a
sixth of what it needed in twelve minutes before the server began
answering 429 to everything. A bulk read of a static file is what a
CDN is for. Reading parquet needs `pyarrow`, which is not a
requirement of the Workshop and is imported inside the fetch and
nowhere else; the distilled bank is a plain text file and playing
never reads parquet.

A sentence is kept only if it is six to fourteen words, every word is
alphabetic and in the frequency list, and every word after the first
is lowercase in the original. That last filter throws away every
sentence containing a proper noun: a scrambled `eostn` is solvable and
a scrambled `ntsoe` that turns out to have been *Notestein* is not.
402,602 sentences seen, 36,118 kept — and the thinnest rung of the
ladder still has 3,900 to draw on. With nothing fetched there are
seventy sentences in the repository, enough to play and not enough to
stop repeating, and the screen says which it has.

Two tasks read this bank. Overrun takes the short end of it — 24 to 44
characters, so a whole sentence fits a lane with its own length of road
ahead of it — and cuts the vocabulary tighter than Scramble does, at
the 20,000 commonest words rather than 60,000: a word you have to work
out is a word you cannot type at speed, and speed is all that task is.

```bash
cd tests && PYTHONPATH=.. ../.venv/bin/python bench_scramble.py
```

#### Verbal Reasoning

Verbal Reasoning draws English multiple-choice questions from the verified
artifact built by the sibling `VerbalIQDataset` project. The corpus is not
copied into the Workshop. It is opened only when the first run begins, and a
trial reads one Parquet row group and only the seven columns needed to play;
imports, the task hub, and opening the task itself do no dataset I/O.

Install the optional reader in the Python environment that runs the Workshop:

```bash
python -m pip install pyarrow
```

By default the task looks for
`/Users/torarinvikbjarko/Documents/Coding Projects/Python Projects/VerbalIQDataset`
and prefers `build/verbal-iq-release`. To use another checkout or a directory
containing Parquet files:

```bash
export NW_VERBAL_IQ_DATASET=/path/to/VerbalIQDataset
```

Only displayable English questions with two to five indexed choices are
offered. Choices are shuffled on every deal while the gold answer follows its
text, so a source's answer-position distribution is not a shortcut.

#### Signals

A partner across the table, a row of objects -- each a colour and a
shape -- and a code nobody explains. When the partner speaks it thinks
of one object and sends one or two glyphs from an alphabet of eight
abstract marks; pick the object it meant. When you speak an object is
outlined; send glyphs (keys Q to I, or click them) and the partner
picks. The answer is shown afterwards either way. Which glyph means
which colour or shape is the partner's own convention and has to be
worked out from what happens, and then used. Each game is a new partner
with a new code.

| Rung | What it adds |
| --- | --- |
| 1 | Only listening; glyphs name colours, every object a different colour. |
| 4+ | Only speaking: find which glyph makes the partner pick the colour wanted. |
| 8+ | Listening and speaking by turns, and glyphs for shapes as well as colours. |
| 12+ | Two glyphs a signal, and objects that only colour and shape *together* tell apart. |
| 16+ | The partner **changes** its code partway through, without a word: two glyphs swap meanings, three from 20. |
| 21+ | Fewer exchanges to learn in than sixteen, and more objects. |

A game passes at par: what a reference learner scores on the identical
game -- a Bayesian count of which glyph went with which colour or
shape, forgetting slowly where codes can change -- with ground given
below rung twenty and, past it, par set halfway between that learner
and a perfect game. Sixteen agent ports: eight to pick an object, eight
to send a glyph. Turn-based, so it takes the think clock.

#### Fold It

A flat net of six squares, printed side up, its squares folding away
from the eye. Any of the eleven nets of a cube can be dealt.

| Rung | The question |
| --- | --- |
| 1 | Lettered squares on the cross: *which face is opposite C?* |
| 2-3 | The same, on any net. |
| 4+ | Coloured squares and a row of cubes, three faces of each in view: *which cube does it fold into?* The wrong cubes have two faces swapped. Four cubes from 7. |
| 10+ | Marks that point a way; a wrong cube may have one mark turned. |
| 13+ | Every square one colour: the marks alone. |
| 16+ | Five cubes, every wrong one a single turned mark or the mirror image of the right cube. |
| 20+ | Marks with a handedness, so a mirrored mark is a different mark; six cubes from 25. |

Which square lands where, and which way up its mark ends, is worked
out by carrying each square's frame across every fold; the tests check
that against turning each square a quarter turn on its hinge in 3D.
Every wrong cube is checked against all 24 ways the right cube could
sit, so none can be the right cube seen another way. A choice is right
or wrong. Six agent ports, one per answer. Turn-based, so it takes the
think clock.

#### Who Knows What?

A short story told in panels -- each the room just after one event,
with what is really in each container, who is in the room and who is
out, and the event in words -- and a question: where will someone look
for something? From rung 9, where does someone think *someone else*
will look? The reader sees everything; nobody in the story does.

Beliefs follow simple rules. Whoever is in the room when a thing is
moved learns where it went; whoever is out keeps believing what they
last knew; coming back in shows nothing, since the containers are
closed. A phone call passes on what the caller believes -- or, in a
lie, what the caller knows is false -- and the one called believes it.
Peeking into the container that holds a thing shows where it is, and
peeking where one thought it was and finding it gone leaves one not
knowing. What A thinks B believes changes only on what A could know.

| Rung | What it adds |
| --- | --- |
| 1 | The classic false belief: Ann puts the ball away and goes out, Ben moves it. Two people, two containers. |
| 3+ | Three containers, random stories of four to six events. |
| 6+ | Three people and two things, stories of six to eight. |
| 9+ | **Second-order** questions, half the time. |
| 13+ | Phone calls. |
| 17+ | Lies; four people, four containers. |
| 21+ | Peeks, three things, stories of ten to thirteen events. |

From rung 3 seven questions in ten have an answer that is *not* where
the thing really is, so the truth is a poor guess. Answers come from
the belief tracker, never from the wording, and the tests check the
tracker on hand-written stories. A trial is right or wrong. Four agent
ports, one per container. Turn-based, so it takes the think clock.

#### Algebra

```
3 + 4
n = 19394 (mod 87679),  n = 62006 (mod 71503),  n = 5611 (mod 76369), ...
```

Both of those are this task, at level one and level twelve. The second
is one integer in a box of 10^28, and nothing will ever find it by
looking.

**What grows is not the size of the numbers.** That was the first
ladder written here and it was thrown away: `48239 × 91827` is
unbounded and it is clerical, and at the top of it sits a calculator
rather than a mathematician. The printed numbers never exceed five
digits at any level. What grows is how much has to be true at once.

Levels one to six are arithmetic — adding, order of operations, signs,
exact fractions, then a letter to find. From seven two families
alternate, because they are hard in different ways: the symbolic ones
multiply out and gather up, ending in a cube in two letters; the
modular ones solve a congruence, then three at once, then six, where
the remainder theorem guarantees exactly one answer below the product
of the moduli.

**A level means how big the naive search is, and it is counted.** Every
level guarantees its answer lies in some space — an interval of
integers, or polynomials with bounded degree and coefficients. Against
that runs a solver that knows no mathematics at all: it can only
*check* an answer, so it walks the space until something fits.

| rung | | kind | candidates | cracked | steps |
|---|---|---|---|---|---|
| 1 | one and one | number | 1.6 | 1.00 | 1 |
| 5 | exact halves | number | 5.1 | 1.00 | 2 |
| 6 | find the letter | number | 1.3 | 1.00 | 3 |
| 9 | collect the powers | expression | 5.4 | 1.00 | 3 |
| 10 | three clocks at once | number | 5.1 | 0.67 | 3 |
| 11 | two letters, cubed | expression | 24.6 | 0.00 | 4 |
| 12 | six clocks at once | number | 27.9 | 0.00 | 6 |

**Searching is not reasoning, and the two columns say so.** Level 5
hides its answer among 10^5.1 values and takes two steps to get; level
6 hides its among nineteen and takes three. The easier-looking level
has a search six thousand times bigger. Ordering by candidates would
put adding two fractions above solving an equation, which is wrong
about people; ordering by steps would put it below adding two whole
numbers, which is wrong about machines. The levels are ordered by what
a person has to know, both columns are printed, and the bench prints
the disagreement in words rather than leaving it to be noticed.

**The superhuman end is a cliff, not a slope.** Everything to level 9
falls to patience alone. Level 10 is at the edge, at two thirds. Then
the space goes from 10^5 to 10^25 in one level and searching stops
being a strategy — which is why the top moduli are five-digit primes
and not the two-digit ones three levels below. Six two-digit primes
put the answer in a box of 10^9, a long afternoon for a laptop; six
five-digit primes put it in 10^28.

**Everything is exact and marked exactly.** Every coefficient is a
`Fraction`, so `64/35` and `128/70` are one answer and `1.828` is not
an answer at all. There is no sympy in this environment — polynomials,
a parser, a canonical form, modular inverses and the remainder theorem
are all hand-rolled on `fractions` and `math`, which is more work and
keeps every step auditable.

Two hazards worth writing down, because both were live before they
were caught. `-x^2` parsed as `(-x)^2` agrees with the truth at x = 0
and nowhere else, so it would fail players who were right and read as
a fault in the generator. And **a question and its own answer are the
same polynomial**, so marking by canonical form alone accepts the
question copied back — the crossword had this exact defect with its
clues. A symbolic answer must therefore also be *gathered up*: no
brackets, and no more written terms than the collected form has.

```bash
cd tests && PYTHONPATH=.. ../.venv/bin/python bench_algebra.py
```

#### Syllogisms

```
volatile is less than purple   numeric is less than pain
envoy is more than purple      envoy is more than hug
hug is less than volatile
Is purple more than hug, or less?     more / less / cannot be told
```

Lines about a handful of named things, and one question about two of
them. Twelve levels, from a chain of *same* and *opposite* to three
claims joined by connectives over thirteen lines of premises. The
shape — a mixed relational drill that climbs — is the one
[Syllogimous v3](https://4skinskywalker.github.io/Syllogimous-v3/)
popularised; none of its code or wording is here and none could be, as
that is CC BY-NC and this is GPL. What is here are the paradigms
themselves, which belong to nobody: transitive inference, parity over
a same/opposite chain, vector composition on a grid, categorical
syllogisms, and three-valued composition over the lot.

**The things are named after ordinary nouns**, drawn from the same
word list the crossword and the Scrabble rack use — which asks
something that list never says outright, whether a word is a singular
common noun, and it is read off the definition: a verb is glossed "to
run" and an adjective "having the quality of", so the shape of the
gloss gives the part of speech away even when the words do not. Run
`python -m neural_workshop.wordlist` once to fetch it; until then the
things are named with made-up words instead, and the options screen
says which you are getting. Made-up names are also a setting, because
they are not a worse task — they are the same one with the belief
taken out, and the paragraph below is what that belief costs.

**A real word carries a belief, and that is priced rather than waved
away.** The place it could be spent is the two categorical levels,
where two nouns picked at random are strangers in the world as well
as in the premises, so "no X is a Y" is usually true outside the page
too. A player who answers that way every time gets 0.13 and 0.17
against a guessing floor of 0.20 — believing the premises is a way of
doing worse than a coin, not a way round the level, because the deal
picks its answer before it picks the premises that give it.

Elsewhere the words cost nothing, and that is checked rather than
measured. **The names are drawn from a random stream of their own**,
started with a single number taken from the deal's, so the same seed
builds the same premises with the same answer whichever way the
things are named — two columns of numbers could only ever have said
the difference was smaller than the sample. The bench deals every
level both ways and finds all 400 pairs identical. The one channel
left is the read-back below, which throws a deal away when the
printed lines do not parse, and no deal is thrown away either way.

**"Cannot be told" is an answer as often as any other.** Premises that
settle everything are premises nobody has to reason about, so the web
of premises falls into two pieces about a third of the time and the
question is sometimes across the gap. That has a cost the design pays
for: **the number of printed lines cannot depend on how many pieces
there are**, or counting the lines would answer the question. So a
second piece is paid for with an extra premise inside the first one.
The two direction levels are the exception — they never leave a
question open, so they do not offer that answer at all, because an
answer that is never right is a free elimination.

**Counting what is left standing measures nothing here.** Ten of the
twelve levels offer three answers, so the *candidates* column that
carries Algebra is log-ten of three on nearly all of them however long
the derivation gets. This task is measured by three baselines that
know nothing instead, and any of them beating chance is a way round
the level:

| rung | | ans | lines | guess | const | surface | steps |
|---|---|---|---|---|---|---|---|
| 1 | same or opposite | 3 | 5 | 0.33 | 0.35 | 0.33 | 3.8 |
| 4 | not more than | 3 | 7 | 0.33 | 0.34 | 0.33 | 3.8 |
| 5 | all and at least one | 5 | 2 | 0.20 | 0.50 | 0.50 | 2.0 |
| 7 | nine lines, and two that matter | 3 | 9 | 0.33 | 0.34 | 0.35 | 4.4 |
| 8 | three at once | 5 | 3 | 0.20 | 0.31 | 0.40 | 2.5 |
| 9 | up and down as well | 27 | 5 | 0.04 | 0.05 | 0.03 | 3.1 |
| 11 | two questions, one answer | 3 | 9 | 0.33 | 0.34 | 0.35 | 6.6 |
| 12 | three questions, one answer | 3 | 13 | 0.33 | 0.35 | 0.33 | 10.3 |

Every column is a proportion over 2,000 deals, good to about ±0.011.
**That width is the point of stating it.** An earlier run of this
bench used 150 deals a rung, where a column moves ±0.04 on its own —
the size of the effects it is printed to catch — and two rungs got
published as sitting at chance that do not.

*guess* is one over the answers. *const* is the best fixed answer —
the column that says whether *cannot be told* is really an answer or a
decoration. *surface* is a reader that never puts two premises
together: it finds the one line naming the thing asked about and
answers with that line's relation.

**Left alone, that reader is not a straw man.** Before the deals were
balanced against it, it answered level two six times in ten: in a
chain, what a thing is to its neighbour is usually what it is to
everything past it. Deals are now chosen so it lands at chance on the
chain and direction levels — and no worse than chance either, because
a reader that is always wrong is a way round the level backwards. It
sits a few points over on the three levels named below, and each of
those has a reason that is not a leak.

**On a two-premise syllogism the surface reader is not even wrong.**
The classical rules — a valid conclusion is negative exactly when a
premise is, particular exactly when a premise is — are the atmosphere
effect written down, and they are necessary conditions for validity.
Measured: on level five, whenever anything follows at all, atmosphere
names the right form **1,000 times out of 1,000**. The four forms are one
answer between them there and the only question left is whether
anything follows, so that level is dealt as the coin it is and both
baselines sit at one half. Level eight blunts it by asking about a
pair with a premise off the path between them, where atmosphere counts
a quality that does not apply: it falls to 0.58 of the deals where
something follows, which is 0.40 of all of them. That measurement is the reason there are two
categorical levels on this ladder rather than six.

**Two conventions are printed on the screen, because they are
choices.** Nothing is equal to anything else in an order, so *not more
than* means *less than* and nothing else — which is why negation is
offered in the two families where it has exactly one reading and not
in the direction families, where *not north of* says seven other
things. And a direction names which sides a thing is on rather than an
angle: *north and east* means north of it and east of it, one square
at a time.

The top two levels are three-valued. An *and* with one false half is
false however the other half reads; an *exactly one of* with an
unsettled half is never settled. That asymmetry is most of what those
levels are about — and it showed up in the measurement first: reading
one line per claim and then combining correctly scored .57 there,
better than the same reader manages on either half alone, because the
connectives absorb misreadings. The connectives are now chosen along
with the claims rather than before them, and it sits at 0.35 against
a floor of 0.33 — measured again over four thousand deals of its own,
0.366 ± 0.008, so the three points are real. What is left is what a
two-valued join gives away for free.

**Every question is read back off its own page** by a parser that
never saw how it was built, and a question that does not read back is
dealt again rather than handed over. That is what catches the failure
this task can have quietly: the generator still knows the answer, but
a negation rendered the wrong way round or a direction put in a frame
that means something else has stopped the page from saying it.

```bash
cd tests && PYTHONPATH=.. ../.venv/bin/python bench_syllogism.py
```

### Planning

Every task in the *Planning* category is scored the same honest way:
against a knowable optimum, because merely finishing any of them
measures patience rather than planning.

**Tower of Hanoi.** Three pegs, a tower of disks, two rules: one disk
at a time, never a disk on a smaller one. Click a peg (or press
**1**–**3**) to lift its top disk, click another to set it down. A
tower of n disks moves in exactly 2^n - 1 moves and no fewer, and
each solve is reported against that minimum — moving the small disk
back and forth finishes eventually; knowing *why* it must go where it
goes finishes at the minimum. With the adaptive option a solve near
the minimum makes the next tower taller, from three disks (7 moves)
up to twelve (4095).

**Traveling Salesman.** Cities scatter across the screen; click them
into the shortest round trip you can see, and the tour closes itself
on the last click. Nothing is hidden — the reasoning is planning under
combinatorics, following the hull and keeping crossings out. The
shortest possible tour is computed exactly (Held-Karp dynamic
programming — instant at twelve cities, a deliberate pause of a
second or two at the eighteen-city ceiling), so the
score says precisely how much longer your route was, and the shortest
route is drawn after each answer. People land within a few per cent
of optimal on sight, which is what makes the gap worth reporting.

**Sokoban.** Push every box onto a goal square — one box at a time,
never a pull, and a box against the wrong wall is stuck there
forever, which is the whole game: seeing the irreversible move
before making it. **U** undoes and **R** restarts, freely; the score
is the push count of the line you finally commit, against the
certified difficulty of the level.

Every level is generated backwards from its own solved position —
the generator *pulls* boxes off their goals through a biased random
walk, and pulling cannot create a deadlock, so every level is
solvable by construction rather than by testing. The rooms
themselves are carved by a drunkard's walk out of solid rock, with
a straight-line bias that produces corridors and cramped chambers
rather than open halls: open space is what makes Sokoban easy —
room to swing any box around any other — and the first version of
this generator, an airy room with scattered pillars, was walked
through at its "ruthless" setting without breaking stride. The
floor share tightens as the ladder climbs.

Difficulty is certified, not asserted, by two instruments. An exact
solver (breadth-first over box positions and the player's reachable
region, run in C via the `bwcore` extension, with a pure-Python
twin defining the contract) certifies the minimum push count on the
lower rungs. Past its reach, two proofs still stand: breadth-first
search visits states in push order, so a budget exhausted at depth
k certifies no solution under k pushes; and each box must travel at
least its relaxed push-distance to whichever goal it is assigned,
so the cheapest perfect assignment of boxes to goals — exact, via
the classic bitmask DP — bounds the whole solution from below at
any board size. The sixteen rungs run from "first steps" (one box,
a bare room) through "packed tight" (eight boxes, 11x11) up to
"superhuman" (thirteen boxes in a 16x16 warren, certified to need
at least 60 pushes and typically 60–106, before a single mistake),
and every rung rejects rooms below its measured floor. The upper
rungs are generated by an optimizer rather than a lottery: rooms
are dealt by the thousand and priced by one flood fill (the sum of
the deepest pull-distances a room can offer bounds anything a walk
could do in it), the promising few get two competing walks — a
random climber that keeps the best position it ever stood on, and a
convoy that drags each box outward in turn — and the deeper
certificate wins. Where the minimum is
unknown the par line says "between X and Y pushes" and a solve is
judged against the proven lower bound — never against the walk's
own length, and never pretending a bound is a minimum. Goals are
grown as one connected clump because that is what makes Sokoban
Sokoban: boxes must arrive in an order that does not wall the rest
out.

Push count is only one axis. Each rung also enforces a *trap
share*: the fraction of the floor from which a box can never reach
a goal, so a single wrong push there loses it forever. The
generator digs one-cell pockets off the corridors — a pocket has a
single entrance, so a box pushed in can never come out — until the
required share of the floor is deadly, and it digs them *after*
building the puzzle, since adding floor can only widen the
solution's options, never break it. The kindergarten rungs demand
no traps at all; "superhuman" requires over half the floor to be
lethal, so its sixty-odd certified pushes must all be threaded
between landmines. An option marks the deadly squares, as training
wheels.

**Maze.** Find the keys, open the doors, get out — in as few steps as
you can. Arrows walk, **R** puts you back at the start, and the par is
always an exact minimum, found by breadth-first search over
`(cell, keys held)`; that search is affordable at every size the ladder
deals, so unlike Sokoban this screen never has to say "at most".

A maze on its own is not a planning task, which is the problem the
generator sets out to solve. A perfect maze has one route between any
two cells, so there is nothing to choose and one hand on one wall
solves it without thinking at all. Two things make the route a
decision. A share of the dead ends are opened back into the maze, so
there are several ways round and the shortest has to be picked rather
than found. And coloured doors are placed on cells that genuinely
*separate* the start from the way out — each is a real lock, not
scenery, and each key is genuinely needed. Every key can be had before
its own door, by construction, so every maze is solvable by induction
along the doors rather than by hope.

That leaves the question of whether any of it is worth *planning*, and
the first answer measured was no. Burying each key one region deeper
than the last makes the keys a queue: the next one to fetch is always
the nearest one, and a walker who never looks further than one key
ahead ties the optimum every time. Scattering them instead — anywhere
at all that can be reached before their own door — leaves several
within reach at once, so which to fetch first is a real choice. That
one change took the share of mazes where fetching them nearest-first
costs something from one in ten to six in ten.

So the ladder runs on two measured axes, ranked rather than merged.
The step floor is the spine: how long the maze is, and what the screen
reports. The *planning* floor is the second: the least share of the
walk that fetching the keys nearest-first throws away. It starts only
at four doors, because below that the keys are too few for the order
to be worth anything, and it never outranks the step floor — a rung
that cannot manage both would rather be long than clever. The fifteen
rungs run from "first steps" (a 9x9 maze, no doors, twenty-two steps)
through "the gauntlet" (25x25, four doors, at least 172 steps of which
at least 2% is wasted by walking it greedily) to "superhuman" (37x37,
six doors, at least 297 steps and 4%). Every floor was measured over
two hundred mazes a rung rather than guessed.

An option marks where you have already been; turning it off makes the
maze a memory task as well, since you then have to carry the map
yourself.

#### 3D Maze

The same maze, from inside it. The screen splits: a first-person view
on the left, cast one ray to a screen column, and on the right a map
of the whole maze — corridors, where you started, where the way out
is, and every door and key in its colour. The map is complete and
accurate.

It is also **fixed**. It is drawn once when a maze is dealt and never
touched again: it does not scroll, it does not follow you, it does not
dim what you have walked, and it carries no marker saying where you
are. That is not an omission, it is the task. You know where you began
and you know what you have done since, so your position is entirely
determined — by arithmetic you do yourself, once per action, without
ever being shown the answer. Miss one turn thirty moves ago and every
corridor still looks plausible and every decision after it is wrong.
The claim is checked the only way worth checking: the tests digest the
pixels under the map panel before a walk and after it, with the player
somewhere else entirely and carrying a key it did not start with, and
require the bytes to be identical.

The maze is not a new one. It comes from the 2D Maze's generator at
the same rungs, so level nine here is the very same maze level nine is
there — which is what makes the price of the view readable straight
off rather than guessed at across two ladders tuned separately.
**Turning costs a step**, and that is what the price is: measured
across all fifteen rungs, the minimum runs a steady 1.27–1.34 times
the flat one next door. Turns have to cost something, or a player
spins on the spot at every cell, reads all four corridors for nothing,
and the task collapses into a 2D maze with a narrow window. Walking
into a wall costs nothing, as in the 2D maze — the wall is plainly
visible from where you are standing.

Two foils say what the rungs are worth. One hand on one wall solves
any maze without loops, and is what a player falls back on once it has
lost its place. Rung one is a perfect maze — no loops at all — and it
gets out of every one of thirty, at 2.7 times the minimum. From rung
two upward the ladder braids dead ends back into loops, and it starts
both wandering further and failing outright: 3.0 to 4.5 times the
minimum where it succeeds, and on a fifth to two fifths of mazes it
never finds the way out at all within twenty thousand steps. The
second foil is the one the task is really about: a player that plans perfectly from
where it *believes* it is, and now and then fails to notice that it
moved. At no slip it walks the exact minimum. At one dropped update in
fifty it gets out of "four doors" twice in eight tries; at one in
twenty, never. Nothing tells it. Every corridor still looks like a
corridor.

The par is its own exact minimum over cell, facing and keys rather
than the flat one on the maze, so the walk is scored the way the rest
of the planning category is scored. Breadth-first over a state packed
into one integer — `(cell * 4 + facing) * 64 + keys` — which is about
three times the speed of the same search written with tuples and a
call to `move()` per edge, and gives the identical answer, as the
tests require of it. The largest rungs still take about a second to
open, but most of that is the 2D Maze's own generator hunting for a
maze that meets the rung's floors: a wait this task inherits rather
than adds.

The screen gives up about a fifth of its height to stop clear of the
strip the agent outcome reader scans. The corridor could have kept it —
it is painted in greys, and grey has its three channels equal, which is
never a verdict and never fades into one — but the map beside it draws
doors and keys in colours that are, and the two share a stage. What that
costs is nothing where it would have mattered: at 37x37 the map's cell
size is set by the panel's *width*, so the height it gave up buys the
guard for free.

#### 3D Sokoban

The same warehouse, from inside it — the 2D game's own engine
throughout. The generator, the ladder, the solver that certifies a
level and the test that says a position is provably lost are all
`neural_workshop.sokoban`; what is new is where you stand. On the left
a first-person view, cast one ray to a screen column; on the right a
plan of the whole warehouse — walls, goals, where you came in, and
where every box stood at the moment the door shut behind you.

The plan is **fixed**, and here that is a harder promise than the 3D
Maze's, because in a warehouse the world moves too. It is drawn once
when the level is dealt and never touched again: not when you move,
not when you turn, and *not when a box moves*. It goes on showing the
load where it started, however far you have shoved it. So what you have
to carry in your head is not a position but a position **and a world**,
and every push you make falsifies a little more of what is on the wall.
The errors are yours: the plan was right, you are the one who moved the
box, and if you cannot say where you put it then nothing on screen will
tell you. The tests digest the pixels under the panel before a push and
after it, with a box standing where the plan does not show one, and
require the bytes to be identical.

Sokoban is the right game to do this to, because Sokoban does not
forgive. From above, a pocket is visible; from inside a corridor you
can see the wall in front of the box and not the one behind it, and
whether the push you are about to make is the one that loses the
warehouse is a question about a model you are holding rather than about
anything you can look at. A box is drawn as a wall in another colour,
because that is what it is to the eye — the ray caster is not told
which is which — and a box already home is drawn in the goal green,
which is the one thing the room gives away for free.

**Turning costs a step**, for the reason it does next door: with free
turns a player spins on the spot at every cell, reads all four
corridors and every box within sight of them for nothing, and the plan
stops being the only account of where things are. So the par is in
*steps* rather than in pushes, and it is an exact minimum over
`(boxes, cell, facing)` — measured across the first nine rungs, a mean
of **3.8 times** the flat game's push count and never below 2.2 or
above 5.5. The exact minimum stays affordable further up than it has
any right to because the walking contracts away: a run is a sequence of
pushes, the pose after a push is decided by the push, and the cheapest
walk between two poses is a small breadth-first sweep over
`(cell, facing)` in the box-avoiding floor. What is left is Dijkstra
over the same push-space the flat solver walks, with the walk priced
into each edge instead of being free. It certifies a minimum on ten
deals out of ten up to rung eight and two out of ten at rung nine;
above that the par is the search's own frontier, a proven lower bound,
which the screen says rather than hides. The contraction is checked
against a plain breadth-first search over every reachable
`(boxes, cell, facing)` on the small rungs, because a shortcut that
gives a different answer is not a shortcut.

Two foils say what the two halves of the state are worth, and they fail
in different ways, which is the interesting part.

`push_forgetful` never loses its own place. It tracks its position
perfectly and it plans perfectly; what it drops is the load, and when
it does it falls back on the plan pinned to the wall. Over thirty
warehouses at "tight corners", forgetting after one push in ten it
still finishes twenty of them, at 1.16 times the minimum; one push in
four, eleven of them at 2.03 times; one in two, seven of them at 2.92
times, with eight more wedged past saving. Forgetting the load costs
**steps**, and then the warehouse.

`push_slipping` is the 3D Maze's own foil brought over: it plans
perfectly from where it *believes* it is and now and then fails to
notice that it moved. In a maze that costs steps. Here it costs the
warehouse, and the numbers say so flatly. At one dropped update in
fifty it finishes eighteen of thirty; at one in twenty, twelve; at one
in ten, **one**. Of the other twenty-nine, eighteen are positions
`deadlocked` can prove are lost and eleven are a player standing among
boxes still out, holding a model in which it has finished. And every
single run it *did* finish took exactly the minimum — it never merely
walks further. It gets away with the slip or it loses the warehouse.

Undo and restart are kept for the person and withheld from the learner,
as they are on the flat screen: undo is how a player explores a line
the way a chess player takes moves back in analysis, and a learner
handed the same key would be handed a way out of the one thing being
measured.

This screen stops its view short of the bottom quarter of the frame,
where the outcome reader looks. A box is Okabe-Ito sky blue,
`(86, 180, 233)`, which is not a verdict colour — but drawn against the
dark room's near-black ceiling its anti-aliased edge runs through
`(69, 140, 180)`, and that is the reader's pattern for a scored trial
exactly. `check_band.py` reports the task clean, and that is the
useless kind of clean: whether a box is ever drawn that low depends on
the deal. So the guard is the geometry — `verdict.above_the_band` — and
the enumeration that found the offending blend is kept beside it as a
test, so the layout keeps its reason.

Writing that argument down is what turned up the same fault, worse, in
the 3D Maze next door, which had been shipping it: see **the agent
environment** below for what a sweep of that one could and could not
have seen.

#### Marble Maze

The wooden labyrinth. Two knobs tip a tray, the tray has walls and holes
in it, and a steel marble goes where gravity tells it. Get every marble
to the green cup before the clock runs out, and do not lose one down a
hole on the way.

It is the workshop's only screen with a **real perspective pipeline**
behind it — a depth buffer, a directional light, a 1024-square shadow
map, four-times multisampling — and that is a requirement rather than a
flourish. The 3D Maze and 3D Sokoban next door are ray casters, which
is the right tool for a corridor seen from inside it, where every
surface is vertical and the only unknown is distance. Here the thing
the player is operating is *the angle of a plane*, and a flat rendering
can show where the marble is but not what the tray is doing. A learner
that cannot see the tilt would be integrating its own action history to
recover the control it is already holding, which is a different and
much worse task. `neural_workshop/ui/render3d.py` is the whole of the
pipeline, in about seven hundred lines.

**The physics is the real thing, in SI units.** A 15mm steel marble on
a 250-to-420mm tray, standard gravity, and a solid sphere rolling
without slipping accelerates at `5/7 g sinθ` — two sevenths of gravity
goes into spin rather than travel. Drop that factor and the marble is
40% too eager, which does not read as wrong physics so much as a board
twice as steep as it looks. Rolling resistance is a constant
`Crr·g·cosθ` against the direction of travel, which gives the tray a
real *stall angle*: below about two thirds of a degree nothing moves at
all, and that is why levelling the tray is a usable move rather than an
approximate one.

**A hole is not a wall**, and this is the part worth playing for. A
marble whose contact patch crosses a rim stops being supported and
starts to *fall* — keeping its in-plane speed and picking up the full
gravity rather than five sevenths of it. Sent across fast enough it
clears the far rim and lands with a clatter. Measured on a 12mm hole:
lost at 0.15 and 0.45 m/s, across at 0.95. Widen the hole to 24mm and
no speed saves it. That is the only reason to ever go fast, and it is
why the capture test is on the marble's *height* rather than on its
position.

**Every tray is generated, and certified before it is dealt.** A
randomised-depth-first maze, braided to taste, walls merged into strips,
then holes bitten out of the corridors against an analytic clearance
test — and then the whole tray is proved passable by a Dijkstra sweep
over a grid of every place the marble's *centre* may legally be. A tray
that has been sealed off by its own holes is not dealt. That matters
more than it sounds: from outside, "unwinnable" and "very hard" look
identical, and the upper rungs run corridors two marble-widths wide.

The sweep does double duty. It is the certificate, and it is also the
distance field the coach's shaping potential is quantised out of, so
the two are the same computation and cannot drift apart.

Two bugs that certification could not catch are worth recording,
because both passed every test that existed at the time:

- **The route bar.** Holes cut a tray into pockets, and a pocketed tray
  still certifies — the marble is placed in the pocket the cup is in,
  and everything passes while "inhuman" deals a marble twelve
  centimetres from home on a forty-centimetre tray. The certificate
  answers *can this be won*, which is not the same question as *is this
  the rung it says it is*. A tray now owes 45% of the route its walls
  alone would give, and gives holes back until it can pay.
- **The rim start.** The free grid rules out points inside a hole, so
  the furthest legal point on a tray is often *exactly on a rim* —
  legal, not over the hole, one millimetre from being over it. Random
  play at rung four resolved at a median of 59 ticks, because half the
  trays dropped their marble down the hole it was standing on inside
  the first second whatever anyone did. A trial lost before the player
  has touched a knob is not a hard trial; a start now clears every pit
  by two marble radii over and above the pit's own.

**Several marbles share one pair of knobs**, from rung five up, to four
of them at rung thirteen. They start nose to tail along the same route
so that a tilt which serves one at least points the rest the right way,
and they knock each other about with an impulse along the line of
centres. This is also where the dense reward stops: the shaping
potential is the summed quantised distance of every live marble, and
the guarantee that one action moves it by at most one step rests on a
marble travelling at most 16.7mm in a tick against a 25mm quantum —
which is an argument about *a* marble. Three of them can each cross a
boundary in the same tick, and on the top rung they measurably do. So
the several-marble rungs are honestly sparse rather than dishonestly
dense, and the gate is on the marble count rather than on the caller.

Two things about the rendering are worth knowing before changing it.
The holes are cut with `discard` and their rims antialiased by
**alpha-to-coverage**, not by per-sample shading: measured on the top
rung at 1880x886, `glMinSampleShading(1)` costs **39.6ms a frame
against 3.8ms**, because it runs the whole shader — wood grain and all
— four times per pixel across the entire tray to smooth an edge a few
thousand pixels long. And the stage stops above the bottom quarter of
the frame, because lit pine passes straight through the outcome
reader's pattern for a *negative* verdict: `(196, 128, 74)` is red over
180 with the other two under 140. `check_band.py` reports the task
clean, and that is the useless kind of clean — whether a frame lands
there depends on the grain seed, the tilt and the shadows. The guard is
the geometry, and `tests/test_ui_marblemaze.py` asserts it at six
window sizes.

The marble's colour, roughness and normal maps are baked out of a
source `.glb` by `tools/bake_marble_textures.py` — 20MB of asset down
to 640KB in `res/marblemaze/` — and the shader keeps a procedural
fallback, so a checkout without them renders a plainer marble rather
than a black one. Nothing is taken from the companion labyrinth asset:
its base-colour map is a UV *atlas* keyed to a fixed two-million-
triangle mesh, and this task generates its trays, so there is no mesh
to key it to. Six candidate squares were cropped and mirror-tiled
looking for a patch of clean grain to tile instead; every one large
enough contained the pale gaps between islands. The tray keeps its
procedural timber, which is better than any of them.

Random play is paid, and paid nothing but red: it wanders a marble into
a hole or runs the clock out, and neither is a green. That is the same
floor Scramble has — what a learner gets for free is what a mistake
costs — so the green needs a policy that knows the answer, and
`tests/test_ui_marblemaze.py` flies one through the same four ports.

**Freeform Tetris.** A well seventy-two columns wide and thirty-two
deep — a tetris well is ten by twenty — with cells about a third the
size, so that where a piece goes is a search rather than a choice
between ten slots. Two things about it are not tetris, and both exist
to move the difficulty off the clock.

*Nothing is dealt at you.* Five pieces sit in a tray and you click the
one that comes next while the current one is still falling, or press
its number. The question the game asks is *which of these, and where*,
and both halves are yours.

*Rotation is continuous.* Hold **Up** or **Down** and the piece winds
round through the whole circle at a steady rate rather than clacking
through four poses. Within seven degrees of a quarter turn it is held
square to the grid — a detent, wide enough to catch by hand — and
everywhere else it is held exactly where you wound it. **S** squares
it up in one go. The detent costs about a sixth of the circle, and the
options screen will give it back: set it to nothing and all 360
degrees are held exactly as wound, with **S** the only way to square
up. Nothing else changes, and in particular a drop no longer quietly
straightens a piece that was meant to be crooked — deciding a piece is
close enough to square is the screen's job, never the engine's.

**The promise, and what it costs.** Every piece in the tray has
somewhere to go that buries nothing, and the count of how many such
places it has is printed under it. That is not a claim about the
generator alone. Pieces are cut out of the board's own skyline —
`carve` takes a window of columns, reads the height of each, and fills
that notch to a level top — so a piece dropped back where it came from
rests on solid cells all along its underside. But *you* choose the
order, so a hand cut against one skyline is a hand about a board that
may not exist by the time you use it. After every placement the whole
tray is re-checked by enumeration, and any piece the last move
stranded is cut again and says so. The promise is therefore *is true
now* rather than *was true when dealt*.

The free spin is where it can be given away, and the game is explicit
about that rather than quietly forgiving it. What lands is what the
grid sees: every cell whose centre falls inside the turned piece. At a
quarter turn that is the polyomino exactly, from any offset. At
thirty-four degrees it is a ragged blob that is a different shape, and
the ghost draws it — hollow teal outlines when the drop would bury
nothing, hollow red-orange when it would, with the count on the status
line. So a gapless run always exists, at lattice angles, and the spin
is a risk you may take on top of it rather than a way the promise can
be lost.

**Difficulty is shape, and only shape.** Gravity is a setting you
choose once and no rung ever touches it; there is not a field on a
rung that could. The ladder climbs by cutting more awkward pieces: the
first rung cuts from level ground and gives level tops, which makes
every piece it can produce a rectangle, and by the seventh it is
cutting dented combs across six columns from skyline that varies by
three. `tests/test_tetris.py` plays a full run at every one of the
eight rungs through the game's own controls — wind, steer, drop — and
holds the hole count at zero throughout.

**Measured.** A reference player that always takes a gapless drop and
takes the tray slots at random ran 28,800 placements across the eight
rungs without burying a single cell. Cutting from the *lowest* of
several candidate windows rather than the first acceptable one is
worth more than it sounds: at the seventh rung it holds the mean pile
height at 9.3 rather than 16.6 and drops the re-cuts from 130 to 49
per 750 placements, because a level board has more stretches of
skyline that match any given piece. Nine hundred steps of uniform
random play through the agent boundary reach 25 verdicts at the first
rung, 12 green and 13 red — a high floor, and the reason is worth
knowing before reading a curve drawn on it: the first rung cuts
rectangles, and a rectangle that falls on its own onto level ground
lands flush wherever it is. The same sweep reads 8 green to 19 red at
the fourth rung and 3 to 15 at the seventh. The floor is a property of
the rung, not of the boundary.

One bug is worth recording because only a test could have found it.
Python's `round` breaks ties to even and the rasteriser floors, so a
piece whose centre sat exactly on a half cell was reckoned to be in
one column by the falling piece and the next column by the hard drop —
about one pose in a hundred, showing up as a piece that jumped a
column the instant it was let go. `snapped` now reads the offset back
off the same scan the collision uses, which cannot drift from it.

Like the other screens here, the well stops above the bottom quarter
of the frame where the outcome reader looks, and the guard is against
the geometry rather than a sweep of pixels — where the pieces land is
content, so a clean sweep of one run says nothing about the next.

**N-in-a-row.** A visual tactics puzzle starts with a five-by-five board and
three-in-a-row, which makes the first position approachable for a child. The
middle rungs return to the familiar five-in-a-row rule, while the upper
rungs make the board and the objective grow together: the final position is
128x128 with 100 in a row to find. It is not a match against a CPU, so the
task measures seeing the winning move rather than waiting for an opponent.

The agent has one opaque port per cell in the largest board, with unused
ports harmless on smaller boards. A pellet is not an answer, and every deal
is rejected unless exactly one empty cell wins immediately. The generator
checks the whole board for both colours, so the useful move is a property of
the position rather than a hidden answer known only to the task. Adaptive
play raises or lowers the rung from the player's success, while the grid,
pellet, and line-length controls can be fixed for children, adults, or a
machine search.

#### Lander

A craft in a lunar valley with gravity, one engine and a tank. **Up**
fires (down and fuel burn), **Left** and **Right** turn, and the agent
has two more ports for firing while turning. Touch down on the pad
slower than the limit, close to upright and without drifting across it.
The minute it gets is plenty.

| Rung | What it adds |
|---|---|
| 1–3 | A wide pad, straight below at first; no fuel limit |
| 4–6 | Starting off to one side and moving; 25 s of fuel |
| 7–9 | Rough ground around the pad |
| 10–12 | Wind |
| 13–15 | Gusts |
| 16–19 | Gravity and the engine's strength change every round, unannounced: feel them out |
| 20+ | The pad slides 8 m back and forth; less fuel, smaller pad, tighter limits |

Speed across a moving pad is judged against the pad, so landing on one
means matching it, not stopping. The model's autopilot lands every
rung below 20 nearly every time and the top rungs a third of the time.

### Self-control

A category of its own rather than a sixth attention task, and the
difference is worth stating. Everything under **Attention** is about
finding or following the right thing. This is about *not* pressing a key
you are already pressing and would rather keep pressing. Reflex would
lose every rung above the fifth by being fast.

**Cookie Thief.** A boy stands at a jar with his hand over it. One press
is one cookie, taken on the beat you asked for it, and at a sixth of a
second a beat that is as fast as you can press. There is no run-up and
nothing in flight: the only thing a player can be wrong about is
*whether* to press.

What you watch instead is **the door**, and it only ever opens. Every
cookie leaves a gap she would notice on its own and that part never
closes again; taking them quickly is noisy on top of that, and that part
dies away on a quiet beat. Both halves are drawn, in one colour at two
strengths, because they are the same door opened further. She comes the
first beat the door reaches a number nobody is told — the range is
shaded on the frame, so you can see you are into the part where she
might be and not which press is the one.

Four things to do with a beat and every one of them worth doing. Grab.
Wait, which lets the noise die down and so buys the grab after next.
**Leave**, which banks the haul and ends the round: the only move that
cannot go wrong and the only one that stops you earning. And reach for
the golden one, which is two beats you cannot take back.

The ladder turns on one measured break. Her warning only ever gets
shorter, six beats down to none, and it runs out for good at the sixth
rung. `oracle_cookie.py --player impulsive` is a thief who takes every
grab short of a certainty and leaves only once somebody is visibly in
the doorway: below the break he is caught in **0%** of rounds, because
the warning is enough on its own; from the sixth rung up he is caught in
**95–100%**, because the press that opens the door far enough is the one
she is already looking at. There is nothing to react to, and stopping
early is the only defence left.

Every rung is winnable **without gambling at all**. `oracle_cookie.py`
takes only grabs that cannot possibly bring her — it can compute that,
because `after_a_grab` reads the jar and the rung and nothing else — and
it clears 300 of 300 at every rung in 13 to 29 beats, two to five
seconds of real time. So a round that was lost was lost on a decision
rather than on the deal. The suite runs it.

A round is scored twice, and the two scores are different questions.
**Clean** is the bar: the quota met with no grab seen. **Points** are
the margin — every cookie is worth one, including the ones past the
quota, and every grab she saw costs two. Capping the haul at the quota
made one more cookie worth exactly zero at a real risk, so the answer
was always to leave on the bar and the round ended at the moment it got
interesting.

`--haul` prices the greed rather than arguing about it, and the price
depends entirely on whether there is a warning. Below the break, pushing
the door the *whole way* into the shaded range is caught **0%** of the
time: you see her coming and leave, so the range is free to walk into.
Above it every step in is paid for, and the haul turns over — a little
way in beats stopping at the line, and the whole way in is worth a third
of it and loses every round.

The **golden cookie** is the other decision on the top three rungs, and
it is neither a trap nor free money — which took measuring to establish,
because a table of hauls alone said it was free money. It sits on the
counter rather than in the jar, so it is worth six or eight cookies that
never open the door on their own; reaching for it is two beats in which
he can neither grab nor leave, and three grabs' worth of noise goes into
the door across them. Taken **on sight** it raises the haul from 18 to
18–22 and throws away a third to a half of the clean rounds doing it.
Taken **only when the door can absorb the reach** — a sum a player can
do off the screen — it is 100% clean and worth 24 to 26, the biggest
single gain in the game. `oracle_cookie.py --gold` prints clean rounds
beside the hauls now, for exactly that reason.

Setting the price of greed took two goes and the failure is worth
recording,
because it is arithmetic rather than taste. A grab into the shaded range
pays `+1` when it is safe and costs `CAUGHT_COST` when it is not, so it
is worth taking exactly while the chance of it bringing her is under
`1/(1 + cost)`. At a cost of three that line sits at one in four, which
is finer than a grab can be aimed — one cookie moves the door about half
a step into the range — so the greed dial had its best setting at zero
and the shaded range was decoration. At two the line is one in three,
which a grab can land inside, and the dial came alive. A test holds the
inequality rather than the number.

The guessing floor is measured rather than derived, because there is
nothing here to derive: what a run of random presses is worth is
whatever a random hand takes before the door is open far enough. It runs
53% at the bottom rung — one cookie, six beats of warning, and *leave*
is one key in four — to 0% from the fourth rung up.

Coach mode is **not** the potential-based shaping the maze and the belt
got, and the wrapper says so rather than letting the resemblance stand.
There is no potential and nothing telescopes. It is the *haul* taken
apart: a cookie he got away with is a piece of the green and a grab she
had her eyes on is the red, so the sum over a round tracks the points
without a learner having to reach the end of one. Where it still
diverges is that the verdict is a bar and the sum is a margin; they
agree on the ordering that matters and cannot agree on what a cookie
past the quota is worth, because one bit cannot carry a margin. What the
coach cannot see is the trigger and the deadline, and that is structural
rather than careful: every function it reads takes a thief and a rung,
and neither of those can reach a `Setup`.

Three things about the feel were wrong before they were right, and all
three came from the same mistake — modelling the boy's momentum as a
*speed* he had to spend. Stopping meant waiting for a bar to fall, the
arm lagged behind the key that moved it, and a press bought a fraction
of a cookie rather than a cookie. The momentum is in the door now
instead of in the boy: it is the room that fills up rather than the
thief who has to slow down, and the thief himself is instantaneous.

**Stop & Switch.** A circle or a square, blue or orange, and two keys:
**F** or **Left** for one answer, **J** or **Right** for the other. The
rule above it says which feature counts. Answer before the window
closes, and when a red ring comes up around the shape *after* it
appeared, answer nothing at all. Pass a block at 85% right (90% from
rung 20).

| Rung | What it adds |
|---|---|
| 1–3 | Shape only, 12 shapes, the window narrowing from 1.5 s |
| 4–6 | Stop rings on a quarter of the shapes, coming later each rung |
| 7–9 | Shapes on the left or right, against the answer's side half the time |
| 10–12 | The colour rule too, switching on a cue every four to six shapes |
| 13–15 | Switches at random, still cued |
| 16–19 | No time to prepare; seven in ten shapes on the wrong side |
| 20+ | A third rule, *opposite*: press the side away from the shape; windows down to 0.45 s, stops to 0.35 s in |

A stop arrives a fixed delay after the shape. That is the classical
stop-signal design, so the task measures what it means to: how late you
can still cancel a press you have started.

**Delay.** One coin now, or eight if you wait for them. **A** or
**Left** takes the coin (or, while waiting, gives up and takes it);
**D** or **Right** waits. Coins only count for the minute you have, so
the question is never *whether* waiting is virtuous but how long a wait
is still worth it. Par is set by a ladder between always taking the coin
and the best fixed patience for that run.

| Rung | The waits |
|---|---|
| 1–3 | Always three seconds, shown |
| 4–6 | Two to six seconds, not shown: wait them out |
| 7–9 | Heavy-tailed: most short, some of them minutes. Give up after a few seconds |
| 10–12 | Shown, with different coins on each offer: compare rates |
| 13–15 | Halfway, the waits change from fair to heavy or back |
| 16–19 | Three in ten never come |
| 20+ | Two kinds in one 45-second run |

The right amount of patience is a property of the world, not of the
player. Waiting it out is right at rung 5 and wrong at rung 8, and the
screen looks the same.

### Decision making

Choosing under uncertainty: what to find out, when to stop finding out
and commit, what a wrong commitment costs, and what waiting costs while
the world moves on.

#### Sonar

One target is hidden on a grid. Click a cell to **ping** it: it costs
one point and shows how far away the target is, in bands of distance.
Shift-click or right-click to **dig**: if the target is there the round
is won; if not, it costs the rung's penalty. The round passes if it
cost no more than **par** — what a Bayesian reference player paid on
the identical deal, give or take the rung's slack.

Every move is a trade, and the ladder adds the trades one at a time:

| Rung | What it adds |
| --- | --- |
| 1–2 | Readings are exact distances. Which cell to ping is the whole question. |
| 3–4 | Readings come in coarse bands, so a ping says less and choosing it well matters more. |
| 5+ | **Noise**: some readings are off by a band. One ping is no longer proof, and a contradiction is something to resolve. |
| 8+ | **Drift**: the target sometimes steps to a neighbouring cell with each action. Waiting is no longer free, and the risk of a wrong dig trades against the risk of losing the trail. |
| 13+ | No slack: match the reference or better. |
| 21+ | Par is *below* the reference's cost, by more at every rung. The top of the ladder is out-planning it. |

The wrong-dig penalty rises at every rung, so the right moment to stop
asking and commit keeps moving.

Par is fair because the reference plays the same deal: noise and drift
are drawn by action number, not by which action was taken, so the
reference meets the same lie on its third ping and the same drift after
its fifth action as you do. It keeps an exact posterior over the grid,
pings where it expects to learn the most, and digs when the expected
penalty is about one ping, or, on a drifting target, when a ping can no
longer learn faster than the drift forgets. It is strong but greedy:
planning further ahead can beat it.

The agent plays it through six ports: four move a cursor (free), one
pings and one digs. It is turn-based, so it takes the think clock.

#### Dispatch

Sonar's decisions, with the clock running. A town map with three
stations and two or three crews. Incidents appear as discs that grow,
and one that fills its ring is lost. Click a crew, then click where to
send it (or press its number, then the incident's letter, or J, K or L
for a station). A crew at an incident shrinks it until it is gone; two
crews shrink it twice as fast. Any crew can be sent somewhere else at
any moment, and what it leaves unfinished starts growing again.

The town's **damage** is the seconds real incidents spent open, plus
twenty for each one lost. A round passes if that is no more than par:
the damage a reference dispatcher took on the identical round. Where
and when every incident appears, how fast it grows, whether it is real
and how wrong its report is are all fixed before the round starts, so
the reference faces exactly what you do.

| Rung | What it adds |
| --- | --- |
| 1–2 | Two crews, one incident at a time and long gaps. Par is nearly twice the reference's damage. |
| 3+ | **Bursts and lulls.** Several incidents at once, then quiet. A burst wants the nearest free crew sent now; a lull is the only time to move crews to where the next burst will need them. |
| 4+ | **False alarms.** A pale disc with a question mark is unconfirmed; a **scout** is three times as fast as a crew and can go and look, but looking takes time the incident keeps growing through. |
| 6+ | **Estimates.** An unconfirmed report's size is off by a margin that widens with the rung. |
| 8+ | **Refits.** A crew sent to a station with Shift held stands there twelve seconds and works twice as fast for the rest of the round. Sent anywhere before the arc round it closes, it loses the refit whole. |
| 12+ | No allowance: match the reference. |
| 21+ | Par is *below* the reference's damage, by more at every rung. |

Growth keeps climbing while the crews stay at three, so by the upper
rungs an incident across town burns out before a crew that sets off at
once can reach it, and where the crews were standing when it appeared
decides it. The reference itself starts losing incidents around rung
sixteen.

The refit is the town's one investment, and it is there for the
decision every other rung leaves out: weaker now for stronger later.
Twelve seconds of a three-crew town is a third of its hands, taken out
of whatever those twelve seconds turn out to hold, and what it buys is
worth less the later in the round it is bought. So there is a question
of when, of which crew, of how many at once, and — when a burst lands
on a refit that is ten seconds in — of whether the incident is worth
the ten seconds. Shift-click a station, or hold Shift with J, K or L,
to send the selected crew in; a refitted crew is drawn larger and
violet.

What a refit buys was chosen by measurement, not taste. Handed to the
reference free at the start of a round, two extra crews cut its damage
by about an eighth at best and by nothing at all up to rung ten: it is
the road and the job that take the time, not the wait for a free crew.
Every crew working twice as fast cuts it by a quarter to a third on
every rung. An investment that is not worth much is not a decision, so
the refit buys work rate.

The reference is deliberately plain: each idle crew goes to the most
urgent incident it can still save, the scout to the nearest unconfirmed
report, and a crew with nothing to do goes in for its refit — one crew
at a time, and seen through whatever comes up. Over sixty rounds a rung
that takes 13 to 21% less damage than never refitting, while sending
every idle crew in at once gives two thirds of the gain back at rung
eight and a third at rung sixteen, and from rung twenty loses most of
an incident more a round. It never moves an idle crew to where the next
burst will be, never puts two crews on one job, never times a refit to
a lull and never changes its mind — which are the ways to beat it.

The agent plays through eighteen ports: one per unit, one per incident
letter, one per station to wait at and one per station to be refitted
at, and an order is a unit then a place. The task
is clocked, so it refuses the think clock; it already has one. Built
for a runtime it also pays per incident, green when one is saved and
red when one is lost, on top of the round's verdict, because one bit a
minute is very little to learn from. That is the round's own result
taken apart, not shaping, and it differs from the round's verdict in
one way: it does not count how long an incident waited. A finished
refit is not paid: whether it was worth its twelve seconds is what the
round's verdict is for.

#### Triage

A few cards, each a row of digits to sort into order by swapping
neighbours, each paying something when it is sorted -- and one budget
of moves for all of them. Not everything on the table can be had, so
the task is not sorting, which is easy, but deciding what to spend
effort on: which puzzles are worth their cost, in what order, and when
to walk away from one that turned out dearer than it looked. A card
worked on and left unsolved pays nothing, and its moves are gone.

The cost of a row can be read off it: the fewest swaps that sort it is
the number of pairs of digits standing in the wrong order. Reading that
is part of the task.

| Rung | What it adds |
| --- | --- |
| 1 | Two short rows and moves enough for both. |
| 2+ | More cards (up to eight), longer rows (up to nine digits), and a budget that covers less of the table -- under a third by rung 20. |
| 8+ | What a card pays no longer follows what it costs. |
| 12+ | Rows dealt **face down**: a card shows its length and pay, and turning it over costs a move. |
| 21+ | Par asks for more than the reference, towards the best any choice of cards could earn. |

Par comes from a reference on the identical deal that keeps taking the
card paying most per move it is expected to cost, and sorts by the
shortest route; below rung twenty par gives some of its earnings away,
and past it par climbs towards four fifths of the gap to the best
possible choice -- a real plan, not a ratio. Random play passes about a
third of rung-one rounds and essentially none past rung five. Seventeen agent
ports: open cards one to eight, swap neighbours one-two to eight-nine
in the open row, Done. Turn-based, so it takes the think clock, which
is the point: what is measured is what gets thought about.

#### Gamble

A row of slot machines with hidden odds. A pull pays what that machine
pays on a win, or nothing, and the strip under each machine shows its
last results -- green a win, grey nothing, red a loss. Which machine is
best has to be found by pulling, and every pull spent finding out is a
pull not spent on the best one: explore or exploit.

A round is scored by what its pulls were **worth**, not what they won:
each pull counts what its machine paid on average at that moment. So a
lucky streak on a bad machine does not pass a round and an unlucky one
on the best machine does not fail it. Coins are shown as well, and
where there is a bankroll they are what runs out.

| Rung | What it adds |
| --- | --- |
| 1 | Two machines far apart. |
| 2+ | A machine more every three rungs, up to eight, closer together. |
| 6+ | The odds **drift**: what was learned goes stale. |
| 10+ | Machines that **bite**: they win more often than the best machine and now and then lose big, so the one that feels best is not. |
| 14+ | The odds **jump**: the machines trade places at an unannounced pull. |
| 18+ | A pull **costs a coin**, wins pay more, and the round starts with a bankroll: run it dry and the round is lost. When nothing pays, **Stop** walks away. |
| 21+ | Par asks for more than the reference: a growing share of the gap between it and knowing the odds. |

Every machine's odds at every pull, and the draw it would make, are
dealt up front, so the reference meets what the player would have met
on the same pull. Par runs from halfway between random pulling and the
reference's worth at rung one to the reference itself at twenty-one.
The reference is discounted Thompson sampling with a belief about each
machine's win and bite rates, and stops once every machine has paid
back less than it took. Measured over sixty deals, random pulling
passes about a third of rung-one rounds and almost none past rung
eighteen; a greedy player that tries each machine once passes three
quarters at rung one and a fifth at rung thirty. Nine agent ports: pull
machines one to eight, Stop. Turn-based, so it takes the think clock.

#### Bluff

A small poker game. Both players put in a chip and get one card from a
short deck; the higher card wins a showdown. The first to act checks or
bets a chip; facing a check the other checks (showdown for two) or
bets; facing a bet a player folds (the bettor takes the pot) or calls
(showdown for four). Who opens alternates. The log on the right shows
the last hands -- both cards where a showdown turned them over, what
each did, what it won -- and that log is how the opponent is read.

| Rung | Across the table |
| --- | --- |
| 1-2 | A **calling station**: calls anything. Bet good cards, never bluff. |
| 3-4 | A **rock**: folds all but the best. Bluff it. |
| 5-6 | A **maniac**: bets nearly every hand. Call it down. |
| 7-13 | One of those, unannounced, from 10 or a sound player; five cards. |
| 14-17 | A player who **adapts to you**: bluff often and it calls more, fold too much and it bluffs more; seven cards. |
| 18+ | One that **changes** at an unannounced hand; nine cards. |
| 21+ | Par is above the reference by a growing share of a chip a hand. |

As in Gamble a round is scored by what its choices were worth -- each
hand's chips averaged over every card the opponent could have held,
against what it really does then -- so the deal's luck neither passes
nor fails it. Cards and the opponent's coin tosses are dealt by hand
number, so the reference plays the same hands. It models the opponent
from showdowns (how often it bets and calls with low, middle and high
cards, forgetting slowly) and plays the best reply, looking ahead
through its own later choice. Par runs from a sound player that never
adapts at rung one to the reference at twenty-one; one-note and random
players fall well short. Two agent ports: check or fold, bet or call.
Turn-based, so it takes the think clock.

#### Explore or Exploit

Slot machines, each with a payout that wobbles around a mean you are
not told. Each card shows the machine's last six payouts. Pull (click or
the number keys) as many times as the round allows and finish above par,
which a ladder sets between pulling at random and a reference that
tracks every machine's recent average and its doubt.

| Rung | What it adds |
|---|---|
| 1–3 | Two machines, far apart, 30 pulls |
| 4–6 | Three and then four machines, closer together |
| 7–9 | The means drift |
| 10–12 | And jump without warning, once in 18 pulls |
| 13–15 | Six machines |
| 16–19 | Payouts show up in batches of five, so you choose before you see |
| 20+ | Eight machines, 80 pulls, noisier payouts; par above the reference |

A machine you stopped pulling never tells you it got better, so the
only way to know is to spend a pull finding out. The exploration that
pays at rung 10 is wasted at rung 3.

### Computer use

#### Desktop

A small computer, drawn by the task itself: windows with title bars,
switches, rows of choices, colour swatches, sliders with notches,
steppers, dropdown lists, and a taskbar with a Start menu, a button for
each open window and Done. A card beside the screen lists settings to
reach, each named by its window (or dialog) and ticked once it holds.
Moving the pointer is free; **every click and every drag costs one**,
whatever it hits. Press Done when the card is all ticked. The round
passes if it is, and the clicks came in at or under par.

Every other task gives its controls a fixed meaning. Here the only
controls are a pointer, a click and a drag, and what they do depends on
what is under the pointer: which window is on top, which tab is open,
whether a menu, a list, a dialog or a popup is in the way.

The window manager keeps a real one's rules. Only what is on top takes
a click, and a click raises its window. Drag a title bar to move a
window and its bottom-right corner to resize it. **–** minimises it to
the taskbar; **×** closes it, throwing away whatever it had not
applied, and the Start menu opens it again. Sticky notes stay on top of
everything until they are moved or put away.

| Rung | What it adds |
| --- | --- |
| 1 | One window, one switch, one setting. |
| 2–4 | Rows of choices, then sliders, then dropdown lists; more controls and more settings. |
| 5+ | **Tabs**: only the open tab's controls are there. |
| 6+ | **Scrolling**: a tab holds more rows than the window shows. |
| 7+ | **Colour swatches**; the card shows the colour beside its name. |
| 8+ | **Menus and dialogs**: settings in a dialog opened from the menu bar, kept by OK, thrown away by Cancel. |
| 9+ | **Steppers**: − and +, one step a click. |
| 10+ | **Popups** arrive on a set click, take every click until answered, and offer *Not now* beside *Restore*, which resets a window's settings. The two swap sides. |
| 11+ | **Overlapping windows**, more every three rungs, up to six. |
| 12+ | Windows that start **minimised**. |
| 13+ | Windows that start **small**: scroll, or drag the corner once. |
| 14+ | **Sticky notes** over the work. |
| 15+ | **Greyed-out controls**, with a note saying which other setting they need. |
| 16+ | **Apply**: changes pending until it is pressed. |
| 17+ | A window hanging **off the edge of the screen**, to be dragged back. |
| 18+ | Windows that start **closed**, reached from the Start menu. |
| 19+ | **Submenus**: menus that cascade from a *More ▸* item. |
| 21+ | Par is below the reference, by 1% more at every rung. |

From rung 6 the computer also has **files**. A file explorer window
has a toolbar (Back, Up, Cut, Paste, Delete), a path bar, a sidebar of
places (Home, Desktop, Documents, Downloads, Music, Pictures, Trash),
tabs that each keep their own folder and history, a **+** for another
tab, and a grid of icons that scrolls. One click selects an icon; two
clicks on it in a row open a folder. The desktop itself carries icons:
the Explorer, the Trash, shortcuts to apps, and whatever has been saved
to the Desktop folder, opened the same way. Start opens a panel of
pinned tiles with **All apps** behind it, an alphabetical list of
everything. Files and folders move by Cut and Paste, or by **dragging
an icon** onto a folder, a sidebar place, another tab's header, the
open grid, the bare desktop (which saves it to Desktop) or the Trash.
A folder will not go inside itself. The card asks for files to be
moved, deleted or restored, each with the path it is at now.

| Rung | What the files add |
| --- | --- |
| 6+ | The **explorer** and one file to move; one more every three rungs, up to eight. |
| 9+ | Folders two deep, then three from 16, deeper every four rungs: the long-horizon end. |
| 12+ | The explorer opens with **two tabs**. |
| 14+ | **Deleting** to the Trash, and files saved on the desktop. |
| 15+ | The explorer starts **closed**: open it from Start, the taskbar or its desktop icon. |
| 10+ | **Copying**: Copy and Paste leave the original where it is; the card asks for a copy in another folder. |
| 16+ | An explorer may open in **list view**; View switches between rows and icons. |
| 18+ | **Restoring** from the Trash, and only a few apps pinned to Start. |
| 24+ | **The card hides** after the first click. *Card* on the taskbar shows it until the next click; par allows two peeks. |

The **right button** opens a menu for whatever is under the pointer: on
a file or folder Open, Cut, Copy, Delete, or Restore if it is in the
Trash (back to where it came from); on an open folder's background, or
the bare desktop, Paste and View. It costs one like any click, and
Restore is the short way back from the Trash. Pasting a copy where the
name is taken names it *name - Copy*, as a real desktop does.

So a round mixes short reaches (one click on a switch), medium ones (a
menu, a dialog, OK) and long ones: open the explorer, walk down five
folders, cut, walk across to another branch, paste, and come back to
the settings with the windows rearranged on the way.

Where every window starts and on which numbered click each popup
arrives are fixed by the deal, so the reference meets the same screen
and the same interruptions. It is deliberately plain: it takes the card
in the order listed and finishes each setting, OK or Apply included,
before the next; it scrolls rather than resizes, minimises a note that
is in the way and drags a window back only when it must. Files it moves
one at a time by walking the sidebar and double-clicking down, then
Cut, walk, Paste, or Delete. It solves
every desktop on every rung tested. Measured over thirty desktops a
rung, a player who stretches windows instead of scrolling and finishes
a dialog before its OK saves 5 to 15% of the reference's clicks on the
settings; with files in the round, dragging icons and shorter folder
routes save only 2 to 7% more, so the top of the ladder asks for
planning not yet found.

People use the mouse, both buttons. The arrow keys also move the drawn
pointer (Shift for a long step, Alt for a short one), Space clicks, D
presses and lets go, R right-clicks, and Enter is Done, which is how the
agent plays: seventeen ports, twelve moving the pointer by 80, 20 or 5
units of a 1000 by 640 screen in each direction, then click, press,
release, Done and the right button. Every point the reference uses is
on that grid. It is turn-based, so it takes the think clock.

Still to come: Reset beside
Apply, controls with no labels whose effect has to be worked out by
trying them, selecting several files at once, renaming, search, and
typing.

#### Forms

Desktop is the pointer half of using a computer; this is the keyboard
half. A card on the right says who someone is, and the form on the left
asks for it. Type into the field in focus; **Tab** goes to the next,
**Enter** sends the page. Every key costs one. A form checks what a
form can check -- a date is a date, a phone number is digits, nothing
required is empty -- and a page sent with such a mistake comes back
marked and costs the rung's penalty. What it cannot check is whether
the values are the right person's: one wrong value when the last page
is sent loses the round.

| Rung | What it adds |
| --- | --- |
| 1 | One field. |
| 2+ | A field more every two rungs, Tab between them. |
| 4+ | A **date** to rewrite: "27 June 1955" goes in as 27/06/1955. |
| 5+ | A **phone number** to strip to digits, country code and all. |
| 6+ | A **list that completes**: type the start of a country, Down to the one meant; it is chosen when the field is left. The fewer letters the better. |
| 8+ | **Checkboxes** (Space) and **radio buttons** (Up, Down). |
| 10+ | A field that **appears** only for some answers. |
| 12+ | Two **pages**; three from 18. |
| 14+ | The card is a **letter** to read, not a list. |
| 16+ | The letter mentions **other people's** details too. |

Par is the keys a reference typist pressed on the identical form -- the
shortest prefix that picks a list item, nothing wasted, every page
right first time -- with room up to rung twenty and none from it.
Forty-six agent ports, one per key: a-z, 0-9, space, @ . - /,
Backspace, Tab, Enter, Up and Down. Clicking a field moves to it for a
key. Turn-based, so it takes the think clock.

#### Manual

A control panel never seen before -- switches, knobs from 0 to 4,
buttons, coloured lamps and a one-digit display -- and a written
procedure to carry out on it, then **Finish**. The lamps and display are
wired to the controls by hidden sums, never explained and never needed:
what matters is that *if lamp L2 is red* asks about the panel as the
steps so far have left it, so the procedure has to be really done, in
order, looking as it goes. The round passes if every control stands
exactly where the procedure leaves it -- a button pressed once too often
fails it -- and the controls that do not are outlined afterwards.

| Rung | What it adds |
| --- | --- |
| 1 | One step on two switches. |
| 2+ | Knobs and buttons; a step more every two rungs, up to ten. |
| 5+ | Steps that **depend on a lamp**: *if L1 is green, ...; otherwise ...*. |
| 9+ | **Counts** read off the display, and copying one control onto another. |
| 13+ | **Loops** (*press P1 until L3 is red*), and putting controls **back as they were at the start**, which nothing on the panel still shows. |
| 17+ | The controls in **shuffled order** along each row: found by label, not place. |
| 20+ | Steps that **skip** the next on a condition. |

Every rung asks at least once for the kind of step it adds, and doing
nothing is never right. There is no par. Twenty-one agent ports that
name *places* on the panel, not controls -- six switches, two to each of
four knobs (down, up), six buttons, Finish -- so once the labels are
shuffled the label has to be read. Turn-based, so it takes the think
clock.

#### Browser

A web shop drawn by the task -- a home page of departments, product
lists that sort and run over pages, a page for each product, a cart --
in a browser with a tab, Back, Home, an address bar and a scrolling
page, and a shopping list under the title: *buy the cheapest kettle in
stock, then check out*. Click links and buttons; scroll with the wheel
or the arrow keys; Backspace goes back. The round passes if the cart at
checkout holds exactly what the list asks for, in no more clicks than
par.

| Rung | What it adds |
| --- | --- |
| 1 | One department, two products: *buy the Brava K2*. |
| 3+ | *The cheapest*; the lists can be sorted. |
| 6+ | *In stock* -- shown only on a product's own page. |
| 9+ | *The lowest price plus shipping* -- shipping too only on the product page. |
| 12+ | *Rated 4 or more*, and lists over pages of eight. |
| 15+ | Two things to buy, in different departments; three from 21. |
| 18+ | List prices that can be **out of date**: the product page is what is charged. |

Departments and products grow throughout, to five departments of
twenty-four. Clicks count, a click on nothing included; moving the
pointer and scrolling are free. Par is the fewest clicks that could do
it -- found by searching the shop with the answer known -- plus a share
of what a thorough shopper spends opening every product of the
departments it needs and coming back: all of it at rung one, under a
third by rung twenty and almost none by thirty, where a sorted list has
to be read well enough to open little but the answer. Fifteen agent
ports, Desktop's pointer and two more: move up, down, left or right by
80, 20 or 5 units of a 1000 by 640 window, click, scroll up, scroll
down. Turn-based, so it takes the think clock.

#### Errands

A small computer: an app strip with **Mail**, **Shop** and
**Expenses**, and a **Done** button. The mail says what is wanted --
*could you order the cheapest kettle in stock and claim it back?* --
among mail that wants nothing. Buy it in the shop (Browser's shop,
drawn by the same code), each errand as an order of its own; then in
Expenses file a claim per order: its order number and total typed from
an on-screen keypad (or the digit keys), and a category. Press Done.
The round passes if exactly what was asked was bought, every order has
one right claim and nothing else was claimed, in no more clicks than
par.

| Rung | What it adds |
| --- | --- |
| 1 | A receipt mail: claim it, no shopping. |
| 2+ | Mail that wants nothing, up to six. |
| 3+ | Something to buy first; the order's number and total are on its confirmation page. |
| 6+ | Browser's harder shops, climbing its ladder from its rung 3. |
| 9+ | The category is no longer said in the request but in a policy mail from Accounts, by department. |
| 12+ | A request followed by a **change of plan** that scraps it and asks for something else. |
| 15+ | Two errands from different people; three from 21. |

Clicks count, a keypad press or a typed digit included; moving and
scrolling are free. Par is the fewest clicks the round could take plus
a share of what a thorough worker spends -- every mail read, every
product looked at -- and of a margin for slips: all of it at rung one,
under a third by rung twenty, a twentieth by thirty. Fifteen agent
ports, Browser's: move the pointer by 80, 20 or 5 units in four
directions, click, scroll up, scroll down. Turn-based, so it takes the
think clock.

#### Spreadsheet

A table of orders (id, item, category, quantity, price, total) and a
question above it: *what is the total of everything in Garden?*, *which
row is the largest?*, *which row's total is wrong?* The tools are on
the screen — filter chips by category, sort by clicking a column header
(twice to turn it round), sum buttons that put the visible rows' sum,
count and largest in the status bar — and the answer goes in from a
keypad and **Submit**. Right, in no more clicks than par, passes.

| Rung | Questions | Rows |
|---|---|---|
| 1–3 | Look a row up | 8–12 |
| 4–6 | Or find the largest | 20 |
| 7–9 | Sum a category | 24 |
| 10–12 | Count one | 30 |
| 13–15 | Find the row whose total is wrong | 30 |
| 16–19 | Any of those | 40 |
| 20+ | Sums, counts, wrong rows, and the corrected total | 60 |

Par is the fewest clicks with a little slack, and the slack shrinks
from 40% to 10% up the ladder. The tools only help the player who knows
which one the question needs: scrolling 60 rows and adding up in your
head is correct and over par.

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

#### Out of Sight as an environment

`nwenv.OutOfSightEnv` is the same `reset → observe → act → advance`
boundary over the Out of Sight task. The n-back environment watches a
game it does not control and has to work out where one trial ends; this
one is the other way round. The task is a continuous animation, so the
driver owns its clock outright and **one step is one rendered tick**.
Nothing moves between steps and two runs under the same seed produce the
same frames byte for byte.

```python
from nwenv import OutOfSightEnv, verify_sight_outcome
env = OutOfSightEnv(seed=1, dots=10, targets=3, blinds=4, frame_hz=60)
obs = env.reset(1)                      # RGBA + frame_seq + timestamp
receipt = env.act(1)                    # one of two opaque ports
obs, events, done = env.step()
env.close()
```

- A **trial is one question**: the window opens on the tick a dot is
  ringed and closes when the ring resolves. Exactly one action may be
  finalized inside it, and it gets a receipt. Pressing both ports or
  neither is not an answer.
- The outcome is `+1` or `-1`, read off the ring's colour in the frame —
  pixels only, never the task's own verdict — so a third party holding
  the archive and the ledger can re-derive it. `verify_sight_outcome`
  applies exactly the rules `verify_public_outcome` does and fails
  closed the same way; only how the scalar is read differs, which is
  now an argument to the shared verifier.
- A question the learner never answers still resolves, and resolves
  as `-1`. Silence is an answer here, because the ring runs out.
- The dials (`dots`, `targets`, `speed`, `blinds`, `blind_width`,
  `cross_ms`, `probes`, `rounds`) default to the values in the source,
  **not** to the player's `config.ini`, so a run under a given seed
  means the same thing on two machines. `adaptive` is off by default:
  a curriculum that moves under the learner is the runtime's business.
- `frame_hz` is what the task is clocked at, not a wall-clock rate. The
  task's seconds stay the task's seconds; a lower rate is simply a
  coarser look at the same motion, which is the observation-rate axis
  the task is hardest along. Ten is the floor — below it a tick would
  outrun how far the task will move in one call, and the environment
  refuses rather than quietly drifting.

```
.venv/bin/python -m nwenv --sight
```

#### The rest of the workshop

Every task in the hub is reachable by the agent, on the same
`reset → observe → act → advance` boundary. `nwenv.catalog` is the list,
and `tests/test_env_catalog.py` fails the build if a task is added to the
hub without one:

```python
from nwenv import catalog
env = catalog.env_class('tower_of_hanoi')(seed=0, disks=4)
obs, events, done = env.step(2)         # one of three opaque ports
env.close()
```

Twenty-two of the forty-five are *declarations* rather than code — where
the task class lives, what one port calls, which phase takes input, which
phase means the trial is over, and what the difficulty knobs are called:

```python
class HanoiEnv(TaskEnv):
    task_class = ('neural_workshop.ui.hanoi', 'TowerOfHanoi')
    ports = 3
    clocked = False
    action = '_pick'
    open_phase = ('solving',)
    settled_phase = ('solved',)
    knobs = {'disks': 'start_disks', 'rounds': 'total_rounds'}
```

They carry **no deriver and no verifier**, because they paint the shared
verdict label and the boundary already knows how to read one. Nineteen
of them add a short method or two — a port that names an object rather than
an index, a port that is a moment rather than a symbol, a trial window the
task has no phase for, a coach gated on whether the boundary will actually
pay it. The four written before that existed still carry both, at about a
hundred lines apiece. Twenty-two and nineteen and four is forty-five, which
is the point of counting them.
`ADDING_A_TASK.md` is the whole contract.

Two things had to change across the workshop to make this work, and both
were latent defects rather than boundary plumbing:

- **Fifteen tasks read the wall clock directly**, so a stepped run either
  never advanced past a feedback window or advanced at a rate set by how
  fast the machine was. They now read `self.clock()`, which the boundary
  swaps for a virtual one; `tests/test_ui_clock.py` keeps it that way.
- **Nine tasks painted into the strip the outcome reader looks at.** Six
  of them not by using a verdict colour — by using any colour with two
  channels far apart, whose *anti-aliased edge* passes through the
  reader's window on its way to the background.
  `neural_workshop.ui.verdict.above_the_band` is now where that line
  lives, and `tests/check_band.py` sweeps every task through its own
  wrapper on every rung.

  The seventh was found later and is a different animal, worth its own
  sentence because it says something about the sweep. Reflex spawns its
  targets from a tenth of the way up the screen, which is inside the
  bottom quarter — and its targets are *photographs*, so whether a run
  painted anything the reader counted depended on which pictures it
  happened to draw. `check_band.py` reported it about one run in three
  and came up clean the rest of the time. **A sampling check that comes
  up clean is not evidence**; where the violation depends on content
  rather than on layout, the guard has to be a test of the geometry, and
  `tests/test_ui_attention.py` now holds every spawn's bottom edge above
  the band whatever picture is in it.

  The eighth and ninth are the two first-person screens, and between them
  they say the last thing worth saying about sweeps. **3D Sokoban** paints
  boxes in Okabe-Ito sky blue, `(86, 180, 233)`, which is not a verdict
  colour — but against the dark room's near-black ceiling its
  anti-aliased edge runs through `(69, 140, 180)`, which is the reader's
  positive pattern exactly. That one was caught before it shipped, by
  enumerating the palette instead of sampling it: what a first-person
  view can paint is a small closed set, so it is cheaper to check all of
  it than to draw some of it.

  **The 3D Maze** is the interesting one. Its map draws doors and keys in
  `KEY_COLORS`, one of which is vermillion `(213, 94, 0)` — the reader's
  *negative* pattern outright, no edge required — and three more of which
  fade through the window on their way to the background. Whether any of
  it landed in the band turned on neither the deal nor the content but on
  the **shape of the window**: the map letterboxes its grid inside its
  panel, so on a tall window a 37-row maze is width-bound and sits well
  clear of the bottom, while on a wide one it is height-bound and the last
  row lands on the panel's floor. Measured with one seed throughout,
  1824x1368 is clear at every rung — and that is the size the tests and
  `check_band.py` run at. 1920x1080 puts a rung-fifteen door at y=533
  against a ceiling of 540; 2560x1080 puts a rung-*eight* door 95 pixels
  inside it. No number of extra deals would have found that.

  The same screen carried a second one, which no sweep could have found
  either. The pips showing which keys you are carrying are `KEY_COLORS`
  too, and they hung a couple of pip-widths *below* the stage — around
  y=143 on a 1920x1080 window, on every rung with a door. What hid it is
  that the coloured half only shows for a key already *held*, and nothing
  that swept it was carrying one. Both are fixed by `above_the_band` and
  by not drawing outside your own rectangle, and
  `tests/test_youarehere.py` now holds the stage above the band across
  five window shapes and holds the pips inside the view with the keys in
  hand.

Random play is paid on twenty-two of the twenty-seven overlays. The other
five — Sudoku, Jigsaw, Concentration and the two mazes — have no
accidental solutions, and are tested by driving them with a policy that
knows the answer through the same ports a learner would use. 3D Sokoban
is not among them, and the reason is worth knowing: random play never
*finishes* a warehouse either, but it very readily shoves a box
somewhere nothing brings it back from, and the screen calls that and
pays it.

```
cd tests && PYTHONPATH=.. ../.venv/bin/python drive_env.py --all 1500
```

One environment at a time: these bind shared-memory segments, and two
workshop instances at once risk a name collision.

#### The think clock: making thinking cost something

A turn-based task waits for ever. The boundary's clock moves on every
step, but nothing reads it as a cost, so a learner that ponders for a
thousand steps is paid what one that answers in ten is — and choosing
*how long to think*, the skill an agent that has to act in real time
needs most, cannot be measured on any of them. The think clock puts a
price on it without changing a single task:

```python
env = catalog.env_class('sokoban')(seed=0, think_seconds=2.0,
                                   refill_seconds=0.5)
```

The learner holds a bank of `think_seconds`. It drains at the
boundary's frame rate while a trial is open — whether the learner acts
or not, because a step with no port *is* thinking — and each new trial
pays `refill_seconds` back into it, up to the full bank. If it runs dry
the trial is forfeit: the boundary paints the standard red verdict over
the task, shows it for one frame, and deals the next trial. A forfeit is
read and verified by the same reader as any other loss.

The two numbers cover the cases worth having:

| `refill_seconds` | What it is |
| --- | --- |
| omitted, or equal to the bank | a deadline per trial |
| `0` | one bank for the whole run: time spent on a hard trial is taken from every later one |
| anything between | a chess clock with an increment: what an easy trial leaves unused pays for a hard one |

The last is "pay for what you use" written as a rule: the policy that
does best answers easy trials at once and spends the savings where
thinking pays. Seconds are the boundary's, not the wall's — at the
default `frame_hz=60` a second is sixty steps.

The bank is drawn as a slate bar along the top edge, so the learner can
see what it has left, and the verdict reader never looks there.
`env.think_left` gives the same number to a caller, and `env.forfeits`
counts the trials lost to it.

It applies to the nineteen turn-based tasks that declare when a trial
is over — the puzzles, the word games, the board positions, Sokoban,
Hanoi, the Maze — and is refused, with the reason, on the rest. A
clocked task already does not wait: its world moves while the learner
thinks, and charging for that time again would charge twice. The 3D Maze
deals its own trials, so the boundary has nothing to forfeit.

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
