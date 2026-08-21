"""Play a wrapped task at random and say whether the boundary paid it.

    PYTHONPATH=.. ../.venv/bin/python drive_env.py removals 400
    PYTHONPATH=.. ../.venv/bin/python drive_env.py --all 700
    PYTHONPATH=.. ../.venv/bin/python drive_env.py --all 700 --runtime

The task names are the ones in :mod:`nwenv.catalog`, which is also
where the list comes from — there is no second list here to fall out
of step with it.

One task at a time: these bind shared-memory segments and two workshop
instances at once risk a name collision. ``--all`` runs them in
sequence for that reason, and it is slow.

**Two constructions, and they do not measure the same thing.** By
default an environment pays only when a trial resolves, and this tool
counts those. A *runtime* builds it with ``neutral_outcomes=True``,
where every tick carries a scalar and zero means "no consequence" —
and that is the only construction in which a task declaring
:attr:`TaskEnv.dense` pays its per-move shaping at all. So You Are
Here in coach mode reads 1 outcome in 1500 steps by default and 272
nonzero ones in 1200 under ``--runtime``; both are true, and only the
second is what a trainer sees. Pass ``--runtime`` when the number you
want is the one the learner gets.

What the numbers mean. *Outcomes* is how many scalars a run of random
actions was paid, and it is not a score — it is whether the boundary
is wired up at all. A task reporting zero is either not reachable by
random play (which several are not, and the sparse ones say so in
their own docstrings) or broken. Under ``--runtime`` the number that
matters is *nonzero*, since every tick is paid something. *Distinct
frames* is how much of what the learner sees actually changes; a
turn-based task where most actions are refused will report far fewer
than it took steps, and that is the task being honest rather than the
driver losing them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import random
import sys

from nwenv import catalog


def main(name, steps, seed=0, runtime=False, **dials):
    if runtime:
        dials['neutral_outcomes'] = True
    env = catalog.env_class(name)(seed=seed, **dials)
    rng = random.Random(seed)
    scalars, frames = [], set()
    try:
        for _step in range(steps):
            obs, events, done = env.step(rng.randrange(env.n_actions))
            frames.add(obs['rgba'])
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done:
                break
    finally:
        env.close()
    live = [value for value in scalars if value]
    print('%-18s %5d steps  %4d outcomes  %4d nonzero (%5.1f%%)  '
          'scalars %-24s  frames %d'
          % (name, steps, len(scalars), len(live),
             100.0 * len(live) / max(1, steps),
             {value: scalars.count(value) for value in sorted(set(scalars))},
             len(frames)))
    return scalars


if __name__ == '__main__':
    argv = [arg for arg in sys.argv[1:] if arg != '--runtime']
    runtime = '--runtime' in sys.argv
    steps = int(argv[1]) if len(argv) > 1 else 400
    if argv[0] == '--all':
        for row in catalog.overlays():
            main(row.task_id, steps, runtime=runtime)
    else:
        main(argv[0], steps, runtime=runtime)
