# coding: utf-8


#!/usr/bin/env python3
"""Build a daily environment summary for BT19/Belfast."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BT19_LAT = 54.6658
BT19_LON = -5.6948
BELFAST_TIDE_URL = "https://www.tidetimes.org.uk/belfast-tide-times"


class DataError(RuntimeError):
    """Raised when external data cannot be parsed."""


def _fetch_text(url: str) -> str:
    with urlopen(url, timeout=20) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def _fetch_json(url: str) -> dict:
    return json.loads(_fetch_text(url))


def _format_time(value: str) -> str:
    dt = datetime.fromisoformat(value)
    return dt.strftime("%H:%M")


def fetch_weather() -> dict:
    params = urlencode(
        {
            "latitude": BT19_LAT,
            "longitude": BT19_LON,
            "daily": "sunrise",
            "current": "temperature_2m,wind_speed_10m,precipitation,rain",
            "timezone": "Europe/London",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    payload = _fetch_json(url)

    try:
        sunrise = payload["daily"]["sunrise"][0]
        current = payload["current"]
        temp_c = float(current["temperature_2m"])
        wind_kph = float(current["wind_speed_10m"])
        rain_mm = float(current.get("rain", 0.0))
        precipitation_mm = float(current.get("precipitation", 0.0))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DataError("Unexpected weather data format") from exc

    return {
        "sunrise": _format_time(sunrise),
        "temperature_c": round(temp_c, 1),
        "wind_kts": round(wind_kph / 1.852, 1),
        "raining": rain_mm > 0.0 or precipitation_mm > 0.0,
    }


def _extract_tide_events(html: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"(?i)\b(high|low)\s+tide\b[^\d]*(\d{1,2}:\d{2}(?:\s*[ap]m)?)"
    )
    events = [(kind.lower(), t.replace(" ", "")) for kind, t in pattern.findall(html)]

    if events:
        return events

    fallback = re.compile(
        r"(?i)\b(high|low)\b[^\d]*(\d{1,2}:\d{2}(?:\s*[ap]m)?)"
    )
    return [(kind.lower(), t.replace(" ", "")) for kind, t in fallback.findall(html)]


def fetch_tides() -> list[tuple[str, str]]:
    html = _fetch_text(BELFAST_TIDE_URL)
    events = _extract_tide_events(html)
    if len(events) < 2:
        raise DataError("Unable to find Belfast tide times")
    return events[:4]


def build_message(weather: dict, tides: list[tuple[str, str]]) -> str:
    tide_summary = ", ".join(f"{kind.title()} {time}" for kind, time in tides)
    rain_summary = "Yes" if weather["raining"] else "No"
    return (
        f"BT19 Sunrise: {weather['sunrise']}\n"
        f"Belfast Tides: {tide_summary}\n"
        f"Air Temp Now: {weather['temperature_c']:.1f}°C\n"
        f"Wind Now: {weather['wind_kts']:.1f} kts\n"
        f"Raining: {rain_summary}"
    )


def _load_weather_from_file(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "sunrise": _format_time(payload["daily"]["sunrise"][0]),
        "temperature_c": round(float(payload["current"]["temperature_2m"]), 1),
        "wind_kts": round(float(payload["current"]["wind_speed_10m"]) / 1.852, 1),
        "raining": float(payload["current"].get("rain", 0.0)) > 0
        or float(payload["current"].get("precipitation", 0.0)) > 0,
    }


def _load_tides_from_file(path: str) -> list[tuple[str, str]]:
    events = _extract_tide_events(Path(path).read_text(encoding="utf-8"))
    if len(events) < 2:
        raise DataError("Unable to find Belfast tide times")
    return events[:4]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BT19/Belfast daily numbers")
    parser.add_argument("--weather-json", help="Path to saved Open-Meteo payload")
    parser.add_argument("--tide-html", help="Path to saved Belfast tide page HTML")
    args = parser.parse_args()

    weather = _load_weather_from_file(args.weather_json) if args.weather_json else fetch_weather()
    tides = _load_tides_from_file(args.tide_html) if args.tide_html else fetch_tides()

    print(build_message(weather, tides))


if __name__ == "__main__":
    print(main())
