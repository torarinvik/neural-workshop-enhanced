# -*- coding: utf-8 -*-
"""``python -m nwenv``: run one session and print the accounting.

With ``--sight`` it drives Out of Sight instead of the n-back workshop.
That run is clocked rather than slept through, so a step is a rendered
tick and the whole thing finishes as fast as the frames can be drawn
and read back. That is a few milliseconds each, and a default run is
five rounds of six questions, so expect a minute or so.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import sys

from . import format_accounting, make_env, make_sight_env

#: Safety stop, so a stuck session cannot spin forever. Out of Sight
#: needs the larger one: its steps are frames, not trials.
MAX_STEPS = 400
MAX_SIGHT_STEPS = 12000


def main() -> None:
    sight = '--sight' in sys.argv[1:]
    env = make_sight_env(seed=1) if sight else make_env(seed=1)
    limit = MAX_SIGHT_STEPS if sight else MAX_STEPS
    try:
        done = False
        steps = 0
        while not done and steps < limit:
            _obs, _events, done = env.step([])
            steps += 1
        print(format_accounting(env.accounting))
        print('steps=%i done=%s' % (steps, done))
    finally:
        env.close()


if __name__ == '__main__':
    main()
