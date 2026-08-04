# coding: utf-8


#!/usr/bin/env python3
"""Build a daily environmen environment summary for BT19/Belfast."""

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

# Cardinal direction labels (16-point compass, each covers 22.5°)
_CARDINAL_DIRS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def _degrees_to_cardinal(degrees: float) -> str:
    idx = round(degrees / 22.5) % 16
    return _CARDINAL_DIRS[idx]


def _rain_description(max_precip_mm: float) -> str:
    """Return a human-readable rain description from max hourly precipitation (mm)."""
    if max_precip_mm <= 0.0:
        return "None"
    if max_precip_mm < 0.5:
        return "Drizzle"
    if max_precip_mm < 2.5:
        return "Light Rain"
    if max_precip_mm < 7.5:
        return "Moderate Rain"
    return "Heavy Rain"


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


def _extract_morning_precip(payload: dict) -> float:
    """Return max hourly precipitation (mm) across the 05:00–07:00 window."""
    try:
        times = payload["hourly"]["time"]
        precip = payload["hourly"]["precipitation"]
    except KeyError:
        return 0.0

    values = [
        p for t, p in zip(times, precip)
        if "T05:" <= t[11:] <= "T07:59"
    ]
    return max(values, default=0.0)


def fetch_weather() -> dict:
    params = urlencode(
        {
            "latitude": BT19_LAT,
            "longitude": BT19_LON,
            "daily": "sunrise",
            "current": "temperature_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation,rain",
            "hourly": "precipitation",
            "timezone": "Europe/London",
            "forecast_days": 1,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    payload = _fetch_json(url)

    try:
        sunrise = payload["daily"]["sunrise"][0]
        current = payload["current"]
        temp_c = float(current["temperature_2m"])
        wind_kph = float(current["wind_speed_10m"])
        wind_gusts_kph = float(current.get("wind_gusts_10m", wind_kph))
        wind_dir_deg = float(current.get("wind_direction_10m", 0.0))
        rain_mm = float(current.get("rain", 0.0))
        precipitation_mm = float(current.get("precipitation", 0.0))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DataError("Unexpected weather data format") from exc

    morning_precip = _extract_morning_precip(payload)

    return {
        "sunrise": _format_time(sunrise),
        "temperature_c": round(temp_c, 1),
        "wind_kts": round(wind_kph / 1.852, 1),
        "wind_gusts_kts": round(wind_gusts_kph / 1.852, 1),
        "wind_direction": _degrees_to_cardinal(wind_dir_deg),
        "raining": rain_mm > 0.0 or precipitation_mm > 0.0,
        "rain_description": _rain_description(morning_precip),
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


def build_message(weather: dict, tides: list[tuple[str, str]], cruise_ship: str = "None") -> str:
    rain_desc = weather.get("rain_description", "Yes" if weather["raining"] else "None")
    wind_dir = weather.get("wind_direction", "")
    wind_str = f"{weather['wind_kts']:.1f} kts {wind_dir}".strip()
    gusts_str = f"{weather.get('wind_gusts_kts', weather['wind_kts']):.1f} kts"
    content_lines = [
        "🌅  BT19 DAILY",
        f"🌄 Sunrise   {weather['sunrise']}",
        f"🌡️  Temp     {weather['temperature_c']:.1f}°C",
        f"💨 Wind     {wind_str}",
        f"💨 Gusts    {gusts_str}",
        f"🌧️  Rain     {rain_desc}",
        f"🚢 Cruise   {cruise_ship}",
        "🌊 Tides (Belfast)",
    ]
    content_lines.extend(
        f"{'🌊' if kind == 'high' else '🏖️'}  {kind.title():4s}  {time}"
        for kind, time in tides
    )
    width = max(len(line) for line in content_lines)

    def boxed(line: str) -> str:
        return f"║ {line:<{width}} ║"

    divider = f"╠{'═' * (width + 2)}╣"

    return "\n".join(
        [
            f"╔{'═' * (width + 2)}╗",
            boxed("🌅  BT19 DAILY"),
            divider,
            boxed(f"🌄 Sunrise   {weather['sunrise']}"),
            divider,
            boxed(f"🌡️  Temp     {weather['temperature_c']:.1f}°C"),
            boxed(f"💨 Wind     {wind_str}"),
            boxed(f"💨 Gusts    {gusts_str}"),
            boxed(f"🌧️  Rain     {rain_desc}"),
            boxed(f"🚢 Cruise   {cruise_ship}"),
            divider,
            boxed("🌊 Tides (Belfast)"),
            *[
                boxed(f"{'🌊' if kind == 'high' else '🏖️'}  {kind.title():4s}  {time}")
                for kind, time in tides
            ],
            f"╚{'═' * (width + 2)}╝",
        ]
    )


def _load_weather_from_file(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    current = payload["current"]
    rain_mm = float(current.get("rain", 0.0))
    precipitation_mm = float(current.get("precipitation", 0.0))
    wind_dir_deg = float(current.get("wind_direction_10m", 0.0))
    morning_precip = _extract_morning_precip(payload)
    return {
        "sunrise": _format_time(payload["daily"]["sunrise"][0]),
        "temperature_c": round(float(current["temperature_2m"]), 1),
        "wind_kts": round(float(current["wind_speed_10m"]) / 1.852, 1),
        "wind_gusts_kts": round(float(current.get("wind_gusts_10m", current["wind_speed_10m"])) / 1.852, 1),
        "wind_direction": _degrees_to_cardinal(wind_dir_deg),
        "raining": rain_mm > 0 or precipitation_mm > 0,
        "rain_description": _rain_description(morning_precip),
    }


def _load_tides_from_file(path: str) -> list[tuple[str, str]]:
    events = _extract_tide_events(Path(path).read_text(encoding="utf-8"))
    if len(events) < 2:
        raise DataError("Unable to find Belfast tide times")
    return events[:4]

def main() -> str:
    parser = argparse.ArgumentParser(description="Generate BT19/Belfast daily numbers")
    parser.add_argument("--weather-json", help="Path to saved Open-Meteo payload")
    parser.add_argument("--tide-html", help="Path to saved Belfast tide page HTML")
    args = parser.parse_args()

    weather = _load_weather_from_file(args.weather_json) if args.weather_json else fetch_weather()
    tides = _load_tides_from_file(args.tide_html) if args.tide_html else fetch_tides()

    # RETURN the final message instead of printing it
    return build_message(weather, tides)


if __name__ == "__main__":
    import sys
    # Send the returned message directly to Shortcuts
    sys.stdout.write(main())
