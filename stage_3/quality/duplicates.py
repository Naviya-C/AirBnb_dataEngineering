import pandas as pd
from typing import Any
from rapidfuzz import fuzz

class DuplicateDetector:
    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe
        
    def deterministic_duplicates(
        self,
        subset: list[str] | None = None,
    ) -> dict[str, Any]:
    
        """
        This function do deterministic duplicate(exact duplicate).
        
        Param:
            - Columns used to determine duplicates.
            - If none then entire row is compared.
        """
    
        duplicated = self.df.duplicated(subset = subset, keep = False)
        
        duplicate_rows = self.df[duplicated]
        
        return {
            "count": int(duplicated.sum()),
            "percentage": round(
                duplicated.mean() * 100,
                2
            ),
            "rows": duplicate_rows.index.to_list(),
        }
        
    def fuzzy_duplicates(
        self,
        column: str,
        threshold: int = 90,
    ) -> dict[str, Any]:
        """
        Detecting fuzzy duplications
        """
        
        values = (
            self.df[column].dropna().astype(str).unique().tolist()
        )
        
        matches = []
        
        for i in range(len(values)):
            for j in range(i+1, len(values)):
                score = fuzz.ratio(values[i], values[j])
                
                if score >= threshold:
                    matches.append({
                        "value_1": values[i],
                        "value_2": values[j],
                        "matching_score": score,
                    })
        
        return {
            "count": len(matches),
            "threshold": threshold,
            "matches": matches,
        }