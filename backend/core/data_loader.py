"""
Load and preprocess the vehicle-tyre mapping Excel data.
"""
import os
import re
import pandas as pd
from typing import List, Dict, Tuple

# Default path: backend/data/ (works both locally and on Railway)
DEFAULT_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data",
    "mcy-vehicle-sku-mapping-v18-14.04.2026.xlsx"
)


def _clean_sku(value) -> str:
    """Return SKU as a plain integer string (e.g. '113264'), never '113264.0'."""
    v = str(value or "").strip()
    if not v or v.lower() in ("nan", "#value!"):
        return ""
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return v


def load_tyre_data(excel_path: str = None) -> List[Dict]:
    """Load and clean tyre mapping data from Excel file."""
    path = excel_path or os.getenv("DATA_PATH", DEFAULT_DATA_PATH)
    path = os.path.abspath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_excel(path)

    # Normalise column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # Find the SKU description column (named "sku-desc." with trailing period)
    sku_desc_col = next(
        (c for c in df.columns if "sku" in c.lower() and "desc" in c.lower()), None
    )

    records: List[Dict] = []
    for _, row in df.iterrows():
        brand = str(row.get("vehicle-brand", "") or "").strip()
        if not brand or brand.lower() == "nan":
            continue

        def clean(val) -> str:
            v = str(val or "").strip()
            return "" if v.lower() in ("nan", "#value!") else v

        tyre_type_raw = clean(row.get("Type", ""))
        if tyre_type_raw == "TT":
            tyre_type_label = "Tube Type (TT)"
        elif tyre_type_raw == "TL":
            tyre_type_label = "Tubeless (TL)"
        else:
            tyre_type_label = tyre_type_raw

        position = clean(row.get("type", ""))
        if position.lower() == "font":
            position = "Front"

        rim_raw = clean(row.get("Rim Size", ""))
        # Drop rows where rim size is junk text (data error)
        try:
            float(rim_raw)
            rim_size = f'{int(float(rim_raw))}"'
        except (ValueError, TypeError):
            rim_size = rim_raw  # keep as-is if not numeric

        record = {
            "vehicle_brand": brand,
            "vehicle_model": clean(row.get("vehicle-model", "")),
            "vehicle_variant": clean(row.get("vehicle-variant", "")),
            "tyre_position": position,
            "sku": _clean_sku(row.get("recommended-sku", "")),
            "sku_description": clean(row.get(sku_desc_col, "")) if sku_desc_col else "",
            "aspect_ratio": clean(row.get("Aspect Ratio", "")),
            "rim_size": rim_size,
            "tyre_brand": clean(row.get("Brand", "")),
            "tyre_type": tyre_type_label,
            "tyre_name": clean(row.get("Tyre Name", "")),
            "construction": clean(row.get("Construction", "")),
        }
        records.append(record)

    return records


def records_to_documents(records: List[Dict]) -> Tuple[List[str], List[Dict], List[str]]:
    """
    Convert records into plain-text documents for embedding.
    Returns (documents, metadatas, ids).
    """
    documents: List[str] = []
    metadatas: List[Dict] = []
    ids: List[str] = []

    for i, r in enumerate(records):
        doc = (
            f"Vehicle: {r['vehicle_brand']} {r['vehicle_model']} {r['vehicle_variant']}\n"
            f"Tyre Position: {r['tyre_position']}\n"
            f"Recommended SKU: {r['sku']}\n"
            f"Tyre Description: {r['sku_description']}\n"
            f"Tyre Name: {r['tyre_name']}\n"
            f"Tyre Brand: {r['tyre_brand']}\n"
            f"Aspect Ratio: {r['aspect_ratio']}\n"
            f"Rim Size: {r['rim_size']}\n"
            f"Type: {r['tyre_type']}\n"
            f"Construction: {r['construction']}"
        )
        documents.append(doc)
        metadatas.append(r)
        ids.append(f"tyre_{i}")

    return documents, metadatas, ids


def get_unique_brands(records: List[Dict]) -> List[str]:
    seen = set()
    result = []
    for r in records:
        b = r["vehicle_brand"]
        if b and b not in seen:
            seen.add(b)
            result.append(b)
    return sorted(result)


def get_models_for_brand(records: List[Dict], brand: str) -> List[str]:
    seen = set()
    result = []
    for r in records:
        if r["vehicle_brand"].lower() == brand.lower() and r["vehicle_model"] not in seen:
            seen.add(r["vehicle_model"])
            result.append(r["vehicle_model"])
    return sorted(result)
