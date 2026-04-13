from decision_rules import load_decision_rules


def suggest_crops(prediction, nitrogen, phosphorus, potassium):
    if prediction != "favorable":
        return [
            "Mucuna (engrais vert)",
            "Dolique (légumineuse)",
            "Jachère améliorée",
        ]

    npk_mean = (nitrogen + phosphorus + potassium) / 3.0

    if npk_mean >= 75:
        return ["Tomate", "Poivron", "Pomme de terre"]
    if npk_mean >= 50:
        return ["Mais", "Haricot", "Arachide"]
    if npk_mean >= 30:
        return ["Mil", "Sorgho", "Niabe"]
    return ["Patate douce", "Manioc", "Sésame"]


def suggest_recovery_crops():
    return [
        "Mucuna (engrais vert)",
        "Dolique (légumineuse)",
        "Jachère améliorée",
    ]


def analyze_hydric_context(data):
    humidity = float(data["humidity"])
    rainfall = float(data["rainfall"])
    future_rainfall = float(data.get("future_rainfall", rainfall))
    soil_type = str(data.get("soil_type", ""))
    soil_profile = str(data.get("soil_profile", ""))

    rain_context = (rainfall + future_rainfall) / 2.0
    is_heavy_soil = soil_type == "clay" or soil_profile in {"hydromorphe", "argilo_sableux", "argilo_limoneux"}

    if (humidity >= 78 and rain_context >= 1200) or (is_heavy_soil and humidity >= 70 and rain_context >= 900):
        return "exces", "Excès d'eau / risque d'engorgement"

    if (humidity <= 35 and rain_context <= 900) or (humidity <= 45 and rain_context <= 550):
        return "deficit", "Stress hydrique probable"

    return "equilibre", ""


def rule_based_actions(data, prediction):
    actions = []
    reasons = []

    ph = float(data["ph"])
    nitrogen = float(data["nitrogen"])
    phosphorus = float(data["phosphorus"])
    potassium = float(data["potassium"])
    soil_profile = str(data.get("soil_profile", ""))

    if soil_profile == "hydromorphe":
        actions.append("Améliorer le drainage et limiter l'engorgement en eau")
        reasons.append("Sol hydromorphe : risque d'asphyxie racinaire")
    if soil_profile == "salin":
        actions.append("Mettre en place un lessivage contrôlé et corriger la salinité")
        reasons.append("Sol salin : stress osmotique élevé")
    if soil_profile == "calcaire":
        actions.append("Surveiller les carences en micronutriments (Fe, Zn)")
        reasons.append("Sol calcaire : risque de carences induites")

    if ph < 5.5:
        actions.append("Ajouter de la chaux pour réduire l'acidité du sol")
        reasons.append("pH trop acide")
    elif ph > 8.0:
        actions.append("Corriger l'alcalinité avec de la matière organique acide")
        reasons.append("pH trop alcalin")

    if nitrogen < 25:
        actions.append("Appliquer un amendement riche en azote")
        reasons.append("Azote insuffisant")
    if phosphorus < 25:
        actions.append("Renforcer le phosphore (engrais de fond)")
        reasons.append("Phosphore faible")
    if potassium < 25:
        actions.append("Apporter du potassium pour la résistance des cultures")
        reasons.append("Potassium faible")

    if nitrogen > 150:
        actions.append("Réduire les apports azotés et fractionner la fertilisation")
        reasons.append("Azote trop élevé")
    if phosphorus > 140:
        actions.append("Limiter le phosphore pour éviter le déséquilibre nutritionnel")
        reasons.append("Phosphore trop élevé")
    if potassium > 140:
        actions.append("Réduire le potassium et vérifier la salinité du sol")
        reasons.append("Potassium trop élevé")

    hydric_state, hydric_reason = analyze_hydric_context(data)
    if hydric_state == "deficit":
        actions.append("Mettre en place une stratégie d'irrigation")
        reasons.append(hydric_reason)
    elif hydric_state == "exces":
        actions.append("Améliorer le drainage du sol et limiter l'irrigation")
        reasons.append(hydric_reason)

    if prediction == "non_favorable" and "Prédiction ML : non favorable" not in reasons:
        reasons.append("Prédiction ML : non favorable")

    if not actions and prediction == "favorable":
        actions.append("Maintenir la fertilisation actuelle et surveiller périodiquement")
        reasons.append("Paramètres globalement équilibrés")
    elif not actions and prediction == "non_favorable":
        actions.append("Vérifier les mesures et refaire une analyse complète du sol")
        reasons.append("Incertitude opérationnelle à confirmer")

    return actions, reasons


def build_decision_support(prediction, confidence, data):
    cultures = suggest_crops(prediction, data["nitrogen"], data["phosphorus"], data["potassium"])
    actions, reasons = rule_based_actions(data, prediction)

    soil_score = compute_soil_score(data, prediction, confidence)
    soil_level = classify_soil_score(soil_score)

    uncertainty_level = "faible"
    uncertain = False
    if confidence < 60:
        uncertainty_level = "elevee"
        uncertain = True
    elif confidence < 75:
        uncertainty_level = "moyenne"
        uncertain = True

    decision_finale, motif_decision = compute_final_decision(prediction, confidence, data)

    # La recommandation doit suivre la decision finale et non la prediction brute du modele.
    if decision_finale != "favorable":
        cultures = suggest_recovery_crops()

    # Garde-fous de cohérence entre decision finale et score de sol.
    if decision_finale == "non_favorable":
        soil_score = min(soil_score, 54.0)
    elif decision_finale == "a_verifier":
        soil_score = min(soil_score, 74.0)
    soil_level = classify_soil_score(soil_score)

    has_operational_constraint = any(
        keyword in str(reason).lower()
        for reason in reasons
        for keyword in ["stress hydrique", "humidite trop elevee", "drainage", "asphyxie", "salin", "hydromorphe"]
    )
    if has_operational_constraint and soil_score >= 90.0:
        soil_score = min(soil_score, 89.0)
        soil_level = "tres_bon_avec_ajustements"

    # Un sol "excellent" ne doit pas masquer une carence explicite.
    lower_reasons = [str(reason).lower() for reason in reasons]
    has_deficiency = any(
        keyword in reason
        for reason in lower_reasons
        for keyword in ["faible", "insuffisant", "carence"]
    )
    if has_deficiency and soil_level == "excellent":
        soil_level = "tres_bon_avec_ajustements"
        soil_score = min(soil_score, 92.0)

    gravite_probleme, alerte_principale = assess_issue_severity(reasons)

    return {
        "cultures_recommandees": cultures,
        "actions_recommandees": actions,
        "raisons_principales": reasons,
        "prediction_incertaine": uncertain,
        "niveau_incertitude": uncertainty_level,
        "soil_score": soil_score,
        "soil_level": soil_level,
        "decision_finale": decision_finale,
        "motif_decision": motif_decision,
        "gravite_probleme": gravite_probleme,
        "alerte_principale": alerte_principale,
    }


def assess_issue_severity(reasons):
    rank = {"faible": 0, "modere": 1, "important": 2, "critique": 3}
    detected = "faible"
    alerte = "Aucune alerte majeure"

    for reason in reasons:
        text = str(reason).lower()
        sev = "faible"
        if "stress hydrique" in text or "deficit hydrique" in text:
            sev = "modere"
        if "exces d'eau" in text or "engorgement" in text:
            sev = "modere"
        if "trop eleve" in text or "desequilibre" in text or "salinite" in text:
            sev = "important"
        if "insuffisant" in text or "faible" in text or "carence" in text or "hydromorphe" in text or "salin" in text:
            sev = "critique"

        if rank[sev] >= rank[detected]:
            detected = sev
            alerte = reason

    return detected, alerte


def compute_final_decision(prediction, confidence, data):
    rules = load_decision_rules()
    npk_rules = rules.get("npk", {})
    confidence_rules = rules.get("confidence", {})

    # Garde-fous agronomiques pour eviter une calibration trop stricte.
    # La calibration automatique ne doit pas descendre en dessous des seuils metier minimaux.
    k_severe_high = max(float(npk_rules.get("k_severe_high", 140.0)), 140.0)
    n_severe_high = max(float(npk_rules.get("n_severe_high", 150.0)), 150.0)
    p_severe_low = min(float(npk_rules.get("p_severe_low", 25.0)), 25.0)
    k_pair_high = max(float(npk_rules.get("k_pair_high", 120.0)), 120.0)

    favorable_min = float(confidence_rules.get("favorable_min", 70.0))
    non_favorable_uncertain_max = float(confidence_rules.get("non_favorable_uncertain_max", 55.0))

    n = float(data["nitrogen"])
    p = float(data["phosphorus"])
    k = float(data["potassium"])
    soil_profile = str(data.get("soil_profile", ""))

    if soil_profile == "hydromorphe":
        return "non_favorable", "Sol hydromorphe : risque d'asphyxie racinaire"

    if soil_profile == "salin":
        return "non_favorable", "Sol salin : contrainte sévère pour la plupart des cultures"

    severe_npk_imbalance = (k > k_severe_high) or (n > n_severe_high) or (p < p_severe_low and k > k_pair_high)

    if prediction == "favorable" and severe_npk_imbalance:
        return "non_favorable", "Déséquilibre NPK sévère détecté"

    if prediction == "favorable" and confidence < favorable_min:
        return "a_verifier", "Confiance du modèle insuffisante"

    if prediction == "non_favorable" and confidence < non_favorable_uncertain_max:
        return "a_verifier", "Prédiction non favorable mais incertaine"

    return prediction, "Décision alignée sur le modèle"


def compute_soil_score(data, prediction, confidence):
    ph = float(data["ph"])
    n = float(data["nitrogen"])
    p = float(data["phosphorus"])
    k = float(data["potassium"])
    humidity = float(data["humidity"])
    temperature = float(data["temperature"])
    rainfall = float(data["rainfall"])
    soil_profile = str(data.get("soil_profile", ""))

    ph_score = 100.0 if 6.0 <= ph <= 7.5 else (75.0 if 5.5 <= ph <= 8.0 else 40.0)
    npk_mean = (n + p + k) / 3.0
    npk_score = 100.0 if 40 <= npk_mean <= 90 else (70.0 if 25 <= npk_mean <= 110 else 35.0)
    humidity_score = 100.0 if 40 <= humidity <= 75 else (70.0 if 30 <= humidity <= 85 else 35.0)
    temperature_score = 100.0 if 18 <= temperature <= 33 else (70.0 if 12 <= temperature <= 38 else 35.0)
    rainfall_score = 100.0 if 500 <= rainfall <= 1600 else (65.0 if 300 <= rainfall <= 2000 else 30.0)

    base_score = (
        ph_score * 0.25
        + npk_score * 0.25
        + humidity_score * 0.20
        + temperature_score * 0.15
        + rainfall_score * 0.15
    )

    # Penalite en cas d'exces nutrionnels majeurs qui degradent la qualite agronomique.
    if n > 150:
        base_score -= 12.0
    if p > 140:
        base_score -= 10.0
    if k > 140:
        base_score -= 14.0

    # Penalites de carences pour aligner le score avec les recommandations terrain.
    if n < 40:
        base_score -= 8.0
    if p < 40:
        base_score -= 10.0
    if k < 40:
        base_score -= 8.0

    if n < 25:
        base_score -= 8.0
    if p < 25:
        base_score -= 10.0
    if k < 25:
        base_score -= 8.0

    if soil_profile == "hydromorphe":
        base_score -= 28.0
    elif soil_profile == "salin":
        base_score -= 30.0
    elif soil_profile == "calcaire":
        base_score -= 10.0

    has_nutrient_deficit = (n < 40) or (p < 40) or (k < 40)

    if prediction == "favorable" and not has_nutrient_deficit:
        base_score += 3.0
    else:
        base_score -= 3.0

    confidence_adjust = (float(confidence) - 50.0) * 0.08
    score = max(0.0, min(100.0, base_score + confidence_adjust))

    # Cohérence entre score et sortie ML pour eviter "non favorable" avec score excellent.
    if prediction == "non_favorable":
        if confidence >= 70:
            score = min(score, 49.0)
        else:
            score = min(score, 62.0)

    return round(score, 2)


def classify_soil_score(score):
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "tres_bon_avec_ajustements"
    if score >= 60:
        return "bon"
    if score >= 45:
        return "moyen"
    return "faible"
