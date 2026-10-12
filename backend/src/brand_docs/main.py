"""FastAPI application factory and local server entry point."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from brand_docs.api.router import ApiRouter
from brand_docs.errors import (
    BrandDocsError,
    InvalidLogoError,
    PdfRenderError,
    SessionNotFoundError,
    UnknownDocumentTypeError,
    UnknownGroupingSectionError,
    YamlValidationError,
)
from brand_docs.factory import build_services
from brand_docs.settings import Settings
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)
FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"


# Starlette types every handler as (Request, Exception); each handler is registered for one class.
def _session_not_found(_: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"errors": [{"message": str(error)}]})


def _invalid_data(_: Request, error: Exception) -> JSONResponse:
    detail: dict[str, str | int] = {"message": str(error)}
    if isinstance(error, YamlValidationError):
        detail = {"message": error.message, "line": error.line, "column": error.column}
    return JSONResponse(status_code=422, content={"errors": [detail]})


def _invalid_request(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        return JSONResponse(status_code=422, content={"errors": [{"message": str(error)}]})
    return JSONResponse(
        status_code=422,
        content={"errors": [{"message": item["msg"]} for item in error.errors()]},
    )


def _invalid_logo(_: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errors": [{"message": str(error)}]})


def _pdf_error(_: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"errors": [{"message": str(error)}]})


def _application_error(_: Request, error: Exception) -> JSONResponse:
    logger.error("Unhandled project error", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"errors": [{"message": "Document generation failed."}]},
    )


def _register_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(SessionNotFoundError, _session_not_found)
    application.add_exception_handler(UnknownDocumentTypeError, _session_not_found)
    application.add_exception_handler(UnknownGroupingSectionError, _invalid_data)
    application.add_exception_handler(YamlValidationError, _invalid_data)
    application.add_exception_handler(RequestValidationError, _invalid_request)
    application.add_exception_handler(InvalidLogoError, _invalid_logo)
    application.add_exception_handler(PdfRenderError, _pdf_error)
    application.add_exception_handler(BrandDocsError, _application_error)


def _register_frontend(application: FastAPI, frontend: Path) -> None:
    if not frontend.exists():
        return

    @application.get("/{path:path}", include_in_schema=False, response_model=None)
    def serve_frontend(path: str) -> FileResponse | JSONResponse:
        if path == "api" or path.startswith("api/"):
            return JSONResponse(
                status_code=404, content={"errors": [{"message": "API endpoint not found."}]}
            )
        candidate = (frontend / path).resolve()
        if not candidate.is_relative_to(frontend.resolve()) or not candidate.is_file():
            candidate = frontend / "index.html"
        return FileResponse(candidate)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API application with its service dependencies."""
    application = FastAPI(title="Brand Knowledge Document Generator", version="0.1.0")
    application.state.services = build_services(settings or Settings())
    application.include_router(ApiRouter().router)
    _register_error_handlers(application)
    _register_frontend(application, FRONTEND_DIST)

    return application


app = create_app()
