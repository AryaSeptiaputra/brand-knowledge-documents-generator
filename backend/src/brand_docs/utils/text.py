"""Text conversion helpers shared by services and templates."""


def humanize_key(key: str) -> str:
    """Replace underscores with spaces and capitalize only the first character."""
    value = key.replace("_", " ")
    return value[:1].upper() + value[1:]
