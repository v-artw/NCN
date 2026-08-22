"""Compatibility module alias for :mod:`ashare_edge_scout.pmkf_mkf.features`."""

import sys

from .pmkf_mkf import features as _implementation

sys.modules[__name__] = _implementation
