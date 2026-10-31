# census-contracts-monitor

Tracks **prime contract awards funded from the two Bureau of the Census
appropriations** on USASpending.gov, and flags those that look like purchases
of commercial data.

| TAS | account |
|---|---|
| `013-0450` | Periodic Censuses and Programs, Bureau of the Census, Commerce |
| `013-0401` | Current Surveys and Programs, Bureau of the Census, Commerce |

Companion to [census-inventory-monitor](https://github.com/jaejunel/census-inventory-monitor),
which tracks the Bureau's published inventory of administrative data files.
The two answer different questions:

- **inventory monitor** — what the Bureau *says it holds*
- **contracts monitor** — what the Bureau *paid for*

The gap between them is the point. See [Cross-linking](#cross-linking) below.

## What it does

1. **Fetch** every prime contract award under those accounts for a fiscal
   year, from the USASpending API.
2. **Verify scope** — abort if the API reports any filter as unused (see
   [The trap](#the-trap-this-project-is-built-around)).
3. **Snapshot** the raw JSON to `snapshots/awards-FY____-YYYY-MM-DD.json`,
   with an order-independent content hash.
4. **Extract** to `extracted/awards-FY____-YYYY-MM-DD.csv`, one row per
   award, flagging likely data acquisitions.
5. **Diff** against the previous snapshot for that fiscal year, keyed on
   USASpending's stable award id.
6. **Changelog** — prepend a Markdown entry, newest first.

## The trap this project is built around

USASpending's `/search/spending_by_award/` endpoint **silently ignores filter
keys it does not recognise** and returns the unfiltered universe, admitting it
only in a `messages` array in the response body.

During calibration, a plausible-looking `federal_account_symbol` filter was
dropped exactly this way and the API cheerfully returned **$1.4 trillion** of
federal contract awards instead of the Census Bureau's. Nothing in the HTTP
status, the result shape, or the record count would tell you.

The working filter is `tas_codes`. `guards.check_filters_applied()` inspects
every page of every response and aborts the run if any filter was dropped.
**Do not remove that check.** It is the difference between this monitor
tracking the Census Bureau and tracking the federal government.

## Data-acquisition classification is a FLAG, not a filter

Every award under the tracked accounts is captured. The `data_acquisition`
column is applied at extract time and can be revised later from the stored
snapshots without re-fetching.

This matters because the classification is genuinely hard:

- **PSC codes don't work.** The Bridgetree voter-data purchase is PSC `R799`
  ("Support — Management: Other"), the same code used for ordinary consulting.
- **Keyword matching alone doesn't work.** "DATA CENTER", "DATA LAKE",
  "EXADATA LICENSES" and "DATA PROCESSING SUPPORT SERVICES" are all IT
  procurement; "HOTEL/MOTEL DATA" and "BUILDING AND PARCEL DATA" are genuine
  data purchases with no acquisition verb at all.

The current rule is: explicit acquisition language (`ACQUISITION OF … DATA`,
`PURCHASE OF … DATA`, `COMMERCIAL … DATA`, `VOTER`, `ADMINISTRATIVE RECORDS`)
**or** a short description that simply names a data product, minus an
exclusion list of IT/services phrases. Calibrated against FY2026 and
regression-tested in `tests/test_classify.py` against real descriptions from
both classes.

**It will have false negatives.** Treat the flag as a high-recall shortlist
for human review, not ground truth.

## What the historical record shows

Backfilled FY2012–FY2026 (6,652 awards). **17 distinct data-acquisition
awards**, first appearing:

| first seen | amount | vendor | description |
|---|---:|---|---|
| FY2015 | $272K | Capital IQ | Commercial data buy |
| FY2017 | $2.5M | Palantir Technologies | Purchase of commercial sales/revenue data |
| FY2019 | $1.9M | Black Knight Data & Analytics | Commercial data files for housing |
| FY2020 | $2.8M | VSGI | Commercial data buy |
| FY2021 | $1.1M | Research Triangle Institute | Trust in administrative records study |
| FY2022 | $6.2M | Nielsen Consumer | Aggregated retail POS/scanner transaction data |
| FY2023 | $8.7M | Circana Group | Aggregated POS/scanner transaction data |
| FY2024 | $6.6M | Nielsen Consumer | Aggregated retail POS/scanner transaction data |
| FY2024 | $4.4M | Reveal Global Consulting | Criminal justice statistics data acquisition |
| FY2024 | $650K | **Data-Clear** | **Voter's registration data** |
| FY2024 | $538K | SafeGraph | Rich places and spend data |
| FY2025 | $360K | Loveland Technologies | Building and parcel data |
| FY2026 | $796K | **Bridgetree** | **Acquisition of voter registration data** |
| FY2026 | $695K | Innovative Mgmt Consulting | Acquisition of personal contact information |
| FY2026 | $465K | ICE Data Services | Acquisition of commercial housing data |
| FY2026 | $443K | SafeGraph | Places and spend commercial data |
| FY2026 | $67K | CoStar Realty | Hotel/motel data |

**Do not read the per-fiscal-year totals as annual spending.** A multi-year
award appears in every fiscal year in which it had an action — the Palantir
award recurs across FY2017–FY2025. Use `unique_award_id` to deduplicate; the
table above is first-appearance only.

## Cross-linking

Several vendors appear in **both** datasets, and the lag between them is
measurable:

- **Data-Clear** — contract FY2024; "Data Clear" voter files first appear in
  the published inventory in the 2025-03-21 edition.
- **SafeGraph**, **ICE Data Services**, **Black Knight**, **VSGI** — all
  present in both. (ICE Data Services is Intercontinental Exchange, which
  acquired Black Knight — a corporate succession visible across both records.
  It is *not* Immigration and Customs Enforcement, despite the inventory
  listing rows under "ICE".)
- As of the 2026-10-22 inventory edition, **Bridgetree**, **Innovative
  Management Consulting** and **CoStar** had contracts but no corresponding
  inventory entry. For Bridgetree the period of performance began 2026-09-01,
  so this is plausibly delivery lag rather than non-disclosure — which is
  exactly the thing worth watching over time rather than asserting now.

## Usage

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python monitor.py run                  # current FY (plus prior FY in Oct-Dec)
python monitor.py backfill --from 2012 # build the historical record
pytest
```

`run` exits non-zero on a scope failure, an implausible result count, or a
churn-guard trip.

## Automation

`.github/workflows/monitor.yml` runs weekly (Mondays, 09:00 UTC) and on
manual dispatch. USASpending loads from FPDS nightly and has no publication
date to aim at, so there is no clever schedule to derive — weekly is granular
enough to date an award's first appearance without churn noise.

On change it commits the snapshot, CSV and changelog, and opens an issue. On
failure it opens an issue and fails the run. Uses the built-in `GITHUB_TOKEN`.

GitHub's scheduled workflows are best-effort and are disabled after 60 days of
repository inactivity. If a month passes with no bot commit, check the Actions
tab.

## Guards

1. **Scope failure** — any filter reported unused aborts the run.
2. **Implausible result count** — fewer than 10 awards for a full fiscal year
   aborts rather than recording a mass disappearance. This is why FY2008–2011
   are excluded: USASpending's TAS linkage is too sparse that far back.
3. **Excess churn** — more than 25% of awards added/removed refuses the
   changelog entry and writes `extracted/*.suspect.csv` for inspection.

## Caveats

- **Contract records are revised retroactively.** Amounts, descriptions and
  periods change after award. `modified` is a normal outcome here, not an
  anomaly, and history genuinely mutates underneath you — which is itself an
  argument for snapshotting.
- **This measures obligations, not deliveries.** A contract is a promise to
  buy; it does not establish that data changed hands, or when.
- **Prime awards only.** Subawards and IDV vehicles are out of scope.
- **Absence of a contract is not absence of acquisition.** Data can reach the
  Bureau through interagency agreements, MOUs, or no-cost arrangements that
  never appear in procurement data at all. Most of the inventory's providers —
  states, universities, other federal agencies — are of exactly that kind.
