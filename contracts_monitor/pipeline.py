"""Orchestration shared by the run and backfill commands."""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from datetime import date

from . import changelog, config, csvio, guards
from .diff import diff_awards
from .extract import to_rows
from .fetch import canonical_hash, fetch_awards

_SNAP_RE = re.compile(r"^awards-(FY\d{4})-(\d{4}-\d{2}-\d{2})\.json$")
_EXT_RE = re.compile(r"^awards-(FY\d{4})-(\d{4}-\d{2}-\d{2})\.csv$")


def fy_window(fy: int) -> tuple[str, str]:
    """US federal fiscal year: Oct 1 (prev year) .. Sep 30."""
    return f"{fy-1}-10-01", f"{fy}-09-30"


def current_fy(today: date | None = None) -> int:
    d = today or date.today()
    return d.year + 1 if d.month >= 10 else d.year


def snapshot_path(fy: int, d: str) -> str:
    return os.path.join(config.SNAPSHOTS_DIR, f"awards-FY{fy}-{d}.json")


def extracted_path(fy: int, d: str) -> str:
    return os.path.join(config.EXTRACTED_DIR, f"awards-FY{fy}-{d}.csv")


def suspect_path(fy: int, d: str) -> str:
    return os.path.join(config.EXTRACTED_DIR, f"awards-FY{fy}-{d}.suspect.csv")


def _dated(directory: str, pattern: re.Pattern, fy: int) -> list[tuple[str, str]]:
    out = []
    if not os.path.isdir(directory):
        return out
    for p in glob.glob(os.path.join(directory, "*")):
        m = pattern.match(os.path.basename(p))
        if m and m.group(1) == f"FY{fy}":
            out.append((m.group(2), p))
    return sorted(out)


def latest_snapshot(fy: int):
    f = _dated(config.SNAPSHOTS_DIR, _SNAP_RE, fy)
    return f[-1] if f else None


def latest_extracted(fy: int):
    f = _dated(config.EXTRACTED_DIR, _EXT_RE, fy)
    return f[-1] if f else None


@dataclass
class Outcome:
    fy: int
    date: str
    status: str  # unchanged | initial | diffed | guard_tripped | error
    detail: str
    count: int | None = None


def process_fy(fy: int, today: str | None = None) -> Outcome:
    d = today or date.today().isoformat()
    os.makedirs(config.SNAPSHOTS_DIR, exist_ok=True)
    os.makedirs(config.EXTRACTED_DIR, exist_ok=True)

    start, end = fy_window(fy)
    awards = fetch_awards(start, end)          # raises FilterIgnoredError if scoped wrong
    guards.check_result_count(len(awards), f"FY{fy}")

    new_hash = canonical_hash(awards)
    prev_snap = latest_snapshot(fy)
    if prev_snap:
        prev = json.load(open(prev_snap[1], encoding="utf-8"))
        if prev.get("content_hash") == new_hash:
            return Outcome(fy, d, "unchanged", f"hash {new_hash[:12]}... matches {prev_snap[1]}", len(awards))

    snap = snapshot_path(fy, d)
    json.dump(
        {"fetched": d, "fiscal_year": fy, "tas_codes": config.TAS_CODES,
         "window": [start, end], "content_hash": new_hash,
         "award_count": len(awards), "awards": awards},
        open(snap, "w", encoding="utf-8"), indent=1, sort_keys=True,
    )

    rows = to_rows(awards)
    prev_ext = latest_extracted(fy)
    if prev_ext is None:
        csvio.write_csv(rows, extracted_path(fy, d))
        entry = (f"## {d}\n\nFiscal year {fy}: initial snapshot, {len(rows)} awards "
                 f"({sum(1 for r in rows if r['data_acquisition']=='yes')} flagged as data acquisitions). "
                 f"Nothing to diff against yet.\n")
        changelog.prepend_changelog(entry)
        return Outcome(fy, d, "initial", f"{len(rows)} awards", len(rows))

    old_rows = csvio.read_csv(prev_ext[1])
    res = diff_awards(old_rows, rows)
    try:
        guards.check_churn(len(res.added), len(res.removed), len(old_rows), len(rows))
    except guards.ChurnGuardError as e:
        csvio.write_csv(rows, suspect_path(fy, d))
        return Outcome(fy, d, "guard_tripped", str(e), len(rows))

    csvio.write_csv(rows, extracted_path(fy, d))
    changelog.prepend_changelog(
        changelog.format_entry(date=d, old_count=len(old_rows), new_count=len(rows), result=res, fy=f"FY{fy}")
    )
    return Outcome(fy, d, "diffed",
                   f"{len(res.added)} added, {len(res.removed)} removed, {len(res.modified)} modified",
                   len(rows))
