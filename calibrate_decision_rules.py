import csv
import json
from pathlib import Path

from decision_rules import DEFAULT_RULES, save_decision_rules


DATASET_PATH = Path("data") / "soil_fertility.csv"
DB_PATH = Path("data") / "history.db"


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    idx = (len(ordered) - 1) * (float(p) / 100.0)
    low = int(idx)
    high = min(low + 1, len(ordered) - 1)
    frac = idx - low
    return float(ordered[low] * (1.0 - frac) + ordered[high] * frac)


def load_csv_rows():
    if not DATASET_PATH.exists():
        return []

    with DATASET_PATH.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = []
        for row in reader:
            label = (row.get("label") or "").strip()
            if label not in {"favorable", "non_favorable"}:
                continue
            try:
                rows.append(
                    {
                        "nitrogen": float(row["nitrogen"]),
                        "phosphorus": float(row["phosphorus"]),
                        "potassium": float(row["potassium"]),
                        "label": label,
                    }
                )
            except (TypeError, ValueError, KeyError):
                continue
    return rows


def load_feedback_rows():
    if not DB_PATH.exists():
        return []

    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT input_data, actual_label
        FROM analyses
        WHERE actual_label IS NOT NULL
        """
    ).fetchall()
    conn.close()

    feedback_rows = []
    for row in rows:
        try:
            payload = json.loads(row["input_data"])
            label = (row["actual_label"] or "").strip()
            if label not in {"favorable", "non_favorable"}:
                continue
            feedback_rows.append(
                {
                    "nitrogen": float(payload["nitrogen"]),
                    "phosphorus": float(payload["phosphorus"]),
                    "potassium": float(payload["potassium"]),
                    "label": label,
                }
            )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            continue
    return feedback_rows


def evaluate_rule(rows, rule):
    tp = 0
    fp = 0
    fn = 0

    for row in rows:
        severe = (
            row["potassium"] > rule["k_severe_high"]
            or row["nitrogen"] > rule["n_severe_high"]
            or (row["phosphorus"] < rule["p_severe_low"] and row["potassium"] > rule["k_pair_high"])
        )
        actual_non_favorable = row["label"] == "non_favorable"

        if severe and actual_non_favorable:
            tp += 1
        elif severe and not actual_non_favorable:
            fp += 1
        elif (not severe) and actual_non_favorable:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    score = precision * 0.75 + recall * 0.25
    return {
        "precision_non_favorable": round(precision, 4),
        "recall_non_favorable": round(recall, 4),
        "f1_non_favorable": round(f1, 4),
        "score": score,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def calibrate_npk_rules(rows):
    favorable = [row for row in rows if row["label"] == "favorable"]
    if len(favorable) < 40:
        return None, {"reason": "Pas assez de lignes favorables pour calibrer"}

    fav_n = [row["nitrogen"] for row in favorable]
    fav_p = [row["phosphorus"] for row in favorable]
    fav_k = [row["potassium"] for row in favorable]

    k_high_candidates = [percentile(fav_k, p) for p in (85, 90, 92, 95, 97)]
    n_high_candidates = [percentile(fav_n, p) for p in (85, 90, 92, 95, 97)]
    p_low_candidates = [percentile(fav_p, p) for p in (3, 5, 8, 10, 12, 15)]
    k_pair_candidates = [percentile(fav_k, p) for p in (75, 80, 85, 90)]

    best_rule = None
    best_eval = None

    for k_high in k_high_candidates:
        for n_high in n_high_candidates:
            for p_low in p_low_candidates:
                for k_pair in k_pair_candidates:
                    rule = {
                        "k_severe_high": round(float(k_high), 2),
                        "n_severe_high": round(float(n_high), 2),
                        "p_severe_low": round(float(p_low), 2),
                        "k_pair_high": round(float(k_pair), 2),
                    }
                    metrics = evaluate_rule(rows, rule)

                    if best_eval is None or metrics["score"] > best_eval["score"]:
                        best_rule = rule
                        best_eval = metrics

    return best_rule, best_eval


def apply_agronomic_guardrails(rule):
    if not rule:
        return rule
    bounded = dict(rule)
    bounded["k_severe_high"] = max(float(bounded.get("k_severe_high", 140.0)), 140.0)
    bounded["n_severe_high"] = max(float(bounded.get("n_severe_high", 150.0)), 150.0)
    bounded["p_severe_low"] = min(float(bounded.get("p_severe_low", 25.0)), 25.0)
    bounded["k_pair_high"] = max(float(bounded.get("k_pair_high", 120.0)), 120.0)
    return {k: round(float(v), 2) for k, v in bounded.items()}


def calibrate_and_save():
    csv_rows = load_csv_rows()
    feedback_rows = load_feedback_rows()
    rows = csv_rows + feedback_rows

    if len(rows) < 100:
        return {
            "saved": False,
            "reason": f"Donnees insuffisantes pour calibrer ({len(rows)} lignes)",
            "rows": len(rows),
        }

    npk_rules, eval_metrics = calibrate_npk_rules(rows)
    if npk_rules is None:
        return {
            "saved": False,
            "reason": eval_metrics.get("reason", "Calibration impossible"),
            "rows": len(rows),
        }

    bounded_npk_rules = apply_agronomic_guardrails(npk_rules)

    rules = {
        "npk": bounded_npk_rules,
        "confidence": DEFAULT_RULES["confidence"],
        "metadata": {
            "source_rows_total": len(rows),
            "source_rows_csv": len(csv_rows),
            "source_rows_feedback": len(feedback_rows),
            "evaluation": eval_metrics,
            "npk_calibres_bruts": npk_rules,
        },
    }
    save_decision_rules(rules)

    return {
        "saved": True,
        "rows": len(rows),
        "npk": bounded_npk_rules,
        "evaluation": eval_metrics,
    }


if __name__ == "__main__":
    print(calibrate_and_save())
