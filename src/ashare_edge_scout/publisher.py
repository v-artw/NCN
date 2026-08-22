"""Compatibility module alias for :mod:`ashare_edge_scout.publication.publisher`."""

import sys

from .publication import publisher as _implementation

sys.modules[__name__] = _implementation
