"""Typed models for validated SEC filing-index records."""

from __future__ import annotations

from datetime import date
import re

from pydantic import BaseModel, Field, field_validator, model_validator

ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")


class FilingRecord(BaseModel):
    """A validated filing record derived from one SEC master-index row."""

    cik: str
    company_name: str
    form_type: str
    filing_date: date
    filename: str
    accession_number: str
    source_line_number: int = Field(gt=0)

    @field_validator("cik")
    @classmethod
    def normalize_cik(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or len(value) > 10:
            raise ValueError("CIK must contain 1 to 10 digits.")
        return value.zfill(10)

    @field_validator("company_name", "form_type")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank.")
        return value

    @field_validator("filename")
    @classmethod
    def require_edgar_archive_path(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("edgar/data/"):
            raise ValueError("Filename must be an EDGAR archive path.")
        return value

    @field_validator("accession_number")
    @classmethod
    def validate_accession_number(cls, value: str) -> str:
        if not ACCESSION_PATTERN.fullmatch(value):
            raise ValueError("Accession number has an invalid format.")
        return value

    @model_validator(mode="after")
    def accession_must_match_filename(self) -> "FilingRecord":
        if self.accession_number not in self.filename:
            raise ValueError("Accession number is not present in the filename.")
        return self


class QuarantineRecord(BaseModel):
    """A rejected source row with an intentional, inspectable reason."""

    source_line_number: int = Field(gt=0)
    raw_line: str
    reason: str
    detail: str