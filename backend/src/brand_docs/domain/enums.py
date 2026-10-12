"""Domain enumerations."""

from enum import StrEnum


class DataKind(StrEnum):
    GENERAL_BRAND = "GENERAL_BRAND"
    PRODUCT = "PRODUCT"


class DocumentType(StrEnum):
    POLICY = "POLICY"
    GUIDE = "GUIDE"
    PRODUCT_KNOWLEDGE = "PRODUCT_KNOWLEDGE"


class ParagraphOrigin(StrEnum):
    LLM = "LLM"


class UnitKind(StrEnum):
    GENERAL_SECTION = "GENERAL_SECTION"
    PRODUCT = "PRODUCT"
    PRODUCT_SIZE = "PRODUCT_SIZE"
