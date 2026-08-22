# Making a task reachable by the agent

The Workshop ships twenty-six playable tasks and **all twenty-six are
reachable by the learning agent**. Reachable means more than playable: the
agent gets pixels and opaque ports, and every scalar it is paid must be
re-derivable from the frames by someone who is not trusted with the game.

This is what a new one has to do. It is short, and the reason it is short is
that four wrappers were written before any of it existed — 628, 680, 719 and
one more — and about 85% of each was the same plumbing.

## The whole of a wrapper

```python
from nwenv.taskenv import TaskEnv


class MyTaskEnv(TaskEnv):
    """One line about what the ports mean."""

    task_class = ('neural_workshop.ui.mytask', 'MyTask')
    ports = 4
    clocked = False
    action = 'walk'
    open_phase = ('playing',)
    settled_phase = ('solved',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials'}
```

Then, at the bottom of the file:

```python
verify_mytask_outcome = MyTaskEnv.verifier()
```

and a row in `nwenv/catalog.py`. That is the whole of it. There is **no
deriver and no verifier** in that file — they already exist, they are
natively accelerated, and they are the same ones every other task uses, so
the programme has one pixel reader to get right rather than one per task.

### What each declaration means

| | |
|---|---|
| `task_class` | module path and class name of the UI task. Imported lazily. |
| `ports` | how many opaque actions there are. **The task's ceiling, not a rung's** — a round offering four choices out of a possible eight leaves four ports doing nothing, and that is fine. |
| `clocked` | whether the task moves on its own. A turn-based task is `False` and is never ticked. |
| `action` | the method one port calls: `action = 'answer'` means `task.answer(port)`. |
| `action_table` | per-port arguments, when a port is not just its own index. Must be exactly `ports` long. |
| `open_phase` | the phases in which a port does anything. Empty means always. |
| `settled_phase` | the phases that mean the trial is over. The driver waits **one published frame** in them before dealing the next, so the verdict is on a frame the learner is actually handed. |
| `deal` / `start` | what deals the next trial and what starts a run. Default `_next_trial` and `start_run`. |
| `knobs` | constructor keyword → task attribute. `MyTaskEnv(rung=4)` sets `task.start_rung = 4`, coerced to the type the task already holds. A knob the task does not have fails the build. |
| `requires` | settings the boundary imposes whatever the player prefers. Almost always `{'feedback': True}`: a trial that resolves with no verdict painted resolves into nothing a third party can read. |

The hooks are all still there — `build`, `drive`, `trial_open`, `tick`,
`resolved`, `finished` — and an override wins over a declaration. Five tasks
need one. Count composes its answer out of digits, Sudoku steers a cursor,
Moving Targets and Concentration name an object rather than an index, and
Reflex has no phase for its trial window at all. Each is six lines. Three
more override `apply_dials` and `dials` only, which is the coach gate below
rather than anything about their ports.

## The two things the UI must do

### 1. Paint the verdict where the reader looks

```python
from neural_workshop.ui.verdict import VerdictLabel

self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
...
self.verdict_shown = (steps <= par, _('Out in %d steps') % steps)
self.verdict.show(*self.verdict_shown)
```

and take it down when the next trial opens:

```python
self.verdict_shown = None
self.verdict.clear()
```

Green reads +1, red reads −1, nothing painted reads as *unresolved*, which is
not the same as zero. The text is for the person and does not affect the
scalar. Keep `verdict_shown` and restore it in `_build_chrome`, or a window
resize on the frame a trial settles drops the label and the outcome is never
derivable.

**Show it only after the action window has closed.** Painted a frame early it
stops being a verdict and becomes an answer key: a learner that can see the
verdict while it can still act will read the label instead of the task, and
every result gathered afterwards is about the label.

**Clear it before the next trial opens.** A verdict left up spans two trials,
and the second derives the first one's scalar.

### 2. Keep the art out of the band

```python
from neural_workshop.ui.verdict import above_the_band

bottom = above_the_band(from_bottom_edge(56))
```

The reader looks at the bottom quarter of the frame and counts a channel at
or above 180 with the other two at or below 140. Anything there is read as a
verdict.

The rule is **not** "avoid three colours", and it is worth knowing why,
because seven tasks got this wrong. The Maze drew its doors in Okabe-Ito
orange, `(230, 159, 0)`, which is not a verdict colour — green sits at 159,
comfortably clear. But an orange square on a pale page is edged by every
blend between the two, and part of that ramp has green already below 140
while red is still above 180. Nine such pixels in a row were being paid as a
scored trial. Any colour with two channels far apart passes through the
window on its way to the background, and no palette avoids that.

So the rule is the simple one: the art stops above the band.
`above_the_band` is where that line lives, and it works it out the same way
`bwaccel.default_band` does, with a few pixels of slack for the edge.

**If the art is content rather than layout, the sweep will lie to you.**
Reflex spawns photographs at random places and used to spawn them from a
tenth of the way up, which is inside the band. Whether a run painted
anything the reader counted depended on which pictures were drawn, so
`check_band.py` reported it about one run in three and came up clean
otherwise. One clean sweep proves nothing there. Where a violation
depends on content, write the guard against the *geometry* — assert that
the spawn box clears `above_the_band()` — and let the sweep be the thing
that finds it rather than the thing that certifies it.

## If the task pays only at the end, shape it

A task whose verdict arrives once a round is a task a learner starting
from nothing is almost never paid on. The fix is not a new reward channel —
it is the same `VerdictLabel`, painted after every action that changed how
far the run has to go:

```python
class MyTaskEnv(TaskEnv):
    dense = True                       # pay per action, not per trial

    def apply_dials(self, task):
        super().apply_dials(task)
        task.coach = self._coach and self.paying_densely
```

and in the task, after an action:

```python
before = potential(...)
...                                    # do the action
delta = potential(...) - before
self.verdict.show(delta < 0, _('Warmer') if delta < 0 else _('Colder'))
```

Three rules make it safe rather than merely dense.

**One action must change the potential by at most one.** Then the sign of
the change *is* the potential-based shaping term of Ng et al., every
closed loop of actions telescopes to zero, and the optimal policy is
unchanged. An action that changes nothing — a turn, a bump, a grab —
clears the label and pays zero. If it paid, doing it on the spot would
farm reward forever.

**The potential must read only what is drawn.** Then the shaping tells a
learner nothing a frame does not already carry, and it is pure
acceleration. Chain of Custody's potential is deliberately blind to which
box is the Core: had it read that, coach mode would have handed over the
answer to the only question the task asks, and every number taken under
it would have been about routing while claiming to be about identity.

**Gate it on `paying_densely`.** `dense` is honoured only by the
neutral-outcomes accounting, which is how a *runtime* builds an
environment. Built the plain way, the sparse path pays the first verdict
it finds and calls it the trial's — so a warmer/colder label a few steps
in scores the whole round. Measured before the gate existed: Chain of
Custody scored 44% against a 38% guessing floor, all of it earned by claw
moves that happened to close a distance, and You Are Here was paid a `+1`
on a maze random play had not solved.

Keep it off for people (`coach = False` in the task's `__init__`), so the
human game stays pixel-identical and every number taken before still
compares.

**Shaping is not the only honest way to be dense**, and a task that is
not doing it should not borrow the vocabulary. Cookie Thief pays per
beat too, but there is no potential in it and nothing telescopes: a
cookie the boy got away with is a piece of the green and a grab Mother
had her eyes on is the red. That is the round's own *haul* taken apart
rather than a potential over it. It orders policies the way the
round's single scalar does — which is what makes it safe — and it
diverges in one way worth writing down: the scalar is all-or-nothing
and the sum is graded, so a learner paid this way tolerates a little
more risk than the verdict rewards. Say which of the two you built. The
first two rules still apply to both; the telescoping one is specific to
shaping.

## Read the clock the driver owns

```python
import time
...
#: Swapped out by an agent environment for a virtual clock.
self.clock = time.time
```

and every deadline goes through `self.clock()`, never `time.time()`.

Fifteen tasks read the wall clock directly and every one of them was
undriveable because of it: a stepped run advances a virtual clock, so a task
gated on real time either never advances or advances at a rate that depends
on how fast the machine happens to be. `tests/test_ui_clock.py` fails the
build if a task module calls `time.time()` anywhere but that one line.

## What a task may not change

`TaskEnv` seals the receipt ledger, the one-outcome-per-receipt rule, the
observation dictionary and the construction of the verifier. Defining a
subclass that touches them raises `SealedContractError`.

This is not tidiness. A task that redefined `_emit_once` could pay one action
twice; one that redefined `_observation` could hand the learner a coordinate.
Neither fails loudly, and every claim the programme makes about its results
rests on both staying true. Five experiments were once retracted for an
instrument defect nobody could see, which is the cost of finding this sort of
thing late.

## Before it counts as ready

**Sweep the band.** It reads every wrapped task through its own wrapper, so
adding the catalogue row is what puts a task in the sweep:

```
cd tests && PYTHONPATH=.. ../.venv/bin/python check_band.py
```

**Play it at random** and see whether the boundary pays it:

```
cd tests && PYTHONPATH=.. ../.venv/bin/python drive_env.py mytask 900
```

Zero outcomes is not automatically a bug. Five tasks have no accidental
solutions — a sudoku, a jigsaw, a memory board and the two mazes — and
random play will never finish one. Those get a test in
`tests/test_env_tasks.py` that drives them with a policy that knows the
answer, through the same ports, and still reads the verdict off the frame.

**Run the panel:**

```
.venv/bin/python -m experiments.brainworkshop_canonical.task_panel --tasks mytask
```

It reports whether actions change the frame, whether the pressed port is
recoverable from consecutive frames, how dense the reward is, whether
anything ever costs, and whether the verifier accepts every claim. Measured
on the first four tasks, **none is good on all four axes**, and they fail
different ones — so the panel is worth reading rather than glancing at.

Recoverability especially: Out of Sight changes 3.6% of the frame against
Fog of War's 0.2% and its action is no more recoverable, because its pixels
are dominated by an animation that runs whether the agent acts or not. What
matters is the agent-caused share of the change, not its size.
