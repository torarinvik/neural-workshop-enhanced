#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Freeform Tetris: the promise, and the price of the free spin.

The module promises that every piece on offer has somewhere to go that
buries nothing, and that the promise survives whatever order the
player takes the pieces in. That is not a claim about a generator in
isolation — it is a claim about a generator and a board that keeps
changing under it — so most of this file is a reference player: one
that always takes a gapless drop, run for hundreds of placements on
every rung, checking after each that the hole count has not moved.

The other half is the free rotation, where the interesting property is
the one that *fails*. A piece held at an angle the grid does not have
lands as a rasterisation of itself, which is a different shape; the
tests here pin down where the two agree exactly (the quarter turns,
from any offset) and where they do not (everywhere else), because the
whole trade the game offers rests on that line being in a knowable
place.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (TASKS, close_overlays, display, key, needs_ui,
                       reset_window, taskoptions)

from neural_workshop import tetris
from neural_workshop.tetris import (GRADES, Board, Pose, Queue, carve,
                                    cells_at, centres, extent, footprint,
                                    gaps_under, grade_at, landing,
                                    lattice_cells, normalise, orientations,
                                    perfect_placements, quarter_turn, settle,
                                    snapped)

try:
    from uisupport import FreeformTetris
except ImportError:                      # pragma: no cover - no GL context
    FreeformTetris = None


#: A few pieces with different symmetry, named for what they test.
SQUARE = normalise([(0, 0), (1, 0), (0, 1), (1, 1)])
DOMINO = normalise([(0, 0), (1, 0)])
ELL = normalise([(0, 0), (0, 1), (0, 2), (1, 0)])
TEE = normalise([(0, 0), (1, 0), (2, 0), (1, 1)])
COMB = normalise([(0, 0), (1, 0), (2, 0), (0, 1), (2, 1)])
#: Big enough that a few degrees of tilt moves a cell centre across a
#: cell boundary, which the small pieces do not.
SLAB = normalise([(x, y) for x in range(5) for y in range(3)])
SHAPES = (SQUARE, DOMINO, ELL, TEE, COMB)


def flat(cols, rows, height):
    """A board filled solid to *height* in every column."""
    board = Board(cols, rows)
    for x in range(cols):
        for y in range(height):
            board.fill(x, y)
    return board


class PieceGeometryTests(unittest.TestCase):
    """Turning, normalising and counting distinct orientations."""

    def test_normalising_puts_a_piece_at_the_origin(self):
        moved = normalise([(4, 7), (5, 7), (4, 8)])
        self.assertEqual(sorted(moved), [(0, 0), (0, 1), (1, 0)])

    def test_four_quarter_turns_are_the_identity(self):
        for shape in SHAPES:
            self.assertEqual(quarter_turn(shape, 4), shape)

    def test_a_turn_swaps_the_extent(self):
        for shape in SHAPES:
            width, height = extent(shape)
            self.assertEqual(extent(quarter_turn(shape, 1)), (height, width))

    def test_symmetry_is_counted_rather_than_assumed(self):
        """A square offers one placement per column, not four."""
        self.assertEqual(len(orientations(SQUARE)), 1)
        self.assertEqual(len(orientations(DOMINO)), 2)
        self.assertEqual(len(orientations(ELL)), 4)
        self.assertEqual(len(orientations(TEE)), 4)

    def test_a_piece_keeps_its_cells_through_a_turn(self):
        for shape in SHAPES:
            for quarter in range(4):
                self.assertEqual(len(quarter_turn(shape, quarter)),
                                 len(shape))


class RasterisationTests(unittest.TestCase):
    """Where the drawn piece and the landed piece agree, and where not."""

    def test_a_quarter_turn_rasterises_to_itself_from_any_offset(self):
        """The one property the whole snap rests on.

        At a quarter turn the footprint is the polyomino translated by
        a whole number of cells — not nearly, exactly, and not only
        from centres that happen to be half-integers. If this were
        merely usually true, a promise of a gapless drop would be
        merely usually keepable.
        """
        for shape in SHAPES:
            for quarter in range(4):
                turned = quarter_turn(shape, quarter)
                width, height = extent(turned)
                for offset in (0.0, 0.1, 0.37, 0.5, 0.9, 3.25):
                    pose = Pose(quarter * 90.0, 7.0 + offset,
                                5.0 + offset)
                    covered = footprint(shape, pose)
                    self.assertEqual(len(covered), len(shape),
                                     (quarter, offset))
                    left = min(x for x, _y in covered)
                    floor = min(y for _x, y in covered)
                    self.assertEqual(covered,
                                     cells_at(turned, left, floor),
                                     (quarter, offset))
                    self.assertEqual(extent(normalise(covered)),
                                     (width, height))

    def test_the_exact_route_and_the_scan_agree_on_the_grid(self):
        """``lattice_cells`` is arithmetic and ``footprint`` is a scan.

        Two ways of asking the same question, and the game uses both —
        the placement search takes the cheap route, the lock takes the
        scan — so they had better not differ.
        """
        for shape in SHAPES:
            for quarter in range(4):
                for cx, cy in ((9.5, 6.25), (4.0, 4.0), (12.75, 3.1)):
                    pose = Pose(quarter * 90.0, cx, cy)
                    self.assertEqual(lattice_cells(shape, pose),
                                     footprint(shape, pose), (quarter, cx))

    def test_inside_the_corridor_the_two_routes_can_still_differ(self):
        """Which is why the piece is *held* at the quarter turn.

        A pose seven degrees off is inside the snapping corridor, so
        the arithmetic route squares it up — but the scan is a
        rasterisation of a piece that is still crooked, and for a slab
        five cells across those are different shapes. Measured: the
        small pieces above survive the whole corridor unchanged and
        this one does not. A game that snapped only when the piece
        locked would therefore be drawing one shape and landing
        another, on exactly the pieces where it matters most. Holding
        the piece at the quarter turn itself is what removes the
        question, and it is what the screen's detent does.
        """
        pose = Pose(tetris.SNAP_DEGREES, 9.5, 6.25)
        self.assertIsNotNone(snapped(SLAB, pose))
        self.assertNotEqual(lattice_cells(SLAB, pose),
                            footprint(SLAB, pose))

    def test_an_angle_off_the_grid_is_a_different_shape(self):
        """Which is the price the free spin charges, stated as a test."""
        crooked = frozenset(footprint(ELL, Pose(45.0, 9.0, 9.0)))
        for quarter in range(4):
            turned = quarter_turn(ELL, quarter)
            straight = {frozenset(cells_at(turned, col, row))
                        for col in range(4, 14) for row in range(4, 14)}
            self.assertNotIn(crooked, straight, quarter)

    def test_the_corridor_snaps_and_outside_it_does_not(self):
        self.assertIsNotNone(snapped(ELL, Pose(0.0, 5.0, 5.0)))
        inside = tetris.SNAP_DEGREES - 0.5
        self.assertIsNotNone(snapped(ELL, Pose(90.0 + inside, 5.0, 5.0)))
        outside = tetris.SNAP_DEGREES + 0.5
        self.assertIsNone(snapped(ELL, Pose(90.0 + outside, 5.0, 5.0)))
        self.assertIsNone(snapped(ELL, Pose(45.0, 5.0, 5.0)))

    def test_a_snapped_pose_is_exactly_a_quarter_turn(self):
        for angle in (0.0, 4.0, 86.0, 91.5, 179.0, 271.0, 356.0):
            pose = snapped(TEE, Pose(angle, 6.3, 4.1))
            if pose is not None:
                self.assertEqual(pose.angle % 90.0, 0.0, angle)

    def test_the_drawn_centres_are_the_cell_middles_when_square(self):
        placed = centres(TEE, Pose(0.0, 10.0, 10.0))
        width, height = extent(TEE)
        for (x, y), (bx, by) in zip(sorted(TEE), placed):
            self.assertAlmostEqual(bx, 10.0 + x + 0.5 - width / 2.0)
            self.assertAlmostEqual(by, 10.0 + y + 0.5 - height / 2.0)

    def test_a_turn_moves_no_cell_nearer_or_further(self):
        """A spin turns the piece; it does not also shove it sideways."""
        def out(spot):
            return ((spot[0] - 8.0) ** 2 + (spot[1] - 8.0) ** 2) ** 0.5

        spans = [out(spot) for spot in centres(COMB, Pose(0.0, 8.0, 8.0))]
        for angle in (17.0, 45.0, 123.5, 270.0):
            for span, spot in zip(spans,
                                  centres(COMB, Pose(angle, 8.0, 8.0))):
                self.assertAlmostEqual(out(spot), span, msg=angle)


class BoardTests(unittest.TestCase):
    """The skyline, the hole count, and where a drop comes to rest."""

    def test_the_skyline_is_one_past_the_topmost_filled_cell(self):
        board = Board(4, 6)
        board.fill(1, 0)
        board.fill(1, 1)
        board.fill(3, 4)
        self.assertEqual(board.skyline(), [0, 2, 0, 5])

    def test_a_hole_is_an_empty_cell_with_something_over_it(self):
        board = Board(3, 5)
        board.fill(0, 0)
        board.fill(0, 2)
        self.assertEqual(board.holes(), 1)
        board.fill(0, 1)
        self.assertEqual(board.holes(), 0)

    def test_a_drop_lands_on_the_skyline(self):
        board = flat(6, 10, 3)
        self.assertEqual(landing(board, SQUARE, 2), 3)
        board.fill(2, 3)
        self.assertEqual(landing(board, SQUARE, 2), 4)

    def test_a_piece_hanging_off_the_edge_has_nowhere_to_land(self):
        board = Board(4, 6)
        self.assertIsNone(landing(board, TEE, 2))

    def test_gaps_are_the_cells_the_piece_would_bury(self):
        board = flat(6, 10, 2)
        board.fill(3, 2)                       # one column stands proud
        # A domino lying across columns 2 and 3 rests on the taller one
        # and leaves the cell beside it covered and empty.
        row = landing(board, DOMINO, 2)
        self.assertEqual(gaps_under(board, cells_at(DOMINO, 2, row)), 1)
        self.assertEqual(gaps_under(board, cells_at(DOMINO, 4, 2)), 0)

    def test_clearing_a_row_settles_what_was_above_it(self):
        board = Board(3, 4)
        for x in range(3):
            board.fill(x, 0)
        board.fill(1, 1)
        self.assertEqual(board.clear_full_rows(), 1)
        self.assertEqual(board.skyline(), [0, 1, 0])

    def test_a_cell_carries_the_byte_it_was_filled_with(self):
        board = Board(2, 2)
        board.fill(0, 0, 5)
        self.assertEqual(board.cells[0][0], 5)
        self.assertTrue(board.filled(0, 0))


class PlacementSearchTests(unittest.TestCase):
    """What ``perfect_placements`` will and will not call gapless."""

    def test_flat_ground_takes_a_flat_piece_anywhere(self):
        board = flat(10, 8, 2)
        found = perfect_placements(board, DOMINO)
        # Nine lying down, ten standing up.
        self.assertEqual(len(found), 19)
        for place in found:
            turned = quarter_turn(DOMINO, place.quarter)
            self.assertEqual(gaps_under(board,
                                        cells_at(turned, place.col,
                                                 place.row)), 0)

    def test_an_overhang_over_a_pit_is_not_gapless(self):
        board = Board(3, 8)
        board.fill(0, 0)
        board.fill(2, 0)                       # a one-cell pit at column 1
        row = landing(board, TEE, 0)
        self.assertEqual(gaps_under(board, cells_at(TEE, 0, row)), 1)

    def test_a_piece_that_would_poke_out_of_the_top_is_refused(self):
        board = flat(6, 4, 3)                  # one row of headroom
        self.assertEqual(perfect_placements(board, SQUARE), [])

    def test_the_limit_stops_the_search_early(self):
        board = flat(20, 8, 1)
        self.assertEqual(len(perfect_placements(board, SQUARE, limit=1)), 1)


class LadderTests(unittest.TestCase):
    """The rungs climb by shape, and nothing on them is a clock."""

    def test_the_ladder_never_mentions_time(self):
        """The one structural promise: no rung can change the speed.

        Every field of a rung is a fact about the piece. There is no
        seconds, no rate and no delay for a rung to raise, so a run
        that climbs cannot be a run that sped up — which is what makes
        a curve drawn across the rungs a curve about packing.
        """
        for field in GRADES[0]._fields:
            self.assertNotIn(field, ('speed', 'seconds', 'rate', 'gravity',
                                     'delay', 'fall'))

    def test_every_axis_climbs_or_holds(self):
        for lower, upper in zip(GRADES, GRADES[1:]):
            self.assertLessEqual(lower.cells[1], upper.cells[1])
            self.assertLessEqual(lower.span[1], upper.span[1])
            self.assertLessEqual(lower.step, upper.step)
            self.assertLessEqual(lower.roughness, upper.roughness)

    def test_the_bottom_rung_cuts_nothing_but_rectangles(self):
        """Which is what "the easiest difficulty gives simple shapes" is.

        The first rung cuts only from level ground and gives only
        level tops, and a shape that is flat underneath and flat on
        top over a run of columns is a rectangle. Checked against a
        board that random play has left ragged, because the claim is
        about the rung and not about the board it started on.
        """
        rng = random.Random(11)
        board = Board(30, 16)
        for _placement in range(40):
            piece = carve(board, grade_at(4), rng)
            places = perfect_placements(board, piece)
            if not places:
                continue
            place = rng.choice(places)
            for x, y in cells_at(quarter_turn(piece, place.quarter),
                                 place.col, place.row):
                board.fill(x, y)
        for _cut in range(120):
            piece = carve(board, grade_at(1), rng)
            width, height = extent(piece)
            self.assertEqual(len(piece), width * height, sorted(piece))
            self.assertLessEqual(len(piece), 4)

    def test_a_higher_rung_really_does_cut_bigger_pieces(self):
        rng = random.Random(5)
        board = Board(40, 20)
        sizes = {}
        for rung in (1, 4, 8):
            sizes[rung] = max(len(carve(board, grade_at(rung), rng))
                              for _cut in range(60))
        self.assertLess(sizes[1], sizes[4])
        self.assertLess(sizes[4], sizes[8])

    def test_the_rung_number_is_clamped_rather_than_thrown(self):
        self.assertIs(grade_at(0), GRADES[0])
        self.assertIs(grade_at(-4), GRADES[0])
        self.assertIs(grade_at(99), GRADES[-1])


class ThePromiseTests(unittest.TestCase):
    """Every piece on offer has somewhere gapless to go. Checked, not said."""

    def test_a_carved_piece_fits_the_board_it_was_cut_from(self):
        rng = random.Random(3)
        for rung in range(1, len(GRADES) + 1):
            board = Board(28, 14)
            for _step in range(30):
                piece = carve(board, grade_at(rung), rng)
                places = perfect_placements(board, piece)
                self.assertTrue(places, (rung, sorted(piece)))
                place = rng.choice(places)
                for x, y in cells_at(quarter_turn(piece, place.quarter),
                                     place.col, place.row):
                    board.fill(x, y)
                board.clear_full_rows()

    def test_a_piece_is_cut_again_when_the_board_strands_it(self):
        """The re-cut is the only way the promise survives free choice.

        A hand dealt against one skyline is a hand about a board that
        no longer exists, and the player is the one deciding how fast
        it stops existing.
        """
        board = flat(8, 6, 5)                  # one row of headroom left
        rng = random.Random(0)
        queue = Queue(board, grade_at(1), rng, 3)
        queue.pieces[1] = SQUARE               # two rows deep: nowhere now
        self.assertEqual(perfect_placements(board, SQUARE), [])
        self.assertEqual(queue.revalidate(), 1)
        self.assertTrue(queue.recut[1])
        self.assertTrue(queue.promise_kept())

    def test_taking_a_piece_leaves_a_full_hand_behind(self):
        board = Board(20, 12)
        queue = Queue(board, grade_at(3), random.Random(7), 4)
        before = list(queue.pieces)
        taken = queue.take(2)
        self.assertIs(taken, before[2])
        self.assertEqual(len(queue), 4)
        self.assertGreater(queue.fits[2], 0)

    def test_a_gapless_run_stays_gapless_on_every_rung(self):
        """The headline. A player who always takes a gapless drop never
        buries a cell, whatever order the hand is taken in.

        The order is the part that matters. The pieces are cut against
        a board that the player is free to change between one piece
        and the next, so a generator that were merely correct at the
        moment of dealing would be wrong by the time the piece was
        used. Taking the slot at random is the cheapest way to say
        that the promise does not depend on taking them in the order
        they were cut.
        """
        for rung in range(1, len(GRADES) + 1):
            for seed in (0, 1):
                rng = random.Random(seed * 100 + rung)
                board = Board(48, 24)
                queue = Queue(board, grade_at(rung), rng, 5)
                for move in range(60):
                    self.assertTrue(queue.promise_kept(),
                                    (rung, seed, move, queue.fits))
                    piece = queue.take(rng.randrange(len(queue)))
                    places = perfect_placements(board, piece)
                    self.assertTrue(places, (rung, seed, move))
                    place = min(places, key=lambda spot: spot.row)
                    before = board.holes()
                    for x, y in cells_at(
                            quarter_turn(piece, place.quarter),
                            place.col, place.row):
                        board.fill(x, y)
                    self.assertEqual(board.holes(), before,
                                     (rung, seed, move))
                    board.clear_full_rows()
                    queue.revalidate()

    def test_settling_never_ends_inside_anything(self):
        rng = random.Random(2)
        board = Board(24, 14)
        for _step in range(60):
            piece = carve(board, grade_at(5), rng)
            for angle in (0.0, 33.0, 90.0, 154.0, 270.0):
                pose = settle(board, piece,
                              Pose(angle, 12.0, float(board.rows + 4)))
                self.assertFalse(tetris.blocked(board, piece, pose), angle)
            place = perfect_placements(board, piece)[0]
            for x, y in cells_at(quarter_turn(piece, place.quarter),
                                 place.col, place.row):
                board.fill(x, y)
            board.clear_full_rows()


@needs_ui
class TetrisScreenTests(unittest.TestCase):
    """The game as a person reaches it: keys, mouse and the tray."""

    def setUp(self):
        close_overlays()
        reset_window()
        self.task = FreeformTetris()
        # A small well and a short run, so a test can play one out.
        self.task.cols = 32
        self.task.rows = 20
        self.task.total_pieces = 8
        self.task.queue_size = 4
        self.task.adaptive = False
        self.task.start_rung = 1
        self.task.start_run()

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    # --- the promise, through the handles a person has ------------------

    def _place_perfectly(self) -> int:
        """Wind, steer and drop the falling piece into a gapless spot.

        Deliberately routed through ``_turn``, ``_slide_toward`` and
        ``drop`` — the same three things the arrow keys, the mouse and
        the space bar reach — rather than by writing a placement into
        the board. What is being checked is that the game can be
        played the way the promise says, not that the engine can
        compute one.
        """
        task = self.task
        places = perfect_placements(task.board, task.piece)
        self.assertTrue(places, (task.rung, sorted(task.piece)))
        place = min(places, key=lambda spot: spot.row)
        task._turn(90.0 * place.quarter)
        self.assertTrue(task.on_the_grid(), place.quarter)
        width = extent(quarter_turn(task.piece, place.quarter))[0]
        task._slide_toward(place.col + width / 2.0)
        before = task.buried
        task.drop()
        return task.buried - before

    def test_starting_deals_a_piece_and_a_full_tray(self):
        self.assertEqual(self.task.phase, 'falling')
        self.assertIsNotNone(self.task.piece)
        self.assertEqual(len(self.task.queue), 4)
        self.assertEqual(len(self.task.slot_rects), 4)

    def test_every_piece_on_offer_has_somewhere_gapless_to_go(self):
        for index, piece in enumerate(self.task.queue.pieces):
            self.assertTrue(perfect_placements(self.task.board, piece),
                            index)
            self.assertGreater(self.task.queue.fits[index], 0, index)

    def test_the_promise_survives_the_whole_run(self):
        for _piece in range(6):
            self.assertTrue(self.task.queue.promise_kept(),
                            self.task.queue.fits)
            self.assertEqual(self._place_perfectly(), 0)
            self.task._next_piece()
        self.assertEqual(self.task.buried, 0)
        self.assertEqual(self.task.clean, self.task.placed)

    def test_a_perfect_run_buries_nothing_on_any_rung(self):
        """The headline claim, played out rather than argued.

        Every rung, from the one that cuts rectangles to the one that
        cuts dented combs across seven columns, played by hand through
        the game's own controls. If a rung could ever deal a piece
        with nowhere flush to go, this is where it would show.
        """
        for rung in range(1, len(GRADES) + 1):
            self.task.close()
            self.task = FreeformTetris()
            self.task.cols = 32
            self.task.rows = 20
            self.task.total_pieces = 20
            self.task.queue_size = 4
            self.task.adaptive = False
            self.task.start_rung = rung
            self.task.start_run()
            self.assertEqual(self.task.rung, rung)
            for _piece in range(6):
                self.assertEqual(self._place_perfectly(), 0, rung)
                self.task._next_piece()
            self.assertEqual(self.task.buried, 0, rung)

    def test_the_well_stays_clear_of_the_verdict_band(self):
        """Guarded against the geometry, not against one sweep of pixels.

        Where the pieces land is content — it depends on how the run
        went — so a clean sweep of one run says nothing about the next.
        What can be checked is the box they are drawn in.
        """
        from neural_workshop.ui.verdict import above_the_band
        self.assertGreaterEqual(self.task.field_bottom,
                                above_the_band(0.0) - 1.0)

    # --- choosing --------------------------------------------------------

    def test_clicking_the_tray_chooses_what_comes_next(self):
        wanted = self.task.queue.pieces[2]
        left, bottom, width, height = self.task.slot_rects[2]
        self.task.on_mouse_press(left + width / 2, bottom + height / 2, 1, 0)
        self.assertEqual(self.task.armed, 2)
        self.task.drop()
        self.task._next_piece()
        self.assertIs(self.task.piece, wanted)

    def test_a_click_before_the_run_starts_it_wherever_it_lands(self):
        self.task.close()
        self.task = FreeformTetris()
        self.assertEqual(self.task.phase, 'ready')
        left, bottom, width, height = self.task.slot_rects[1]
        self.task.on_mouse_press(left + width / 2, bottom + height / 2, 1, 0)
        self.assertEqual(self.task.phase, 'falling')

    def test_the_number_keys_choose_too(self):
        self.task.on_key_press(key._3, 0)
        self.assertEqual(self.task.armed, 2)
        self.task.on_key_press(key._1, 0)
        self.assertEqual(self.task.armed, 0)

    def test_a_taken_slot_is_cut_full_again(self):
        was = self.task.queue.pieces[1]
        self.task.arm(1)
        self.task.drop()
        self.task._next_piece()
        self.assertEqual(len(self.task.queue), 4)
        self.assertIsNot(self.task.queue.pieces[1], was)
        self.assertGreater(self.task.queue.fits[1], 0)

    # --- the spin ---------------------------------------------------------

    def test_holding_a_key_winds_the_piece_round(self):
        self.task.spin_rate = 180.0
        self.task.on_key_press(key.UP, 0)
        for _tick in range(30):
            self.task.update(1 / 60.)
        self.assertGreater(self.task.spun, 20.0)
        wound = self.task.spun
        self.task.on_key_release(key.UP, 0)
        for _tick in range(30):
            self.task.update(1 / 60.)
        self.assertAlmostEqual(self.task.spun, wound)

    def test_the_two_keys_wind_opposite_ways(self):
        self.task.spin_rate = 180.0
        self.task.on_key_press(key.DOWN, 0)
        for _tick in range(20):
            self.task.update(1 / 60.)
        self.assertGreater(self.task.spun, 180.0)   # wound backwards past 0
        self.task.on_key_release(key.DOWN, 0)
        self.assertEqual(self.task.spin, 0.0)

    def test_both_keys_at_once_cancel(self):
        self.task.on_key_press(key.UP, 0)
        self.task.on_key_press(key.DOWN, 0)
        self.assertEqual(self.task.spin, 0.0)
        self.task.on_key_release(key.DOWN, 0)
        self.assertEqual(self.task.spin, 1.0)

    def test_the_detent_holds_the_piece_square_near_a_quarter_turn(self):
        self.task._turn(90.0 - tetris.SNAP_DEGREES / 2.0)
        self.assertTrue(self.task.on_the_grid())
        self.assertEqual(self.task.pose.angle, 90.0)

    def test_outside_the_detent_the_piece_is_held_where_it_was_wound(self):
        self.task._turn(45.0)
        self.assertFalse(self.task.on_the_grid())
        self.assertAlmostEqual(self.task.pose.angle, 45.0)

    def test_the_detent_can_be_turned_off_for_the_whole_circle(self):
        """The setting that makes "any angle" mean every angle.

        A corridor a few degrees wide is what makes a square landing
        catchable by hand, and it costs about a sixth of the circle.
        A player who wants the sixth back can have it: nothing else
        changes, S still squares up exactly, and a drop no longer
        quietly straightens a piece that was meant to be crooked.
        """
        self.task.detent = 0.0
        self.task._turn(90.0 - 2.0)
        self.assertFalse(self.task.on_the_grid())
        self.assertAlmostEqual(self.task.pose.angle, 88.0)
        landing = tetris.settle(self.task.board, self.task.piece,
                                self.task.pose)
        self.assertAlmostEqual(landing.angle, 88.0)
        self.task.square_up()
        self.assertTrue(self.task.on_the_grid())
        self.assertEqual(self.task.pose.angle, 90.0)

    def test_a_square_piece_is_drawn_on_the_columns_it_will_fill(self):
        """What is drawn and what lands have to be the same columns.

        The rasterisation rounds a square piece onto whole cells
        wherever its centre is, so nothing stops the two drifting half
        a cell apart — except doing this.
        """
        self.task._slide_toward(11.37)
        self.assertTrue(self.task.on_the_grid())
        drawn = tetris.centres(self.task.piece, self.task.pose)
        landing = tetris.footprint(self.task.piece, self.task.pose)
        for x, _y in drawn:
            self.assertIn(int(x), {column for column, _row in landing})
        width = extent(self.task.piece)[0]
        self.assertAlmostEqual(self.task.pose.cx % 1.0, (width / 2.0) % 1.0)

    def test_squaring_up_takes_the_nearest_quarter_turn(self):
        self.task._turn(100.0)
        self.task.square_up()
        self.assertTrue(self.task.on_the_grid())
        self.assertEqual(self.task.pose.angle, 90.0)

    def test_a_crooked_drop_is_what_buries_cells(self):
        """The price of the free spin, on the board rather than in prose."""
        self.task.piece = SLAB
        self.task.spun = 0.0
        self.task.pose = Pose(0.0, 16.0, float(self.task.rows) - 2.0)
        self.task._turn(45.0)
        self.assertFalse(self.task.on_the_grid())
        self.task.drop()
        self.assertGreater(self.task.buried, 0)

    # --- scoring ----------------------------------------------------------

    def test_the_verdict_is_green_only_when_nothing_was_buried(self):
        self.assertEqual(self._place_perfectly(), 0)
        self.assertEqual(self.task.phase, 'landed')
        self.assertIsNotNone(self.task.verdict_shown)
        self.assertTrue(self.task.verdict_shown[0])
        self.assertTrue(self.task.verdict.label.visible)

    def test_a_burying_drop_paints_a_red_one(self):
        self.task.piece = SLAB
        self.task.spun = 0.0
        self.task.pose = Pose(0.0, 16.0, float(self.task.rows) - 2.0)
        self.task._turn(45.0)
        self.task.drop()
        self.assertFalse(self.task.verdict_shown[0])

    def test_the_verdict_comes_down_before_the_next_piece(self):
        self._place_perfectly()
        self.assertTrue(self.task.verdict.label.visible)
        self.task._next_piece()
        self.assertEqual(self.task.phase, 'falling')
        self.assertIsNone(self.task.verdict_shown)
        self.assertFalse(self.task.verdict.label.visible)

    def test_a_run_ends_with_a_score(self):
        self.task.total_pieces = 3
        for _piece in range(3):
            self._place_perfectly()
            self.task._next_piece()
        self.assertEqual(self.task.phase, 'done')
        tally = self.task.score()
        self.assertEqual(tally['pieces'], 3)
        self.assertEqual(tally['clean'], 100)
        self.assertEqual(tally['buried'], 0)
        self.task.on_draw()

    def test_the_ladder_climbs_without_the_gravity_moving(self):
        """The whole point of the ladder, checked where it could slip."""
        from neural_workshop.ui.tetris import CLIMB_AFTER
        self.task.adaptive = True
        gravity = self.task.fall_rate
        for _piece in range(CLIMB_AFTER):
            self._place_perfectly()
            self.task._next_piece()
        self.assertEqual(self.task.rung, 2)
        self.assertEqual(self.task.fall_rate, gravity)
        self.assertEqual(self.task.queue.grade, grade_at(2))

    # --- the boundary's ports --------------------------------------------

    def test_every_port_does_what_the_keys_do(self):
        # Left then right has to come back to where it started, which
        # only holds because a piece is squared onto whole columns as
        # it spawns -- an odd-width piece centred on the well is not.
        was = self.task.pose.cx
        self.task.press(0)
        self.assertAlmostEqual(self.task.pose.cx, was - 1.0)
        self.task.press(1)
        self.assertAlmostEqual(self.task.pose.cx, was)
        self.task.press(2)
        self.assertGreater(self.task.spun, 0.0)
        self.task.press(3)
        self.assertAlmostEqual(self.task.spun, 0.0)
        self.task.press(7)
        self.assertEqual(self.task.armed, 2)
        self.task.press(4)
        self.assertEqual(self.task.phase, 'landed')

    def test_a_port_off_the_end_does_nothing(self):
        was = self.task.pose
        self.task.press(-1)
        self.task.press(99)
        self.assertEqual(self.task.pose, was)

    def test_twenty_four_spin_presses_are_a_whole_turn(self):
        for _press in range(24):
            self.task.press(2)
        self.assertAlmostEqual(self.task.spun % 360.0, 0.0)
        self.assertTrue(self.task.on_the_grid())

    # --- furniture --------------------------------------------------------

    def test_it_is_in_the_hub_and_has_its_own_options(self):
        self.assertIn('tetris',
                      [task for task, _name in TASKS['planning']])
        self.assertTrue(taskoptions.has_options('tetris'))
        dials = {'TETRIS_COLUMNS': 72, 'TETRIS_ROWS': 32, 'TETRIS_RUNG': 1,
                 'TETRIS_ADAPTIVE': True, 'TETRIS_FALL': 2.5,
                 'TETRIS_DETENT': 7}
        note = taskoptions.TETRIS.note(dials)
        self.assertIn('200', note)
        self.assertIn('shape, not speed', note)
        self.assertIn('7', note)
        dials['TETRIS_DETENT'] = 0
        self.assertIn('exactly as wound', taskoptions.TETRIS.note(dials))

    def test_a_resize_keeps_the_verdict_up(self):
        self._place_perfectly()
        self.task.relayout()
        self.assertTrue(self.task.verdict.label.visible)

    def test_it_draws_at_every_phase(self):
        self.task.on_draw()
        self._place_perfectly()
        self.task.on_draw()
        self.task.total_pieces = 1
        self.task._next_piece()
        self.assertEqual(self.task.phase, 'done')
        self.task.on_draw()

    def test_a_run_played_badly_tops_out_rather_than_jams(self):
        """The losing path, which is the one nothing else exercises.

        A small well and the largest pieces, dropped wherever they
        happened to spawn. The run has to end — with a verdict, a
        score and a screen that still draws — rather than sit in a
        phase with no way out of it.
        """
        self.task.close()
        self.task = FreeformTetris()
        self.task.cols, self.task.rows = 20, 10
        self.task.total_pieces = 200
        self.task.adaptive = False
        self.task.start_rung = len(GRADES)
        self.task.start_run()
        for _drop in range(200):
            if self.task.phase != 'falling':
                break
            self.task.drop()
            self.task._next_piece()
        self.assertEqual(self.task.phase, 'done')
        self.assertIn('Topped out', self.task.message)
        self.assertGreater(self.task.buried, 0)
        self.assertEqual(self.task.score()['pieces'], self.task.placed)
        self.task.on_draw()

    def test_closing_gives_back_its_handlers(self):
        self.task.close()
        self.assertIsNone(FreeformTetris.instance)
        self.assertNotIn(self.task, display.open_overlays())
