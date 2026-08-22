"""Compatibility module alias for :mod:`ashare_edge_scout.signals.signal_scoring`."""

import sys
from .signals import signal_scoring as _implementation
sys.modules[__name__] = _implementation
