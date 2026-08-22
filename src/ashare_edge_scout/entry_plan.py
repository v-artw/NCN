"""Compatibility module alias for :mod:`ashare_edge_scout.signals.entry_plan`."""

import sys
from .signals import entry_plan as _implementation
sys.modules[__name__] = _implementation
