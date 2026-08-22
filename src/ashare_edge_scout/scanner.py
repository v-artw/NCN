"""Compatibility module alias for :mod:`ashare_edge_scout.scan.scanner`."""

import sys

from .scan import scanner as _implementation

sys.modules[__name__] = _implementation
