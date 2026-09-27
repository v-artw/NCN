"""Path bootstrap for SMC-owned tests.

``smc/tests`` runs against two source trees: the main package in ``REPO/src``
(data/research/config modules the SMC pipeline still consumes) and the SMC
package in ``smc/src``. The root ``pyproject.toml`` only puts ``src`` on the
path via pytest ``pythonpath``, and it deliberately never references ``smc/``
so deleting the subproject cannot break main-suite collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

SMC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SMC_ROOT.parent

for candidate in (str(REPO_ROOT / "src"), str(SMC_ROOT / "src"), str(REPO_ROOT), str(SMC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)
