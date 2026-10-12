"""Project errors translated into safe API responses."""


class BrandDocsError(Exception):
    """Base class for expected application errors."""


class YamlValidationError(BrandDocsError):
    """YAML validation failure with source location."""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


class UnknownGroupingSectionError(BrandDocsError):
    """Grouping change refers to a section that is not in the session grouping."""


class UnknownDocumentTypeError(BrandDocsError):
    """Requested document type is not a known document type."""


class SessionNotFoundError(BrandDocsError):
    """Requested session is missing or expired."""


class InvalidLogoError(BrandDocsError):
    """Logo upload is unsupported, invalid, or too large."""


class LlmUnavailableError(BrandDocsError):
    """Local Ollama service cannot be reached."""


class LlmOutputError(BrandDocsError):
    """Ollama returned output that does not match its schema."""


class PdfRenderError(BrandDocsError):
    """HTML could not be rendered as a PDF."""


class PdfEngineUnavailableError(PdfRenderError):
    """The PDF engine or its system libraries are not installed on the server."""
