"""Compose customer-facing documents from grouped source facts."""

from importlib.resources import files

from jinja2 import Environment, StrictUndefined
from pydantic import ValidationError

from brand_docs.domain.enums import DocumentType, ParagraphOrigin, UnitKind
from brand_docs.domain.models import (
    BrandData,
    ComposedSection,
    Document,
    Fact,
    Grouping,
    GroupingEntry,
    Paragraph,
    Section,
    SourceReference,
)
from brand_docs.errors import LlmOutputError, LlmUnavailableError
from brand_docs.llm.client import LlmClient
from brand_docs.utils.logger import setup_logger
from brand_docs.utils.text import format_fact_sentence, humanize_key

logger = setup_logger(__name__)
DOCUMENT_TITLES = {
    DocumentType.POLICY: "Kebijakan",
    DocumentType.GUIDE: "Panduan",
    DocumentType.PRODUCT_KNOWLEDGE: "Product Knowledge",
}
DOCUMENT_PURPOSES = {
    DocumentType.POLICY: "brand policies and customer terms",
    DocumentType.GUIDE: "customer instructions supported by the provided facts",
    DocumentType.PRODUCT_KNOWLEDGE: "product information for customers",
}


class DocumentComposer:
    """Build document structure from templates with optional LLM prose."""

    def __init__(self, llm: LlmClient, use_llm: bool, max_retries: int) -> None:
        self.llm = llm
        self.use_llm = use_llm
        self.max_retries = max_retries
        self.prompt_environment = Environment(undefined=StrictUndefined, autoescape=False)
        self.prompt_template = self.prompt_environment.from_string(
            files("brand_docs.llm.prompts").joinpath("section.j2").read_text(encoding="utf-8")
        )

    def _build_prompt(
        self, brand: BrandData, doc_type: DocumentType, heading: str, facts: list[Fact]
    ) -> str:
        return self.prompt_template.render(
            brand_name=brand.brand_name,
            document_type=f"{doc_type.value}: {DOCUMENT_PURPOSES[doc_type]}",
            heading=heading,
            facts=facts,
        )

    def _fallback_section(
        self, heading: str, source_section: str, order: int, facts: list[Fact]
    ) -> Section:
        return Section(
            heading=heading,
            order=order,
            source_section=source_section,
            paragraphs=[
                Paragraph(
                    text=format_fact_sentence(fact),
                    origin=ParagraphOrigin.TEMPLATE,
                    sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                )
                for fact in facts
            ],
            facts=facts,
        )

    def _compose_section(
        self,
        brand: BrandData,
        doc_type: DocumentType,
        heading: str,
        source_section: str,
        order: int,
        facts: list[Fact],
    ) -> Section:
        if not self.use_llm:
            return self._fallback_section(heading, source_section, order, facts)
        prompt = self._build_prompt(brand, doc_type, heading, facts)
        for attempt in range(self.max_retries + 1):
            try:
                output = self.llm.generate(prompt, ComposedSection)
                if output.heading != heading or not 1 <= len(output.paragraphs) <= 3:
                    raise ValueError("Structured output has a wrong heading or paragraph count.")
                if any(not paragraph.text.strip() for paragraph in output.paragraphs):
                    raise ValueError("Structured output contains an empty paragraph.")
                return Section(
                    heading=heading,
                    order=order,
                    source_section=source_section,
                    paragraphs=[
                        Paragraph(
                            text=paragraph.text,
                            origin=ParagraphOrigin.LLM,
                            sources=[
                                SourceReference(
                                    fact_path=path,
                                    line=next(
                                        (fact.line for fact in facts if fact.path == path),
                                        0,
                                    ),
                                )
                                for path in paragraph.source_paths
                            ],
                        )
                        for paragraph in output.paragraphs
                    ],
                    facts=facts,
                )
            except (LlmOutputError, LlmUnavailableError, ValidationError, ValueError):
                # Retry once per setting, then use factual fallback prose.
                logger.warning(
                    "Section generation failed on attempt %d", attempt + 1, exc_info=True
                )
                if attempt == self.max_retries:
                    return self._fallback_section(heading, source_section, order, facts)
        return self._fallback_section(heading, source_section, order, facts)

    @staticmethod
    def _facts_for_unit(brand: BrandData, unit: str) -> list[Fact]:
        return [
            fact
            for fact in brand.facts
            if fact.path == unit or fact.path.startswith(f"{unit}.")
        ]

    @staticmethod
    def _most_specific_size_unit(
        size_units: list[GroupingEntry], fact_path: str
    ) -> GroupingEntry | None:
        return max(
            (
                entry
                for entry in size_units
                if fact_path == entry.section or fact_path.startswith(f"{entry.section}.")
            ),
            key=lambda entry: len(entry.section),
            default=None,
        )

    @staticmethod
    def _facts_for_size_unit(
        brand: BrandData,
        grouping: Grouping,
        unit: str,
        doc_type: DocumentType,
    ) -> list[Fact]:
        nested_units = [
            entry.section
            for entry in grouping.entries
            if entry.unit_kind == UnitKind.PRODUCT_SIZE
            and entry.section.startswith(f"{unit}.")
            and doc_type in entry.document_types
        ]
        return [
            fact
            for fact in DocumentComposer._facts_for_unit(brand, unit)
            if not any(
                fact.path == nested_unit or fact.path.startswith(f"{nested_unit}.")
                for nested_unit in nested_units
            )
        ]

    @staticmethod
    def _product_facts(
        brand: BrandData,
        grouping: Grouping,
        product_root: str,
        doc_type: DocumentType,
        include_product: bool,
    ) -> list[Fact]:
        size_units = [
            entry
            for entry in grouping.entries
            if entry.unit_kind == UnitKind.PRODUCT_SIZE
            and entry.section.startswith(f"{product_root}.")
        ]
        facts: list[Fact] = []
        for fact in brand.facts:
            if fact.path != product_root and not fact.path.startswith(f"{product_root}."):
                continue
            if fact.path == product_root and include_product:
                facts.append(fact)
            if fact.path == product_root:
                continue
            size_entry = DocumentComposer._most_specific_size_unit(size_units, fact.path)
            if size_entry is None and include_product:
                facts.append(fact)
            elif (
                size_entry is not None
                and doc_type == DocumentType.PRODUCT_KNOWLEDGE
                and doc_type in size_entry.document_types
            ):
                facts.append(fact)
        return facts

    @staticmethod
    def _heading(unit: str, kind: UnitKind) -> str:
        pieces = unit.split(".")
        if kind == UnitKind.PRODUCT_SIZE:
            product_name = pieces[1]
            return f"{humanize_key(pieces[-1])} \u00b7 {product_name}"
        if kind == UnitKind.PRODUCT:
            return pieces[-1]
        return humanize_key(pieces[-1])

    def _compose_document(
        self, brand: BrandData, grouping: Grouping, doc_type: DocumentType
    ) -> Document | None:
        sections: list[Section] = []
        handled_products: set[str] = set()
        for entry in grouping.entries:
            if doc_type not in entry.document_types:
                continue
            if entry.unit_kind == UnitKind.PRODUCT:
                product_root = entry.section
                facts = self._product_facts(
                    brand,
                    grouping,
                    product_root,
                    doc_type,
                    include_product=True,
                )
                handled_products.add(product_root)
                heading = entry.section.split(".")[-1]
            elif entry.unit_kind == UnitKind.PRODUCT_SIZE:
                product_root = ".".join(entry.section.split(".")[:2])
                if doc_type == DocumentType.PRODUCT_KNOWLEDGE and product_root in handled_products:
                    continue
                if doc_type == DocumentType.PRODUCT_KNOWLEDGE:
                    facts = self._product_facts(
                        brand, grouping, product_root, doc_type, include_product=False
                    )
                    handled_products.add(product_root)
                    heading = entry.section.split(".")[1]
                else:
                    facts = self._facts_for_size_unit(brand, grouping, entry.section, doc_type)
                    heading = self._heading(entry.section, entry.unit_kind)
            else:
                facts = self._facts_for_unit(brand, entry.section)
                heading = self._heading(entry.section, entry.unit_kind)
            if not facts:
                continue
            sections.append(
                self._compose_section(
                    brand, doc_type, heading, entry.section, len(sections) + 1, facts
                )
            )
        if not sections:
            return None
        return Document(
            document_type=doc_type,
            title=f"{DOCUMENT_TITLES[doc_type]} {brand.brand_name}",
            brand_name=brand.brand_name,
            sections=sections,
        )

    def compose(self, brand: BrandData, grouping: Grouping) -> list[Document]:
        documents: list[Document] = []
        for doc_type in DocumentType:
            document = self._compose_document(brand, grouping, doc_type)
            if document is not None:
                documents.append(document)
        return documents
