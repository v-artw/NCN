"""Compatibility module alias for :mod:`ashare_edge_scout.data.reference_prices`."""

import sys

from .data import reference_prices as _implementation

sys.modules[__name__] = _implementation
