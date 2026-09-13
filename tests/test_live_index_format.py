from datetime import date

from edgar_monitor.index_parser import parse_master_index
from edgar_monitor.validation import validate_raw_rows


def test_current_sec_header_and_compact_date_are_accepted() -> None:
    payload = """Description:           Daily Index of EDGAR Dissemination Feed
Last Data Received:    Sep 10, 2026

CIK|Company Name|Form Type|Date Filed|File Name
--------------------------------------------------------------------------------
1000275|ROYAL BANK OF CANADA|10-Q|20260910|edgar/data/1000275/0000950103-26-013746.txt
"""

    document = parse_master_index(payload)
    valid_records, quarantined_records = validate_raw_rows(document.rows)

    assert document.header[-1] == "File Name"
    assert len(document.rows) == 1
    assert len(valid_records) == 1
    assert quarantined_records == ()
    assert valid_records[0].filing_date == date(2026, 9, 10)
    assert valid_records[0].accession_number == "0000950103-26-013746"