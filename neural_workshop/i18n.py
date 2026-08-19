# -*- coding: utf-8 -*-
"""Translation.

The original program relied on ``gettext.install`` putting ``_`` into
builtins, which made every use of it invisible to static analysis. Here
``_`` is an ordinary function that modules import by name.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import gettext
import os

_LOCALE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'res', 'i18n')

_translation = gettext.translation('messages', localedir=_LOCALE_DIR,
                                   fallback=True)


def _(message: str) -> str:
    """Translate *message* into the active language."""
    return _translation.gettext(message)


def set_language(language: str) -> None:
    """Switch the active language to *language* (e.g. ``'de'``)."""
    global _translation
    _translation = gettext.translation(
        'messages', localedir=_LOCALE_DIR, languages=[language],
        fallback=True)
