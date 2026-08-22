"""Compatibility module alias for :mod:`ashare_edge_scout.signals.start_signals`."""

import sys
from .signals import start_signals as _implementation
sys.modules[__name__] = _implementation
