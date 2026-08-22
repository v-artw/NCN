"""Compatibility module alias for :mod:`ashare_edge_scout.data.contracts`."""

import sys

from .data import contracts as _implementation

sys.modules[__name__] = _implementation
