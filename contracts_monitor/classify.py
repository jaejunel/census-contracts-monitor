"""Flag awards that look like purchases of data (as opposed to IT, services,
construction, etc.).

This is a FLAG applied at extract time, not a filter applied at fetch time.
Every award under the tracked accounts is captured regardless; misclassified
rows can be re-classified later from the stored snapshots without re-fetching
or losing anything.
"""

from __future__ import annotations

import re

from . import config

_PATS = [re.compile(p, re.I) for p in config.DATA_ACQUISITION_PATTERNS]
_EXCL = [re.compile(p, re.I) for p in config.DATA_ACQUISITION_EXCLUDE]


def is_data_acquisition(description: str, naics: str = "") -> bool:
    """True if the award description reads like a data purchase.

    Exclusions are applied first: "DATA CENTER", "DATA WAREHOUSE",
    software/licence/subscription language all describe IT procurement that
    happens to contain the word 'data'.
    """
    text = (description or "").strip()
    if not text:
        return False
    if any(e.search(text) for e in _EXCL):
        return False
    return any(p.search(text) for p in _PATS)


def naics_is_information(naics: str) -> bool:
    """Corroborating signal: NAICS sector 51 is Information."""
    return str(naics or "").strip().startswith(config.NAICS_INFORMATION_PREFIX)
