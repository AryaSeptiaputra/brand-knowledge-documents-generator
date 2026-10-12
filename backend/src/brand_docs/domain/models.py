"""Pydantic domain models shared by services and API DTOs."""

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml.comments import CommentedMap

from brand_docs.domain.enums import DataKind, DocumentType, ParagraphOrigin, UnitKind


class YamlError(BaseModel):
    message: str
    line: int
    column: int


class ValidationResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    is_valid: bool
    errors: list[YamlError] = Field(default_factory=list)
    data: CommentedMap | None = None


class Fact(BaseModel):
    path: str
    value: (
        str
        | int
        | float
        | bool
        | datetime
        | date
        | None
        | list[str | int | float | bool | datetime | date | None]
    )
    data_kind: DataKind
    product: str | None = None
    line: int

    def section(self) -> str:
        return ".".join(self.path.split(".")[:-1])


class Product(BaseModel):
    name: str
    fact_paths: list[str] = Field(default_factory=list)


class BrandData(BaseModel):
    brand_name: str
    raw_yaml: str
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    facts: list[Fact] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)

    def facts_of(self, section: str) -> list[Fact]:
        return [
            fact
            for fact in self.facts
            if fact.path == section or fact.path.startswith(f"{section}.")
        ]


class GroupingEntry(BaseModel):
    section: str
    unit_kind: UnitKind
    document_types: list[DocumentType]
    changed_by_user: bool = False


class Grouping(BaseModel):
    entries: list[GroupingEntry]
    confirmed_by_user: bool = False

    def types_for(self, section: str) -> list[DocumentType]:
        entry = next((item for item in self.entries if item.section == section), None)
        return entry.document_types if entry else []

    def sections_for(self, doc_type: DocumentType) -> list[str]:
        return [item.section for item in self.entries if doc_type in item.document_types]


class CompletenessSuggestion(BaseModel):
    message: str
    related_path: str | None = None


class SourceReference(BaseModel):
    fact_path: str
    line: int


class Paragraph(BaseModel):
    text: str
    origin: ParagraphOrigin
    sources: list[SourceReference] = Field(default_factory=list)


class Section(BaseModel):
    heading: str
    order: int
    source_section: str
    paragraphs: list[Paragraph] = Field(default_factory=list)
    facts: list[Fact]


class Document(BaseModel):
    document_type: DocumentType
    title: str
    brand_name: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sections: list[Section] = Field(default_factory=list)


class CheckResult(BaseModel):
    document_type: DocumentType
    coverage_percent: float
    fabrication_found: bool
    replaced_paragraphs: list[str] = Field(default_factory=list)
    uncovered_facts: list[str] = Field(default_factory=list)


class PdfFile(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_name: str
    document_type: DocumentType
    content: bytes


class BrandLogo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_name: str
    media_type: str
    content: bytes


class ComposedParagraph(BaseModel):
    text: str
    source_paths: list[str]


class ComposedSection(BaseModel):
    heading: str
    paragraphs: list[ComposedParagraph]
