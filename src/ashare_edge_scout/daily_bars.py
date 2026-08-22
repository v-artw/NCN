"""Compatibility module alias for :mod:`ashare_edge_scout.data.daily_bars`."""

import sys

from .data import daily_bars as _implementation

sys.modules[__name__] = _implementation
