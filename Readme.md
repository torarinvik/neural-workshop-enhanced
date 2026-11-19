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

#### Kerbside

A street you cannot see. Cars pass from left and right, each heard as
it comes: louder as it nears, higher in pitch as it approaches and
lower once past, in the ear of the side it is on. **Up** walks
forward, **Down** steps back; the lines between lanes are safe to
stand on. Cross to the far kerb without being struck.

| Rung | What it adds |
|---|---|
| 1–3 | One lane, slow cars, long gaps |
| 4–6 | Two lanes, faster |
| 7–9 | Quiet electric cars |
| 10–12 | Vans that muffle the cars behind them |
| 13+ | More lanes, denser and faster traffic, wind over everything |

Pass: the far kerb, unhurt. Every street is dealt only when a player
who waits a fixed time and then walks cannot cross it, so the ears
have to do the work.

#### Steadicam

Keep a moving subject inside the framing box. **Arrows** (or WASD)
pan and tilt, **Q / E** or the wheel zoom. The subject walks, stops and turns; the take counts the
share of time it was framed.

| Rung | What it adds |
|---|---|
| 1–3 | One walker, a wide box |
| 4–6 | A size rule: the subject must fill the box properly |
| 7–9 | A heavy head that keeps turning after you let go |
| 10–12 | Lead room: leave space on the side the subject faces |
| 13+ | Several people and cues to switch to another; faster walkers |

Pass: framed for the share the rung asks. Holding any one control, or
none, fails every dealt take.

#### Free Kick

The ball on the grass, the goal ahead with a ring lit in its mouth.
Set the kick -- **Left / Right** aim, **Up / Down** height, **A / D**
curl, **W / S** power -- and **Space** kicks. The air slows the ball,
spin bends it, wind carries it; it must cross the line inside the ring,
past the wall and out of the keeper's reach. One kick a round.

| Rung | What it adds |
|---|---|
| 1–2 | The flight is drawn before kicking (rung 1 and 2); a big ring |
| 3 | No drawn flight |
| 4–6 | A wall and a keeper |
| 7–9 | Wind, shown by a flag |
| 10–12 | Kicks from off to the side; the wall jumps |
| 13+ | The ring shrinks every rung, the wind strengthens, the keeper quickens |

Pass: in the ring. The reference finds a scoring kick by solving the
flight and sets the dials to it; the kick as first set never scores.

#### Glove

A pitcher throws ball after ball; move the glove -- mouse or arrows --
to meet each one at the plate. The camera will not hold still: it cuts
without warning between seven angles (behind the catcher, behind the
pitcher, both sides, down low, overhead, high to one side), and the
glove always moves the way the screen shows it, so every cut turns the
controls with the picture.

| Rung | What it adds |
|---|---|
| 1 | One camera; slow lobs; a big glove; one miss allowed |
| 2–3 | A new angle for each pitch, never during one |
| 4–6 | Cuts in flight, about once a second |
| 7–9 | Curveballs that bend late |
| 10–12 | Overhead and ground-level views |
| 13+ | Cuts ever more often, faster pitches, a smaller glove |

Pass: every pitch caught, bar the misses allowed.

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

#### By Ear

A short melody plays on a keyboard; play it back. Click the keys, or
type them on the home row laid out like a piano: A W S E D F T G Y H U
J K from C up to the next C.

| Rung | What it adds |
|---|---|
| 1–3 | Two or three notes, close together |
| 4–9 | Longer melodies, wider steps |
| 10–12 | Play it back starting from the lit key |
| 13+ | Notes in pairs, played together |

Pass: every note right and in order. A wrong note ends the round.

#### Piano Tuner

A reference string and one to tune, heard together. Turn the pin --
**Up / Down**, slowly with **Shift** -- until the beating between them
stops, then press **Enter**.

| Rung | What it adds |
|---|---|
| 1–3 | Tune to the same note, a wide allowance |
| 4–6 | Tune to an interval: an octave, a fifth |
| 7–12 | Stiff strings, whose overtones sit sharp, so the beats lie |
| 13+ | The allowance narrows every rung |

Pass: within the allowance when done is called. The pin's position on
screen says nothing; only the sound does.

#### Cricket Hunt

A dark room and crickets chirping somewhere in it. Walk and turn
(**WASD**), look up and down, and grab (**Space**) when one is within
reach in front of you. The chirp comes from its side, brighter in front
than behind and louder when faced.

| Rung | What it adds |
|---|---|
| 1–3 | One cricket in a small room |
| 4–6 | Two, a bigger room |
| 7–9 | A hum under the chirps |
| 10+ | Crickets that hop when you come near |

Pass: every cricket caught with at most three misses.

#### Claw Machine

A glass cabinet from the front, prizes on its floor, a claw on a cable.
Move the trolley left and right, in and out (**arrows**; **Up** is
in), and drop with **Space**. Left and right
are easy from the front; how far in is the whole difficulty.

| Rung | What it adds |
|---|---|
| 1 | A side view as well, and the claw's shadow |
| 2–3 | The shadow only |
| 4–6 | Neither: depth only from perspective |
| 7–9 | The claw swings when the trolley moves |
| 10–12 | A low camera and prizes of different sizes |
| 13+ | A moving floor; a smaller allowance every rung |

Pass: the claw closes on the gold prize.

#### Symmetric?

Is the pattern its own mirror image? Patterns that are not are, past
the first rungs, symmetric ones with a few cells spoilt -- down to one,
swapped rather than recoloured so the colour counts give nothing away.
Cells are drawn as squares, dots or tiles, in several palettes.

| Rung | What it adds |
|---|---|
| 1–3 | Folded down the middle; the others plainly lopsided |
| 4–6 | Across as well; three cells off |
| 7–9 | Diagonals too; two cells off |
| 10–12 | Bigger grids; one cell off |
| 13–15 | Or: the same turned upside down? |
| 16+ | Grids to 24, four colours, a swapped cell |

#### Tangram

A silhouette and a few sets of pieces: which set covers it, every piece
turned or flipped as needed, with no gaps or overlaps? The other sets
have the same area. Pieces are squares joined edge to edge, so the
answer is exact.

| Rung | What it adds |
|---|---|
| 1–3 | Two small pieces; three sets |
| 4–6 | Three pieces |
| 7–9 | Three or four; near-miss pieces |
| 10–12 | Four pieces; two wrong ones keeping the area; four sets |
| 13+ | A piece more every three rungs, to eight |

#### Will It Fit?

A flat piece and a hole in a board. The piece may be turned on the
table but not turned over. Does it go in? Higher up: which of several
holes does it go into?

| Rung | What it adds |
|---|---|
| 1–3 | Small pieces the way up the hole is |
| 4–6 | The piece shown turned |
| 7–9 | Mirror-image holes, which would need turning over |
| 10–12 | Three holes |
| 13+ | Four holes, bigger pieces, wrong holes a square short |

#### Holds More

Containers seen side on, each round about its middle: which holds the
most? Higher up, water in one is poured into another: which mark does
it reach? Volumes are exact; tall and thin against short and wide is
the old trap.

| Rung | What it adds |
|---|---|
| 1–3 | Two plain jars, one bigger every way |
| 4–6 | Tall and thin against short and wide |
| 7–9 | Cones, bowls, vases |
| 10–12 | Three containers |
| 13–15 | Pouring |
| 16+ | The margin narrows from a fifth to a twentieth; four containers |

#### More or Less

Two clouds of dots flash and are covered: which had more? Too quick to
count past the first rungs, and the more numerous dots are the smaller,
so the ink is no guide. From rung 7 some trials are Piaget's
conservation question: two matched columns, then one spreads out while
you watch -- has either got more, or are they the same?

| Rung | What it adds |
|---|---|
| 1–3 | Two to one; three seconds -- countable |
| 4–6 | Three to two; a second and a half; ink controlled |
| 7–9 | Four to three; a second; conservation columns |
| 10–12 | One mixed cloud in two colours |
| 13+ | The ratio closes toward 1.06; the flash toward a quarter second |

#### Spot the Change

Two pictures flicker, one thing different. Without a blank between them
the change jumps out; with one, it has to be found figure by figure
(change blindness). Click the part of the picture it is in.

| Rung | What it adds |
|---|---|
| 1–3 | Four parts; a figure vanishes; no blank |
| 4–6 | Nine parts, a blank, colour and shape changes |
| 7–9 | Any change: moved, grown, turned |
| 10–12 | Sixteen parts, twenty figures |
| 13+ | Up to forty figures, shorter pictures, less time |

#### Find It

The target is shown; a crowd flashes and is covered. Was it there? A
target alone in its colour pops out; one that shares a colour with some
and a shape with others must be looked for; one that differs only in
which way it points is slowest of all.

| Rung | What it adds |
|---|---|
| 1–3 | Six figures; the target alone in its colour; four seconds |
| 4–6 | Twelve; colour-and-shape search |
| 7–9 | Eighteen; a second and a half |
| 10–12 | The target differs only in how it is turned |
| 13+ | Up to sixty, a shorter look, turns a step apart |

#### Longer or Sooner?

Which lasted longer, the first or the second? Which came first, the
left or the right? Asked of lights and of tones (the tones in the left
and right ear). Higher up the shorter one is the brighter, bigger or
higher -- which makes it seem longer -- and the later onset the
stronger.

| Rung | What it adds |
|---|---|
| 1–3 | Which lasted longer, two to one |
| 4–6 | Three to two; which came first, a third of a second apart |
| 7–9 | Thirteen to ten; a twelfth of a second; the shorter one stronger |
| 10–12 | Six to five; a twentieth |
| 13+ | Toward 1.03 and eight thousandths of a second |

#### Behind the Screen

Balls roll in and go behind a screen; some roll on out, some come back.
How many are behind it now?

| Rung | What it adds |
|---|---|
| 1–3 | One to three go behind and stay |
| 4–6 | Some leave out the far side |
| 7–9 | Two colours; the question is about one |
| 10–12 | Two screens, balls crossing between them |
| 13+ | More balls, faster, more of them moving at once |

#### Same or Different?

Two things: the same or different in one named respect, while others
may differ -- the same relation in seven guises: **shape**, **count**,
**orientation**, **colour**, **size**, **pitch** and **rhythm** (the
last two heard). **S** / **D** answer. The ladder is the same in every
guise: the difference shrinks every rung toward the limits of
perception, other respects differ from rung 4, and from rung 10 the two
are shown one after the other. ``SAMEDIFF_GUISE`` keeps a run to one
guise, so whether "same" learned in one carries to another can be
tested.

#### Live Claw Machine

An arcade crane simulated as the thing itself (MuJoCo), drawn in real
3D. A gantry carries a winch about the top of a glass cabinet; from it
hangs a rope, and on the rope a claw of three hinged, sprung fingers,
which swings when the gantry starts and stops and comes to rest on
whatever is under it. The prizes -- balls, eggs, boxes, pucks -- are
loose bodies heaped in the pit; they lean on one another, get pushed
aside by a finger that lands on them, and slide out of a grip that is
not square on them. Arrows or **WASD** drive the gantry, **Space** is
the button, **V** walks round to the side window.

One play is a play on the machine: steer while the time runs, press
(or run out of time), and the machine does the rest -- lets the claw
down until the rope goes slack, closes it, winds it up, drives home
over the chute and opens it. Whatever falls down the chute is won. How
hard the fingers close, and how much of that is kept once the claw is
up, are the operator's settings, as on a real machine.

| Rung | What it adds |
|---|---|
| 1–3 | One ball in an empty pit; a firm grip that holds; a rope that hardly swings |
| 4–6 | Three prizes of different shapes |
| 7–9 | Six prizes; the grip slackens to 70% once the claw is up |
| 10–12 | A heap of ten; a rope that swings freely; 30 seconds |
| 13–15 | Only the gold prize counts |
| 16+ | A weaker grip, heavier prizes, more of them, less time |

A pilot that steers dead over the best-placed prize and waits for the
claw to hang still wins about 19 plays in 20 on rungs 1-6, 17 on 7-9,
16 on 10-12, 14 where it must be the gold one, about one in three at
rung 16 and one in ten by rung 30: the rest are the machine's. Doing nothing, and pressing at random, win
nothing: the claw starts over the chute, where there is no prize.

#### The Artist

A picture on the left, a blank canvas on the right, and a plain paint
box: pencil, brush, line, box, filled block, filled round, fill, a
colour picker, four widths, undo and clear. Copy the picture as closely
as you can, then press **Done**. Drag on the canvas to draw; **1**-**8**
choose a tool, **[** and **]** the width, **Z** undoes, **K** checks how
alike the two are without ending the trial, **Enter** is Done. A right
click on the picture takes the colour there.

How alike is measured, pixel by pixel, against the best that one flat
colour could do: ``alike = 1 - error(canvas) / error(best flat
colour)``. A blank canvas, or a canvas filled with any one colour,
scores nought or less; a perfect copy scores 1. Below rung 13 both are
blurred a little and the canvas is tried a pixel over in every
direction, so a slip of a pixel costs little or nothing.

| Rung | The picture | Passes at |
|---|---|---|
| 1–3 | 8 × 8: one filled block in one of three colours | 25% |
| 4–6 | 12 × 12: two shapes | 55% |
| 7–9 | 16 × 16: three shapes -- blocks, rounds, lines | 60% |
| 10–12 | 24 × 24: four shapes, outlines and brush strokes too | 65% |
| 13–15 | 32 × 32: five or six shapes over one another | 70% |
| 16–18 | 48 × 48: a landscape in twelve flat colours | 60% |
| 19–24 | 64 × 64: a photograph in sixteen colours | 60% |
| 25–29 | 96 × 96: a photograph in thirty-two colours | 70% |
| 30+ | 128 × 128: a photograph in full colour | 80%, rising a point a rung to 95% |

The photographs come from the downloaded libraries (the jigsaw
photographs, else the memory games'); where there are none the upper
rungs paint a shaded landscape of their own, never the same twice. An
agent draws through fifteen ports -- a cursor, a pen that goes down
and up, the next tool, colour and width, pick, undo, done -- and a
reference pilot that knows how each picture of shapes was made passes
those rungs through the same ports.

#### Piano Man

A melody plays; then play it back on the keyboard, note for note. Click
the keys, or use the computer's own: **Z X C V B N M** are the white
keys of the lower octave with **S D G H J** its black ones, **Q W E R T
Y U** and **2 3 5 6 7** the upper octave, **I** the top C. **Space**
plays the melody again, where that is allowed, and only before your
first note. One wrong key ends the trial; the rhythm is not judged,
only the notes and their order. Once it is judged the melody's keys
are numbered and the scale is named.

Every melody is drawn from a real scale -- major and minor pentatonic,
major, natural and harmonic minor, blues, Dorian, Mixolydian -- and
moves the way tunes do: mostly by step, a leap now and then, no
trills, and from five notes on it comes home to the keynote.

| Rung | The melody | The help |
|---|---|---|
| 1–3 | 2 notes, C major pentatonic, one octave | Each key lights as it sounds; first note marked; the scale's keys tinted; heard again twice |
| 4–6 | 3 notes, pentatonic or major | The keys no longer light |
| 7–9 | 4 notes, minor scales too, in any key | |
| 10–12 | 5 notes on two octaves, uneven rhythm | The scale is no longer tinted |
| 13–15 | 6 notes; blues and the modes; other instruments | Heard again once |
| 16+ | 7 notes and one more every two rungs, to 24; quicker | Only the keynote is marked; from rung 22 heard once only |

The melody reaches an agent only as sound (and, on rungs 1-3, as the
lit keys); it answers through twenty-six ports, one a key and the last
to hear it again, and hears its own keys as it plays them.

#### Thirty judgements by eye and ear

The thirty tasks from *Brighter* to *Flash and Beep* are each one quick
judgement, asked again and again: a run is twenty of them, each judged
on its own, and at the first rung a guess is right a half or a third of
the time. Every deal draws its own look, and the right answer's place
comes from its own stream. Each task's model describes its picture as
a list of plain shapes (``neural_workshop/scenes.py``), so what was
shown can be checked without a window, and each has a reference that
answers from the picture or the sound itself -- measuring the areas,
finding the chain, reading the pile -- which must agree with every
deal. The six heard tasks reach the agent only as sound.

#### Brighter

Grey patches, each on its own ground: which patch is the lighter? A grey looks lighter on a dark ground and darker on a light one, so from rung 4 the grounds are dealt to argue against the truth.

| Rung | What it adds |
|---|---|
| 1–3 | Two patches on like grounds, a fifth apart |
| 4–6 | Grounds that mislead |
| 7–9 | Closer greys on graded grounds |
| 10–12 | Patches of different sizes |
| 13+ | Three patches, four from 19; the step narrowing toward one in a hundred |

#### Colour Match

A sample and a row of swatches; exactly one is the sample's colour, the others a step off in hue, strength or lightness.

| Rung | What it adds |
|---|---|
| 1–3 | Three swatches, far off |
| 4–6 | Four, each on a ground of its own colour |
| 7–9 | Closer |
| 10–12 | Different shapes and sizes |
| 13+ | Five swatches, six from 19; ever closer |

#### Longer Line

Which line is the longest? Arrowheads make a line look shorter and tails longer (Müller-Lyer); between converging rails the line nearer the narrow end looks longer (Ponzo). The fins are dealt against the truth.

| Rung | What it adds |
|---|---|
| 1–3 | Two level lines, one half as long again |
| 4–6 | Any angle; a fifth longer |
| 7–9 | Fins that mislead; an eighth |
| 10–12 | Rails that mislead; a twelfth |
| 13+ | Three lines, four from 19; toward one part in fifty |

#### Steeper

Two slopes: which is nearer upright?

| Rung | What it adds |
|---|---|
| 1–3 | 25 degrees apart |
| 4–6 | 12; different lengths |
| 7–9 | 6; one climbs each way |
| 10–12 | 4; each in a tilted frame |
| 13+ | Narrowing toward half a degree |

#### Bigger Area

Which shape covers the most paper? A long shape looks bigger than a compact one of the same area, so the smaller shapes are the longer ones.

| Rung | What it adds |
|---|---|
| 1–3 | Two like shapes, one bigger by three fifths |
| 4–6 | Compact against long; by a third |
| 7–9 | Free outlines; by a fifth |
| 10–12 | Turned any way; by an eighth |
| 13+ | Three shapes, four from 19; toward one part in thirty |

#### Midpoint

A line with numbered marks across it: which is exactly halfway?

| Rung | What it adds |
|---|---|
| 1–3 | Three marks, an eighth of the line apart |
| 4–6 | Any angle; a twelfth |
| 7–9 | Fins at the ends that make one half look longer |
| 10–12 | No line, only its ends; four marks |
| 13+ | Five marks, toward one part in a hundred |

#### Parallel?

Two long lines: parallel or not quite? From rung 7 short hatches cross them, slanted to hide a real tilt or to fake one (Zöllner).

| Rung | What it adds |
|---|---|
| 1–3 | Level lines; 8 degrees off or parallel |
| 4–6 | Any angle; 4 degrees |
| 7–9 | Hatching; 2.5 |
| 10–12 | 1.5 |
| 13+ | Toward a quarter of a degree |

#### Hidden Figure

A small figure of a few strokes and some busier drawings; exactly one contains it, the same way up and the same size. A deal is kept only when a search of every position finds it in one drawing and no other.

| Rung | What it adds |
|---|---|
| 1–3 | Three strokes among three more; two drawings |
| 4–6 | Four among six; three drawings |
| 7–9 | Among nine; the wrong drawings miss it by one stroke |
| 10–12 | Five among twelve on a bigger lattice; four drawings |
| 13+ | More strokes around it; six-stroke figures from 16 |

#### Contour

A field of short strokes pointing every way; in one part some lie end to end along a smooth path. Which part? The path is kept only when it is the longest chain a chain-finder can find anywhere in the field.

| Rung | What it adds |
|---|---|
| 1–3 | Left or right; ten strokes dead in line |
| 4–6 | Nine, each a little off true |
| 7–9 | Four quarters; eight strokes |
| 10–12 | More off true, a tighter curve |
| 13+ | Seven strokes, up to fifteen degrees off |

#### Same Line?

Lines cross the page through a tangle, all in one ink. Are the two dots on the same line? Higher up: which end does the marked line come out at?

| Rung | What it adds |
|---|---|
| 1–3 | Three lines, two stretches; same or not |
| 4–6 | Four lines, three stretches |
| 7–9 | Which end? |
| 10–12 | Five lines, four stretches |
| 13+ | Six lines; a longer tangle every three rungs |

#### Texture Edge

A page of small strokes that all lean one way, except in one square patch. No outline is drawn. Which part of the page is it in? From rung 7 the texture is sometimes crosses among corners -- the same two strokes, arranged differently.

| Rung | What it adds |
|---|---|
| 1–3 | Left or right; a big patch at right angles |
| 4–6 | Four quarters; 60 degrees; untidy strokes |
| 7–9 | 45 degrees, a smaller patch; figures too |
| 10–12 | 30 degrees |
| 13+ | A patch of four strokes, toward 10 degrees |

#### What Is Behind

A shape with a screen across it, and whole shapes below: exactly one agrees with the parts that show.

| Rung | What it adds |
|---|---|
| 1–3 | A third hidden; two shapes, quite unlike |
| 4–6 | Two fifths hidden; three shapes |
| 7–9 | Half hidden behind two screens; closer shapes |
| 10–12 | Four shapes |
| 13+ | The whole shapes turned round, and ever closer |

#### Top Card

Numbered cards dropped one on another. Where one card's edge runs unbroken across another it lies over it, and the whole order can be read. A deal is kept only when what can be seen settles the order.

| Rung | What it adds |
|---|---|
| 1–3 | Three cards: which is on top? |
| 4–6 | Four cards |
| 7–9 | The bottom card too |
| 10–12 | Five cards; second from the top |
| 13+ | Six cards of one colour, seven from 19; third from the top |

#### Bump or Dent

Round marks shaded from one side to the other. A bump is lit on the side facing the lamp and a dent on the side away, so the same picture upside down changes from one to the other.

| Rung | What it adds |
|---|---|
| 1–3 | One mark; the lamp above or below |
| 4–6 | The lamp anywhere round |
| 7–9 | No lamp: a mark labelled as a bump shows the light |
| 10–12 | Four to six marks and a lamp: how many are bumps? |
| 13+ | Counting from a labelled bump; more marks, fainter shading |

#### Far Size

Posts on flat ground running to the horizon: which is really the tallest? A post whose top just reaches the horizon is as tall as the eye is high, wherever it stands.

| Rung | What it adds |
|---|---|
| 1–3 | Two posts, one half as tall again, and it looks it |
| 4–6 | The taller post is farther, and drawn smaller |
| 7–9 | Different thicknesses; a quarter taller |
| 10–12 | Three posts; an eighth |
| 13+ | Four posts from 16; no ground lines from 19 |

#### Reflection

A figure and a mirror: which figure is what the mirror shows? The others are the figure itself, turned half round, or mirrored the other way.

| Rung | What it adds |
|---|---|
| 1–3 | An upright mirror; two figures |
| 4–6 | A level mirror; three |
| 7–9 | A slanted mirror; four |
| 10–12 | A mirror at any angle |
| 13+ | One of the others is a reflection with a stroke wrong |

#### Gaze

A face and numbered things around it. Each eye points at the thing for itself, so the two converge on it. Which thing?

| Rung | What it adds |
|---|---|
| 1–3 | Three things, 60 degrees apart or more |
| 4–6 | Four, 40 degrees |
| 7–9 | Five, 25 degrees |
| 10–12 | Six; one lies on the same line as the thing looked at, nearer or farther |
| 13+ | Eight, toward 6 degrees apart |

#### Which Way

A field of short-lived dots; some all drift one way, the rest every way. Which way is the drift?

| Rung | What it adds |
|---|---|
| 1–3 | Left or right; nine in ten together |
| 4–6 | Half |
| 7–9 | Four ways; a third |
| 10–12 | A quarter; shorter lives |
| 13+ | Eight ways; toward one in sixteen |

#### Faster

Two windows of moving dots: in which are they faster?

| Rung | What it adds |
|---|---|
| 1–3 | One dot each; three fifths faster |
| 4–6 | Three dots; the faster ones bigger; a third |
| 7–9 | Eight dots moving different ways; a fifth |
| 10–12 | An eighth |
| 13+ | One window after the other; toward one part in thirty |

#### Walker

Eleven lights on the joints of someone walking on the spot. Which way does the figure face? Knees lead and elbows trail.

| Rung | What it adds |
|---|---|
| 1–3 | The limbs are drawn in |
| 4–6 | Lights only |
| 7–9 | Eight stray lights that move as joints do; a smaller walker |
| 10–12 | Sixteen |
| 13+ | More every rung, to sixty |

#### Collision Course

Two balls roll toward where their ways cross and are covered before they get there. Will they hit?

| Rung | What it adds |
|---|---|
| 1–3 | Their ways are drawn; square on or a miss by four widths |
| 4–6 | No ways drawn |
| 7–9 | Unlike speeds; a miss by two and a half |
| 10–12 | Covered sooner; nearer misses, hits that only clip |
| 13+ | Sooner still; a miss by one and a fifth |

#### Heading

Dots stream outward from the point being headed for. Which numbered mark is it?

| Rung | What it adds |
|---|---|
| 1–3 | Two marks, far apart |
| 4–6 | Three |
| 7–9 | Four; one dot in five strays |
| 10–12 | Five; three in ten; short-lived dots |
| 13+ | Seven marks closing up; more strays |

#### Number Line

A line with a number at each end and a mark along it: what number is at the mark? From rung 7 also the other way: which mark is at a given number.

| Rung | What it adds |
|---|---|
| 1–3 | Nought to a hundred; three answers, 30 apart |
| 4–6 | Four answers, 15 apart |
| 7–9 | Any ends; a tenth of the line apart |
| 10–12 | 7 parts in a hundred |
| 13+ | Five answers, six from 16; toward 1.5 in a hundred |

#### What Share

A bar, a round or a scatter of dots, part coloured: what share is that?

| Rung | What it adds |
|---|---|
| 1–3 | A bar or a round; three answers a quarter apart |
| 4–6 | Four answers, 15 apart; the round starts anywhere |
| 7–9 | 10 apart; the coloured part in two pieces |
| 10–12 | 7 apart; scatters of dots too |
| 13+ | Five answers, six from 16; toward 3 in a hundred |

#### Louder

Tones in turn: which was the loudest? Heard, not seen; the whole trial is played now quietly, now loudly.

| Rung | What it adds |
|---|---|
| 1–3 | Two tones, one twice as strong |
| 4–6 | Half as strong again; the quieter one higher |
| 7–9 | A quarter; the quieter one longer |
| 10–12 | Three tones; an eighth |
| 13+ | Toward one part in thirty |

#### Which Ear

A tone between the ears: left or right? Higher up, two tones: was the second left or right of the first?

| Rung | What it adds |
|---|---|
| 1–3 | Far to one side |
| 4–6 | Halfway |
| 7–9 | Two tones, a quarter of the way apart |
| 10–12 | An eighth; different pitches |
| 13+ | Toward one part in forty |

#### Up or Down

Two tones: did it go up or down? From rung 10 three tones: which was highest?

| Rung | What it adds |
|---|---|
| 1–3 | A fifth apart |
| 4–6 | A third; the lower tone brighter |
| 7–9 | A semitone |
| 10–12 | The highest of three |
| 13+ | Toward a twentieth of a semitone |

#### How Many Beeps

A run of beeps: how many?

| Rung | What it adds |
|---|---|
| 1–3 | One to three, slow |
| 4–6 | Up to five, quicker |
| 7–9 | Up to six, unevenly spaced |
| 10–12 | Up to seven, on different notes |
| 13+ | Up to nine, among low knocks that do not count |

#### Same Instrument

Two notes: one instrument or two? From rung 10 three notes: which was on the other instrument?

| Rung | What it adds |
|---|---|
| 1–3 | The same note; instruments of different families |
| 4–6 | Notes up to a third apart |
| 7–9 | Sometimes instruments of one family |
| 10–12 | The odd one of three |
| 13+ | Always one family; an octave apart; shorter notes |

#### Flash and Beep

A lamp flashes and a beep sounds: which came first? Higher up the lamp flashes a few times among a different number of beeps: how many flashes?

| Rung | What it adds |
|---|---|
| 1–3 | 0.4 s apart |
| 4–6 | 0.14 s |
| 7–9 | 0.07 s; counting one or two flashes |
| 10–12 | 0.04 s; up to three |
| 13+ | Up to four, quicker; toward 0.01 s |

### Accuracy and order

Getting it exactly right: rules applied to the letter, and things kept
in their places.

#### Desk Jockey

A rulebook on the left, a tray of forms on the right, and the form on
top of the tray in the middle with whatever is attached to it -- an
ID card, receipts. Do the one right thing with each form: **approve**
it, **send it back** for something missing, **forward** it to another
office, **reject** it under the rule that says so, or **hold** it
until another form has been dealt with. Click the action or press its
key. Everything needed is on the desk; every shift has a new book.

The rules are tried in their order of precedence and the first that
applies decides; if none does, the form is approved. So a form that
breaks two rules is rejected under the one that comes first, and
rejecting it under the other is wrong.

| Rung | The book | The tray |
|---|---|---|
| 1–3 | One rule: an unsigned form is sent back | 3 forms |
| 4–6 | Three rules; rejecting under the right one | 4 |
| 7–9 | Four rules; ID cards and receipts to check against the form -- the name, the day it runs out, whether the receipts add up | 5 |
| 10–12 | Five rules; exceptions ("unless it is countersigned"); forwarding | 5 |
| 13–15 | The order of precedence is no longer the order the rules are written in | 6, one slip allowed |
| 16–18 | Six rules; a memo arrives that changes a rule for forms from a day on | 6 |
| 19–21 | Seven rules; a travel claim waits for the same person's leave request, which may be further down the tray | 7 |
| 22+ | Eight or nine rules, two memos, exceptions to exceptions | 8, rising to 12 |

A shift is dealt only if it shows what its rung is about: at least one
form is approved; where there are exceptions, a form the exception
saves; where the precedence is shuffled, a form that the written order
would decide the other way; where there is a memo, a form it changes;
where forms wait, one that has to be held. Following the book clears
every tray. Approving everything, or sending everything back, never
does; pressing actions at random clears about one three-form tray in
eight at rung 1 and next to none above.

### First steps

Tasks for a learner starting from nothing. A beginner pressing at random is paid on almost none of the multi-press tasks, so it has nothing to learn from. Each of these gives a first payment that is within reach and then asks for one small step more:

* rung 1 is paid by presses at random well inside twenty trials;
* each rung adds exactly one thing: one more press, one more frame of looking back, one more candidate;
* every trial is judged quickly: a wrong press ends it with a red verdict;
* layout, colours and positions change from trial to trial.

In what follows *n* is the rung. In the short walks a press that does not bring the goal nearer ends the trial.

The frame-by-frame memory families below (now and earlier, carried through, own presses, a cue far back, heard back) show a frame every half second and may be stepped one step a shown frame: their environments accept `frame_hz=2`, where every other clocked task keeps its floor of ten, and a trial driven that way is judged as it is at ten.

Several pairs are **twins**: the same rule in another look, with other colours, shapes, layout and port order. `nwenv.catalog.TWINS` records the pairs and `twin_of()` looks one up. The catalogue also marks a few tasks as held out (`nwenv.catalog.HELD_OUT`); they are not described here.

#### Short Maze

A small maze with the way out *n* steps from the walker. Four ports steer.

#### Short Tower

A tower of discs *n* moves from stacked on the marked peg. Six ports, one a peg-to-peg move.

#### Turned Tiles

A board on which *n* tiles are turned out of place, never more than half of them; a pattern tile shows how they should sit. One port a tile.

#### Short Push

A box-pushing room *n* presses from solved. Four ports steer.

#### Short Maze, Step by Step

A small maze with the way out *n* steps from the walker, for a learner paid by the press: built by a runtime, each right step is marked green as it is taken, as well as the finish. Built the plain way only the finish is paid.

#### Marker Walk, Shuffled

A marker on an open grid and a marked square *n* moves away. Each port moves the marker one way, and which way is dealt afresh for each run, so what a port does has to be found by pressing it.

#### Match Shapes

Two sets of *n* shapes side by side: the same, or different in one place?

#### Match Tiles

Two strips of *n* coloured tiles, one above the other: the same, or different in one place? The twin of the same-or-different rule in another look, with the two ports the other way round.

#### Odd Shape

A row of *n* + 2 shapes, one of them another shape: which?

#### Next Shape

A run of shapes repeating every *n* + 1: which of three cards comes next?

#### Next Tile

A column of pip tiles repeating every *n* + 1: which of three cards comes next?

#### In the Loop

An outline with *n* + 3 corners and a dot: inside or outside?

#### In the Pen

A fence round *n* + 3 squares of squared paper and a mark: outside or inside?

#### Shape Back

A shape a frame; then press the card for the shape that was showing *n* frames ago.

#### Hidden Cue

One of four squares lights, then nothing shows for *n* frames: which was it?

#### Sound Back

A tone a frame, low, middle or high, reaching the agent only as sound; then press for the tone *n* frames ago.

#### Changed Tile

Four tiles show, each a hue, and show again *n* frames later with one of them another hue: press the tile that changed.

#### Swapped Boxes

One of four boxes lights and goes out; then, *n* times, two boxes are joined and what they hold changes places: press the box the light is in now.

#### Which Rule?

Three cards, and one hidden rule for the whole run saying which to press ("the largest", "the red one"). The rule is one of two candidates at rung 1 and one more each rung; every press is judged at once, so wrong presses rule candidates out.

#### Now and earlier

Things show twice, *n* frames apart, and the answer is what is different the second time; neither showing alone says anything about it. Each comes in two looks, shapes on a grid with the cards in a row, and coloured beads round a ring with the cards in a column, numbered the other way round.

* **Which Moved?** and **Moved Bead**: four things, then the same four with one in another place: press the card of the one that moved.
* **Which Is New?** and **New Bead**: three things, then four in fresh places: press the card of the new one.
* **Which Is Gone?** and **Gone Bead**: four things, then three of them in fresh places: press the card of the one that went. The cards are the one that went and three never shown.
* **Traded Places** and **Traded Beads**: five things in a row, then the same row with two of them changed places and one of the two marked: press the place of the one it changed places with. Five ports.

From the second showing alone every answer is as likely as another. Keeping where one thing was earns one half on Which Moved? and three in five on Traded Places; keeping one old thing earns a third on Which Is New? and seven in sixteen on Which Is Gone?.

### Reasoning

The *Reasoning* category holds 39 tasks.

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

#### 3D Matrix

Matrix Reasoning with solid things. Each cell of a three-by-three
matrix holds a small construction -- blocks stacked on a table, a ball
or a cone on them, a small cube on the very top, a yellow ramp leaning
on one side, a blue ring round the foot -- drawn in 3D with light and
shadow from some viewpoint. The ninth cell is missing: click the
construction that completes the matrix, or press its number. Once it
is judged the missing cell is filled in and the rules are named.

Eight things can differ between cells: the ring, the small cube, the
ramp's side (right, front, left), the colour, what sits on top, the
block's shape (cube, drum, tub), how many blocks, and the viewpoint
(from the right, from the left, from above). Each follows one rule:

| Rule | What it means |
|---|---|
| The same everywhere | |
| Set by the row | One value a row |
| Set by the column | One value a column |
| Each once | Three values, each once in every row and column |
| In just one | There in the third cell of a row when it is in exactly one of the first two (the ring, the small cube) |

| Rung | Rules at work | In play | Answers |
|---|---|---|---|
| 1–3 | 1, by row or column | Ring, small cube, ramp, colour | 4 |
| 4–6 | 2, one by row and one by column | + what sits on top | 4 |
| 7–9 | 2, each-once too | + the block's shape | 6 |
| 10–12 | 3, in-just-one too | + how many blocks | 6 |
| 13–15 | 3 | + the viewpoint | 6 |
| 16–18 | 4 | everything | 8 |
| 19–24 | 5 | | 8 |
| 25+ | 6 | | 8 |

A matrix is dealt only if the eight cells shown settle the ninth under
every rule they obey, and a solver that reads nothing but those eight
cells agrees with every deal. The answers give nothing away on their
own: they are corners of a cube over two or three of the attributes,
so each value an answer has appears in as many answers as its
alternative. From two rules up the answer is never a cell already on
show. Two shortcuts remain and are measured: on rungs 1-3, where one
rule cannot avoid it, the answer is one of the two answers that are on
show; and from rung 4 to 15 picking among the answers *not* on show
wins about one time in three or four where chance is one in four or
six. From rung 16 that is at chance too.

#### The Linguist

Every trial deals a language nobody has seen, written in letters made
up for that trial. A few sentences are shown, each under a picture of
what it says; then comes one question about a new picture or a new
sentence. Nothing carries over from one trial to the next except how
languages are put together.

In a picture, an arrow runs from the doer to the done-to and its kind
-- plain, dashed, doubled -- is the deed; three of a thing is more
than one; a large one is big; grey has no colour said.

| Question | What to do |
|---|---|
| Which is the same word? | Rungs 1-3: find the written word among near-copies |
| Which sentence says this picture? | Pick it; the others each go wrong in one way or two |
| Which picture does this sentence say? | Pick it |
| Say this picture | From rung 10: click the word tiles in order (a few do not belong); **Backspace** takes one back, **Enter** is done |

| Rung | What the language may do |
|---|---|
| 1–3 | Nothing yet: matching written words of three, four and five letters |
| 4–6 | Words for things and colours; the describing word before or after its thing |
| 7–9 | Who does what to whom: the six orders of doer, deed and done-to |
| 10–12 | "More than one" and "big", each a letter before the word or after it |
| 13–15 | The deed-word agrees in number with the doer, with the done-to, or with neither; describing words may agree too. Six answers |
| 16–18 | "More than one" may be the word's own first or last letter said twice |
| 19–21 | The doer or the done-to is marked on the word itself, and the order is free |
| 22–24 | A clause inside a clause -- "the square pushes the circle that sees the star" -- before or after its thing |
| 25+ | Another clause deeper every three rungs, without end |

A trial is dealt only if its examples settle the answer: of the up to
2,560 ways a language of the rung can be put together, every one that
accounts for all the examples must give the same answer. The solver
is that learner -- it reads the examples and the question and nothing
else -- and it agrees with every deal. Examples the answer does not
hang on are then taken away, so every one shown is needed: four or
five on most rungs, seven or eight at the deepest.

The wrong answers are corners of a cube over two or three single
faults -- roles swapped, a number or colour or deed changed, the
describing word on the wrong side, agreement with the wrong one -- so
each fault is in as many answers as are free of it.

Not in it: sound rules beyond a letter said twice, and exceptions to
a language's own rules.

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

#### Dr Shape

A turtle flies through a dark neon stage laying down a line, and every
stroke it draws is also a note: the stroke's **height is its pitch**,
its **left–right place is where it sits between the ears** -- and the
note slides from one ear toward the other as the stroke does (level and
a fraction-of-a-millisecond delay, so it sounds placed, not panned) --
its **nearness is how loud and bright** it rings, its length is how long
it lasts, and **its colour is its instrument**. A thing far off sounds
quieter, duller, a few milliseconds late and full of the room's echoes.
Every shape has a sound, and the sound is the shape heard. Pick the
matching card with 1–6 or a click.

What has to be understood grows rung by rung: a shape however it is
turned; a shape and its mirror; which colour goes where; how big a thing
really is when it might be near or far; and where several things stand
in a place seen from somewhere else -- or only heard.

| Kind | You get | The cards are | Pick |
| --- | --- | --- | --- |
| **See** | the turtle drawing, with its song | shapes | the same shape |
| **Hear** | only the song | shapes | the shape that sounds like that |
| **Sing** | the turtle drawing in silence | sounds, played in turn, twice | the sound that is the shape |
| **Echo** | only the song | sounds, each colour on another instrument, in another key | the same tune |
| **Scene** | three things on a platform by a striped beacon, each singing from where it stands | the platform seen from elsewhere | the one where everything stands where it stood |
| **Hear scene** | only the three songs, placed by ear | platforms | the one you heard |

Shapes are paths, spirals, coils and branches, curves (torus knots,
Lissajous loops, helices) and solids (twisted and tapered prisms, leaning
pyramids, stretched tetrahedra, cubes and octahedra), drawn as lit tubes
with shaded see-through faces, fogging with distance, casting shadows.
After a pick, sound cards turn into the shapes they were.

| Rung | What it adds |
| --- | --- |
| 1–2 | Flat polygons and stars; the shape stays in view; three cards; see only |
| 3–4 | From memory; spirals; cards turned in the plane; echoes in the same instrument and key |
| 5–7 | Paths and curves through space, turned every which way; sing trials; more instruments |
| 8–10 | Mirror images, look-alikes with one part changed, prisms; **two colours**, and look-alikes with the colours moved; echoes change key |
| 11–13 | Solids, pyramids, knots and coils; **three colours**; five cards; echoes change instruments; bent instruments |
| 14–16 | Hear, sing and echo trials only: every trial turns on the ear |
| 17–19 | **Near and far**: picture cards are floors running to the horizon, each shape standing somewhere on one; some look-alikes are the same shape bigger or smaller, set nearer or farther so they look the same size -- only where they meet the floor, their shadow and the fog tell; cards turn and sing |
| 20–22 | **Scenes**: three things on a platform, the cards seen from another side; look-alikes swap two things, move one, mirror the place or put a different thing in |
| 23+ | Everything; scenes only heard; each scene card seen from its own side; sensory overload -- branching shapes, six cards, sparks, flicker, shaking cards, hiss and decoy chirps in both ears, instruments that change under the strokes, a faster turtle -- worse every rung |

No look-alike is ever the same thing in disguise: a mirror is only dealt
for a shape that is truly handed, a recolouring only when no turn of the
shape would undo it, a scene only when no thing stands where it stood.
Wherever the ear has to decide, no two cards sing the same tune. The
agent gets the stereo samples made since the last frame with every
frame -- 22.05 kHz, two channels -- and six ports, one per card.
Clocked: the turtle draws and the choosing time runs out whatever the
agent does.

#### Inside or Out?

One closed line on paper and a dot: is the dot inside? **I** or **Y**
for inside, **O** or **N** for out, or click. A glance settles a blob; a
winding labyrinth has to be followed, or the dot's way out looked for.
The line never crosses itself and the dot is never on it.

| Rung | What it adds |
|---|---|
| 1–3 | A round blob, the dot well in or well out |
| 4–6 | Deep fingers; the dot in a finger or a bay |
| 7–9 | A small labyrinth of one-cell corridors |
| 10–12 | A larger labyrinth |
| 13–15 | Two dots: can one reach the other without crossing the line? |
| 16–19 | Loose lines that do not close lie about as decoys |
| 20+ | Larger labyrinths every rung |

Two agent ports, inside (or *yes*) and out (or *no*). Turn-based, so it
takes the think clock.

#### Touching?

Two outlined shapes: do they stand **A**part, **T**ouch, or **O**verlap?
Touching is exact -- the outlines meet at one point -- and apart and
overlapping always clear a visible margin, which narrows up the ladder.

| Rung | What it adds |
|---|---|
| 1–3 | Two circles the same size, wide gaps and deep overlaps |
| 4–6 | Different sizes, narrower margins |
| 7–9 | Squares and circles, turned |
| 10–12 | How many pairs touch (0–5), among three or four circles |
| 13–15 | Thick outlines and filled shapes, thin margins |
| 16+ | More shapes, thinner margins every rung |

After the answer the touching points are ringed. Six agent ports: the
three answers, or a count. Turn-based, so it takes the think clock.

#### Time It

A ball rolls (or flies) behind a screen with a mark on it. Press
**Space** the moment the hidden ball is at the mark. Its motion has to
be carried on in the head -- its speed, its slowing, its bounce, its
fall -- from the stretch where it could be seen, and a hum follows it
while it is in view. Afterwards a ghost shows where it really was.

| Rung | What it adds |
|---|---|
| 1–3 | A steady roll, a short screen, a wide window |
| 4–6 | A longer screen, a narrower window |
| 7–9 | Friction: the ball slows as it rolls |
| 10–12 | It bounces off a wall behind the screen and comes back |
| 13–15 | Thrown in an arc; the mark is where it lands |
| 16–19 | Any of these, faster, longer hidden |
| 20+ | Tighter windows every rung |

One agent port, the press. Clocked: the ball moves whatever the agent
does, and the agent hears the hum with every frame.

#### Tuner

A sound plays once -- a dog, rain, a chainsaw. Then an old radio warms
up: static across the dial, and here and there a station, each playing
its own recording over and over. Find the station playing the sound you
heard -- drag the needle or click along the dial, drag the knob, or
hold **Left** / **Right** (**Shift** for fine) -- and press **Space** to
lock on, then stay with it for a moment. Locking onto the wrong station
loses the trial. **R** plays the sound again. Nothing on the screen says
which station plays what; the signal meter only says how strong a
station is.

The recordings are the ESC-50 clips the memory games use (see
[the media libraries](#long-term-memory-games-and-their-media-libraries); the default 500 are enough, all
2,000 give more variety). Each clip's kind and sounding stretch is
indexed in `res/misc/esc50/index.tsv`, built by
`tools/index_esc50.py`, so a trial is chosen without opening files and
only the clips it plays are read. Without the library the stations
play little synthesised tunes instead, on the same ladder.

| Rung | What it adds |
|---|---|
| 1–3 | Three stations, lamps on the dial, each sound from a different walk of life (animals, nature, people, home, street) |
| 4–6 | No lamps, four stations, narrower |
| 7–9 | Every station from the same walk of life -- all animals, say |
| 10–12 | The sound heard first is played faster or slower than the station plays it, and one station plays it backwards |
| 13–15 | Stations drift along the dial: hold on while locking |
| 16–19 | Stations fade in and out; one plays another recording of the same kind of sound -- a different dog |
| 20+ | More stations, narrower, faster drift every rung; from 24, two other recordings of the same kind |

Six agent ports: dial down and up, coarse and fine, lock, and hear it
again. The sound and the radio reach the agent only as audio, mixed
exactly as it plays. Clocked.

#### Shadow Play

A bent copper rod hangs in a lamplit room; its shadow falls on the
back wall, where a gold outline shows the shadow wanted. Turn the rod --
drag it (right button or **Shift** rolls), or **A**/**D**, **W**/**S**
and **Q**/**E** -- until its shadow lies in the outline, and hold it
there a moment. Every turn moves the whole shadow at once, and more than
one way the rod might hang can throw the same shadow.

| Rung | What it adds |
|---|---|
| 1–3 | A short rod turning about the upright only; a hum rises as the fit closes |
| 4–6 | A longer rod that tips as well |
| 7–9 | Rolling too |
| 10–12 | A floor lamp throws a second shadow with its own outline; no hum |
| 13–15 | The outline turns slowly: catch it and keep up |
| 16–19 | The lamp swings, so the shadow wanted keeps changing |
| 20+ | All of it, longer rods, a tighter fit every rung |

Six agent ports, one per turn direction. Clocked.

#### Captcha

Type the characters in the picture -- the keyboard types, **Backspace**
rubs out, **Enter** submits. The rule above the picture says which
characters count. At the bottom of the ladder it is four clean capitals;
up the ladder every character takes its own typeface, colour, size and
lean, the line waves and crowds, lines are struck through it, the
background fills with stripes, blobs, arcs and a confetti of stray
glyphs, and decoys stand among the real characters to be left out by
colour, by size or because they are upside down. Characters any font or
turn could confuse (0/O, 1/I/L, 2/Z, 5/S, 8/B, 6/9) are never used.

| Rung | What it adds |
|---|---|
| 1–3 | Four clean capitals, one typeface |
| 4–6 | Five, letters and digits, three typefaces, colours and tilts |
| 7–9 | Any of sixteen typefaces; a wavy, crowded line struck through |
| 10–12 | Six, with decoys in other colours: *type only the blue characters* |
| 13–15 | Small decoys to leave out; a cluttered background |
| 16–19 | Seven, with upside-down decoys to leave out; more of everything |
| 20+ | Eight, any rule (two at once from rung 24), more clutter and steeper tilts every rung |

After the answer the real characters are ringed. Twenty-five agent
ports: one per character, rub out, submit. Turn-based, so it takes the
think clock.

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

#### The Cipher Abyss

A laboratory with a machine in it. The machine takes a row of coloured
symbols (each with a shape, a number and a note) and gives back
another row; what it does is hidden. **Click** symbols from the
palette (or type **1–8**) to build an input, **Enter** to run it, and
read the result in the notebook on the right. Experiments are limited.
When you are ready, or the experiments are spent, **T** starts the
test. The test starts the machine afresh (its run count and memory
back to nothing), shows inputs it has never shown before, and you must
give its answer to every one. The end of each round says what the
machine was, in words.

The machines are programs in a small language
(`neural_workshop/cipherlang.py`) that grows up the ladder; what was
learned below stays in the language above, as the simpler look-alikes
each machine has to be told apart from. Each stage starts gently and
grows inside itself (a longer row, one more kind of piece, an
experiment fewer).

| Rung | Stage | What the machine can do |
|---|---|---|
| 1–3 | Patterns | Two colours. Rung 1 is the gentle start: a row of three, one plain thing (reverse, rotate by one or two, swap neighbours, flip the colours) and a different one on a row of one colour, two questions. Rung 2: a row of four, one named move or flip, the same kind of quirk. Rung 3: a move and a flip together, with a hidden quirk |
| 4–6 | Transformations | Three symbols mod 3: shifts, multiplying, affine maps, running sums, differences, sorting, counting runs, adding each to its mirror |
| 7–9 | Conditions | One transformation or another, picked by a hidden test of the input |
| 10–12 | Composition | Two transformations chained |
| 13–15 | State | What it does depends on its run count or its last input |
| 16–18 | Hidden language | Some symbols are instructions with hidden meanings, the rest data; each instruction is applied in turn to the data, so the answer is shorter |
| 19–21 | Cryptography | Affine maps and weighted sums mod 4, xor and multiplication in GF(4) and GF(8), Feistel rounds, after a reshuffle of positions |
| 22–24 | Rules that change rules | A list of rules worked through, moving on after every input that passes a hidden test |
| 25–27 | Nested | The test that picks the rule may look at the machine's own last answer or its run count; the branches are chains |
| 28–39 | Adversarial | A hidden exception for a row of one symbol (always asked about); rules that drop repeats, double up or halve the row; six symbols, longer rows, fewer experiments |
| 40+ | Open-ended | No ceiling. Programs grown at random from the whole language (held-out family included). Chains lengthen with the square root of the climb and branches nest with its logarithm, so the machines grow for ever: about 10 steps at rung 40, 70 at rung 100, over a thousand at rung 2000. Symbols rise to eight, rows to twelve, questions to six, and experiments fall to four |

On the patterns, transformations, composition,
hidden-language and cryptography stages every machine also has a **quirk**: on a rare kind
of row (one symbol throughout, a row that reads the same both ways, a
row already in order) it does something else, and the test asks about
it. So the simplest explanation of one experiment is never the whole
story.

**The language.** Every machine is a program; the end of a round
prints it in this notation. Each step works on a whole row, symbols
counted mod k:

| Step | In words | `0 1 1 3 2 0` gives (four symbols) |
|---|---|---|
| `rev` | reverse | `0 2 3 1 1 0` |
| `swap` | swap neighbours | `1 0 3 1 0 2` |
| `rot(2)` | rotate right 2 | `2 0 0 1 1 3` |
| `mirror` | reverse each half | `1 1 0 0 2 3` |
| `weave` | evens first, then odds | `0 1 2 1 3 0` |
| `unweave` | deal into evens and odds | `0 3 1 2 1 0` |
| `perm([2,0,1,5,3,4])` | shuffle positions 201534 | `1 0 1 0 3 2` |
| `stride(5)` | read every 5-th place, wrapping round | `0 0 2 3 1 1` |
| `shift(1)` | add 1 to each | `1 2 2 0 3 1` |
| `mul(3)` | multiply each by 3 | `0 3 3 1 2 0` |
| `affine(3,1)` | multiply by 3 and add 1 | `1 0 0 2 3 1` |
| `sub([1,0,3,2])` | substitute 1032 | `1 0 0 2 3 1` |
| `prefix` | running sum | `0 1 2 1 3 3` |
| `diff` | differences | `0 1 0 2 3 2` |
| `sort` | sort | `0 0 1 1 2 3` |
| `conv(1,2,0)` | out = 1*this + 2*before + 0 | `0 1 3 1 0 0` |
| `runs` | count each run | `1 1 2 1 1 1` |
| `oddshift(1)` | add 1 at odd places | `0 2 1 0 2 1` |
| `fold` | add each to its mirror | `0 3 0 0 3 0` |
| `xor(1)` | xor each with 1 | `1 0 0 2 3 1` |
| `gf(2)` | multiply each by 2 in GF(k) | `0 2 2 1 3 0` |
| `feistel(seq(shift(1)))` | a Feistel round of (add 1 to each) | `3 2 0 0 0 2` |
| `dedupe` | drop repeats | `0 1 3 2 0` |
| `double` | double each | `0 0 1 1 1 1 3 3 2 2 0 0` |
| `halve` | keep every other | `0 1 2` |
| `tshift(1)` | add 1 more each run | `1 2 2 0 3 1` (second run, after `1 2 3 0 1 2`) |
| `mem` | add the last input | `1 3 0 3 3 2` (second run, after `1 2 3 0 1 2`) |

Steps chain with `seq(a,b,...)`, and five forms combine them:
`if(test,a,b)` (a when the test holds, else b), `alt(a,b)` (a on even
runs, b on odd ones), `except(a,b)` (a, but b on a row of one symbol
throughout), `meta(test,a,b,...)` (a until an input passes the test,
then b, and so on round) and `prog(s:a,t:b)` (symbols s and t are
instructions meaning a and b, the rest data: each instruction in the
row is applied to the data in turn). The tests: `first(v)`, `last(v)`,
`has(v)`, `evens(v)` (an even number of v), `sumeven`, `rises`,
`same`, `pal`, `sorted`, and the stateful `tparity` (the run count is
even) and `echo(v)` (the last answer started with v). `tshift`, `mem`,
`alt`, `meta`, `tparity` and `echo` are why the test starts the machine
afresh. `perm` and `feistel` are defined for one row length only, so
machines using them get no longer-row question.

**Every machine dealt can be pinned down, and needs to be.** The
reference player keeps every rule of the rung's language still
consistent with what it has seen and runs whichever input splits them
most evenly. A machine is only dealt when, after the reference
player's experiments:

* every rule still standing gives the same answer to every test
  question (so the answer follows from the experiments);
* no simpler rule than the real one still fits (so the honest
  explanation is the shortest one);
* for every random first experiment, the simplest rule that fits it is
  some other rule (so one look is never enough), and the test asks a
  question each of those rules gets wrong, and questions that rules
  which fitted a few experiments earlier get wrong;
* the rung's commonest rule, and the rules most often mistaken for the
  real one after a single stray experiment, each get a test question
  wrong (a wrong-length answer counts only as far as the row goes, and
  at most one test row is a single symbol throughout).

Rungs 1 and 2 are short (rows of three and four, one plain step, two
questions) but hold the same guarantees as the rest: the quirk on a row
of one colour means one look is never enough, so the greedy and
commonest-rule players fail there too.

**Measured** (`tools/bench_cipher.py`, 30 machines a rung on every
other rung from 1 to 59 and on 64, 70, 80, 100, 150 and 300). The
reference player passes every round dealt, and every machine built
before the filter too. No shortcut player passes more than 3.3% of
rounds on any rung. A deal takes 0.37 s on average:
under 0.6 s up to rung 64, and about 1 s on the far rungs, where the
machines run to dozens of steps. Before this work the greedy player
passed 6–97% of rounds (53% on average) and the commonest rule up to
30%.

**The laboratory.** Above the intake row is the *hypothesis board*:
write down a guess at the rule from blocks (two steps in a row, if …
then … else, a rule per run, the rung's tests and transformations).
The menu only offers blocks that fit the next empty slot, so whatever
is on the board is a well-formed start of a program. **Check** (C) runs
the finished guess over every row of the notebook from a fresh start
and marks each row green or red. From rung 10 **Submit** (S) gives the
guess itself as the answer: it wins when it behaves exactly like the
machine on a large hidden set of inputs run in order (and on longer
rows where both allow it), however it is written. **Predict** (P) makes
you type what the machine will give before each run; the notebook
ticks or crosses each guess. The notebook scrolls (PageUp/PageDown),
sorts by time or by input (O), marks rows (M, or a click), shows a dot
over every place the output changed, and shows each symbol's number
under it (N hides them); shapes always tell the symbols apart, so
colour is never needed. The machine's answer comes out symbol by
symbol, each with its note, while the gears turn. The end of a round
shows the machine in words and in its formal notation, how many bits
each experiment told (the rung's rules standing before and after it),
which told most, and the inputs a careful experimenter ran. On the
very first round at rung 1 arrows walk you through it (remembered in
the data folder).

**Harder questions.** From rung 25 the last test question is on a row
two symbols longer than any experiment, so a table of the rows seen
cannot answer it: only the rule can. From rung 10 about one round in
four is a *two machines* round: after the test, a second machine is
described in words. It is either yours written another way (a step
split in two, two steps that commute swapped) or one that differs from
yours on only a few rows. Press **S** if they are the same, or give an
input on which they differ. Whether they are the same always follows
from the experiments. On the cryptography stage (rungs 19–21) some
rounds are *invert it*: the machine is one-to-one, the test shows an
output and asks for the input that gives it.

**What it remembers.** Each operator you crack (rotate, shift, xor,
...) goes into a small library in the data folder
(`cipher_abyss_library.json`) with the rung where you first cracked it.
Higher stages bring the same operators back inside new structure, and
the end of a round says "you met rot at rung 4" when it does. One
family is *held out*: reading every s-th place, wrapping round
(`stride`), appears in no machine and no look-alike below rung 30, so
the first time you meet it is a test of transfer, not of memory. **X**
saves the notebook as plain numbers (`cipher_abyss_notebook.txt`) for
keeping. Nothing is written in agent or test runs, and the first-time
arrows only show in a visible session, so agent runs stay deterministic.

**Scoring the reasoning, not only the result.** The ladder stays pass
or fail. Beside it, every round is measured: test accuracy, experiments
used against the reference player's, bits gained per experiment (the
rung's rules standing before and after each one), the size of a
submitted rule against the machine's, and the time taken. The end
screen shows them, and a visible session appends one JSON object per
round to `cipher_abyss_rounds.jsonl` in the data folder, with the
fields `rung, stage, kind (crack, twins or invert), won, accuracy,
questions, experiments, reference_experiments, bits,
bits_per_experiment, rule, rule_size, submitted, submitted_size,
seconds`. An agent sees these only as the end screen's pixels: the
agent boundary gives the learner pixels, sound and the pass/fail
scalar, nothing else, so they are never a reward.
`tools/score_cipher.py` is the benchmark: a fixed list of rounds (the
first rung and two rungs into every stage, rungs 30, 46 and 52 for the
held-out family and the open top, the same seeds every time), played
by any player given as `module:function` (default: the reference
player), or scores a results file with `--rounds`.

Keys: **1–8** symbols, **Backspace** takes one out, **Enter** runs or
answers, **T** starts the test, **Up/Down** and **Space** pick a block,
**Z** takes one off, **C** checks, **S** submits, **P** predicts,
**PageUp/PageDown**, **M**, **N**, **O** for the notebook. Everything
can also be clicked.

Thirty-seven agent ports. Ports 0–11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets it go; 14–21 add symbols 0–7, 22 takes the last
one out, 23 runs (or answers) and 24 starts the test. The hypothesis
board is ports too: 25/26 move down/up the block menu, 27 adds the
block, 28 takes one off, 29 checks, 30 submits; 31 turns predicting on
or off, 32/33 scroll the notebook, 34 marks its last row, 35 toggles
numbers and 36 sorts. The agent hears every answer as a short tune.
Clocked, but the clock is long.

#### Crazy Cog

A motor turns on the left of a workshop pegboard, a winch with a bucket
on its rope waits to the right, and along the bottom is a tray of cogs
of five sizes, each marked with its teeth (hover over one to see it at
its true size), and a coil of chain. **Drag** a cog onto the board:
dropped beside other cogs it snaps into mesh with them, dropped over an
axle (the motor's, the winch's, the fan's) it goes on it. Meshed cogs
turn opposite ways, and a smaller cog turns faster by the ratio of
their sizes. A **chain**, dragged onto one cog and then clicked onto
another at any distance, turns them the same way by the same ratio.
The motor is strong at a crawl and weak at speed, so a small cog on
the motor driving a big one on the winch lifts a heavy bucket slowly,
and the other way round stalls. Turn the winch the wrong way and the
bucket stays put; close a ring of cogs that cannot all turn and the
train jams. A cog in the hand shows a green or red ghost of where it
will land; drag a placed cog to move it, or **R** to clear the board.

**The machine has depth.** From rung 10 it is a box of glass planes,
one behind the other (two at rung 10, three at 16, four at 24, five
from 32). The motor turns on the front plane; the winch, its axle and
its bucket stand on the deepest. **Tab** (or **F**) moves your hand one
plane deeper, **G** (or **Shift+Tab**) one nearer, and **1–5** jump to a
plane. The plane in hand is drawn full size; the planes behind it
shrink toward a vanishing point at the back of the box, dimmer the
deeper they are, and the planes in front are faint ghosts, so the whole
train can be seen in depth, with steel shafts running back between
cogs that share an axle. Cogs on different planes pass over each other,
walls stand on one plane only, and a cog dropped on a plane over the
middle of a cog on another plane goes on its axle and turns with it.
That shared axle is the only way the drive travels back through the
box, so from rung 10 every train is carried down plane by plane, and a
cog on the winch's spot on the wrong plane turns nothing. Shared axles
are also compound gears, the only way to gear down far enough for the
heaviest buckets.

| Rung | What it adds |
|---|---|
| 1–3 | The motor and the winch side by side: two cogs that fit |
| 4–6 | Further apart: idlers and chains between, and the winch must turn the right way |
| 7–9 | A heavy bucket: gear down or the motor stalls |
| 10–12 | Two planes, the winch on the back one; walls to build around |
| 13–15 | Front walls across the direct way |
| 16–19 | Three planes; a fan that must turn the way its arrow shows, and a tight clock |
| 20–23 | Buckets only a compound gear lifts, the fan's speed on its dial's green, walls on every plane, less time every rung |
| 24–31 | Four planes |
| 32+ | Five planes, and the train runs back through all of them |

Seventeen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; 14 clears the board, 15 moves a plane deeper (from
the deepest, round to the front) and 16 a plane nearer. The
agent hears each cog go down (higher when it meshes), a chain hooked
on, the motor's hum rising with its speed and groaning when it stalls,
a grind when the train jams, and the winch ticking as the bucket
rises. Clocked.

#### The Proofreader

A passage of real text, damaged. Each sentence sits on its own line and
each word on its own tile. Mend the passage until it reads exactly as
it was written, then press **DONE** (or **Enter**). **R** puts the
damage back.

- **Drag a word** along its line to move it. Words never change lines.
- **Drag a sentence by its number** to move the whole line.
- **Click a word** to see four forms it could take (for example *walk*,
  *walks*, *walked*, *walking*, or a word of similar rank), then click
  one to write it. The forms are drawn the same way for every word, so
  they don't tell you which words are wrong.

The first word of each line is shown with a capital and the last with a
full stop wherever they move, so neither gives the answer away. Names
are never damaged.

| Rung | What can go wrong |
|---|---|
| 1 | Two neighbouring words swapped, in a single sentence |
| 2 | Plus a word with its letters scrambled |
| 4 | Two sentences, and the sentences out of order |
| 7 | Plus an intruder: a word replaced by another word |
| 10 | Three sentences. Plus a broken agreement: the wrong form of the right word (*was* for *were*, *walk* for *walked*, *a* for *an*) |
| 13 | Plus a word moved far from its place |
| 16+ | Four sentences and more (up to six). Scrambles move the first letter too |
| 19+ | No count of the mistakes. The intruders and wrong forms are close in rank to the true word, so the forms on offer look plausible |

Mistakes grow by one every three rungs up to rung 30, then one every
four rungs without end, capped at a third of the words. Past rung 25
the time shrinks once the mistakes have reached their cap.

Every damage is checked against the text banks: a damaged word never
makes a pair of words that appears anywhere in the corpus, and a
scramble never spells a known word. The aim is one right answer.
Grading is an exact match with the original.

The sentences come from Simple English Wikipedia (CC BY-SA 3.0), the
same source as the sentence tasks. The bank of passages (runs of two to
six sentences from one article) is fetched once with
`python -m neural_workshop.passages`. Without it, a small built-in set
of handwritten passages is used.

For the agent, ports 0–11 move the pointer, 12 presses and 13 lets go,
14 hands the passage in and 15 resets it. Sounds mark a lift, a drop
and a pick but never say whether a change was right. Clocked.

#### Full Stop

A few sentences of real text run together, with every full stop and
every capital taken out. **Click the last word of each sentence** to
put a stop after it (click again to take it away); the next word gets
its capital. The stop after the last word is already there. **Enter**
hands it in, **R** takes every stop away. It passes when every stop is
where it was written and there are no others.

| Rung | What changes |
|---|---|
| 1 | Two sentences, and one more every two rungs, up to twelve at rung 21 |
| 1–9 | The number of sentences is shown, with a running count |
| 14+ | Names lose their capitals too, so a capital is no clue |
| 20+ | Short sentences (four to eight words), so more stops in the same words |
| 22+ | The clock (a little under a second a word) shortens without end |

A passage is only dealt if every true break joins two words that never
stand side by side inside any sentence of the corpus, so English never
runs on across a break. Ports as in The Proofreader: 0–11 move, 12
presses, 13 lets go, 14 hands in, 15 resets. Clocked.

#### The Missing Word

A passage of real text, one sentence a line, has lost some words and,
from rung 7, gained some it never had. Under every gap between two
words is a small **caret**. **Click a caret** to see four words that
could go there and click one to put it in. **Click a word** to strike
it out. **Enter** hands it in, **R** puts the passage back as dealt. It
passes when it reads exactly as written.

The first and last words of a line are never missing, and no two
missing words were next to each other. A word is only taken out where
the two words it leaves side by side never appear together in the
corpus. A word is only put in where it makes such a pair on both
sides. Every caret offers four words, drawn the same way whether a
word is missing there or not, so the offer doesn't give the gaps away.

| Rung | What changes |
|---|---|
| 1 | One sentence, one missing word; one more mistake every three rungs |
| 4 | Two sentences |
| 7 | Extra words that don't belong |
| 10 | Three sentences; four or more from 16 |
| 13 | The other words on offer are as common as the right one |
| 19 | No count of the mistakes |
| 25+ | Once a quarter of the words are wrong, the clock shortens without end |

Ports as in The Proofreader. Clocked.

#### Figures of Speech

Words that do not mean what they say, from BIG-bench (see
[Social](#social) for the source and how to fetch it). It runs on the
same screen as the Emotion tasks.

| Rung | Questions |
|---|---|
| 1–3 | A sentence with a metaphor; pick the plain words that could take its place ("Her joy was ___": overwhelming, hidden...) |
| 4–6 | Also: which figure of speech a sentence uses, from four (simile, metaphor, personification, hyperbole...) |
| 7–9 | Also: the moral of a fable, from five; six figures to choose from |
| 10+ | Also: which of five sentences is not a metaphor of the kind the others are; eight figures; less time to read |

#### Heavier

Crates that look alike stand in lanes. Push one -- hold it with the
mouse, or hold **1-4** -- and it goes off as fast as its mass and the
floor under it let it; let go and it slides until the floor stops it.
Answer which crate is heaviest with the button at the end of its lane
(or **Z / X / C / V**). A round is five boards of three crates, or
four of four from rung 7, each to be answered right.

| Rung | What it adds |
|---|---|
| 1–3 | Three crates, one far heavier, the same floor under all |
| 4–6 | A floor of its own under each crate: slow to start may mean grip, not mass -- watch it slow as well |
| 7–9 | Four crates; some boards ask for the slipperiest floor |
| 10–12 | Crates of different sizes, which say nothing of mass |
| 13+ | The heaviest is heavier by less every rung; the push weakens |

Pass: every board right. From rung 4 the crate slowest off the mark is
the answer only by chance; the slowing after release gives the floor,
and the two together give the mass.

#### Analogies

A is to B as C is to which? Three glyph panels and a row of candidates.
What turned A into B -- a colour, a size, a number of copies, a turn, a
fill, a shape, a move across the panel -- has to be done to C. Colour,
fill and shape *become* B's value; size, count, turn and place *step*
as A stepped, and from rung 10 the two readings would differ, so only
the step is offered.

| Rung | What it adds |
|---|---|
| 1–3 | One change; three candidates |
| 4–6 | Turning and shape; four candidates |
| 7–9 | Two changes at once |
| 10–12 | Stepped values differ from A's; five candidates, most one property off |
| 13–15 | Three changes; glyphs placed across the panel, and moving |
| 16+ | A change more every four rungs to six; up to eight candidates |

#### Odd One Out

Every panel but one shares something; click the one that does not.
Every feature a panel can have is tried, and a deal is kept only when
the panel it means is the only one any feature singles out.

| Rung | What it adds |
|---|---|
| 1–3 | Three panels, alike in all but one or two properties |
| 4–6 | Four panels, every other property free |
| 7–9 | Pairs: the odd pair breaks a relation (the two share a colour...) |
| 10–12 | Five panels; the odd pair may be the one that keeps it |
| 13+ | A panel more every three rungs to eight; from 16 the odd panel is one property away from another |

#### Which Side?

Six panels left of a line follow a rule; six right of it do not. Does a
new panel go left or right (**Left** / **Right**)? Every rule the rung
allows is checked against the examples, and a deal is kept only when
all the rules they leave standing send the new panel the same way.

| Rung | What it adds |
|---|---|
| 1–3 | One property's value: "red", "three copies" |
| 4–6 | Or its opposite |
| 7–9 | Or two at once |
| 10–12 | Or either of two |
| 13–15 | Pairs, and rules about the pair |
| 16+ | Fewer examples a side, down to three; the new panel a property from one of them |

#### Pecking Order

Creatures in an order nobody shows; clues are pairs, "this one beats
that one". Who wins a pair the clues never put together? Higher up:
which creature stands *k*-th?

| Rung | What it adds |
|---|---|
| 1–3 | Three creatures, clues in order |
| 4–6 | Four, clues shuffled, the pair two steps apart |
| 7–9 | Five, and a spare clue |
| 10–12 | Six, and "loses to" clues |
| 13–15 | Seven or eight, the pair far apart |
| 16+ | A creature's place in the order, among up to twelve |

#### Card Sort

Key cards differ from each other in every property. Each card goes
under one; only "right" or "wrong" is said, and after a run of right
answers the rule (colour, shape, count, fill) **changes without
warning**. A run keeps the rule and the streak across trials.

| Rung | What it adds |
|---|---|
| 1–3 | Two keys, colour or shape, changes after six right and announced |
| 4–6 | Three keys and count; changes no longer announced |
| 7–9 | Four keys; changes after five right |
| 10–12 | Fill as well; after four |
| 13–15 | After three to five, and it may change back |
| 16+ | It changes after two to six cards, right or not |

Pass: the card under the key the rule in force says. A reference player
that keeps the rules the answers allow stays above 70% at every rung;
sticking to one rule, or guessing, falls below 60% and 50%.

#### Triples

Cards in colour, shape, number and fill, each one of three ways. Three
make a **triple** when, property by property, they are all alike or all
unlike. Which card completes the pair? Higher up: how many triples are
on the table?

| Rung | What it adds |
|---|---|
| 1–3 | Two properties vary; two or three candidates |
| 4–6 | Three properties; four candidates |
| 7–9 | Four properties; the wrong ones a property off |
| 10–12 | Count the triples among six cards |
| 13+ | A card more every two rungs, to twelve |

#### Who Lives Where?

Houses in a row; each has one of every kind of thing. Picture clues:
``=`` same house, ``≠`` not, ``|`` just left of, ``…`` somewhere left
of, ``↔`` next to, ``@ n`` at house *n*. Which house has the asked
thing? The clues always settle it, and none can be dropped.

| Rung | What it adds |
|---|---|
| 1–3 | Three houses, two kinds of thing, "same" and "at" |
| 4–6 | Three kinds; "not" and "just left of" |
| 7–9 | Four houses; "next to", "somewhere left of" |
| 10–12 | Four kinds |
| 13–15 | Five houses |
| 16+ | Six houses; from 22 a fifth kind and ever weaker clues |

#### Which Urn?

Two kinds of urn, their balls shown, and how many of each kind. Some
balls were drawn from one: from which kind, more likely? The answer is
the posterior by Bayes -- not whichever urn was really picked -- and a
deal is kept only when one kind is ahead by the rung's margin.

| Rung | What it adds |
|---|---|
| 1–3 | Nine to one against one to nine; one to three balls |
| 4–6 | Seven to three; up to five balls |
| 7–9 | Three colours |
| 10–12 | More urns of one kind: the prior and the draw may disagree |
| 13–15 | Small urns, drawn without putting back |
| 16+ | The margin narrows; more balls |

#### Grid Change

Two or three pairs of coloured grids, a before and an after, the same
change made to each; then a new grid and candidates. The changes are
flips, turns, recolourings, falls, shifts, filling holes, keeping the
largest piece, framing, doubling and mirroring -- and chains of them.
Every chain the rung allows is tried on the examples, and a deal is
kept only when all those that fit do the same to the new grid.

| Rung | What it adds |
|---|---|
| 1–3 | One flip or turn; small grids; three candidates |
| 4–6 | Recolouring, falling, shifting; four candidates |
| 7–9 | Two operations in a row |
| 10–12 | Operations on pieces |
| 13–15 | Up to three; grids to seven |
| 16+ | Two examples; bigger grids; candidates a cell off |

#### Button Box

A figure, a target, and a row of buttons, each doing one hidden thing
(turn, recolour, grow, move, change shape) -- dealt afresh every trial.
Press to find out; **R** resets the figure for free. Match the target
before the presses run out. Every property wraps round, so every press
can be undone.

| Rung | What it adds |
|---|---|
| 1–3 | Two or three buttons, the target a press away, presses to spare |
| 4–6 | Four buttons, two presses away |
| 7–9 | Five or six, three away; a button may do nothing |
| 10–12 | Buttons that do two things; no presses to spare |
| 13+ | A button more every two rungs to twelve; the target farther, to ten |

Pass: matched within the presses -- which are exactly what a player who
tries each button once and then takes the shortest way needs, plus the
rung's spare. Random pressing wins about three trials in four at rung 1
and almost none from rung 13.

#### Which Block?

Blocks, and a machine that lights for some. Earlier tries are shown;
the player may put blocks on and **Run** it (a try), then name the block
that makes it go. Past rung 3 the earlier tries are dealt so that
watching cannot tell -- the block that works was always seen with
another -- and only a try can: the difference between seeing two things
together and testing whether one makes the other happen.

| Rung | What it adds |
|---|---|
| 1–3 | Three blocks; a try already shows it alone |
| 4–6 | Four; the cause always seen with a decoy |
| 7–9 | Five; two decoys |
| 10–12 | Two blocks needed together; name both |
| 13–15 | Six or seven blocks, tries only just enough |
| 16+ | Up to eight; the machine sometimes fails to light |

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

#### Juggler

A circus cart under spotlights with a springy tray. Balls drop from the
top of the tent; **Left** and **Right** drive the cart, and a ball that
lands on the tray is tossed back up. Every toss stays in the air the
same time, heavy balls flying lower and light ones higher, so the
rhythm holds; where the tray meets a ball decides where it goes next.

| Rung | What it adds |
|---|---|
| 1–3 | One ball, then two |
| 4–6 | Three balls |
| 7–9 | Heavy and light balls, each falling at its own pace |
| 10–12 | Four balls |
| 13–15 | A draught that drifts the balls sideways |
| 16–19 | A narrower tray |
| 20+ | Five balls, a longer act, a smaller tray |

Pass: no ball dropped before the act ends. The model's juggler aims
every catch so the ball comes back toward the middle and keeps all of
them up through rung 10 nearly every time.

#### Balance

A handcar in a fenced desert yard at dusk, seen from behind and above,
with a lantern on a pole standing on it. The **arrow keys** (or **W A S
D**) push the cart left, right, away and near; the pole can lean any way
and leans against the push. Its shadow, and a gauge seen from above,
show which way. Flags stand in the yard (a map in the corner shows
them); stop under the lit one and hold still a second with the pole up,
then the next lights. Only the lantern touching the ground is a fall;
the fence just stops the cart.

| Rung | What it adds |
|---|---|
| 1–8 | Soft gravity, gentle pushes and training wheels (a pull back to upright, a damper on the swing): on rungs 1–2 the pole stands itself up, so just driving to the flags passes; from rung 3 the pull is well under gravity and you must balance; it is gone from rung 8, full strength from 9 |
| 1–3 | A long, slow pole; two flags close together |
| 4–6 | A shorter pole, three flags |
| 7–9 | Flags far apart |
| 10–12 | Gusts push the pole |
| 13–15 | A short, quick pole |
| 16–19 | The pole's length changes partway through, unannounced |
| 20+ | Shorter still, stronger gusts, more flags |

The model's controller balances both ways at once, with gains worked
out for each pole length and gravity, and passes every rung tried.

#### Crossings

How many times does the red line cross the blue? Press the number. Every
crossing is clean -- a fair angle, well apart from the others, and no
grazing in between -- so it is only a matter of following one line and
counting.

| Rung | What it adds |
|---|---|
| 1–3 | Two bent lines, up to two crossings |
| 4–6 | More bends, up to three |
| 7–9 | Smooth curves, up to four |
| 10–12 | A green line crosses both as a decoy |
| 13–15 | Up to five, at shallower angles |
| 16+ | More decoys, up to six |

After the answer every crossing is ringed. Seven agent ports, 0 to 6.
Turn-based, so it takes the think clock.

#### Keep the Beat

A metronome ticks -- a click, a lamp, a swinging arm -- then a curtain
drops over it and it goes silent. Keep tapping **Space** (or **J**, **F**)
on every beat that would have come. Only the silent part is judged: three
taps in four within the window, and no more than two strays. Nothing on
screen moves with the beat behind the curtain, so it has to be held
inside.

| Rung | What it adds |
|---|---|
| 1–3 | A slow, steady beat, a wide window, six beats to carry |
| 4–6 | A narrower window, eight beats |
| 7–9 | Any tempo from slow to brisk |
| 10–12 | Swing: long, short, long, short |
| 13–15 | Threes: long, short, short |
| 16–19 | The metronome comes back for a bar halfway, then goes again |
| 20+ | Longer silences, tighter windows every rung |

One agent port, the tap; the clicks reach the agent as audio with every
frame. Clocked. At 60 frames a second every rung can be hit; at the
slowest frame rate the tightest windows fall between frames.

#### Glider

A paper glider flies on through a sunset canyon. Hold **Space** (or
**Up**, **W**) to climb, let go to sink; it carries its speed, so it has
to be eased, not jerked. Pass every wall's gap without touching rock,
roof or floor.

| Rung | What it adds |
|---|---|
| 1–3 | Wide gaps, slow walls, far apart |
| 4–6 | Narrower gaps, closer walls |
| 7–9 | Faster |
| 10–12 | Gaps that slide up and down |
| 13–15 | Gusts of wind push the glider |
| 16–19 | A heavier glider, slower to answer |
| 20+ | Narrower, faster, gustier every rung |

Every course is flown by the model's pilot before it is dealt, so each
one can be passed. One agent port, held. Clocked.

#### Catch

A court runs away from you in perspective and a thrower lobs balls down
it. Move the basket -- the mouse runs it to the spot under the pointer,
or the arrows / **WASD** -- to wherever a ball will come down. Every ball
pops when thrown, whistles from where it is as it flies (higher the
higher, louder the nearer) and thuds where it lands. On the screen a
ball landing near and one landing far trace nearly the same curve: the
depth is the whole task. Drop no more than one.

| Rung | What it adds |
|---|---|
| 1–3 | One basket, slow high lobs one at a time, a shadow under the ball |
| 4–6 | Quicker, flatter throws, a smaller basket |
| 7–9 | No shadow; spinning balls curve sideways |
| 10–12 | Bounces off the side walls; two balls in the air at once |
| 13–15 | Two baskets -- red on the keys, blue on the mouse -- each catching its own colour |
| 16–19 | Fog over the far half of the court: listen for the throw |
| 20+ | The view swings to and fro, wind, smaller baskets, more balls |

Eight agent ports, four per basket. Clocked, with the balls' sound.

#### Echo Cave

Fly a bat down a winding cave, steering with the mouse (it flies toward
the pointer) or the arrows, without touching rock, and fly through moths
to catch them. **Space** clicks: the rock answers sooner and louder from
the near side, higher from above and lower from below, and a long low
echo from far down the cave says which way it turns. The moths buzz from
where they are. The light fails up the ladder until the ears are all
there is.

| Rung | What it adds |
|---|---|
| 1–3 | A lit, wide cave, gentle bends; catch one of three moths |
| 4–6 | Dimmer -- only the near cave shows; catch two of four |
| 7–9 | Dark: a click lights the cave for a moment |
| 10–12 | The moths can only be heard |
| 13–15 | Narrower and faster, winding up and down as much as sideways |
| 16–19 | No light at all: fly by the echoes |
| 20+ | Narrower and faster every rung |

Nine agent ports: eight steering directions and the click. Clocked;
clicks, echoes and moths reach the agent as sound.

#### Drone Hoops

Fly a little drone through hoops standing on poles in a walled yard at
dusk, in order, before the clock runs out. Hold the mouse button and
the drone flies to the spot under the pointer (the wheel sets its
height), or push it with **arrows** / **WASD**, **Space** / **E** up and
**Shift** / **Q** down. Pushes are relative to the camera -- forward is
into the screen -- and the drone coasts a little after you let go.
Clip a hoop's rim and you bounce back. The next hoop rings a bell that
rings faster the nearer you are, higher when the hoop is above you,
from its side of the screen. A shadow and a thin line down to it show
the drone's height; green and red lights mark its nose and tail.

| Rung | What it adds |
|---|---|
| 1–3 | Three big hoops, the next one gold; the camera rides behind the drone, looking at the next hoop |
| 4–6 | Smaller hoops set at angles; the camera follows the drone's heading |
| 7–9 | The camera cuts between fixed cameras round the yard every few seconds, so forward changes with it |
| 10–12 | No gold: every hoop looks alike and only the bell says which is next; flying through any other hoop loses the run |
| 13–15 | Hoops bob and turn on their poles; quicker cuts |
| 16–19 | Gusts of wind, heard before they hit; birds that chirp from where they fly |
| 20+ | The camera also circles the drone; lightning and thunder; from 24 a second bell rings on a wrong hoop at its own steady pace; more, smaller hoops every rung |

Ten agent ports, each a push for one step relative to the camera:
forward, back, left, right, the four diagonals, up and down. The agent
hears the bell, the rotors, the wind, the birds and the thunder.
Clocked.

#### Field Manual

A cube of a machine with buttons, switches, dials and sliders on its
faces, and an order in words along the top: "Press the red button",
"Turn the green dial to 5", "After the third beep, flip the switch left
of the blue dial". **Drag** the machine to turn it over, **click**
buttons and switches, **drag** a dial sideways or a slider along its
track, **type** numbers on the digit keys and hold **Shift** when an
order says so. The machine answers in sound: a tick for every notch, a
bell on a dial's hidden notch, a tone that follows a slider, a hum to
match it to, beeps to count. A wrong control, a wrong key or the clock
running out loses the job.

| Rung | What it adds |
|---|---|
| 1–3 | One order, three parts, all on the front face |
| 4–6 | Two orders; parts on the sides, so the machine has to be turned; dials, sliders, numbers to type |
| 7–9 | Three orders, every face; parts named by their neighbours; numbers painted on faces to find and type |
| 10–12 | "Until it tocks" (by ear alone), Shift held with a click, "every button except the red one" |
| 13–15 | Four orders; "after the third beep"; a slider matched to a hum by ear |
| 16–19 | The machine turns by itself; beeps come high and low and only one kind counts; noise |
| 20+ | Orders vanish after a few seconds; more orders, more parts, faster spin and less time every rung |

Twenty-five agent ports. Ports 0–11 move a pointer drawn on the screen (up, down, left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button and 13 lets go; 14–23 type the digits; 24 is Shift,
which counts as held for a quarter of a second after it is sent.
Clocked.

#### Safecracker

A vault door with a dial, a word lock and a handle, and an alarm
counting down. **Drag round the dial**: it ticks at every number and
thunks as it passes the number the next tumbler wants -- clockwise for
the first, back the other way for the second -- and letting go there
sets the tumbler. **Type** the answer to the clue along the top, then
**drag the handle down**.

| Rung | What it adds |
|---|---|
| 1–3 | One tumbler, a wide mark and a lamp that turns green on the number; the clue is the word itself |
| 4–6 | Two tumblers, no lamp; the clue is read off the door (the colour of a lamp) |
| 7–9 | Three tumblers; the camera drifts; opposites |
| 10–12 | False thunks at a higher pitch; words backwards; three mistakes set off the alarm |
| 13–15 | The door swings on its hinge; things on the door to count |
| 16–19 | Four tumblers, a quieter thunk, clues in two parts |
| 20+ | More tumblers, a finer mark, more false thunks, a wider swing and less time every rung |

Forty-one agent ports. Ports 0–11 move a pointer drawn on the screen (up, down, left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button and 13 lets go; 14–39 type A to Z; 40 is Backspace.
Clocked.

#### Stagehand

A small stage with props on marks and an actor wandering about, and a
script that comes up a line at a time. **Drag** a prop to the mark the
line names ("Move the lamp behind the chair" -- left, right, behind and
in front are always the audience's), **click** a prop to put the
spotlight on it, and press a cue key: **L** lights, **C** curtain,
**M** music, **S** smoke, **T** thunder. Lines that wait -- "When the
bell rings twice, ...", "On the drum, ...", "When the actor reaches the
table, ..." -- must be done in the moment after it happens, neither
before nor late.

| Rung | What it adds |
|---|---|
| 1–3 | Two lines, three props (labelled); moves, and key cues that name their key |
| 4–6 | The spotlight; lines that wait for the bell |
| 7–9 | The camera cuts between seats in the house; lines that wait for the actor |
| 10–12 | Bells that ring the wrong number of times first; cues no longer name their key |
| 13–15 | A camera backstage, where left and right are reversed; the drum, and a whistle that is not it |
| 16–19 | Quicker cuts, shorter moments |
| 20+ | A line more every few rungs and less time for each |

Nineteen agent ports. Ports 0–11 move a pointer drawn on the screen (up, down, left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button and 13 lets go; 14–18 are the cue keys. Clocked.

#### Loading Dock

A warehouse: a shelf of crates along the back, trucks along the front,
their orders written at the top ("OSLO: two red crates and a blue
crate."). **Arrows / WASD** drive the forklift the way a forklift
drives -- forward, back, turn. With the forklift beside a shelf bay,
**drag** a crate onto it (it carries two); beside a truck, **drag** a
crate from the forklift onto the truck; **click** a truck's lamp to
send it once its order is met. Each truck sounds its own horn three
seconds before it leaves by itself. The wrong crate, a truck sent
short, or a truck that leaves without its order loses the run.

| Rung | What it adds |
|---|---|
| 1–3 | One truck, one crate, three kinds on the shelf |
| 4–6 | Two trucks, one or two crates each |
| 7–9 | Three trucks; the camera cuts between corners of the warehouse |
| 10–12 | Marked crates: "a fragile crate", "a heavy red crate" |
| 13–15 | "A crate that is not red"; cameras overhead and behind the shelf |
| 16–19 | Four trucks in two waves; another forklift at work and a radio |
| 20+ | More trucks, less time for each, quicker cuts |

Twenty agent ports. Ports 0–11 move a pointer drawn on the screen (up, down, left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button and 13 lets go; 14–19 drive for the step they are sent in:
forward, back, turn left, turn right, forward-left, forward-right.
Clocked.

#### Gunslinger

A duel in a street at sundown, seen down your own barrel. Your revolver
is already in your hand and its sight follows the **mouse**, but you
may not fire until the other man goes for his gun; then you have as
long as he takes to draw and shoot. **Click** to fire. Fire before he
moves and you have shot first, which loses; take too long and he shoots
you. Aiming while you wait is allowed. From rung 4 **Space** cocks the
hammer before every shot. The notice nailed up along the top says who
your man is and what to hit. There is no clock on the screen.

| Rung | What it adds |
|---|---|
| 1–3 | One man, three seconds, and the word DRAW when he moves |
| 4–6 | Cock the hammer; no word -- watch his hand, listen for the leather |
| 7–9 | Two men, yours named by his hat; he feints; your aim sways |
| 10–12 | Three men, and the others reach too; "shoot his hat off" means the hat only |
| 13–15 | The men pace about; your man is named by who he stands next to |
| 16–19 | Four men, dust across the street, a drifting camera, bells and crows; sometimes your man is only "the one who draws" |
| 20+ | He is quicker every rung (down to four tenths of a second), the sway wider, more men and feints |

Fifteen agent ports. Ports 0–11 move the sight (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 pulls the trigger
and 13 lets it go; 14 cocks the hammer. Clocked.

#### Potter's Wheel

A lump of clay turns on the wheel. **Hold the mouse button** against it
at some height and the clay there moves, slowly, to where the pointer
is: in to narrow it, out to widen it. Shape it to the pot you are
shown, foot to rim, and take your hands off. **Up** and **Down** change
the wheel's speed (a faster wheel shapes faster and wobbles more);
**Space** wets the clay, which dries as it turns and will not move when
dry. Press a band to nothing, or draw it out too far, and the pot
collapses.

| Rung | What it adds |
|---|---|
| 1–3 | Four bands, the pot drawn over the clay, clay that stays wet |
| 4–6 | Six bands; the clay dries; moving a band drags its neighbours |
| 7–9 | Eight bands; the pot is drawn beside the clay, not over it |
| 10–12 | The wheel wobbles at speed; a finer match |
| 13–19 | Ten bands; the pot is shown for a few seconds and taken away |
| 20+ | More bands, a finer match, quicker drying and less time every rung |

Seventeen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; 14 spins the wheel faster, 15 slower, 16 wets
the clay. Clocked.

#### Conductor

The orchestra from the podium: strings to the left, woodwind in the
middle, brass to the right, drums at the back. The drummer gives the
pulse. **Flick the pointer down** on every beat. The score along the
top says what else is wanted and when: "Beat 5: bring in the brass"
(**click** that section, on that beat), "Beat 9: louder" (**Up**),
"Beat 12: softer" (**Down**), "Beat 14: cut the strings" (click them
again). A section that has been brought in is heard; one that has not
is silent. A missed beat, a missed cue or a wrong one is a slip.

| Rung | What it adds |
|---|---|
| 1–3 | Eight slow beats, one cue, the beat number shown, three slips forgiven |
| 4–6 | Twelve beats, two cues, louder and softer |
| 7–9 | The beat number only on the first of each four; cuts as well as entries |
| 10–12 | Quicker; a stray beat now counts as a slip |
| 13–15 | No beat numbers after the first four |
| 16–19 | The tempo bends: follow the drummer |
| 20+ | Longer pieces, more cues, a quicker pulse, a narrower moment, fewer slips forgiven |

Sixteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; 14 is louder and 15 softer. Clocked.

#### Tightrope

Seen in 3D from just behind your shoulders, you are on a wire strung
between two towers high over a city, holding a long pole. Move the
**mouse** left and right and the heavy pole follows a moment behind,
which tips you back the other way: when you lean left, put the pole
out to the right. You can fall forward and backward too: every step
lurches you forward, and moving the mouse **up** carries the pole
forward, which rights you backward (down carries it back). A spirit
level in the corner shows both. **Space** (or Up, or W) takes a step.
A gust of wind is heard coming, from the side it will blow from, a
second before it hits. Birds land on the pole and weigh that end down
until you **click** them off, which means reaching out to them.

Every rung is a little harder than the one below (more steps, sharper
jolts, quicker tipping, less time), and each new trouble comes in
gently and grows:

| From rung | What comes in |
|---|---|
| 1 | Five steps, soft jolts, a slow lean, plenty of time; on rungs 1–8 you tip far more slowly, the pole answers the hand more gently, and training wheels pull you upright -- on rungs 1–2 (and nearly to 4) just stepping gets you across -- firming up to full strength at 9 |
| 4 | The wire sways under you |
| 7 | Gusts of wind |
| 10 | Birds on the pole |
| 13 | A breeze that keeps shifting, sideways and fore and aft |
| 16 | A springy wire that swings sideways: your steps set it going, your lean shoves it, its swing throws you |
| 20 | The wire bounces too: a high bounce makes a lean grow faster and rocks you forward and back |

Fifteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; 14 takes a step. Clocked.

#### Sign Painter

A board hangs on two chains and the job is written above it: "Paint
TENT in blue." The letters are made of straight strokes: put the brush
down at the start of a stroke (**hold the button**), draw it along to
its end, lift. Wander off a stroke with the brush down, or paint in
the wrong colour, and you have smudged the sign; three smudges ruin
it. **1–4** (or R, G, B, Y) take up red, green, blue and yellow;
**Space** dips the brush when it runs dry.

| Rung | What it adds |
|---|---|
| 1–3 | Two or three letters, drawn faintly on the board; a wide brush; any colour |
| 4–6 | The colour named in the job |
| 7–9 | Only the corners of each letter are marked; the brush runs dry |
| 10–12 | Four letters; the board swings on its chains |
| 13–15 | Nothing is marked: you know your letters |
| 16–19 | Five letters, and a brush that drags behind the hand |
| 20+ | A finer brush, a wider swing, less paint and less time every rung |

Nineteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; 14–17 pick red, green, blue and yellow, 18
dips the brush. Clocked.

#### Bartender

You stand at the near end of a long bar with bottles on the shelf and
one glass. Orders come up in words: "Seat 3: a double red on the
rocks." **Hold a bottle over the glass** to pour: the glass sings a
higher note the fuller it gets. A single is half a glass, a double a
full one; over the brim is a spill. **Space** puts ice in. Then **take
the glass, draw it back, push it forward and let go**: it slides four
times as far as you pushed it, and has to stop in front of the
customer who ordered it. A wrong drink, a spill, a glass off the end
of the bar or a customer who gives up waiting is a strike.

| Rung | What it adds |
|---|---|
| 1–3 | One customer, two bottles, singles |
| 4–6 | Two customers; doubles |
| 7–9 | Three customers; ice |
| 10–12 | A pewter mug: the level has to be heard; only two strikes |
| 13–15 | Four customers, and regulars who ask for "the usual": what that hat had last time |
| 16–19 | Five customers, less patient |
| 20+ | More customers, more bottles, less patience |

Fifteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; 14 is the ice. Clocked.

#### Lock Pick

A lock cut open, its pins in a row, and two hands' work. One holds
tension on the plug: **hold Space** (or T) and it builds, let go and it
eases, and it has to stay in the band on the gauge -- too little and
set pins drop back, too much and the wrench slips. The other works the
pick: put its tip under a pin, **hold the button**, and raise it. Only
one pin binds at a time. Raise that one to its own height and it sets
with a click; shove it past and the lock jams and every pin drops.

| Rung | What it adds |
|---|---|
| 1–3 | Three pins that bind left to right; the binding pin glows; a tone climbs as it nears its height |
| 4–6 | Four pins in any order; no glow -- the binding pin sounds stiff when touched |
| 7–9 | Five pins; no climbing tone, only the click; a narrower band |
| 10–12 | Pins that are not binding give false clicks, higher than the true one |
| 13–19 | Six pins, and the pins cannot be seen |
| 20+ | More pins, finer heights, a narrower band, less time every rung |

Fifteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; port 14, held, tightens the wrench. Clocked.

#### Air Hockey

A table seen from your end. Your mallet goes where the **mouse** is on
your half; knock the puck into the far goal. Your own goal is kept by
a short bar that slides across its mouth on **Left / A** and **Right /
D**, so one hand attacks while the other defends. A puck that meets a
still mallet goes dead: it has to be struck. First to the goals wanted
wins; let in too many and you have lost.

| Rung | What it adds |
|---|---|
| 1–3 | One goal wins, three lose; a slow puck and opponent |
| 4–6 | Two goals to win; a quicker puck |
| 7–9 | A wider goal to keep; a quicker opponent |
| 10–12 | Three goals to win, two lose |
| 13–15 | The camera swings from side to side over the table |
| 16–19 | And at times looks from the far end |
| 20+ | A faster puck and opponent every rung; one goal against loses |

Sixteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; ports 14 and 15, held, slide the bar left and
right. Clocked.

#### 3D Brick Breaker

A ball in a box that runs away from you, a wall of bricks at the far
end, and a paddle across the near one. The **mouse** slides the paddle
across the opening; the **arrow keys** tilt it -- Left and Right turn
its face that way, Up and Down tip it -- and the ball leaves a tilted
paddle the way light leaves a mirror, which is how a brick is aimed
at. **Enter** levels the paddle; **Space** changes its colour, where
colour matters; **W A S D** slide it too. The paddle is a frame, to be
seen through, with a rod standing out of it that shows which way it
faces; the ball's shadow on the floor tells how far back it is.

A ball that gets past the paddle costs a life. A board is cleared when
every brick that has to go is gone, before the lives or the time run
out. The first ball is served a second after the paddle is first
touched.

| Brick | Looks | What it does |
|---|---|---|
| Plain | pale | Breaks |
| Tough | a raised plate for each extra hit | Takes two or three hits |
| Mine | black, a red stud | Costs a life when touched; need not be cleared |
| Steel | grey metal | Never breaks; need not be cleared |
| Numbered | a number; the next one lit | Breaks only when its number is the lowest left |
| Coloured | red, green or blue | Breaks only for a ball of its colour; the ball takes the paddle's colour each time it is returned |
| Bomb | orange, a black stud | Takes its neighbours with it -- mines too, and safely |

| Rung | What is added |
|---|---|
| 1–3 | Four to six plain bricks, a slow ball, a wide paddle |
| 4–6 | Seven bricks, some tough |
| 7–9 | Mines; a smaller paddle |
| 10–12 | Two layers, steel, three numbered bricks |
| 13–15 | Two colours, bombs |
| 16–18 | Gravity; the wall of bricks slides from side to side |
| 19–21 | A wind that comes and goes; three colours; three layers; a ball that quickens with every return; a smaller paddle |
| 22+ | Two balls; more bricks and mines, faster, a stronger wind |

So the top rungs ask for more than quick hands: which brick may be
broken next, what colour the ball must be when it gets there, whether
a bomb will clear the mines round it, and where a falling, drifting
ball will come back -- all while a second ball is on its way.

An agent plays through fourteen ports: eight slide the paddle (the
four ways and the diagonals), four turn its face, one levels it and
one changes its colour.

A reference pilot that gets under the ball and tilts the paddle for a
brick worth hitting, one port a step, clears every board in forty on
rungs 1-12, 35 to 39 in forty on rungs 13-21, and then 23 at rung 22,
19 at rung 26 and 12 at rung 30. Doing nothing never clears a board;
pressing ports at random cleared one in forty at rung 1 and almost
none above. A paddle that only follows the ball and never tilts clears
about half the boards up to rung 15 -- there, keeping the ball in play
is most of the job -- one in forty at rung 19 and none from 22, where
the mines find it.

#### Semaphore

A signaller on a far ship holds two flags; each pair of positions is a
letter in the workshop's own code. **Drag your own two flags** by their
tips to the same pose, then **type the letter**, before the signaller
moves on. A wrong letter, flags that do not match, or a signal let
pass is a strike. When the signaller's back is to you, what you see is
the mirror of the letter, and yours must be the letter itself.

| Rung | What it adds |
|---|---|
| 1–3 | Four slow letters of a word, each written beside the signaller: learn the code |
| 4–6 | No letter written; the code chart is on the screen |
| 7–9 | The ship rolls, so nothing is quite upright |
| 10–12 | The chart shows only at the start of each signal; two strikes lose |
| 13–15 | The signaller sometimes turns their back |
| 16–19 | No chart, and letters that spell nothing |
| 20+ | Fog, more letters, and a faster hand every rung |

Forty agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; ports 14–39 are the letters A to Z. Clocked.

#### Shadow Puppets

A lamp throws the shadow of a figure made of blocks on the wall.
**Drag** to turn the figure (across spins it, up and down tips it) and
roll it with **Q** and **E**. Bring its shadow to the shape asked for
and hold it there a moment. The same figure throws quite different
shadows from different sides.

| Rung | What it adds |
|---|---|
| 1–3 | A flat figure, the wanted shadow drawn on the wall under the real one, a tone that rises as you near it |
| 4–6 | A figure with a different shape from every side |
| 7–9 | The wanted shadow is on a card, not on the wall |
| 10–12 | Two shadows one after the other; no tone |
| 13–15 | The shape is only named: "Cast a T" |
| 16–19 | The figure is behind a screen: you see its shadow alone |
| 20+ | Three shadows and more, a finer fit every rung |

Sixteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; 14 and 15 roll the figure a little left and
right. Clocked.

#### Night Watch

A dark warehouse and one torch: you see only the round of light at the
**mouse**. People come in at the doors -- thieves, who walk to the
safe; the guard on his round; the cat -- and every footstep sounds
from the side it falls on. The night's orders, along the top, say what
a thief wears. **Click** a thief to catch them. Clicking anyone else
is a strike, a click on nobody wastes one of your few whistle blasts,
and a thief who reaches the safe ends the night. When the floor is
wider than the view, **Left / A** and **Right / D** turn you along it.

| Rung | What it adds |
|---|---|
| 1–3 | Two slow thieves in red caps, a floor you see whole, a wide torch |
| 4–6 | Three thieves, with a guard and a cat about; the guard's keys jingle |
| 7–9 | A floor wider than the view |
| 10–12 | The orders name tonight's colours, which change; a narrower torch; two strikes lose |
| 13–15 | Every step sounds the same |
| 16–19 | A wider floor yet, and thieves who do not walk straight |
| 20+ | More thieves, quicker, in a smaller light every rung; one strike loses |

Sixteen agent ports. Ports 0–11 move the drawn pointer (up, down, left, right
by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses its button
and 13 lets it go; ports 14 and 15, held, turn the view left and
right. Clocked.

#### Rail Yard

Trains leave a tunnel one after another, each painted the colour of the
station it must reach. **Click a set of points** (or press its number)
to throw it, and click a tunnel's signal (Q, W) to hold trains back or
let them go. A train that reaches points while they move comes off the
rails; two trains on one stretch of track collide.

| Rung | What it adds |
|---|---|
| 1–3 | Two stations, five trains, points throw at once; one wrong station forgiven |
| 4–6 | Four stations, closer together |
| 7–9 | Points take a second to throw |
| 10–12 | Eight stations, no wrong station forgiven |
| 13–15 | A second tunnel, merging into the yard |
| 16–19 | Express trains that catch up with the one in front |
| 20+ | Sixteen stations; more trains, closer and faster, every rung |

The model's dispatcher throws points for the next train in and releases
a train only when its whole route is clear; it clears every rung.

#### Air Traffic

A radar scope with planes coming in from the edges. **Pick a plane**
(click it or 1–8) and tell it to **hold** (H), **turn** 45 degrees (A,
D) or **land** (L) on a runway. Keep every pair apart, keep them out of
storms and inside the airspace, and land them all.

| Rung | What it adds |
|---|---|
| 1–3 | One runway, three planes |
| 4–6 | Two runways, five planes |
| 7–9 | A storm cell drifting across |
| 10–12 | Fuel: a plane circling too long is lost |
| 13–15 | A runway closes for a while; two storms |
| 16–19 | The wind turns and the runways flip ends; planes on approach go around |
| 20+ | More, faster planes and less fuel every rung; three storms |

The model's controller resolves conflicts, steers round storms and
clears one plane per runway at a time; it lands nearly every round low
down and few at the top, which is honest: the top is hard.

#### Escort

Walkers cross a torch-lit temple from the west gate to the east, never
stopping of their own accord. **Pull levers** (1–6, or click) to open
portcullis doors and slide bridges over pits; flame jets keep their own
clock, and each stands just past a door so the door is how a walker is
timed through it. A moving bridge carries no one.

| Rung | What it adds |
|---|---|
| 1–3 | One walker, doors and bridges, a lever each |
| 4–9 | Flame jets, then more devices |
| 10–12 | Coupled levers: one lever works two devices at once |
| 13–15 | Two walkers |
| 16–19 | Walkers change pace without warning |
| 20+ | Three walkers, faster |

Every temple is dealt so that the model's escort, which weighs what each
lever would break against what it would fix, brings everyone through.

#### Sokoban Live

Crates and pads in a lit warehouse, but the clock runs. **Arrows** step
the worker and push. Guards patrol straight aisles, one square a beat,
turning at walls and crates, so every push re-routes them; meeting one
ends the trial, and so does a crate pushed where it can never leave.

| Rung | What it adds |
|---|---|
| 1–3 | One crate, then one slow guard |
| 4–9 | Two crates, then a second guard |
| 10–12 | Three crates |
| 13–15 | Shutters that open and shut on a cycle |
| 16–19 | Four crates, faster guards |
| 20+ | Three guards, quicker every rung |

Rooms come from the Sokoban generator, made roomier; every one dealt is
cleared by the model's worker, which plans the pushes and then waits or
sidesteps when a guard would meet it.

#### Kitchen

One cook, crates of tomatoes, onions, mushrooms and fish, chopping
boards, stoves, plates, a pass and a bin. Tickets arrive along the rail,
each a dish of one to three parts and each losing patience. **Send the
cook to a station** (1–4, Q W, E R T, A S, D, F, or click) and it does
the obvious thing there; a pan left done too long burns.

| Rung | What it adds |
|---|---|
| 1–3 | One-part dishes, one stove, slow tickets; one may lapse |
| 4–6 | Two stoves; some parts are served chopped, not cooked |
| 7–9 | Two-part dishes, two plates |
| 10–12 | Pans burn sooner; nothing may lapse |
| 13–15 | Three-part dishes, a second board |
| 16+ | Three stoves; quicker tickets and less patience every rung |

The model's cook keeps every plate building toward the most urgent
ticket and serves nearly every shift below rung 25.

#### Crane

A harbour crane at dawn: a trolley on a rail high above, a hook on a
cable, a ship moored alongside and bays on the quay. **Left** and
**Right** drive the trolley (it coasts when let go), **Up** and **Down**
work the hoist, and **Grab** takes or lets go a box. Unload every box
into its bay; the load swings, and a box swung into anything is lost.

| Rung | What it adds |
|---|---|
| 1–3 | Two containers, a short way, a heavy damper on the hook |
| 4–6 | Three containers, a lighter damper |
| 7–9 | A tall stack between ship and bays to clear |
| 10–12 | Wind pushes the load |
| 13–15 | Four containers, bays stacked two high in order |
| 16–19 | The ship rolls, so the roofs rise and fall |
| 20+ | Gusts, a faster trolley, less time every rung |

The model's crane driver damps the swing with gains computed offline
for each cable length and unloads nearly every yard through rung 25.

#### Ferry

A river ferry between piers on two banks, with barges coming down the
lanes. **Ahead**, **Astern**, **Left** and **Right** (and the two
diagonals) work engine and rudder; the current carries everything
downstream. Dock at the lit pier, gently, and cross again as many times
as the shift asks, without touching a barge or running aground.

| Rung | What it adds |
|---|---|
| 1–3 | A gentle river, two crossings, no traffic |
| 4–6 | One lane of barges |
| 7–9 | A stronger river, two lanes |
| 10–12 | Three lanes and three crossings |
| 13–15 | Gusts up and down the river |
| 16–19 | Fog: barges show only near the ferry |
| 20+ | Faster barges, a stronger river, more crossings |

The model's skipper waits at each lane's edge for a gap and crosses
nearly every shift through rung 16.

#### Docking

The view from a ship's cockpit: the station's face, its port a ring
with a cross on a post standing out of it. Lined up, the cross sits in
the middle of the ring. **WASD** thrust across and up, **R / F**
forward and back, the **arrows** turn the nose, **Q / E** roll. Dock
centred, square and slow, before the fuel runs out.

| Rung | What it adds |
|---|---|
| 1–3 | Start near the line; range and closing speed shown |
| 4–6 | Drift, and the nose turned off |
| 7–12 | No readouts; spin; the station turns |
| 13+ | Tighter limits; fuel closer to what the best approach uses |

Pass: docked within the limits. The fuel is the reference's own use
times a slack that shrinks with the rung.

#### Rover

A rover on another world. What you send reaches it some time later,
and what its camera sees reaches you late again: half the delay each
way, and the screen shows the rover as it was. Drive to each flag in
turn (**W** drive, **S** brake and back up, **A / D** steer) without
hitting a rock or tipping over on a slope. The bar along the bottom
shows the commands still on their way.

| Rung | What it adds |
|---|---|
| 1 | A fifth of a second; one flag on open ground |
| 2–3 | Half a second; two flags |
| 4–6 | A second; rocks |
| 7–9 | Up to two seconds; slopes that tip a rover driven across them |
| 10–12 | Up to three seconds, and the delay wanders |
| 13+ | Three tenths of a second more every rung; more rocks |

Pass: every flag reached. The reference plans a route on a grid clear
of rocks and steep cross-slopes and steers from where the rover will
be when its command lands.

#### Unicycle

A rider on one wheel in open country, drawn in lit 3D with shadows,
the camera riding behind them. The rider is joined to the wheel by a
springy body, so every bump shakes them and every pedal stroke rocks
them back -- and they can topple sideways too, so the balance is kept
in all four directions. **Up / Down** pedal and back-pedal, **W / S**
lean forward and back, **Left / Right** (or **A / D**) lean left and
right -- and, as on a real unicycle, a sideways lean also turns the
wheel that way, which is how you steer. Hold a pedal and a lean key to
do both. Ride to each flag in turn (a map in the corner shows them).
Only the head touching the ground ends the ride.

| Rung | What it adds |
|---|---|
| 1–8 | Soft gravity, gentle pedalling and leaning, and training wheels: on rungs 1–2 the rider rights themselves, so just pedalling and steering at the flag passes; from rung 3 you must balance; the help is gone from rung 8, full strength from 9 |
| 1 | Flat ground, one flag straight ahead, plenty of time |
| 2–3 | Gentle hills, the flag off to one side |
| 4–6 | Steeper hills, small bumps, two flags |
| 7–9 | Steps up and down |
| 10–12 | Ledges to ride off, three flags, sharper turns |
| 13+ | Longer, rougher rides; the time allowed closes in on the reference's |

Pass: the flag, in time, head up. The time allowed is the reference
rider's own time with a slack that shrinks toward a tenth.

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

**Hold It.** A lamp lights and a tone sounds for a while, then both stop.
Hold **Space** for just as long; the lamp lights again while it is held,
but nothing shows how much time has gone. Close enough, as a share of
the time asked for, passes.

| Rung | What it adds |
|---|---|
| 1–3 | One short time, a generous margin |
| 4–6 | Longer times, a narrower margin |
| 7–9 | Hold half as long, or twice as long, as was shown |
| 10–12 | Two lamps one after another: hold for both together |
| 13–15 | A ticking clock runs at the wrong speed throughout |
| 16+ | Any of these, tighter every rung |

One agent port, held. Clocked, with the tone in the agent's audio.

#### Morning Round

A paper round up a street, seen from above. The bicycle rides near the
bottom and the houses come down past it, left and right. **Left /
Right** (or **A / D**) steer, **Up / Down** (or **W / S**) pedal faster
or slower, **Z** throws a paper to the left and **X** to the right. A
paper flies straight across to the lawns and lands where the bicycle
has got to by then, so throw a little before a house comes level.

Every house shows what it is: its door colour, its number, a pointed or
flat roof, a dog in the yard, the mailbox flag up or down, lit or dark
windows, a cat on the step. The **rulebook** on the left says which
houses take a paper. Riding is the easy part; the rules are the task.

| Rung | The rules |
|---|---|
| 1 | Subscribers have a star in the window. Slow, nothing in the road, two mistakes allowed |
| 2–4 | One written rule for the whole street: one feature ("blue door"), then two ("cat and not red door") |
| 5–6 | Two rules, A and B, and blocks between crossroads; a sign at each crossroads says which rule holds from there |
| 7–8 | No signs. The rulebook names the rule to start with; at any crossroads the rule may silently change to the other one (as often as not it does) |
| 9 | Three rules; house numbers (even, divisible by three) and the side of the street |
| 10 | Rules that look elsewhere: the house across the street ("across from: dog"), every second house of a kind, a door the colour of the last one on its side |
| 11+ | The rulebook is shown at the depot, then put away: ride from memory |
| 12+ | The block's landmark (a church on the corner) in the rules; four blocks |
| 13+ | No ceiling on the climb: more rules (up to six), more parts to each (up to nine), more blocks (up to eight), a faster bicycle and less time at the depot |

When the rule is not told, the houses are all there is to go by. A
subscriber thanks you for a paper (a chime and a tick), a house that
wanted none shouts (a cross), and a subscriber passed without one
complains (a horn and an exclamation mark). A house passed in silence
wanted none. The new rule has to be worked out from that, on the move.

A round passes when the street is done with no more mistakes than it
allows (a paper to the wrong house or a missed subscriber each count)
and without three falls. It allows one, two on the first two rungs,
and two more for every crossroads where the rule might change unseen.
Cones, bins and parked cars are in the road from rung 3, and from
rung 8 cyclists come the other way.

Every round dealt is passed by a reference rider that knows the
rulebook but not the hidden rule: it weighs the rules still possible
in each block by what the houses have said. A round is only dealt if
throwing at every house, at none, or keeping the first rule through
every crossroads would make too many mistakes; throwing at random
fails too. Each rule changes something on the street in
every part, and every two rules disagree about at least two houses in
every block.

For the agent: ports 0–1 steer, 2–3 pedal faster or slower (each for the
step it is sent in), 4 throws left, 5 throws right. Clocked.


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

#### Firebreak

A forest fire on a painted landscape, driven by the wind. **Arrows**
move the crew (Shift: four squares), **Space** digs a firebreak, and a
click digs where you point. Grass burns fast, forest slow, water and
rock not at all, and the shovels are few. Save the town: the trial
passes when the fire is out and no roof has burned.

| Rung | What it adds |
|---|---|
| 1–3 | One fire, a steady breeze, the town far off |
| 4–6 | Faster fire, fewer shovels, the town nearer |
| 7–9 | Two fires |
| 10–12 | The wind swings round mid-round |
| 13–15 | Embers jump a narrow break downwind |
| 16–19 | No wind arrow: only the smoke shows which way it blows |
| 20+ | Faster fire, slower digging, fewer shovels every rung |

Where to dig is the decision: a ring close round the town is cheap but
embers leap it; a wide one costs shovels the fire may not leave time to
spend. The model's crew rings the town twice against embers and saves
it nearly always below rung 20.

#### Crossroads

A town seen from above, its traffic lights yours. **1–4** (or a click)
switch a junction between its two ways; every switch runs through amber
and a moment of all-red. A road whose queue backs out of town is
gridlock; from rung 10 ambulances come through, and one held at a red
light too long loses the shift too.

| Rung | What it adds |
|---|---|
| 1–3 | One junction, light traffic |
| 4–6 | Heavier traffic, lopsided between the roads |
| 7–9 | Two junctions on one main road |
| 10–12 | Ambulances |
| 13–15 | Four junctions in a square |
| 16–19 | Rush hour: the busy road changes partway |
| 20+ | More traffic, more ambulances, a longer shift |

Every town dealt is one the model's pressure controller clears and that
leaving the lights alone does not.

#### Dam Keeper

Reservoirs step down a valley to a town. Each dam has a gate with four
notches (**Q W E** open a notch, **A S D** shut one); water let out of
one dam reaches the next some seconds later, and storms drift down the
valley raining into whatever they pass. Keep every dam from overtopping,
never send the town more than its river carries, and never let a
reservoir run so low its turbines stop.

| Rung | What it adds |
|---|---|
| 1–3 | Two dams, one storm |
| 4–6 | Three dams, two storms |
| 7–9 | Slower rivers between dams, a lower flood line |
| 10–12 | Bigger storms, back to back |
| 13–15 | Gates take time to move a notch |
| 16–19 | Storms show only once they are over the valley |
| 20+ | Heavier rain and a lower flood line every rung |

A storm brings water faster than a gate lets it out, so room has to be
made before it comes. Gates start shut, and every valley dealt is one
that doing nothing floods.

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

### Emotion

Reading feeling: in a face, in a voice, in what people write, in a
dialogue, and in what a situation is bound to make someone feel. All six
tasks share one screen. The item (a face, or text on a sheet) is shown
in the middle, the question under it, and the answers on buttons: click
one or press its number (**1–8**). Some items ask two or four things in
turn. After each item the right answer turns green (and a wrong pick
red) for a moment, with a chime or a low note. A row of dots along the
top shows the round so far. A round passes when enough items are right
that guessing, or giving the same answer every time, would almost never
do it (no more than 3% of rounds), and no fewer than the rung's share
for a careful reader. For the agent, ports 0–7 pick answers 1–8. All six
are clocked: each item has its own time.

The material is public data, fetched once into the data directory and
never bundled:

```bash
python -m neural_workshop.emotiondata              # all four
python -m neural_workshop.emotiondata faces         # or one of them
```

| Source | What it is | Licence |
|---|---|---|
| FER-2013 faces, with Microsoft's FERPlus labels | 34,484 photographs (48 by 48 pixels, grey), each read by ten people | FERPlus labels MIT; FER-2013 is a research challenge set with no stated licence, so it is only downloaded on request |
| GoEmotions | 33,457 Reddit comments with a single emotion of 27, or neutral | Apache 2.0 |
| EQ-Bench | 170 dialogues: how strongly a character feels four emotions, 0–10 | MIT |
| EmoBench | 400 English stories: how someone feels and why, or what would help | MIT |

Without them each task still runs on what is built in: faces drawn from
a few lines, and a handful of comments, dialogues and stories.

#### Emotion

Which emotion is the face showing? The right answer is what most of
the ten FERPlus readers said, and the ladder starts on faces nearly all
of them read the same way.

| Rung | Faces |
|---|---|
| 1 | Happy or sad, on faces at least 90% of readers agreed on |
| 2–3 | Surprised; then angry and neutral |
| 4–5 | All seven basic emotions (afraid, disgusted), 80% agreement |
| 6–7 | Contempt too: eight answers, 70% agreement |
| 8 | The face is covered after a moment (1.6 s, shrinking to 0.15 s) |
| 9+ | Faces fewer readers agreed on: 60 to 85% |
| 10+ | Some faces show only the eyes or only the mouth |
| 14+ | Faces with two emotions in them: name the strongest, then the next |
| 15+ | Down to faces only half the readers agreed on, and less time each, without end |

#### Which Feeling

What does the writer of a Reddit comment feel? GoEmotions' raters say.
The ladder is how close the other answers are to the right one.

| Rung | The answers |
|---|---|
| 1–2 | Two, of opposite feeling (joy or anger) |
| 3–4 | Three, one of them neither good nor bad (surprise, curiosity) |
| 5–7 | Four, one a near neighbour of the right one |
| 8–10 | Four, all of the same kind (anger, annoyance, disapproval, disgust) |
| 11–13 | Six of the same kind, and neutral |
| 14+ | Eight, and less time to read each rung |

#### How Strongly

A short dialogue from EQ-Bench, and four emotions. Up to rung 3: which
of the four does the character feel most at the end? From rung 4: how
strongly they feel each, on a scale of 0, 2, 4, 6, 8, 10. The four
answers together may be off from EQ-Bench's reference by 8 points at
rung 4, two fewer every two rungs, and not at all from rung 11. Only
dialogues where giving the same answer to all four would fail are
dealt.

#### Reading People

Stories from EmoBench. Rungs 1–3 ask how the subject feels; rungs 4–6
how they feel and then why; rungs 7–9 what would be the most helpful
thing for them to do; from rung 10 all of these, mixed, with less time
to read each rung.

#### Why They Feel

Short stories made up for the task, each built so that one emotion
follows from it by the appraisal theory of Ortony, Clore and Collins:
an emotion is how a person sees what happened. Was it good or bad for
what they wanted? Has it happened yet? Who did it, and was it right?
Did it happen to someone they like?

| Rung | Stories |
|---|---|
| 1–2 | What they wanted happened, or did not: happy or sad |
| 3–4 | It is still to come, and the signs are good or bad: hopeful or worried |
| 5–6 | They feared it, and it went well; they hoped for it, and it went badly: relieved or disappointed |
| 7–8 | They did it (proud, ashamed, remorseful), or someone else did (admiring, disapproving, grateful, angry) |
| 9–11 | News about a friend or a rival: glad for them, sorry for them, resentful, gloating |
| 12+ | People who want what others would not, like the player who hopes the match is rained off |
| 15+ | What one person thinks another feels, when they heard it wrong: "What does Cal think Bo thinks Ana feels?" One more level every five rungs, up to four |

Answers that would also be fair (someone relieved is happy too) are
never offered against each other. The number of answers grows from two
to eight, and the time per story shrinks with every rung.


#### Tone of Voice

An actor says an ordinary sentence ("It's eleven o'clock") angry,
disgusted, afraid, happy, sad or plainly. The words are shown, and
they are the same whatever the feeling, so only the voice tells. Each
clip plays twice; the time to answer runs after the second. The clips
are CREMA-D's (see [Social](#social)): 91 actors, and only clips that
listeners who heard them, without seeing the face, took for the
emotion the actor meant. How many of them agreed sets how plain a clip
is.

| Rung | Voices |
|---|---|
| 1 | Two emotions to choose between, on clips at least 85% of listeners agreed on; 20 clips, 16 needed |
| 2–3 | Three, 80% agreement |
| 4–6 | Four, 70% |
| 7–9 | All six, the plain voice among them, 65% |
| 10–12 | A hiss behind the voice, 55% |
| 13–15 | Only the first 1.2 s of each clip, a louder hiss |
| 16+ | 0.9 s, the loudest hiss, clips half the listeners agreed on |

Without the clips the voice is a hum made here: six syllables whose
pitch, pace, loudness and fall follow what is known of how each
emotion sounds. The voice also goes to an agent on the audio channel.

### Social

Reading people past their words. Both tasks run on the Emotion screen
(the text in the middle, answers on buttons, **1–8** or a click), and so
do Figures of Speech (under Reasoning) and the two Rationality tasks.
Answers are shuffled, and a round where pressing the same number every
time would pass is dealt again. The bar is set where guessing passes no
more than 3% of rounds, and never under the rung's share for a careful
reader. Long answers get a full-width row each. Time to read follows the
length of the text, and shrinks with the rung.

The material is fetched once into the data directory and never
bundled:

```bash
python -m neural_workshop.socialdata              # all three
python -m neural_workshop.socialdata voices        # or one of them
```

| Source | What it is | Licence |
|---|---|---|
| BIG-bench (`tasksource/bigbench`) | 492 indirect replies, 181 pairs of remarks (one sarcastic), 99 ironic or plain sentences, 213 metaphors, 59 figures of speech, 173 fables, 41 odd-metaphor-out questions, 1,400 short arguments and 3,000 syllogisms with negations | Apache 2.0 |
| Social IQa (AI2) | 35,172 everyday situations, each with a question about motives, feelings or what follows, and three answers | published by AI2 for research; see its site for terms |
| CREMA-D | 1,859 voice clips of 6 emotions, from 91 actors, each rated by listeners who only heard it | Open Database License |

Without them each task still runs on a handful of questions written
here (and Tone of Voice on its hum).

#### Between the Lines

What someone means, not what they say. Every question has two answers,
so a round has twenty and needs fifteen.

| Rung | Questions |
|---|---|
| 1–3 | "Are you coming to the party?" "I have an exam at eight." Does it mean yes or no? |
| 4–6 | Also: which of two remarks is sarcastic |
| 7–9 | Also: whether a sentence is ironic |
| 10+ | All three mixed, with less time to read each rung |

#### Social Sense

Everyday situations from Social IQa, each with a question and three
answers.

| Rung | Questions |
|---|---|
| 1–3 | How someone feels afterwards, and what they are like |
| 4–6 | Also: what they need to do first, and will want to do next |
| 7–9 | Also: why they did it, how others feel, what happens to them |
| 10–12 | Every kind of question, with less time |
| 13+ | Two questions about the same situation, both to be right |

### Rationality

Thinking twice. Both tasks make their questions here, so there is
never a shortage and none has been seen before.

#### Bad Argument

Does the conclusion follow from what is given? The arguments take a few
forms, valid or not: *if p then q; p; so q* and *if p then q; not q;
so not p* (valid); *if p then q; q; so p* (affirming the consequent)
and *if p then q; not p; so not q* (denying the antecedent); *all M are
P; all S are M; so all S are P* and *no M are P; all S are M; so no S
are P* (valid); *all S are P; all M are P; so all S are M* (an
undistributed middle) and *all S are M; so all M are S* (an "all"
turned round). The tests check every argument made against every way
its sets or facts could be.

| Rung | Arguments |
|---|---|
| 1 | Made-up words ("If the stone is gimble, it is mimsy"): a valid step, or one that changes the subject |
| 2–3 | Made-up words, every form, so only the form can tell |
| 4–6 | Real things, and the trap: half the valid arguments are about the world as it is not ("if the kettle is switched on, the water freezes") and half the invalid ones about the world as it is, so judging by whether it all sounds true gets half right, as guessing does |
| 7–9 | Also BIG-bench's short arguments |
| 10–12 | Say what is wrong: it follows, affirming the consequent, denying the antecedent, an undistributed middle, or an "all" turned round |
| 13–15 | Chains of three premises, whole or with a link turned round, and BIG-bench's syllogisms with negations |
| 16+ | All of it, naming the flaw again, with less time |

#### Second Thoughts

Questions whose first answer is wrong; that answer is always among the
choices.

| Rung | Questions |
|---|---|
| 1–3 | The race (overtake the runner in third: you are third), the pond (lily pads double daily and cover it in 48 days: half on day 47), the coin (heads six times: tails is no likelier), and a test told in counts of people (of those who test positive, how many are ill?) |
| 4–6 | Also: the bakers (5 bake 5 cakes in 5 minutes: 100 bake 100 in 5), the price (a bat and ball cost 1.10, the bat 1.00 more: the ball is 0.05), and the description (more likely a bank teller, or a bank teller and an activist? asked the other way round as often) |
| 7–9 | Also: the hospitals (the small one sees more days with over 60% boys), and the test in percentages, where the lure is the test's accuracy |
| 10–12 | All of them, with less time |
| 13+ | Also: the chance of illness after two positive tests |

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
