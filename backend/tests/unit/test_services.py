"""Unit coverage for YAML services, grouping, fallback, and content checks."""

import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from ruamel.yaml.comments import CommentedMap

from brand_docs.domain.enums import DataKind, DocumentType, ParagraphOrigin, UnitKind
from brand_docs.domain.models import (
    BrandData,
    ComposedParagraph,
    ComposedSection,
    Document,
    Fact,
    Grouping,
    GroupingEntry,
    Paragraph,
    Section,
    SourceReference,
)
from brand_docs.errors import (
    InvalidLogoError,
    LlmOutputError,
    LlmUnavailableError,
    PdfEngineUnavailableError,
    PdfRenderError,
    SessionNotFoundError,
)
from brand_docs.llm.client import FakeLlmClient
from brand_docs.llm.ollama_client import OllamaClient
from brand_docs.rendering.html import HtmlRenderer
from brand_docs.rendering.pdf import PdfRenderer
from brand_docs.services.advisor import CompletenessAdvisor
from brand_docs.services.checker import ContentChecker
from brand_docs.services.composer import DocumentComposer
from brand_docs.services.extractor import FactExtractor
from brand_docs.services.grouper import DocumentGrouper
from brand_docs.session.store import Session, SessionStore
from brand_docs.settings import Settings
from tests.conftest import build_validator


class UnusedLlm:
    def generate(self, prompt: str, schema: type) -> object:
        raise AssertionError("No-model composition must not call the LLM.")


class FailingLlm:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, schema: type) -> object:
        self.calls += 1
        raise LlmUnavailableError("The local language model is unavailable.")


class FakeOllamaRunner:
    def __init__(self, response: str | Exception) -> None:
        self.response = response

    def generate(self, **_: object) -> SimpleNamespace:
        if isinstance(self.response, Exception):
            raise self.response
        return SimpleNamespace(response=self.response)


def test_validator_reports_missing_brand_location(yaml_without_brand) -> None:
    result = build_validator(max_logo_bytes=100).validate(yaml_without_brand)

    assert result.is_valid is False
    assert result.errors[0].line == 1
    assert result.errors[0].column == 1


def test_extractor_preserves_the_brand_value_verbatim() -> None:
    raw = 'brand: " Example "\n'
    result = build_validator(max_logo_bytes=100).validate(raw)
    assert result.data is not None

    brand = FactExtractor().extract(result.data, raw)

    assert brand.brand_name == " Example "


def test_extractor_preserves_leaf_fact_line_number(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")

    assert fact.line == 3


def test_extractor_uses_each_mixed_sequence_item_line() -> None:
    raw = "brand: Example\nmixed:\n  - plain\n  - nested:\n      value: x\n  - 12\n"
    result = build_validator(max_logo_bytes=100).validate(raw)
    assert result.data is not None

    facts = FactExtractor().extract(result.data, raw).facts

    lines = {fact.path: fact.line for fact in facts}
    assert lines == {"mixed.0": 3, "mixed.1.nested.value": 5, "mixed.2": 6}


def test_extractor_handles_deep_mapping_without_recursion() -> None:
    raw = "brand: Example\nnested: value\n"
    result = build_validator(max_logo_bytes=100).validate(raw)
    assert result.data is not None

    nested: object = "leaf"
    for index in range(1200):
        nested = {f"level_{index}": nested}
    result.data["nested"] = nested

    facts = FactExtractor().extract(result.data, raw).facts

    assert len(facts) == 1
    assert facts[0].value == "leaf"
    assert facts[0].path.count("level_") == 1200


def test_validator_rejects_recursive_yaml_aliases() -> None:
    result = build_validator(max_logo_bytes=100).validate(
        "brand: Example\nitems: &items [*items]\n"
    )

    assert result.is_valid is False
    assert result.errors[0].message == "Recursive YAML aliases are not supported."


def _nested_alias_yaml(levels: int, width: int) -> str:
    lines = ["brand: Example", f"a0: &a0 [{', '.join(['x'] * width)}]"]
    for level in range(1, levels + 1):
        aliases = ", ".join([f"*a{level - 1}"] * width)
        lines.append(f"a{level}: &a{level} [{aliases}]")
    return "\n".join(lines) + "\n"


def test_validator_rejects_nested_alias_expansion() -> None:
    raw = _nested_alias_yaml(levels=5, width=10)

    result = build_validator(max_yaml_nodes=20_000).validate(raw)

    assert len(raw.encode()) < 400
    assert result.is_valid is False
    assert "expands to more than 20000 values" in result.errors[0].message
    assert result.errors[0].line > 1


def test_validator_counts_alias_expansion_within_limit() -> None:
    raw = _nested_alias_yaml(levels=1, width=3)

    assert build_validator(max_yaml_nodes=22).validate(raw).is_valid is True
    assert build_validator(max_yaml_nodes=21).validate(raw).is_valid is False


def test_validator_rejects_yaml_over_the_size_limit() -> None:
    raw = "brand: Example\nnote: " + "x" * 200 + "\n"

    result = build_validator(max_yaml_bytes=100).validate(raw)

    assert result.is_valid is False
    assert result.errors[0].message == "The YAML document exceeds the 100 byte limit."
    assert (result.errors[0].line, result.errors[0].column) == (1, 1)


def test_validator_handles_deep_parsed_mappings_without_recursion() -> None:
    validator = build_validator(max_logo_bytes=100)
    nested = CommentedMap()
    current = nested
    for _ in range(1500):
        child = CommentedMap()
        current["next"] = child
        current = child
    data = CommentedMap({"brand": "Example", "nested": nested})
    validator.yaml.load = lambda _: data

    result = validator.validate("brand: Example\n")

    assert result.is_valid is True


def test_validator_maps_parser_recursion_error_to_yaml_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator = build_validator(max_logo_bytes=100)

    def raise_recursion_error(_: str) -> None:
        raise RecursionError

    monkeypatch.setattr(validator.yaml, "load", raise_recursion_error)

    result = validator.validate("brand: Example\n")

    assert result.is_valid is False
    assert result.errors[0].message == "The YAML document is nested too deeply."


def test_grouper_splits_size_and_applies_grouping_change(brand_data) -> None:
    grouper = DocumentGrouper()
    grouping = grouper.propose(brand_data)

    size_entry = next(entry for entry in grouping.entries if entry.section.endswith(".size"))
    assert size_entry.document_types == [DocumentType.PRODUCT_KNOWLEDGE, DocumentType.GUIDE]
    changed = grouper.apply_change(grouping, "retur", [DocumentType.GUIDE])
    assert changed.confirmed_by_user is True
    assert changed.types_for("retur") == [DocumentType.GUIDE]


def test_composer_uses_only_template_blocks_without_model(brand_data) -> None:
    grouping = DocumentGrouper().propose(brand_data)
    composer = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1)
    documents = composer.compose(brand_data, grouping)

    assert {document.document_type for document in documents} == set(DocumentType)
    sections = [section for document in documents for section in document.sections]
    assert all(section.paragraphs == [] and section.facts for section in sections)
    product_document = next(
        doc for doc in documents if doc.document_type == DocumentType.PRODUCT_KNOWLEDGE
    )
    assert len(product_document.sections) == 1
    assert product_document.sections[0].heading == "kaos boxy"


def test_composer_falls_back_to_template_blocks_after_retries(brand_data) -> None:
    llm = FailingLlm()
    grouping = DocumentGrouper().propose(brand_data)

    documents = DocumentComposer(llm, use_llm=True, max_retries=1).compose(brand_data, grouping)

    sections = [section for document in documents for section in document.sections]
    assert llm.calls == 2 * len(sections)
    assert all(section.paragraphs == [] and section.facts for section in sections)


def test_no_model_html_shows_each_fact_once() -> None:
    raw = "brand: Contoh\nretur:\n  batas_hari: 7\n  syarat: [label masih terpasang]\n"
    result = build_validator().validate(raw)
    assert result.data is not None
    brand = FactExtractor().extract(result.data, raw)
    document = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(
        brand, DocumentGrouper().propose(brand)
    )[0]

    html = HtmlRenderer().render(document, show_sources=False)

    assert html.count("Batas hari") == 1
    assert html.count("label masih terpasang") == 1
    assert "Batas hari: 7." not in html


def test_composer_accepts_structured_paragraph_with_source_facts(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")
    llm = FakeLlmClient(
        ComposedSection(
            heading="Retur",
            paragraphs=[
                ComposedParagraph(
                    text="Anda dapat mengajukan retur sesuai batas hari yang ditentukan.",
                    source_paths=[fact.path],
                )
            ],
        )
    )
    composer = DocumentComposer(llm, use_llm=True, max_retries=1)

    grouping = Grouping(
        entries=[
            GroupingEntry(
                section="retur",
                unit_kind=UnitKind.GENERAL_SECTION,
                document_types=[DocumentType.GUIDE],
            )
        ]
    )
    section = composer.compose(brand_data, grouping)[0].sections[0]

    assert section.paragraphs[0].origin == ParagraphOrigin.LLM
    assert section.paragraphs[0].sources[0].fact_path == fact.path
    assert f"{fact.path} = 7" in llm.prompts[0]


def test_ollama_client_validates_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeOllamaRunner(
        '{"heading":"Retur","paragraphs":[{"text":"Ikuti ketentuan retur.",'
        '"source_paths":["retur.syarat"]}]}'
    )
    monkeypatch.setattr("brand_docs.llm.ollama_client.Client", lambda **_: runner)

    output = OllamaClient(Settings()).generate("prompt", ComposedSection)

    assert output.heading == "Retur"
    assert output.paragraphs[0].source_paths == ["retur.syarat"]


def test_ollama_client_forwards_host_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}

    def fake_client(**kwargs: object) -> FakeOllamaRunner:
        received.update(kwargs)
        return FakeOllamaRunner("{}")

    monkeypatch.setattr("brand_docs.llm.ollama_client.Client", fake_client)

    OllamaClient(Settings(ollama_host="http://ollama:11434", ollama_timeout_seconds=30))

    assert received == {"host": "http://ollama:11434", "timeout": 30}


def test_ollama_client_maps_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeOllamaRunner("not-json")
    monkeypatch.setattr("brand_docs.llm.ollama_client.Client", lambda **_: runner)

    with pytest.raises(LlmOutputError):
        OllamaClient(Settings()).generate("prompt", ComposedSection)


def test_ollama_client_maps_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeOllamaRunner(ConnectionError("unavailable"))
    monkeypatch.setattr("brand_docs.llm.ollama_client.Client", lambda **_: runner)

    with pytest.raises(LlmUnavailableError):
        OllamaClient(Settings()).generate("prompt", ComposedSection)


def test_product_and_size_rows_do_not_duplicate_facts(brand_data) -> None:
    grouper = DocumentGrouper()
    grouping = grouper.propose(brand_data)
    grouping = grouper.apply_change(grouping, "product.kaos boxy", [DocumentType.GUIDE])
    documents = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(
        brand_data, grouping
    )
    guide = next(document for document in documents if document.document_type == DocumentType.GUIDE)
    product = next(section for section in guide.sections if section.heading == "kaos boxy")
    size = next(section for section in guide.sections if section.heading == "Size \u00b7 kaos boxy")
    product_paths = {fact.path for fact in product.facts}
    size_paths = {fact.path for fact in size.facts}

    assert len(guide.sections) == 2
    assert product_paths.isdisjoint(size_paths)
    assert all(path.startswith("product.kaos boxy.size.") for path in size_paths)


def test_fact_mapped_to_multiple_types_appears_in_each_document(fact_in_two_documents) -> None:
    documents = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(
        fact_in_two_documents, DocumentGrouper().propose(fact_in_two_documents)
    )
    size_paths = {
        fact.path
        for fact in fact_in_two_documents.facts
        if fact.path.startswith("product.kaos boxy.size.")
    }
    assert size_paths

    for doc_type in (DocumentType.PRODUCT_KNOWLEDGE, DocumentType.GUIDE):
        document = next(doc for doc in documents if doc.document_type == doc_type)
        document_paths = {fact.path for section in document.sections for fact in section.facts}
        assert size_paths <= document_paths


def test_nested_product_size_heading_uses_product_name() -> None:
    fact = Fact(
        path="product.kaos boxy.measurements.size.chest_cm",
        value=50,
        data_kind=DataKind.PRODUCT,
        product="kaos boxy",
        line=4,
    )
    brand = BrandData(brand_name="Contoh", raw_yaml="", facts=[fact])
    grouping = Grouping(
        entries=[
            GroupingEntry(
                section="product.kaos boxy.measurements.size",
                unit_kind=UnitKind.PRODUCT_SIZE,
                document_types=[DocumentType.GUIDE],
            )
        ]
    )
    document = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(brand, grouping)[
        0
    ]

    assert document.sections[0].heading == "Size · kaos boxy"


def test_nested_product_size_heading_uses_last_size_component() -> None:
    fact = Fact(
        path="product.kaos boxy.size.measurements.ukuran.chest_cm",
        value=50,
        data_kind=DataKind.PRODUCT,
        product="kaos boxy",
        line=4,
    )
    brand = BrandData(brand_name="Contoh", raw_yaml="", facts=[fact])
    grouping = Grouping(
        entries=[
            GroupingEntry(
                section="product.kaos boxy.size.measurements.ukuran",
                unit_kind=UnitKind.PRODUCT_SIZE,
                document_types=[DocumentType.GUIDE],
            )
        ]
    )

    document = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(brand, grouping)[
        0
    ]

    assert document.sections[0].heading == "Ukuran · kaos boxy"


def test_nested_size_units_do_not_duplicate_facts_between_sections() -> None:
    facts = [
        Fact(
            path="product.kaos boxy.size.length_cm",
            value=68,
            data_kind=DataKind.PRODUCT,
            product="kaos boxy",
            line=4,
        ),
        Fact(
            path="product.kaos boxy.size.ukuran.chest_cm",
            value=50,
            data_kind=DataKind.PRODUCT,
            product="kaos boxy",
            line=5,
        ),
    ]
    brand = BrandData(brand_name="Contoh", raw_yaml="", facts=facts)
    grouping = DocumentGrouper().propose(brand)

    guide = next(
        document
        for document in DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(
            brand, grouping
        )
        if document.document_type == DocumentType.GUIDE
    )
    section_paths = [fact.path for section in guide.sections for fact in section.facts]

    assert section_paths.count(facts[0].path) == 1
    assert section_paths.count(facts[1].path) == 1
    assert [section.heading for section in guide.sections] == [
        "Size · kaos boxy",
        "Ukuran · kaos boxy",
    ]


def test_product_size_scalar_respects_its_document_mapping() -> None:
    fact = Fact(
        path="product.kaos boxy.size",
        value="M",
        data_kind=DataKind.PRODUCT,
        product="kaos boxy",
        line=3,
    )
    brand = BrandData(brand_name="Contoh", raw_yaml="", facts=[fact])
    grouper = DocumentGrouper()
    grouping = grouper.propose(brand)
    grouping = grouper.apply_change(grouping, "product.kaos boxy.size", [DocumentType.GUIDE])

    documents = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(brand, grouping)

    assert [document.document_type for document in documents] == [DocumentType.GUIDE]
    assert documents[0].sections[0].facts == [fact]


def test_nested_size_mapping_uses_the_most_specific_grouping_unit() -> None:
    facts = [
        Fact(
            path="product.kaos boxy.size.length_cm",
            value=68,
            data_kind=DataKind.PRODUCT,
            product="kaos boxy",
            line=4,
        ),
        Fact(
            path="product.kaos boxy.size.ukuran.chest_cm",
            value=50,
            data_kind=DataKind.PRODUCT,
            product="kaos boxy",
            line=5,
        ),
    ]
    brand = BrandData(brand_name="Contoh", raw_yaml="", facts=facts)
    grouper = DocumentGrouper()
    grouping = grouper.propose(brand)
    grouping = grouper.apply_change(
        grouping,
        "product.kaos boxy.size",
        [DocumentType.PRODUCT_KNOWLEDGE],
    )
    grouping = grouper.apply_change(
        grouping,
        "product.kaos boxy.size.ukuran",
        [DocumentType.GUIDE],
    )

    documents = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(brand, grouping)
    product_knowledge = next(
        document
        for document in documents
        if document.document_type == DocumentType.PRODUCT_KNOWLEDGE
    )
    guide = next(document for document in documents if document.document_type == DocumentType.GUIDE)

    assert [fact.path for fact in product_knowledge.sections[0].facts] == [facts[0].path]
    assert [fact.path for fact in guide.sections[0].facts] == [facts[1].path]


def test_advisor_returns_suggestions_outside_document_content(brand_data) -> None:
    suggestions = CompletenessAdvisor().suggest(brand_data)

    assert suggestions
    assert all(item.related_path for item in suggestions)


def test_session_store_expires_sessions() -> None:
    validator = build_validator(max_logo_bytes=100)
    result = validator.validate("brand: Example\n")
    assert result.data is not None
    brand = FactExtractor().extract(result.data, "brand: Example\n")
    session = Session(session_id="expired", brand=brand, grouping=DocumentGrouper().propose(brand))
    store = SessionStore(ttl=timedelta(minutes=0))
    store.create(session)

    with pytest.raises(SessionNotFoundError):
        store.get("expired")


class ManualClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _example_session(session_id: str) -> Session:
    brand = BrandData(brand_name="Example", raw_yaml="brand: Example", facts=[])
    return Session(session_id=session_id, brand=brand, grouping=Grouping(entries=[]))


def test_session_store_keeps_sessions_that_are_accessed() -> None:
    clock = ManualClock()
    store = SessionStore(ttl=timedelta(minutes=60), clock=clock)
    store.create(_example_session("active"))

    for _ in range(3):
        clock.now += timedelta(minutes=50)
        assert store.get("active").session_id == "active"


def test_session_store_expires_sessions_left_unused() -> None:
    clock = ManualClock()
    store = SessionStore(ttl=timedelta(minutes=60), clock=clock)
    store.create(_example_session("active"))
    store.create(_example_session("idle"))

    clock.now += timedelta(minutes=50)
    store.get("active")
    clock.now += timedelta(minutes=20)

    assert store.get("active").session_id == "active"
    with pytest.raises(SessionNotFoundError):
        store.get("idle")


def test_checker_drops_fabricated_paragraphs(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")
    doc = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        sections=[
            {
                "heading": "Retur",
                "order": 1,
                "source_section": "retur",
                "facts": [fact],
                "paragraphs": [
                    Paragraph(
                        text="Anda dapat mengajukan retur dalam 30 hari.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            }
        ],
    )

    checked, result = ContentChecker().check(doc, [fact])

    assert result.fabrication_found is True
    assert result.replaced_paragraphs == ["Anda dapat mengajukan retur dalam 30 hari."]
    assert checked.sections[0].paragraphs == []
    assert checked.sections[0].facts == [fact]


def test_checker_measures_llm_coverage_before_template_blocks() -> None:
    facts = [
        Fact(path="retur.batas_hari", value=7, data_kind=DataKind.GENERAL_BRAND, line=3),
        Fact(
            path="retur.syarat",
            value=["label masih terpasang"],
            data_kind=DataKind.GENERAL_BRAND,
            line=4,
        ),
    ]
    paragraph = Paragraph(
        text="Retur dapat diajukan sesuai batas hari.",
        origin=ParagraphOrigin.LLM,
        sources=[SourceReference(fact_path=facts[0].path, line=facts[0].line)],
    )
    section = Section(
        heading="Retur",
        order=1,
        source_section="retur",
        facts=facts,
        paragraphs=[paragraph],
    )
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[section],
    )

    checked, result = ContentChecker().check(document, facts)

    assert result.coverage_percent == 50
    assert result.uncovered_facts == []
    assert len(checked.sections[0].paragraphs) == 1


@pytest.mark.parametrize(
    ("fact_path", "paragraph_text"),
    [
        ("pengiriman.gratis_ongkir_min", "Gratis ongkir mulai Rp 300.000."),
        ("pengiriman.estimasi.jawa", "Estimasi berlangsung 2 sampai 3 hari."),
        ("product.kaos boxy.bahan", "Bahan menggunakan cotton combed 24s."),
    ],
)
def test_checker_accepts_equivalent_numbers(
    brand_data, fact_path: str, paragraph_text: str
) -> None:
    fact = next(item for item in brand_data.facts if item.path == fact_path)
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section=fact.section(),
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text=paragraph_text,
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is False


def test_checker_rejects_unsupported_unicode_proper_term(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section=fact.section(),
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text="Pilihan Élodie tersedia.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is True


def _check_retur_paragraph(text: str) -> bool:
    fact = Fact(path="retur.batas_hari", value=7, data_kind=DataKind.GENERAL_BRAND, line=2)
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section="retur",
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text=text,
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )
    _, result = ContentChecker().check(document, [fact])
    return result.fabrication_found


def test_checker_checks_sentence_start_word_again_mid_sentence() -> None:
    text = "Gojek menjemput retur Anda. Kurir Gojek datang dalam 7 hari."

    assert _check_retur_paragraph(text) is True


def test_checker_always_checks_ampersand_and_alphanumeric_tokens() -> None:
    assert _check_retur_paragraph("J&T menjemput retur dalam 7 hari.") is True
    assert _check_retur_paragraph("Retur dalam 7 hari. X7 menjemputnya.") is True


def test_checker_exempts_only_the_sentence_start_occurrence() -> None:
    assert _check_retur_paragraph("Kurir menjemput retur dalam 7 hari.") is False


def test_checker_accepts_brand_name_with_sentence_punctuation(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section=fact.section(),
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text="Silakan membaca kebijakan Kaos Rimba.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is False


def test_checker_matches_underscored_fact_keys_to_prose(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section=fact.section(),
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text="Pengajuan harus mengikuti Batas hari yang berlaku.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is False


def test_checker_accepts_normalized_numeric_shorthand(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "pengiriman.gratis_ongkir_min")
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        sections=[
            Section(
                heading="Pengiriman",
                order=1,
                source_section=fact.section(),
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text="Gratis ongkir mulai 300rb.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is False


def test_checker_rejects_integer_when_source_is_decimal() -> None:
    fact = Fact(
        path="retur.persentase",
        value=3.5,
        data_kind=DataKind.GENERAL_BRAND,
        line=2,
    )
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section="retur",
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text="Persentase retur mencapai 35.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is True


@pytest.mark.parametrize(
    ("text", "fabrication_found"),
    [
        ("Suhu tercatat 5 derajat.", True),
        ("Suhu tercatat -5 derajat.", False),
    ],
)
def test_checker_preserves_signs_of_negative_numbers(text: str, fabrication_found: bool) -> None:
    fact = Fact(
        path="suhu.minimum",
        value=-5,
        data_kind=DataKind.GENERAL_BRAND,
        line=2,
    )
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Suhu",
                order=1,
                source_section="suhu",
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text=text,
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is fabrication_found


def test_checker_accepts_supported_iso_date() -> None:
    fact = Fact(
        path="kebijakan.mulai_berlaku",
        value="2025-02-03",
        data_kind=DataKind.GENERAL_BRAND,
        line=2,
    )
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Kebijakan",
                order=1,
                source_section="kebijakan",
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text="Kebijakan berlaku sejak 2025-02-03.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is False


def test_checker_expands_unit_shared_by_range_endpoints() -> None:
    fact = Fact(
        path="pengiriman.biaya",
        value="2-3 juta",
        data_kind=DataKind.GENERAL_BRAND,
        line=2,
    )
    paragraph = Paragraph(
        text="Biaya berkisar antara 2.000.000 dan 3.000.000.",
        origin=ParagraphOrigin.LLM,
        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
    )
    section = Section(
        heading="Pengiriman",
        order=1,
        source_section="pengiriman",
        facts=[fact],
        paragraphs=[paragraph],
    )
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[section],
    )

    _, result = ContentChecker().check(document, [fact])

    assert result.fabrication_found is False


def test_checker_drops_paragraph_citing_foreign_facts(brand_data) -> None:
    local_fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")
    foreign_fact = next(
        item for item in brand_data.facts if item.path == "pengiriman.gratis_ongkir_min"
    )
    doc = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section="retur",
                facts=[local_fact],
                paragraphs=[
                    Paragraph(
                        text="Anda dapat mengajukan retur.",
                        origin=ParagraphOrigin.LLM,
                        sources=[
                            SourceReference(fact_path=local_fact.path, line=local_fact.line),
                            SourceReference(fact_path=foreign_fact.path, line=foreign_fact.line),
                        ],
                    )
                ],
            )
        ],
    )

    checked, result = ContentChecker().check(doc, brand_data.facts)

    assert result.replaced_paragraphs == ["Anda dapat mengajukan retur."]
    assert checked.sections[0].paragraphs == []
    assert checked.sections[0].facts == [local_fact]


def test_checker_ignores_the_document_date(brand_data) -> None:
    fact = next(item for item in brand_data.facts if item.path == "retur.batas_hari")
    doc = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Kaos Rimba",
        brand_name=brand_data.brand_name,
        generated_at=datetime.fromisoformat("2026-10-12T00:00:00+00:00"),
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section="retur",
                facts=[fact],
                paragraphs=[
                    Paragraph(
                        text="Batas retur tercatat pada 2026-10-12.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path=fact.path, line=fact.line)],
                    )
                ],
            )
        ],
    )

    checked, result = ContentChecker().check(doc, [fact])

    assert result.fabrication_found is False
    assert checked.sections[0].paragraphs[0].origin == ParagraphOrigin.LLM


def test_pdf_html_omits_source_references_and_suggestions(brand_data) -> None:
    grouping = DocumentGrouper().propose(brand_data)
    composer = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1)
    document = composer.compose(brand_data, grouping)[0]

    html = HtmlRenderer().render(document, show_sources=False)

    assert "retur.batas_hari \u00b7 L" not in html
    assert "Consider adding" not in html


def test_pdf_renderer_omits_source_references(monkeypatch: pytest.MonkeyPatch, brand_data) -> None:
    document = DocumentComposer(UnusedLlm(), use_llm=False, max_retries=1).compose(
        brand_data, DocumentGrouper().propose(brand_data)
    )[0]
    captured_html: list[str] = []

    class PdfHtmlDouble:
        def __init__(self, string: str) -> None:
            captured_html.append(string)

        @staticmethod
        def write_pdf() -> bytes:
            return b"%PDF-test"

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=PdfHtmlDouble))
    pdf = PdfRenderer(HtmlRenderer()).render(document)

    assert pdf.content == b"%PDF-test"
    assert "retur.batas_hari \u00b7 L" not in captured_html[0]


def test_pdf_renderer_maps_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingPdfHtml:
        def __init__(self, string: str) -> None:
            self.string = string

        def write_pdf(self) -> bytes:
            raise ValueError("Invalid generated HTML.")

    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
    )
    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FailingPdfHtml))

    with pytest.raises(PdfRenderError):
        PdfRenderer(HtmlRenderer()).render(document)


def test_pdf_renderer_maps_missing_weasyprint(monkeypatch: pytest.MonkeyPatch) -> None:
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
    )
    # A None entry makes "from weasyprint import HTML" raise ImportError, as without GTK.
    monkeypatch.setitem(sys.modules, "weasyprint", None)

    with pytest.raises(PdfEngineUnavailableError, match="PDF component is not installed"):
        PdfRenderer(HtmlRenderer()).render(document)


def test_pdf_write_failure_is_not_reported_as_missing_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingPdfHtml:
        def __init__(self, string: str) -> None:
            self.string = string

        def write_pdf(self) -> bytes:
            raise ValueError("Invalid generated HTML.")

    document = Document(document_type=DocumentType.POLICY, title="Kebijakan", brand_name="Contoh")
    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FailingPdfHtml))

    with pytest.raises(PdfRenderError) as raised:
        PdfRenderer(HtmlRenderer()).render(document)

    assert not isinstance(raised.value, PdfEngineUnavailableError)
    assert str(raised.value) == "Unable to render the requested PDF."


def _llm_document() -> Document:
    return Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        generated_at=datetime(2026, 10, 12, tzinfo=UTC),
        sections=[
            Section(
                heading="Retur",
                order=0,
                source_section="retur",
                facts=[
                    Fact(
                        path="retur.batas_hari",
                        value=7,
                        data_kind=DataKind.GENERAL_BRAND,
                        line=3,
                    )
                ],
                paragraphs=[
                    Paragraph(
                        text="Retur dalam 7 hari.",
                        origin=ParagraphOrigin.LLM,
                        sources=[SourceReference(fact_path="retur.batas_hari", line=3)],
                    )
                ],
            )
        ],
    )


def test_renderer_writes_document_header_meta_and_title() -> None:
    html = HtmlRenderer().render(_llm_document(), show_sources=True)

    assert '<span class="doc-meta">Contoh · Policy · 2026-10-12</span>' in html
    assert "<h1>Kebijakan Contoh</h1>" in html
    assert 'class="doc-header"' in html


def test_preview_shows_source_chips_and_preview_note() -> None:
    html = HtmlRenderer().render(_llm_document(), show_sources=True)

    assert '<span class="source">retur.batas_hari · L3</span>' in html
    assert html.count('<span class="source">') == 2
    assert 'class="preview-note"' in html
    assert 'class="preview-mode"' in html


def test_pdf_html_has_no_source_chips_or_preview_note() -> None:
    html = HtmlRenderer().render(_llm_document(), show_sources=False)

    assert 'class="source"' not in html
    assert "retur.batas_hari · L3" not in html
    assert 'class="preview-note"' not in html
    assert 'class="pdf-mode"' in html
    assert "<h1>Kebijakan Contoh</h1>" in html


def test_renderer_tables_general_mapping_of_mappings() -> None:
    facts = [
        Fact(path=f"size.{size}.{key}", value=value, data_kind=DataKind.GENERAL_BRAND, line=line)
        for line, (size, key, value) in enumerate(
            [
                ("S", "chest_cm", 50),
                ("S", "length_cm", 68),
                ("M", "chest_cm", 52),
                ("M", "length_cm", 70),
            ],
            start=1,
        )
    ]
    document = Document(
        document_type=DocumentType.GUIDE,
        title="Panduan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Ukuran",
                order=1,
                source_section="size",
                facts=facts,
            )
        ],
    )

    html = HtmlRenderer().render(document)

    assert "<table>" in html
    assert "<th>S</th>" in html
    assert "<th>M</th>" in html


def test_renderer_tables_mapping_with_one_shared_attribute() -> None:
    facts = [
        Fact(
            path=f"size.{size}.chest_cm",
            value=value,
            data_kind=DataKind.GENERAL_BRAND,
            line=line,
        )
        for line, (size, value) in enumerate([("S", 50), ("M", 52)], start=1)
    ]
    document = Document(
        document_type=DocumentType.GUIDE,
        title="Panduan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Ukuran",
                order=1,
                source_section="size",
                facts=facts,
            )
        ],
    )

    html = HtmlRenderer().render(document)

    assert "<table>" in html
    assert "<td>50</td>" in html
    assert "<td>52</td>" in html


def test_renderer_renders_scalar_lists() -> None:
    fact = Fact(
        path="retur.syarat",
        value=["label masih terpasang", "belum dicuci"],
        data_kind=DataKind.GENERAL_BRAND,
        line=3,
    )
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[Section(heading="Retur", order=1, source_section="retur", facts=[fact])],
    )

    html = HtmlRenderer().render(document)

    assert "<li>label masih terpasang</li>" in html
    assert "<li>belum dicuci</li>" in html


def test_renderer_preserves_nested_scalar_mapping_as_definition_list() -> None:
    facts = [
        Fact(
            path=f"retur.ongkir.{label}",
            value=value,
            data_kind=DataKind.GENERAL_BRAND,
            line=line,
        )
        for line, (label, value) in enumerate(
            [("normal", "ditanggung pembeli"), ("cacat", "ditanggung brand")],
            start=1,
        )
    ]
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section="retur",
                facts=facts,
            )
        ],
    )

    html = HtmlRenderer().render(document)

    assert "<h3>Ongkir</h3>" in html
    assert "<dt>Normal</dt>" in html
    assert "<dt>Cacat</dt>" in html
    assert "retur.ongkir.normal \u00b7 L1" in html


def test_renderer_escapes_user_values_as_text() -> None:
    fact = Fact(
        path="retur.catatan",
        value='<script>alert("x")</script>',
        data_kind=DataKind.GENERAL_BRAND,
        line=2,
    )
    document = Document(
        document_type=DocumentType.POLICY,
        title="Kebijakan Contoh",
        brand_name="Contoh",
        sections=[
            Section(
                heading="Retur",
                order=1,
                source_section="retur",
                facts=[fact],
            )
        ],
    )

    html = HtmlRenderer().render(document)

    assert "&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt;" in html
    assert "<script>alert" not in html


def test_logo_validation_checks_content_and_sanitizes_svg(fake_logo_file) -> None:
    validator = build_validator(max_logo_bytes=1024)
    uploaded = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xml:base="https://external.example/" '
        b'onload="run()">'
        b'<script>run()</script><image href="https://example.com/logo.png" />'
        b'<circle cx="2" cy="2" r="1" fill="url(https://example.com/gradient.svg#paint)" />'
        b"</svg>"
    )

    logo = validator.validate_logo("brand.svg", uploaded)
    assert logo.media_type == "image/svg+xml"
    assert b"script" not in logo.content
    assert b"onload" not in logo.content
    assert b"https://example.com" not in logo.content
    assert b"https://external.example" not in logo.content

    with pytest.raises(InvalidLogoError):
        validator.validate_logo("fake.png", fake_logo_file)


def test_logo_validation_accepts_valid_svg(valid_svg_logo) -> None:
    logo = build_validator(max_logo_bytes=1024).validate_logo("mark.svg", valid_svg_logo)

    assert logo.media_type == "image/svg+xml"


def test_logo_validation_accepts_valid_jpeg(valid_jpeg_logo) -> None:
    logo = build_validator(max_logo_bytes=1024).validate_logo("mark.jpg", valid_jpeg_logo)

    assert logo.media_type == "image/jpeg"


def test_logo_validation_rejects_jpeg_signature_without_frame() -> None:
    with pytest.raises(InvalidLogoError):
        build_validator(max_logo_bytes=1024).validate_logo("fake.jpg", b"\xff\xd8\xff\xd9")


def test_logo_validation_rejects_logo_over_the_size_limit(valid_png_logo) -> None:
    with pytest.raises(InvalidLogoError):
        build_validator(max_logo_bytes=len(valid_png_logo) - 1).validate_logo(
            "mark.png", valid_png_logo
        )
