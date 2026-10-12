"""Shared fixtures for service and endpoint tests, read from tests/fixtures/."""

from pathlib import Path

import pytest

from brand_docs.domain.models import BrandData
from brand_docs.services.extractor import FactExtractor
from brand_docs.services.validator import DataValidator

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def read_fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def build_validator(
    max_logo_bytes: int = 100, max_yaml_bytes: int = 1024 * 1024, max_yaml_nodes: int = 20_000
) -> DataValidator:
    return DataValidator(max_logo_bytes, max_yaml_bytes, max_yaml_nodes)


def extract_brand(yaml_text: str) -> BrandData:
    result = build_validator(max_logo_bytes=1024 * 1024).validate(yaml_text)
    assert result.data is not None
    return FactExtractor().extract(result.data, yaml_text)


KAOS_RIMBA_YAML = read_fixture_text("kaos_rimba.yaml")


@pytest.fixture
def brand_data() -> BrandData:
    return extract_brand(KAOS_RIMBA_YAML)


@pytest.fixture
def fact_in_two_documents() -> BrandData:
    return extract_brand(read_fixture_text("fact_in_two_documents.yaml"))


@pytest.fixture
def yaml_without_brand() -> str:
    return read_fixture_text("without_brand.yaml")


@pytest.fixture
def broken_yaml() -> str:
    return read_fixture_text("broken.yaml")


@pytest.fixture
def valid_png_logo() -> bytes:
    return read_fixture_bytes("logo.png")


@pytest.fixture
def valid_svg_logo() -> bytes:
    return read_fixture_bytes("logo.svg")


@pytest.fixture
def valid_jpeg_logo() -> bytes:
    return read_fixture_bytes("logo.jpg")


@pytest.fixture
def fake_logo_file() -> bytes:
    return read_fixture_bytes("fake_logo.png")
