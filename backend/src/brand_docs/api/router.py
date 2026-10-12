"""HTTP endpoints coordinating workflow services."""

from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from brand_docs.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorDetail,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    GroupingChange,
    LogoInfo,
    LogoUpload,
)
from brand_docs.domain.enums import DocumentType
from brand_docs.domain.models import Document, Grouping
from brand_docs.errors import InvalidLogoError, SessionNotFoundError, UnknownDocumentTypeError
from brand_docs.factory import Services
from brand_docs.session.store import Session
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)
SESSION_ERROR = {
    "model": ErrorResponse,
    "description": "The requested session or document was not found.",
}
DOCUMENT_ERROR = {
    "model": ErrorResponse,
    "description": "The session, document type, or generated document was not found.",
}
VALIDATION_ERROR = {
    "model": ErrorResponse,
    "description": "The submitted data is invalid.",
}
GROUPING_ERROR = {
    "model": ErrorResponse,
    "description": "The submitted grouping change is invalid or names an unknown section.",
}
PDF_ERROR = {"model": ErrorResponse, "description": "The document could not be rendered."}
PDF_CONTENT = {"schema": {"type": "string", "format": "binary"}}
LOGO_REQUEST_BODY = {
    "required": True,
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["logo"],
                "properties": {"logo": {"type": "string", "format": "binary", "title": "Logo"}},
            }
        }
    },
}


def get_services(request: Request) -> Services:
    """Resolve configured services from the application instance."""
    return cast(Services, request.app.state.services)


async def read_logo_upload(
    request: Request, services: Annotated[Services, Depends(get_services)]
) -> LogoUpload:
    """Read the multipart logo body in memory within the configured size limit."""
    return await services.logo_reader.read(request)


class ApiRouter:
    """Coordinate API requests and translate expected errors."""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api")
        self._register_routes()

    def _register_analyze_routes(self) -> None:
        self.router.add_api_route(
            "/analyze",
            self.analyze,
            methods=["POST"],
            response_model=AnalyzeResponse,
            responses={422: VALIDATION_ERROR},
        )
        self.router.add_api_route(
            "/grouping",
            self.change_grouping,
            methods=["PATCH"],
            response_model=Grouping,
            responses={404: SESSION_ERROR, 422: GROUPING_ERROR},
        )

    def _register_document_routes(self) -> None:
        self.router.add_api_route(
            "/documents",
            self.generate,
            methods=["POST"],
            response_model=GenerateResponse,
            responses={404: SESSION_ERROR},
        )
        self.router.add_api_route(
            "/documents/{doc_type}/preview",
            self.preview,
            methods=["GET"],
            response_class=Response,
            responses={
                200: {
                    "description": "The document preview as HTML.",
                    "content": {"text/html": {"schema": {"type": "string"}}},
                },
                404: DOCUMENT_ERROR,
                422: VALIDATION_ERROR,
            },
        )
        self.router.add_api_route(
            "/documents/{doc_type}/pdf",
            self.download_pdf,
            methods=["GET"],
            response_class=Response,
            responses={
                200: {
                    "description": "A PDF file or ZIP archive.",
                    "content": {
                        "application/pdf": PDF_CONTENT,
                        "application/zip": PDF_CONTENT,
                    },
                },
                404: DOCUMENT_ERROR,
                422: VALIDATION_ERROR,
                500: PDF_ERROR,
            },
        )

    def _register_logo_routes(self) -> None:
        self.router.add_api_route(
            "/logo",
            self.upload_logo,
            methods=["PUT"],
            response_model=LogoInfo,
            responses={404: SESSION_ERROR, 422: VALIDATION_ERROR},
            openapi_extra={"requestBody": LOGO_REQUEST_BODY},
        )
        self.router.add_api_route(
            "/logo",
            self.delete_logo,
            methods=["DELETE"],
            status_code=204,
            responses={404: SESSION_ERROR},
        )

    def _register_routes(self) -> None:
        self._register_analyze_routes()
        self._register_document_routes()
        self._register_logo_routes()

    def analyze(
        self, req: AnalyzeRequest, services: Annotated[Services, Depends(get_services)]
    ) -> AnalyzeResponse | Response:
        result = services.validator.validate(req.yaml)
        if not result.is_valid or result.data is None:
            return Response(
                content=ErrorResponse(
                    errors=[
                        ErrorDetail(message=error.message, line=error.line, column=error.column)
                        for error in result.errors
                    ]
                ).model_dump_json(),
                status_code=422,
                media_type="application/json",
            )
        brand = services.extractor.extract(result.data, req.yaml)
        grouping = services.grouper.propose(brand)
        suggestions = services.advisor.suggest(brand)
        session = Session(
            session_id=str(uuid4()), brand=brand, grouping=grouping, suggestions=suggestions
        )
        session_id = services.store.create(session)
        return AnalyzeResponse(
            session_id=session_id,
            brand_name=brand.brand_name,
            grouping=grouping,
            suggestions=suggestions,
        )

    def change_grouping(
        self, req: GroupingChange, services: Annotated[Services, Depends(get_services)]
    ) -> Grouping:
        session = services.store.get(req.session_id)
        session.grouping = services.grouper.apply_change(
            session.grouping, req.section, req.document_types
        )
        return session.grouping

    def generate(
        self, req: GenerateRequest, services: Annotated[Services, Depends(get_services)]
    ) -> GenerateResponse:
        session = services.store.get(req.session_id)
        documents = services.composer.compose(session.brand, session.grouping)
        checked_results = [
            services.checker.check(document, session.brand.facts) for document in documents
        ]
        session.documents = [item[0] for item in checked_results]
        session.check_results = [item[1] for item in checked_results]
        return GenerateResponse(documents=session.documents, check_results=session.check_results)

    @staticmethod
    def _find_document(session: Session, doc_type: str) -> Document:
        try:
            selected_type = DocumentType(doc_type.upper())
        except ValueError as error:
            raise UnknownDocumentTypeError(f"Unknown document type: {doc_type}.") from error
        document = next(
            (item for item in session.documents if item.document_type == selected_type), None
        )
        if document is None:
            raise SessionNotFoundError("The requested document has not been generated.")
        return document

    def preview(
        self,
        doc_type: str,
        session_id: str,
        services: Annotated[Services, Depends(get_services)],
    ) -> HTMLResponse:
        session = services.store.get(session_id)
        document = self._find_document(session, doc_type)
        content = services.html_renderer.render(document, session.logo, show_sources=True)
        return HTMLResponse(content=content)

    def download_pdf(
        self,
        doc_type: str,
        session_id: str,
        services: Annotated[Services, Depends(get_services)],
    ) -> Response:
        session = services.store.get(session_id)
        if doc_type.lower() == "all":
            if not session.documents:
                raise SessionNotFoundError("No documents have been generated for this session.")
            content = services.pdf_renderer.render_all(session.documents, session.logo)
            return Response(
                content=content,
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="brand-documents.zip"'},
            )
        document = self._find_document(session, doc_type)
        pdf = services.pdf_renderer.render(document, session.logo)
        return Response(
            content=pdf.content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{pdf.file_name}"'},
        )

    def upload_logo(
        self,
        session_id: str,
        upload: Annotated[LogoUpload, Depends(read_logo_upload)],
        services: Annotated[Services, Depends(get_services)],
    ) -> LogoInfo | Response:
        services.store.get(session_id)
        try:
            brand_logo = services.validator.validate_logo(upload.file_name, upload.content)
        except InvalidLogoError as error:
            return Response(
                content=ErrorResponse(errors=[ErrorDetail(message=str(error))]).model_dump_json(
                    exclude_none=True
                ),
                status_code=422,
                media_type="application/json",
            )
        services.store.set_logo(session_id, brand_logo)
        return LogoInfo(file_name=brand_logo.file_name, media_type=brand_logo.media_type)

    def delete_logo(
        self, session_id: str, services: Annotated[Services, Depends(get_services)]
    ) -> Response:
        services.store.set_logo(session_id, None)
        return Response(status_code=204)
