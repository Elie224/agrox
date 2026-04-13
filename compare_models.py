import json
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from train_model import load_data


OUTPUT_JSON = Path("model") / "model_comparison.json"
OUTPUT_MD = Path("docs") / "rapport_comparaison.md"


def make_models():
    return {
        "RandomForest": Pipeline(
            [
                ("vectorizer", DictVectorizer(sparse=False)),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=250,
                        max_depth=16,
                        min_samples_split=10,
                        min_samples_leaf=3,
                        max_features="sqrt",
                        bootstrap=True,
                        class_weight="balanced",
                        random_state=42,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
        "DecisionTree": Pipeline(
            [
                ("vectorizer", DictVectorizer(sparse=False)),
                (
                    "classifier",
                    DecisionTreeClassifier(
                        max_depth=10,
                        min_samples_leaf=3,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "LogisticRegression": Pipeline(
            [
                ("vectorizer", DictVectorizer(sparse=False)),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=3000,
                        class_weight="balanced",
                        random_state=42,
                        solver="lbfgs",
                    ),
                ),
            ]
        ),
    }


def evaluate_model(name, pipeline, x_train, x_test, y_train, y_test):
    pipeline.fit(x_train, y_train)
    pred = pipeline.predict(x_test)

    cv_f1 = cross_val_score(
        pipeline,
        x_train,
        y_train,
        cv=3,
        scoring="f1_weighted",
        n_jobs=1,
    )

    return {
        "modele": name,
        "accuracy_test": float(accuracy_score(y_test, pred)),
        "precision_weighted_test": float(precision_score(y_test, pred, average="weighted", zero_division=0)),
        "recall_weighted_test": float(recall_score(y_test, pred, average="weighted", zero_division=0)),
        "f1_weighted_test": float(f1_score(y_test, pred, average="weighted", zero_division=0)),
        "f1_weighted_cv_mean": float(cv_f1.mean()),
    }


def save_report(results, best):
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)

    payload = {"resultats": results, "meilleur_modele": best}
    with OUTPUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    lines = [
        "# Rapport de comparaison des modeles",
        "",
        "## Resultats",
        "",
        "| Modele | Accuracy test | F1 weighted test | F1 weighted CV |",
        "|---|---:|---:|---:|",
    ]

    for item in results:
        lines.append(
            f"| {item['modele']} | {item['accuracy_test']:.4f} | {item['f1_weighted_test']:.4f} | {item['f1_weighted_cv_mean']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Meilleur modele",
            "",
            f"- Nom: {best['modele']}",
            f"- F1 weighted test: {best['f1_weighted_test']:.4f}",
            f"- Accuracy test: {best['accuracy_test']:.4f}",
        ]
    )

    with OUTPUT_MD.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def main():
    x, y = load_data()
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    results = []
    for name, pipeline in make_models().items():
        results.append(evaluate_model(name, pipeline, x_train, x_test, y_train, y_test))

    best = max(results, key=lambda item: item["f1_weighted_test"])
    save_report(results, best)

    print("Comparaison terminee.")
    print(f"Meilleur modele: {best['modele']}")
    print(f"Rapport JSON: {OUTPUT_JSON}")
    print(f"Rapport Markdown: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
