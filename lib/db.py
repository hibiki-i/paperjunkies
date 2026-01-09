from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from supabase import Client


@dataclass(frozen=True)
class Profile:
    id: str
    display_name: str
    citation_style: str
    timezone: str | None


@dataclass(frozen=True)
class Reference:
    id: str
    bibtex_key: str | None
    bibtex_raw: str | None
    csl_json: dict[str, Any] | None
    title: str | None
    abstract: str | None
    authors: str | None
    year: int | None
    venue: str | None
    doi: str | None
    url: str | None
    fingerprint: str


@dataclass(frozen=True)
class TimelinePost:
    id: str
    user_id: str
    reference_id: str
    note: str | None
    read_at: datetime
    display_name: str
    citation_style: str
    reference: Reference


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def fetch_profile(sb: Client, user_id: str) -> Profile | None:
    resp = (
        sb.table("profiles")
        .select("id,display_name,citation_style,timezone")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return Profile(
        id=row["id"],
        display_name=row["display_name"],
        citation_style=row.get("citation_style") or "apa",
        timezone=row.get("timezone"),
    )


def upsert_profile_style(sb: Client, user_id: str, citation_style: str) -> None:
    # Keep it simple: update if exists; otherwise do nothing (profiles are assumed to exist).
    sb.table("profiles").update({"citation_style": citation_style}).eq("id", user_id).execute()


def upsert_profile_display_name(sb: Client, user_id: str, display_name: str) -> None:
    # Keep it simple: update if exists; otherwise do nothing (profiles are assumed to exist).
    sb.table("profiles").update({"display_name": display_name}).eq("id", user_id).execute()


def upsert_profile_timezone(sb: Client, user_id: str, timezone_name: str | None) -> None:
    # Keep it simple: update if exists; otherwise do nothing (profiles are assumed to exist).
    sb.table("profiles").update({"timezone": timezone_name}).eq("id", user_id).execute()


def get_reference_by_fingerprint(sb: Client, fingerprint: str) -> Reference | None:
    resp = (
        sb.table("references")
        .select(
            "id,bibtex_key,bibtex_raw,csl_json,title,abstract,authors,year,venue,doi,url,fingerprint"
        )
        .eq("fingerprint", fingerprint)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    if not data:
        return None
    return _row_to_reference(data[0])


def insert_reference(sb: Client, reference_payload: dict[str, Any]) -> Reference:
    resp = sb.table("references").insert(reference_payload, returning="representation").execute()
    row = _require_single_row(resp.data, context="insert_reference")
    return _row_to_reference(row)


def insert_post(sb: Client, user_id: str, reference_id: str, note: str | None) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "reference_id": reference_id,
        "note": note,
        "read_at": now_utc().isoformat(),
    }
    resp = sb.table("posts").insert(payload, returning="representation").execute()
    row = _require_single_row(resp.data, context="insert_post")
    return row


def fetch_timeline_posts(sb: Client, limit: int = 50) -> list[TimelinePost]:
    posts_resp = (
        sb.table("posts")
        .select("id,user_id,reference_id,note,read_at")
        .order("read_at", desc=True)
        .limit(limit)
        .execute()
    )
    posts = posts_resp.data or []
    if not posts:
        return []

    user_ids = sorted({p["user_id"] for p in posts})
    ref_ids = sorted({p["reference_id"] for p in posts})

    profiles_by_id = _fetch_profiles_by_id(sb, user_ids)
    refs_by_id = _fetch_refs_by_id(sb, ref_ids)

    timeline: list[TimelinePost] = []
    for p in posts:
        profile = profiles_by_id.get(p["user_id"])
        ref = refs_by_id.get(p["reference_id"])
        if not profile or not ref:
            # Skip orphaned rows (shouldn't happen with correct FK constraints).
            continue

        read_at = _parse_dt(p["read_at"])
        timeline.append(
            TimelinePost(
                id=p["id"],
                user_id=p["user_id"],
                reference_id=p["reference_id"],
                note=p.get("note"),
                read_at=read_at,
                display_name=profile.display_name,
                citation_style=profile.citation_style,
                reference=ref,
            )
        )

    return timeline


def fetch_posts_for_dashboard(sb: Client, user_id: str | None) -> list[dict[str, Any]]:
    q = sb.table("posts").select("id,user_id,reference_id,read_at")
    if user_id:
        q = q.eq("user_id", user_id)

    resp = q.order("read_at", desc=False).execute()
    posts = resp.data or []
    if not posts:
        return []

    ref_ids = sorted({p["reference_id"] for p in posts})
    refs_by_id = _fetch_refs_by_id(sb, ref_ids)

    out: list[dict[str, Any]] = []
    for p in posts:
        ref = refs_by_id.get(p["reference_id"])
        if not ref:
            continue
        out.append(
            {
                "post_id": p["id"],
                "user_id": p["user_id"],
                "read_at": _parse_dt(p["read_at"]),
                "title": ref.title or "",
                "abstract": ref.abstract or "",
            }
        )

    return out


def _fetch_profiles_by_id(sb: Client, user_ids: Iterable[str]) -> dict[str, Profile]:
    ids = list(user_ids)
    resp = sb.table("profiles").select("id,display_name,citation_style,timezone").in_("id", ids).execute()
    rows = resp.data or []
    out: dict[str, Profile] = {}
    for r in rows:
        out[r["id"]] = Profile(
            id=r["id"],
            display_name=r["display_name"],
            citation_style=r.get("citation_style") or "apa",
            timezone=r.get("timezone"),
        )
    return out


def _fetch_refs_by_id(sb: Client, ref_ids: Iterable[str]) -> dict[str, Reference]:
    ids = list(ref_ids)
    resp = (
        sb.table("references")
        .select(
            "id,bibtex_key,bibtex_raw,csl_json,title,abstract,authors,year,venue,doi,url,fingerprint"
        )
        .in_("id", ids)
        .execute()
    )
    rows = resp.data or []
    return {r["id"]: _row_to_reference(r) for r in rows}


def _row_to_reference(row: dict[str, Any]) -> Reference:
    return Reference(
        id=row["id"],
        bibtex_key=row.get("bibtex_key"),
        bibtex_raw=row.get("bibtex_raw"),
        csl_json=row.get("csl_json"),
        title=row.get("title"),
        abstract=row.get("abstract"),
        authors=row.get("authors"),
        year=row.get("year"),
        venue=row.get("venue"),
        doi=row.get("doi"),
        url=row.get("url"),
        fingerprint=row["fingerprint"],
    )


def _parse_dt(val: str) -> datetime:
    # Supabase returns ISO timestamps.
    # Python 3.11 handles 'Z' poorly via fromisoformat, so normalize.
    if val.endswith("Z"):
        val = val[:-1] + "+00:00"
    return datetime.fromisoformat(val)


def _require_single_row(data: Any, *, context: str) -> dict[str, Any]:
    if data is None:
        raise RuntimeError(
            f"Supabase returned no data for {context}. "
            "Check RLS policies or PostgREST 'returning' behavior."
        )
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        if len(data) != 1:
            raise RuntimeError(f"Expected 1 row for {context}, got {len(data)}")
        if not isinstance(data[0], dict):
            raise RuntimeError(f"Unexpected row shape for {context}")
        return data[0]
    raise RuntimeError(f"Unexpected response type for {context}: {type(data)!r}")
