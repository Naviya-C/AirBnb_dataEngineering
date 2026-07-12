import json
from datetime import datetime
from pathlib import Path


class OverallQualityReport:

    def __init__(self, root_data_dir: Path):
        self.root_data_dir = root_data_dir

    def generate(self) -> dict:

        reports = list(self.root_data_dir.rglob("quality_report.json"))

        datasets = []

        summary = {
            "pass": 0,
            "warning": 0,
            "fail": 0,
            "total_exact_duplicates": 0,
            "total_fuzzy_duplicates": 0,
            "total_outliers": 0,
            "total_validation_violations": 0,
        }

        missing_percentages = []

        for report_path in reports:

            with report_path.open("r", encoding="utf-8") as f:
                report = json.load(f)

            # --------------------------------------------------
            # Dataset metadata
            # --------------------------------------------------

            city = report_path.parents[1].name
            snapshot = report_path.parent.name

            status = report["overall_quality"]["status"]
            issues = report["overall_quality"]["issues_found"]

            # --------------------------------------------------
            # Duplicate summary
            # --------------------------------------------------

            exact_duplicates = report["duplicates"]["exact"]["count"]
            fuzzy_duplicates = report["duplicates"]["fuzzy"]["count"]

            # --------------------------------------------------
            # Completeness
            # --------------------------------------------------

            missing = report["completeness"][
                "overall_missing_percentage"
            ]

            missing_percentages.append(missing)

            # --------------------------------------------------
            # Outliers
            # --------------------------------------------------

            price_outliers = report["outliers"].get("price", {}).get("count", 0)

            availability_outliers = report["outliers"].get("availability_365", {}).get("count", 0)

            review_outliers = report["outliers"].get("number_of_reviews", {}).get("count", 0)

            total_outliers = (
                price_outliers
                + availability_outliers
                + review_outliers
            )

            # --------------------------------------------------
            # Validation
            # --------------------------------------------------

            validation_errors = sum(
                result["violations"]
                for result in report["validation"].values()
                if result is not None
            )

            # --------------------------------------------------
            # Dataset summary
            # --------------------------------------------------

            datasets.append(
                {
                    "dataset": city,
                    "snapshot_date": snapshot,

                    "overall_quality": {
                        "status": status,
                        "issues_found": issues,
                    },

                    "summary": {
                        "exact_duplicates": exact_duplicates,
                        "fuzzy_duplicates": fuzzy_duplicates,

                        "overall_missing_percentage": missing,

                        "price_outliers": price_outliers,
                        "availability_outliers": availability_outliers,
                        "review_outliers": review_outliers,

                        "validation_violations": validation_errors,
                    },
                }
            )

            # --------------------------------------------------
            # Aggregate summary
            # --------------------------------------------------

            summary[status.lower()] += 1

            summary["total_exact_duplicates"] += exact_duplicates

            summary["total_fuzzy_duplicates"] += fuzzy_duplicates

            summary["total_outliers"] += total_outliers

            summary["total_validation_violations"] += validation_errors

        overall = {
            "generated_at": datetime.now().isoformat(),
            "datasets_processed": len(datasets),
            "datasets": datasets,
            "overall_summary": {
                **summary,
                "average_missing_percentage": round(
                    sum(missing_percentages)
                    / len(missing_percentages),
                    2,
                )
                if missing_percentages
                else 0,
            },
        }

        return overall

    def save(self, output_path: Path) -> Path:

        output_path.parent.mkdir(parents=True, exist_ok=True)

        report = self.generate()

        with output_path.open("w", encoding="utf-8") as f:

            json.dump(
                report,
                f,
                indent = 4,
                ensure_ascii = False,
            )

        return output_path


if __name__ == "__main__":

    report = OverallQualityReport(
        Path("data/01_raw/mallorca/2026-06-23/")
    )

    output = report.save(
        Path("reports/overall_quality_report.json")
    )

    print(f"Saved: {output}")