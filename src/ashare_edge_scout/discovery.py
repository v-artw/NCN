"""Compatibility module alias for :mod:`ashare_edge_scout.signals.discovery`."""

import sys
from .signals import discovery as _implementation
sys.modules[__name__] = _implementation
