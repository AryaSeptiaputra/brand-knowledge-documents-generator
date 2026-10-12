"""Build configured services and shared application dependencies."""

from dataclasses import dataclass
from datetime import timedelta

from brand_docs.llm.ollama_client import OllamaClient
from brand_docs.rendering.html import HtmlRenderer
from brand_docs.rendering.pdf import PdfRenderer
from brand_docs.services.advisor import CompletenessAdvisor
from brand_docs.services.checker import ContentChecker
from brand_docs.services.composer import DocumentComposer
from brand_docs.services.extractor import FactExtractor
from brand_docs.services.grouper import DocumentGrouper
from brand_docs.services.validator import DataValidator
from brand_docs.session.store import SessionStore
from brand_docs.settings import Settings


@dataclass
class Services:
    settings: Settings
    store: SessionStore
    validator: DataValidator
    extractor: FactExtractor
    grouper: DocumentGrouper
    advisor: CompletenessAdvisor
    composer: DocumentComposer
    checker: ContentChecker
    html_renderer: HtmlRenderer
    pdf_renderer: PdfRenderer


def build_services(settings: Settings) -> Services:
    """Wire production service instances from one settings object."""
    html_renderer = HtmlRenderer()
    ollama = OllamaClient(settings)
    return Services(
        settings=settings,
        store=SessionStore(timedelta(minutes=settings.session_ttl_minutes)),
        validator=DataValidator(settings.max_logo_bytes),
        extractor=FactExtractor(),
        grouper=DocumentGrouper(),
        advisor=CompletenessAdvisor(),
        composer=DocumentComposer(ollama, settings.use_llm, settings.max_retries),
        checker=ContentChecker(),
        html_renderer=html_renderer,
        pdf_renderer=PdfRenderer(html_renderer),
    )
