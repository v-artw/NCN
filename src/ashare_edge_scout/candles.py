"""Compatibility module alias for :mod:`ashare_edge_scout.signals.candles`."""

import sys
from .signals import candles as _implementation
sys.modules[__name__] = _implementation
