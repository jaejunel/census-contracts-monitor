"""Configuration for the Census contracts monitor.

Calibrated against the live USASpending API on 2026-10-30.

WHAT THIS TRACKS
----------------
Prime contract awards funded from the two Bureau of the Census appropriations:

  013-0450  Periodic Censuses and Programs, Bureau of the Census, Commerce
  013-0401  Current Surveys and Programs, Bureau of the Census, Commerce

These are Treasury Account Symbols (TAS). The first funds the decennial
census and periodic programs -- it is where the Bureau's commercial data
purchases have appeared (voter registration data, housing data, places/spend
data). The second funds ongoing surveys (ACS, CPS and friends).

THE API TRAP THIS CONFIG EXISTS TO AVOID
----------------------------------------
USASpending's /search/spending_by_award/ endpoint **silently ignores filter
keys it does not recognise** and returns the unfiltered universe -- all
federal contract awards -- admitting it only in a `messages` array in the
response body. During calibration a plausible-looking `federal_account_symbol`
filter was dropped exactly this way, returning $1.4 trillion of awards
instead of the Census Bureau's. A monitor that did not check for this would
appear to work and would be silently wrong.

`tas_codes` is the filter name that actually applies. guards.py enforces the
check on every fetch; never remove it.
"""

from __future__ import annotations

API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
AWARD_URL = "https://api.usaspending.gov/api/v2/awards/{award_id}/"

# The accounts we track. aid = agency identifier, main = main account code.
TAS_CODES = [
    {"aid": "013", "main": "0450"},  # Periodic Censuses and Programs
    {"aid": "013", "main": "0401"},  # Current Surveys and Programs
]

TAS_LABELS = {
    "013-0450": "Periodic Censuses and Programs, Bureau of the Census, Commerce",
    "013-0401": "Current Surveys and Programs, Bureau of the Census, Commerce",
}

# Prime contract award types (A/B/C/D). IDVs are a different family and are
# excluded for now -- they are vehicles, not purchases.
AWARD_TYPE_CODES = ["A", "B", "C", "D"]

# Fields requested from the API. The API's field names are title-cased
# strings; our CSV column names are the snake_case values.
API_FIELDS = {
    "Award ID": "award_id",
    "Recipient Name": "recipient_name",
    "Award Amount": "award_amount",
    "Total Outlays": "total_outlays",
    "Description": "description",
    "Start Date": "start_date",
    "End Date": "end_date",
    "Last Modified Date": "last_modified_date",
    "Awarding Agency": "awarding_agency",
    "Awarding Sub Agency": "awarding_sub_agency",
    "Contract Award Type": "contract_award_type",
    "NAICS": "naics",
    "PSC": "psc",
}

COLUMN_NAMES = [
    "unique_award_id",  # generated_internal_id -- the stable key
    "award_id",
    "recipient_name",
    "award_amount",
    "total_outlays",
    "description",
    "start_date",
    "end_date",
    "last_modified_date",
    "awarding_agency",
    "awarding_sub_agency",
    "contract_award_type",
    "naics",
    "psc",
    "data_acquisition",  # our classification, not the API's
]

# A contract record's identity. generated_internal_id is USASpending's own
# stable identifier for an award and survives modifications, so unlike the
# PDF inventory we get a real key rather than a constructed one.
KEY_FIELDS = ["unique_award_id"]

# Fields whose change is worth reporting. Deliberately excludes
# last_modified_date: it ticks on every administrative touch and would
# drown the changelog.
COMPARE_FIELDS = [
    "recipient_name",
    "award_amount",
    "total_outlays",
    "description",
    "start_date",
    "end_date",
    "contract_award_type",
    "naics",
    "psc",
    "data_acquisition",
]

SNAPSHOTS_DIR = "snapshots"
EXTRACTED_DIR = "extracted"
CHANGELOG_PATH = "CHANGELOG.md"
CHECK_LOG_PATH = "CHECK_LOG.md"

# --- Data-acquisition classification -----------------------------------
#
# The Bureau buys commercial data under generic service PSCs (the Bridgetree
# voter-data award is PSC R799 "Support - Management: Other"), so PSC alone
# cannot identify these. Description text is the strongest signal; NAICS 51
# (Information) is corroborating.
#
# This is a FLAG, not a filter. Every award under the tracked accounts is
# captured; classification happens at analysis time so a bad rule can be
# revised without losing data. See README.
DATA_ACQUISITION_PATTERNS = [
    # Explicit acquisition language
    r"\bACQUISITION OF\b.{0,40}\bDATA\b",
    r"\bPURCHASE OF\b.{0,40}\bDATA\b",
    r"\bDATA\b.{0,20}\bACQUISITION\b",
    r"\bCOMMERCIAL\b.{0,25}\bDATA\b",
    r"\bTHIRD[- ]PARTY DATA\b",
    r"\bADMINISTRATIVE RECORDS?\b",
    r"\bVOTER\b",
    # A description that simply NAMES a data product, e.g.
    # "HOTEL/MOTEL DATA", "BUILDING AND PARCEL DATA",
    # "AGGREGATED RETAIL POINT-OF-SALE/SCANNER TRANSACTION DATA."
    # Anchored and length-capped so it cannot swallow service contracts
    # that merely mention data somewhere in a long statement of work.
    r"^[A-Z0-9 ,./&'\-]{0,60}\bDATA\b\.?$",
]

# Phrases that look data-ish but describe IT procurement, services, or
# collection operations rather than the purchase of a dataset.
DATA_ACQUISITION_EXCLUDE = [
    r"\bDATA CENTER\b",
    r"\bDATA WAREHOUSE\b",
    r"\bDATA LAKE\b",
    r"\bEXADATA\b",
    r"\bEDATABASE\b",
    r"\bSOFTWARE\b",
    r"\bLICENSE[SD]?\b",
    r"\bSUBSCRIPTION\b",
    r"\bFILE TRANSFER\b",
    r"\bHOSTING\b",
    r"\bDATA SERVICES\b",
    r"\bDATA COLLECTION\b",
    r"\bDATA PROCESSING\b",
    r"\bDATA INTEGRITY\b",
    r"\bDATA ARCHITECTURE\b",
    r"\bDATA SCIENCE\b",
    r"\bMETADATA\b",
    r"\bSUPPORT SERVICES\b",
    r"\bMAINTENANCE\b",
    r"\bINFRASTRUCTURE\b",
]

NAICS_INFORMATION_PREFIX = "51"  # corroborating signal only

# --- Guards -------------------------------------------------------------
# If the API reports ANY filter as unused, abort -- see module docstring.
# If a fetch returns zero awards for a fiscal year that previously had
# awards, abort rather than record a mass disappearance.
# If added+removed exceeds this fraction of the larger snapshot, refuse to
# write a changelog entry.
MAX_CHURN_FRACTION = 0.25
# A percentage is meaningless on a tiny base: one new award is 11-20% churn on
# 5-9 rows. Below this many rows the churn guard looks only at removals, and
# needs several of them (see guards.check_churn).
MIN_ROWS_FOR_CHURN_PCT = 50
MIN_REMOVALS_SMALL = 3
# A fiscal year younger than this is still filling up, so additions are
# expected and only removals are suspicious.
YOUNG_FY_DAYS = 90
MIN_EXPECTED_AWARDS = 10  # a full-year fetch below this is implausible
