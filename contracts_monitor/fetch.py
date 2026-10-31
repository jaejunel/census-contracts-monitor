"""Fetching award records from the USASpending API.

Every page is checked for ignored filters before its results are accepted --
see guards.check_filters_applied and the config module docstring.
"""

from __future__ import annotations

import hashlib
import json
import time

import requests

from . import config
from .guards import check_filters_applied

_MAX_ATTEMPTS = 5
_BACKOFF = 4
_PAGE_LIMIT = 100
_MAX_PAGES = 100  # safety stop; ~215 awards/FY means 3 pages in practice


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(awards: list[dict]) -> str:
    """Hash of the award set, independent of API result ordering.

    Sorting by the stable award id means a pure reordering by the API does
    not read as a change -- the same principle as the inventory monitor's
    key-based diff.
    """
    rows = sorted(awards, key=lambda a: str(a.get("generated_internal_id", "")))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(blob)


def _post(body: dict, timeout: int) -> dict:
    last = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            r = requests.post(config.API_URL, json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            last = e
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_BACKOFF * attempt)
    raise last  # type: ignore[misc]


def fetch_awards(start_date: str, end_date: str, timeout: int = 90) -> list[dict]:
    """All prime contract awards under config.TAS_CODES in a date window.

    Dates are ISO strings. USASpending's search is limited to action dates
    from 2007-10-01 onward.
    """
    out: list[dict] = []
    page = 1
    while page <= _MAX_PAGES:
        body = {
            "filters": {
                "time_period": [{"start_date": start_date, "end_date": end_date}],
                "award_type_codes": config.AWARD_TYPE_CODES,
                "tas_codes": config.TAS_CODES,
            },
            "fields": list(config.API_FIELDS.keys()),
            "page": page,
            "limit": _PAGE_LIMIT,
            "sort": "Award Amount",
            "order": "desc",
            "subawards": False,
        }
        payload = _post(body, timeout)
        check_filters_applied(payload)  # <- the critical guard
        out.extend(payload.get("results", []))
        if not payload.get("page_metadata", {}).get("hasNext"):
            break
        page += 1
    return out
