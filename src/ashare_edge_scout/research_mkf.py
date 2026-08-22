"""Compatibility module alias for :mod:`ashare_edge_scout.pmkf_mkf.research`."""

import sys

from .pmkf_mkf import research as _implementation

sys.modules[__name__] = _implementation
