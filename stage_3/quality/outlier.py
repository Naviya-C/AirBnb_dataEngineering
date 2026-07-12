from typing import Any
import pandas as pd


class OutlierDetector:
    """
    Detect numerical outliers using the IQR method.
    """

    DEFAULT_COLUMNS = [
        "price",
        "availability_365",
        "number_of_reviews",
    ]

    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe

    def analyze(self, columns: list[str] | None = None) -> dict[str, Any]:
        if columns is None:
            columns = self.DEFAULT_COLUMNS

        results = {}

        for column in columns:

            if column not in self.df.columns:
                continue

            series = self.df[column]

            # Clean Airbnb price values like "$1,250.00"
            if column == "price":
                series = (
                    series.astype(str)
                    .str.replace("$", "", regex=False)
                    .str.replace(",", "", regex=False)
                )

            # Convert to numeric
            series = (
                pd.to_numeric(
                    series,
                    errors="coerce",
                )
                .dropna()
            )

            if series.empty:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)

            iqr = q3 - q1

            lower = q1 - (1.5 * iqr)
            upper = q3 + (1.5 * iqr)

            mask = (
                (series < lower)
                | (series > upper)
            )

            outliers = series[mask]

            results[column] = {
                "method": "IQR",
                "count": int(mask.sum()),
                "percentage": round(
                    (mask.sum() / len(series)) * 100,
                    2,
                ),
                "lower_bound": float(lower),
                "upper_bound": float(upper),
                "min_outlier": (
                    float(outliers.min())
                    if not outliers.empty
                    else None
                ),
                "max_outlier": (
                    float(outliers.max())
                    if not outliers.empty
                    else None
                ),
            }

        return results