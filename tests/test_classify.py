"""Classifier tests, using real descriptions observed in the live data."""
from __future__ import annotations
import pytest
from contracts_monitor.classify import is_data_acquisition

REAL_DATA_BUYS = [
    "ACQUISITION OF VOTER REGISTRATION DATA.",
    "ACQUISITION OF PERSONAL CONTACT INFORMATION (DATA).",
    "ACQUISITION OF COMMERCIAL HOUSING DATA.",
    "PLACES AND SPEND COMMERCIAL DATA.",
    "HOTEL/MOTEL DATA",
    "BUILDING AND PARCEL DATA",
    "AGGREGATED POINT OF SALE / SCANNER TRANSACTION DATA",
    "AGGREGATED RETAIL POINT-OF-SALE/SCANNER TRANSACTION DATA.",
    "PURCHASE OF COMMERCIAL SALES/REVENUE DATA. IGF::OT::IGF",
    "COMMERCIAL DATA BUY",
    "AWARD OF COMMERCIAL DATA FILES FOR HOUSING.",
    "VOTER'S REGISTRATION DATA",
]

REAL_NOT_DATA_BUYS = [
    "IT INFRASTRUCTURE SUPPORT SERVICES-DATA CENTER  IGF::OT::IGF",
    "RENEWAL ATLASSIAN JIRA DATA CENTER SOFTWARE LICENSE",
    "ETESTING SUPPORT SERVICES ORDER 0017 ENTERPRISE DATA LAKE",
    "ORACLE EXADATA LICENSES",
    "DATA HOSTING",
    "BROADBAND DATA SERVICES",
    "PROVIDE DATA PROCESSING SUPPORT SERVICES",
    "DATA ARCHITECTURE SUPPORT SERVICES",
    "CONTRACT AWARD FOR DATA INTEGRITY SUPPORT SERVICES",
    "INTERNET DATA COLLECTION",
    "QUESTIONNAIRE DESIGN & METADATA (QDM) ENHANCEMENTS AND MAINTENANCE SERVICES",
    "GIS ESRI SUPPORT",
    "",
]


@pytest.mark.parametrize("d", REAL_DATA_BUYS)
def test_real_data_purchases_flagged(d):
    assert is_data_acquisition(d) is True


@pytest.mark.parametrize("d", REAL_NOT_DATA_BUYS)
def test_real_non_purchases_not_flagged(d):
    assert is_data_acquisition(d) is False


def test_exclusion_beats_inclusion():
    """'DATA CENTER' contains neither an acquisition verb nor a bare product
    name, but belt-and-braces: an exclusion must win even if both match."""
    assert is_data_acquisition("ACQUISITION OF DATA CENTER SOFTWARE") is False


def test_long_statement_of_work_not_flagged_by_bare_name_rule():
    """The bare-product-name rule is length-capped so it cannot swallow a
    long statement of work that happens to end in the word DATA."""
    long = ("THIS CONTRACT PROVIDES FOR THE DESIGN, DEVELOPMENT, AND DEPLOYMENT "
            "OF A COMPREHENSIVE ENTERPRISE SYSTEM INCLUDING INGEST OF DATA")
    assert is_data_acquisition(long) is False
