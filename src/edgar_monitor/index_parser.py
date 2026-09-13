"""Parse SEC EDGAR daily master-index files."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

CURRENT_MASTER_INDEX_HEADER = (
    "CIK",
    "Company Name",
    "Form Type",
    "Date Filed",
    "File Name",
)

LEGACY_MASTER_INDEX_HEADER = (
    "CIK",
    "Company Name",
    "Form Type",
    "Date Filed",
    "Filename",
)

SUPPORTED_MASTER_INDEX_HEADERS = frozenset(
    {
        CURRENT_MASTER_INDEX_HEADER,
        LEGACY_MASTER_INDEX_HEADER,
    }
)


class MasterIndexFormatError(ValueError):
    """Raised when an SEC master-index file has an unsupported structure."""


@dataclass(frozen=True)
class RawIndexRow:
    """A non-empty filing row preserved exactly as received from SEC."""

    line_number: int
    raw_line: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class MasterIndexDocument:
    """Parsed SEC master-index metadata and raw filing rows."""

    header: tuple[str, ...]
    schema_fingerprint: str
    rows: tuple[RawIndexRow, ...]


def fingerprint_header(header: tuple[str, ...]) -> str:
    """Create a stable fingerprint for the source schema."""
    joined_header = "|".join(header)
    return sha256(joined_header.encode("utf-8")).hexdigest()


def is_separator_line(line: str) -> bool:
    """Return whether a line is the dashed separator below the SEC header."""
    stripped_line = line.strip()
    return bool(stripped_line) and set(stripped_line) == {"-"}


def parse_master_index(payload: str) -> MasterIndexDocument:
    """Parse a raw SEC daily master-index response.

    The parser preserves raw filing rows for later validation. It accepts both
    the current SEC ``File Name`` header and the earlier fixture-compatible
    ``Filename`` variant, but rejects all other schema changes.
    """
    header: tuple[str, ...] | None = None
    header_line_number: int | None = None
    lines = payload.splitlines()

    for line_number, line in enumerate(lines, start=1):
        values = tuple(part.strip() for part in line.split("|"))

        if values in SUPPORTED_MASTER_INDEX_HEADERS:
            header = values
            header_line_number = line_number
            break

    if header is None or header_line_number is None:
        raise MasterIndexFormatError(
            "Expected SEC master-index header was not found."
        )

    rows: list[RawIndexRow] = []

    for line_number, line in enumerate(
        lines[header_line_number:],
        start=header_line_number + 1,
    ):
        if not line.strip() or is_separator_line(line):
            continue

        values = tuple(part.strip() for part in line.split("|"))
        rows.append(
            RawIndexRow(
                line_number=line_number,
                raw_line=line,
                values=values,
            )
        )

    return MasterIndexDocument(
        header=header,
        schema_fingerprint=fingerprint_header(header),
        rows=tuple(rows),
    )