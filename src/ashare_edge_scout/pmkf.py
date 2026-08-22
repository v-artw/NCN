"""Compatibility module alias for :mod:`ashare_edge_scout.pmkf_mkf.core`."""

import sys

from .pmkf_mkf import core as _implementation

sys.modules[__name__] = _implementation
