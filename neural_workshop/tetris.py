# -*- coding: utf-8 -*-
"""Freeform Tetris: a fine grid, pieces you pick, and a promise kept.

Four guarantees hold this module together:

* **Every piece on offer fits somewhere with no gap under it.** The
  pieces are not drawn from a bag of seven. They are cut out of the
  board's own skyline: :func:`carve` takes a window of columns, reads
  the height of each, and builds the polyomino that fills that notch
  flush to a level top. Such a piece dropped back into the notch it
  came from rests on solid cells all along its underside, so it adds
  no covered hole. That is a construction, not a hope, and the
  argument for it is written out over :func:`carve`.

* **The construction is checked rather than trusted.**
  :func:`perfect_placements` enumerates the four lattice orientations
  at every column, hard-drops each one, and keeps those that cover
  nothing. The generator runs it over what it has just cut; the
  :class:`Queue` runs it over every piece it holds after every
  placement, and re-cuts any piece whose fit the last move destroyed.
  So the promise is not *was true when dealt* — it is *is true now*,
  and the screen prints the count each piece currently has.

* **The freedom to spin costs something, and the cost is stated.**
  A piece may be held at any angle in the full 360, and what lands is
  what the grid sees: :func:`footprint` fills every cell whose centre
  falls inside the turned piece. At an angle that is not a quarter
  turn a square's rasterisation is ragged, so it very nearly always
  covers something. Within :data:`SNAP_DEGREES` of a quarter turn the
  pose is pulled onto the lattice by :func:`snapped` and the
  footprint is the whole polyomino again, exactly. **The gapless play
  the first guarantee promises therefore exists at lattice angles**,
  and the free spin is the risk the player may take on top of it,
  never a way the promise can be lost.

* **Difficulty is shape, and only shape.** A rung of the ladder says
  how many cells a piece may have, how many columns it may straddle,
  how uneven a skyline it may be cut from and how uneven a top it may
  be given. No rung says anything about speed — gravity is the
  player's own setting and every rung falls at it. Climbing the
  ladder makes the packing harder to see, never harder to reach.

Row 0 is the floor and y counts upward, which is the direction
gravity, the skyline and pyglet all already agree on.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import (Dict, FrozenSet, Iterable, List, NamedTuple, Optional,
                    Sequence, Set, Tuple)

#: A cell of the grid, as (column, row).
Cell = Tuple[int, int]

#: A piece: its cells in its own frame, normalised so the lowest row
#: and leftmost column are both zero. Frozen because pieces are shared
#: between the queue, the falling piece and the placement search, and
#: a piece that changed under one of them would be a bug nothing
#: catches.
Piece = FrozenSet[Cell]

#: How near a quarter turn still counts as *on* the grid, in degrees.
#: Wide enough to catch by hand while a piece is falling, narrow
#: enough that a pose meant to be crooked stays crooked.
SNAP_DEGREES: float = 7.0

#: How far a free-angle piece is moved down between collision tests
#: while it is being dropped, in cells. Eighths, because a rasterised
#: footprint changes on cell boundaries and nothing finer can change
#: the answer — but it can change *when* the answer arrives, and a
#: piece that tunnelled through a one-cell ledge would be a gap the
#: player never chose.
DROP_STEP: float = 0.125


# --- the board -----------------------------------------------------------

class Board:
    """A fine grid of cells, row 0 at the floor.

    Much wider and much finer than a tetris well: the point of the
    grid is that a piece is small against it, so where a piece goes is
    a question with many answers rather than ten.
    """

    __slots__ = ('cols', 'rows', 'cells', '_sky')

    def __init__(self, cols: int, rows: int) -> None:
        self.cols = int(cols)
        self.rows = int(rows)
        self.cells: List[bytearray] = [bytearray(self.cols)
                                       for _ in range(self.rows)]
        self._sky: Optional[List[int]] = None

    def copy(self) -> 'Board':
        twin = Board(self.cols, self.rows)
        twin.cells = [bytearray(row) for row in self.cells]
        return twin

    def filled(self, x: int, y: int) -> bool:
        """True when (x, y) is inside the board and occupied."""
        return (0 <= x < self.cols and 0 <= y < self.rows
                and bool(self.cells[y][x]))

    def fill(self, x: int, y: int, value: int = 1) -> None:
        """Occupy (x, y), optionally carrying a byte of the caller's own.

        Everything in this module asks a cell only whether it is
        truthy, so a screen may store which piece filled it — a colour
        index, one past zero — and get the pile's colouring carried
        through line clears for free rather than keeping a second grid
        beside this one and hoping the two stay in step.
        """
        if 0 <= x < self.cols and 0 <= y < self.rows:
            self.cells[y][x] = value & 0xFF or 1
            self._sky = None

    def skyline(self) -> List[int]:
        """Per column, the first row that is free of anything stacked.

        One past the topmost filled cell, so a piece whose lowest cell
        in a column rests here touches down on it. Everything at or
        above this row is empty by definition; everything empty
        *below* it is a hole, which is the quantity this whole module
        exists to keep at zero.
        """
        if self._sky is None:
            sky = [0] * self.cols
            for y in range(self.rows - 1, -1, -1):
                row = self.cells[y]
                for x in range(self.cols):
                    if row[x] and sky[x] == 0:
                        sky[x] = y + 1
            self._sky = sky
        return self._sky

    def holes(self) -> int:
        """Empty cells with something stacked over them."""
        sky = self.skyline()
        total = 0
        for x in range(self.cols):
            for y in range(sky[x]):
                if not self.cells[y][x]:
                    total += 1
        return total

    def clear_full_rows(self) -> int:
        """Drop every complete row and settle what was above it."""
        keep = [row for row in self.cells if not all(row)]
        cleared = self.rows - len(keep)
        if cleared:
            keep.extend(bytearray(self.cols) for _ in range(cleared))
            self.cells = keep
            self._sky = None
        return cleared


# --- pieces --------------------------------------------------------------

def normalise(cells: Iterable[Cell]) -> Piece:
    """Slide *cells* until their lowest row and leftmost column are 0."""
    cells = list(cells)
    left = min(x for x, _y in cells)
    floor = min(y for _x, y in cells)
    return frozenset((x - left, y - floor) for x, y in cells)


def extent(cells: Piece) -> Tuple[int, int]:
    """The width and height of a normalised piece, in cells."""
    return (max(x for x, _y in cells) + 1, max(y for _x, y in cells) + 1)


def quarter_turn(cells: Piece, quarter: int) -> Piece:
    """*cells* turned anticlockwise by *quarter* right angles."""
    turned = cells
    for _ in range(quarter % 4):
        turned = normalise((-y, x) for x, y in turned)
    return turned


def orientations(cells: Piece) -> List[Tuple[int, Piece]]:
    """The distinct lattice orientations, as (quarter, cells).

    A square has one, a domino two, most pieces four. Counted rather
    than assumed, so the number of placements the screen reports is
    the number of genuinely different things a player could do — a
    square that reported four identical drops would be advertising a
    choice it does not offer.
    """
    seen: Set[Piece] = set()
    found: List[Tuple[int, Piece]] = []
    for quarter in range(4):
        turned = quarter_turn(cells, quarter)
        if turned not in seen:
            seen.add(turned)
            found.append((quarter, turned))
    return found


def cells_at(cells: Piece, col: int, row: int) -> Set[Cell]:
    """*cells* translated so its own origin sits at (col, row)."""
    return {(col + x, row + y) for x, y in cells}


# --- where a piece would land, and what it would cover --------------------

class Placement(NamedTuple):
    """A lattice drop: which quarter turn, which column, which row."""

    quarter: int
    col: int
    row: int


def landing(board: Board, cells: Piece, col: int,
            sky: Optional[Sequence[int]] = None) -> Optional[int]:
    """The row a hard drop of *cells* down column *col* comes to rest at.

    ``None`` when the piece hangs off either side. Read straight off
    the skyline rather than simulated: every cell at or above the
    skyline is empty, so the first contact is whichever of the piece's
    lowest cells reaches its own column's skyline first.
    """
    width, _height = extent(cells)
    if col < 0 or col + width > board.cols:
        return None
    sky = board.skyline() if sky is None else sky
    lowest: Dict[int, int] = {}
    for x, y in cells:
        if y < lowest.get(x, board.rows + 1):
            lowest[x] = y
    return max(sky[col + x] - low for x, low in lowest.items())


def gaps_under(board: Board, footprint: Iterable[Cell],
               sky: Optional[Sequence[int]] = None) -> int:
    """How many empty cells *footprint* would bury.

    The one definition of a gap in this game, and everything else
    asks it rather than keeping an opinion of its own. A cell counts
    when it is empty, is not part of the piece, sits at or above its
    column's skyline — so it is not already buried — and has some
    part of the piece above it. Those are exactly the cells that
    become holes, because the piece is the only thing being added.

    Works for a rasterised, ragged footprint as well as a lattice
    one, which is what makes the free spin measurable on the same
    scale as everything else.
    """
    sky = board.skyline() if sky is None else sky
    footprint = set(footprint)
    ceiling: Dict[int, int] = {}
    for x, y in footprint:
        if y > ceiling.get(x, -1):
            ceiling[x] = y
    buried = 0
    for x, top in ceiling.items():
        if not 0 <= x < board.cols:
            continue
        for y in range(sky[x], top):
            if (x, y) not in footprint:
                buried += 1
    return buried


def perfect_placements(board: Board, piece: Piece,
                       limit: int = 0) -> List[Placement]:
    """Every lattice drop of *piece* that buries nothing.

    This is the proof obligation of the whole module, discharged by
    enumeration: four orientations by every column the piece fits in,
    each hard-dropped and then asked what it would cover. Cheap enough
    to run on the entire queue after every placement — a few hundred
    drops of a handful of cells each — which is why the promise can be
    re-checked continuously rather than made once and hoped over.

    *limit* stops early, for callers that only need to know whether
    one exists.
    """
    sky = board.skyline()
    found: List[Placement] = []
    for quarter, turned in orientations(piece):
        width, height = extent(turned)
        for col in range(board.cols - width + 1):
            row = landing(board, turned, col, sky)
            if row is None or row + height > board.rows:
                continue
            if not gaps_under(board, cells_at(turned, col, row), sky):
                found.append(Placement(quarter, col, row))
                if limit and len(found) >= limit:
                    return found
    return found


def fits_somewhere(board: Board, piece: Piece) -> bool:
    """Whether *piece* has any gapless drop left on this board."""
    return bool(perfect_placements(board, piece, limit=1))


# --- holding a piece at an arbitrary angle --------------------------------

class Pose(NamedTuple):
    """A falling piece: its angle in degrees, and where its centre is.

    The centre is the middle of the piece's own bounding box, in board
    cells, and it is what the piece turns about — so a spin does not
    also shove the piece sideways.
    """

    angle: float
    cx: float
    cy: float


def _cos_sin(angle: float) -> Tuple[float, float]:
    """Cosine and sine of *angle* degrees, exact on the quarter turns.

    ``math.cos(math.radians(90))`` is 6.1e-17 rather than zero, and
    six times ten to the minus seventeen is the difference between a
    piece that rasterises to itself and one that rasterises to itself
    almost always. The lattice cases are looked up instead.
    """
    quarter, rest = divmod(angle, 90.0)
    if rest == 0.0:
        index = int(quarter) % 4
        return ((1.0, 0.0, -1.0, 0.0)[index], (0.0, 1.0, 0.0, -1.0)[index])
    radians = math.radians(angle)
    return (math.cos(radians), math.sin(radians))


def footprint(cells: Piece, pose: Pose) -> Set[Cell]:
    """The board cells the piece covers when held at *pose*.

    A cell is covered when its centre lies inside the turned piece.
    That rule is what makes an arbitrary angle mean something on a
    grid at all, and it is deliberately the plainest one available:
    area is preserved on average, the answer does not depend on which
    way the piece is being spun, and at a quarter turn it reproduces
    the polyomino exactly rather than nearly.
    """
    width, height = extent(cells)
    cos, sin = _cos_sin(pose.angle)
    reach = 0.5 * math.hypot(width, height)
    covered: Set[Cell] = set()
    for x in range(math.floor(pose.cx - reach), math.ceil(pose.cx + reach)):
        for y in range(math.floor(pose.cy - reach),
                       math.ceil(pose.cy + reach)):
            dx = x + 0.5 - pose.cx
            dy = y + 0.5 - pose.cy
            # The inverse turn: rotating the cell's centre back into
            # the piece's own frame is cheaper than turning the piece.
            local_x = dx * cos + dy * sin + width / 2.0
            local_y = -dx * sin + dy * cos + height / 2.0
            if 0.0 <= local_x < width and 0.0 <= local_y < height:
                if (int(local_x), int(local_y)) in cells:
                    covered.add((x, y))
    return covered


def snapped(cells: Piece, pose: Pose,
            tolerance: float = SNAP_DEGREES) -> Optional[Pose]:
    """*pose* pulled onto the lattice, or ``None`` if it is not close.

    A pose within *tolerance* of a quarter turn is moved to that
    quarter turn exactly and its centre to the middle of the whole
    cells it then covers. This is the only kind of pose whose
    footprint is the piece rather than a rasterisation of it, so it is
    the only kind that can be relied on to bury nothing — which is why
    it gets a corridor of a few degrees rather than having to be hit
    dead on.

    **Where the offset comes from matters.** It is read back off
    :func:`footprint` rather than worked out by rounding the centre,
    and the reason is a tie: a piece whose centre sits exactly on a
    half cell is rounded one way by ``round`` — which breaks ties to
    even — and floored the other way by the rasterisation, so the two
    disagreed about which column the piece was in about one pose in
    a hundred. On the screen that is a piece that jumps a column the
    instant it is dropped, and a ghost that was pointing at the wrong
    place while it fell. Asking the scan cannot drift from the scan.
    """
    angle = pose.angle % 360.0
    if abs((angle + 45.0) % 90.0 - 45.0) > tolerance:
        return None
    quarter = int(angle / 90.0 + 0.5) % 4
    square = Pose(quarter * 90.0, pose.cx, pose.cy)
    covered = footprint(cells, square)
    if not covered:
        return None
    width, height = extent(quarter_turn(cells, quarter))
    return Pose(quarter * 90.0,
                min(x for x, _y in covered) + width / 2.0,
                min(y for _x, y in covered) + height / 2.0)


def lattice_cells(cells: Piece, pose: Pose) -> Optional[Set[Cell]]:
    """The cells of a snapped *pose*, taken the exact way.

    Equal to :func:`footprint` of the snapped pose — the offset came
    from that scan in the first place — and kept because reading a
    piece's cells off arithmetic is both faster than a scan and
    impossible to get slightly wrong, which is what the placement
    search and the hard drop want.
    """
    lattice = snapped(cells, pose)
    if lattice is None:
        return None
    quarter = int(lattice.angle / 90.0 + 0.5) % 4
    turned = quarter_turn(cells, quarter)
    width, height = extent(turned)
    return cells_at(turned, int(lattice.cx - width / 2.0),
                    int(lattice.cy - height / 2.0))


def blocked(board: Board, cells: Piece, pose: Pose) -> bool:
    """Whether the piece at *pose* is inside a wall, the floor or the pile.

    Above the board is not blocked: a piece spawns high and has to be
    allowed to turn up there, where a corner sticking over the top is
    ordinary rather than fatal. Locking up there is what is fatal, and
    :meth:`Game.lock` is where that is decided.
    """
    for x, y in footprint(cells, pose):
        if x < 0 or x >= board.cols or y < 0:
            return True
        if y < board.rows and board.cells[y][x]:
            return True
    return False


def settle(board: Board, cells: Piece, pose: Pose,
           step: float = DROP_STEP, tolerance: float = 0.0) -> Pose:
    """*pose* dropped straight down as far as it will go.

    A pose already square to the grid falls to its skyline in one step
    of arithmetic. A crooked one is walked down in eighths of a cell,
    because its footprint changes shape as it descends and there is no
    closed form for where a rasterisation first touches.

    *tolerance* is zero here rather than :data:`SNAP_DEGREES`, and on
    purpose. Deciding that a piece a few degrees off is close enough
    to count as square is the *screen's* job — it is what the detent
    does, and a player who has turned the detent off means the tilt. A
    drop that quietly squared it up anyway would be landing a piece
    nobody aimed.
    """
    lattice = snapped(cells, pose, tolerance)
    if lattice is not None:
        quarter = int(lattice.angle / 90.0 + 0.5) % 4
        turned = quarter_turn(cells, quarter)
        width, height = extent(turned)
        col = int(lattice.cx - width / 2.0)
        row = landing(board, turned, col)
        if row is not None:
            return Pose(lattice.angle, col + width / 2.0,
                        row + height / 2.0)
    falling = pose
    while falling.cy > -board.rows:
        lower = Pose(falling.angle, falling.cx, falling.cy - step)
        if blocked(board, cells, lower):
            break
        falling = lower
    return falling


# --- the ladder ----------------------------------------------------------

class Grade(NamedTuple):
    """One rung: what shapes it cuts, and nothing at all about speed.

    Every field here is a fact about the *piece*. That is the whole
    design of the ladder: a harder rung is harder to pack, not harder
    to keep up with, so a player who has run out of ability has run
    out of it at seeing rather than at reacting. Gravity is set by the
    player once and never touched again.
    """

    name: str
    #: Fewest and most cells a piece of this rung may have.
    cells: Tuple[int, int]
    #: Fewest and most columns it may straddle. One column is a bar.
    span: Tuple[int, int]
    #: How uneven a stretch of skyline the rung will cut from, in
    #: cells. Zero means only level ground, which is what makes the
    #: bottom of the ladder rectangles: a flat cut with a flat top is
    #: a rectangle and cannot be anything else.
    step: int
    #: How uneven a *top* it gives the piece it cut. Zero leaves the
    #: top level; the piece is then exactly the notch it came out of.
    roughness: int


#: Rectangles to thickets. The two axes climb in step but do different
#: work: *step* is how ragged the ground a piece is shaped against may
#: be, and *roughness* is how ragged the piece is on the side nothing
#: shaped it. The first makes a piece that fits one place well; the
#: second makes the place it leaves behind worse, which is what turns
#: a packing puzzle into a planning one. Neither touches the clock.
GRADES: Tuple[Grade, ...] = (
    Grade('first blocks', (2, 4), (1, 2), 0, 0),
    Grade('longer blocks', (2, 6), (1, 3), 0, 0),
    Grade('one step', (3, 6), (2, 3), 1, 0),
    Grade('tetromino country', (3, 7), (2, 4), 1, 1),
    Grade('pentominoes', (4, 9), (2, 4), 2, 1),
    Grade('combs', (5, 11), (3, 5), 2, 2),
    Grade('sprawl', (6, 14), (3, 6), 3, 2),
    Grade('thicket', (8, 18), (4, 7), 4, 3),
)


def grade_at(rung: int) -> Grade:
    """The rung of the ladder, counted from one and clamped."""
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


# --- cutting a piece out of the skyline ----------------------------------

def _bridge(base: Sequence[int], tops: List[int]) -> None:
    """Raise tops until neighbouring columns actually touch.

    Two columns of a piece are joined when their cells overlap in some
    row. Give them independently dented tops and they need not, and a
    piece in two halves is not a piece. Raising is the repair that
    cannot fail: it only ever adds cells, and adding a cell to a column
    can never separate it from anything.
    """
    for i in range(1, len(base)):
        need = max(base[i - 1], base[i]) + 1
        if tops[i - 1] < need:
            tops[i - 1] = need
        if tops[i] < need:
            tops[i] = need


def _bar(board: Board, grade: Grade) -> Piece:
    """The fallback: an upright bar over the shallowest column.

    Wanted rarely — when the rung will not cut from any window the
    board currently offers — and it has to be something the promise
    still holds for. An upright bar is: its lowest cell rests on the
    skyline of the one column it is in, and it has no second column to
    leave hanging, so it buries nothing wherever it goes. It is also
    the *only* shape with that property on every board, which is why
    the fallback is this and not something prettier.
    """
    sky = board.skyline()
    column = min(range(board.cols), key=lambda x: sky[x])
    room = board.rows - 1 - sky[column]
    height = max(1, min(grade.cells[0], room))
    return normalise((0, y) for y in range(height))


def carve(board: Board, grade: Grade, rng: random.Random,
          attempts: int = 32, shortlist: int = 8) -> Piece:
    """Cut a piece out of the board's own skyline.

    Take a window of columns, read the height of each, and fill the
    notch to a level top: column *i* of the piece runs from the
    skyline of its column up to that level. Then dent the top by up to
    the rung's roughness, and raise whatever that separated back into
    contact.

    **Why the piece fits.** Drop what came out back where it came
    from. Each of the piece's columns has its lowest cell exactly at
    that column's skyline, so :func:`landing` puts every one of them
    down at once, the piece lands at the height it was cut from, and
    each column's cells run unbroken from the skyline upward. Nothing
    empty ends up underneath any of them, so :func:`gaps_under`
    returns zero — which is the definition the rest of the module
    uses. The dents are cut out of the *top*, and nothing about a top
    can bury anything.

    That argument is why one placement always exists. The caller is
    still expected to ask :func:`perfect_placements` how many there
    are, because a proof about the piece the generator meant to make
    is not a proof about the piece it made.

    **Why the lowest window wins.** Up to *shortlist* windows are
    tried and the one sitting lowest is the one cut from. The piece is
    the same kind of piece either way; what changes is the board a
    hundred pieces later. Measured over 750 placements of the seventh
    rung against a generator that took the first window it liked: mean
    pile height 9.3 rather than 16.6, and 49 re-cuts rather than 130.
    Both come from the same thing — a level board has more stretches
    of skyline that match any given piece, so pieces keep having
    somewhere to go and the queue keeps its promise without being
    re-cut. It levels the pile rather than towering it, which is the
    difference between a rung that is hard and one that is short.
    """
    sky = board.skyline()
    least, most = grade.cells
    narrowest, widest = grade.span
    ceiling = board.rows - 1
    cut: List[Tuple[int, Piece]] = []
    for _attempt in range(attempts):
        width = rng.randint(narrowest, min(widest, board.cols))
        start = rng.randrange(board.cols - width + 1)
        base = sky[start:start + width]
        if max(base) - min(base) > grade.step:
            continue
        # A level top at height *top* spends width*top - sum(base)
        # cells, which is monotone in top, so the rung's cell budget
        # is a range of tops and picking one is picking a piece.
        stacked = sum(base)
        lowest = max(max(base) + 1, -((-(least + stacked)) // width))
        highest = min((most + stacked) // width, ceiling)
        if lowest > highest:
            continue
        tops = [rng.randint(lowest, highest)] * width
        if grade.roughness:
            tops = [max(base[i] + 1, tops[i] - rng.randint(0, grade.roughness))
                    for i in range(width)]
            _bridge(base, tops)
        if max(tops) > ceiling:
            continue
        if not least <= sum(t - b for t, b in zip(tops, base)) <= most:
            continue
        cut.append((max(base), normalise((i, y) for i in range(width)
                                         for y in range(base[i], tops[i]))))
        if len(cut) >= shortlist:
            break
    if not cut:
        return _bar(board, grade)
    return min(cut, key=lambda found: found[0])[1]


# --- the hand of pieces on offer ------------------------------------------

class Queue:
    """The pieces the player may choose between, kept honest.

    The queue is the whole of the promise this game makes, so it is
    the queue that carries the checking. After every placement each
    piece is asked how many gapless drops it still has; a piece the
    last move left with none is cut again against the board as it now
    is. What the screen shows beside each piece is that count, so the
    promise is on display rather than in a docstring.

    Re-cutting is not a courtesy, it is the only way the promise can
    be kept while the player, not the game, chooses the order. A hand
    dealt against one skyline is a hand about a board that no longer
    exists.
    """

    def __init__(self, board: Board, grade: Grade, rng: random.Random,
                 size: int = 5) -> None:
        self.board = board
        self.grade = grade
        self.rng = rng
        self.pieces: List[Piece] = [carve(board, grade, rng)
                                    for _ in range(max(1, size))]
        self.fits: List[int] = [0] * len(self.pieces)
        #: Which slots the last :meth:`revalidate` had to cut again.
        #: Shown briefly, because a piece that changed while the
        #: player was looking at it should say so.
        self.recut: List[bool] = [False] * len(self.pieces)
        self.revalidate()

    def __len__(self) -> int:
        return len(self.pieces)

    def revalidate(self) -> int:
        """Re-count every piece's fits and re-cut those left with none.

        Returns how many had to be cut again.
        """
        again = 0
        for index, piece in enumerate(self.pieces):
            found = perfect_placements(self.board, piece)
            self.recut[index] = False
            if not found:
                self.pieces[index] = carve(self.board, self.grade, self.rng)
                found = perfect_placements(self.board, self.pieces[index])
                self.recut[index] = True
                again += 1
            self.fits[index] = len(found)
        return again

    def take(self, index: int) -> Piece:
        """Hand out the piece in *index* and cut a fresh one behind it."""
        index = max(0, min(len(self.pieces) - 1, int(index)))
        piece = self.pieces[index]
        self.pieces[index] = carve(self.board, self.grade, self.rng)
        self.fits[index] = len(perfect_placements(self.board,
                                                  self.pieces[index]))
        self.recut[index] = False
        return piece

    def promise_kept(self) -> bool:
        """Whether every piece on offer has somewhere gapless to go."""
        return all(count > 0 for count in self.fits)


def centres(cells: Piece, pose: Pose) -> List[Tuple[float, float]]:
    """Where each of the piece's own squares has its middle, in cells.

    A screen drawing a piece at an angle the grid does not have needs
    the piece itself, turned — not the cells it happens to cover. Those
    are two different pictures at every angle but a quarter turn, and
    showing both is how a player sees what the spin is costing:
    :func:`footprint` is what will land, this is what is being held,
    and they coincide exactly when the piece is square to the grid.

    In the same order as ``sorted(cells)``, so a caller may pair these
    up with anything else it sorted the same way.
    """
    width, height = extent(cells)
    cos, sin = _cos_sin(pose.angle)
    placed = []
    for x, y in sorted(cells):
        dx = x + 0.5 - width / 2.0
        dy = y + 0.5 - height / 2.0
        placed.append((pose.cx + dx * cos - dy * sin,
                       pose.cy + dx * sin + dy * cos))
    return placed
