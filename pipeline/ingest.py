"""
3.1 -- Data ingestion
=====================

This file implements the data ingestion layer of your Airbnb pipeline. Its job is to:

    Download datasets from Inside Airbnb.
    Avoid downloading files unnecessarily.
    Record exactly what was downloaded.
    Load the downloaded files into pandas DataFrames.
    Return the data in a structured format for the next pipeline stage (cleaning).

Think of it as the Extract (E) in an ETL (Extract → Transform → Load) pipeline.
"""

import gzip
import hashlib
import io
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

from config import CITIES, CITY_FILES, RAW_DIR, City

MANIFEST = RAW_DIR / "_manifest.json" # This records every downloads.
_CHUNK = 1 << 16 # Rather than load the whole file to memory for download, it used 64KB means memeory safe. 


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def _save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=4, sort_keys=True))


def _download(url: str, dest: Path, *, timeout: int = 60) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "airbnb-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        while chunk := resp.read(_CHUNK):
            out.write(chunk)


def fetch_city(city: City, *, files: dict | None = None, force: bool = False) -> dict[str, Path]:
    """Download (or reuse) every file for one city. Returns {logical_name: path}."""
    files = files or CITY_FILES
    manifest = _load_manifest()
    out: dict[str, Path] = {}
    city_dir = RAW_DIR / city.key
    city_dir.mkdir(parents=True, exist_ok=True)

    for logical, fname in files.items():
        dest = city_dir / fname
        url = city.file_url(fname)
        key = f"{city.key}/{fname}"

        if dest.exists() and not force:
            # Trust an existing file; still (re)record its checksum in the manifest.
            out[logical] = dest
            manifest[key] = {**manifest.get(key, {}),
                             "url": url, "bytes": dest.stat().st_size,
                             "sha256": _sha256(dest), "reused": True}
            continue

        try:
            _download(url, dest)
            manifest[key] = {"url": url, "bytes": dest.stat().st_size,
                             "sha256": _sha256(dest),
                             "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                             "reused": False}
            out[logical] = dest
        except Exception as exc:  # network down, 404 for that snapshot, etc.
            manifest[key] = {"url": url, "error": str(exc)}
            print(f"  [warn] {key}: {exc}")

    _save_manifest(manifest)
    return out


def _read_csv(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:
        raw = fh.read()
    return pd.read_csv(io.BytesIO(raw), dtype=str, low_memory=False,
                       keep_default_na=True, na_values=["", "N/A", "NA", "null"])
  

def load_city(city: City, paths: dict[str, Path]) -> dict[str, pd.DataFrame]:
    """Turn downloaded files into DataFrames, tagging each row with its city so a
    multi-city run can be concatenated into one master frame later (3.3)."""
    frames: dict[str, pd.DataFrame] = {}
    for logical, path in paths.items():
        if not path.exists():
            continue
        df = _read_csv(path)
        df.insert(0, "city_key", city.key)
        df.insert(1, "snapshot_date", city.snapshot)
        frames[logical] = df
    return frames


def ingest(cities: list[City] | None = None, *, force: bool = False
           ) -> dict[str, dict[str, pd.DataFrame]]:
    """Top-level entry point. Returns {city_key: {logical_name: DataFrame}}."""
    cities = cities or CITIES
    result: dict[str, dict[str, pd.DataFrame]] = {}
    for city in cities:
        print(f"[ingest] {city.display} ({city.snapshot})")
        paths = fetch_city(city, force=force)
        frames = load_city(city, paths)
        for name, df in frames.items():
            print(f"   {name:14s} {len(df):>8,} rows  {df.shape[1]:>3} cols")
        result[city.key] = frames
    return result


if __name__ == "__main__":
    ingest()
