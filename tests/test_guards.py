"""Guard tests. check_filters_applied is the most important test in this
suite: the API's silent filter-dropping is this project's defining hazard."""
from __future__ import annotations
import pytest
from contracts_monitor.guards import (ChurnGuardError, EmptyResultError,
                                      FilterIgnoredError, check_churn,
                                      check_filters_applied, check_result_count)


def test_clean_payload_passes():
    check_filters_applied({"results": [], "messages": []})
    check_filters_applied({"results": []})  # messages absent entirely


def test_ignored_filter_raises():
    """The real message observed during calibration, when a plausible but
    wrong filter name silently returned all federal awards."""
    payload = {"messages": [
        "The following filters from the request were not used: "
        "{'federal_account_symbol'}. See https://api.usaspending.gov/docs/"]}
    with pytest.raises(FilterIgnoredError, match="ignored"):
        check_filters_applied(payload)


def test_unrelated_message_does_not_raise():
    payload = {"messages": [
        "For searches, time period start and end dates are currently limited "
        "to an earliest date of 2007-10-01."]}
    check_filters_applied(payload)  # must not raise


def test_result_count_floor():
    check_result_count(215, "FY2026")
    with pytest.raises(EmptyResultError):
        check_result_count(0, "FY2026")


def test_churn_guard():
    check_churn(5, 5, 200, 200)                      # 5% -- fine
    with pytest.raises(ChurnGuardError):
        check_churn(60, 60, 200, 200)                # 60% -- not fine


def test_churn_boundary_is_exclusive():
    from contracts_monitor import config
    n = int(100 * config.MAX_CHURN_FRACTION)
    check_churn(n, 0, 100, 100 - n)                  # exactly at threshold


def test_young_fiscal_year_is_not_an_alarm():
    """Regression: the first live run failed because FY2027, three weeks
    old with 5 awards, tripped the absolute floor. A young fiscal year with
    few awards is normal."""
    check_result_count(5, "FY2027", prior_count=None, fy_days_elapsed=30)


def test_mature_fiscal_year_with_no_awards_still_alarms():
    with pytest.raises(EmptyResultError):
        check_result_count(5, "FY2026", prior_count=None, fy_days_elapsed=300)


def test_large_drop_against_prior_snapshot_alarms():
    with pytest.raises(EmptyResultError, match="disappeared"):
        check_result_count(40, "FY2026", prior_count=215)


def test_small_drop_against_prior_snapshot_is_fine():
    check_result_count(210, "FY2026", prior_count=215)


def test_young_fy_with_prior_snapshot_uses_drop_rule_not_floor():
    """Once a young FY has a prior snapshot, growth is normal and only a
    collapse should alarm."""
    check_result_count(9, "FY2027", prior_count=5, fy_days_elapsed=40)
