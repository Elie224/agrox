import json
import sqlite3
import csv
import os
import io
import threading
from functools import wraps
from datetime import datetime, UTC
from pathlib import Path

import joblib
from openpyxl import Workbook
from flask import Flask, jsonify, render_template, request, send_file
from recommendations import build_decision_support
from ml_utils import VALID_ACTUAL_LABELS, validate_payload, detect_input_anomalies
from weather_service import fetch_weather_forecast
from decision_rules import load_decision_rules
from calibrate_decision_rules import calibrate_and_save


BASE_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
MODEL_PATH = BASE_DIR / "model" / "soil_model.joblib"
CALIBRATOR_PATH = BASE_DIR / "model" / "proba_calibrator.joblib"
LABEL_MAP_PATH = BASE_DIR / "model" / "label_map.json"
METRICS_PATH = BASE_DIR / "model" / "metrics.json"
DB_PATH = BASE_DIR / "data" / "history.db"

model = None
calibrateur = None
label_map = {"0": "non_favorable", "1": "favorable"}
_runtime_initialized = False
_runtime_lock = threading.Lock()


def decode_label(value):
    try:
        key = str(int(value))
        return label_map.get(key, str(value))
    except (TypeError, ValueError):
        return str(value)


def get_local_feature_contributions(input_data, top_n=5):
    vectorizer = model.named_steps["vectorizer"]
    classifier = model.named_steps["classifier"]

    transformed = vectorizer.transform([input_data])[0]
    feature_names = vectorizer.get_feature_names_out()
    importances = classifier.feature_importances_

    raw_contributions = []
    for feature_name, feature_value, importance in zip(feature_names, transformed, importances):
        score = float(abs(feature_value) * importance)
        if score <= 0:
            continue
        raw_contributions.append((feature_name, score))

    total_score = sum(score for _, score in raw_contributions) or 1.0
    contributions = [
        {
            "facteur": feature_name,
            "influence": round(score / total_score * 100.0, 2),
        }
        for feature_name, score in raw_contributions
    ]

    contributions.sort(key=lambda item: item["influence"], reverse=True)
    return contributions[:top_n]


def enrich_with_weather_if_needed(payload, validated_input):
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    meteo = None

    if latitude in (None, "") or longitude in (None, ""):
        return validated_input, meteo

    try:
        weather = fetch_weather_forecast(float(latitude), float(longitude))
        enriched = dict(validated_input)
        enriched["future_rainfall"] = weather["future_rainfall"]
        enriched["temperature_forecast"] = weather["temperature_forecast"]
        meteo = {
            "source_meteo": weather["source"],
            "future_rainfall": round(weather["future_rainfall"], 2),
            "temperature_forecast": round(weather["temperature_forecast"], 2),
        }
        return enriched, meteo
    except Exception as exc:
        _ = exc
        meteo = {"erreur": "Contexte meteo indisponible"}
        return validated_input, meteo


def require_admin(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        expected_key = (os.getenv("ADMIN_API_KEY") or "").strip()
        if not expected_key:
            return view_func(*args, **kwargs)

        provided_key = (request.headers.get("X-Admin-Key") or "").strip()
        if provided_key != expected_key:
            return jsonify({"erreur": "Acces admin non autorise"}), 401
        return view_func(*args, **kwargs)

    return wrapper


def get_db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            input_data TEXT NOT NULL,
            prediction TEXT NOT NULL,
            confidence REAL NOT NULL,
            actual_label TEXT
        )
        """
    )
    conn.execute("PRAGMA table_info(analyses)")
    columns = [row[1] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()]
    if "actual_label" not in columns:
        conn.execute("ALTER TABLE analyses ADD COLUMN actual_label TEXT")
    conn.commit()
    conn.close()


def load_model():
    global model, calibrateur, label_map
    if MODEL_PATH.exists():
        model = joblib.load(MODEL_PATH)
    if CALIBRATOR_PATH.exists():
        calibrateur = joblib.load(CALIBRATOR_PATH)
    if LABEL_MAP_PATH.exists():
        with LABEL_MAP_PATH.open("r", encoding="utf-8") as file:
            label_map = json.load(file)


def initialize_runtime():
    global _runtime_initialized
    if _runtime_initialized:
        return
    with _runtime_lock:
        if _runtime_initialized:
            return
        init_db()
        load_model()
        _runtime_initialized = True


def save_history(input_data, prediction, confidence):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO analyses (created_at, input_data, prediction, confidence) VALUES (?, ?, ?, ?)",
        (
            datetime.now(UTC).isoformat(timespec="seconds"),
            json.dumps(input_data),
            prediction,
            confidence,
        ),
    )
    conn.commit()
    conn.close()


def fetch_history(limit=100):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, created_at, input_data, prediction, confidence, actual_label FROM analyses ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append(
            {
                "id": row["id"],
                "date_creation": row["created_at"],
                "donnees_entree": json.loads(row["input_data"]),
                "prediction": row["prediction"],
                "confiance": row["confidence"],
                "actual_label": row["actual_label"],
            }
        )
    return history


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values):
    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    var = sum((x - mu) ** 2 for x in values) / len(values)
    return var ** 0.5


def compute_monitoring_stats(rows):
    if not rows:
        return {
            "anomaly_rate_recent": 0.0,
            "a_verifier_rate_recent": 0.0,
            "confidence_recent": 0.0,
            "drift_index": 0.0,
            "drift_level": "faible",
            "monitoring_message": "Aucune analyse recente disponible pour le monitoring.",
        }

    latest_rows = rows[:60]
    recent = latest_rows[:30]
    baseline = latest_rows[30:60]

    anomaly_count = 0
    a_verifier_count = 0
    confidence_values = []

    numeric_fields = ["ph", "humidity", "temperature", "nitrogen", "phosphorus", "potassium", "rainfall"]
    recent_by_field = {field: [] for field in numeric_fields}
    baseline_by_field = {field: [] for field in numeric_fields}

    for row in recent:
        input_data = json.loads(row["input_data"])
        anomalies = detect_input_anomalies(input_data)
        if anomalies:
            anomaly_count += 1
        if row["prediction"] == "a_verifier":
            a_verifier_count += 1
        confidence_values.append(float(row["confidence"]))
        for field in numeric_fields:
            v = _safe_float(input_data.get(field))
            if v is not None:
                recent_by_field[field].append(v)

    for row in baseline:
        input_data = json.loads(row["input_data"])
        for field in numeric_fields:
            v = _safe_float(input_data.get(field))
            if v is not None:
                baseline_by_field[field].append(v)

    drift_components = []
    if baseline:
        for field in numeric_fields:
            recent_vals = recent_by_field[field]
            base_vals = baseline_by_field[field]
            if not recent_vals or not base_vals:
                continue
            delta = abs(_mean(recent_vals) - _mean(base_vals))
            scale = _std(base_vals) + 1e-6
            drift_components.append(delta / scale)

    drift_index = _mean(drift_components)
    if drift_index >= 0.75:
        drift_level = "eleve"
        monitoring_message = "Drift eleve detecte: verifier les donnees terrain et envisager un reentrainement."
    elif drift_index >= 0.35:
        drift_level = "moyen"
        monitoring_message = "Drift modere detecte: surveiller les prochains lots d'analyses."
    else:
        drift_level = "faible"
        monitoring_message = "Systeme stable: pas de drift significatif detecte."

    total_recent = len(recent) or 1
    return {
        "anomaly_rate_recent": round(anomaly_count / total_recent * 100.0, 2),
        "a_verifier_rate_recent": round(a_verifier_count / total_recent * 100.0, 2),
        "confidence_recent": round(_mean(confidence_values), 2),
        "drift_index": round(drift_index, 3),
        "drift_level": drift_level,
        "monitoring_message": monitoring_message,
    }


def compute_dashboard_stats():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT created_at, input_data, prediction, confidence, actual_label FROM analyses ORDER BY id DESC"
    ).fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        return {
            "total_analyses": 0,
            "taux_favorable": 0.0,
            "confiance_moyenne": 0.0,
            "nombre_feedbacks": 0,
            "precision_terrain": 0.0,
            "repartition_par_type_sol": [],
            "tendance_7_jours": [],
            "monitoring": compute_monitoring_stats([]),
        }

    favorable_count = 0
    confidence_sum = 0.0
    feedback_count = 0
    evaluated_feedback_count = 0
    correct_count = 0
    soil_stats = {}
    daily_counts = {}

    for row in rows:
        prediction = row["prediction"]
        confidence = float(row["confidence"])
        actual_label = row["actual_label"]
        input_data = json.loads(row["input_data"])
        soil_type = input_data.get("soil_type", "inconnu")
        day = str(row["created_at"]).split("T")[0]

        if prediction == "favorable":
            favorable_count += 1
        confidence_sum += confidence

        if actual_label is not None:
            feedback_count += 1
            if prediction in VALID_ACTUAL_LABELS:
                evaluated_feedback_count += 1
            if prediction in VALID_ACTUAL_LABELS and actual_label == prediction:
                correct_count += 1

        if soil_type not in soil_stats:
            soil_stats[soil_type] = {"total": 0, "favorable": 0}
        soil_stats[soil_type]["total"] += 1
        if prediction == "favorable":
            soil_stats[soil_type]["favorable"] += 1

        daily_counts[day] = daily_counts.get(day, 0) + 1

    repartition = []
    for soil_type, stats in soil_stats.items():
        favorable_rate = (stats["favorable"] / stats["total"] * 100.0) if stats["total"] else 0.0
        repartition.append(
            {
                "soil_type": soil_type,
                "total": stats["total"],
                "favorable_rate": round(favorable_rate, 2),
            }
        )

    repartition.sort(key=lambda item: item["total"], reverse=True)

    trend_days = sorted(daily_counts.keys())[-7:]
    trend = [{"date": day, "count": daily_counts[day]} for day in trend_days]

    precision_terrain = (correct_count / evaluated_feedback_count * 100.0) if evaluated_feedback_count else 0.0

    return {
        "total_analyses": total,
        "taux_favorable": round(favorable_count / total * 100.0, 2),
        "confiance_moyenne": round(confidence_sum / total, 2),
        "nombre_feedbacks": feedback_count,
        "nombre_feedbacks_evalues": evaluated_feedback_count,
        "precision_terrain": round(precision_terrain, 2),
        "repartition_par_type_sol": repartition,
        "tendance_7_jours": trend,
        "monitoring": compute_monitoring_stats(rows),
    }


def predict_single_item(input_data):
    if calibrateur is not None:
        proba = calibrateur.predict_proba([input_data])[0]
        classes = list(calibrateur.classes_)
        idx = int(proba.argmax())
        prediction = decode_label(classes[idx])
        confidence = float(proba[idx] * 100)
    else:
        raw_prediction = model.predict([input_data])[0]
        prediction = decode_label(raw_prediction)
        proba = model.predict_proba([input_data])[0]
        confidence = float(max(proba) * 100)
    support = build_decision_support(prediction, confidence, input_data)
    return prediction, confidence, support


def adjust_decision_confidence(raw_confidence, prediction_modele, decision_finale, anomalies):
    confidence = float(raw_confidence)

    # Si la decision finale est forcee par des regles, la confiance terrain doit etre plus prudente.
    if decision_finale != prediction_modele:
        confidence = min(confidence, 69.0)

    # Des donnees suspectes degradent fortement la confiance operationnelle.
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


def apply_responsible_mode(prediction_affichage, decision_finale, support, confidence, anomalies):
    motifs = []
    if anomalies:
        motifs.append("Donnees d'entree atypiques")
    if float(confidence) < 65.0:
        motifs.append("Confiance operationnelle insuffisante")
    if support.get("niveau_incertitude") in {"elevee", "moyenne"}:
        motifs.append("Incertitude predictive notable")

    if not motifs:
        return prediction_affichage, decision_finale, support, {
            "active": False,
            "message": "Aucun risque majeur detecte, decision automatisable.",
            "motifs": [],
        }

    # Ne pas annuler une decision non favorable critique deja etablie.
    if decision_finale == "non_favorable":
        support["prediction_incertaine"] = True
        if support.get("niveau_incertitude") == "faible":
            support["niveau_incertitude"] = "moyenne"
        return "non_favorable", "non_favorable", support, {
            "active": True,
            "message": "Mode prudent actif: decision non favorable maintenue, verification humaine recommandee.",
            "motifs": motifs,
        }

    support["decision_finale"] = "a_verifier"
    support["motif_decision"] = "Mode responsable active: verification humaine requise"
    support["prediction_incertaine"] = True
    support["niveau_incertitude"] = "elevee"
    support["cultures_recommandees"] = ["Validation terrain par un agronome recommandee"]

    safe_actions = [
        "Verifier les mesures (capteurs / prelevement)",
        "Confirmer la decision avec un conseiller agronome",
        "Lancer un essai sur petite parcelle avant generalisation",
    ]
    existing_actions = support.get("actions_recommandees") or []
    merged_actions = []
    for action in safe_actions + existing_actions:
        if action not in merged_actions:
            merged_actions.append(action)
    support["actions_recommandees"] = merged_actions

    return "a_verifier", "a_verifier", support, {
        "active": True,
        "message": "Mode prudent active: ne pas appliquer automatiquement sans verification humaine.",
        "motifs": motifs,
    }


def has_critical_anomaly(anomalies):
    if not anomalies:
        return False
    critical_tokens = [
        "suspecte",
        "anormalement",
        "incoherence",
        "hors plage",
    ]
    for item in anomalies:
        text = str(item).lower()
        if any(token in text for token in critical_tokens):
            return True
    return False


def apply_score_reliability_policy(support, anomalies):
    if not has_critical_anomaly(anomalies):
        return {
            "score_fiable": True,
            "score_message": "Score interpretable.",
        }

    support["soil_score"] = None
    support["soil_level"] = "non_fiable"
    support["gravite_probleme"] = "critique"
    support["alerte_principale"] = "Donnees incoherentes detectees"
    return {
        "score_fiable": False,
        "score_message": "Score non fiable (donnees incoherentes detectees).",
    }


def sanitize_explanations_for_anomalies(explanations, anomalies):
    if not has_critical_anomaly(anomalies):
        return explanations

    blocked_factors = set()
    anomaly_text = " ".join(str(item).lower() for item in anomalies)
    if "pluviometrie" in anomaly_text or "pluie" in anomaly_text:
        blocked_factors.update({"rainfall", "future_rainfall", "rainfall_ratio_forecast"})
    if "humidite" in anomaly_text:
        blocked_factors.add("humidity")
    if "temperature" in anomaly_text:
        blocked_factors.update({"temperature", "temperature_forecast", "temperature_delta_forecast"})

    if not blocked_factors:
        return explanations

    sanitized = [item for item in explanations if str(item.get("facteur")) not in blocked_factors]
    return sanitized


@app.route("/")
def index():
    return render_template("index.html")


@app.before_request
def ensure_runtime_initialized():
    initialize_runtime()


@app.route("/health")
def health():
    return jsonify({"statut": "ok", "modele_charge": model is not None})


@app.route("/ready")
def ready():
    checks = {
        "model_loaded": model is not None,
        "database_ok": False,
        "decision_rules_ok": False,
    }

    db_error = None
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["database_ok"] = True
    except Exception as exc:
        db_error = str(exc)

    rules_error = None
    try:
        rules = load_decision_rules(force_reload=False)
        checks["decision_rules_ok"] = isinstance(rules, dict) and bool(rules)
    except Exception as exc:
        rules_error = str(exc)

    ready_state = all(checks.values())
    payload = {
        "statut": "ready" if ready_state else "not_ready",
        "checks": checks,
    }
    if db_error:
        payload["database_error"] = db_error
    if rules_error:
        payload["decision_rules_error"] = rules_error

    return jsonify(payload), (200 if ready_state else 503)


@app.route("/modele/info", methods=["GET"])
def model_info():
    if not METRICS_PATH.exists():
        return jsonify({"erreur": "Métriques indisponibles"}), 404

    with METRICS_PATH.open("r", encoding="utf-8") as file:
        metrics = json.load(file)

    return jsonify(
        {
            "algorithme": metrics.get("algorithm"),
            "date_entrainement": metrics.get("training_datetime_utc"),
            "f1_cv": metrics.get("search", {}).get("best_cv_score_f1_weighted"),
            "precision_test": metrics.get("test_metrics", {}).get("accuracy"),
            "accuracy_test": metrics.get("test_metrics", {}).get("accuracy"),
            "log_loss": metrics.get("test_metrics", {}).get("log_loss"),
        }
    )


@app.route("/regles/info", methods=["GET"])
def rules_info():
    return jsonify(load_decision_rules(force_reload=True))


@app.route("/regles/calibrer", methods=["POST"])
@require_admin
def rules_calibrate():
    result = calibrate_and_save()
    status_code = 200 if result.get("saved") else 202
    return jsonify(result), status_code


@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return (
            jsonify(
                {
                    "erreur": "Modèle introuvable. Lancez train_model.py d'abord.",
                }
            ),
            500,
        )

    payload = request.get_json(silent=True) or {}
    is_valid, result = validate_payload(payload)
    if not is_valid:
        return jsonify({"erreur": result}), 400

    anomalies = detect_input_anomalies(result)
    input_data, meteo = enrich_with_weather_if_needed(payload, result)

    prediction, confidence, support = predict_single_item(input_data)
    explain = get_local_feature_contributions(input_data)
    decision_finale = support["decision_finale"]
    prediction_affichage = "a_verifier" if decision_finale == "a_verifier" else decision_finale
    confiance_decision = adjust_decision_confidence(confidence, prediction, decision_finale, anomalies)
    apply_decision_uncertainty(support, confiance_decision)
    prediction_affichage, decision_finale, support, avis_responsable = apply_responsible_mode(
        prediction_affichage,
        decision_finale,
        support,
        confiance_decision,
        anomalies,
    )
    score_policy = apply_score_reliability_policy(support, anomalies)
    explain = sanitize_explanations_for_anomalies(explain, anomalies)

    save_history(input_data, prediction_affichage, confiance_decision)

    return jsonify(
        {
            "prediction_modele": prediction,
            "prediction": prediction_affichage,
            "decision_finale": decision_finale,
            "motif_decision": support["motif_decision"],
            "confiance": confiance_decision,
            "est_favorable": decision_finale == "favorable",
            "recommandations_culture": support["cultures_recommandees"],
            "actions_recommandees": support["actions_recommandees"],
            "raisons_principales": support["raisons_principales"],
            "prediction_incertaine": support["prediction_incertaine"],
            "niveau_incertitude": support["niveau_incertitude"],
            "score_sol": support["soil_score"],
            "niveau_sol": support["soil_level"],
            "score_fiable": score_policy["score_fiable"],
            "message_score": score_policy["score_message"],
            "gravite_probleme": support.get("gravite_probleme"),
            "alerte_principale": support.get("alerte_principale"),
            "donnees_suspectes": len(anomalies) > 0,
            "anomalies": anomalies,
            "mode_responsable": avis_responsable["active"],
            "avis_responsable": avis_responsable["message"],
            "motifs_responsable": avis_responsable["motifs"],
            "explication_locale": explain,
            "contexte_meteo": meteo,
        }
    )


@app.route("/predict/batch", methods=["POST"])
def predict_batch():
    if model is None:
        return jsonify({"erreur": "Modèle introuvable. Lancez train_model.py d'abord."}), 500

    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"erreur": "Fichier CSV manquant"}), 400

    if not file.filename.lower().endswith(".csv"):
        return jsonify({"erreur": "Le fichier doit etre au format CSV"}), 400

    try:
        content = file.stream.read().decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({"erreur": "Encodage invalide. Utilisez UTF-8."}), 400

    first_line = content.splitlines()[0] if content.splitlines() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return jsonify({"erreur": "Le fichier CSV est vide"}), 400

    output_rows = []
    success_count = 0
    error_count = 0

    for row in rows:
        is_valid, result = validate_payload(row)
        row_result = dict(row)
        if not is_valid:
            row_result.update(
                {
                    "prediction": "",
                    "confiance": "",
                    "est_favorable": "",
                    "recommandations_culture": "",
                    "statut": "erreur",
                    "erreur": result,
                }
            )
            error_count += 1
            output_rows.append(row_result)
            continue

        enriched_input, _meteo = enrich_with_weather_if_needed(row, result)
        prediction, confidence, support = predict_single_item(enriched_input)
        anomalies = detect_input_anomalies(result)
        decision_finale = support["decision_finale"]
        prediction_affichage = "a_verifier" if decision_finale == "a_verifier" else decision_finale
        confiance_decision = adjust_decision_confidence(confidence, prediction, decision_finale, anomalies)

        apply_decision_uncertainty(support, confiance_decision)
        prediction_affichage, decision_finale, support, avis_responsable = apply_responsible_mode(
            prediction_affichage,
            decision_finale,
            support,
            confiance_decision,
            anomalies,
        )
        score_policy = apply_score_reliability_policy(support, anomalies)

        save_history(enriched_input, prediction_affichage, confiance_decision)

        row_result.update(
            {
            "prediction_modele": prediction,
            "prediction": prediction_affichage,
                "confiance": confiance_decision,
            "est_favorable": decision_finale == "favorable",
                "recommandations_culture": ", ".join(support["cultures_recommandees"]),
                "actions_recommandees": ", ".join(support["actions_recommandees"]),
                "niveau_incertitude": support["niveau_incertitude"],
                "score_sol": support["soil_score"],
                "niveau_sol": support["soil_level"],
                "score_fiable": score_policy["score_fiable"],
                "message_score": score_policy["score_message"],
                "gravite_probleme": support.get("gravite_probleme"),
                "alerte_principale": support.get("alerte_principale"),
                "donnees_suspectes": len(anomalies) > 0,
                "anomalies": " | ".join(anomalies),
                "mode_responsable": avis_responsable["active"],
                "avis_responsable": avis_responsable["message"],
                "motifs_responsable": " | ".join(avis_responsable["motifs"]),
                "statut": "ok",
                "erreur": "",
            }
        )
        success_count += 1
        output_rows.append(row_result)

    fieldnames = []
    for item in output_rows:
        for key in item.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)
    payload = io.BytesIO(csv_buffer.getvalue().encode("utf-8"))
    payload.seek(0)

    response = send_file(
        payload,
        as_attachment=True,
        download_name="predictions_batch_resultats.csv",
        mimetype="text/csv",
    )
    response.headers["X-Lot-Total"] = str(len(rows))
    response.headers["X-Lot-Succes"] = str(success_count)
    response.headers["X-Lot-Erreurs"] = str(error_count)
    return response


@app.route("/history", methods=["GET"])
def history():
    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 1000))
    return jsonify(fetch_history(limit=limit))


@app.route("/history/effacer", methods=["POST"])
@require_admin
def clear_history():
    conn = get_db_connection()
    conn.execute("DELETE FROM analyses")
    conn.commit()
    conn.close()
    return jsonify({"message": "Historique effacé"})


@app.route("/feedback", methods=["POST"])
def feedback():
    payload = request.get_json(silent=True) or {}
    analysis_id = payload.get("analysis_id")
    actual_label = (payload.get("actual_label") or "").strip()

    if not analysis_id:
        return jsonify({"erreur": "analysis_id requis"}), 400
    if actual_label not in VALID_ACTUAL_LABELS:
        return jsonify({"erreur": "actual_label doit etre favorable ou non_favorable"}), 400

    conn = get_db_connection()
    result = conn.execute(
        "UPDATE analyses SET actual_label = ? WHERE id = ?",
        (actual_label, analysis_id),
    )
    conn.commit()
    conn.close()

    if result.rowcount == 0:
        return jsonify({"erreur": "Analyse introuvable"}), 404

    return jsonify({"message": "Feedback enregistré"})


@app.route("/feedback/stats", methods=["GET"])
def feedback_stats():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT prediction, actual_label FROM analyses"
    ).fetchall()
    conn.close()

    total = len(rows)
    feedback_count = 0
    evaluated_count = 0
    correct_count = 0
    for row in rows:
        actual_label = row["actual_label"]
        prediction = row["prediction"]
        if actual_label is None:
            continue
        feedback_count += 1
        if prediction not in VALID_ACTUAL_LABELS:
            continue
        evaluated_count += 1
        if actual_label == prediction:
            correct_count += 1

    precision_terrain = (correct_count / evaluated_count * 100.0) if evaluated_count else 0.0

    return jsonify(
        {
            "total_analyses": total,
            "nombre_feedbacks": feedback_count,
            "nombre_corrects": correct_count,
            "nombre_evalues": evaluated_count,
            "precision_terrain": round(precision_terrain, 2),
        }
    )


@app.route("/dashboard/stats", methods=["GET"])
def dashboard_stats():
    return jsonify(compute_dashboard_stats())


@app.route("/retrain/auto", methods=["POST"])
@require_admin
def retrain_auto():
    payload = request.get_json(silent=True) or {}
    try:
        min_feedback = int(payload.get("min_feedback", 20))
    except (TypeError, ValueError):
        return jsonify({"erreur": "min_feedback doit etre un entier"}), 400
    if min_feedback < 1:
        return jsonify({"erreur": "min_feedback doit etre >= 1"}), 400

    from retrain_from_feedback import retrain_if_ready

    result = retrain_if_ready(min_feedback=min_feedback)
    status_code = 200 if result.get("retrained") else 202
    result_fr = {
        "reentraine": bool(result.get("retrained")),
        "raison": result.get("reason"),
        "nombre_feedbacks": result.get("feedback_rows"),
        "lignes_ajoutees": result.get("rows_appended"),
    }
    return jsonify(result_fr), status_code


@app.route("/export/csv", methods=["GET"])
@require_admin
def export_csv():
    records = fetch_history(limit=1000)
    if not records:
        return jsonify({"erreur": "Aucun historique disponible"}), 404

    rows = []
    for item in records:
        row = {
            "id": item["id"],
            "date_creation": item["date_creation"],
            "prediction": item["prediction"],
            "confiance": item["confiance"],
        }
        row.update(item["donnees_entree"])
        rows.append(row)

    fieldnames = list(rows[0].keys())
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    payload = io.BytesIO(csv_buffer.getvalue().encode("utf-8"))
    payload.seek(0)
    return send_file(payload, as_attachment=True, download_name="history_export.csv", mimetype="text/csv")


@app.route("/export/excel", methods=["GET"])
@require_admin
def export_excel():
    records = fetch_history(limit=1000)
    if not records:
        return jsonify({"erreur": "Aucun historique disponible"}), 404

    rows = []
    for item in records:
        row = {
            "id": item["id"],
            "date_creation": item["date_creation"],
            "prediction": item["prediction"],
            "confiance": item["confiance"],
        }
        row.update(item["donnees_entree"])
        rows.append(row)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "history"

    headers = list(rows[0].keys())
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])

    payload = io.BytesIO()
    workbook.save(payload)
    payload.seek(0)
    return send_file(
        payload,
        as_attachment=True,
        download_name="history_export.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    initialize_runtime()
    port = int(os.getenv("PORT", "5001"))
    debug_mode = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
