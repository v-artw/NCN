"""SMC-owned research package, separated from ``ashare_edge_scout`` on 2026-09-27.

Dependency direction is strictly smc -> main: modules here import from
``ashare_edge_scout`` (MKF/main tree), but the main tree must never import
from this package. Deleting or relocating ``smc/`` has to leave MKF untouched.
"""
