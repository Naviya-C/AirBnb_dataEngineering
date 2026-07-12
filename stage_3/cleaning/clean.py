from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class DataCleaner:

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)

        self.report = {
            "price": {},
            "dates": {},
            "categories": {},
            "missing_values": {},
            "validation": {},
            "geography": {},
        }

    def clean(self) -> pd.DataFrame:
        self._clean_price()
        self._clean_dates()
        self._normalize_categories()
        self._handle_missing_values()
        self._validate_records()
        self._standardize_geography()

        return self.df

    def save(self, output_csv: Path, report_json: Path) -> pd.DataFrame:

        output_csv.parent.mkdir(parents=True,exist_ok=True)

        report_json.parent.mkdir(parents=True, exist_ok=True)

        cleaned_df = self.clean()

        cleaned_df.to_csv(output_csv, index=False,)

        with report_json.open("w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=4, ensure_ascii=False)

        return cleaned_df

    def _clean_price(self):
        if "price" not in self.df.columns:
            return

        original_nulls = self.df["price"].isna().sum()

        self.df["price"] = (
            self.df["price"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
        )

        self.df["price"] = pd.to_numeric(
            self.df["price"],
            errors="coerce",
        )

        self.report["price"] = {
            "cleaned": len(self.df),
            "null_after_conversion":
                int(self.df["price"].isna().sum()),
            "original_nulls":
                int(original_nulls),
        }

    def _clean_dates(self):
        date_columns = [
            column
            for column in self.df.columns
            if "date" in column.lower()
        ]

        cleaned = []

        for column in date_columns:

            self.df[column] = pd.to_datetime(
                self.df[column],
                errors="coerce",
            )

            cleaned.append(column)

        self.report["dates"] = {
            "columns": cleaned
        }

    def _normalize_categories(self):

        mappings = {

            "room_type": {
                "entire home": "Entire home/apt",
                "Entire Home": "Entire home/apt",
                "private room": "Private room",
            }

        }

        normalized = []

        for column, mapping in mappings.items():

            if column not in self.df.columns:
                continue

            self.df[column] = (
                self.df[column]
                .replace(mapping)
            )

            normalized.append(column)

        self.report["categories"] = {
            "normalized_columns": normalized
        }

    def _handle_missing_values(self):

        missing_before = (
            self.df.isna().sum().sum()
        )

        numeric = self.df.select_dtypes(
            include="number"
        ).columns

        self.df[numeric] = (
            self.df[numeric].fillna(0)
        )

        missing_after = (
            self.df.isna().sum().sum()
        )

        self.report["missing_values"] = {
            "before": int(missing_before),
            "after": int(missing_after),
        }

    def _validate_records(self):
        removed = 0
        if "price" in self.df.columns:
            invalid = self.df["price"] < 0
            removed = int(invalid.sum())
            self.df = self.df[~invalid]

        self.report["validation"] = {
            "removed_records": removed
        }

    def _standardize_geography(self):
        standardized = []

        if "neighbourhood" in self.df.columns:

            self.df["neighbourhood"] = (
                self.df["neighbourhood"]
                .astype(str)
                .str.strip()
                .str.title()
            )

            standardized.append("neighbourhood")

        if "latitude" in self.df.columns:

            self.df["latitude"] = (
                self.df["latitude"]
                .round(6)
            )

            standardized.append("latitude")

        if "longitude" in self.df.columns:

            self.df["longitude"] = (self.df["longitude"].round(6))

            standardized.append("longitude")

        self.report["geography"] = {
            "standardized": standardized
        }

from pathlib import Path

if __name__ == "__main__":

    cleaner = DataCleaner(
        Path(
            "data/01_raw/mallorca/2026-06-23/listing.csv"
        )
    )

    cleaner.save(
        output_csv=Path(
            "data/02_clean/mallorca/2026-06-23/listing_clean.csv"
        ),
        report_json=Path(
            "data/02_clean/mallorca/2026-06-23/cleaning_report.json"
        ),
    )

    print("Cleaning completed successfully.")