"""YAML and logo validation services."""

import re
import struct
import zlib
from pathlib import Path
from threading import RLock
from xml.etree import ElementTree

from fastapi import UploadFile
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from brand_docs.domain.models import BrandLogo, ValidationResult, YamlError
from brand_docs.errors import InvalidLogoError
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)


class DataValidator:
    """Validate user YAML and optional uploaded brand logos."""

    def __init__(self, max_logo_bytes: int) -> None:
        self.max_logo_bytes = max_logo_bytes
        self.yaml = YAML(typ="rt")
        self.yaml.allow_duplicate_keys = False
        self.yaml_lock = RLock()

    @staticmethod
    def _has_cycle(data: object) -> bool:
        active: set[int] = set()
        complete: set[int] = set()
        stack: list[tuple[object, bool]] = [(data, False)]
        while stack:
            node, exiting = stack.pop()
            if not isinstance(node, (CommentedMap, list, tuple, CommentedSeq)):
                continue
            identity = id(node)
            if exiting:
                active.remove(identity)
                complete.add(identity)
                continue
            if identity in active:
                return True
            if identity in complete:
                continue
            active.add(identity)
            stack.append((node, True))
            values = node.values() if isinstance(node, CommentedMap) else node
            stack.extend((value, False) for value in values)
        return False

    def _error_for_key(self, data: CommentedMap, key: object, message: str) -> YamlError:
        try:
            location = data.lc.key(key)
        except KeyError:
            location = None
        line, column = location if location is not None else (0, 0)
        return YamlError(message=message, line=line + 1, column=column + 1)

    def _validate_root(self, data: CommentedMap) -> ValidationResult:
        errors: list[YamlError] = []
        brand = data.get("brand")
        if not isinstance(brand, str) or not brand.strip():
            errors.append(self._error_for_key(data, "brand", "Add a non-empty brand name."))
        for key, value in data.items():
            if str(key).lower() in {"product", "produk", "products"} and not isinstance(
                value, CommentedMap
            ):
                errors.append(
                    self._error_for_key(
                        data, key, "Product data must be a mapping of product names."
                    )
                )
        return ValidationResult(
            is_valid=not errors,
            errors=errors,
            data=data if not errors else None,
        )

    def validate(self, raw: str) -> ValidationResult:
        try:
            with self.yaml_lock:
                data = self.yaml.load(raw)
        except YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            line = mark.line + 1 if mark else 1
            column = mark.column + 1 if mark else 1
            problem = getattr(error, "problem", None) or "Invalid YAML"
            return ValidationResult(
                is_valid=False,
                errors=[YamlError(message=problem, line=line, column=column)],
            )
        except RecursionError:
            return ValidationResult(
                is_valid=False,
                errors=[
                    YamlError(message="The YAML document is nested too deeply.", line=1, column=1)
                ],
            )
        if not isinstance(data, CommentedMap):
            return ValidationResult(
                is_valid=False,
                errors=[
                    YamlError(message="The YAML document must be a mapping.", line=1, column=1)
                ],
            )
        if self._has_cycle(data):
            return ValidationResult(
                is_valid=False,
                errors=[
                    YamlError(
                        message="Recursive YAML aliases are not supported.",
                        line=1,
                        column=1,
                    )
                ],
            )
        return self._validate_root(data)

    @staticmethod
    def _is_valid_png(content: bytes) -> bool:
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            return False
        offset = 8
        has_header = False
        has_data = False
        has_end = False
        while offset + 12 <= len(content):
            length = struct.unpack(">I", content[offset : offset + 4])[0]
            chunk_type = content[offset + 4 : offset + 8]
            chunk_end = offset + 12 + length
            if chunk_end > len(content):
                return False
            chunk = content[offset + 4 : offset + 8 + length]
            expected_crc = struct.unpack(">I", content[offset + 8 + length : chunk_end])[0]
            if zlib.crc32(chunk) & 0xFFFFFFFF != expected_crc:
                return False
            if chunk_type == b"IHDR" and length != 13:
                return False
            if chunk_type == b"IHDR":
                width, height = struct.unpack(">II", content[offset + 8 : offset + 16])
                if width == 0 or height == 0:
                    return False
                has_header = True
            elif chunk_type == b"IDAT":
                has_data = True
            elif chunk_type == b"IEND":
                has_end = length == 0
                break
            offset = chunk_end
        return has_header and has_data and has_end

    @staticmethod
    def _is_valid_jpeg(content: bytes) -> bool:
        if (
            len(content) < 4
            or not content.startswith(b"\xff\xd8")
            or not content.endswith(b"\xff\xd9")
        ):
            return False
        frame_markers = {
            0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
        }
        offset = 2
        has_frame = False
        while offset < len(content) - 2:
            if content[offset] != 0xFF:
                return False
            while offset < len(content) and content[offset] == 0xFF:
                offset += 1
            if offset >= len(content):
                return False
            marker = content[offset]
            offset += 1
            if marker in {0xD8, 0xD9}:
                return False
            if marker == 0x01 or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(content):
                return False
            segment_length = struct.unpack(">H", content[offset : offset + 2])[0]
            if segment_length < 2 or offset + segment_length > len(content):
                return False
            if marker in frame_markers:
                if segment_length < 8:
                    return False
                height, width = struct.unpack(">HH", content[offset + 3 : offset + 7])
                if not height or not width:
                    return False
                has_frame = True
            if marker == 0xDA:
                return has_frame and content.endswith(b"\xff\xd9")
            offset += segment_length
        return False

    @staticmethod
    def _detect_logo_type(content: bytes) -> str | None:
        if DataValidator._is_valid_png(content):
            return "image/png"
        if DataValidator._is_valid_jpeg(content):
            return "image/jpeg"
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError:
            return None
        if root.tag.rsplit("}", 1)[-1].lower() == "svg":
            return "image/svg+xml"
        return None

    @staticmethod
    def _sanitize_svg(content: bytes) -> bytes:
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as error:
            logger.error("Invalid SVG logo", exc_info=True)
            raise InvalidLogoError("The uploaded SVG is invalid.") from error
        # Removes external CSS URLs and imports from style attributes and style elements.
        style_pattern = re.compile(
            r"url\s*\(\s*['\"]?(?!#)[^)]+\)|@import[^;]+;",
            re.IGNORECASE,
        )
        for parent in root.iter():
            for child in list(parent):
                if child.tag.rsplit("}", 1)[-1].lower() in {"script", "foreignobject", "iframe"}:
                    parent.remove(child)
            for attribute in list(parent.attrib):
                value = parent.attrib[attribute].strip().lower()
                name = attribute.rsplit("}", 1)[-1].lower()
                if (
                    name == "base"
                    or name.startswith("on")
                    or (name in {"href", "src"} and not value.startswith("#"))
                ):
                    del parent.attrib[attribute]
                elif style_pattern.search(value):
                    parent.attrib[attribute] = style_pattern.sub("", parent.attrib[attribute])
        for element in root.iter():
            if "style" in element.attrib:
                element.attrib["style"] = style_pattern.sub("", element.attrib["style"])
            if element.tag.rsplit("}", 1)[-1].lower() == "style" and element.text:
                element.text = style_pattern.sub("", element.text)
        return ElementTree.tostring(root, encoding="utf-8")

    def validate_logo(self, file: UploadFile) -> BrandLogo:
        try:
            content = file.file.read(self.max_logo_bytes + 1)
        except OSError as error:
            logger.error("Unable to read logo upload", exc_info=True)
            raise InvalidLogoError("Unable to read the uploaded logo.") from error
        if not content or len(content) > self.max_logo_bytes:
            raise InvalidLogoError("Logo is empty or exceeds the upload size limit.")
        media_type = self._detect_logo_type(content)
        if media_type is None:
            raise InvalidLogoError("Only valid PNG, JPEG, and SVG logos are supported.")
        safe_content = self._sanitize_svg(content) if media_type == "image/svg+xml" else content
        return BrandLogo(
            file_name=Path(file.filename or "brand-logo").name,
            media_type=media_type,
            content=safe_content,
        )
