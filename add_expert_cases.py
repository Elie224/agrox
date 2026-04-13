import csv
from pathlib import Path


DATASET_PATH = Path("data") / "soil_fertility.csv"


def expert_cases():
    # Cas experts proposes pour renforcer la robustesse du modele.
    # Labels cibles definis selon logique agronomique terrain.
    return [
        {
            "ph": 5.6,
            "humidity": 35.0,
            "temperature": 27.0,
            "nitrogen": 18.0,
            "phosphorus": 14.0,
            "potassium": 145.0,
            "rainfall": 320.0,
            "soil_type": "sandy",
            "label": "non_favorable",
        },
        {
            "ph": 6.5,
            "humidity": 50.0,
            "temperature": 24.0,
            "nitrogen": 40.0,
            "phosphorus": 32.0,
            "potassium": 45.0,
            "rainfall": 1550.0,
            "soil_type": "loam",
            "label": "favorable",
        },
        {
            "ph": 6.8,
            "humidity": 60.0,
            "temperature": 26.0,
            "nitrogen": 85.0,
            "phosphorus": 65.0,
            "potassium": 80.0,
            "rainfall": 240.0,
            "soil_type": "loam",
            "label": "non_favorable",
        },
        {
            "ph": 6.3,
            "humidity": 48.0,
            "temperature": 27.0,
            "nitrogen": 36.0,
            "phosphorus": 28.0,
            "potassium": 42.0,
            "rainfall": 780.0,
            "soil_type": "silty",
            "label": "favorable",
        },
        {
            "ph": 7.4,
            "humidity": 70.0,
            "temperature": 25.0,
            "nitrogen": 32.0,
            "phosphorus": 24.0,
            "potassium": 130.0,
            "rainfall": 1200.0,
            "soil_type": "sandy",
            "label": "non_favorable",
        },
        {
            "ph": 6.2,
            "humidity": 88.0,
            "temperature": 29.0,
            "nitrogen": 34.0,
            "phosphorus": 30.0,
            "potassium": 48.0,
            "rainfall": 420.0,
            "soil_type": "hydromorphe",
            "label": "non_favorable",
        },
        {
            "ph": 8.1,
            "humidity": 72.0,
            "temperature": 30.0,
            "nitrogen": 38.0,
            "phosphorus": 22.0,
            "potassium": 44.0,
            "rainfall": 1350.0,
            "soil_type": "loam",
            "label": "non_favorable",
        },
        {
            "ph": 6.4,
            "humidity": 86.0,
            "temperature": 27.0,
            "nitrogen": 40.0,
            "phosphorus": 28.0,
            "potassium": 55.0,
            "rainfall": 680.0,
            "soil_type": "hydromorphe",
            "label": "non_favorable",
        },
        {
            "ph": 7.3,
            "humidity": 52.0,
            "temperature": 31.0,
            "nitrogen": 35.0,
            "phosphorus": 24.0,
            "potassium": 120.0,
            "rainfall": 920.0,
            "soil_type": "salin",
            "label": "non_favorable",
        },
    ]


def row_key(row):
    ordered = (
        row["ph"],
        row["humidity"],
        row["temperature"],
        row["nitrogen"],
        row["phosphorus"],
        row["potassium"],
        row["rainfall"],
        row["soil_type"],
        row["label"],
    )
    return "|".join(str(item) for item in ordered)


def normalize_dataset_row(row):
    return {
        "ph": float(row["ph"]),
        "humidity": float(row["humidity"]),
        "temperature": float(row["temperature"]),
        "nitrogen": float(row["nitrogen"]),
        "phosphorus": float(row["phosphorus"]),
        "potassium": float(row["potassium"]),
        "rainfall": float(row["rainfall"]),
        "soil_type": (row["soil_type"] or "").strip().lower(),
        "label": (row["label"] or "").strip().lower(),
    }


def append_expert_cases():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset introuvable: {DATASET_PATH}")

    with DATASET_PATH.open("r", encoding="utf-8") as file:
        existing_rows = list(csv.DictReader(file))

    existing_keys = {row_key(normalize_dataset_row(row)) for row in existing_rows}

    to_add = []
    for case in expert_cases():
        key = row_key(case)
        if key not in existing_keys:
            to_add.append(case)

    if not to_add:
        return {"added": 0, "total": len(existing_rows)}

    with DATASET_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "ph",
                "humidity",
                "temperature",
                "nitrogen",
                "phosphorus",
                "potassium",
                "rainfall",
                "soil_type",
                "label",
            ],
        )
        writer.writerows(to_add)

    return {"added": len(to_add), "total": len(existing_rows) + len(to_add)}


if __name__ == "__main__":
    result = append_expert_cases()
    print(result)
