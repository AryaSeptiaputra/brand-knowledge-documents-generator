"""HTTP workflow tests for the documented backend endpoints."""

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from brand_docs.domain.models import BrandData, Grouping, PdfFile
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


def _verify_logo_endpoints(
    client: TestClient, session_id: str, valid_png_logo: UploadFile
) -> None:
    upload = client.put(
        "/api/logo",
        params={"session_id": session_id},
        files={
            "logo": (
                valid_png_logo.filename,
                valid_png_logo.file.read(),
                "image/png",
            )
        },
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
    valid_png_logo: UploadFile,
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
        response = client.get(
            "/api/documents/all/pdf", params={"session_id": "not-generated"}
        )

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

    assert analyze_error["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
    assert pdf_error["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
    assert set(pdf_responses["200"]["content"]) == {"application/pdf", "application/zip"}
