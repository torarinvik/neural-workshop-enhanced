#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The pixels-versus-points rule, enforced.

On a scaled display a window's drawing surface (pixels) and the size
the operating system gives it (points) are different numbers, related
by ``window.scale``. Mixing them up is invisible on an unscaled
display and doubles the window on a Retina one, so
:mod:`neural_workshop.geometry` owns every call into pyglet's
point-space API and everything else goes through it.

The source scan below is the part that survives us: it fails the build
the next time someone reaches for ``window.set_size`` directly.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import ast
import os
import re
import unittest

from uisupport import (Message, MonkeyLadder, ROOT, TaskHub, close_overlays,
                       display, geometry, key, needs_ui, on_key_press,
                       reset_window, state)

#: pyglet window APIs that speak points, or convert between the two.
#: Only geometry may call them; everyone else uses its helpers. Matched
#: as whole names so sprite ``.scale`` and the like are left alone.
POINT_SPACE_CALLS = (
    r'\bset_size\s*\(',
    r'\bget_size\s*\(',
    r'\bget_framebuffer_size\s*\(',
    r'\bset_minimum_size\s*\(',
    r'\bwindow\.scale\b',
)

#: The one module allowed to name them, plus this test.
OWNERS = ('neural_workshop/geometry.py', 'tests/test_ui_units.py')

#: Packages the rule covers.
PACKAGES = ('neural_workshop', 'bwaccel', 'nwenv')


def _source_files():
    for package in PACKAGES:
        for folder, _dirs, files in os.walk(os.path.join(ROOT, package)):
            if '__pycache__' in folder:
                continue
            for name in sorted(files):
                if name.endswith('.py'):
                    path = os.path.join(folder, name)
                    yield os.path.relpath(path, ROOT).replace(os.sep, '/')


class SourceRuleTests(unittest.TestCase):
    """Nothing outside geometry may touch pyglet's point-space API."""

    def test_the_scan_sees_the_source(self):
        files = list(_source_files())
        self.assertIn('neural_workshop/geometry.py', files)
        self.assertIn('neural_workshop/window.py', files)
        self.assertGreater(len(files), 30)

    def test_only_geometry_calls_the_point_space_api(self):
        offenders = []
        for relpath in _source_files():
            if relpath in OWNERS:
                continue
            with open(os.path.join(ROOT, relpath), encoding='utf-8') as handle:
                for number, line in enumerate(handle, 1):
                    code = line.split('#', 1)[0]
                    for call in POINT_SPACE_CALLS:
                        if re.search(call, code):
                            offenders.append(
                                '%s:%i matches %s' % (relpath, number, call))
        self.assertEqual(offenders, [], '\n'.join(
            ['point-space API used outside neural_workshop/geometry.py; '
             'use geometry.set_window_size / point_size / '
             'framebuffer_size / apply_minimum_size:']
            + offenders))

    def test_the_scan_would_catch_a_new_offender(self):
        # Guard the guard: a rule that cannot fail is not a rule.
        offences = ['window.set_size(state.window.width, state.window.height)',
                    'w, h = window.get_size()',
                    'window.set_minimum_size(1, 1)',
                    'factor = self.window.scale']
        for sample in offences:
            self.assertTrue(
                any(re.search(call, sample) for call in POINT_SPACE_CALLS),
                sample)

    def test_the_scan_leaves_unrelated_names_alone(self):
        allowed = ['sprite.scale = 2',
                   'self.scale = dt',
                   'graphic.scale = 1',
                   'x = state.window.width / 8',
                   'from .geometry import scale_to_width']
        for sample in allowed:
            self.assertFalse(
                any(re.search(call, sample) for call in POINT_SPACE_CALLS),
                sample)


@needs_ui
class UnitConversionTests(unittest.TestCase):
    """Points and pixels must round-trip through geometry."""

    def tearDown(self):
        reset_window()

    def test_scale_relates_the_two_spaces(self):
        scale = geometry.window_scale()
        self.assertGreater(scale, 0)
        pixels = geometry.pixel_size()
        points = geometry.point_size()
        self.assertEqual(points[0], round(pixels[0] / scale))
        self.assertEqual(points[1], round(pixels[1] / scale))

    def test_conversions_are_inverses(self):
        for value in (1, 37, 640, 1024, 1920):
            self.assertEqual(
                geometry.pixels_to_points(geometry.points_to_pixels(value)),
                value)

    def test_set_window_size_takes_points_and_round_trips(self):
        for width, height in ((1024, 768), (800, 600), (912, 684)):
            geometry.set_window_size(width, height)
            self.assertEqual(geometry.point_size(), (width, height))
            self.assertEqual(
                geometry.pixel_size(),
                (geometry.points_to_pixels(width),
                 geometry.points_to_pixels(height)))

    def test_repeated_round_trips_do_not_drift(self):
        # The bug this rules out: reading pixels and setting them back
        # as points, which doubles the window on every pass.
        geometry.set_window_size(900, 700)
        for _ in range(5):
            width, height = geometry.point_size()
            geometry.set_window_size(width, height)
        self.assertEqual(geometry.point_size(), (900, 700))

    def test_only_an_oversized_result_counts_as_wrong(self):
        # A window manager capping the size is routine; growing is the
        # units bug, so only that should raise its voice.
        self.assertFalse(geometry.resize_overshot((1100, 800), (1100, 800)))
        self.assertFalse(geometry.resize_overshot((1100, 800), (1100, 786)))
        self.assertFalse(geometry.resize_overshot((1100, 800), (900, 700)))
        self.assertTrue(geometry.resize_overshot((1100, 800), (2200, 1600)))
        self.assertTrue(geometry.resize_overshot((1100, 800), (1100, 1600)))

    def test_an_absurd_size_is_capped_and_still_lays_out(self):
        # A hidden window has no window manager to cap a silly request,
        # so the cap has to be ours. Widgets sized from the height are
        # what break first, hence the font ceiling too.
        geometry.set_window_size(20000, 20000)
        width, height = geometry.pixel_size()
        self.assertLessEqual(width, geometry.MAX_WINDOW_PIXELS)
        self.assertLessEqual(height, geometry.MAX_WINDOW_PIXELS)
        display.relayout()           # must not raise
        self.assertEqual(display._laid_out_for, geometry.pixel_size())

    def test_font_sizes_stop_growing_with_the_window(self):
        geometry.set_window_size(912, 684)
        modest = geometry.calc_fontsize(22)
        geometry.set_window_size(20000, 20000)
        self.assertGreater(geometry.calc_fontsize(22), modest)
        self.assertLessEqual(geometry.calc_fontsize(22), geometry.MAX_FONT_SIZE)
        self.assertLessEqual(geometry.calc_fontsize(10000),
                             geometry.MAX_FONT_SIZE)

    def test_clamp_points_holds_both_ends(self):
        ceiling = geometry.pixels_to_points(geometry.MAX_WINDOW_PIXELS)
        self.assertEqual(geometry.clamp_points(1, 640), 640)
        self.assertEqual(geometry.clamp_points(800, 640), 800)
        self.assertEqual(geometry.clamp_points(10 ** 6, 640), ceiling)

    def test_a_size_below_the_minimum_is_clamped(self):
        geometry.set_window_size(1, 1)
        self.assertEqual(geometry.point_size(),
                         (geometry.MIN_WINDOW_WIDTH, geometry.MIN_WINDOW_HEIGHT))

    def test_the_window_starts_at_the_configured_point_size(self):
        self.assertGreaterEqual(state.cfg.WINDOW_WIDTH, geometry.MIN_WINDOW_WIDTH)
        self.assertGreaterEqual(state.cfg.WINDOW_HEIGHT, geometry.MIN_WINDOW_HEIGHT)


@needs_ui
class AutomaticRelayoutTests(unittest.TestCase):
    """A size change lays the game out again without being asked."""

    def setUp(self):
        reset_window()
        display.relayout(force=True)

    def tearDown(self):
        reset_window()

    def test_resizing_alone_schedules_a_relayout(self):
        before = (state.field.center_x, state.field.center_y)
        geometry.set_window_size(1024, 768)
        # No explicit relayout: on_resize asked for one, the clock runs it.
        display._deferred_relayout(0.0)
        self.assertNotEqual((state.field.center_x, state.field.center_y), before)

    def test_on_resize_defers_rather_than_rebuilding_inline(self):
        geometry.set_window_size(1024, 768)
        display._relayout_pending = False
        display.on_resize(*geometry.pixel_size())
        self.assertTrue(display._relayout_pending)

    def test_repeated_resizes_coalesce_into_one_rebuild(self):
        rebuilds = []
        original = display._rebuild_everything
        display._rebuild_everything = lambda: rebuilds.append(True)
        try:
            for width in (700, 800, 900, 1000):
                geometry.set_window_size(width, 650)
                display.on_resize(*geometry.pixel_size())
            self.assertEqual(rebuilds, [])
            display._deferred_relayout(0.0)
            self.assertEqual(len(rebuilds), 1)
        finally:
            display._rebuild_everything = original

    def test_an_unchanged_size_costs_nothing(self):
        rebuilds = []
        original = display._rebuild_everything
        display._rebuild_everything = lambda: rebuilds.append(True)
        try:
            display.relayout()
            self.assertEqual(rebuilds, [])
            display.relayout(force=True)
            self.assertEqual(len(rebuilds), 1)
        finally:
            display._rebuild_everything = original

    def test_relayout_does_not_reenter(self):
        seen = []

        def reentrant():
            seen.append(True)
            display.relayout(force=True)   # must be refused

        original = display._rebuild_everything
        display._rebuild_everything = reentrant
        try:
            geometry.set_window_size(1024, 768)
            display.relayout()
            self.assertEqual(len(seen), 1)
        finally:
            display._rebuild_everything = original

    def test_relayout_is_safe_before_the_widgets_exist(self):
        field = state.field
        state.field = None
        try:
            self.assertFalse(display.layout_ready())
            display.relayout()          # must not raise
            display.on_resize(800, 600)
            self.assertFalse(display._relayout_pending)
        finally:
            state.field = field

    def test_fullscreen_toggle_lays_out_synchronously(self):
        windowed = geometry.pixel_size()
        try:
            display.toggle_fullscreen()
            # Whether or not the window manager granted it, the widgets
            # must already match the size the window actually is.
            self.assertEqual(display._laid_out_for, geometry.pixel_size())
            if display.is_fullscreen():
                self.assertNotEqual(geometry.pixel_size(), windowed)
        finally:
            display.set_fullscreen(False)
        self.assertEqual(display._laid_out_for, geometry.pixel_size())

    def test_a_resize_is_refused_while_fullscreen(self):
        try:
            if not display.set_fullscreen(True):
                self.skipTest('no display server to go fullscreen on')
            fullscreen_size = geometry.point_size()
            geometry.set_window_size(800, 600)
            self.assertEqual(geometry.point_size(), fullscreen_size)
        finally:
            display.set_fullscreen(False)

    def test_leaving_fullscreen_does_not_double_the_window(self):
        # pyglet restores the windowed size in the wrong space; three
        # round trips would be 8x the window if that leaked through.
        geometry.set_window_size(1000, 700)
        display.relayout()
        for _ in range(3):
            if not display.set_fullscreen(True):
                self.skipTest('no display server to go fullscreen on')
            display.set_fullscreen(False)
            self.assertEqual(geometry.point_size(), (1000, 700))

    def test_f11_still_reaches_the_toggle(self):
        calls = []
        original = display.toggle_fullscreen
        display.toggle_fullscreen = lambda: calls.append(True)
        try:
            state.mode.title_screen = True
            on_key_press(key.F11, 0)
        finally:
            display.toggle_fullscreen = original
            state.mode.title_screen = False
        self.assertEqual(len(calls), 1)


@needs_ui
class WindowedSizeMemoryTests(unittest.TestCase):
    """Leaving fullscreen returns to the size the player last chose."""

    def tearDown(self):
        reset_window()

    def test_remember_window_size_records_points(self):
        geometry.set_window_size(1024, 768)
        display.remember_window_size()
        self.assertEqual((state.cfg.WINDOW_WIDTH, state.cfg.WINDOW_HEIGHT),
                         (1024, 768))

    def test_remembered_size_restores_exactly(self):
        geometry.set_window_size(1000, 720)
        display.remember_window_size()
        geometry.set_window_size(800, 600)
        geometry.set_window_size(state.cfg.WINDOW_WIDTH,
                                 state.cfg.WINDOW_HEIGHT)
        self.assertEqual(geometry.point_size(), (1000, 720))


class OverlayRuleTests(unittest.TestCase):
    """A screen that draws itself must also lay itself out again.

    Overlays own their batch and position everything from the window,
    so each one has to (a) join the display registry while it is on
    screen, (b) offer ``relayout``, and (c) check for a stale layout
    before it draws. Miss any of the three and the overlay is the one
    thing left at the old size after a resize — which is precisely the
    kind of thing nobody notices until a user files a screenshot.
    """

    #: Where the overlay classes live.
    UI_DIR = 'neural_workshop/ui'

    def _overlay_classes(self):
        """Every class whose ``push_handlers`` includes its own on_draw."""
        found = []
        for relpath in _source_files():
            if not relpath.startswith(self.UI_DIR):
                continue
            with open(os.path.join(ROOT, relpath), encoding='utf-8') as handle:
                source = handle.read()
            tree = ast.parse(source, relpath)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                body = ast.get_source_segment(source, node) or ''
                if not re.search(r'push_handlers\([^)]*on_draw', body, re.S):
                    continue
                found.append((relpath, node.name, body))
        return found

    def test_the_scan_finds_the_overlays(self):
        names = {name for _path, name, _body in self._overlay_classes()}
        for expected in ('Menu', 'TaskHub', 'MonkeyLadder', 'NCupMonte',
                         'Message', 'TextInputScreen'):
            self.assertIn(expected, names)

    def test_every_overlay_registers_and_unregisters(self):
        missing = []
        for path, name, body in self._overlay_classes():
            if 'display.register_overlay(self)' not in body:
                missing.append('%s.%s never calls display.register_overlay'
                               % (path, name))
            if 'display.unregister_overlay(self)' not in body:
                missing.append('%s.%s never calls display.unregister_overlay'
                               % (path, name))
        self.assertEqual(missing, [], '\n'.join(missing))

    def test_every_overlay_can_relayout(self):
        missing = [
            '%s.%s has no relayout()' % (path, name)
            for path, name, body in self._overlay_classes()
            if not re.search(r'def relayout\(', body)]
        self.assertEqual(missing, [], '\n'.join(missing))

    def test_every_draw_checks_for_a_stale_layout(self):
        missing = []
        for path, name, body in self._overlay_classes():
            draw = re.search(r'def on_draw\(self.*?(?=\n    def |\Z)', body, re.S)
            self.assertIsNotNone(draw, '%s.%s has no on_draw' % (path, name))
            if 'ensure_laid_out()' not in draw.group(0):
                missing.append('%s.%s.on_draw does not call '
                               'display.ensure_laid_out()' % (path, name))
        self.assertEqual(missing, [], '\n'.join(missing))

    def test_the_main_draw_checks_too(self):
        with open(os.path.join(ROOT, 'neural_workshop/events.py'),
                  encoding='utf-8') as handle:
            source = handle.read()
        draw = re.search(r'def on_draw\(\).*?(?=\ndef |\Z)', source, re.S)
        self.assertIsNotNone(draw)
        self.assertIn('ensure_laid_out()', draw.group(0))


@needs_ui
class OverlayRegistryTests(unittest.TestCase):
    """The registry tracks what is actually on screen."""

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_opening_and_closing_tracks_the_registry(self):
        self.assertEqual(display.open_overlays(), [])
        hub = TaskHub()
        self.assertIn(hub, display.open_overlays())
        task = MonkeyLadder()
        self.assertEqual(display.open_overlays(), [hub, task])
        task.close()
        self.assertEqual(display.open_overlays(), [hub])
        hub.close()
        self.assertEqual(display.open_overlays(), [])

    def test_registering_twice_lists_an_overlay_once(self):
        hub = TaskHub()
        display.register_overlay(hub)
        self.assertEqual(display.open_overlays().count(hub), 1)
        hub.close()

    def test_closing_twice_is_harmless(self):
        hub = TaskHub()
        hub.close()
        hub.close()
        self.assertEqual(display.open_overlays(), [])

    def test_a_registered_overlay_is_laid_out_again(self):
        class Probe:
            def __init__(self):
                self.count = 0

            def relayout(self):
                self.count += 1

        probe = Probe()
        display.register_overlay(probe)
        try:
            geometry.set_window_size(1024, 768)
            display.relayout()
            self.assertEqual(probe.count, 1)
        finally:
            display.unregister_overlay(probe)

    def test_a_broken_overlay_does_not_strand_the_player(self):
        class Broken:
            def relayout(self):
                raise RuntimeError('boom')

        broken = Broken()
        display.register_overlay(broken)
        try:
            geometry.set_window_size(1024, 768)
            display.relayout()          # must not raise
            self.assertEqual(display._laid_out_for, geometry.pixel_size())
        finally:
            display.unregister_overlay(broken)

    def test_a_resize_notifies_the_size_listeners(self):
        calls = []

        def listener():
            calls.append(True)

        geometry.add_size_listener(listener)
        try:
            geometry.set_window_size(1024, 768)
            self.assertEqual(len(calls), 1)
            geometry.set_window_size(1024, 768)   # no change, no call
            self.assertEqual(len(calls), 1)
        finally:
            geometry.remove_size_listener(listener)
        geometry.set_window_size(800, 600)
        self.assertEqual(len(calls), 1)

    def test_a_broken_listener_does_not_break_resizing(self):
        def listener():
            raise RuntimeError('boom')

        geometry.add_size_listener(listener)
        try:
            self.assertEqual(geometry.set_window_size(1024, 768), (1024, 768))
        finally:
            geometry.remove_size_listener(listener)

    def test_drawing_lays_out_even_if_nothing_pumped_the_events(self):
        message = Message('hello')
        try:
            geometry.set_window_size(1024, 768)
            display._laid_out_for = (0, 0)      # pretend the resize was missed
            message.on_draw()
            self.assertEqual(display._laid_out_for, geometry.pixel_size())
        finally:
            message.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
