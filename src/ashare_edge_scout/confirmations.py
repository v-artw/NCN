"""Compatibility module alias for :mod:`ashare_edge_scout.signals.confirmations`."""

import sys
from .signals import confirmations as _implementation
sys.modules[__name__] = _implementation
