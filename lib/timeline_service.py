from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from supabase import Client

from .bibtex_utils import ParsedBibtex
from .db import Reference, get_reference_by_fingerprint, insert_post, insert_reference
from .timezone_utils import get_zoneinfo, to_timezone


def post_read(sb: Client, *, user_id: str, parsed: ParsedBibtex, note: str | None) -> tuple[Reference, dict[str, Any]]:
    """Create a post for a read, inserting/reusing the underlying reference."""

    existing = get_reference_by_fingerprint(sb, parsed.fingerprint)
    if existing is None:
        ref_payload = {
            "bibtex_key": parsed.bibtex_key,
            "bibtex_raw": parsed.bibtex_raw,
            "csl_json": parsed.csl_json,
            "title": parsed.title,
            "abstract": parsed.abstract,
            "authors": parsed.authors,
            "year": parsed.year,
            "venue": parsed.venue,
            "doi": parsed.doi,
            "url": parsed.url,
            "fingerprint": parsed.fingerprint,
        }
        existing = insert_reference(sb, ref_payload)

    post = insert_post(sb, user_id=user_id, reference_id=existing.id, note=note)
    return existing, post


def calculate_streak(dates: list[datetime], timezone_name: str | None) -> int:
    if not dates:
        return 0

    tz = get_zoneinfo(timezone_name)
    now_local = datetime.now(tz)
    today = now_local.date()
    yesterday = today - timedelta(days=1)

    # Convert all dates to local dates, unique, sorted desc
    local_dates = sorted(
        {to_timezone(d, timezone_name).date() for d in dates},
        reverse=True
    )

    if not local_dates:
        return 0

    streak = 0
    # Check if the sequence starts today or yesterday
    if local_dates[0] == today:
        current_check = today
    elif local_dates[0] == yesterday:
        current_check = yesterday
    else:
        # Streak broken
        return 0

    for d in local_dates:
        if d == current_check:
            streak += 1
            current_check -= timedelta(days=1)
        elif d > current_check:
            # Should not happen as we sorted and checked start
            continue
        else:
            # skipped a day
            break

    return streak
