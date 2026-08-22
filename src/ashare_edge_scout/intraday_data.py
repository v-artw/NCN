"""Compatibility module alias for :mod:`ashare_edge_scout.data.intraday_data`."""

import sys

from .data import intraday_data as _implementation

sys.modules[__name__] = _implementation
