"""Compatibility module alias for :mod:`ashare_edge_scout.audit.prospective`."""

import sys

from .audit import prospective as _implementation

sys.modules[__name__] = _implementation
