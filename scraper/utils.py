def distribute_target(total: int, buckets: int) -> list[int]:
    """Split a target count across search queries without dropping the remainder."""
    if buckets <= 0:
        return []

    base, remainder = divmod(max(0, total), buckets)
    return [base + (1 if index < remainder else 0) for index in range(buckets)]
