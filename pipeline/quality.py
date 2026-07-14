"""
3.1 -- Data quality assessment.

Four independent checks, each returning a tidy DataFrame so they can be dropped
straight into the report:

  duplicates   -- deterministic (exact-row + primary-key) AND fuzzy (name+geo);
  completeness -- per-field missingness ranked, with a plain-English implication;
  outliers     -- Tukey/IQR fences on the key numeric fields;
  validation   -- domain rules (price>0, valid lat/long, sane minimum_nights).

None of these mutate the data -- they only *document*. Cleaning (3.2) consumes
their verdicts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from config import THRESHOLDS as T

# Natural keys per dataset, used for deterministic key-duplicate detection.
PRIMARY_KEYS = {
    "listings": ["id"],
    "calendar": ["listing_id", "date"],
    "reviews": ["id"],
    "neighbourhoods": ["neighbourhood"],
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def money_to_float(s: pd.Series) -> pd.Series:
    """'$1,234.00' -> 1234.0 ; invalid -> NaN. Used across quality + cleaning."""
    return pd.to_numeric(
        s.astype(str).str.replace(r"[\$,]", "", regex=True).str.strip(),
        errors="coerce")


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


# ---------------------------------------------------------------------------
# duplicates
# ---------------------------------------------------------------------------
def deterministic_duplicates(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    rows = []
    # 1. fully identical rows
    exact = int(df.duplicated(keep="first").sum())
    rows.append({"dataset": dataset, "method": "exact_row",
                 "key": "<all columns>", "duplicate_rows": exact})
    # 2. duplicate primary key
    keys = PRIMARY_KEYS.get(dataset.split(".")[-1])
    if keys and set(keys).issubset(df.columns):
        pk_dupes = int(df.duplicated(subset=keys, keep="first").sum())
        rows.append({"dataset": dataset, "method": "primary_key",
                     "key": "+".join(keys), "duplicate_rows": pk_dupes})
    return pd.DataFrame(rows)


def fuzzy_duplicates(listings: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Near-duplicate listings: same room_type, coordinates within ~50m, and a
    fuzzy name match >= threshold. Blocking on a rounded geo grid keeps this
    O(n) per bucket instead of O(n^2) across the whole frame."""
    if not {"latitude", "longitude", "name", "room_type", "id"}.issubset(listings.columns):
        return pd.DataFrame(columns=["dataset", "id_a", "id_b", "name_a", "name_b", "score"])

    df = listings.copy()
    df["_lat"] = _num(df["latitude"])
    df["_lon"] = _num(df["longitude"])
    df = df.dropna(subset=["_lat", "_lon"])
    step = T.fuzzy_geo_eps
    df["_gy"] = (df["_lat"] / step).round().astype("Int64")
    df["_gx"] = (df["_lon"] / step).round().astype("Int64")

    pairs = []
    for (_, _, rt), grp in df.groupby(["_gy", "_gx", "room_type"], dropna=False):
        if len(grp) < 2:
            continue
        recs = grp[["id", "name"]].to_dict("records")
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                if recs[i]["id"] == recs[j]["id"]:
                    continue  # identical id -> exact dup, handled deterministically
                score = fuzz.token_sort_ratio(str(recs[i]["name"]), str(recs[j]["name"]))
                if score >= T.fuzzy_threshold:
                    pairs.append({"dataset": dataset,
                                  "id_a": recs[i]["id"], "id_b": recs[j]["id"],
                                  "name_a": recs[i]["name"], "name_b": recs[j]["name"],
                                  "score": int(score)})
    return pd.DataFrame(pairs)


# ---------------------------------------------------------------------------
# completeness
# ---------------------------------------------------------------------------
_IMPLICATIONS = {
    "review_scores_rating": "no rating -> listing likely never booked/reviewed; skews quality analysis",
    "reviews_per_month": "absent for zero-review listings; treat as 0 not missing for demand metrics",
    "bedrooms": "missing bedrooms blocks price-per-bedroom derivation (3.3)",
    "beds": "missing beds weakens capacity/occupancy estimates",
    "host_response_rate": "host-behaviour models lose rows; impute or flag",
    "license": "high missingness expected (regulatory) -- keep explicit null, do not impute",
    "price": "missing price is fatal for revenue metrics -- such rows are dropped, not imputed",
    "last_review": "no last_review -> inactive listing; affects occupancy/tenure",
}


def completeness(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    n = len(df)
    miss = df.isna().sum()
    out = (pd.DataFrame({"dataset": dataset, "field": miss.index,
                         "missing": miss.values,
                         "missing_pct": (miss.values / n * 100).round(2)})
           .sort_values("missing_pct", ascending=False))
    out["implication"] = out["field"].map(_IMPLICATIONS).fillna("")
    return out[out["missing"] > 0].reset_index(drop=True)


# ---------------------------------------------------------------------------
# outliers (Tukey / IQR)
# ---------------------------------------------------------------------------
def outliers(listings: pd.DataFrame, dataset: str) -> pd.DataFrame:
    rows = []
    for field in T.outlier_numeric_fields:
        if field not in listings.columns:
            continue
        series = money_to_float(listings[field]) if field == "price" else _num(listings[field])
        series = series.dropna()
        if series.empty:
            continue
        q1, q3 = series.quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - T.iqr_k * iqr, q3 + T.iqr_k * iqr
        mask = (series < lo) | (series > hi)
        rows.append({"dataset": dataset, "field": field,
                     "q1": round(q1, 2), "q3": round(q3, 2),
                     "lower_fence": round(lo, 2), "upper_fence": round(hi, 2),
                     "n_outliers": int(mask.sum()),
                     "outlier_pct": round(mask.mean() * 100, 2),
                     "min": round(series.min(), 2), "max": round(series.max(), 2)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# domain validation
# ---------------------------------------------------------------------------
def validate(listings: pd.DataFrame, dataset: str) -> pd.DataFrame:
    rows = []

    def _rule(name, mask, sample_col="id"):
        n_bad = int(mask.sum())
        sample = (listings.loc[mask, sample_col].astype(str).head(3).tolist()
                  if n_bad and sample_col in listings.columns else [])
        rows.append({"dataset": dataset, "rule": name, "violations": n_bad,
                     "sample_ids": ", ".join(sample)})

    if "price" in listings.columns:
        p = money_to_float(listings["price"])
        _rule("price_present", p.isna())
        _rule("price_gt_0", p.notna() & (p <= T.price_min))
        _rule("price_lt_max", p.notna() & (p > T.price_max))
    if "latitude" in listings.columns:
        lat = _num(listings["latitude"])
        _rule("latitude_in_range", lat.notna() & ((lat < T.lat_min) | (lat > T.lat_max)))
    if "longitude" in listings.columns:
        lon = _num(listings["longitude"])
        _rule("longitude_in_range", lon.notna() & ((lon < T.lon_min) | (lon > T.lon_max)))
    if "minimum_nights" in listings.columns:
        mn = _num(listings["minimum_nights"])
        _rule("minimum_nights_sane", mn.notna() & ((mn < 1) | (mn > T.min_nights_max)))
    return pd.DataFrame(rows)
