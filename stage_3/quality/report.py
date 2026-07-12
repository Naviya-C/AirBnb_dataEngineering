import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from quality.completeness import CompletenessAnalyzer
from quality.duplicates import DuplicateDetector
from quality.outlier import OutlierDetector
from quality.validation import DomainValidator


class QualityReport:

    def __init__(
        self,
        csv_path: Path,
        profile_path: Path | None = None,
    ):
        self.csv_path = csv_path
        self.profile_path = profile_path

        self.df = pd.read_csv(csv_path)

    def generate(self) -> dict:
        duplicate_detector = DuplicateDetector(self.df)

        completeness_analyzer = CompletenessAnalyzer(
            dataframe=self.df,
            profile_path=self.profile_path,
        )

        outlier_detector = OutlierDetector(self.df)

        validator = DomainValidator(self.df)


        duplicates_result = {
            "exact": duplicate_detector.deterministic_duplicates(
                subset=["id"]
            ),
            "fuzzy": duplicate_detector.fuzzy_duplicates(
                column="name",
                threshold=90,
            ),
        }

        completeness_result = completeness_analyzer.analyze()

        outliers_result = outlier_detector.analyze()

        validation_result = validator.validate()


        report = {
            "dataset": self.csv_path.name,
            "generated_at": datetime.now().isoformat(),

            "duplicates": duplicates_result,

            "completeness": completeness_result,

            "outliers": outliers_result,

            "validation": validation_result,

            "overall_quality": self._overall_quality(
                duplicates_result,
                validation_result,
            ),
        }

        return report

    def save(self, output_path: Path) -> Path:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        report = self.generate()

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                report,
                f,
                indent=4,
                ensure_ascii=False,
            )

        return output_path

    def _overall_quality(self, duplicates: dict, validation: dict) -> dict:
        """
        Summarize the overall quality of the dataset.
        """

        issues = 0

        # Exact duplicates
        issues += duplicates["exact"]["count"]

        # Fuzzy duplicates
        issues += duplicates["fuzzy"]["count"]

        # Validation violations
        for result in validation.values():

            if result is None:
                continue

            issues += result["violations"]

        if issues == 0:
            status = "PASS"

        elif issues <= 20:
            status = "WARNING"

        else:
            status = "FAIL"

        return {
            "status": status,
            "issues_found": issues,
        }


if __name__ == "__main__":

    report = QualityReport(
        csv_path=Path(
            "data/01_raw/mallorca/2026-06-23/listing.csv"
        ),
        profile_path=Path(
            "data/01_raw/mallorca/2026-06-23/listing_profile.json"
        ),
    )

    output = report.save(
        Path(
            "data/01_raw/mallorca/2026-06-23/quality_report.json"
        )
    )

    print(f"Quality report saved to: {output}")