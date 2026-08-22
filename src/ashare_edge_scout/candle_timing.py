"""Compatibility module alias for :mod:`ashare_edge_scout.signals.candle_timing`."""

import sys
from .signals import candle_timing as _implementation
sys.modules[__name__] = _implementation
