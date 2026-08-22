"""Compatibility module alias for :mod:`ashare_edge_scout.pmkf_mkf.quality`."""

import sys

from .pmkf_mkf import quality as _implementation

sys.modules[__name__] = _implementation
