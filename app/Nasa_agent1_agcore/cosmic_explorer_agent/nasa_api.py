import os
from strands import tool
import requests
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "https://api.nasa.gov"
API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")


def nasa_get(
    endpoint: str,
    params: dict | None = None
) -> dict:
    """Send a GET request to a NASA API endpoint."""

    url = f"{BASE_URL}/{endpoint.lstrip('/')}"

    request_params = dict(params or {})
    request_params["api_key"] = API_KEY

    response = requests.get(
        url,
        params=request_params,
        timeout=15
    )

    response.raise_for_status()

    return response.json()

@tool
def get_astronomy_picture(date: str | None = None) -> dict:
    """Return NASA's Astronomy Picture of the Day."""

    params = {}

    if date:
        params["date"] = date

    data = nasa_get(
        endpoint="planetary/apod",
        params=params
    )

    return {
        "date": data.get("date"),
        "title": data.get("title"),
        "explanation": data.get("explanation"),
        "media_type": data.get("media_type"),
        "url": data.get("url"),
        "copyright": data.get("copyright")
    }

@tool
def get_near_earth_asteroids(date: str) -> dict:
    """Return up to five closest Earth approaches on YYYY-MM-DD."""

    # Reject invalid dates before making an API request.
    from datetime import date as calendar_date

    calendar_date.fromisoformat(date)

    data = nasa_get(
        endpoint="neo/rest/v1/feed",
        params={
            "start_date": date,
            "end_date": date
        }
    )

    asteroids = []

    for asteroid in data["near_earth_objects"].get(date, []):
        diameter = asteroid["estimated_diameter"]["meters"]

        for approach in asteroid["close_approach_data"]:
            if approach["orbiting_body"] != "Earth":
                continue

            if approach["close_approach_date"] != date:
                continue

            asteroids.append({
                "name": asteroid["name"],
                "diameter_min_m": round(
                    diameter["estimated_diameter_min"], 1
                ),
                "diameter_max_m": round(
                    diameter["estimated_diameter_max"], 1
                ),
                "miss_distance_km": float(
                    approach["miss_distance"]["kilometers"]
                ),
                "speed_kmh": round(float(
                    approach["relative_velocity"]["kilometers_per_hour"]
                ), 1),
                "source_url": asteroid["nasa_jpl_url"]
            })

    asteroids.sort(key=lambda item: item["miss_distance_km"])

    return {
        "date": date,
        "total_earth_approaches": len(asteroids),
        "closest_approaches": asteroids[:5]
    }