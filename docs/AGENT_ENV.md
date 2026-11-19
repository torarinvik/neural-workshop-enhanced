# Agent environment

How a learning agent plays Neural Workshop: the stepped boundary, what an
observation holds, how actions and outcomes work, and how an outcome is
verified. Writing a wrapper for a new task is covered in
[ADDING_A_TASK.md](../ADDING_A_TASK.md).

## The n-back environment

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

## Out of Sight as an environment

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

## The rest of the workshop

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

## The think clock: making thinking cost something

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
