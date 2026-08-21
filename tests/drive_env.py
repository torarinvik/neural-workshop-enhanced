"""Play a wrapped task at random and say whether the boundary paid it.

    PYTHONPATH=.. ../.venv/bin/python drive_env.py removals 400
    PYTHONPATH=.. ../.venv/bin/python drive_env.py --all 700

The task names are the ones in :mod:`nwenv.catalog`, which is also
where the list comes from — there is no second list here to fall out
of step with it.

One task at a time: these bind shared-memory segments and two workshop
instances at once risk a name collision. ``--all`` runs them in
sequence for that reason, and it is slow.

What the numbers mean. *Outcomes* is how many scalars a run of random
actions was paid, and it is not a score — it is whether the boundary
is wired up at all. A task reporting zero is either not reachable by
random play (which several are not, and the sparse ones say so in
their own docstrings) or broken. *Distinct frames* is how much of what
the learner sees actually changes; a turn-based task where most
actions are refused will report far fewer than it took steps, and that
is the task being honest rather than the driver losing them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import random
import sys

from nwenv import catalog


def main(name, steps, seed=0, **dials):
    env = catalog.env_class(name)(seed=seed, **dials)
    rng = random.Random(seed)
    paid, scalars, frames = 0, [], set()
    try:
        for _step in range(steps):
            obs, events, done = env.step(rng.randrange(env.n_actions))
            frames.add(obs['rgba'])
            for event in events:
                if event.get('type') == 'outcome':
                    paid += 1
                    scalars.append(event['scalar'])
            if done:
                break
    finally:
        env.close()
    print('%-18s %5d steps  %3d outcomes  scalars %-22s  frames %d'
          % (name, steps, paid,
             {value: scalars.count(value) for value in sorted(set(scalars))},
             len(frames)))
    return paid, scalars


if __name__ == '__main__':
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    if sys.argv[1] == '--all':
        for row in catalog.overlays():
            main(row.task_id, steps)
    else:
        main(sys.argv[1], steps)
