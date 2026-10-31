"""Turn raw API award records into normalised rows."""

from __future__ import annotations

from . import config
from .classify import is_data_acquisition


def _flat(v) -> str:
    """API returns NAICS/PSC as nested dicts in some response shapes."""
    if isinstance(v, dict):
        return str(v.get("code") or v.get("description") or "")
    return "" if v is None else str(v)


def to_rows(awards: list[dict]) -> list[dict[str, str]]:
    rows = []
    for a in awards:
        row = {"unique_award_id": str(a.get("generated_internal_id") or "")}
        for api_field, col in config.API_FIELDS.items():
            row[col] = _flat(a.get(api_field))
        row["data_acquisition"] = (
            "yes" if is_data_acquisition(row.get("description", ""), row.get("naics", "")) else ""
        )
        rows.append(row)
    rows.sort(key=lambda r: r["unique_award_id"])
    return rows
