"""
End-to-end orchestrator for the Inside Airbnb pipeline.

    python run.py                # full run on config.CITIES
    python run.py --sample       # regenerate synthetic data first (offline demo)
    python run.py --queries      # (re)run analytics.sql against the warehouse

Stages: ingest -> profile -> quality -> clean -> enrich -> model -> analytics.
All artefacts land in data/reports/ and data/airbnb.duckdb.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

from config import CITIES, INTERIM_DIR, REPORTS_DIR, ROOT, WAREHOUSE
from pipeline import clean, enrich, model, profile, quality
from pipeline.ingest import ingest


def _w(df: pd.DataFrame, name: str) -> Path:
    p = REPORTS_DIR / name
    df.to_csv(p, index=False)
    return p


def run(cities=None) -> None:
    cities = cities or CITIES

    # ---- 3.1 ingest -----------------------------------------------------
    frames_by_city = ingest(cities)

    # ---- 3.1 profile ----------------------------------------------------
    prof = profile.profile_all(frames_by_city)
    tdist = profile.type_distribution(prof)
    _w(prof, "profile_columns.csv")
    _w(tdist, "profile_type_distribution.csv")

    # ---- 3.1 quality ----------------------------------------------------
    dupe_parts, comp_parts, out_parts, val_parts, fuzzy_parts = [], [], [], [], []
    for city, frames in frames_by_city.items():
        for logical, df in frames.items():
            ds = f"{city}.{logical}"
            dupe_parts.append(quality.deterministic_duplicates(df, ds))
            comp_parts.append(quality.completeness(df, ds))
        listings = frames["listings"]
        out_parts.append(quality.outliers(listings, f"{city}.listings"))
        val_parts.append(quality.validate(listings, f"{city}.listings"))
        fuzzy_parts.append(quality.fuzzy_duplicates(listings, f"{city}.listings"))

    dupes = pd.concat(dupe_parts, ignore_index=True)
    comp = pd.concat(comp_parts, ignore_index=True)
    outl = pd.concat(out_parts, ignore_index=True)
    val = pd.concat(val_parts, ignore_index=True)
    fuzzy = pd.concat(fuzzy_parts, ignore_index=True)
    for df, nm in [(dupes, "dq_duplicates.csv"), (comp, "dq_completeness.csv"),
                   (outl, "dq_outliers.csv"), (val, "dq_validation.csv"),
                   (fuzzy, "dq_fuzzy_duplicates.csv")]:
        _w(df, nm)

    # ---- 3.2 clean ------------------------------------------------------
    masters, all_rejects = {}, []
    clean_calendars = {}
    all_reviews = {}
    for city, frames in frames_by_city.items():
        cl, rej = clean.clean_listings(frames["listings"])
        cal = clean.clean_calendar(frames["calendar"]) if "calendar" in frames else pd.DataFrame()
        clean_calendars[city] = cal
        all_rejects.append(rej)
        cl.to_parquet(INTERIM_DIR / f"{city}_listings_clean.parquet", index=False)

        # ---- 3.3 enrich (per city) -------------------------------------
        reviews = frames.get("reviews", pd.DataFrame())
        all_reviews[city] = reviews
        masters[city] = enrich.build_master(cl, reviews, cal)

    rejects = pd.concat(all_rejects, ignore_index=True)
    _w(rejects[["city_key", "id", "reject_reason"]] if not rejects.empty else rejects,
       "rejected_records.csv")

    # ---- 3.3 cross-city union ------------------------------------------
    master = enrich.unify_cities(masters)
    master.to_parquet(INTERIM_DIR / "master_all_cities.parquet", index=False)

    # ---- 3.4 model ------------------------------------------------------
    calendar_all = pd.concat(clean_calendars.values(), ignore_index=True) \
        if clean_calendars else pd.DataFrame()
    reviews_all = (
        pd.concat(all_reviews.values(), ignore_index=True)
        if all_reviews else pd.DataFrame()
    )
    con = model.load_warehouse(master, calendar_all, reviews_all)
    counts = model.table_counts(con)

    # ---- consolidated data-quality report ------------------------------
    _write_report(frames_by_city, prof, tdist, dupes, fuzzy, comp, outl, val,
                  rejects, counts)

    # ---- 3.4 analytics --------------------------------------------------
    _run_queries(con)
    con.close()

    print("\nDone. Artefacts in", REPORTS_DIR)
    print("Warehouse:", WAREHOUSE)


def _md_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    return df.head(max_rows).to_markdown(index=False)


def _write_report(frames_by_city, prof, tdist, dupes, fuzzy, comp, outl, val,
                  rejects, counts) -> None:
    lines = ["# Data Quality Report — Inside Airbnb pipeline", ""]
    lines.append(f"Cities: {', '.join(sorted(frames_by_city))}")
    total_rows = sum(len(df) for f in frames_by_city.values() for df in f.values())
    lines += [f"Total ingested rows (all datasets): {total_rows:,}", ""]

    lines += ["## 1. Ingested datasets", ""]
    inv = [{"dataset": f"{c}.{k}", "rows": len(df), "cols": df.shape[1]}
           for c, fr in frames_by_city.items() for k, df in fr.items()]
    lines += [_md_table(pd.DataFrame(inv)), ""]

    lines += ["## 2. Column type distribution (inferred)", "",
              _md_table(tdist, 40), ""]

    lines += ["## 3. Duplicates", "", "### Deterministic", "",
              _md_table(dupes), "",
              f"### Fuzzy (name+geo, score ≥ threshold): {len(fuzzy)} candidate pairs", ""]
    if not fuzzy.empty:
        lines += [_md_table(fuzzy[["dataset", "id_a", "id_b", "score"]], 10), ""]

    lines += ["## 4. Completeness — most-missing fields", "",
              _md_table(comp.sort_values("missing_pct", ascending=False), 15), ""]

    lines += ["## 5. Outliers (Tukey/IQR)", "", _md_table(outl), ""]

    lines += ["## 6. Domain validation", "", _md_table(val), "",
              f"Rejected records (failed hard rules): {len(rejects):,}", ""]

    lines += ["## 7. Warehouse (star schema) row counts", "",
              _md_table(counts), ""]

    (REPORTS_DIR / "DATA_QUALITY_REPORT.md").write_text("\n".join(lines))


def _run_queries(con) -> None:
    raw = (ROOT / "sql" / "analytics.sql").read_text()
    # strip full-line and trailing "-- ..." comments so a ';' inside a comment
    # can't split a statement in half
    no_comments = "\n".join(line.split("--", 1)[0] for line in raw.splitlines())
    blocks = [b.strip() for b in no_comments.split(";") if b.strip()]
    out_lines = ["# Analytical query results", ""]
    labels = ["Q1 price by city+room type", "Q2 top neighbourhoods by revenue",
              "Q3 superhost premium", "Q4 price by property family",
              "Q5 tenure vs reviews", "Q6 monthly availability",
              "Q7 review sub-scores by city"]
    for i, block in enumerate(blocks):
        try:
            res = con.execute(block).df()
            label = labels[i] if i < len(labels) else f"Query {i+1}"
            out_lines += [f"## {label}", "", res.head(12).to_markdown(index=False), ""]
        except Exception as exc:
            out_lines += [f"## Query {i+1} FAILED", f"```\n{exc}\n```", ""]
    (REPORTS_DIR / "QUERY_RESULTS.md").write_text("\n".join(out_lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="regenerate synthetic data first")
    ap.add_argument("--queries", action="store_true", help="only rerun analytics.sql")
    args = ap.parse_args()

    if args.sample:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_sample_data.py")], check=True)

    if args.queries:
        import duckdb
        _run_queries(duckdb.connect(str(WAREHOUSE)))
        print("Queries rerun ->", REPORTS_DIR / "QUERY_RESULTS.md")
    else:
        run()
