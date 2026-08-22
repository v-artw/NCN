"""Compatibility module alias for :mod:`ashare_edge_scout.pmkf_mkf.candidates`."""

import sys

from .pmkf_mkf import candidates as _implementation

sys.modules[__name__] = _implementation
