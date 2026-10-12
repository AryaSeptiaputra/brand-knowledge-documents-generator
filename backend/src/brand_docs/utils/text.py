"""Text conversion helpers shared by services and templates."""

from brand_docs.domain.models import Fact


def humanize_key(key: str) -> str:
    """Replace underscores with spaces and capitalize only the first character."""
    value = key.replace("_", " ")
    return value[:1].upper() + value[1:]


def format_fact_sentence(fact: Fact) -> str:
    """Format a fact as a safe, directly sourced sentence."""
    label = humanize_key(fact.path.split(".")[-1])
    if fact.value is None:
        value = "null"
    elif isinstance(fact.value, list):
        value = ", ".join(str(item) for item in fact.value)
    else:
        value = str(fact.value)
    punctuation = "" if value.endswith((".", "!", "?")) else "."
    return f"{label}: {value}{punctuation}"
