from __future__ import annotations

import re

try:  # optional dependency; declared in pyproject.toml
    from pylatexenc.latex2text import LatexNodes2Text

    _LATEX_TO_TEXT = LatexNodes2Text()
except Exception:  # pragma: no cover
    _LATEX_TO_TEXT = None

from .db import Reference


def format_citation(ref: Reference, style: str) -> str:
    """Format a reference as a simple human-readable citation.

    This is intentionally lightweight (no CSL engine). It supports a basic APA-like
    rendering by default.
    """

    style = (style or "apa").strip().lower()

    year = str(ref.year) if ref.year else "n.d."
    title = _clean_bibtex_text(ref.title or "")
    venue = _clean_bibtex_text(ref.venue or "")
    link = _doi_url(ref.doi, ref.url)

    if style == "mla":
        authors = _clean_bibtex_text(ref.authors or "")
        parts = []
        if authors:
            parts.append(f"{authors}.")
        if title:
            parts.append(f"\"{title}.\"")
        if venue:
            parts.append(f"{venue},")
        parts.append(f"{year}.")
        if link:
            parts.append(link)
        return " ".join(p for p in parts if p)

    if style == "chicago":
        authors = _clean_bibtex_text(ref.authors or "")
        parts = []
        if authors:
            parts.append(f"{authors}.")
        if title:
            parts.append(f"{title}.")
        if venue:
            parts.append(f"{venue}.")
        parts.append(f"{year}.")
        if link:
            parts.append(link)
        return " ".join(p for p in parts if p)

    # default: APA-like
    authors = _format_authors_apa(ref.authors or "")
    parts: list[str] = []
    if authors:
        parts.append(authors)
    parts.append(f"({year}).")
    if title:
        parts.append(f"{title}.")
    if venue:
        parts.append(f"{venue}.")
    if link:
        parts.append(link)
    return " ".join(p for p in parts if p)


def _doi_url(doi: str | None, url: str | None) -> str:
    if doi and doi.strip():
        d = doi.strip()
        d = d.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
        return f"https://doi.org/{d}"
    if url and url.strip():
        return url.strip()
    return ""


def _format_authors_apa(authors_raw: str) -> str:
    authors_raw = _clean_bibtex_text(authors_raw)
    # BibTeX authors commonly: "First Last and Second Last and ..."
    authors = [a.strip() for a in re.split(r"\s+and\s+", authors_raw) if a.strip()]
    if not authors:
        return ""

    formatted = [_name_last_first_initials(a) for a in authors]

    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} & {formatted[1]}"

    return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"


def _name_last_first_initials(name: str) -> str:
    # Handles "Last, First Middle" and "First Middle Last".
    if "," in name:
        last, rest = [p.strip() for p in name.split(",", 1)]
        initials = _initials(rest)
        return f"{last}, {initials}".strip().rstrip(",")

    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if len(parts) == 1:
        return parts[0]

    last = parts[-1]
    firsts = " ".join(parts[:-1])
    return f"{last}, {_initials(firsts)}".strip().rstrip(",")


def _initials(given: str) -> str:
    parts = [p for p in re.split(r"\s+", given.strip()) if p]
    initials = []
    for p in parts:
        if p:
            initials.append(p[0].upper() + ".")
    return " ".join(initials)


def _clean_bibtex_text(s: str) -> str:
    """Convert BibTeX/LaTeX-ish strings into readable Unicode.

    - Strips BibTeX braces used for capitalization (e.g. {ENGAGE}).
    - Converts common TeX accents, including shorthand like "'{e}".
    """

    s = (s or "").strip()
    if not s:
        return ""

    # Some BibTeX strings use accent shorthand without a leading backslash (e.g., Tass'{e}).
    # Normalize those into valid TeX accents before decoding.
    s = re.sub(r"(?<!\\)(['\"`\^~=.Hcuv])\{", r"\\\1{", s)

    if _LATEX_TO_TEXT is not None:
        try:
            s = _LATEX_TO_TEXT.latex_to_text(s)
        except Exception:  # pragma: no cover
            pass

    # Remove remaining BibTeX braces (commonly used to preserve capitalization).
    s = s.replace("{", "").replace("}", "")

    # Normalize whitespace.
    s = re.sub(r"\s+", " ", s).strip()
    return s
