from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer


@dataclass(frozen=True)
class SemanticTrendsResult:
    data: pd.DataFrame  # columns: period, term, count


@dataclass(frozen=True)
class TimeOfDayResult:
    data: pd.DataFrame  # columns: group, hour


def compute_semantic_trends(
    posts: list[dict],
    *,
    time_grain: str,
    timezone: str = "UTC",
    top_k_terms: int = 12,
    min_term_total: int = 2,
) -> SemanticTrendsResult:
    """Aggregate term usage over time from title+abstract.

    time_grain: 'weekly' | 'monthly'
    """

    df = _posts_to_df(posts, timezone=timezone)
    if df.empty:
        return SemanticTrendsResult(data=pd.DataFrame(columns=["period", "term", "count"]))

    df["text"] = (df["title"].fillna("") + " " + df["abstract"].fillna("")).str.strip()
    df = df[df["text"].str.len() > 0]
    if df.empty:
        return SemanticTrendsResult(data=pd.DataFrame(columns=["period", "term", "count"]))

    df["period"] = df["read_at"].apply(lambda d: _period_start(d, time_grain))

    grouped = df.groupby("period", as_index=False)["text"].apply(lambda s: " \n ".join(s.tolist()))

    vectorizer = CountVectorizer(stop_words="english", max_features=2000)
    X = vectorizer.fit_transform(grouped["text"].tolist())

    terms = np.array(vectorizer.get_feature_names_out())
    counts_by_period = X.toarray()  # small enough for typical personal/team timelines

    term_totals = counts_by_period.sum(axis=0)
    keep_mask = term_totals >= min_term_total
    terms = terms[keep_mask]
    counts_by_period = counts_by_period[:, keep_mask]

    if terms.size == 0:
        return SemanticTrendsResult(data=pd.DataFrame(columns=["period", "term", "count"]))

    # select top_k terms overall
    top_idx = np.argsort(counts_by_period.sum(axis=0))[::-1][:top_k_terms]
    terms = terms[top_idx]
    counts_by_period = counts_by_period[:, top_idx]

    long_rows = []
    for i, period in enumerate(grouped["period"].tolist()):
        for j, term in enumerate(terms.tolist()):
            c = int(counts_by_period[i, j])
            if c:
                long_rows.append({"period": period, "term": term, "count": c})

    out = pd.DataFrame(long_rows)
    if out.empty:
        out = pd.DataFrame(columns=["period", "term", "count"])

    return SemanticTrendsResult(data=out)


def compute_time_of_day(posts: list[dict], *, group_by: str, timezone: str = "UTC") -> TimeOfDayResult:
    """Prepare hour-of-day distributions.

    group_by: 'daily' | 'weekly' | 'monthly' | 'yearly'
    """

    df = _posts_to_df(posts, timezone=timezone)
    if df.empty:
        return TimeOfDayResult(data=pd.DataFrame(columns=["group", "hour"]))

    df["hour"] = df["read_at"].dt.hour
    df["group"] = df["read_at"].apply(lambda d: _group_label(d, group_by))

    out = df[["group", "hour"]].copy()
    return TimeOfDayResult(data=out)


def _posts_to_df(posts: list[dict], *, timezone: str) -> pd.DataFrame:
    if not posts:
        return pd.DataFrame(columns=["read_at", "title", "abstract"])  # type: ignore[return-value]

    df = pd.DataFrame(posts)
    if "read_at" in df.columns:
        read_at = pd.to_datetime(df["read_at"], utc=True)
        try:
            read_at = read_at.dt.tz_convert(timezone)
        except Exception:
            # Invalid/unknown tz name -> keep UTC.
            pass
        df["read_at"] = read_at
    else:
        df["read_at"] = pd.NaT

    df["title"] = df.get("title", "")
    df["abstract"] = df.get("abstract", "")

    df = df.dropna(subset=["read_at"])
    return df


def _period_start(dt: datetime, grain: str) -> datetime:
    d = dt
    if grain == "weekly":
        # Monday-start week
        start = (d - pd.to_timedelta(d.weekday(), unit="D")).normalize()
        return start.to_pydatetime()
    if grain == "monthly":
        start = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start
    raise ValueError("time_grain must be 'weekly' or 'monthly'")


def _group_label(dt: datetime, group_by: str) -> str:
    if group_by == "daily":
        return dt.date().isoformat()
    if group_by == "weekly":
        start = _period_start(dt, "weekly")
        return start.date().isoformat()
    if group_by == "monthly":
        return f"{dt.year:04d}-{dt.month:02d}"
    if group_by == "yearly":
        return f"{dt.year:04d}"
    raise ValueError("group_by must be 'daily', 'weekly', 'monthly', or 'yearly'")
