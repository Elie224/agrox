import random
import csv
from pathlib import Path


SOIL_TYPES = ["sandy", "clay", "loam", "silty"]


def score_row(ph, humidity, temperature, n, p, k, rainfall, soil_type):
    score = 0

    if 6.0 <= ph <= 7.5:
        score += 2
    elif 5.5 <= ph <= 8.0:
        score += 1

    if 40 <= humidity <= 75:
        score += 2
    elif 30 <= humidity <= 85:
        score += 1

    if 18 <= temperature <= 33:
        score += 2
    elif 12 <= temperature <= 38:
        score += 1

    npk_mean = (n + p + k) / 3
    if 35 <= npk_mean <= 85:
        score += 2
    elif 20 <= npk_mean <= 95:
        score += 1

    if 500 <= rainfall <= 1600:
        score += 1

    if soil_type in {"loam", "silty"}:
        score += 1

    return "favorable" if score >= 7 else "non_favorable"


def generate_dataset(n_rows=1200, seed=42):
    random.seed(seed)
    rows = []

    for _ in range(n_rows):
        soil_type = random.choice(SOIL_TYPES)
        row = {
            "ph": round(random.uniform(4.5, 9.0), 2),
            "humidity": round(random.uniform(15, 95), 2),
            "temperature": round(random.uniform(10, 42), 2),
            "nitrogen": round(random.uniform(5, 120), 2),
            "phosphorus": round(random.uniform(5, 120), 2),
            "potassium": round(random.uniform(5, 120), 2),
            "rainfall": round(random.uniform(200, 2200), 2),
            "soil_type": soil_type,
        }

        row["label"] = score_row(
            row["ph"],
            row["humidity"],
            row["temperature"],
            row["nitrogen"],
            row["phosphorus"],
            row["potassium"],
            row["rainfall"],
            row["soil_type"],
        )
        rows.append(row)

    return rows


def main():
    output_path = Path("data") / "soil_fertility.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = generate_dataset()
    fieldnames = [
        "ph",
        "humidity",
        "temperature",
        "nitrogen",
        "phosphorus",
        "potassium",
        "rainfall",
        "soil_type",
        "label",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Dataset generated: {output_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
