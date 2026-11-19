# Fork history

What changed when Neural Workshop was forked from Brain Workshop.
Python 2 is no longer supported; the notes below are kept as a record.

## Changes at the fork

* Elements on the screen scale depending on the window size, making it much more
  usable if you have a hidpi monitor.
* Using a widescreen resolution causes items on the screen to be placed/scale properly
* Fullscreen mode sets the resolution of the screen automatically
* Font size scales based on window size
  * Positioning of items also scales with window size
  * Window position and font size are determined with one function to do scaling,
    thereby making it easier in the future to make adjustments
* Set fonts differently for serif and for monospace fonts, eventually to allow
  them to be configurable.
* Now compatible with Python 3
  * Fixed issues with at least three modules not loading. This was due to
    being renamed or their semantics changing. Fixed in a way to maintain Python 2
    compatibility.
  * Fix alignment of the polygons/icons in the grid due to changes to division
    in Python 3
* Compatible with *both* Python 2 and Python 3!
* Fixed crash with text.Label not recognizing `halign`; use `align` instead since
  `halign` is deprecated. Though to avoid breaking anything, we try `align` first
  and if that fails we fall back to using `halign`
* Fix many more crashes and issues of Brain Workshop failing to launch
