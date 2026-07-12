from __future__ import annotations

from typing import Any

import pandas as pd


class DomainValidator:
    """
    Validate dataset.
    """

    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe

    def validate(self) -> dict[str, Any]:

        return {
            "price": self._validate_price(),
            "latitude": self._validate_latitude(),
            "longitude": self._validate_longitude(),
            "availability_365": self._validate_availability(),
            "minimum_nights": self._validate_minimum_nights(),
            "number_of_reviews": self._validate_reviews(),
        }

    def _validate_price(self):

        if "price" not in self.df.columns:
            return None

        price = (
            self.df["price"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
        )

        price = pd.to_numeric(price, errors="coerce")

        invalid = self.df[price < 0]

        return {
            "rule": "price >= 0",
            "violations": int(len(invalid)),
            "rows": invalid.index.tolist(),
        }

    def _validate_latitude(self):

        if "latitude" not in self.df.columns:
            return None

        invalid = self.df[
            (self.df["latitude"] < -90)
            | (self.df["latitude"] > 90)
        ]

        return {
            "rule": "-90 <= latitude <= 90",
            "violations": int(len(invalid)),
            "rows": invalid.index.tolist(),
        }

    def _validate_longitude(self):

        if "longitude" not in self.df.columns:
            return None

        invalid = self.df[
            (self.df["longitude"] < -180)
            | (self.df["longitude"] > 180)
        ]

        return {
            "rule": "-180 <= longitude <= 180",
            "violations": int(len(invalid)),
            "rows": invalid.index.tolist(),
        }

    def _validate_availability(self):

        if "availability_365" not in self.df.columns:
            return None

        invalid = self.df[
            (self.df["availability_365"] < 0)
            | (self.df["availability_365"] > 365)
        ]

        return {
            "rule": "0 <= availability_365 <= 365",
            "violations": int(len(invalid)),
            "rows": invalid.index.tolist(),
        }

    def _validate_minimum_nights(self):

        if "minimum_nights" not in self.df.columns:
            return None

        invalid = self.df[
            self.df["minimum_nights"] < 1
        ]

        return {
            "rule": "minimum_nights >= 1",
            "violations": int(len(invalid)),
            "rows": invalid.index.tolist(),
        }

    def _validate_reviews(self):

        if "number_of_reviews" not in self.df.columns:
            return None

        invalid = self.df[
            self.df["number_of_reviews"] < 0
        ]

        return {
            "rule": "number_of_reviews >= 0",
            "violations": int(len(invalid)),
            "rows": invalid.index.tolist(),
        }