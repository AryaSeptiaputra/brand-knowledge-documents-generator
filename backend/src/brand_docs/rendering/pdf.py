"""Render HTML documents to accessible, text-based PDFs."""

import io
import zipfile

from brand_docs.domain.models import BrandLogo, Document, PdfFile
from brand_docs.errors import PdfEngineUnavailableError, PdfRenderError
from brand_docs.rendering.html import HtmlRenderer
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)


class PdfRenderer:
    """Render individual PDFs and a ZIP containing every document."""

    def __init__(self, html: HtmlRenderer) -> None:
        self.html = html

    def _write_pdf(self, html: str) -> bytes:
        try:
            # Imported on use so the app and tests start without the GTK libraries WeasyPrint needs.
            from weasyprint import HTML
        except (ImportError, OSError) as error:
            logger.error("PDF engine could not be loaded", exc_info=True)
            raise PdfEngineUnavailableError(
                "PDF download is not available because the PDF component is not installed "
                "on the server."
            ) from error
        try:
            content = HTML(string=html).write_pdf()
        except (OSError, ValueError) as error:
            logger.error("PDF rendering failed", exc_info=True)
            raise PdfRenderError("Unable to render the requested PDF.") from error
        if not isinstance(content, bytes):
            raise PdfRenderError("Unable to render the requested PDF.")
        return content

    def render(self, doc: Document, logo: BrandLogo | None = None) -> PdfFile:
        return PdfFile(
            file_name=f"{doc.document_type.value.lower()}.pdf",
            document_type=doc.document_type,
            content=self._write_pdf(self.html.render(doc, logo, show_sources=False)),
        )

    def render_all(self, docs: list[Document], logo: BrandLogo | None = None) -> bytes:
        archive = io.BytesIO()
        try:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
                for doc in docs:
                    pdf = self.render(doc, logo)
                    zipped.writestr(pdf.file_name, pdf.content)
        except (OSError, zipfile.BadZipFile) as error:
            logger.error("PDF archive rendering failed", exc_info=True)
            raise PdfRenderError("Unable to render the requested PDF archive.") from error
        return archive.getvalue()
