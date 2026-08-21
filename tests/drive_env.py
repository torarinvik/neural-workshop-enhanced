"""Play a wrapped task at random and say whether the boundary paid it.

    PYTHONPATH=.. ../.venv/bin/python drive_env.py removals 400

One task at a time: these bind shared-memory segments and two workshop
instances at once risk a name collision.
"""
import importlib
import random
import sys

WRAPPED = {
    'removals': ('nwenv.removals', 'RemovalsEnv'),
    'crossedwires': ('nwenv.crossedwires', 'CrossedWiresEnv'),
    'youarehere': ('nwenv.youarehere', 'YouAreHereEnv'),
    'inthedark': ('nwenv.inthedark', 'InTheDarkEnv'),
    'sudoku': ('nwenv.sudoku', 'SudokuEnv'),
    'maze': ('nwenv.maze', 'MazeEnv'),
    'sokoban': ('nwenv.sokoban', 'SokobanEnv'),
    'hanoi': ('nwenv.hanoi', 'HanoiEnv'),
}


def main(name, steps, seed=0, **dials):
    where, klass = WRAPPED[name]
    env = getattr(importlib.import_module(where), klass)(seed=seed, **dials)
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
    print('%-14s %4d steps  %3d outcomes  scalars %s  distinct frames %d'
          % (name, steps, paid,
             {value: scalars.count(value) for value in sorted(set(scalars))},
             len(frames)))
    return paid, scalars


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 400)
