from pathlib import Path
import json
import csv
import os
from datetime import datetime, UTC

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction import DictVectorizer
from xgboost import XGBClassifier
from ml_utils import enrich_features, normalize_soil_profile, normalize_soil_type


DEFAULT_REAL_DATA_PATH = Path("data") / "soil_fertility_real.csv"
FALLBACK_DATA_PATH = Path("data") / "soil_fertility.csv"
MODEL_PATH = Path("model") / "soil_model.joblib"
METRICS_PATH = Path("model") / "metrics.json"
FEATURES_PATH = Path("model") / "feature_importance.json"
CALIBRATOR_PATH = Path("model") / "proba_calibrator.joblib"
LABEL_MAP_PATH = Path("model") / "label_map.json"


RANDOM_SEARCH_SPACE = {
    "classifier__n_estimators": [400, 700, 1000, 1400],
    "classifier__max_depth": [4, 6, 8, 10, 12],
    "classifier__learning_rate": [0.03, 0.05, 0.08],
    "classifier__subsample": [0.7, 0.85, 1.0],
    "classifier__colsample_bytree": [0.65, 0.8, 1.0],
    "classifier__min_child_weight": [1, 3, 5, 7],
    "classifier__reg_lambda": [1.0, 3.0, 8.0],
    "classifier__reg_alpha": [0.0, 0.5, 1.0, 2.0],
    "classifier__gamma": [0.0, 0.1, 0.3],
}


FAST_TRAIN_MODE = os.getenv("AGROX_FAST_TRAIN", "0").strip().lower() in {"1", "true", "yes", "on"}
REQUIRE_REAL_DATA = os.getenv("AGROX_REQUIRE_REAL_DATA", "0").strip().lower() in {"1", "true", "yes", "on"}


def resolve_data_path():
    custom_path = (os.getenv("AGROX_DATA_PATH") or "").strip()
    if custom_path:
        candidate = Path(custom_path)
        if candidate.exists():
            return candidate, False
        raise FileNotFoundError(f"AGROX_DATA_PATH introuvable: {candidate}")

    if DEFAULT_REAL_DATA_PATH.exists():
        return DEFAULT_REAL_DATA_PATH, False

    if REQUIRE_REAL_DATA:
        raise FileNotFoundError(
            "Données réelles requises, mais aucun fichier trouvé. "
            "Ajoutez data/soil_fertility_real.csv ou définissez AGROX_DATA_PATH."
        )

    return FALLBACK_DATA_PATH, True


def load_data(data_path):
    if not data_path.exists():
        raise FileNotFoundError(
            f"Missing dataset at {data_path}."
        )

    with data_path.open("r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    if not rows:
        raise ValueError("Dataset is empty")

    required_columns = {
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
    missing = required_columns - set(rows[0].keys())
    if missing:
        raise ValueError(f"Dataset missing columns: {sorted(missing)}")

    features = []
    labels = []
    sample_weights = []
    numeric_fields = [
        "ph",
        "humidity",
        "temperature",
        "nitrogen",
        "phosphorus",
        "potassium",
        "rainfall",
    ]

    for row in rows:
        item = {}
        for field in numeric_fields:
            value = row.get(field)
            if value in (None, ""):
                item[field] = 0.0
            else:
                item[field] = float(value)
        raw_soil_type = row.get("soil_type") or ""
        soil_profile = normalize_soil_profile(raw_soil_type)
        item["soil_profile"] = soil_profile
        item["soil_type"] = normalize_soil_type(raw_soil_type)
        features.append(enrich_features(item))
        label = (row.get("label") or "").strip()
        labels.append(label)

        # Renforce l'apprentissage des cas critiques pour améliorer la robustesse terrain.
        weight = 1.0
        if label == "non_favorable":
            weight += 0.25
        if soil_profile in {"hydromorphe", "salin", "calcaire", "organique"}:
            weight += 0.5
        if label == "non_favorable" and soil_profile in {"hydromorphe", "salin"}:
            weight += 0.5
        sample_weights.append(weight)

    return features, labels, sample_weights


def build_pipeline():
    n_estimators = 300 if FAST_TRAIN_MODE else 1000
    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=n_estimators,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=3.0,
        reg_alpha=0.5,
        gamma=0.1,
        random_state=42,
        n_jobs=1,
        tree_method="hist",
    )

    pipeline = Pipeline(
        steps=[
            ("vectorizer", DictVectorizer(sparse=False)),
            ("classifier", model),
        ]
    )
    return pipeline


def train_with_tuning(X_train, y_train, sample_weight_train):
    base_pipeline = build_pipeline()
    n_splits = 3 if FAST_TRAIN_MODE else 5
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    n_iter = 10 if FAST_TRAIN_MODE else 45
    search = RandomizedSearchCV(
        estimator=base_pipeline,
        param_distributions=RANDOM_SEARCH_SPACE,
        n_iter=n_iter,
        scoring="f1_macro",
        cv=cv,
        random_state=42,
        n_jobs=1,
        verbose=0,
    )
    search.fit(X_train, y_train, classifier__sample_weight=sample_weight_train)
    return search


def build_metrics(y_test, y_pred, search):
    cm = confusion_matrix(y_test, y_pred, labels=[1, 0])
    return {
        "training_datetime_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "algorithm": "XGBoostClassifier",
        "search": {
            "best_params": search.best_params_,
            "best_cv_score_f1_weighted": float(search.best_score_),
        },
        "test_metrics": {
            "accuracy": accuracy_score(y_test, y_pred),
            "balanced_accuracy": balanced_accuracy_score(y_test, y_pred),
            "precision_weighted": precision_score(y_test, y_pred, average="weighted", zero_division=0),
            "recall_weighted": recall_score(y_test, y_pred, average="weighted", zero_division=0),
            "f1_weighted": f1_score(y_test, y_pred, average="weighted", zero_division=0),
            "classification_report": classification_report(
                y_test,
                y_pred,
                labels=[1, 0],
                target_names=["favorable", "non_favorable"],
                output_dict=True,
                zero_division=0,
            ),
            "confusion_matrix": {
                "labels": ["favorable", "non_favorable"],
                "values": cm.tolist(),
            },
        },
    }


def label_distribution(values):
    counts = {}
    total = len(values)
    for item in values:
        counts[item] = counts.get(item, 0) + 1
    return {
        key: {
            "count": value,
            "ratio": round(value / total, 4) if total else 0.0,
        }
        for key, value in sorted(counts.items(), key=lambda x: x[0])
    }


def save_feature_importance(best_pipeline):
    vectorizer = best_pipeline.named_steps["vectorizer"]
    classifier = best_pipeline.named_steps["classifier"]
    feature_names = vectorizer.get_feature_names_out()
    importances = classifier.feature_importances_

    ordered = sorted(
        [
            {
                "feature": feature,
                "importance": float(score),
            }
            for feature, score in zip(feature_names, importances)
        ],
        key=lambda item: item["importance"],
        reverse=True,
    )

    with FEATURES_PATH.open("w", encoding="utf-8") as file:
        json.dump(ordered, file, indent=2)


def main():
    data_path, is_fallback = resolve_data_path()
    print(f"Dataset utilise: {data_path}")
    if is_fallback:
        print("AVERTISSEMENT: fallback vers un dataset non reel. Fournissez des donnees terrain pour la production.")

    X, y, sample_weights = load_data(data_path)
    label_to_int = {"non_favorable": 0, "favorable": 1}
    y_encoded = [label_to_int[item] for item in y]

    X_train, X_test, y_train, y_test, sw_train, _sw_test = train_test_split(
        X,
        y_encoded,
        sample_weights,
        test_size=0.2,
        random_state=42,
        stratify=y_encoded,
    )

    X_fit, X_calib, y_fit, y_calib, sw_fit, _sw_calib = train_test_split(
        X_train,
        y_train,
        sw_train,
        test_size=0.2,
        random_state=42,
        stratify=y_train,
    )

    search = train_with_tuning(X_fit, y_fit, sw_fit)
    pipeline = search.best_estimator_
    pipeline.fit(X_fit, y_fit, classifier__sample_weight=sw_fit)

    calibrator = CalibratedClassifierCV(estimator=FrozenEstimator(pipeline), method="sigmoid")
    calibrator.fit(X_calib, y_calib)

    y_pred = calibrator.predict(X_test)
    metrics = build_metrics(y_test, y_pred, search)
    y_proba = calibrator.predict_proba(X_test)

    reverse_map = {0: "non_favorable", 1: "favorable"}
    metrics["train_distribution"] = label_distribution([reverse_map[v] for v in y_train])
    metrics["test_distribution"] = label_distribution([reverse_map[v] for v in y_test])
    metrics["test_metrics"]["log_loss"] = float(log_loss(y_test, y_proba, labels=calibrator.classes_))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    joblib.dump(calibrator, CALIBRATOR_PATH)
    save_feature_importance(pipeline)

    with LABEL_MAP_PATH.open("w", encoding="utf-8") as file:
        json.dump({"0": "non_favorable", "1": "favorable"}, file, indent=2)

    with METRICS_PATH.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("Modele entraine et sauvegarde:", MODEL_PATH)
    print("Calibrateur de probabilites sauvegarde:", CALIBRATOR_PATH)
    print("Mapping des classes sauvegarde:", LABEL_MAP_PATH)
    print("Metriques sauvegardees:", METRICS_PATH)
    print("Importance des variables sauvegardee:", FEATURES_PATH)
    print(f"Meilleur score CV (F1 macro): {metrics['search']['best_cv_score_f1_weighted']:.4f}")
    print(f"Accuracy test: {metrics['test_metrics']['accuracy']:.4f}")


if __name__ == "__main__":
    main()
