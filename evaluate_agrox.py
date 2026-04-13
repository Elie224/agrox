import json
from datetime import datetime, UTC
from pathlib import Path

from app import app, init_db, load_model


METRICS_PATH = Path("model") / "metrics.json"
OUTPUT_JSON = Path("model") / "test_suite_results.json"
OUTPUT_MD = Path("docs") / "rapport_qualite_agrox.md"


def get_test_cases():
    return [
        {
            "nom": "Sol limono-argileux equilibre",
            "attendu": "favorable",
            "payload": {
                "ph": 6.8,
                "humidity": 45,
                "temperature": 22,
                "nitrogen": 30,
                "phosphorus": 25,
                "potassium": 140,
                "rainfall": 900,
                "soil_type": "limono-argileux",
            },
        },
        {
            "nom": "Sol degrade sec et carence N/P",
            "attendu": "non_favorable",
            "payload": {
                "ph": 5.0,
                "humidity": 35,
                "temperature": 31,
                "nitrogen": 15,
                "phosphorus": 12,
                "potassium": 18,
                "rainfall": 320,
                "soil_type": "sableux",
            },
        },
        {
            "nom": "Exces potassium severe",
            "attendu": "non_favorable",
            "payload": {
                "ph": 6.5,
                "humidity": 65,
                "temperature": 28,
                "nitrogen": 90,
                "phosphorus": 60,
                "potassium": 170,
                "rainfall": 900,
                "soil_type": "sableux",
            },
        },
        {
            "nom": "Hydromorphe",
            "attendu": "non_favorable",
            "payload": {
                "ph": 6.2,
                "humidity": 86,
                "temperature": 29,
                "nitrogen": 34,
                "phosphorus": 30,
                "potassium": 48,
                "rainfall": 420,
                "soil_type": "hydromorphe",
            },
        },
        {
            "nom": "Salin",
            "attendu": "non_favorable",
            "payload": {
                "ph": 7.3,
                "humidity": 52,
                "temperature": 31,
                "nitrogen": 35,
                "phosphorus": 24,
                "potassium": 120,
                "rainfall": 920,
                "soil_type": "salin",
            },
        },
        {
            "nom": "Calcaire tropical",
            "attendu": "non_favorable",
            "payload": {
                "ph": 8.1,
                "humidity": 72,
                "temperature": 30,
                "nitrogen": 38,
                "phosphorus": 22,
                "potassium": 44,
                "rainfall": 1350,
                "soil_type": "calcaire",
            },
        },
        {
            "nom": "Organique humide tempere",
            "attendu": "favorable",
            "payload": {
                "ph": 6.4,
                "humidity": 68,
                "temperature": 23,
                "nitrogen": 55,
                "phosphorus": 40,
                "potassium": 55,
                "rainfall": 1000,
                "soil_type": "organique",
            },
        },
        {
            "nom": "Argilo-limoneux bien equilibre",
            "attendu": "favorable",
            "payload": {
                "ph": 6.6,
                "humidity": 58,
                "temperature": 25,
                "nitrogen": 60,
                "phosphorus": 45,
                "potassium": 60,
                "rainfall": 980,
                "soil_type": "argilo-limoneux",
            },
        },
        {
            "nom": "Limono-sableux sec",
            "attendu": "non_favorable",
            "payload": {
                "ph": 6.3,
                "humidity": 30,
                "temperature": 32,
                "nitrogen": 28,
                "phosphorus": 20,
                "potassium": 35,
                "rainfall": 260,
                "soil_type": "limono-sableux",
            },
        },
        {
            "nom": "Argilo-sableux moyen",
            "attendu": "a_verifier",
            "payload": {
                "ph": 5.8,
                "humidity": 42,
                "temperature": 29,
                "nitrogen": 26,
                "phosphorus": 21,
                "potassium": 36,
                "rainfall": 560,
                "soil_type": "argilo-sableux",
            },
        },
    ]


def read_metrics():
    if not METRICS_PATH.exists():
        return {}
    with METRICS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_cases():
    init_db()
    load_model()

    cases = get_test_cases()
    results = []

    with app.test_client() as client:
        for case in cases:
            response = client.post("/predict", json=case["payload"])
            payload = response.get_json() or {}
            decision = payload.get("prediction")
            expected = case["attendu"]
            passed = decision == expected or (expected == "a_verifier" and decision in {"a_verifier", "non_favorable"})
            results.append(
                {
                    "nom": case["nom"],
                    "attendu": expected,
                    "obtenu": decision,
                    "confiance": payload.get("confiance"),
                    "motif": payload.get("motif_decision"),
                    "ok": bool(passed),
                }
            )

    return results


def save_reports(metrics, results):
    total = len(results)
    passed = sum(1 for item in results if item["ok"])
    pass_rate = (passed / total * 100.0) if total else 0.0

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_metrics": {
            "algorithm": metrics.get("algorithm"),
            "accuracy": metrics.get("test_metrics", {}).get("accuracy"),
            "balanced_accuracy": metrics.get("test_metrics", {}).get("balanced_accuracy"),
            "f1_weighted": metrics.get("test_metrics", {}).get("f1_weighted"),
            "f1_cv": metrics.get("search", {}).get("best_cv_score_f1_weighted"),
        },
        "test_suite": {
            "total": total,
            "passed": passed,
            "pass_rate": round(pass_rate, 2),
            "results": results,
        },
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    lines = [
        "# Rapport Qualite AgroX",
        "",
        f"- Date (UTC): {payload['generated_at_utc']}",
        f"- Algorithme: {payload['model_metrics']['algorithm']}",
        f"- Accuracy test: {payload['model_metrics']['accuracy']}",
        f"- Balanced accuracy: {payload['model_metrics']['balanced_accuracy']}",
        f"- F1 weighted: {payload['model_metrics']['f1_weighted']}",
        f"- F1 CV: {payload['model_metrics']['f1_cv']}",
        "",
        "## Resultats des 10 cas fixes",
        "",
        f"- Cas reussis: {passed}/{total} ({pass_rate:.2f}%)",
        "",
        "| Cas | Attendu | Obtenu | Confiance | Verdict |",
        "|---|---|---|---:|---|",
    ]

    for item in results:
        verdict = "OK" if item["ok"] else "ECHEC"
        confidence = "-" if item["confiance"] is None else f"{item['confiance']}%"
        lines.append(f"| {item['nom']} | {item['attendu']} | {item['obtenu']} | {confidence} | {verdict} |")

    lines.extend([
        "",
        "## Details des motifs",
        "",
    ])

    for item in results:
        lines.append(f"- {item['nom']}: {item['motif']}")

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_MD.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines))


if __name__ == "__main__":
    metrics = read_metrics()
    results = evaluate_cases()
    save_reports(metrics, results)
    print(f"Rapport JSON: {OUTPUT_JSON}")
    print(f"Rapport Markdown: {OUTPUT_MD}")
