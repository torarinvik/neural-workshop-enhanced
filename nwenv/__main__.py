# -*- coding: utf-8 -*-
"""``python -m nwenv``: run one session and print the accounting.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from . import format_accounting, make_env

#: Safety stop, so a stuck session cannot spin forever.
MAX_STEPS = 400


def main() -> None:
    env = make_env(seed=1)
    try:
        done = False
        steps = 0
        while not done and steps < MAX_STEPS:
            _obs, _events, done = env.step([])
            steps += 1
        print(format_accounting(env.accounting))
        print('steps=%i done=%s' % (steps, done))
    finally:
        env.close()


if __name__ == '__main__':
    main()
