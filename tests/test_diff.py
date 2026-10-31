"""Diff tests: adds, removes, retroactive modifications, and reordering."""
from __future__ import annotations
from contracts_monitor.diff import diff_awards


def row(uid, amt="100", desc="X DATA", rec="ACME", da="yes"):
    return {"unique_award_id": uid, "award_id": uid, "recipient_name": rec,
            "award_amount": amt, "total_outlays": "0", "description": desc,
            "start_date": "2026-01-01", "end_date": "2026-12-31",
            "last_modified_date": "2026-01-01", "awarding_agency": "DOC",
            "awarding_sub_agency": "Census", "contract_award_type": "D",
            "naics": "518210", "psc": "R799", "data_acquisition": da}


def test_add_remove_modify_and_reorder():
    old = [row("A"), row("B"), row("C", amt="500")]
    new = [row("C", amt="900"), row("A"), row("D")]   # reordered; B gone; D new; C amount changed
    r = diff_awards(old, new)
    assert [x["unique_award_id"] for x in r.added] == ["D"]
    assert [x["unique_award_id"] for x in r.removed] == ["B"]
    assert len(r.modified) == 1
    assert r.modified[0].key == "C"
    assert r.modified[0].changes == {"award_amount": ("500", "900")}


def test_pure_reordering_is_not_a_change():
    old = [row("A"), row("B")]
    new = [row("B"), row("A")]
    assert diff_awards(old, new).total_changes == 0


def test_last_modified_date_churn_is_ignored():
    """last_modified_date ticks on administrative touches; it is excluded
    from COMPARE_FIELDS so it cannot flood the changelog."""
    old = [row("A")]
    new = [dict(row("A"), last_modified_date="2026-09-09")]
    assert diff_awards(old, new).total_changes == 0


def test_reclassification_is_reported():
    """If a description is revised such that it now reads as a data
    purchase, that reclassification should surface."""
    old = [row("A", desc="SUPPORT SERVICES", da="")]
    new = [row("A", desc="ACQUISITION OF VOTER DATA.", da="yes")]
    r = diff_awards(old, new)
    assert "data_acquisition" in r.modified[0].changes
