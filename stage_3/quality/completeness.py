import pandas as pd
import json
from pathlib import Path
from typing import Any


class CompletenessAnalyzer:
    def __init__(
        self,
        dataframe: pd.DataFrame,
        profile_path: Path | None = None,
    ):
        self.df = dataframe
        self.profile_path = profile_path

    def analyze(self) -> dict[str, Any]:
        """
        Uses the profiling artifact if it exists.
        Otherwise computes completeness directly from the dataframe.
        """

        if self.profile_path and self.profile_path.exists():
            with self.profile_path.open(
                "r",
                encoding="utf-8",
            ) as f:
                profile = json.load(f)

            null_rates = profile["null_rates"]
            rows = profile["rows"]

        else:
            rows = len(self.df)

            null_rates = (
                self.df.isnull()
                .mean()
                .mul(100)
                .round(2)
                .to_dict()
            )

        columns = {}

        for column, percentage in null_rates.items():

            missing_count = int(
                round(rows * percentage / 100)
            )

            columns[column] = {
                "missing_count": missing_count,
                "missing_percentage": percentage,
                "implication": self._implication(
                    percentage
                ),
            }

        overall_missing = round(
            sum(null_rates.values()) / len(null_rates),
            2,
        )

        return {
            "overall_missing_percentage": overall_missing,
            "columns": columns,
        }

    @staticmethod
    def _implication(
        missing_percentage: float,
    ) -> str:

        if missing_percentage == 0:
            return "Complete."

        if missing_percentage >0 and missing_percentage < 2:
            return "Negligible Impact."

        if missing_percentage >2 and missing_percentage < 10:
            return "Low Impact"

        if missing_percentage > 10 and missing_percentage < 30:
            return "Medium Implact."

        return (
            "Very high missingness. "
            "Consider imputation or drop this field."
        )