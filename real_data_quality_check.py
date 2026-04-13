from pathlib import Path
import csv
import json
import os

REQUIRED_COLUMNS = {
    "ph",
    "humidity",
    "temperature",
    "nitrogen",
    "phosphorus",
    "potassium",
    "rainfall",
    "soil_type",
    "label",
}

NUMERIC_COLUMNS = [
    "ph",
    "humidity",
    "temperature",
    "nitrogen",
    "phosphorus",
    "potassium",
    "rainfall",
]


def parse_float(value):
    if value is None:
        raise ValueError("none")
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    return float(value)


def detect_range_issue(row):
    issues = []
    ph = parse_float(row["ph"])
    humidity = parse_float(row["humidity"])
    temperature = parse_float(row["temperature"])
    n = parse_float(row["nitrogen"])
    p = parse_float(row["phosphorus"])
    k = parse_float(row["potassium"])
    rainfall = parse_float(row["rainfall"])

    if ph < 3.5 or ph > 10:
        issues.append("ph_extreme")
    if humidity < 0 or humidity > 100:
        issues.append("humidity_extreme")
    if temperature < -5 or temperature > 60:
        issues.append("temperature_extreme")
    if n < 0 or p < 0 or k < 0:
        issues.append("npk_negative")
    if rainfall < 0 or rainfall > 5000:
        issues.append("rainfall_extreme")

    return issues


def main():
    raw_path = (os.getenv("AGROX_DATA_PATH") or "data/soil_fertility_real.csv").strip()
    data_path = Path(raw_path)

    if not data_path.exists():
        raise FileNotFoundError(f"Dataset introuvable: {data_path}")

    with data_path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        raise ValueError("Dataset vide")

    missing_columns = sorted(REQUIRED_COLUMNS - set(rows[0].keys()))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes: {missing_columns}")

    missing_values = {col: 0 for col in REQUIRED_COLUMNS}
    invalid_numeric_rows = 0
    range_issue_rows = 0
    label_counts = {}

    for row in rows:
        for col in REQUIRED_COLUMNS:
            if (row.get(col) or "").strip() == "":
                missing_values[col] += 1

        for col in NUMERIC_COLUMNS:
            try:
                parse_float(row.get(col))
            except Exception:
                invalid_numeric_rows += 1
                break

        try:
            issues = detect_range_issue(row)
            if issues:
                range_issue_rows += 1
        except Exception:
            range_issue_rows += 1

        label = (row.get("label") or "").strip().lower()
        label_counts[label] = label_counts.get(label, 0) + 1

    total = len(rows)
    report = {
        "dataset_path": str(data_path),
        "row_count": total,
        "missing_columns": missing_columns,
        "missing_values": missing_values,
        "invalid_numeric_rows": invalid_numeric_rows,
        "range_issue_rows": range_issue_rows,
        "label_distribution": label_counts,
        "quality_flags": {
            "enough_rows": total >= 200,
            "balanced_labels": len(label_counts) >= 2,
            "low_missing_values": sum(missing_values.values()) <= total,
            "low_invalid_numeric": invalid_numeric_rows <= max(3, int(total * 0.01)),
            "low_range_issues": range_issue_rows <= max(5, int(total * 0.02)),
        },
    }

    output_path = Path("docs") / "rapport_qualite_donnees_reelles.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(f"Rapport qualite genere: {output_path}")
    print(json.dumps(report["quality_flags"], ensure_ascii=False))


if __name__ == "__main__":
    main()
