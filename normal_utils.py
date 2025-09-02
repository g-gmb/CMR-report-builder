
import os
import pandas as pd
from typing import Dict

AGE_COLUMNS = ["18- 29", "30- 39", "40- 49", "50- 59", "60- 69", "70+"]

def _load_table(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna('')
    header = df.iloc[0].tolist()
    df.columns = header
    df = df.iloc[1:].reset_index(drop=True)
    if "Variable" not in df.columns:
        first = header[0]
        df = df.rename(columns={first: "Variable"})
    df["Variable"] = df["Variable"].astype(str).str.strip()
    for c in AGE_COLUMNS:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df

def _is_section_row(row: pd.Series) -> bool:
    if not str(row.get("Variable", "")).strip():
        return False
    vals = [str(row.get(c, "")).strip() for c in AGE_COLUMNS if c in row.index]
    return all(v == "" for v in vals)

def _split_sections(df: pd.DataFrame):
    sections = {}
    current = "Generale"
    rows = []
    for _, row in df.iterrows():
        if _is_section_row(row):
            if rows:
                sections[current] = pd.DataFrame(rows)
                rows = []
            current = row["Variable"]
        else:
            rows.append(row)
    if rows:
        sections[current] = pd.DataFrame(rows)
    return sections

def load_normals(data_dir: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    male_df = _load_table(os.path.join(data_dir, "table_1.csv"))
    female_df = _load_table(os.path.join(data_dir, "table_2.csv"))
    return {
        "M": _split_sections(male_df),
        "F": _split_sections(female_df),
    }

def pick_age_column(age: int) -> str:
    if age is None or age < 18: return "18- 29"
    if 18 <= age <= 29: return "18- 29"
    if 30 <= age <= 39: return "30- 39"
    if 40 <= age <= 49: return "40- 49"
    if 50 <= age <= 59: return "50- 59"
    if 60 <= age <= 69: return "60- 69"
    return "70+"

PLACEHOLDER_TO_VARIABLE = {
    "LVedv": "LVEDV (ml)",
    "LVedvbsa": "LVEDVi (ml/m2)",
    "LVmass": "LVM diast (g)",
    "LVmassbsa": "LVMi diast (g/m2)",
    "LVEF": "LVEF (%)",
    "RVedv": "RVEDV (ml)",
    "RVedvbsa": "RVEDVi (ml/m2)",
    "RVEF": "RVEF (%)",
    "LA": "LAESV (ml)",
    "LAbsa": "LAESVi (ml/m2)",
    "RA": "RAESV (ml)",
    "RAbsa": "RAESVi (ml/m2)",
}

def get_normal_value(normals, sex: str, age: int, key: str) -> str:
    var_name = PLACEHOLDER_TO_VARIABLE.get(key)
    if var_name is None:
        return ""
    sections = normals.get(sex, {})
    age_col = pick_age_column(age)
    for _, df in sections.items():
        if "Variable" in df.columns:
            mask = df["Variable"].astype(str).str.strip() == var_name
            if mask.any():
                row = df[mask].iloc[0]
                return str(row.get(age_col, ""))
    return ""
