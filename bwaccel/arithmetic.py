# -*- coding: utf-8 -*-
"""Arithmetic n-back: exact Decimal arithmetic, never ``eval``.

The player is shown a number and must apply the current operation to it
and to the number *n* trials back. Operations are named, applied here by
name, and evaluated in :class:`~decimal.Decimal` so that the answer the
player typed is compared exactly.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Sequence, Tuple

from .fallback import _resolve_back

#: The operations a session may use.
ARITHMETIC_OPS: Tuple[str, ...] = ('add', 'subtract', 'multiply', 'divide')


def apply_arithmetic(op: str, left: Any, right: Any) -> Decimal:
    """Apply named operation *op* to two operands.

    Raises ``ValueError`` for an unknown operation, and
    ``InvalidOperation`` / ``ZeroDivisionError`` for bad operands.
    """
    if op not in ARITHMETIC_OPS:
        raise ValueError('unknown arithmetic operation: %r' % (op,))
    a = left if isinstance(left, Decimal) else Decimal(left)
    b = right if isinstance(right, Decimal) else Decimal(right)
    if op == 'add':
        return a + b
    if op == 'subtract':
        return a - b
    if op == 'multiply':
        return a * b
    return a / b


def score_arithmetic(nback: int, crab: bool = False,
                     variable_list: Optional[Sequence[int]] = None,
                     session: Optional[Dict[str, Any]] = None
                     ) -> Tuple[int, int]:
    """Rights and wrongs for an arithmetic session."""
    if session is None:
        return (0, 0)
    numbers = session.get('numbers') or []
    ops = session.get('operation') or []
    answers = session.get('arithmetic_input') or []

    rights = wrongs = 0
    for x in range(nback, min(len(numbers), len(ops), len(answers))):
        back = _resolve_back(x, nback, crab, variable_list)
        if back > x:
            continue
        try:
            expected = apply_arithmetic(ops[x], numbers[x - back], numbers[x])
            given = answers[x]
            if not isinstance(given, Decimal):
                given = Decimal(given)
            if expected == given:
                rights += 1
            else:
                wrongs += 1
        except (InvalidOperation, ZeroDivisionError, ValueError, TypeError):
            wrongs += 1
    return (rights, wrongs)
