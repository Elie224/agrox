import json
from urllib.request import urlopen
from urllib.parse import urlencode


def fetch_weather_forecast(latitude, longitude, timeout=8):
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": 2,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{query}"

    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    daily = payload.get("daily", {})
    precipitation = daily.get("precipitation_sum", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])

    if len(precipitation) < 2 or len(t_max) < 2 or len(t_min) < 2:
        raise ValueError("Donnees meteo insuffisantes")

    forecast_rainfall = float(precipitation[1]) * 365.0
    forecast_temperature = (float(t_max[1]) + float(t_min[1])) / 2.0

    return {
        "future_rainfall": forecast_rainfall,
        "temperature_forecast": forecast_temperature,
        "source": "open-meteo",
    }
