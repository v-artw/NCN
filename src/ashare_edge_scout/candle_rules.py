"""Compatibility module alias for :mod:`ashare_edge_scout.signals.candle_rules`."""

import sys
from .signals import candle_rules as _implementation
sys.modules[__name__] = _implementation
