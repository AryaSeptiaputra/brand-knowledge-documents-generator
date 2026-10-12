"""Render documents as safe HTML for preview and PDF conversion."""

import base64
from collections import defaultdict
from typing import TypedDict

from jinja2 import Environment, PackageLoader

from brand_docs.domain.models import BrandLogo, Document, Fact
from brand_docs.utils.logger import setup_logger
from brand_docs.utils.text import humanize_key

logger = setup_logger(__name__)


class RenderRow(TypedDict):
    label: str
    values: list[str]


class RenderDefinition(TypedDict):
    label: str
    value: str


class RenderBlock(TypedDict):
    kind: str
    label: str
    value: str
    items: list[str]
    caption: str
    row_heading: str
    headings: list[str]
    rows: list[RenderRow]
    definitions: list[RenderDefinition]
    source_label: str


class HtmlRenderer:
    """Render the shared customer document template."""

    def __init__(self) -> None:
        self.env = Environment(
            loader=PackageLoader("brand_docs.rendering", "templates"),
            autoescape=True,
        )
        self.env.filters["humanize_key"] = humanize_key

    def _table_groups(self, facts: list[Fact]) -> dict[str, list[Fact]]:
        table_candidates: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            parts = fact.path.split(".")
            if len(parts) >= 3:
                table_candidates[".".join(parts[:-2])].append(fact)
        table_groups: dict[str, list[Fact]] = {}
        for parent, candidates in table_candidates.items():
            rows = list(dict.fromkeys(fact.path.split(".")[-2] for fact in candidates))
            headings = list(dict.fromkeys(fact.path.split(".")[-1] for fact in candidates))
            headings_by_row = {
                row: {
                    fact.path.split(".")[-1]
                    for fact in candidates
                    if fact.path.split(".")[-2] == row
                }
                for row in rows
            }
            if len(rows) > 1 and all(
                set(headings) == row_headings for row_headings in headings_by_row.values()
            ):
                table_groups[parent] = candidates
        return table_groups

    @staticmethod
    def _table_block(parent: str, candidates: list[Fact]) -> RenderBlock:
        headings = list(dict.fromkeys(fact.path.split(".")[-1] for fact in candidates))
        row_names = list(dict.fromkeys(fact.path.split(".")[-2] for fact in candidates))
        rows: list[RenderRow] = []
        for row_name in row_names:
            values = [
                str(
                    next(
                        (
                            fact.value
                            for fact in candidates
                            if fact.path.split(".")[-2:] == [row_name, heading]
                        ),
                        "",
                    )
                )
                for heading in headings
            ]
            rows.append({"label": row_name, "values": values})
        lines = [fact.line for fact in candidates]
        return {
            "kind": "table",
            "label": parent.split(".")[-1],
            "value": "",
            "items": [],
            "caption": parent.split(".")[-1],
            "row_heading": humanize_key(parent.split(".")[-1]),
            "headings": headings,
            "rows": rows,
            "definitions": [],
            "source_label": f"{parent} \u00b7 L{min(lines)}\u2013{max(lines)}",
        }

    @staticmethod
    def _definition_groups(
        facts: list[Fact], source_section: str, table_paths: set[str]
    ) -> dict[str, list[Fact]]:
        root_depth = len(source_section.split("."))
        groups: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            if fact.path in table_paths or isinstance(fact.value, list):
                continue
            parts = fact.path.split(".")
            parent = ".".join(parts[:-1])
            if len(parts[:-1]) > root_depth:
                groups[parent].append(fact)
        return dict(groups)

    @staticmethod
    def _definition_block(parent: str, facts: list[Fact]) -> RenderBlock:
        definitions: list[RenderDefinition] = []
        for fact in facts:
            value = "null" if fact.value is None else str(fact.value)
            definitions.append({"label": fact.path.split(".")[-1], "value": value})
        source_labels = [f"{fact.path} \u00b7 L{fact.line}" for fact in facts]
        return {
            "kind": "definition",
            "label": parent.split(".")[-1],
            "value": "",
            "items": [],
            "caption": "",
            "row_heading": "",
            "headings": [],
            "rows": [],
            "definitions": definitions,
            "source_label": "; ".join(source_labels),
        }

    @staticmethod
    def _fact_block(fact: Fact) -> RenderBlock:
        label = fact.path.split(".")[-1]
        if isinstance(fact.value, list):
            return {
                "kind": "list",
                "label": label,
                "value": "",
                "items": [str(item) for item in fact.value],
                "caption": "",
                "row_heading": "",
                "headings": [],
                "rows": [],
                "definitions": [],
                "source_label": f"{fact.path} \u00b7 L{fact.line}",
            }
        value = "null" if fact.value is None else str(fact.value)
        return {
            "kind": "value",
            "label": label,
            "value": value,
            "items": [],
            "caption": "",
            "row_heading": "",
            "headings": [],
            "rows": [],
            "definitions": [],
            "source_label": f"{fact.path} \u00b7 L{fact.line}",
        }

    def _blocks(self, facts: list[Fact], source_section: str) -> list[RenderBlock]:
        table_groups = self._table_groups(facts)
        table_blocks = {
            parent: self._table_block(parent, candidates)
            for parent, candidates in table_groups.items()
        }
        table_paths = {fact.path for candidates in table_groups.values() for fact in candidates}
        definition_groups = self._definition_groups(facts, source_section, table_paths)
        definition_blocks = {
            parent: self._definition_block(parent, candidates)
            for parent, candidates in definition_groups.items()
        }
        parent_by_path = {
            fact.path: parent for parent, candidates in table_groups.items() for fact in candidates
        }
        definition_parent_by_path = {
            fact.path: parent
            for parent, candidates in definition_groups.items()
            for fact in candidates
        }
        blocks: list[RenderBlock] = []
        rendered_tables: set[str] = set()
        rendered_definitions: set[str] = set()
        for fact in facts:
            parent = parent_by_path.get(fact.path)
            if parent is not None and parent not in rendered_tables:
                blocks.append(table_blocks[parent])
                rendered_tables.add(parent)
                continue
            if parent is not None:
                continue
            definition_parent = definition_parent_by_path.get(fact.path)
            if definition_parent is not None:
                if definition_parent not in rendered_definitions:
                    blocks.append(definition_blocks[definition_parent])
                    rendered_definitions.add(definition_parent)
                continue
            blocks.append(self._fact_block(fact))
        return blocks

    def render(
        self, doc: Document, logo: BrandLogo | None = None, show_sources: bool = True
    ) -> str:
        template = self.env.get_template("document.html.j2")
        logo_data = base64.b64encode(logo.content).decode("ascii") if logo else ""
        section_blocks = {
            section.order: self._blocks(section.facts, section.source_section)
            for section in doc.sections
        }
        return template.render(
            document=doc,
            logo=logo,
            logo_data=logo_data,
            show_sources=show_sources,
            section_blocks=section_blocks,
        )
