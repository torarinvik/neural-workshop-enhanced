# -*- coding: utf-8 -*-
"""Odd Stripe.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .twins import _Rung


class OddStripeEnv(_Rung):
    """Odd Stripe."""

    task_class = ('neural_workshop.ui.oddstripe', 'OddStripe')
    ports = 12


verify_odd_stripe_outcome = OddStripeEnv.verifier()

__all__ = ['OddStripeEnv']
