"""
3.4 -- Build the star schema in DuckDB.

Takes the unified cross-city master, the cleaned calendar, and the raw reviews and:
  1. derives conformed dimensions with integer surrogate keys,
  2. attaches those keys back onto the facts,
  3. creates the schema from sql/schema.sql (PK/FK constraints and all),
  4. bulk-inserts every table via DuckDB's zero-copy pandas registration.

FIXES vs previous version:
  * date_key is computed VECTORISED (year*10000+month*100+day) instead of a
    per-row pd.to_datetime .map() -- the latter is unusable on the 14M-row
    calendar and 1.4M-row reviews.
  * fact_review no longer re-merges city_key (reviews already carry it from
    ingest); the old merge produced city_key_x/_y and then KeyError'd.
  * fact_listing now carries the OFFICIAL occupancy/revenue estimates and the
    six review sub-scores.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from config import CITIES, REVIEW_SUBSCORES, ROOT, WAREHOUSE

SCHEMA_SQL = ROOT / "sql" / "schema.sql"


def _date_key_series(s: pd.Series) -> pd.Series:
    """Vectorised yyyymmdd integer key; NaT -> <NA>. Fast on millions of rows."""
    dt = pd.to_datetime(s, errors="coerce")
    key = dt.dt.year * 10000 + dt.dt.month * 100 + dt.dt.day
    return key.astype("Int64")


def _slug_parts() -> dict[str, tuple[str, str]]:
    parts = {}
    for c in CITIES:
        seg = c.slug.split("/")
        parts[c.key] = (seg[0].replace("-", " ").title(), seg[1].replace("-", " ").title())
    return parts


def build_dimensions(master: pd.DataFrame, calendar: pd.DataFrame, review: pd.DataFrame):
    parts = _slug_parts()

    dim_city = pd.DataFrame([
        {"city_key": c.key, "display_name": c.display,
         "country": parts[c.key][0], "region": parts[c.key][1]}
        for c in CITIES if c.key in master["city_key"].unique()])

    # dim_host (SCD-1): one row per natural host_id
    host_cols = ["host_id", "host_name", "host_since", "host_is_superhost",
                 "host_identity_verified", "host_listings_count", "host_tenure_years"]
    dim_host = master[host_cols].drop_duplicates("host_id").reset_index(drop=True)
    dim_host.insert(0, "host_sk", np.arange(1, len(dim_host) + 1))

    # dim_neighbourhood (aggregates pre-joined)
    nb_cols = ["city_key", "neighbourhood_std", "nb_listing_count",
               "nb_median_price", "nb_avg_rating", "nb_density_pct"]
    dim_nb = (master[nb_cols].drop_duplicates(["city_key", "neighbourhood_std"])
              .reset_index(drop=True).rename(columns={"neighbourhood_std": "neighbourhood"}))
    dim_nb.insert(0, "neighbourhood_sk", np.arange(1, len(dim_nb) + 1))

    # dim_property
    dim_prop = (master[["property_type_clean", "property_family"]]
                .drop_duplicates().reset_index(drop=True))
    dim_prop.insert(0, "property_sk", np.arange(1, len(dim_prop) + 1))

    # dim_room_type
    dim_rt = master[["room_type"]].drop_duplicates().reset_index(drop=True)
    dim_rt.insert(0, "room_type_sk", np.arange(1, len(dim_rt) + 1))

    # dim_date: union of snapshot + calendar + review dates
    dates = pd.Index(master["snapshot_date"].dropna().unique())
    if calendar is not None and not calendar.empty:
        dates = dates.union(pd.Index(calendar["date"].dropna().astype(str).unique()))
    if review is not None and not review.empty:
        dates = dates.union(pd.Index(review["date"].dropna().astype(str).unique()))
    dd = pd.to_datetime(pd.Series(dates), errors="coerce").dropna().drop_duplicates()
    dim_date = pd.DataFrame({
        "date_key": (dd.dt.year * 10000 + dd.dt.month * 100 + dd.dt.day).astype(int),
        "date": dd.dt.date, "year": dd.dt.year, "quarter": dd.dt.quarter,
        "month": dd.dt.month, "day": dd.dt.day}).reset_index(drop=True)

    return dict(dim_city=dim_city, dim_host=dim_host, dim_neighbourhood=dim_nb,
                dim_property=dim_prop, dim_room_type=dim_rt, dim_date=dim_date)


def build_facts(master: pd.DataFrame, calendar: pd.DataFrame,
                reviews: pd.DataFrame, dims: dict):
    m = master.copy()
    m["snapshot_date_key"] = _date_key_series(m["snapshot_date"])

    m = m.merge(dims["dim_host"][["host_sk", "host_id"]], on="host_id", how="left")
    m = m.merge(dims["dim_neighbourhood"][["neighbourhood_sk", "city_key", "neighbourhood"]]
                .rename(columns={"neighbourhood": "neighbourhood_std"}),
                on=["city_key", "neighbourhood_std"], how="left")
    m = m.merge(dims["dim_property"], on=["property_type_clean", "property_family"], how="left")
    m = m.merge(dims["dim_room_type"], on="room_type", how="left")

    fact_listing = {
        "listing_id": m["id"], "snapshot_date_key": m["snapshot_date_key"],
        "city_key": m["city_key"], "host_sk": m["host_sk"],
        "neighbourhood_sk": m["neighbourhood_sk"], "property_sk": m["property_sk"],
        "room_type_sk": m["room_type_sk"], "price": m["price"],
        "price_per_bedroom": m.get("price_per_bedroom"),
        "accommodates": m.get("accommodates"), "minimum_nights": m.get("minimum_nights"),
        "number_of_reviews": m.get("number_of_reviews"),
        "reviews_per_month": m.get("reviews_per_month"),
        "review_scores_rating": m.get("review_scores_rating"),
        "availability_365": m.get("availability_365"),
        # official Inside Airbnb performance estimates
        "estimated_occupancy_l365d": m.get("estimated_occupancy_l365d"),
        "estimated_revenue_l365d": m.get("estimated_revenue_l365d"),
        "review_frequency_pm": m.get("review_frequency_pm"),
    }
    for c in REVIEW_SUBSCORES:                     # six sub-scores
        fact_listing[c] = m.get(c)
    fact_listing = pd.DataFrame(fact_listing).drop_duplicates(
        subset=["listing_id", "snapshot_date_key"])

    # ---- fact_calendar (time grain) -------------------------------------
    if calendar is None or calendar.empty:
        fact_calendar = pd.DataFrame(columns=["listing_id", "date_key", "city_key",
                                              "available", "minimum_nights"])
    else:
        c = calendar.copy()
        fact_calendar = pd.DataFrame({
            "listing_id": pd.to_numeric(c["listing_id"], errors="coerce"),
            "date_key": _date_key_series(c["date"]),
            "city_key": c["city_key"],
            "available": c["available"],
            "minimum_nights": c.get("minimum_nights")})
        fact_calendar = fact_calendar.dropna(subset=["listing_id", "date_key"])

    # ---- fact_review (review grain) -- reviews ALREADY carry city_key ----
    if reviews is None or reviews.empty:
        fact_review = pd.DataFrame(columns=["review_sk", "listing_id", "city_key", "date_key"])
    else:
        r = reviews.copy()
        r["listing_id"] = pd.to_numeric(r["listing_id"], errors="coerce").astype("Int64")
        fact_review = pd.DataFrame({
            "review_sk": np.arange(1, len(r) + 1),
            "listing_id": r["listing_id"],
            "city_key": r["city_key"],                 # from ingest, no re-merge (FIX)
            "date_key": _date_key_series(r["date"])})
        fact_review = fact_review.dropna(subset=["listing_id", "date_key"])

    return fact_listing, fact_calendar, fact_review


def load_warehouse(master: pd.DataFrame, calendar: pd.DataFrame, review: pd.DataFrame,
                   db_path: Path = WAREHOUSE) -> duckdb.DuckDBPyConnection:
    dims = build_dimensions(master, calendar, review)
    fact_listing, fact_calendar, fact_review = build_facts(master, calendar, review, dims)

    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA_SQL.read_text())

    tables = {**dims, "fact_listing": fact_listing,
              "fact_calendar": fact_calendar, "fact_review": fact_review}
    order = ["dim_city", "dim_date", "dim_host", "dim_neighbourhood",
             "dim_property", "dim_room_type", "fact_listing", "fact_calendar", "fact_review"]
    for name in order:
        df = tables[name]
        con.register("_tmp", df)
        cols = ", ".join(con.execute(f"SELECT * FROM {name} LIMIT 0").df().columns)
        con.execute(f"INSERT INTO {name} ({cols}) SELECT {cols} FROM _tmp")
        con.unregister("_tmp")
    return con


def table_counts(con) -> pd.DataFrame:
    names = ["dim_city", "dim_host", "dim_neighbourhood", "dim_property",
             "dim_room_type", "dim_date", "fact_listing", "fact_calendar", "fact_review"]
    return pd.DataFrame([{"table": t,
                          "rows": con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]}
                         for t in names])
