[![Build status](https://github.com/torarinvik/neural-workshop/actions/workflows/zip.yml/badge.svg?branch=master)](https://github.com/torarinvik/neural-workshop/actions/workflows/zip.yml)

# Neural Workshop

Neural Workshop is a cognitive-training workshop built on
[Brain Workshop](http://brainworkshop.sourceforge.net), the Dual N-Back
trainer. Alongside the original n-back game it offers some 250 tasks in
fourteen categories, from working memory and perception to planning,
reasoning, decision making and computer use. Every task can be played by
a person and driven by a learning agent through the same screen, so what
the agent learns from is exactly what a player sees.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running](#running)
- [Media libraries](#media-libraries)
- [Agent environment](#agent-environment)
- [Project layout](#project-layout)
- [Development](#development)
- [Documentation](#documentation)
- [License](#license)

## Features

- **Dual N-Back and its variants**, as in Brain Workshop, with screen
  elements and fonts that scale to any window size and resolution.
- **A task hub** of about 250 tasks across fourteen categories: working
  memory, long-term memory, attention, perception, reasoning, planning,
  self-control, decision making, computer use, emotion, social,
  rationality, accuracy and order, and first steps. Most are graded on a
  ladder of rungs, each rung adding one thing.
- **An agent boundary** (`nwenv`): stepped, seedable environments whose
  observations are pixels and sound only, with outcomes read off the
  rendered frame and verifiable by a third party.
- **Optional native kernels** in C for the heaviest loops, with a pure
  Python fallback.

## Requirements

- Python 3.11 or later (3.11 and 3.13 are tested)
- [pyglet](https://pyglet.org) 2
- [python-chess](https://python-chess.readthedocs.io) and
  [MuJoCo](https://mujoco.org) 3.2 (for the chess tasks and the Marble
  Maze's physics)
- Optional: a C compiler, to build the native kernels; `ffmpeg`, for
  the video tasks; `pyarrow`, for faster bulk media downloads

## Installation

Windows builds are published on the
[releases page](https://github.com/torarinvik/neural-workshop/releases).
To run from source:

```bash
git clone https://github.com/torarinvik/neural-workshop.git
cd neural-workshop
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python setup.py build_ext --inplace   # optional native kernels
```

With [uv](https://docs.astral.sh/uv/), `uv venv --python 3.13` and
`uv pip install -r requirements.txt --python .venv/bin/python` do the
same.

The native extension, `bwcore`, speeds up sequence construction,
scoring and stats parsing; without it the `bwaccel` package falls back
to equivalent Python. The title screen shows `native: C` or
`native: Python` so you can see which is in use.

## Running

```bash
./run                              # uses .venv
.venv/bin/python brainworkshop.py  # the same, by hand
```

On the title screen, press **Space** to open the task hub (arrow keys
choose a category and a task; **Esc** goes back) or **C** to choose an
n-back game mode. Settings live in `config.ini` in the data folder,
which is created on first launch; `--datadir` and `--resdir` point the
game at other folders.

## Media libraries

Some tasks play on photographs, sound clips and video that are too
large to ship, so they are downloaded once on request; nothing
downloads on its own, and a task whose library is missing says so.

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
  command of its own, `python -m neural_workshop.trivia`, and it is
  described in the [task reference](docs/TASKS.md#trivia).

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

## Agent environment

The `nwenv` package wraps every task as a stepped environment. Each step
returns the next rendered frame (RGBA, a sequence number and a
timestamp) and any outcome events; actions are opaque port indices, and
an outcome is a scalar read off the frame's verdict label together with
the SHA-256 digests of the frames it was read from.

```python
from nwenv import catalog

env = catalog.env_class('short_maze')(seed=1, rung=3, trials=20)
obs, events, done = env.step(None)   # a frame, no press
obs, events, done = env.step(2)      # press port 2
env.close()
```

`nwenv.catalog` lists every task (`task_ids()`, `env_class()`), its
family and twin, and gives each a card (`card(task_id)`) with its ports,
its clock and, for the first-steps families, its chance levels.
Clocked tasks take `frame_hz`; every task takes `frame_scale` to read
frames back at a half or a quarter of each side. The n-back game itself
is `nwenv.NeuralWorkshopEnv`. See [docs/AGENT_ENV.md](docs/AGENT_ENV.md)
for the full contract and [ADDING_A_TASK.md](ADDING_A_TASK.md) for
writing a wrapper.

## Project layout

| Path | Contents |
| --- | --- |
| `brainworkshop.py` | Entry point, and a thin facade over the packages below |
| `neural_workshop/` | The game: configuration, state, modes, scoring, sessions, and every task's model; screens under `ui/` |
| `nwenv/` | The agent boundary: frame capture, outcomes and their verification, and the stepped environments |
| `bwaccel/` | Accelerated kernels, using the `bwcore` C extension when built and Python otherwise |
| `native/` | Source of the `bwcore` extension |
| `res/` | Images, sounds, music and translations |
| `tests/` | The test suite |
| `tools/` | Maintenance scripts: freezing, media indexing, benchmarks |
| `docs/` | Task reference and technical notes |

Task models that need no window (puzzle generators, word lists, the
Matrix Reasoning generator in `neural_workshop/ravens/`) import no
pyglet, so they can be built and checked headlessly.
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) covers the code layout in
more depth.

## Development

The tests use the standard library's `unittest` and run from the
`tests` folder:

```bash
cd tests
PYTHONPATH=.. ../.venv/bin/python -m unittest test_firststeps test_env_tasks
PYTHONPATH=.. ../.venv/bin/python -m unittest discover   # everything
```

The full suite is long (the better part of an hour); run the modules
for the area you are working on while developing. Tests that need a
window skip themselves when pyglet cannot open one.

New tasks follow [ADDING_A_TASK.md](ADDING_A_TASK.md): a model, a
screen, a wrapper, an entry in the catalogue and the task hub, and a
section in [docs/TASKS.md](docs/TASKS.md).

## Documentation

| Document | Contents |
| --- | --- |
| [docs/TASKS.md](docs/TASKS.md) | Every task in the hub: what it asks, how its rungs grow, and its options |
| [docs/AGENT_ENV.md](docs/AGENT_ENV.md) | The agent environment: observations, actions, outcomes, verification |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Code layout, coordinate spaces, timing, the native kernels |
| [ADDING_A_TASK.md](ADDING_A_TASK.md) | Writing a task and its wrapper |
| [docs/HISTORY.md](docs/HISTORY.md) | Changes made when the fork began |
| [docs/BRAIN_WORKSHOP.md](docs/BRAIN_WORKSHOP.md) | The original Brain Workshop readme and changelog |
| [Readme-instructions.txt](Readme-instructions.txt) | How to play Dual N-Back |

## License

Neural Workshop is free software under the GNU General Public License,
version 2 or later; see [LICENSE.md](LICENSE.md). It is a fork of Brain
Workshop. The media libraries fetched for some tasks keep their own
licenses, given in [Media libraries](#media-libraries).
