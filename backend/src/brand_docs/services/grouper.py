"""Propose deterministic document grouping from YAML structure."""

from brand_docs.domain.enums import DocumentType, UnitKind
from brand_docs.domain.models import BrandData, Grouping, GroupingEntry
from brand_docs.errors import UnknownGroupingSectionError
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)
GUIDE_KEYWORDS = frozenset(
    {
        "cara",
        "langkah",
        "panduan",
        "petunjuk",
        "tutorial",
        "perawatan",
        "rawat",
        "pemesanan",
        "pesan",
        "ukuran",
        "size",
        "sizing",
        "howto",
        "guide",
    }
)
SIZE_KEYWORDS = frozenset({"ukuran", "size", "sizing"})


class DocumentGrouper:
    """Create default groupings and apply user's grouping edits."""

    @staticmethod
    def _matches(key: str, keywords: frozenset[str]) -> bool:
        tokens = key.lower().replace("-", "_").replace(" ", "_").split("_")
        return any(token in keywords for token in tokens)

    def _units(self, brand: BrandData) -> list[tuple[str, UnitKind]]:
        units: list[tuple[str, UnitKind]] = []
        seen: set[str] = set()
        for fact in brand.facts:
            if fact.product is None:
                section = fact.path.split(".")[0]
                identity = f"general:{section}"
                if identity not in seen:
                    units.append((section, UnitKind.GENERAL_SECTION))
                    seen.add(identity)
                continue
            product_root = fact.path.split(".")[0]
            product_path = f"{product_root}.{fact.product}"
            product_identity = f"product:{product_path}"
            if product_identity not in seen:
                units.append((product_path, UnitKind.PRODUCT))
                seen.add(product_identity)
            components = fact.path.split(".")
            for index, component in enumerate(components[2:], start=2):
                if self._matches(component, SIZE_KEYWORDS):
                    size_path = ".".join(components[: index + 1])
                    size_identity = f"size:{size_path}"
                    if size_identity not in seen:
                        units.append((size_path, UnitKind.PRODUCT_SIZE))
                        seen.add(size_identity)
        return units

    def _classify(self, key: str, kind: UnitKind) -> list[DocumentType]:
        if kind == UnitKind.PRODUCT:
            return [DocumentType.PRODUCT_KNOWLEDGE]
        if kind == UnitKind.PRODUCT_SIZE:
            return [DocumentType.PRODUCT_KNOWLEDGE, DocumentType.GUIDE]
        if self._matches(key.split(".")[-1], GUIDE_KEYWORDS):
            return [DocumentType.POLICY, DocumentType.GUIDE]
        return [DocumentType.POLICY]

    def propose(self, brand: BrandData) -> Grouping:
        return Grouping(
            entries=[
                GroupingEntry(
                    section=section,
                    unit_kind=kind,
                    document_types=self._classify(section, kind),
                )
                for section, kind in self._units(brand)
            ]
        )

    def apply_change(
        self, grouping: Grouping, section: str, document_types: list[DocumentType]
    ) -> Grouping:
        entries = [entry.model_copy(deep=True) for entry in grouping.entries]
        target = next((entry for entry in entries if entry.section == section), None)
        if target is None:
            raise UnknownGroupingSectionError(f"Unknown grouping section: {section}.")
        target.document_types = list(dict.fromkeys(document_types))
        target.changed_by_user = True
        return Grouping(entries=entries, confirmed_by_user=True)
