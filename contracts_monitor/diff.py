"""Diff two award snapshots by stable award id.

Unlike the PDF inventory, USASpending gives us a real primary key
(generated_internal_id), so row identity is not a heuristic. The interesting
complication here is different: contract records are **revised
retroactively**. An award's obligated amount, description, or period can
change long after it was signed, so "modified" is a first-class outcome
rather than an edge case.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config


@dataclass
class ModifiedAward:
    key: str
    changes: dict[str, tuple[str, str]]
    recipient: str = ""
    description: str = ""


@dataclass
class DiffResult:
    added: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    modified: list[ModifiedAward] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.removed) + len(self.modified)


def diff_awards(old_rows: list[dict], new_rows: list[dict]) -> DiffResult:
    old = {r["unique_award_id"]: r for r in old_rows}
    new = {r["unique_award_id"]: r for r in new_rows}
    res = DiffResult()
    for k in sorted(set(new) - set(old)):
        res.added.append(new[k])
    for k in sorted(set(old) - set(new)):
        res.removed.append(old[k])
    for k in sorted(set(old) & set(new)):
        ch = {}
        for f in config.COMPARE_FIELDS:
            o, n = (old[k].get(f) or ""), (new[k].get(f) or "")
            if o != n:
                ch[f] = (o, n)
        if ch:
            res.modified.append(
                ModifiedAward(key=k, changes=ch,
                              recipient=new[k].get("recipient_name", ""),
                              description=new[k].get("description", ""))
            )
    return res
