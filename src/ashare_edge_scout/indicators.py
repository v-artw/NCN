"""Compatibility module alias for :mod:`ashare_edge_scout.signals.indicators`."""

import sys
from .signals import indicators as _implementation
sys.modules[__name__] = _implementation
