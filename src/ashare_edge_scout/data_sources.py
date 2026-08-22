"""Compatibility module alias for :mod:`ashare_edge_scout.data.data_sources`."""

import sys

from .data import data_sources as _implementation

sys.modules[__name__] = _implementation
