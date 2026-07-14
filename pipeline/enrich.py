"""
3.3 -- Enrichment & joining.

Builds the enriched listing master:
  * review summary join      -- n_reviews, first/last review, span in days;
  * occupancy & revenue      -- Inside Airbnb's OFFICIAL estimates (see note);
  * neighbourhood aggregates -- median price, listing density, avg rating;
  * derived fields           -- host tenure, review frequency, price/bedroom;
  * cross-city union          -- consistent schema across cities.

Occupancy/revenue source (FIX): the 2026 calendar extract has no nightly price
column, so a DIY revenue estimate is not possible from it. Inside Airbnb already
ships `estimated_occupancy_l365d` and `estimated_revenue_l365d` on the listings
table (their own model). We use those as the authoritative measures and keep the
calendar purely for the time-grain availability fact.

Tenure (FIX): tenure is measured from each row's own snapshot date, not a global
constant -- a hardcoded anchor silently biases every tenure value.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# review summary
# ---------------------------------------------------------------------------
def review_summary(reviews: pd.DataFrame) -> pd.DataFrame:
    if reviews is None or reviews.empty:
        return pd.DataFrame(columns=["listing_id", "rev_count", "rev_first",
                                     "rev_last", "rev_span_days"])
    r = reviews.copy()
    r["listing_id"] = pd.to_numeric(r["listing_id"], errors="coerce").astype("Int64")
    r["review_date"] = pd.to_datetime(r["date"], errors="coerce")
    g = r.groupby("listing_id")["review_date"].agg(rev_count="count",
                                                    rev_first="min", rev_last="max")
    g["rev_span_days"] = (g["rev_last"] - g["rev_first"]).dt.days
    return g.reset_index()


# ---------------------------------------------------------------------------
# official occupancy + revenue (Inside Airbnb estimates)
# ---------------------------------------------------------------------------
def coerce_official_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce Inside Airbnb's own occupancy/revenue estimates to numeric IN PLACE.
    These columns already exist on the master (passthrough from clean), so we must
    NOT merge them back in -- that would create *_x/*_y and lose the measures.
    Defensive money parsing in case a snapshot formats revenue with $ or commas."""
    if "estimated_occupancy_l365d" in df.columns:
        df["estimated_occupancy_l365d"] = pd.to_numeric(
            df["estimated_occupancy_l365d"], errors="coerce")
    if "estimated_revenue_l365d" in df.columns:
        df["estimated_revenue_l365d"] = pd.to_numeric(
            df["estimated_revenue_l365d"].astype(str).str.replace(r"[\$,]", "", regex=True),
            errors="coerce")
    return df


# ---------------------------------------------------------------------------
# neighbourhood aggregates
# ---------------------------------------------------------------------------
def neighbourhood_aggregates(listings: pd.DataFrame) -> pd.DataFrame:
    key = ["city_key", "neighbourhood_std"]
    g = listings.groupby(key)
    agg = g.agg(
        nb_listing_count=("id", "count"),
        nb_median_price=("price", "median"),
        nb_avg_rating=("review_scores_rating", "mean"),
        nb_avg_reviews=("number_of_reviews", "mean"),
    ).reset_index()
    city_tot = agg.groupby("city_key")["nb_listing_count"].transform("sum")
    agg["nb_density_pct"] = (agg["nb_listing_count"] / city_tot * 100).round(2)
    agg["nb_median_price"] = agg["nb_median_price"].round(2)
    agg["nb_avg_rating"] = agg["nb_avg_rating"].round(3)
    return agg


# ---------------------------------------------------------------------------
# derived fields
# ---------------------------------------------------------------------------
def add_derived(listings: pd.DataFrame) -> pd.DataFrame:
    df = listings.copy()

    # host tenure in years -- anchored to THIS row's snapshot date (FIX)
    if "host_since" in df.columns and "snapshot_date" in df.columns:
        hs = pd.to_datetime(df["host_since"], errors="coerce")
        anchor = pd.to_datetime(df["snapshot_date"], errors="coerce")
        tenure = (anchor - hs).dt.days / 365.25
        df["host_tenure_years"] = tenure.round(2)
        df.loc[df["host_tenure_years"] < 0, "host_tenure_years"] = np.nan  # guard bad dates

    # review frequency (reviews per active month)
    if {"rev_count", "rev_span_days"}.issubset(df.columns):
        months = (df["rev_span_days"] / 30.44).replace(0, np.nan)
        df["review_frequency_pm"] = (df["rev_count"] / months).round(3)

    # price per bedroom (imputed bedrooms so ratio is defined; source null kept)
    if {"price", "bedrooms_filled"}.issubset(df.columns):
        beds = df["bedrooms_filled"].replace(0, np.nan)
        df["price_per_bedroom"] = (df["price"] / beds).round(2)
    return df


# ---------------------------------------------------------------------------
# master build (per city) + cross-city union
# ---------------------------------------------------------------------------
def build_master(clean_listings: pd.DataFrame,
                 reviews: pd.DataFrame,
                 calendar: pd.DataFrame | None = None) -> pd.DataFrame:
    """calendar is accepted for signature stability but no longer used for
    revenue (official estimates are used instead); it still feeds fact_calendar
    downstream in model.py."""
    master = clean_listings.copy()

    master = master.merge(review_summary(reviews), left_on="id",
                          right_on="listing_id", how="left").drop(
                              columns=["listing_id"], errors="ignore")

    master = coerce_official_performance(master)

    master = add_derived(master)
    nb = neighbourhood_aggregates(master)
    master = master.merge(nb, on=["city_key", "neighbourhood_std"], how="left")
    return master


def unify_cities(masters: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Cross-city master with a consistent column set (3.3 final bullet)."""
    cols = sorted(set().union(*[set(m.columns) for m in masters.values()]))
    aligned = [m.reindex(columns=cols) for m in masters.values()]
    return pd.concat(aligned, ignore_index=True)
