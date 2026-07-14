from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # downloaded .csv.gz
INTERIM_DIR = DATA_DIR / "interim"  # cleaned / standardised parquet
REPORTS_DIR = DATA_DIR / "reports"  # profiling + data-quality artefacts
WAREHOUSE = DATA_DIR / "airbnb.duckdb"

for _d in (RAW_DIR, INTERIM_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


BASE_URL = "https://data.insideairbnb.com"


@dataclass(frozen=True)
class City:
    key: str            # short internal id, e.g. "amsterdam"
    display: str        # human name, e.g. "Amsterdam"
    slug: str           # url path, e.g. "the-netherlands/north-holland/amsterdam"
    snapshot: str       # scrape date, e.g. "2024-12-13"

    def file_url(self, name: str) -> str:
        sub = "visualisations" if name.endswith(".csv") and "neighbourhoods" in name else "data"
        return f"{BASE_URL}/{self.slug}/{self.snapshot}/{sub}/{name}"


CITIES: list[City] = [
    City("mallorca", "Mallorca", "spain/islas-baleares/mallorca", "2026-06-23"),
    City("melbourne", "Melbourne", "australia/vic/melbourne", "2026-06-16"),
    # City("lisbon", "Lisbon", "portugal/lisbon/lisbon", "2024-12-16"),
]


CITY_FILES = {
    "listings":       "listings.csv.gz",       # detailed (~90 cols)
    "calendar":       "calendar.csv.gz",        # future availability (no price in 2026 extracts)
    "reviews":        "reviews.csv.gz",         # full review text
    "neighbourhoods": "neighbourhoods.csv",     # canonical neighbourhood list
}

# ---------------------------------------------------------------------------
# Review sub-score columns present in the 2026 detailed listings. Carried
# through cleaning into fact_listing for 4.5 / ML feature use.
# ---------------------------------------------------------------------------
REVIEW_SUBSCORES = [
    "review_scores_accuracy",
    "review_scores_cleanliness",
    "review_scores_checkin",
    "review_scores_communication",
    "review_scores_location",
    "review_scores_value",
]


# ---------------------------------------------------------------------------
# Thresholds (profiling, outliers, dedup, validation)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Thresholds:
    # --- Profiling --------------------------------------------------------
    high_null_pct: float = 40.0          # flag a column if >40% missing
    high_cardinality_ratio: float = 0.9  # distinct/rows above this => id/free-text
    constant_col_max_distinct: int = 1   # one distinct non-null => constant (no info)

    # --- Outliers (Tukey rule: outside Q1-1.5*IQR .. Q3+1.5*IQR) ----------
    # price is parsed to float first (strips $ and ,). Only availability_365 is
    # profiled among the availability_* family; extend after the pipeline is green.
    iqr_k: float = 1.5
    outlier_numeric_fields: tuple = ("price", "minimum_nights", "number_of_reviews",
                                     "availability_365", "reviews_per_month")

    # --- Fuzzy dedup ------------------------------------------------------
    # threshold high (98) because true-duplicate names are near-identical;
    # geo_eps ~= 50 m buckets coordinates before name comparison.
    fuzzy_threshold: int = 98
    fuzzy_geo_eps: float = 0.0005
    fuzzy_bucket_cap: int = 200          # skip pathological dense cells (O(n^2) guard)

    # --- Validation bounds ------------------------------------------------
    price_min: float = 0.0               # price must be > this (strictly positive)
    price_max: float = 50000.0           # above this is almost certainly an error
    lat_min: float = -90.0
    lat_max: float = 90.0
    lon_min: float = -180.0
    lon_max: float = 180.0
    min_nights_max: int = 1125           # airbnb hard cap on minimum nights
    coord_precision: int = 6             # round lat/long to 6dp (~11cm)


THRESHOLDS = Thresholds()


# Airbnb officially uses four room types; normalise capitalisation to these.
CANONICAL_ROOM_TYPES = {
    "entire home/apt": "Entire home/apt",
    "private room": "Private room",
    "shared room": "Shared room",
    "hotel room": "Hotel room",
}
