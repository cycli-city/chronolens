from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class IngestRequest(BaseModel):
    """Schema for document ingestion request."""
    document_id: str = Field(..., min_length=1, max_length=100)
    version: int = Field(..., ge=1, le=1000)
    timestamp: str = Field(..., description="YYYY-MM-DD format")
    doc_name: str = Field(..., min_length=1, max_length=200)
    doc_type: str = Field(default="general", max_length=50)

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        # Only alphanumeric, underscores, dashes
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("document_id can only contain letters, numbers, _ and -")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("timestamp must be in YYYY-MM-DD format")
        return v

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        allowed = {"general", "contract", "policy", "regulation", "report", "memo"}
        if v not in allowed:
            raise ValueError(f"doc_type must be one of: {allowed}")
        return v


class IngestResponse(BaseModel):
    status: str
    document_id: str
    version: int
    chunks_created: int
    total_text_length: int


class VersionInfo(BaseModel):
    version: int
    timestamp: str
    doc_name: str


class DocumentVersionsResponse(BaseModel):
    document_id: str
    versions: list[VersionInfo]
    total_versions: int