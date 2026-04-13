import csv
import json
from pathlib import Path

from app import get_db_connection
from ml_utils import REQUIRED_FIELDS, VALID_ACTUAL_LABELS
from train_model import main as train_main


DATASET_PATH = Path("data") / "soil_fertility.csv"
INGESTED_FEEDBACK_IDS_PATH = Path("data") / "feedback_ingested_ids.json"


def extract_feedback_rows():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, input_data, actual_label
        FROM analyses
        WHERE actual_label IS NOT NULL
        """
    ).fetchall()
    conn.close()

    out = []
    for row in rows:
        payload = json.loads(row["input_data"])
        actual = (row["actual_label"] or "").strip()
        if actual not in VALID_ACTUAL_LABELS:
            continue

        record = {key: payload.get(key) for key in REQUIRED_FIELDS}
        if any(record.get(key) in (None, "") for key in REQUIRED_FIELDS):
            continue
        record["label"] = actual
        record["analysis_id"] = int(row["id"])
        out.append(record)

    return out


def append_feedback_to_dataset(feedback_rows):
    if not feedback_rows:
        return 0

    ingested_ids = set()
    if INGESTED_FEEDBACK_IDS_PATH.exists():
        with INGESTED_FEEDBACK_IDS_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
            ingested_ids = {int(item) for item in data}

    new_rows = []
    for row in feedback_rows:
        analysis_id = int(row.get("analysis_id", -1))
        if analysis_id in ingested_ids:
            continue
        ingested_ids.add(analysis_id)
        row_to_append = dict(row)
        row_to_append.pop("analysis_id", None)
        new_rows.append(row_to_append)

    if not new_rows:
        return 0

    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = DATASET_PATH.exists()

    with DATASET_PATH.open("a", newline="", encoding="utf-8") as file:
        fieldnames = REQUIRED_FIELDS + ["label"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_rows)

    INGESTED_FEEDBACK_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INGESTED_FEEDBACK_IDS_PATH.open("w", encoding="utf-8") as file:
        json.dump(sorted(ingested_ids), file, indent=2)

    return len(new_rows)


def retrain_if_ready(min_feedback=20):
    feedback_rows = extract_feedback_rows()
    if len(feedback_rows) < min_feedback:
        return {
            "retrained": False,
            "reason": f"Feedback insuffisant ({len(feedback_rows)}/{min_feedback})",
            "feedback_rows": len(feedback_rows),
        }

    appended = append_feedback_to_dataset(feedback_rows)
    train_main()
    return {
        "retrained": True,
        "feedback_rows": len(feedback_rows),
        "rows_appended": appended,
    }


if __name__ == "__main__":
    result = retrain_if_ready(min_feedback=20)
    print(result)
