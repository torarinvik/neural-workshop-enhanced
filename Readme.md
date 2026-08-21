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
| `nwenv/` | the agent boundary — frame capture, public outcomes and their verification, and the stepped environments |

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
| `div2k` | 900 photographs, 2K resolution | ~4 GB |

The `div2k` library feeds the jigsaw puzzles and comes by a different
route: the Hugging Face dataset (`eugenesiow/Div2k`) is a loading
script over the original NTIRE challenge archives rather than hosted
rows, so the fetch downloads those zip archives whole and unpacks
them. The default hundred images is the validation archive alone
(~430 MB); asking for more pulls the 3.5 GB training archive too. The
download resumes where it left off if interrupted. DIV2K is published
for academic research use; the images are collected from the Internet
and their copyright stays with their owners.

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

#### Jigsaw Puzzle

A photograph is cut into a square grid of tiles and shuffled; click
two tiles to swap them, and the puzzle is done when the picture is
whole. The photographs are the DIV2K set at 2K resolution — detailed
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
a solve near the minimum takes the next puzzle up a size, from
two-by-two to ten-by-ten. The finished picture is shown beside the
board like the lid of the box; turn it off and the tiles are all
there is.

Every photograph in the library is used before any is used again, and
the rotation is remembered across sessions — a jigsaw of a picture
you have already assembled is a memory task, not a reasoning one. A
larger library therefore means longer before anything comes round
again; the default hundred images is a hundred fresh puzzles.

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

#### You Are Here

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
of the planning category is scored. On the largest rungs that takes a
second to solve before the maze opens, which the options screen says
in advance.

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
