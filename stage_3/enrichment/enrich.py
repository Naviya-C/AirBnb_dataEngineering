from pathlib import Path
import pandas as pd

class DataEnricher:

    def __init__(
        self,
        listing_path: Path,
        reviews_path: Path | None = None,
        calendar_path: Path | None = None,
        neighbourhood_path: Path | None = None,
    ):

        self.listings = pd.read_csv(listing_path)

        self.reviews = (
            pd.read_csv(reviews_path)
            if reviews_path and reviews_path.exists()
            else None
        )

        self.calendar = (
            pd.read_csv(calendar_path)
            if calendar_path and calendar_path.exists()
            else None
        )

        self.neighbourhoods = (
            pd.read_csv(neighbourhood_path)
            if neighbourhood_path and neighbourhood_path.exists()
            else None
        )

        self.master = self.listings.copy()

    # -----------------------------------------------------

    def enrich(self) -> pd.DataFrame:
        self._join_calendar()
        self._join_neighbourhood_statistics()
        self._derive_features()

        return self.master

    # -----------------------------------------------------

    def save(self, output_csv: Path) -> Path:

        output_csv.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df = self.enrich()

        df.to_csv(
            output_csv,
            index=False,
        )

        return output_csv

    # =====================================================
    # Review Summary
    # =====================================================

        """
        Review summary already in the listing.csv.
        Therefore no need add it.
        """
        

    # =====================================================
    # Calendar
    # =====================================================

    def _join_calendar(self):

        if self.calendar is None:
            return

        calendar = self.calendar.copy()

        calendar["available"] = (calendar["available"].astype(str).str.lower())

        summary = (
            calendar.groupby("listing_id")
            .agg(
                occupied_days=(
                    "available",
                    lambda x: (x == "f").sum(),
                ),
                total_days=("available", "count"),
            )
            .reset_index()
        )

        summary["occupancy_rate"] = (
            summary["occupied_days"]
            / summary["total_days"]
        )

        self.master = self.master.merge(summary, left_on="id", right_on="listing_id", how="left")

        self.master.drop(columns=["listing_id"], inplace=True, errors="ignore",)

        # Revenue estimate using listing price
        if "price" in self.master.columns:
            self.master["estimated_revenue"] = (
                self.master["price"]
                * self.master["occupied_days"]
            )

    # =====================================================
    # Neighbourhood Aggregates
    # =====================================================

    def _join_neighbourhood_statistics(self):

        if "neighbourhood" not in self.master.columns:
            return

        stats = (
            self.master
            .groupby("neighbourhood")
            .agg(
                neighbourhood_median_price=("price", "median"),
                neighbourhood_listing_count=("id","count"),
                neighbourhood_average_rating=(
                    "review_scores_rating",
                    "mean",
                ),
            )
            .reset_index()
        )

        self.master = self.master.merge(
            stats,
            on="neighbourhood",
            how="left",
        )

    # =====================================================
    # Derived Features
    # =====================================================

    def _derive_features(self):

        if "host_since" in self.master.columns:

            self.master["host_since"] = pd.to_datetime(
                self.master["host_since"],
                errors="coerce",
            )

            today = pd.Timestamp.today()

            self.master["host_tenure_years"] = (
                (
                    today
                    - self.master["host_since"]
                )
                .dt.days
                / 365.25
            ).round(2)

        if {
            "number_of_reviews",
            "host_tenure_years",
        }.issubset(self.master.columns):

            self.master["review_frequency"] = (
                self.master["number_of_reviews"]
                /
                self.master["host_tenure_years"]
            )

        if {
            "price",
            "bedrooms",
        }.issubset(self.master.columns):

            self.master["price_per_bedroom"] = (
                self.master["price"]
                /
                self.master["bedrooms"].replace(
                    0,
                    pd.NA,
                )
            )


if __name__ == "__main__":

    enricher = DataEnricher(
        listing_path=Path(
            "data/02_clean/mallorca/2026-06-23/listing_clean.csv"
        ),
        reviews_path=Path(
            "data/01_raw/mallorca/2026-06-23/reviews.csv"
        ),
        calendar_path=Path(
            "data/01_raw/mallorca/2026-06-23/calendar.csv"
        ),
    )

    output = enricher.save(
        Path(
            "data/03_enriched/mallorca/2026-06-23/listing_master.csv"
        )
    )

    print(f"Saved: {output}")