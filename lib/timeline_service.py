from __future__ import annotations

from typing import Any

from supabase import Client

from .bibtex_utils import ParsedBibtex
from .db import Reference, get_reference_by_fingerprint, insert_post, insert_reference


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
