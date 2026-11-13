"""UTC replay timing with exact nanosecond arithmetic; no source log parsing."""

import re
from datetime import UTC, datetime, timedelta

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?Z$")


def timestamp_ns(value):
    match = PATTERN.fullmatch(value)
    if not match:
        raise ValueError("invalid_replay_timestamp")
    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    delta = datetime(year, month, day, hour, minute, second, tzinfo=UTC) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000 + int(
        (match[7] or "").ljust(9, "0")
    )


def timestamp_text(value):
    seconds, fraction = divmod(value, 1_000_000_000)
    date = EPOCH + timedelta(seconds=seconds)
    return f"{date.year:04d}-{date.month:02d}-{date.day:02d}T{date.hour:02d}:{date.minute:02d}:{date.second:02d}.{fraction:09d}Z"
