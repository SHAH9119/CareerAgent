def distribute_target(total: int, buckets: int) -> list[int]:
    """Split a target count across search queries without dropping the remainder."""
    if buckets <= 0:
        return []

    base, remainder = divmod(max(0, total), buckets)
    return [base + (1 if index < remainder else 0) for index in range(buckets)]


def clean_strings(values) -> list[str]:
    """Return non-empty strings from messy LLM/API lists."""
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]

    cleaned: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned


def safe_join(values, sep: str = ", ") -> str:
    return sep.join(clean_strings(values))
