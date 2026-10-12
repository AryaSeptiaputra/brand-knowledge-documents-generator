"""Shared YAML fixture for service and endpoint tests."""

import base64
from io import BytesIO

import pytest
from fastapi import UploadFile

from brand_docs.domain.models import BrandData
from brand_docs.services.extractor import FactExtractor
from brand_docs.services.validator import DataValidator

KAOS_RIMBA_YAML = """brand: Kaos Rimba
retur:
  batas_hari: 7
  syarat: [label masih terpasang, belum dicuci, ada bukti pembelian]
pengiriman:
  kurir: [JNE, J&T, SiCepat]
  estimasi: {jawa: \"2-3 hari\", luar_jawa: \"4-7 hari\"}
  gratis_ongkir_min: 300000
product:
  kaos boxy:
    size:
      S: {lebar_dada_cm: 50, panjang_cm: 68}
      M: {lebar_dada_cm: 52, panjang_cm: 70}
    bahan: cotton combed 24s
"""


@pytest.fixture
def brand_data() -> BrandData:
    validator = DataValidator(max_logo_bytes=1024 * 1024)
    result = validator.validate(KAOS_RIMBA_YAML)
    assert result.data is not None
    return FactExtractor().extract(result.data, KAOS_RIMBA_YAML)


@pytest.fixture
def yaml_without_brand() -> str:
    return "retur: true\n"


@pytest.fixture
def broken_yaml() -> str:
    return "brand: ["


@pytest.fixture
def valid_png_logo() -> UploadFile:
    content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
    )
    return UploadFile(filename="mark.png", file=BytesIO(content))


@pytest.fixture
def valid_svg_logo() -> UploadFile:
    content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1" /></svg>'
    return UploadFile(filename="mark.svg", file=BytesIO(content))


@pytest.fixture
def valid_jpeg_logo() -> UploadFile:
    content = base64.b64decode(
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
        "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
        "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
        "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
        "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
        "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
        "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
        "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
        "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
        "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
        "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iii"
        "gD//2Q=="
    )
    return UploadFile(filename="mark.jpg", file=BytesIO(content))


@pytest.fixture
def fake_logo_file() -> UploadFile:
    return UploadFile(filename="fake.png", file=BytesIO(b"not-an-image"))
