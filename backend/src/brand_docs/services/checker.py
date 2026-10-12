"""Check LLM prose against the facts of its section."""

import re
from decimal import Decimal, InvalidOperation

from brand_docs.domain.enums import ParagraphOrigin
from brand_docs.domain.models import CheckResult, Document, Fact, Paragraph, Section
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)
# Splits prose into Unicode words with connectors, such as "Élodie", "J&T", and "24s".
PROPER_TERM_PATTERN = re.compile(r"\b\w+(?:[&.-]\w+)*\b")
# Captures the first token after a sentence boundary for grammatical capitalization checks.
SENTENCE_START_PATTERN = re.compile(r"(?:^|[.!?]\s+)(\w+(?:[&.-]\w+)*)")
# Identifies number shorthand already normalized by the numeric checker, such as "3jt" or "4rb".
NUMBER_UNIT_PATTERN = re.compile(r"\d+(?:[.,]\d+)*(?:ribu|rb|k|juta|jt)", re.IGNORECASE)


class ContentChecker:
    """Drop unsupported model prose and measure its fact coverage."""

    ALLOWED_TERMS: frozenset[str] = frozenset(
        {
            "Anda",
            "Rp",
            "Kebijakan",
            "Panduan",
            "Product",
            "Knowledge",
            "Policy",
            "Guide",
            "dan",
            "Yang",
            "Untuk",
        }
    )

    @staticmethod
    def _format_number(value: str) -> str | None:
        # Finds the optional Indonesian shorthand suffix, such as "rb" or "jt".
        unit_match = re.search(r"(ribu|rb|k|juta|jt)$", value.strip(), re.IGNORECASE)
        unit = unit_match.group(1).lower() if unit_match else ""
        raw_number = value[: unit_match.start()] if unit_match else value
        separators = [char for char in raw_number if char in ".,"]
        if "." in separators and "," in separators:
            # Uses the last separator as decimal only when one or two digits follow it.
            decimal_index = max(raw_number.rfind("."), raw_number.rfind(","))
            decimal_places = len(raw_number) - decimal_index - 1
            decimal_separator = raw_number[decimal_index] if decimal_places in {1, 2} else ""
        elif separators:
            # Treats three-digit groups as thousands; other suffix lengths are decimals.
            # Splits the formatted number into its integer and separator-delimited groups.
            groups = re.split(r"[.,]", raw_number)
            grouped = len(groups) > 1 and all(len(group) == 3 for group in groups[1:])
            decimal_separator = "" if grouped else separators[-1]
        else:
            decimal_separator = ""
        # Removes grouping separators before Decimal parsing.
        cleaned = re.sub(r"[.,]", "", raw_number)
        if decimal_separator:
            decimal_position = raw_number.rfind(decimal_separator)
            # Retains only digits from the integer side of the decimal separator.
            integer_part = re.sub(r"\D", "", raw_number[:decimal_position]) or "0"
            # Retains only digits from the decimal side of the decimal separator.
            decimal_part = re.sub(r"\D", "", raw_number[decimal_position + 1 :])
            cleaned = f"{integer_part}.{decimal_part}"
        try:
            number = Decimal(cleaned)
        except InvalidOperation:
            return None
        multiplier = 1_000_000 if unit in {"juta", "jt"} else 1_000 if unit else 1
        normalized = number * multiplier
        rendered = format(normalized, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return "0" if rendered in {"", "-0"} else rendered

    @staticmethod
    def _numbers_in(text: str) -> set[str]:
        # Removes ordered-list prefixes such as "1. " before comparing cited numbers.
        clean_text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
        # Recognizes signed numbers, ISO dates, ranges, and Indonesian thousand/million units.
        raw_values = re.findall(
            r"(?<![\w.+-])(?:\d{4}-\d{1,2}-\d{1,2}|[+-]?\d+(?:[.,]\d+)*"
            r"(?:\s*(?:ribu|rb|k|juta|jt))?"
            r"(?:\s*(?:-|\u2013|sampai)\s*[+-]?\d+(?:[.,]\d+)*"
            r"(?:\s*(?:ribu|rb|k|juta|jt))?)?)",
            clean_text,
            re.IGNORECASE,
        )
        numbers: set[str] = set()
        for raw in raw_values:
            # Splits dates or ranges so every component is checked independently.
            if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", raw):
                parts = raw.split("-")
            else:
                parts = re.split(
                    r"(?<=\d)\s*(?:-|\u2013|sampai)\s*(?=[+-]?\d)",
                    raw,
                    flags=re.IGNORECASE,
                )
            # Reads optional range units such as "2-3jt" and applies them to both endpoints.
            units = [
                match.group(1)
                if (match := re.search(r"(ribu|rb|k|juta|jt)$", part.strip(), re.IGNORECASE))
                else ""
                for part in parts
            ]
            shared_unit = next((unit for unit in units if unit), "")
            numbers.update(
                normalized
                for part, unit in zip(parts, units, strict=True)
                if (
                    normalized := ContentChecker._format_number(
                        part.strip() if unit or not shared_unit else f"{part.strip()}{shared_unit}"
                    )
                )
                is not None
            )
        return numbers

    @staticmethod
    def _proper_terms_in(text: str) -> set[str]:
        # Only the occurrence at a sentence start is exempt; the same word elsewhere is checked.
        sentence_starts = {match.start(1) for match in SENTENCE_START_PATTERN.finditer(text)}
        terms: set[str] = set()
        for match in PROPER_TERM_PATTERN.finditer(text):
            term = match.group()
            if term in ContentChecker.ALLOWED_TERMS or NUMBER_UNIT_PATTERN.fullmatch(term):
                continue
            is_marked = "&" in term or (
                any(char.isalpha() for char in term) and any(char.isdigit() for char in term)
            )
            is_capitalized = term[0].isupper() and match.start() not in sentence_starts
            if is_marked or is_capitalized:
                terms.add(term)
        return terms

    @staticmethod
    def _extract_source_terms(facts: list[Fact]) -> set[str]:
        terms: set[str] = set()
        for fact in facts:
            for key in fact.path.split("."):
                terms.update(PROPER_TERM_PATTERN.findall(key.replace("_", " ")))
            terms.update(PROPER_TERM_PATTERN.findall(str(fact.value)))
        return terms

    def _verify(self, paragraph: Paragraph, facts: list[Fact], document: Document) -> bool:
        source_paths = {source.fact_path for source in paragraph.sources}
        fact_by_path = {fact.path: fact for fact in facts}
        if not source_paths or not source_paths.issubset(fact_by_path):
            return False
        source_facts = [fact_by_path[path] for path in source_paths]
        allowed_numbers = self._numbers_in(" ".join(str(fact.value) for fact in source_facts))
        paragraph_text = paragraph.text.replace(document.generated_at.date().isoformat(), " ")
        if not self._numbers_in(paragraph_text).issubset(allowed_numbers):
            return False
        allowed_terms = set(ContentChecker.ALLOWED_TERMS)
        # Matches name tokens such as "Kaos-Rimba" and "J&T" for the allow-list.
        allowed_terms.update(PROPER_TERM_PATTERN.findall(document.brand_name))
        # Matches document title tokens such as "Product" and "Knowledge".
        allowed_terms.update(PROPER_TERM_PATTERN.findall(document.title))
        # Adds every cited fact key and value token to the paragraph's permitted terms.
        allowed_terms.update(self._extract_source_terms(source_facts))
        folded_terms = {term.casefold() for term in allowed_terms}
        return all(
            term.casefold() in folded_terms for term in self._proper_terms_in(paragraph_text)
        )

    def check(self, doc: Document, facts: list[Fact]) -> tuple[Document, CheckResult]:
        mapped_paths = {fact.path for section in doc.sections for fact in section.facts}
        llm_paths: set[str] = set()
        replaced: list[str] = []
        sections: list[Section] = []
        for section in doc.sections:
            kept_paragraphs: list[Paragraph] = []
            for paragraph in section.paragraphs:
                is_llm = paragraph.origin == ParagraphOrigin.LLM
                if is_llm and not self._verify(paragraph, section.facts, doc):
                    # Rejected prose is dropped; the template blocks still show every section fact.
                    replaced.append(paragraph.text)
                    continue
                kept_paragraphs.append(paragraph)
                if is_llm:
                    llm_paths.update(source.fact_path for source in paragraph.sources)
            sections.append(section.model_copy(update={"paragraphs": kept_paragraphs}))
        checked = doc.model_copy(update={"sections": sections})
        coverage = (
            len(llm_paths & mapped_paths) / len(mapped_paths) * 100 if mapped_paths else 100.0
        )
        return checked, CheckResult(
            document_type=doc.document_type,
            coverage_percent=round(coverage, 2),
            fabrication_found=bool(replaced),
            replaced_paragraphs=replaced,
            uncovered_facts=[],
        )
