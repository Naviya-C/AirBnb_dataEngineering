from pathlib import Path
from dataclasses import dataclass

from ingestion import AirbnbIngestionPipeline
from profiling import Profiling
from quality.report import QualityReport
from overall_quality_report import OverallQualityReport


@dataclass
class Dataset:
    city: str
    snapshot: str
    url: str


class AirbnbPipeline:

    def __init__(self):

        self.ingestion = AirbnbIngestionPipeline()

    def run(self, datasets: list[Dataset]) -> None:
        
        for dataset in datasets:
            print(f"\nProcessing {dataset.city} ({dataset.snapshot})")

            # ----------------------------------------
            # Stage 1 : Download & Extract
            # ----------------------------------------

            csv_path = self.ingestion.download_dataset(
                url = dataset.url,
                city = dataset.city,
                filename = "listing.csv.gz",
                snapshot_date = dataset.snapshot,
            )

            # If your ingestion already returns listing.csv,
            # remove this line.
            csv_path = csv_path.with_suffix("")

            # ----------------------------------------
            # Stage 2 : Profiling
            # ----------------------------------------

            profile_path = (
                csv_path.parent /
                "listing_profile.json"
            )

            profiler = Profiling(csv_path)

            profiler.save_profile(profile_path)

            # ----------------------------------------
            # Stage 3 : Quality Report
            # ----------------------------------------

            quality_report_path = (
                csv_path.parent /
                "quality_report.json"
            )

            quality = QualityReport(
                csv_path=csv_path,
                profile_path=profile_path,
            )

            quality.save(quality_report_path)

        # ----------------------------------------
        # Stage 4 : Overall Quality Report
        # ----------------------------------------

        overall = OverallQualityReport(
            Path("data/01_raw")
        )

        overall.save(
            Path(
                "reports/overall_quality_report.json"
            )
        )

        print("\nPipeline completed successfully.")


if __name__ == "__main__":

    datasets = [

        Dataset(
            city="mallorca",
            snapshot="2026-06-23",
            url="https://data.insideairbnb.com/spain/islas-baleares/mallorca/2026-06-23/data/listings.csv.gz",
        ),

        Dataset(
            city="madrid",
            snapshot="2026-06-20",
            url="https://data.insideairbnb.com/spain/comunidad-de-madrid/madrid/2026-06-20/data/listings.csv.gz",
        ),
        
        Dataset(
            city="Melbourne",
            snapshot="2026-06-16",
            url="https://data.insideairbnb.com/australia/vic/melbourne/2026-06-16/data/listings.csv.gz",
        ),

    ]

    pipeline = AirbnbPipeline()

    pipeline.run(datasets)