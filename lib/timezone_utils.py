from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "UTC"


def normalize_timezone_name(tz_name: str | None) -> str:
    tz_name = (tz_name or "").strip()
    return tz_name or DEFAULT_TIMEZONE


def get_zoneinfo(tz_name: str | None) -> ZoneInfo:
    name = normalize_timezone_name(tz_name)
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_timezone(dt: datetime, tz_name: str | None) -> datetime:
    zone = get_zoneinfo(tz_name)
    return as_utc(dt).astimezone(zone)


def format_in_timezone(dt: datetime, tz_name: str | None, *, fmt: str = "%Y-%m-%d %H:%M") -> str:
    local = to_timezone(dt, tz_name)
    tz_label = local.tzname() or normalize_timezone_name(tz_name)
    return f"{local.strftime(fmt)} {tz_label}"
