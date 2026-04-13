import argparse
import csv
import json
from pathlib import Path

import joblib

from recommendations import build_decision_support
from ml_utils import detect_input_anomalies, validate_payload


MODEL_PATH = Path("model") / "soil_model.joblib"
CALIBRATOR_PATH = Path("model") / "proba_calibrator.joblib"
LABEL_MAP_PATH = Path("model") / "label_map.json"

FIELD_ALIASES = {
    "ph": "ph",
    "humidite": "humidity",
    "humidity": "humidity",
    "temperature": "temperature",
    "azote": "nitrogen",
    "nitrogen": "nitrogen",
    "phosphore": "phosphorus",
    "phosphorus": "phosphorus",
    "potassium": "potassium",
    "pluviometrie": "rainfall",
    "rainfall": "rainfall",
    "type_sol": "soil_type",
    "soil_type": "soil_type",
    "type de sol": "soil_type",
}


def load_artifacts():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Modele introuvable. Lancez train_model.py avant.")

    model = joblib.load(MODEL_PATH)
    calibrator = joblib.load(CALIBRATOR_PATH) if CALIBRATOR_PATH.exists() else None
    label_map = {"0": "non_favorable", "1": "favorable"}
    if LABEL_MAP_PATH.exists():
        with LABEL_MAP_PATH.open("r", encoding="utf-8") as file:
            label_map = json.load(file)
    return model, calibrator, label_map


def decode_label(value, label_map):
    try:
        key = str(int(value))
        return label_map.get(key, str(value))
    except (TypeError, ValueError):
        return str(value)


def predict_single_item(model, calibrator, label_map, input_data):
    if calibrator is not None:
        proba = calibrator.predict_proba([input_data])[0]
        classes = list(calibrator.classes_)
        idx = int(proba.argmax())
        prediction = decode_label(classes[idx], label_map)
        confidence = float(proba[idx] * 100)
    else:
        raw_prediction = model.predict([input_data])[0]
        prediction = decode_label(raw_prediction, label_map)
        proba = model.predict_proba([input_data])[0]
        confidence = float(max(proba) * 100)

    support = build_decision_support(prediction, confidence, input_data)
    return prediction, confidence, support


def adjust_decision_confidence(raw_confidence, prediction_modele, decision_finale, anomalies):
    confidence = float(raw_confidence)
    if decision_finale != prediction_modele:
        confidence = min(confidence, 69.0)
    if anomalies:
        confidence = min(confidence, 55.0)
    return round(max(0.0, min(100.0, confidence)), 2)


def apply_decision_uncertainty(support, confidence):
    if confidence < 60:
        support["niveau_incertitude"] = "elevee"
        support["prediction_incertaine"] = True
    elif confidence < 75:
        support["niveau_incertitude"] = "moyenne"
        support["prediction_incertaine"] = True
    else:
        support["niveau_incertitude"] = "faible"
        support["prediction_incertaine"] = False


def normalize_row_keys(row):
    normalized = {}
    for key, value in row.items():
        key_clean = (key or "").strip().lower()
        target_key = FIELD_ALIASES.get(key_clean, key_clean)
        normalized[target_key] = value
    return normalized


def read_csv_rows(input_path):
    with input_path.open("r", encoding="utf-8", newline="") as file:
        content = file.read()

    first_line = content.splitlines()[0] if content.splitlines() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    rows = list(csv.DictReader(content.splitlines(), delimiter=delimiter))
    return [normalize_row_keys(row) for row in rows]

def predict_file(input_path, output_path):
    model, calibrator, label_map = load_artifacts()

    rows = read_csv_rows(input_path)

    results = []
    for i, row in enumerate(rows, start=1):
        try:
            is_valid, item = validate_payload(row)
            if not is_valid:
                raise ValueError(item)
            anomalies = detect_input_anomalies(item)
            prediction_modele, confidence_modele, support = predict_single_item(model, calibrator, label_map, item)
            decision_finale = support["decision_finale"]
            prediction = "a_verifier" if decision_finale == "a_verifier" else decision_finale
            confidence = adjust_decision_confidence(
                confidence_modele,
                prediction_modele,
                decision_finale,
                anomalies,
            )
            apply_decision_uncertainty(support, confidence)
            row_result = dict(row)
            row_result.update(
                {
                    "prediction_modele": prediction_modele,
                    "prediction": prediction,
                    "confiance": confidence,
                    "est_favorable": decision_finale == "favorable",
                    "recommandation_culture": ", ".join(support["cultures_recommandees"]),
                    "actions_recommandees": ", ".join(support["actions_recommandees"]),
                    "motif_decision": support["motif_decision"],
                    "niveau_incertitude": support["niveau_incertitude"],
                    "score_sol": support["soil_score"],
                    "niveau_sol": support["soil_level"],
                    "anomalies": " | ".join(anomalies),
                    "statut": "ok",
                    "erreur": "",
                }
            )
        except Exception as exc:
            row_result = dict(row)
            row_result.update(
                {
                    "prediction": "",
                    "confiance": "",
                    "est_favorable": "",
                    "recommandation_culture": "",
                    "statut": "erreur",
                    "erreur": str(exc),
                }
            )
            print(f"Ligne {i}: {exc}")

        results.append(row_result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(results[0].keys()) if results else []
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Predictions en lot terminees: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Prediction en lot sur fichier CSV")
    parser.add_argument("--input", required=True, help="Chemin du CSV d'entree")
    parser.add_argument("--output", default="data/predictions_batch.csv", help="Chemin du CSV de sortie")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {input_path}")

    predict_file(input_path, output_path)


if __name__ == "__main__":
    main()
