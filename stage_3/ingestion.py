import gzip
import shutil
from datetime import datetime
from pathlib import Path

import requests

from logger import logger

logger = logger(__name__)


class AirbnbIngestionPipeline:

    def __init__(self, base_data_dir: str = "data"):
        self.base_data_dir = Path(base_data_dir) / "01_raw"

    def _ensure_directory(
        self,
        city: str,
        snapshot_date: str,
    ) -> Path:

        target_dir = (
            self.base_data_dir
            / city.lower().replace(" ", "_")
            / snapshot_date
        )

        target_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        return target_dir

    def _download_file(
        self,
        url: str,
        destination: Path,
    ) -> Path:

        if destination.exists():
            logger.info(f"{destination.name} already exists.")
            return destination

        logger.info(f"Downloading {destination.name}")

        with requests.get(
            url,
            stream=True,
            timeout=30,
        ) as response:

            response.raise_for_status()

            with destination.open("wb") as f:

                for chunk in response.iter_content(
                    chunk_size=8192
                ):

                    if chunk:
                        f.write(chunk)

        return destination

    def _extract_gzip(
        self,
        gz_path: Path,
    ) -> Path:

        csv_path = gz_path.with_suffix("")

        if csv_path.exists():
            logger.info(f"{csv_path.name} already extracted.")
            return csv_path

        logger.info(f"Extracting {gz_path.name}")

        with gzip.open(
            gz_path,
            "rb",
        ) as src:

            with csv_path.open(
                "wb",
            ) as dst:

                shutil.copyfileobj(
                    src,
                    dst,
                )

        return csv_path

    def download_city_data(
        self,
        city: str,
        snapshot_date: str,
        base_url: str,
        assets: list[str],
    ) -> dict[str, Path]:

        target_dir = self._ensure_directory(
            city,
            snapshot_date,
        )

        downloaded = {}

        for asset in assets:

            url = f"{base_url}/{asset}"

            gz_path = target_dir / asset

            self._download_file(
                url,
                gz_path,
            )

            if gz_path.suffix == ".gz":
                csv_path = self._extract_gzip(
                    gz_path,
                )

                downloaded[
                    csv_path.stem
                ] = csv_path

            else:

                downloaded[
                    gz_path.stem
                ] = gz_path

        return downloaded
    
if __name__ == "__main__":

    pipeline = AirbnbIngestionPipeline()

    files = pipeline.download_city_data(

        city="Mallorca",

        snapshot_date="2026-06-23",

        base_url="https://data.insideairbnb.com/spain/islas-baleares/mallorca/2026-06-23/data",

        assets=[
            "listings.csv.gz",
            "reviews.csv.gz",
            "calendar.csv.gz",
        ],
    )

    print(files)