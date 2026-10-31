# census-contracts-monitor

[![Monitor](https://github.com/jaejunel/census-contracts-monitor/actions/workflows/monitor.yml/badge.svg)](https://github.com/jaejunel/census-contracts-monitor/actions/workflows/monitor.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)

Tracks U.S. Census Bureau contract awards on USASpending.gov and flags purchases of commercial data.

Companion to [census-inventory-monitor](https://github.com/jaejunel/census-inventory-monitor). That project tracks what the Bureau *says it holds*; this one tracks what it *paid for*.

## Contents

- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Configuration](#configuration)
- [Output](#output)
- [Findings](#findings)
- [Reliability](#reliability)
- [Limitations](#limitations)
- [Development](#development)
- [Citation](#citation)
- [License](#license)

## Overview

The Census Bureau buys commercial data — voter registration files, retail scanner transactions, housing and parcel records — through ordinary federal contracts. Those contracts are public on USASpending.gov, but they are scattered across thousands of unrelated awards and are not labelled as data purchases.

This tool monitors every prime contract award funded from the Bureau's two appropriations, flags the ones that look like data acquisitions, and records changes over time.

| TAS | Account |
|-----|---------|
| `013-0450` | Periodic Censuses and Programs, Bureau of the Census, Commerce |
| `013-0401` | Current Surveys and Programs, Bureau of the Census, Commerce |

## Installation

Requires Python 3.9+.

```bash
git clone https://github.com/jaejunel/census-contracts-monitor.git
cd census-contracts-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No API key is required. USASpending's API is public and unauthenticated.

## Usage

```bash
# Check the current fiscal year (plus the prior one during Oct-Dec,
# when late modifications are still common)
python monitor.py run

# Build the historical record
python monitor.py backfill --from 2012

# Run the tests
pytest
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success — no change, or changes recorded |
| `1` | Needs attention — scope failure, implausible result count, or churn guard tripped |

## How it works

```
fetch → verify scope → snapshot → extract → diff → changelog
```

1. **Fetch** all prime contract awards under the tracked accounts for a fiscal year.
2. **Verify scope** — abort if the API reports any filter as unused (see [Reliability](#reliability)).
3. **Snapshot** raw JSON to `snapshots/`, with an order-independent content hash.
4. **Extract** to a CSV in `extracted/`, one row per award, flagging likely data acquisitions.
5. **Diff** against the previous snapshot for that fiscal year, keyed on USASpending's stable award ID.
6. **Changelog** — prepend a Markdown entry, newest first.

### Automation

`.github/workflows/monitor.yml` runs weekly (Mondays, 09:00 UTC) and on manual dispatch. On change it commits the new snapshot, CSV and changelog, then opens a GitHub issue summarising what changed. On failure it opens an issue and fails the run. Uses the built-in `GITHUB_TOKEN`; no secrets to configure.

USASpending loads from FPDS nightly and has no fixed publication date, so weekly is simply granular enough to date an award's first appearance without generating churn noise.

## Configuration

All configuration lives in [`contracts_monitor/config.py`](contracts_monitor/config.py).

| Setting | Default | Purpose |
|---------|---------|---------|
| `TAS_CODES` | `013-0450`, `013-0401` | Treasury accounts to track |
| `AWARD_TYPE_CODES` | `A`, `B`, `C`, `D` | Prime contract types (IDVs excluded) |
| `DATA_ACQUISITION_PATTERNS` | see file | Regexes that flag a data purchase |
| `DATA_ACQUISITION_EXCLUDE` | see file | Regexes that veto a match (IT procurement) |
| `MAX_CHURN_FRACTION` | `0.25` | Added+removed share that refuses a changelog entry |
| `MIN_EXPECTED_AWARDS` | `10` | Plausibility floor for a mature fiscal year |

### Classification is a flag, not a filter

Every award under the tracked accounts is captured. The `data_acquisition` column is applied at extraction, so a revised rule can be re-applied to stored snapshots without refetching.

This matters because classification is genuinely hard:

- **Product codes don't work.** The Bridgetree voter-data purchase is PSC `R799` ("Support — Management: Other"), the same code used for ordinary consulting.
- **Keywords alone don't work.** `DATA CENTER`, `DATA LAKE` and `EXADATA LICENSES` are IT procurement; `HOTEL/MOTEL DATA` and `BUILDING AND PARCEL DATA` are genuine data purchases with no acquisition verb at all.

The current rule combines explicit acquisition language (`ACQUISITION OF … DATA`, `PURCHASE OF … DATA`, `COMMERCIAL … DATA`, `VOTER`, `ADMINISTRATIVE RECORDS`) with a bare-product-name pattern, minus an exclusion list. It is regression-tested in [`tests/test_classify.py`](tests/test_classify.py) against real descriptions from both classes.

**Expect false negatives.** Treat the flag as a high-recall shortlist for review, not ground truth.

## Output

```
snapshots/awards-FY2026-2026-10-30.json   Raw API response + content hash
extracted/awards-FY2026-2026-10-30.csv    One row per award
CHANGELOG.md                              Human-readable diffs, newest first
CHECK_LOG.md                              Every run, changed or not
```

### CSV schema

| Column | Description |
|--------|-------------|
| `unique_award_id` | USASpending's stable award ID (the diff key) |
| `award_id` | Contract PIID |
| `recipient_name` | Vendor |
| `award_amount` | Obligated amount |
| `total_outlays` | Amount actually disbursed |
| `description` | Award description as filed |
| `start_date`, `end_date` | Period of performance |
| `last_modified_date` | Last record revision (excluded from diffs) |
| `awarding_agency`, `awarding_sub_agency` | Awarding office |
| `contract_award_type` | A/B/C/D |
| `naics`, `psc` | Industry and product-service codes |
| `data_acquisition` | `yes` if flagged by the classifier |

## Findings

Backfilled FY2012–FY2026 (6,652 awards). **17 distinct data-acquisition awards**, by first appearance:

| First seen | Amount | Vendor | Description |
|------------|-------:|--------|-------------|
| FY2015 | $272K | Capital IQ | Commercial data buy |
| FY2017 | $2.5M | Palantir Technologies | Purchase of commercial sales/revenue data |
| FY2019 | $1.9M | Black Knight Data & Analytics | Commercial data files for housing |
| FY2020 | $2.8M | VSGI | Commercial data buy |
| FY2021 | $1.1M | Research Triangle Institute | Trust in administrative records study |
| FY2022 | $6.2M | Nielsen Consumer | Aggregated retail POS/scanner transaction data |
| FY2023 | $8.7M | Circana Group | Aggregated POS/scanner transaction data |
| FY2024 | $6.6M | Nielsen Consumer | Aggregated retail POS/scanner transaction data |
| FY2024 | $4.4M | Reveal Global Consulting | Criminal justice statistics data acquisition |
| FY2024 | $650K | Data-Clear | Voter's registration data |
| FY2024 | $538K | SafeGraph | Rich places and spend data |
| FY2025 | $360K | Loveland Technologies | Building and parcel data |
| FY2026 | $796K | Bridgetree | Acquisition of voter registration data |
| FY2026 | $695K | Innovative Mgmt Consulting | Acquisition of personal contact information |
| FY2026 | $465K | ICE Data Services | Acquisition of commercial housing data |
| FY2026 | $443K | SafeGraph | Places and spend commercial data |
| FY2026 | $67K | CoStar Realty | Hotel/motel data |

### Cross-linking with the inventory monitor

Several vendors appear in both datasets, and the lag between a contract and its disclosure is measurable:

- **Data-Clear** — contract FY2024; "Data Clear" voter files first appear in the published inventory in the 2025-03-21 edition.
- **SafeGraph**, **ICE Data Services**, **Black Knight**, **VSGI** — present in both.
- **ICE Data Services is Intercontinental Exchange**, which acquired Black Knight — a corporate succession visible across both records. It is *not* Immigration and Customs Enforcement, despite the inventory listing rows under "ICE".
- As of the 2026-10-22 inventory edition, **Bridgetree**, **Innovative Management Consulting** and **CoStar** had contracts with no corresponding inventory entry. Bridgetree's performance period began 2026-09-01, so this is plausibly delivery lag rather than non-disclosure.

## Reliability

### The API trap this project is built around

USASpending's `/search/spending_by_award/` endpoint **silently ignores filter keys it does not recognise** and returns the unfiltered universe, reporting it only in a `messages` array in the response body.

During calibration, a plausible-looking `federal_account_symbol` filter was dropped exactly this way and the API returned **$1.4 trillion** of federal contract awards instead of the Census Bureau's. Nothing in the HTTP status, the result shape, or the record count indicated a problem.

`guards.check_filters_applied()` inspects every page of every response and aborts the run if any filter was dropped. **Do not remove that check.** It is the difference between this monitor tracking the Census Bureau and tracking the federal government.

### Guards

| Guard | Trigger | Action |
|-------|---------|--------|
| Scope failure | API reports any filter unused | Abort the run |
| Implausible count | Mature FY below the floor, or >50% drop vs. prior snapshot | Abort the run |
| Excess churn | >25% of awards added/removed | Refuse changelog; write `*.suspect.csv` |

The second guard was itself corrected after a false alarm: a fiscal year three weeks old legitimately has only a handful of awards, so the absolute floor now applies only once a year is 90+ days old, with a drop-based rule when a prior snapshot exists.

## Limitations

- **Contract records are revised retroactively.** Amounts, descriptions and periods change after award, so `modified` is a normal outcome and history genuinely mutates underneath you.
- **Per-fiscal-year totals are not annual spending.** A multi-year award appears in every fiscal year in which it had an action — the Palantir award recurs across FY2017–FY2025. Deduplicate on `unique_award_id`.
- **This measures obligations, not deliveries.** A contract is a promise to buy; it does not establish that data changed hands, or when.
- **Prime awards only.** Subawards and IDV vehicles are out of scope.
- **Absence of a contract is not absence of acquisition.** Data reaches the Bureau through interagency agreements, MOUs and no-cost arrangements that never appear in procurement data. Most of the inventory's providers — states, universities, other federal agencies — are of exactly that kind.
- **FY2008–2011 are excluded.** USASpending's TAS linkage is too sparse that far back to distinguish from an outage.
- **The backfill is today's view of history,** not artifacts captured at the time. "FY2015" means "FY2015 as USASpending described it on 2026-10-30".

## Development

```bash
pytest                 # 42 tests
pytest -q --tb=short   # quieter
```

Tests cover the scope guard (including the exact ignored-filter message observed in production), the classifier against real descriptions from both classes, diff behaviour including retroactive modification and reordering, and the young-fiscal-year regression.

Dependencies are pinned in `requirements.txt`.

## Citation

This repository contains two citable artifacts: the **software** and the **dataset** (snapshots, extractions and changelog). If you use the data, cite the dataset; if you describe the method, cite the software.

## License

Not yet specified. Open an issue if you need a particular licence for reuse.
