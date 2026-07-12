import pandas as pd
from pathlib import Path
import json
from logger import logger

logger = logger("__main__")

class Profiling:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)

    def _profile(self):
        rows, columns = self.df.shape
        
        data_type_distribution = {
            dtype.name if hasattr(dtype, "name") else str(dtype): int(count)
            for dtype, count in self.df.dtypes.value_counts().items()
        }

        profile = {
            "rows": rows,
            "columns": columns,
            "data_type_distribution": data_type_distribution,
            "null_rates": (self.df.isnull().mean() * 100).round(2).to_dict(),
            "column_cardinality": self.df.nunique().to_dict(),
        }
        
        #logger.info(f"Profiling Successful")

        return profile

    def save_profile(self, output_path: Path):
        profile = self._profile()

        #logger.info("Start export to json format")
         
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)
        
        #logger.info("Exporting Successful")

        return output_path
    
if __name__ == "__main__":
    prof = Profiling(Path("data/01_raw/mallorca/2026-06-23/listing.csv"))
    
    prof.save_profile(Path("data/01_raw/mallorca/2026-06-23/listing.json"))