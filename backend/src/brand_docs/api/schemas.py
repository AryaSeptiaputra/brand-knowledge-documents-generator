"""Request and response DTOs exposed through the API."""

from pydantic import BaseModel, Field

from brand_docs.domain.enums import DocumentType
from brand_docs.domain.models import (
    CheckResult,
    CompletenessSuggestion,
    Document,
    Grouping,
)


class AnalyzeRequest(BaseModel):
    yaml: str


class AnalyzeResponse(BaseModel):
    session_id: str
    brand_name: str
    grouping: Grouping
    suggestions: list[CompletenessSuggestion]


class GroupingChange(BaseModel):
    session_id: str
    section: str
    document_types: list[DocumentType]


class GenerateRequest(BaseModel):
    session_id: str


class GenerateResponse(BaseModel):
    documents: list[Document]
    check_results: list[CheckResult]
    model_used: bool = Field(
        description="False when documents come from templates only; coverage is not measured."
    )


class LogoInfo(BaseModel):
    file_name: str
    media_type: str


class ErrorDetail(BaseModel):
    message: str
    line: int | None = None
    column: int | None = None


class ErrorResponse(BaseModel):
    errors: list[ErrorDetail] = Field(default_factory=list)


class LogoUpload(BaseModel):
    file_name: str | None
    content: bytes
