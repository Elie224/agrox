---
title: Agrox
emoji: "🚀"
colorFrom: pink
colorTo: blue
sdk: docker
pinned: false
short_description: AgroX - Analyse de fertilite des sols
---

# AgroX - Détection de la fertilité du sol (XGBoost)

Projet ML professionnel pour predire si un sol est favorable a l'agriculture.

## Fonctionnalites

- Modele XGBoost pour la prediction binaire: favorable / non_favorable
- Optimisation automatique des hyperparametres (RandomizedSearchCV)
- Variables d'entree: ph, humidity, temperature, nitrogen, phosphorus, potassium, rainfall, soil_type
- Feature engineering integre: fertility_index, climate_factor, np_ratio, pk_ratio
- Score de confiance (%)
- Historique des analyses (SQLite)
- Boucle de feedback terrain (etiquettes reelles + statistiques)
- Export de l'historique en CSV et Excel
- Interface web Flask simple
- Recommandation de cultures apres prediction
- Moteur de regles metier (actions correctives et raisons explicables)
- Detection d'incertitude de prediction
- Contexte meteo optionnel via Open-Meteo (latitude/longitude)
- Explication locale par prediction (facteurs influents)
- Prediction en lot sur CSV
- Comparaison XGBoost, Random Forest, Decision Tree et Logistic Regression

## Structure du projet

- `generate_sample_data.py`: genere un jeu de donnees synthetique
- `train_model.py`: pretraitement + tuning XGBoost + calibration + evaluation + sauvegarde
- `app.py`: API Flask et serveur web
- `recommendations.py`: logique de recommandation de cultures
- `ml_utils.py`: validation des entrees + normalisation + features derivees
- `batch_predict.py`: prediction en lot a partir d'un CSV
- `retrain_from_feedback.py`: auto-reentrainement depuis les feedbacks terrain
- `calibrate_decision_rules.py`: calibration automatique des seuils metier (NPK)
- `weather_service.py`: recuperation du contexte meteo previsionnel
- `schedule_retrain.ps1`: creation d'une tache Windows hebdomadaire pour reentrainer
- `compare_models.py`: comparaison des performances de plusieurs modeles
- `templates/index.html`: interface web
- `static/style.css`: styles
- `static/app.js`: logique frontend

Sorties d'entrainement:

- `model/soil_model.joblib`: modele pret pour l'API
- `model/metrics.json`: metriques test + meilleur score CV + matrice de confusion
- `model/feature_importance.json`: importance des variables
- `model/decision_rules.json`: seuils metier calibres pour la decision finale

## Installation

1. Creer et activer un environnement virtuel Python.
2. Installer les dependances:

```bash
pip install -r requirements.txt
```

3. Generer un dataset d'exemple (ou remplacer par votre fichier dans `data/soil_fertility.csv`):

```bash
python generate_sample_data.py
```

4. Entrainer le modele XGBoost:

```bash
python train_model.py
```

5. Lancer l'application web:

```bash
python app.py
```

6. Ouvrir:

- `http://127.0.0.1:5001`

## Format du dataset

Colonnes attendues:

- ph
- humidity
- temperature
- nitrogen
- phosphorus
- potassium
- rainfall
- soil_type
- label

La colonne `label` doit contenir `favorable` ou `non_favorable`.

## Objectifs de performance

- Accuracy >= 0.80
- Bon equilibre precision/recall
- Reponse API inferieure a 2 secondes en execution locale normale

## Notes

- Vous pouvez remplacer Flask par Django sans changer le pipeline ML.
- Pour la production, ajoutez l'authentification, l'audit des entrees et la gestion de versions du modele.

## Note de compatibilite

- Ce projet est adapte pour fonctionner sans pandas afin d'eviter les blocages DLL sur certains environnements Windows securises.

## Commandes utiles

Prediction en lot:

python batch_predict.py --input data/soil_fertility.csv --output data/predictions_batch.csv

Comparer les modeles:

python compare_models.py

API prediction en lot (upload CSV):

- Endpoint: `POST /predict/batch`
- Form-data: champ `file` contenant un fichier `.csv`
- Reponse: telechargement automatique du CSV enrichi

Feedback terrain:

- Endpoint: `POST /feedback`
- Payload JSON: `analysis_id`, `actual_label` (`favorable` ou `non_favorable`)
- Endpoint stats: `GET /feedback/stats`

Auto-reentrainement:

- Endpoint: `POST /retrain/auto`
- Payload JSON optionnel: `min_feedback` (par defaut: 20)
- Exemple: `{ "min_feedback": 10 }`

Protection admin (recommande):

- Definir `ADMIN_API_KEY` dans l'environnement.
- Envoyer l'en-tete HTTP `X-Admin-Key` pour les endpoints sensibles:
	- `POST /regles/calibrer`
	- `POST /history/effacer`
	- `POST /retrain/auto`
	- `GET /export/csv`
	- `GET /export/excel`

Calibration des regles metier:

- Script: `python calibrate_decision_rules.py`
- Endpoint calibration: `POST /regles/calibrer`
- Endpoint lecture regles: `GET /regles/info`

Prediction contextualisee meteo:

- Endpoint: `POST /predict`
- Champs optionnels: `latitude`, `longitude`
- La reponse inclut `contexte_meteo` et `explication_locale`

Planification Windows (hebdomadaire):

- Commande: `./schedule_retrain.ps1 -TaskName AgriRetrainHebdo -Day MON -Time 02:00`

Sorties de comparaison:

- `model/model_comparison.json`
- `docs/rapport_comparaison.md`
