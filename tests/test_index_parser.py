from pathlib import Path

import pytest

from edgar_monitor.index_parser import MasterIndexFormatError, parse_master_index

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_master.idx"
EXPECTED_SCHEMA_FINGERPRINT = (
    "48b837c31e02d663d2c9ce3dae00bf3a1d4a765958b41a77c4f98c196719fd19"
)


def test_parse_master_index_preserves_raw_rows() -> None:
    document = parse_master_index(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert document.header == (
        "CIK",
        "Company Name",
        "Form Type",
        "Date Filed",
        "Filename",
    )
    assert document.schema_fingerprint == EXPECTED_SCHEMA_FINGERPRINT
    assert len(document.rows) == 4
    assert document.rows[0].values[0] == "0000320193"
    assert document.rows[0].values[2] == "10-K"


def test_parse_master_index_rejects_missing_header() -> None:
    with pytest.raises(MasterIndexFormatError, match="header"):
        parse_master_index("CIK,Company Name,Form Type\n1,Example,10-K\n")