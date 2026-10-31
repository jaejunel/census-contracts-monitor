"""Guards against silently-wrong data.

The dominant failure mode for this source is not a parse error -- the API
returns clean JSON -- but a *silently wrong query*. USASpending drops filter
keys it does not recognise and returns the unfiltered universe, reporting it
only in a `messages` array. check_filters_applied() is therefore the single
most important guard here, and runs on every page of every fetch.
"""

from __future__ import annotations

from . import config


class FilterIgnoredError(Exception):
    """The API ignored one or more of our filters -- results are not ours."""


class EmptyResultError(Exception):
    """A fetch returned implausibly few awards."""


class ChurnGuardError(Exception):
    """A diff looks more like a query/source break than real change."""


def check_filters_applied(payload: dict) -> None:
    """Abort if USASpending reports any filter as unused.

    The message text looks like:
      "The following filters from the request were not used: {'foo'}"
    """
    for msg in payload.get("messages", []) or []:
        if "not used" in msg.lower():
            raise FilterIgnoredError(
                f"USASpending ignored one or more request filters, so these "
                f"results are NOT scoped to the Census accounts and must not "
                f"be recorded. API said: {msg!r}"
            )


def check_result_count(n: int, context: str, prior_count: int | None = None,
                       fy_days_elapsed: int | None = None) -> None:
    """Abort on an implausibly small result set.

    "Implausible" depends on context, which the first version of this guard
    got wrong and a live run caught: a fiscal year that began three weeks ago
    legitimately has only a handful of awards, and failing on that is a false
    alarm, not a detection.

    The rules, in order:

    * If we have a prior snapshot for this fiscal year, a large *drop* is the
      signal -- awards do not vanish from USASpending en masse. More than
      half disappearing is alarming regardless of absolute count.
    * With no prior snapshot, the absolute floor only applies once the fiscal
      year is actually underway (90+ days). Before that, low counts are
      expected and we record them quietly.
    """
    if prior_count is not None and prior_count >= config.MIN_EXPECTED_AWARDS:
        if n < prior_count * 0.5:
            raise EmptyResultError(
                f"{context}: {n} awards returned, down from {prior_count} in "
                f"the previous snapshot -- more than half have disappeared. "
                f"Awards do not vanish from USASpending like this. Refusing "
                f"to record it."
            )
        return

    if fy_days_elapsed is not None and fy_days_elapsed < 90:
        return  # young fiscal year: a small count is expected

    if n < config.MIN_EXPECTED_AWARDS:
        raise EmptyResultError(
            f"{context}: only {n} awards returned for a fiscal year that is "
            f"well underway, below the plausibility floor of "
            f"{config.MIN_EXPECTED_AWARDS}. Either the API changed, the TAS "
            f"codes are wrong, or there is an outage."
        )


def check_churn(n_added: int, n_removed: int, old_count: int, new_count: int) -> None:
    total = max(old_count, new_count, 1)
    churn = n_added + n_removed
    frac = churn / total
    if frac > config.MAX_CHURN_FRACTION:
        raise ChurnGuardError(
            f"{churn} of {total} awards ({frac:.0%}) added or removed between "
            f"snapshots -- above the {config.MAX_CHURN_FRACTION:.0%} threshold. "
            f"Contract records do change retroactively, but not like this. "
            f"Refusing to write a changelog entry; the extracted CSV is saved "
            f"with a .suspect.csv suffix for inspection."
        )
