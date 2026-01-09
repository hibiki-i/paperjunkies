from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import bibtexparser


@dataclass(frozen=True)
class ParsedBibtex:
    bibtex_key: str | None
    bibtex_raw: str
    title: str
    abstract: str
    authors: str | None
    year: int | None
    venue: str | None
    doi: str | None
    url: str | None
    csl_json: dict[str, Any]
    fingerprint: str


def parse_bibtex_entry(bibtex_raw: str) -> ParsedBibtex:
    bibtex_raw = (bibtex_raw or "").strip()
    if not bibtex_raw:
        raise ValueError("BibTeX is empty")

    try:
        # bibtexparser v2 exposes parse_string(); v1 uses loads() + BibTexParser.
        if hasattr(bibtexparser, "parse_string"):
            lib = bibtexparser.parse_string(bibtex_raw)
            entries = getattr(lib, "entries", None) or []
        else:
            parser = bibtexparser.bparser.BibTexParser(common_strings=True)
            if hasattr(parser, "ignore_nonstandard_types"):
                parser.ignore_nonstandard_types = False
            lib = bibtexparser.loads(bibtex_raw, parser=parser)
            entries = getattr(lib, "entries", None) or []
    except Exception as e:  # pragma: no cover
        raise ValueError(f"Invalid BibTeX: {e}") from e

    if not entries:
        raise ValueError("No BibTeX entries found")
    if len(entries) != 1:
        raise ValueError("Please paste exactly one BibTeX entry")

    entry = entries[0]

    title = _get_required(entry, "title")
    abstract = _get_required(entry, "abstract")

    authors = _get_optional(entry, "author")
    year = _parse_year(_get_optional(entry, "year"))

    # Venue is often journal or booktitle
    venue = _get_optional(entry, "journal") or _get_optional(entry, "booktitle")

    doi = _get_optional(entry, "doi")
    url = _get_optional(entry, "url")

    bibtex_key = getattr(entry, "key", None) or entry.get("ID") or entry.get("id")

    fingerprint = compute_fingerprint(title=title, year=year, doi=doi)

    csl_json = bibtex_to_csl_json(
        title=title,
        abstract=abstract,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        url=url,
    )

    return ParsedBibtex(
        bibtex_key=bibtex_key,
        bibtex_raw=bibtex_raw,
        title=title,
        abstract=abstract,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        url=url,
        csl_json=csl_json,
        fingerprint=fingerprint,
    )


def compute_fingerprint(*, title: str, year: int | None, doi: str | None) -> str:
    norm_title = _normalize_text(title)
    norm_year = str(year or "")
    norm_doi = _normalize_doi(doi)

    base = "|".join([norm_title, norm_year, norm_doi]).encode("utf-8")
    return hashlib.sha256(base).hexdigest()


def bibtex_to_csl_json(
    *,
    title: str,
    abstract: str,
    authors: str | None,
    year: int | None,
    venue: str | None,
    doi: str | None,
    url: str | None,
) -> dict[str, Any]:
    issued: dict[str, Any] | None = None
    if year:
        issued = {"date-parts": [[year]]}

    author_list = []
    for a in _split_bibtex_authors(authors or ""):
        parsed = _parse_author(a)
        if parsed:
            author_list.append(parsed)

    csl: dict[str, Any] = {
        "type": "article-journal" if venue else "article",
        "title": title,
        "abstract": abstract,
    }
    if author_list:
        csl["author"] = author_list
    if issued:
        csl["issued"] = issued
    if venue:
        csl["container-title"] = venue
    if doi:
        csl["DOI"] = doi.strip()
    if url:
        csl["URL"] = url.strip()

    return csl


def _get_required(entry: Any, key: str) -> str:
    v = _get_optional(entry, key)
    if not v:
        raise ValueError(f"BibTeX must include '{key}'")
    return v


def _get_optional(entry: Any, key: str) -> str | None:
    # bibtexparser v2 entries behave like dicts
    v = entry.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_year(val: str | None) -> int | None:
    if not val:
        return None
    m = re.search(r"\d{4}", val)
    return int(m.group(0)) if m else None


def _normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return s


def _normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    d = doi.strip().lower()
    d = d.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
    return d


def _split_bibtex_authors(authors: str) -> list[str]:
    authors = authors.strip()
    if not authors:
        return []
    return [a.strip() for a in re.split(r"\s+and\s+", authors) if a.strip()]


def _parse_author(a: str) -> dict[str, str] | None:
    # Return CSL name object.
    a = a.strip()
    if not a:
        return None
    if "," in a:
        family, given = [p.strip() for p in a.split(",", 1)]
        out = {"family": family}
        if given:
            out["given"] = given
        return out

    parts = [p for p in re.split(r"\s+", a) if p]
    if len(parts) == 1:
        return {"literal": parts[0]}
    return {"given": " ".join(parts[:-1]), "family": parts[-1]}
