"""Reading and writing extracted/*.csv."""

from __future__ import annotations

import csv

from . import config


def write_csv(rows: list[dict[str, str]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=config.COLUMN_NAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]
