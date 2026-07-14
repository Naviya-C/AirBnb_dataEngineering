"""
3.2 -- Data cleaning & standardisation.
=======================================

Input: the raw all-string listings frame. Output: a typed, standardised frame
PLUS a `rejects` frame holding rows that failed hard validation (documented, not
silently dropped). Design rule: every transformation is explicit and reversible
in intent -- we never let a parser guess.

Missing-value policy (documented per the brief):
  * price          -> row is REJECTED if unparseable/<=0 (revenue metrics depend on it)
  * bedrooms/beds  -> explicit null kept; a `*_imputed` flag column records median fill
                      used only for derived ratios, never overwriting the source null
  * reviews_per_month -> 0 (a genuine zero for never-reviewed listings, not "unknown")
  * license        -> explicit null (regulatory absence is meaningful; do NOT impute)
  * host_is_superhost / verified -> 't'/'f' -> boolean; null -> False with a flag
  
  
  Its main goals are:

        Convert everything from strings into proper data types.
        Standardize inconsistent values.
        Handle missing values in a documented way.
        Reject rows with critical errors instead of silently dropping them.
        Preserve the original information wherever possible.

        This is the Transform (T) stage in an ETL pipeline.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from config import CANONICAL_ROOM_TYPES, THRESHOLDS as T
from pipeline.quality import money_to_float

_WS = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# field-level standardisers
# ---------------------------------------------------------------------------
def std_price(s: pd.Series) -> pd.Series:
    """Strip $ and thousands separators, cast to float."""
    return money_to_float(s)


def std_dates(s: pd.Series) -> pd.Series:
    """Parse mixed formats ('2021-07-01', '2012/08/09') to a single date dtype."""
    return pd.to_datetime(s.astype(str).str.replace("/", "-", regex=False),
                          errors="coerce", format="mixed").dt.date


def std_percent(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.rstrip("%"), errors="coerce") / 100.0


def std_bool(s: pd.Series) -> pd.Series:
    m = s.astype(str).str.strip().str.lower().map({"t": True, "true": True,
                                                   "f": False, "false": False})
    return m  

def norm_room_type(s: pd.Series) -> pd.Series:
    key = s.astype(str).str.strip().str.lower()
    return key.map(CANONICAL_ROOM_TYPES).fillna(s.str.strip())


def norm_property_type(s: pd.Series) -> pd.Series:
    """Collapse messy free-text into a small consistent vocabulary.
    'Entire  rental  unit' / 'entire rental unit' -> 'Entire rental unit', and
    everything is bucketed into a coarse family for analytics."""
    cleaned = (s.astype(str).str.strip().str.replace(_WS, " ", regex=True)
               .str.replace("condominium", "condo", case=False, regex=False))
    cleaned = cleaned.str.replace(r"\b(\w)", lambda m: m.group(1).upper(), regex=True)

    def family(v: str) -> str:
        v = v.lower()
        if v.startswith("entire"):
            return "Entire place"
        if v.startswith("private room"):
            return "Private room"
        if v.startswith("shared room"):
            return "Shared room"
        if "hotel" in v or "hostel" in v:
            return "Hotel/Hostel"
        return "Other"

    return pd.DataFrame({"property_type_clean": cleaned,
                         "property_family": cleaned.map(family)})


def std_geo(df: pd.DataFrame) -> pd.DataFrame:
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce").round(T.coord_precision)
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce").round(T.coord_precision)
    # neighbourhood: strip trailing ", City" noise, collapse whitespace, title-case
    if "neighbourhood_cleansed" in df.columns:
        df["neighbourhood_std"] = (df["neighbourhood_cleansed"].astype(str)
                                   .str.split(",").str[0].str.strip()
                                   .str.replace(_WS, " ", regex=True))
    return df


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def clean_listings(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()

    # --- identity keys as integers (consistent join keys everywhere) ------
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    if "host_id" in df.columns:
        df["host_id"] = pd.to_numeric(df["host_id"], errors="coerce").astype("Int64")

    # --- numeric / typed casts -------------------------------------------
    df["price"] = std_price(df["price"])
    #print(df["price"].head(20)) // use for debug
    
    integer_cols = (
        "accommodates", 
        "bedrooms", 
        "beds", 
        "minimum_nights", 
        "maximum_nights",
        
        "number_of_reviews",
        "number_of_reviews_l30d",
        "number_of_reviews_ltm",
        "number_of_reviews_ly",
        "review_scores_accuracy",
        "review_scores_checkin",
        "review_scores_cleanliness",
        "review_scores_communication",
        "review_scores_location",
        "review_scores_value",
        
        "availability_30",
        "availability_60",
        "availability_90",
        "availability_365", 
        "availability_eoy",
        
        "host_listings_count",
        "host_total_listings_count",
        "calculated_host_listings_count",
        "calculated_host_listings_count_entire_homes",
        "calculated_host_listings_count_private_rooms",
        "calculated_host_listings_count_shared_rooms",
        
        "estimated_occupancy_l365d",
        "estimated_revenue_l365d",
        
        "maximum_maximum_nights",
        "maximum_nights_avg_ntm",
        "minimum_maximum_nights",
        "minimum_minimum_nights",
        "minimum_nights_avg_ntm",
        
        "price_quote_price_per_night",
        "price_quote_total_price",
    )
    
    
    
    for c in integer_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "reviews_per_month" in df.columns:
        df["reviews_per_month"] = pd.to_numeric(df["reviews_per_month"],
                                                errors="coerce").fillna(0.0)
    if "review_scores_rating" in df.columns:
        df["review_scores_rating"] = pd.to_numeric(df["review_scores_rating"], errors="coerce")
    if "host_response_rate" in df.columns:
        df["host_response_rate"] = std_percent(df["host_response_rate"])

    # --- dates ------------------------------------------------------------
    for c in ("host_since", "first_review", "last_review", "last_scraped"):
        if c in df.columns:
            df[c] = std_dates(df[c])

    # --- booleans ---------------------------------------------------------
    for c in ("host_is_superhost", "host_identity_verified"):
        if c in df.columns:
            df[c + "_missing"] = df[c].isna()
            df[c] = std_bool(df[c]).fillna(False)

    # --- categoricals -----------------------------------------------------
    if "room_type" in df.columns:
        df["room_type"] = norm_room_type(df["room_type"])
    if "property_type" in df.columns:
        pt = norm_property_type(df["property_type"])
        df["property_type_clean"] = pt["property_type_clean"]
        df["property_family"] = pt["property_family"]

    # --- geo --------------------------------------------------------------
    df = std_geo(df)

    # --- imputation flags (never overwrite source nulls) ------------------
    for c in ("bedrooms", "beds"):
        if c in df.columns:
            med = df[c].median()
            df[c + "_imputed"] = df[c].isna()
            df[c + "_filled"] = df[c].fillna(med)

    # --- validation gate: split clean vs rejects --------------------------
    lat, lon, price = df["latitude"], df["longitude"], df["price"]
    reason = pd.Series("", index=df.index)
    reason = reason.mask(price <= T.price_min, reason + "bad_price;")
    reason = reason.mask(price > T.price_max, reason + "price_over_max;")
    reason = reason.mask(lat.isna() | (lat < T.lat_min) | (lat > T.lat_max),
                         reason + "bad_latitude;")
    reason = reason.mask(lon.isna() | (lon < T.lon_min) | (lon > T.lon_max),
                         reason + "bad_longitude;")

    bad = reason != ""
    rejects = df[bad].copy()
    rejects["reject_reason"] = reason[bad]
    clean = df[~bad].copy()

    # deterministic dedup on primary key, keeping first occurrence
    before = len(clean)
    clean = clean.drop_duplicates(subset=["id"], keep="first")
    clean.attrs["pk_duplicates_removed"] = before - len(clean)

    return clean, rejects


def clean_calendar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = std_dates(df["date"])
    df["available"] = std_bool(df["available"])
    for c in ("price", "adjusted_price"):
        if c in df.columns:
            df[c] = std_price(df[c])
    for c in ("minimum_nights", "maximum_nights", "listing_id"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["listing_id", "date"])
