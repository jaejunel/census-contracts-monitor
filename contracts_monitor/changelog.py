"""Markdown changelog formatting."""

from __future__ import annotations

import os

from . import config
from .diff import DiffResult

_HEADER = (
    "# Changelog\n\n"
    "Changes to Bureau of the Census prime contract awards funded from\n"
    "013-0450 (Periodic Censuses and Programs) and 013-0401 (Current Surveys\n"
    "and Programs), newest first. Awards flagged **[DATA]** matched the\n"
    "data-acquisition classifier -- see README for what that does and does\n"
    "not mean.\n\n"
)


def _money(v) -> str:
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v or "")


def _label(r: dict) -> str:
    flag = "**[DATA]** " if r.get("data_acquisition") == "yes" else ""
    return f"{flag}{r.get('recipient_name','?')} — {r.get('description','') or '(no description)'} ({_money(r.get('award_amount'))})"


def format_entry(*, date: str, old_count: int, new_count: int, result: DiffResult, fy: str) -> str:
    L = [f"## {date}", "", f"Fiscal year {fy}: {old_count} → {new_count} awards.", "",
         f"**{len(result.added)} added, {len(result.removed)} removed, {len(result.modified)} modified.**", ""]
    da = [r for r in result.added if r.get("data_acquisition") == "yes"]
    if da:
        L += [f"### Data acquisitions added ({len(da)})", ""]
        L += [f"- {_label(r)}" for r in sorted(da, key=lambda r: -float(r.get("award_amount") or 0))]
        L.append("")
    other = [r for r in result.added if r.get("data_acquisition") != "yes"]
    if other:
        L += [f"### Other awards added ({len(other)})", ""]
        L += [f"- {_label(r)}" for r in sorted(other, key=lambda r: -float(r.get("award_amount") or 0))]
        L.append("")
    if result.removed:
        L += [f"### Removed ({len(result.removed)})", ""]
        L += [f"- {_label(r)}" for r in result.removed]
        L.append("")
    if result.modified:
        L += [f"### Modified ({len(result.modified)})", ""]
        for m in result.modified:
            flag = "**[DATA]** " if any(
                f == "data_acquisition" and n == "yes" for f, (o, n) in m.changes.items()
            ) else ""
            L.append(f"- {flag}{m.recipient} — {m.description[:70]}")
            for f, (o, n) in m.changes.items():
                if f in ("award_amount", "total_outlays"):
                    L.append(f"  - `{f}`: {_money(o)} → {_money(n)}")
                else:
                    L.append(f"  - `{f}`: {o[:70]!r} → {n[:70]!r}")
        L.append("")
    if not result.total_changes:
        L += ["No changes detected (content hash differed, but awards matched).", ""]
    return "\n".join(L)


def prepend_changelog(entry: str, path: str = config.CHANGELOG_PATH) -> None:
    existing = open(path, encoding="utf-8").read() if os.path.exists(path) else _HEADER
    i = existing.find("\n## ")
    if i == -1:
        out = existing.rstrip("\n") + "\n\n" + entry.strip("\n") + "\n"
    else:
        i += 1
        out = existing[:i] + entry.strip("\n") + "\n\n" + existing[i:]
    open(path, "w", encoding="utf-8").write(out)


def latest_entry(path: str = config.CHANGELOG_PATH) -> str:
    if not os.path.exists(path):
        return ""
    c = open(path, encoding="utf-8").read()
    s = c.find("\n## ")
    if s == -1:
        return ""
    s += 1
    e = c.find("\n## ", s)
    return (c[s:e] if e != -1 else c[s:]).strip("\n")


def append_check_log(line: str, path: str = config.CHECK_LOG_PATH) -> None:
    need = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if need:
            f.write("# Check log\n\nEvery run of the monitor, whether or not awards changed.\n\n")
        f.write(line.rstrip("\n") + "\n")
