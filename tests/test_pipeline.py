"""Pipeline wiring: a guard trip must not make the next run go quiet."""
from __future__ import annotations

import os

from contracts_monitor import pipeline


def award(i, desc="IT SUPPORT"):
    return {"generated_internal_id": f"A{i:03d}", "Award ID": f"X{i}", "Recipient Name": "VENDOR",
            "Award Amount": 100, "Description": desc, "Start Date": "2026-10-05",
            "Last Modified Date": "2026-11-01 00:00:00", "Awarding Sub Agency": "U.S. Census Bureau",
            "NAICS": "541512", "PSC": "DA01"}


def run(monkeypatch, n, today, removed=()):
    awards = [award(i) for i in range(n) if i not in removed]
    monkeypatch.setattr(pipeline, "fetch_awards", lambda s, e: awards)
    return pipeline.process_fy(2027, today=today)


def test_young_year_growth_is_diffed_and_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run(monkeypatch, 6, "2026-11-02").status == "initial"
    out = run(monkeypatch, 9, "2026-11-09")        # the exact production case
    assert out.status == "diffed" and "3 added" in out.detail
    assert os.path.exists("extracted/awards-FY2027-2026-11-09.csv")


def test_tripped_diff_is_retried_not_forgotten(tmp_path, monkeypatch):
    """After a trip the snapshot is saved but no extraction is. The next run
    sees the same hash; it must re-diff, not report 'unchanged'."""
    monkeypatch.chdir(tmp_path)
    run(monkeypatch, 40, "2026-11-02")
    # 20 of 40 disappear: trips even under the young-year (removals-only) rule
    out = run(monkeypatch, 20, "2026-11-09", removed=set(range(20, 40)))
    assert out.status == "guard_tripped"
    assert os.path.exists("extracted/awards-FY2027-2026-11-09.suspect.csv")
    again = run(monkeypatch, 20, "2026-11-10", removed=set(range(20, 40)))
    assert again.status == "guard_tripped"          # still loud, not 'unchanged'
