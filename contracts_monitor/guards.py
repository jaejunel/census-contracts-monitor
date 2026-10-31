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


def check_result_count(n: int, context: str) -> None:
    if n < config.MIN_EXPECTED_AWARDS:
        raise EmptyResultError(
            f"{context}: only {n} awards returned, below the plausibility "
            f"floor of {config.MIN_EXPECTED_AWARDS}. Either the API changed, "
            f"the TAS codes are wrong, or there is an outage. Refusing to "
            f"record this as a mass disappearance."
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
