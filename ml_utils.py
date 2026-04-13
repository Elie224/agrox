import math


REQUIRED_FIELDS = [
    "ph",
    "humidity",
    "temperature",
    "nitrogen",
    "phosphorus",
    "potassium",
    "rainfall",
    "soil_type",
]

SOIL_PROFILE_MAP = {
    "sableux": "sandy",
    "sandy soil": "sandy",
    "sandy": "sandy",
    "argileux": "clay",
    "clayey": "clay",
    "clay": "clay",
    "franc": "loam",
    "loamy": "loam",
    "loamy soil": "loam",
    "loam": "loam",
    "limoneux": "silty",
    "silt": "silty",
    "silty soil": "silty",
    "silty": "silty",
    "limono-argileux": "limono_argileux",
    "limono argileux": "limono_argileux",
    "limono-sableux": "limono_sableux",
    "limono sableux": "limono_sableux",
    "argilo-sableux": "argilo_sableux",
    "argilo sableux": "argilo_sableux",
    "argilo-limoneux": "argilo_limoneux",
    "argilo limoneux": "argilo_limoneux",
    "hydromorphe": "hydromorphe",
    "organique": "organique",
    "organique / tourbe": "organique",
    "tourbe": "organique",
    "calcaire": "calcaire",
    "salin": "salin",
    "sale": "salin",
    "salin / sale": "salin",
}

SOIL_TEXTURE_BY_PROFILE = {
    "sandy": "sandy",
    "clay": "clay",
    "loam": "loam",
    "silty": "silty",
    "limono_argileux": "loam",
    "limono_sableux": "sandy",
    "argilo_sableux": "clay",
    "argilo_limoneux": "loam",
    "hydromorphe": "clay",
    "organique": "loam",
    "calcaire": "loam",
    "salin": "sandy",
}


VALID_ACTUAL_LABELS = {"favorable", "non_favorable"}


def normalize_soil_type(value):
    soil_type = str(value).strip().lower()
    if soil_type not in SOIL_PROFILE_MAP:
        raise ValueError(f"Type de sol invalide: {soil_type}")
    profile = SOIL_PROFILE_MAP[soil_type]
    return SOIL_TEXTURE_BY_PROFILE[profile]


def normalize_soil_profile(value):
    soil_type = str(value).strip().lower()
    if soil_type not in SOIL_PROFILE_MAP:
        raise ValueError(f"Type de sol invalide: {soil_type}")
    return SOIL_PROFILE_MAP[soil_type]


def parse_float(value):
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Valeur non finie")
    return parsed


def enrich_features(data):
    enriched = dict(data)
    n = float(enriched["nitrogen"])
    p = float(enriched["phosphorus"])
    k = float(enriched["potassium"])
    humidity = float(enriched["humidity"])
    temperature = float(enriched["temperature"])

    # Features derivees pour donner plus de contexte au modele.
    enriched["fertility_index"] = (n + p + k) / 3.0
    enriched["climate_factor"] = (humidity / 100.0) * (temperature / 40.0)
    enriched["np_ratio"] = n / (p + 1e-6)
    enriched["pk_ratio"] = p / (k + 1e-6)

    forecast_rainfall = enriched.get("future_rainfall", enriched["rainfall"])
    forecast_temperature = enriched.get("temperature_forecast", enriched["temperature"])
    enriched["future_rainfall"] = float(forecast_rainfall)
    enriched["temperature_forecast"] = float(forecast_temperature)
    enriched["rainfall_ratio_forecast"] = enriched["future_rainfall"] / (float(enriched["rainfall"]) + 1e-6)
    enriched["temperature_delta_forecast"] = enriched["temperature_forecast"] - float(enriched["temperature"])

    profile = str(enriched.get("soil_profile", "standard"))
    enriched["soil_profile"] = profile
    enriched["waterlogging_risk"] = 1.0 if profile == "hydromorphe" else 0.0
    enriched["salinity_risk"] = 1.0 if profile == "salin" else 0.0
    enriched["calcareous_risk"] = 1.0 if profile == "calcaire" else 0.0
    enriched["organic_soil"] = 1.0 if profile == "organique" else 0.0

    return enriched


def validate_payload(payload):
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        return False, f"Champs manquants: {', '.join(missing)}"

    try:
        soil_profile = normalize_soil_profile(payload["soil_type"])
        cleaned = {
            "ph": parse_float(payload["ph"]),
            "humidity": parse_float(payload["humidity"]),
            "temperature": parse_float(payload["temperature"]),
            "nitrogen": parse_float(payload["nitrogen"]),
            "phosphorus": parse_float(payload["phosphorus"]),
            "potassium": parse_float(payload["potassium"]),
            "rainfall": parse_float(payload["rainfall"]),
            "soil_type": SOIL_TEXTURE_BY_PROFILE[soil_profile],
            "soil_profile": soil_profile,
        }
        if payload.get("future_rainfall") not in (None, ""):
            cleaned["future_rainfall"] = parse_float(payload["future_rainfall"])
        if payload.get("temperature_forecast") not in (None, ""):
            cleaned["temperature_forecast"] = parse_float(payload["temperature_forecast"])
    except (TypeError, ValueError):
        return False, "Valeurs numeriques invalides ou type de sol invalide"

    return True, enrich_features(cleaned)


def detect_input_anomalies(data):
    anomalies = []

    ph = float(data["ph"])
    humidity = float(data["humidity"])
    temperature = float(data["temperature"])
    n = float(data["nitrogen"])
    p = float(data["phosphorus"])
    k = float(data["potassium"])
    rainfall = float(data["rainfall"])

    if ph < 4.0 or ph > 9.5:
        anomalies.append("pH hors plage agronomique habituelle")
    if humidity < 10 or humidity > 98:
        anomalies.append("Humidite suspecte")
    if temperature < 5 or temperature > 48:
        anomalies.append("Temperature suspecte")
    if rainfall < 100 or rainfall > 3000:
        anomalies.append("Pluviometrie suspecte")
    if n > 180 or p > 180 or k > 180:
        anomalies.append("Valeurs NPK anormalement elevees")

    if ph < 4.5 and (n > 120 or p > 120 or k > 120):
        anomalies.append("Incoherence possible: sol tres acide avec NPK tres eleves")
    if humidity < 20 and rainfall > 1800:
        anomalies.append("Incoherence possible: humidite tres basse avec forte pluviometrie")

    return anomalies
