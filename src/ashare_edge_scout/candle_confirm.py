"""Compatibility module alias for :mod:`ashare_edge_scout.signals.candle_confirm`."""

import sys
from .signals import candle_confirm as _implementation
sys.modules[__name__] = _implementation
