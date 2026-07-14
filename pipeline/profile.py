"""
3.1 -- Dataset profiling.

Everything arrives as string (see ingest._read_csv), so profiling infers a *likely*
semantic type per column rather than trusting pandas dtypes. For each column we
report: non-null count, null count & rate, distinct count, cardinality ratio,
inferred type, and a few example values. Table-level we report row/col counts and
a flag summary (constant columns, high-null columns, likely-id columns).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import pandas as pd

from config import THRESHOLDS as T

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?$")
_MONEY_RE = re.compile(r"^\$?-?[\d,]+(\.\d+)?$")
_BOOL_VALS = {"t", "f", "true", "false"}
_DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def _infer_type(s: pd.Series) -> str:
    vals = s.dropna().astype(str).str.strip()
    if vals.empty:
        return "empty"
    sample = vals.head(1000)
    if sample.str.lower().isin(_BOOL_VALS).mean() > 0.95:
        return "boolean"
    if sample.str.match(_INT_RE).mean() > 0.95:
        return "integer"
    if sample.str.match(_MONEY_RE).mean() > 0.95 and sample.str.contains(r"[\$,]").any():
        return "money"
    if sample.str.match(_FLOAT_RE).mean() > 0.95:
        return "float"
    if sample.str.match(_DATE_RE).mean() > 0.90:
        return "date"
    if sample.str.endswith("%").mean() > 0.90:
        return "percent"
    return "string"


@dataclass
class ColumnProfile:
    column: str
    inferred_type: str
    non_null: int
    nulls: int
    null_pct: float
    distinct: int
    cardinality_ratio: float
    examples: str
    flags: str


def profile_frame(df: pd.DataFrame, *, name: str) -> pd.DataFrame:
    n = len(df)
    records: list[dict] = []
    for col in df.columns:
        s = df[col]
        non_null = int(s.notna().sum())
        nulls = n - non_null
        distinct = int(s.nunique(dropna=True))
        card_ratio = round(distinct / n, 4) if n else 0.0
        itype = _infer_type(s)

        flags = []
        if non_null and distinct <= T.constant_col_max_distinct:
            flags.append("constant")
        if nulls / n * 100 >= T.high_null_pct if n else False:
            flags.append("high_null")
        if card_ratio >= T.high_cardinality_ratio and itype in ("string", "integer"):
            flags.append("likely_id_or_freetext")

        examples = ", ".join(map(str, s.dropna().astype(str).head(3).tolist()))[:80]
        records.append(asdict(ColumnProfile(
            column=col, inferred_type=itype, non_null=non_null, nulls=nulls,
            null_pct=round(nulls / n * 100, 2) if n else 0.0,
            distinct=distinct, cardinality_ratio=card_ratio,
            examples=examples, flags="|".join(flags))))
    out = pd.DataFrame(records)
    out.insert(0, "dataset", name)
    return out


def profile_all(frames_by_city: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Profile every (city, dataset) frame and stack the results."""
    parts = []
    for city, frames in frames_by_city.items():
        for logical, df in frames.items():
            p = profile_frame(df, name=f"{city}.{logical}")
            parts.append(p)
    return pd.concat(parts, ignore_index=True)


def type_distribution(profile: pd.DataFrame) -> pd.DataFrame:
    """Data-type distribution across all profiled columns (brief 3.1)."""
    return (profile.groupby(["dataset", "inferred_type"]).size()
            .rename("n_columns").reset_index()
            .sort_values(["dataset", "n_columns"], ascending=[True, False]))
