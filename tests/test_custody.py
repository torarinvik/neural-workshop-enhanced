#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Chain of Custody's model: the belt, the machines, and the two promises.

Nothing here draws anything. What is being checked is the part the
screen only reports:

* that a colour never answers the question — every rung deals more
  boxes than coats, so a player who has lost the Core is guessing from
  a field that gets wider up the ladder rather than narrower;

* that every rung is winnable, by a player who knows which box is the
  Core, well inside its budget — so a round that is lost was lost on
  the identity or the plan and not on the clock;

* that coach mode's shaping is potential-based and **blind to the
  Core**, which is the one thing that could quietly turn this from a
  task about identity into a task about routing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

import oracle_custody as O                          # noqa: E402
from neural_workshop import custody as C            # noqa: E402


def dealt(level, seed=0):
    """A layout and its boxes, the way a round starts."""
    layout = C.generate(level, seed=seed)
    return layout, C.fresh_boxes(layout, random.Random(seed))


class TheLadder(unittest.TestCase):
    """What the rungs promise before anybody plays them."""

    def test_a_colour_never_closes_the_field(self):
        """More boxes than coats, everywhere there is more than one box."""
        for grade in C.GRADES[1:]:
            self.assertGreater(grade.rivals, 1.0, grade.name)

    def test_the_guessing_floor_never_falls(self):
        """A rung is never easier than the one below it, on its own axis."""
        floors = [grade.rivals for grade in C.GRADES]
        self.assertEqual(floors, sorted(floors), floors)

    def test_the_first_rung_is_one_box_and_nothing_else(self):
        """A ladder whose bottom rung needs a plan has no bottom."""
        first = C.GRADES[0]
        self.assertEqual(first.boxes, 1)
        self.assertEqual(first.need_charge, 0)
        self.assertFalse(first.moving)
        self.assertEqual(first.chargers + first.coolers + first.painters, 0)

    def test_each_rung_adds_something(self):
        for below, above in zip(C.GRADES, C.GRADES[1:]):
            harder = (
                above.boxes > below.boxes
                or above.rivals > below.rivals
                or above.moving > below.moving
                or above.need_charge > below.need_charge
                or above.max_heat < below.max_heat
                or above.decay > below.decay
                or (above.chargers + above.coolers + above.painters
                    > below.chargers + below.coolers + below.painters))
            self.assertTrue(harder, '%s adds nothing to %s'
                                    % (above.name, below.name))

    def test_a_deal_puts_every_machine_the_rung_asked_for(self):
        for level, grade in enumerate(C.GRADES, 1):
            for seed in range(20):
                layout = C.generate(level, seed=seed)
                for kind, wanted in ((C.CHARGER, grade.chargers),
                                     (C.COOLER, grade.coolers),
                                     (C.PAINTER, grade.painters)):
                    self.assertEqual(len(C.slots_of(layout, kind)), wanted,
                                     '%s seed %d' % (grade.name, seed))

    def test_no_machine_stands_on_the_bay(self):
        """One there could never be used: dropping in it delivers."""
        for level in range(1, len(C.GRADES) + 1):
            for seed in range(20):
                layout = C.generate(level, seed=seed)
                self.assertIsNone(C.machine_at(layout, layout.bay))

    def test_no_two_machines_are_adjacent(self):
        """Or a box left in one rides into the next and is undone."""
        for level in range(1, len(C.GRADES) + 1):
            for seed in range(20):
                layout = C.generate(level, seed=seed)
                slots = sorted(m.slot for m in layout.machines)
                for one, other in zip(slots, slots[1:]):
                    self.assertGreater(other - one, 1)
                if len(slots) > 1:      # the ring wraps, so check the seam
                    self.assertNotEqual((slots[0] - slots[-1]) % layout.slots,
                                        1)


class TheRing(unittest.TestCase):
    """Distance on a loop, which is what the shaping is built on."""

    def test_the_gap_is_symmetric_and_short_way_round(self):
        for slots in (10, 14, 20):
            for one in range(slots):
                for other in range(slots):
                    found = C.gap(one, other, slots)
                    self.assertEqual(found, C.gap(other, one, slots))
                    self.assertLessEqual(found, slots // 2)

    def test_one_step_changes_the_gap_by_exactly_one(self):
        """The property the whole shaping guarantee rests on."""
        slots = 14
        for here in range(slots):
            for there in range(slots):
                if C.gap(here, there, slots) == slots // 2:
                    continue        # the far side, where both ways tie
                for step in (1, -1):
                    moved = C.gap((here + step) % slots, there, slots)
                    self.assertEqual(abs(moved - C.gap(here, there, slots)), 1)


class TheBelt(unittest.TestCase):
    """What a step of the belt does, and what it does not."""

    def test_a_box_moves_one_slot_a_step(self):
        """The bug this pins: a jam pass carrying one box several slots.

        Measured before it was fixed, a box crossed five or six slots
        in a step, which put it past the claw every time — the boxes
        could not be intercepted at all, and half the ladder was
        unwinnable without saying so.
        """
        layout, boxes = dealt(10, seed=3)
        for _step in range(60):
            before = {id(box): box.slot for box in C.loose(boxes)}
            C.step_belt(boxes, layout)
            for box in C.loose(boxes):
                if id(box) not in before:
                    continue
                moved = (box.slot - before[id(box)]) % layout.slots
                self.assertIn(moved, (0, 1), 'moved %d slots' % moved)

    def test_boxes_never_share_a_slot(self):
        layout, boxes = dealt(10, seed=5)
        for _step in range(80):
            C.step_belt(boxes, layout)
            slots = [box.slot for box in C.loose(boxes)]
            self.assertEqual(len(slots), len(set(slots)))

    def test_a_still_belt_does_not_move(self):
        layout, boxes = dealt(1)
        self.assertFalse(layout.moving)
        was = [box.slot for box in boxes]
        C.step_belt(boxes, layout)
        self.assertEqual([box.slot for box in boxes], was)

    def test_the_belt_does_not_work_the_charger(self):
        """It used to, and that made preparation free.

        A box left to ride would pass the charger and then the cooler
        on its own and arrive prepared, so the plan the middle rungs
        are named for cost nothing at all.
        """
        layout, boxes = dealt(5, seed=2)
        charger = C.slots_of(layout, C.CHARGER)[0]
        for _step in range(layout.slots * 3):
            C.step_belt(boxes, layout)
        self.assertTrue(all(box.charge == 0 for box in boxes))
        self.assertIsNotNone(charger)

    def test_the_belt_does_work_the_painter(self):
        """Because a painter is a hazard rather than a service.

        Watched over the whole walk rather than compared end to end.
        With two coats a painter is a toggle, so a box that laps an
        even number of times is wearing what it started in — the coat
        is periodic, and a snapshot at the wrong moment says nothing
        happened when in fact it happened twice.
        """
        layout, boxes = dealt(6, seed=1)
        started = {id(box): box.look for box in boxes}
        changed = set()
        for _step in range(layout.slots * 2):
            C.step_belt(boxes, layout)
            changed |= {id(box) for box in boxes
                        if box.look != started[id(box)]}
        self.assertEqual(len(changed), len(boxes))


class TheMachines(unittest.TestCase):
    """What the claw can make happen, and what it costs."""

    def setUp(self):
        self.layout, self.boxes = dealt(5, seed=2)
        self.charger = C.slots_of(self.layout, C.CHARGER)[0]
        self.cooler = C.slots_of(self.layout, C.COOLER)[0]

    def put_into(self, box, slot):
        box.held = True
        box.slot = slot
        others = [other for other in self.boxes if other is not box]
        return C.put_down(box, others, slot, self.layout)

    def test_charging_raises_charge_and_heat_together(self):
        box = self.boxes[0]
        self.put_into(box, self.charger)
        self.assertEqual(box.charge, C.CHARGE_STEP)
        self.assertEqual(box.heat, C.CHARGE_HEAT)

    def test_one_charge_clears_the_mark_and_breaks_the_heat_limit(self):
        """Which is what makes the order a decision rather than a list."""
        box = self.boxes[0]
        self.put_into(box, self.charger)
        self.assertGreaterEqual(box.charge, self.layout.need_charge)
        self.assertGreater(box.heat, self.layout.max_heat)
        self.assertFalse(C.wanted(box, self.layout))

    def test_cooling_afterwards_finishes_the_job(self):
        box = self.boxes[0]
        self.put_into(box, self.charger)
        self.put_into(box, self.cooler)
        self.assertTrue(C.wanted(box, self.layout))

    def test_cooling_first_is_wasted(self):
        box = self.boxes[0]
        self.put_into(box, self.cooler)
        self.put_into(box, self.charger)
        self.assertFalse(C.wanted(box, self.layout))

    def test_a_machine_holds_a_box_for_one_belt_step(self):
        """So the claw can put one in and take it straight back out.

        Without it, using a machine cost a whole lap of the ring to
        get the box in hand again — and with charge bleeding, that was
        not a cost but a wall: the top two rungs became unwinnable.
        """
        box = self.boxes[0]
        self.put_into(box, self.charger)
        C.step_belt(self.boxes, self.layout)
        self.assertEqual(box.slot, self.charger)
        C.step_belt(self.boxes, self.layout)
        self.assertNotEqual(box.slot, self.charger)

    def test_charging_over_and_over_cooks_the_box(self):
        """The trap that stops a learner farming the charger."""
        box = self.boxes[0]
        for _again in range(6):
            self.put_into(box, self.charger)
        self.assertEqual(box.charge, 100)
        self.assertGreater(box.heat, self.layout.max_heat)

    def test_the_painter_moves_a_coat_on_rather_than_fixing_it(self):
        """Measured both ways.

        Setting every box to one colour drove the whole belt to the
        same coat within three laps, which killed the colour channel
        outright and repainted the Core once a round instead of once a
        lap. Cycling keeps the coats spread and the Core changing.
        """
        layout, boxes = dealt(6, seed=1)
        box = boxes[0]
        was = box.look
        C.treat(box, C.PAINTER, layout)
        self.assertNotEqual(box.look, was)
        self.assertLess(box.look, layout.looks)

    def test_decay_bites_only_what_rides(self):
        layout, boxes = dealt(9, seed=1)
        self.assertGreater(layout.decay, 0)
        riding, carried = boxes[0], boxes[1]
        riding.charge = carried.charge = 90
        carried.held = True
        C.step_belt(boxes, layout)
        self.assertLess(riding.charge, 90)
        self.assertEqual(carried.charge, 90)


class TheClaw(unittest.TestCase):
    """Picking up, putting down, and delivering."""

    def setUp(self):
        self.layout, self.boxes = dealt(5, seed=2)

    def test_a_slot_with_no_box_gives_nothing(self):
        empty = next(slot for slot in range(self.layout.slots)
                     if C.box_at(self.boxes, slot) is None)
        self.assertIsNone(C.grab(self.boxes, empty))

    def test_a_held_box_is_off_the_belt(self):
        box = self.boxes[0]
        C.grab(self.boxes, box.slot)
        self.assertTrue(box.held)
        self.assertNotIn(box, C.loose(self.boxes))

    def test_a_taken_slot_refuses_a_second_box(self):
        one, other = self.boxes[0], self.boxes[1]
        C.grab(self.boxes, one.slot)
        self.assertFalse(C.put_down(one, self.boxes, other.slot, self.layout))
        self.assertTrue(one.held)

    def test_the_bay_delivers_and_delivering_is_final(self):
        box = self.boxes[0]
        C.grab(self.boxes, box.slot)
        self.assertTrue(C.put_down(box, self.boxes, self.layout.bay,
                                   self.layout))
        self.assertTrue(box.delivered)
        self.assertNotIn(box, C.loose(self.boxes))
        self.assertIsNone(C.grab(self.boxes, self.layout.bay))


class TheShaping(unittest.TestCase):
    """Coach mode: dense, safe, and blind to the answer."""

    def setUp(self):
        self.layout, self.boxes = dealt(5, seed=2)
        self.held = self.boxes[0]
        self.held.held = True

    def test_nothing_held_has_no_potential(self):
        """An empty claw has no plan to be near or far from."""
        self.assertIsNone(C.potential(None, 0, self.layout))

    def test_one_claw_move_changes_it_by_at_most_one(self):
        """What makes the sign of the change a valid shaping term."""
        for claw in range(self.layout.slots):
            self.held.slot = claw
            here = C.potential(self.held, claw, self.layout)
            for step in (1, -1):
                there = (claw + step) % self.layout.slots
                self.held.slot = there
                moved = C.potential(self.held, there, self.layout)
                self.assertLessEqual(abs(moved - here), 1)

    def test_a_closed_loop_of_moves_telescopes_to_nothing(self):
        """The property that makes it dense rather than farmable."""
        for start in range(self.layout.slots):
            claw = start
            self.held.slot = claw
            total = 0
            for step in [1] * 5 + [-1] * 5:
                before = C.potential(self.held, claw, self.layout)
                claw = (claw + step) % self.layout.slots
                self.held.slot = claw
                total += before - C.potential(self.held, claw, self.layout)
            self.assertEqual(claw, start)
            self.assertEqual(total, 0)

    def test_it_cannot_see_which_box_is_the_core(self):
        """The one thing that would quietly gut the task.

        Had the potential read the Core's position, coach mode would
        have handed a learner the identity for free and every result
        taken under it would have been about routing while claiming to
        be about custody.
        """
        for core in range(self.layout.boxes):
            other = self.layout._replace(core=core)
            self.assertEqual(C.potential(self.held, 3, other),
                             C.potential(self.held, 3, self.layout))

    def test_it_leads_to_the_charger_first_and_the_bay_last(self):
        claw = 0
        self.held.slot = claw
        self.assertIn(C.next_target(self.held, self.layout, claw),
                      C.slots_of(self.layout, C.CHARGER))
        C.treat(self.held, C.CHARGER, self.layout)
        self.assertIn(C.next_target(self.held, self.layout, claw),
                      C.slots_of(self.layout, C.COOLER))
        C.treat(self.held, C.COOLER, self.layout)
        self.assertEqual(C.next_target(self.held, self.layout, claw),
                         self.layout.bay)


class EveryRungIsWinnable(unittest.TestCase):
    """Checked by playing them, not by believing the budgets."""

    ROUNDS = 40

    def test_a_player_who_knows_the_core_always_delivers_it(self):
        for level, wins, _costs in O.survey(self.ROUNDS):
            self.assertEqual(wins, self.ROUNDS,
                             '%s lost %d of %d'
                             % (C.GRADES[level - 1].name,
                                self.ROUNDS - wins, self.ROUNDS))

    def test_the_budget_ends_a_round_rather_than_being_the_difficulty(self):
        """Four times the worst honest route, so being wrong is affordable."""
        for level, _wins, costs in O.survey(self.ROUNDS):
            grade = C.GRADES[level - 1]
            self.assertLess(max(costs), grade.budget / 2.0,
                            '%s: worst route %d of %d budget'
                            % (grade.name, max(costs), grade.budget))

    def test_running_out_of_actions_is_the_only_way_to_stall(self):
        """Nothing about a deal can make it unwinnable on its own."""
        for level in range(1, len(C.GRADES) + 1):
            for seed in range(8):
                spent, ok, layout = O.play(level, seed)
                self.assertTrue(ok, 'rung %d seed %d' % (level, seed))
                self.assertLess(spent, layout.budget)


if __name__ == '__main__':
    unittest.main()
