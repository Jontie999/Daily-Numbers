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
BELFAST_HARBOUR_URL = "https://www.belfast-harbour.co.uk/port-info/harbour-movements/"

# Berths used by cruise ships in Belfast Harbour
_CRUISE_BERTHS = {"d1c", "d1", "d3", "d4"}

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


def _extract_cruise_ships(html: str) -> str:
    """Return cruise ship names visible in the Belfast Harbour movements HTML.

    Looks for table rows where the berth column contains a known cruise berth
    (e.g. D1C) or the vessel type contains "cruise".  Falls back to a simple
    keyword scan so that the function still works if the page layout changes.

    Returns a comma-separated ship list, or "None" when no cruise ships are found.
    """
    from html.parser import HTMLParser

    class _TableParser(HTMLParser):
        """Collect <tr> cell text from the harbour movements table."""

        def __init__(self) -> None:
            super().__init__()
            self._rows: list[list[str]] = []
            self._current_row: list[str] | None = None
            self._current_cell: list[str] | None = None
            self._in_cell = False

        def handle_starttag(self, tag: str, attrs: list) -> None:
            if tag == "tr":
                self._current_row = []
            elif tag in {"td", "th"} and self._current_row is not None:
                self._current_cell = []
                self._in_cell = True

        def handle_endtag(self, tag: str) -> None:
            if tag in {"td", "th"} and self._current_cell is not None:
                self._current_row.append(" ".join(self._current_cell).strip())
                self._current_cell = None
                self._in_cell = False
            elif tag == "tr" and self._current_row is not None:
                if self._current_row:
                    self._rows.append(self._current_row)
                self._current_row = None

        def handle_data(self, data: str) -> None:
            if self._in_cell and self._current_cell is not None:
                self._current_cell.append(data.strip())

    parser = _TableParser()
    parser.feed(html)

    ships: list[str] = []

    if parser._rows:
        # Identify header row to find column indices
        header_row = parser._rows[0]
        headers = [h.lower() for h in header_row]

        def _col(names: list[str]) -> int:
            for name in names:
                for i, h in enumerate(headers):
                    if name in h:
                        return i
            return -1

        name_col = _col(["vessel", "ship", "name"])
        berth_col = _col(["berth"])
        type_col = _col(["type", "vessel type", "ship type"])

        for row in parser._rows[1:]:
            if not row:
                continue
            vessel_name = row[name_col].strip() if name_col >= 0 and name_col < len(row) else ""
            berth = row[berth_col].strip().lower() if berth_col >= 0 and berth_col < len(row) else ""
            vessel_type = row[type_col].strip().lower() if type_col >= 0 and type_col < len(row) else ""

            if berth in _CRUISE_BERTHS or "cruise" in vessel_type:
                if vessel_name and vessel_name not in ships:
                    ships.append(vessel_name)

    if not ships:
        # Fallback: scan raw text for patterns like "D1C   <ShipName>" or "Cruise Ship <ShipName>"
        berth_pattern = re.compile(
            r"\bD1C\b[^\n<]{0,60}?([A-Z][A-Za-z0-9 .'-]{3,})",
            re.IGNORECASE,
        )
        for m in berth_pattern.finditer(html):
            name = m.group(1).strip()
            if name and name not in ships:
                ships.append(name)

        cruise_pattern = re.compile(
            r"cruise\s+ship\s*[:\-]?\s*([A-Z][A-Za-z0-9 .'-]{3,})",
            re.IGNORECASE,
        )
        for m in cruise_pattern.finditer(html):
            name = m.group(1).strip()
            if name and name not in ships:
                ships.append(name)

    return ", ".join(ships) if ships else "None"


def fetch_cruise_ships() -> str:
    """Fetch and return cruise ship names from Belfast Harbour movements page."""
    try:
        html = _fetch_text(BELFAST_HARBOUR_URL)
        return _extract_cruise_ships(html)
    except Exception:  # noqa: BLE001
        return "None"


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

def _load_cruise_ships_from_file(path: str) -> str:
    """Return cruise ship names parsed from a saved harbour movements HTML file."""
    return _extract_cruise_ships(Path(path).read_text(encoding="utf-8"))

def build_html(message):
    return f"""
    <html>
    <head>
        <title>BT19 Daily Numbers</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f7f9fc;
                color: #333;
                line-height: 1.6;
            }}

            .container {{
                max-width: 700px;
                margin: auto;
                background: white;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}

            h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                text-align: center;
                color: #1a73e8;
            }}

            .section {{
                margin-top: 25px;
            }}

            .section h2 {{
                font-size: 20px;
                margin-bottom: 10px;
                color: #444;
                border-bottom: 2px solid #e5e5e5;
                padding-bottom: 6px;
            }}

            .item {{
                margin-bottom: 8px;
                font-size: 17px;
            }}

            .emoji {{
                font-size: 20px;
                margin-right: 6px;
            }}

            footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 14px;
                color: #777;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>BT19 Daily Numbers</h1>

            <div class="section">
                <h2>Summary</h2>
                <div class="item">{message.replace("\n", "<br>")}</div>
            </div>

            <footer>
                Updated automatically by GitHub Actions
            </footer>
        </div>
    </body>
    </html>
    """




def main() -> str:
    parser = argparse.ArgumentParser(description="Generate BT19/Belfast daily numbers")
    parser.add_argument("--weather-json", help="Path to saved Open-Meteo payload")
    parser.add_argument("--tide-html", help="Path to saved Belfast tide page HTML")
    parser.add_argument("--cruise-html", help="Path to saved Belfast Harbour movements HTML")
    args = parser.parse_args()

    weather = _load_weather_from_file(args.weather_json) if args.weather_json else fetch_weather()
    tides = _load_tides_from_file(args.tide_html) if args.tide_html else fetch_tides()
    cruise_ship = _load_cruise_ships_from_file(args.cruise_html) if args.cruise_html else fetch_cruise_ships()

    message = build_message(weather, tides, cruise_ship=cruise_ship)

    html_path = Path(__file__).parent / "docs" / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(build_html(message), encoding="utf-8")

    # RETURN the final message instead of printing it
    return message


if __name__ == "__main__":
    import sys
    # Send the returned message directly to Shortcuts
    sys.stdout.write(main())
    
