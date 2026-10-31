#!/usr/bin/env python3
"""CLI for the Census contracts monitor.

    python monitor.py run                 Check the current fiscal year (and,
                                           in Oct-Dec, the prior one too,
                                           since late modifications are common).
    python monitor.py backfill --from 2008
                                          Build the historical record. Unlike
                                           the inventory monitor, no archive
                                           luck is needed: USASpending serves
                                           history back to FY2008 directly.

Exit code is nonzero when something needs a human: a scope failure (the API
ignored our filters), an implausible result count, or a churn-guard trip.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from contracts_monitor import changelog, guards
from contracts_monitor.pipeline import Outcome, current_fy, process_fy


def _report(o: Outcome) -> int:
    tag = f"FY{o.fy}"
    if o.status == "unchanged":
        changelog.append_check_log(f"- {o.date} {tag}: unchanged ({o.count} awards)")
        print(f"{tag}: no change ({o.count} awards)")
        return 0
    if o.status == "initial":
        changelog.append_check_log(f"- {o.date} {tag}: initial snapshot ({o.detail})")
        print(f"{tag}: initial snapshot — {o.detail}")
        return 0
    if o.status == "diffed":
        changelog.append_check_log(f"- {o.date} {tag}: diffed ({o.detail})")
        print(f"{tag}: changed — {o.detail}")
        return 0
    if o.status == "guard_tripped":
        changelog.append_check_log(f"- {o.date} {tag}: CHURN GUARD TRIPPED — {o.detail}")
        print(f"{tag}: CHURN GUARD TRIPPED\n{o.detail}", file=sys.stderr)
        return 1
    raise AssertionError(o.status)


def cmd_run(args) -> int:
    fys = [current_fy()]
    if date.today().month in (10, 11, 12):
        # Awards keep being modified after the fiscal year closes; re-check
        # the prior year through the first quarter.
        fys.append(current_fy() - 1)
    rc = 0
    for fy in fys:
        try:
            rc |= _report(process_fy(fy, today=args.date))
        except guards.FilterIgnoredError as e:
            changelog.append_check_log(f"- {args.date or date.today().isoformat()} FY{fy}: SCOPE FAILURE — {e}")
            print(f"FY{fy}: SCOPE FAILURE\n{e}", file=sys.stderr)
            rc = 1
        except guards.EmptyResultError as e:
            changelog.append_check_log(f"- {args.date or date.today().isoformat()} FY{fy}: EMPTY RESULT — {e}")
            print(f"FY{fy}: EMPTY RESULT\n{e}", file=sys.stderr)
            rc = 1
    return rc


def cmd_backfill(args) -> int:
    rc = 0
    for fy in range(args.start, current_fy() + 1):
        print(f"--- FY{fy} ---")
        try:
            rc |= _report(process_fy(fy, today=args.date))
        except (guards.FilterIgnoredError, guards.EmptyResultError) as e:
            print(f"FY{fy}: SKIPPED — {e}", file=sys.stderr)
    return rc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", default=None, help="Override snapshot date (testing).")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Check the current fiscal year.").set_defaults(func=cmd_run)
    b = sub.add_parser("backfill", help="Build the historical record.")
    b.add_argument("--from", dest="start", type=int, default=2008, help="First fiscal year (default 2008).")
    b.set_defaults(func=cmd_backfill)
    a = p.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
