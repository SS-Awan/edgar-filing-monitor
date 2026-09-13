"""Parse SEC EDGAR daily master-index files without validating filing values."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

EXPECTED_HEADER = (
    "CIK",
    "Company Name",
    "Form Type",
    "Date Filed",
    "Filename",
)


class MasterIndexFormatError(ValueError):
    """Raised when an SEC master-index document has an unexpected structure."""


@dataclass(frozen=True)
class RawIndexRow:
    """One unvalidated source row preserved for later validation."""

    line_number: int
    raw_line: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class MasterIndexDocument:
    """Parsed source document with provenance for its schema."""

    header: tuple[str, ...]
    schema_fingerprint: str
    rows: tuple[RawIndexRow, ...]


def parse_master_index(payload: str) -> MasterIndexDocument:
    """Parse the header and raw rows from an SEC master-index payload."""
    lines = payload.splitlines()

    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip() == "|".join(EXPECTED_HEADER)
        ),
        None,
    )

    if header_index is None:
        raise MasterIndexFormatError("Expected SEC master-index header was not found.")

    header = tuple(lines[header_index].split("|"))
    if header != EXPECTED_HEADER:
        raise MasterIndexFormatError("SEC master-index header does not match the source contract.")

    rows = tuple(
        RawIndexRow(
            line_number=line_number,
            raw_line=line,
            values=tuple(line.split("|")),
        )
        for line_number, line in enumerate(lines[header_index + 1 :], start=header_index + 2)
        if line.strip()
    )

    schema_fingerprint = sha256("|".join(header).encode("utf-8")).hexdigest()

    return MasterIndexDocument(
        header=header,
        schema_fingerprint=schema_fingerprint,
        rows=rows,
    )