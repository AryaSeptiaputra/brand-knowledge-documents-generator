"""HTTP workflow tests for the documented backend endpoints."""

import asyncio
import struct
import tempfile
import zlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from brand_docs.api.logo_upload import FORM_OVERHEAD_BYTES, LogoFormReader
from brand_docs.domain.models import BrandData, Grouping, PdfFile
from brand_docs.errors import InvalidLogoError
from brand_docs.main import create_app
from brand_docs.session.store import Session
from brand_docs.settings import Settings
from tests.conftest import KAOS_RIMBA_YAML


def _create_session(client: TestClient, broken_yaml: str) -> str:
    missing_field = client.post("/api/analyze", json={})
    assert missing_field.status_code == 422
    assert missing_field.json()["errors"]
    invalid = client.post("/api/analyze", json={"yaml": broken_yaml})
    assert invalid.status_code == 422
    assert "line" in invalid.json()["errors"][0]
    analyzed = client.post("/api/analyze", json={"yaml": KAOS_RIMBA_YAML})
    assert analyzed.status_code == 200
    return analyzed.json()["session_id"]


def _generate_and_preview(client: TestClient, session_id: str) -> None:
    changed = client.patch(
        "/api/grouping",
        json={"session_id": session_id, "section": "retur", "document_types": ["GUIDE"]},
    )
    assert changed.status_code == 200
    generated = client.post("/api/documents", json={"session_id": session_id})
    assert generated.status_code == 200
    assert generated.json()["documents"]
    preview = client.get("/api/documents/GUIDE/preview", params={"session_id": session_id})
    assert preview.status_code == 200
    assert "retur" in preview.text.lower()
    assert "\u00b7 L" in preview.text


def _verify_logo_endpoints(client: TestClient, session_id: str, valid_png_logo: bytes) -> None:
    upload = client.put(
        "/api/logo",
        params={"session_id": session_id},
        files={"logo": ("mark.png", valid_png_logo, "image/png")},
    )
    assert upload.status_code == 200
    assert upload.json()["media_type"] == "image/png"
    assert client.delete("/api/logo", params={"session_id": session_id}).status_code == 204
    invalid = client.put(
        "/api/logo",
        params={"session_id": session_id},
        files={"logo": ("fake.png", b"not-an-image", "image/png")},
    )
    assert invalid.status_code == 422


def _verify_pdf_endpoints(
    client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch, session_id: str
) -> None:
    services = app.state.services
    monkeypatch.setattr(
        services.pdf_renderer,
        "render",
        lambda doc, logo=None: PdfFile(
            file_name=f"{doc.document_type.value.lower()}.pdf",
            document_type=doc.document_type,
            content=b"pdf-test",
        ),
    )
    pdf = client.get("/api/documents/GUIDE/pdf", params={"session_id": session_id})
    assert pdf.status_code == 200
    assert pdf.content == b"pdf-test"
    archive = client.get("/api/documents/all/pdf", params={"session_id": session_id})
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"


def test_analyze_group_generate_preview_and_logo_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    broken_yaml: str,
    valid_png_logo: bytes,
) -> None:
    app = create_app(Settings(use_llm=False, max_logo_bytes=1024 * 1024))
    with TestClient(app) as client:
        session_id = _create_session(client, broken_yaml)
        _generate_and_preview(client, session_id)
        _verify_logo_endpoints(client, session_id, valid_png_logo)
        _verify_pdf_endpoints(client, app, monkeypatch, session_id)


def test_archive_download_before_generation_returns_404() -> None:
    app = create_app(Settings(use_llm=False))
    app.state.services.store.create(
        Session(
            session_id="not-generated",
            brand=BrandData(brand_name="Contoh", raw_yaml="", facts=[]),
            grouping=Grouping(entries=[]),
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/documents/all/pdf", params={"session_id": "not-generated"})

    assert response.status_code == 404


def test_session_expiry_returns_404() -> None:
    app = create_app(Settings(use_llm=False, session_ttl_minutes=0))
    with TestClient(app) as client:
        response = client.post("/api/documents", json={"session_id": "missing"})

    assert response.status_code == 404


def test_openapi_documents_project_error_responses() -> None:
    schema = create_app(Settings(use_llm=False)).openapi()
    analyze_error = schema["paths"]["/api/analyze"]["post"]["responses"]["422"]
    pdf_responses = schema["paths"]["/api/documents/{doc_type}/pdf"]["get"]["responses"]
    pdf_error = pdf_responses["500"]

    assert analyze_error["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
    assert pdf_error["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
    assert set(pdf_responses["200"]["content"]) == {"application/pdf", "application/zip"}


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _large_png(data_bytes: int) -> bytes:
    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", bytes(data_bytes))
        + _png_chunk(b"IEND", b"")
    )


def _analyze_session(client: TestClient) -> str:
    response = client.post("/api/analyze", json={"yaml": KAOS_RIMBA_YAML})
    assert response.status_code == 200
    return str(response.json()["session_id"])


def test_analyze_rejects_nested_alias_expansion() -> None:
    lines = ["brand: Example", "a0: &a0 [x, x, x, x, x, x, x, x, x, x]"]
    lines += [
        f"a{level}: &a{level} [" + ", ".join([f"*a{level - 1}"] * 10) + "]" for level in range(1, 6)
    ]
    app = create_app(Settings(use_llm=False, max_yaml_nodes=20_000))
    with TestClient(app) as client:
        response = client.post("/api/analyze", json={"yaml": "\n".join(lines) + "\n"})

    assert response.status_code == 422
    error = response.json()["errors"][0]
    assert "expands to more than 20000 values" in error["message"]
    assert error["line"] > 1


def test_analyze_rejects_yaml_over_the_size_limit() -> None:
    app = create_app(Settings(use_llm=False, max_yaml_bytes=64))
    with TestClient(app) as client:
        response = client.post("/api/analyze", json={"yaml": KAOS_RIMBA_YAML})

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == (
        "The YAML document exceeds the 64 byte limit."
    )


def test_logo_upload_stays_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_disk(*_: object, **__: object) -> None:
        raise AssertionError("The logo upload must not be written to disk.")

    for name in ("SpooledTemporaryFile", "TemporaryFile", "NamedTemporaryFile", "mkstemp"):
        monkeypatch.setattr(tempfile, name, refuse_disk)
    monkeypatch.setattr("starlette.formparsers.SpooledTemporaryFile", refuse_disk)
    logo = _large_png(2 * 1024 * 1024)
    app = create_app(Settings(use_llm=False, max_logo_bytes=5 * 1024 * 1024))
    with TestClient(app) as client:
        session_id = _analyze_session(client)
        response = client.put(
            "/api/logo",
            params={"session_id": session_id},
            files={"logo": ("big.png", logo, "image/png")},
        )

    assert response.status_code == 200
    assert response.json() == {"file_name": "big.png", "media_type": "image/png"}
    assert app.state.services.store.get(session_id).logo.content == logo


def test_logo_upload_rejects_oversized_declared_length() -> None:
    app = create_app(Settings(use_llm=False, max_logo_bytes=1024))
    with TestClient(app) as client:
        session_id = _analyze_session(client)
        response = client.put(
            "/api/logo",
            params={"session_id": session_id},
            files={"logo": ("big.png", _large_png(200 * 1024), "image/png")},
        )

    assert response.status_code == 422
    assert response.json() == {
        "errors": [{"message": "Logo is empty or exceeds the upload size limit."}]
    }


def test_logo_reader_stops_reading_an_oversized_stream() -> None:
    received: list[int] = []

    async def receive() -> dict[str, object]:
        received.append(len(received))
        return {"type": "http.request", "body": b"x" * 16 * 1024, "more_body": True}

    scope = {
        "type": "http",
        "method": "PUT",
        "path": "/api/logo",
        "headers": [(b"content-type", b"multipart/form-data; boundary=x")],
    }
    reader = LogoFormReader(max_logo_bytes=1024)

    with pytest.raises(InvalidLogoError):
        asyncio.run(reader.read(Request(scope, receive)))

    assert len(received) == (1024 + FORM_OVERHEAD_BYTES) // (16 * 1024) + 1


def test_logo_upload_rejects_logo_over_limit_within_form_overhead() -> None:
    app = create_app(Settings(use_llm=False, max_logo_bytes=1024))
    with TestClient(app) as client:
        session_id = _analyze_session(client)
        response = client.put(
            "/api/logo",
            params={"session_id": session_id},
            files={"logo": ("big.png", _large_png(4 * 1024), "image/png")},
        )

    assert response.status_code == 422


def test_logo_upload_requires_the_logo_field() -> None:
    app = create_app(Settings(use_llm=False))
    with TestClient(app) as client:
        session_id = _analyze_session(client)
        response = client.put(
            "/api/logo",
            params={"session_id": session_id},
            files={"image": ("mark.png", b"data", "image/png")},
        )

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == "Attach the logo in the 'logo' form field."


def test_openapi_documents_logo_multipart_body() -> None:
    schema = create_app(Settings(use_llm=False)).openapi()
    body = schema["paths"]["/api/logo"]["put"]["requestBody"]

    logo_schema = body["content"]["multipart/form-data"]["schema"]
    assert body["required"] is True
    assert logo_schema["properties"]["logo"]["format"] == "binary"
