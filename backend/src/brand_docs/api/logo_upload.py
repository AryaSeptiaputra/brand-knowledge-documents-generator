"""Read logo uploads into memory with a request size limit."""

from dataclasses import dataclass, field

from python_multipart.exceptions import FormParserError
from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import ClientDisconnect, Request

from brand_docs.api.schemas import LogoUpload
from brand_docs.errors import InvalidLogoError

LOGO_FIELD = "logo"
# Room for multipart boundaries and part headers around the logo bytes.
FORM_OVERHEAD_BYTES = 64 * 1024
TOO_LARGE_MESSAGE = "Logo is empty or exceeds the upload size limit."


@dataclass
class _FormPart:
    headers: dict[bytes, bytes] = field(default_factory=dict)
    content: bytearray = field(default_factory=bytearray)


class LogoFormReader:
    """Read a multipart logo upload without spooling it to disk."""

    def __init__(self, max_logo_bytes: int) -> None:
        self.max_body_bytes = max_logo_bytes + FORM_OVERHEAD_BYTES

    def _has_oversized_length(self, request: Request) -> bool:
        declared = request.headers.get("content-length", "")
        return declared.isdigit() and int(declared) > self.max_body_bytes

    async def _load_body(self, request: Request) -> bytes:
        body = bytearray()
        try:
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > self.max_body_bytes:
                    raise InvalidLogoError(TOO_LARGE_MESSAGE)
        except ClientDisconnect as error:
            raise InvalidLogoError("The logo upload was interrupted.") from error
        return bytes(body)

    @staticmethod
    def _split_parts(body: bytes, boundary: bytes) -> list[_FormPart]:
        parts: list[_FormPart] = []
        header_name = bytearray()
        header_value = bytearray()

        def on_header_end() -> None:
            parts[-1].headers[bytes(header_name).lower()] = bytes(header_value)
            header_name.clear()
            header_value.clear()

        parser = MultipartParser(
            boundary,
            {
                "on_part_begin": lambda: parts.append(_FormPart()),
                "on_header_field": lambda data, start, end: header_name.extend(data[start:end]),
                "on_header_value": lambda data, start, end: header_value.extend(data[start:end]),
                "on_header_end": on_header_end,
                "on_part_data": lambda data, start, end: parts[-1].content.extend(data[start:end]),
            },
        )
        try:
            parser.write(body)
            parser.finalize()
        except FormParserError as error:
            raise InvalidLogoError("The logo upload is not valid multipart form data.") from error
        return parts

    def _parse_form(self, body: bytes, content_type: str) -> LogoUpload:
        media_type, options = parse_options_header(content_type)
        boundary = options.get(b"boundary")
        if media_type != b"multipart/form-data" or not boundary:
            raise InvalidLogoError("Upload the logo as multipart form data.")
        for part in self._split_parts(body, boundary):
            _, disposition = parse_options_header(part.headers.get(b"content-disposition"))
            if disposition.get(b"name") != LOGO_FIELD.encode():
                continue
            file_name = disposition.get(b"filename")
            return LogoUpload(
                file_name=file_name.decode("utf-8", errors="replace") if file_name else None,
                content=bytes(part.content),
            )
        raise InvalidLogoError("Attach the logo in the 'logo' form field.")

    async def read(self, request: Request) -> LogoUpload:
        """Read the `logo` form field of a multipart request into memory.

        Args:
            request: Incoming upload request.

        Returns:
            The client file name and the raw logo bytes.

        Raises:
            InvalidLogoError: The body is too large, interrupted, or not a valid logo form.
        """
        if self._has_oversized_length(request):
            raise InvalidLogoError(TOO_LARGE_MESSAGE)
        body = await self._load_body(request)
        return self._parse_form(body, request.headers.get("content-type", ""))
