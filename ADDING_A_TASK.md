# Making a task reachable by the agent

The Workshop ships around two dozen playable tasks. Four are reachable by the
learning agent, because reachable means more than playable: the agent gets
pixels and opaque ports, and every scalar it is paid must be re-derivable from
the frames by someone who is not trusted with the game.

The three wrappers written before this document came to 628, 680 and 719
lines. Measured across them, about 85% of each was plumbing — 584, 605 and
524 lines respectively that were not the deriver, its helpers or the verifier.
A fourth written the same way would be another six hundred lines already
written three times.

## What a task supplies now

```python
from nwenv.taskenv import TaskEnv

class MyTaskEnv(TaskEnv):
    ports = 4

    def build(self, seed, **dials):
        return MyTask(seed=seed, **dials)      # the UI task

    def drive(self, task, port):
        task.walk(('ahead', 'back', 'left', 'right')[port])

    def dials(self):
        return {'MYTASK_LEVEL': self.level}
```

Optionally `begin(task)` and `settled(task)` if a trial is not always open.

That is the whole of it. There is **no deriver and no verifier** in that
file, and that is the point: they already exist, they are natively
accelerated, and they are the same ones every other task uses, so the
programme has one pixel reader to get right rather than one per task.

## The one thing the UI must do

Paint the verdict where the reader looks:

```python
from neural_workshop.ui.verdict import VerdictLabel

self.verdict = VerdictLabel()
...
self.verdict.show(good=steps <= par, text=_('Out in %d steps') % steps)
```

and take it down when the next trial opens:

```python
self.verdict.clear()
```

Green reads +1, red reads -1, nothing painted reads as *unresolved*, which is
not the same as zero. The text is for the person and does not affect the
scalar.

### Two rules about it

**Show it only after the action window has closed.** Painted a frame early it
stops being a verdict and becomes an answer key: a learner that can see the
verdict while it can still act will read the label instead of the task, and
every result gathered afterwards is about the label.

**Clear it before the next trial opens.** A verdict left up spans two trials,
and the second derives the first one's scalar.

**Keep the bottom quarter otherwise plain.** The reader is deliberately
tolerant — a channel at or above 180 with the other two at or below 140 —
because anti-aliased glyph edges never land on an exact value. Any saturated
red, green or blue down there will be read as a verdict. A bare application
window already contributes one blue run, so a task painting here must own the
band.

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

Run the panel:

```
.venv/bin/python -m experiments.brainworkshop_canonical.task_panel --tasks mytask
```

It plays the task at random and reports whether actions change the frame,
whether the pressed port is recoverable from consecutive frames, how dense
the reward is, whether anything ever costs, and whether the verifier accepts
every claim. Measured on the four existing tasks, **none is good on all four
axes**, and they fail different ones — so the panel is worth reading rather
than glancing at.

Recoverability especially: Out of Sight changes 3.6% of the frame against Fog
of War's 0.2% and its action is no more recoverable, because its pixels are
dominated by an animation that runs whether the agent acts or not. What
matters is the agent-caused share of the change, not its size.
