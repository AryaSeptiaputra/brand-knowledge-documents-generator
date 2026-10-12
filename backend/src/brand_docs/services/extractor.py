"""Extract stable source facts and products from parsed YAML."""

from collections.abc import Mapping
from datetime import UTC, date, datetime

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from brand_docs.domain.enums import DataKind
from brand_docs.domain.models import BrandData, Fact, Product
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)
PRODUCT_KEYS = frozenset({"product", "produk", "products"})


class FactExtractor:
    """Convert parsed YAML into ordered facts with source locations."""

    @staticmethod
    def _scalar(value: object) -> str | int | float | bool | date | datetime | None:
        if value is None or isinstance(value, (str, int, float, bool, date, datetime)):
            return value
        return str(value)

    def _walk(self, node: object, path: str, product: str | None, line: int) -> list[Fact]:
        facts: list[Fact] = []
        stack: list[tuple[object, str, int]] = [(node, path, line)]
        data_kind = DataKind.PRODUCT if product else DataKind.GENERAL_BRAND
        while stack:
            current, current_path, current_line = stack.pop()
            if isinstance(current, Mapping):
                for key, value in reversed(list(current.items())):
                    child_path = f"{current_path}.{key}" if current_path else str(key)
                    child_line = (
                        current.lc.key(key)[0] + 1
                        if isinstance(current, CommentedMap)
                        else current_line
                    )
                    stack.append((value, child_path, child_line))
                continue
            if isinstance(current, CommentedSeq):
                if all(not isinstance(value, (Mapping, list, tuple)) for value in current):
                    facts.append(
                        Fact(
                            path=current_path,
                            value=[self._scalar(value) for value in current],
                            data_kind=data_kind,
                            product=product,
                            line=current_line,
                        )
                    )
                    continue
                for index in reversed(range(len(current))):
                    value = current[index]
                    location = current.lc.item(index)
                    item_line = location[0] + 1 if location is not None else current_line
                    stack.append((value, f"{current_path}.{index}", item_line))
                continue
            if current is None or isinstance(current, (str, int, float, bool, date, datetime)):
                facts.append(
                    Fact(
                        path=current_path,
                        value=current,
                        data_kind=data_kind,
                        product=product,
                        line=current_line,
                    )
                )
        return facts

    def extract(self, data: CommentedMap, raw: str) -> BrandData:
        product_key = next((key for key in data if str(key).lower() in PRODUCT_KEYS), None)
        facts: list[Fact] = []
        products: list[Product] = []
        for key, value in data.items():
            key_text = str(key)
            if key_text.lower() in PRODUCT_KEYS and isinstance(value, CommentedMap):
                for product_name, product_data in value.items():
                    name = str(product_name)
                    path = f"{key_text}.{name}"
                    line = value.lc.key(product_name)[0] + 1
                    product_facts = self._walk(product_data, path, name, line)
                    facts.extend(product_facts)
                    products.append(
                        Product(name=name, fact_paths=[fact.path for fact in product_facts])
                    )
            if key == "brand" or key_text.lower() in PRODUCT_KEYS:
                continue
            line = data.lc.key(key)[0] + 1
            facts.extend(self._walk(value, key_text, None, line))
        if product_key is None:
            logger.debug("No product mapping found in submitted YAML")
        return BrandData(
            brand_name=str(data["brand"]),
            raw_yaml=raw,
            submitted_at=datetime.now(UTC),
            facts=facts,
            products=products,
        )
