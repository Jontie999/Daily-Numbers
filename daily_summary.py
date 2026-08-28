# coding: utf-8


#!/usr/bin/env python3
"""Build a daily environmen environment summary for BT19/Belfast."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_LAT = 54.6658
_LON = -5.6948
BELFAST_TIDE_URL = "https://www.tidetimes.org.uk/belfast-tide-times"
BELFAST_HARBOUR_URL = "https://www.belfast-harbour.co.uk/port-info/harbour-movements/"

# Berths used by cruise ships in Belfast Harbour
_CRUISE_BERTHS = {"d1c", "d1", "d3", "d4"}

# Cardinal direction labels (16-point compass, each covers 22.5°)
_CARDINAL_DIRS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]

_DIRECTION_ARROWS = {
    "N": "↑",
    "NNE": "↗",
    "NE": "↗",
    "ENE": "↗",
    "E": "→",
    "ESE": "↘",
    "SE": "↘",
    "SSE": "↘",
    "S": "↓",
    "SSW": "↙",
    "SW": "↙",
    "WSW": "↙",
    "W": "←",
    "WNW": "↖",
    "NW": "↖",
    "NNW": "↖",
}

_WEATHER_CODE_ICON = {
    0: "clear",
    1: "partly-cloudy",
    2: "partly-cloudy",
    3: "cloudy",
    45: "cloudy",
    48: "cloudy",
    51: "rain",
    53: "rain",
    55: "rain",
    56: "rain",
    57: "rain",
    61: "rain",
    63: "rain",
    65: "rain",
    66: "rain",
    67: "rain",
    71: "cloudy",
    73: "cloudy",
    75: "cloudy",
    77: "cloudy",
    80: "rain",
    81: "rain",
    82: "rain",
    85: "cloudy",
    86: "cloudy",
    95: "storm",
    96: "storm",
    99: "storm",
}

_SVG_ICONS = {
    "clear": """<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="9" fill="#FDB813"/><g stroke="#FDB813" stroke-linecap="round" stroke-width="3"><path d="M24 4v7"/><path d="M24 37v7"/><path d="M4 24h7"/><path d="M37 24h7"/><path d="M10 10l5 5"/><path d="M33 33l5 5"/><path d="M10 38l5-5"/><path d="M33 15l5-5"/></g></svg>""",
    "partly-cloudy": """<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="18" cy="18" r="7" fill="#FDB813"/><path d="M15 35h19a7 7 0 0 0 0-14 10 10 0 0 0-19-2 7 7 0 0 0 0 16Z" fill="#D9E6F2" stroke="#8BA3B8" stroke-width="2"/></svg>""",
    "cloudy": """<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M14 35h20a8 8 0 0 0 0-16 11 11 0 0 0-21-2 8 8 0 0 0 1 18Z" fill="#D9E6F2" stroke="#8BA3B8" stroke-width="2"/></svg>""",
    "rain": """<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M14 29h20a8 8 0 0 0 0-16 11 11 0 0 0-21-2 8 8 0 0 0 1 18Z" fill="#D9E6F2" stroke="#8BA3B8" stroke-width="2"/><g stroke="#4A90E2" stroke-linecap="round" stroke-width="3"><path d="M18 34l-2 6"/><path d="M25 34l-2 6"/><path d="M32 34l-2 6"/></g></svg>""",
    "storm": """<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M14 29h20a8 8 0 0 0 0-16 11 11 0 0 0-21-2 8 8 0 0 0 1 18Z" fill="#D9E6F2" stroke="#8BA3B8" stroke-width="2"/><path d="M24 20l-4 9h5l-3 9 10-13h-5l3-5Z" fill="#F5A623"/></svg>""",
    "daylight": """<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 32a16 16 0 0 1 32 0" fill="none" stroke="#FDB813" stroke-width="3" stroke-linecap="round"/><circle cx="24" cy="24" r="6" fill="#FDB813"/><path d="M6 38h36" stroke="#8BA3B8" stroke-width="3" stroke-linecap="round"/></svg>""",
    "tide": """<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M6 28c4 0 4-4 8-4s4 4 8 4 4-4 8-4 4 4 8 4 4-4 8-4" fill="none" stroke="#2E86DE" stroke-width="3" stroke-linecap="round"/><path d="M6 36c4 0 4-4 8-4s4 4 8 4 4-4 8-4 4 4 8 4 4-4 8-4" fill="none" stroke="#74B9FF" stroke-width="3" stroke-linecap="round"/></svg>""",
    "vessel": """<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 29h32l-4 8-12 5-12-5-4-8Z" fill="#4A90E2"/><path d="M14 18h12v11H14Z" fill="#D9E6F2"/><path d="M28 22h6v7h-6Z" fill="#8BA3B8"/></svg>""",
    "updated": """<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="16" fill="none" stroke="#8BA3B8" stroke-width="3"/><path d="M24 14v11l7 4" fill="none" stroke="#4A90E2" stroke-linecap="round" stroke-width="3"/></svg>""",
}


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
    request = Request(url, headers={"User-Agent": "Daily-Numbers/1.0"})
    with urlopen(request, timeout=20) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def _fetch_json(url: str) -> dict:
    return json.loads(_fetch_text(url))


def _format_time(value: str) -> str:
    dt = datetime.fromisoformat(value)
    return dt.strftime("%H:%M")


def _normalize_clock_time(value: str) -> str:
    clean = value.strip().upper().replace(" ", "")
    if clean.endswith(("AM", "PM")):
        return datetime.strptime(clean, "%I:%M%p").strftime("%H:%M")
    return datetime.strptime(clean, "%H:%M").strftime("%H:%M")


def _time_to_minutes(value: str) -> int:
    hours, minutes = map(int, _normalize_clock_time(value).split(":"))
    return hours * 60 + minutes


def _direction_to_arrow(direction: str) -> str:
    return _DIRECTION_ARROWS.get(direction.upper(), "•") if direction else "•"


def _weather_icon_name(weather: dict) -> str:
    if weather.get("raining"):
        return "rain"
    return _WEATHER_CODE_ICON.get(int(weather.get("weather_code", 0)), "clear")


def _sparkline(values: list[float]) -> str:
    if not values:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    low = min(values)
    high = max(values)
    if high == low:
        return bars[4] * len(values)
    return "".join(
        bars[round(((value - low) / (high - low)) * (len(bars) - 1))]
        for value in values
    )


def _daylight_bar(sunrise: str, sunset: str, width: int = 24) -> str:
    if not sunrise or not sunset:
        return ""
    start = _time_to_minutes(sunrise)
    end = _time_to_minutes(sunset)
    slots = []
    for idx in range(width):
        minute = (idx / width) * 1440
        slots.append("█" if start <= minute <= end else "░")
    return "".join(slots)


def _parse_harbour_table_rows(html: str) -> list[list[str]]:
    from html.parser import HTMLParser

    class _TableParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.rows: list[list[str]] = []
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
                    self.rows.append(self._current_row)
                self._current_row = None

        def handle_data(self, data: str) -> None:
            if self._in_cell and self._current_cell is not None:
                self._current_cell.append(data.strip())

    parser = _TableParser()
    parser.feed(html)
    return parser.rows


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
            "latitude": _LAT,
            "longitude": _LON,
            "daily": "sunrise,sunset",
            "current": "temperature_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation,rain,weather_code",
            "hourly": "precipitation",
            "timezone": "Europe/London",
            "forecast_days": 1,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    payload = _fetch_json(url)

    try:
        sunrise = payload["daily"]["sunrise"][0]
        sunset = payload["daily"]["sunset"][0]
        current = payload["current"]
        temp_c = float(current["temperature_2m"])
        wind_kph = float(current["wind_speed_10m"])
        wind_gusts_kph = float(current.get("wind_gusts_10m", wind_kph))
        wind_dir_deg = float(current.get("wind_direction_10m", 0.0))
        rain_mm = float(current.get("rain", 0.0))
        precipitation_mm = float(current.get("precipitation", 0.0))
        weather_code = int(current.get("weather_code", 0))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DataError("Unexpected weather data format") from exc

    morning_precip = _extract_morning_precip(payload)

    return {
        "sunrise": _format_time(sunrise),
        "sunset": _format_time(sunset),
        "collected_at": _format_time(current["time"]) if current.get("time") else datetime.now().strftime("%H:%M"),
        "temperature_c": round(temp_c, 1),
        "wind_kts": round(wind_kph / 1.852, 1),
        "wind_gusts_kts": round(wind_gusts_kph / 1.852, 1),
        "wind_direction": _degrees_to_cardinal(wind_dir_deg),
        "weather_code": weather_code,
        "raining": rain_mm > 0.0 or precipitation_mm > 0.0,
        "rain_description": _rain_description(morning_precip),
    }


def _extract_tide_events(html: str) -> list[dict[str, str | float | None]]:
    patterns = [
        re.compile(
            r"(?i)\b(high|low)\s+tide\b[^\d]*(\d{1,2}:\d{2}(?:\s*[ap]m)?)(?:[^\d]{0,12}(\d+(?:\.\d+)?)\s*m)?"
        ),
        re.compile(
            r"(?i)\b(high|low)\b[^\d]*(\d{1,2}:\d{2}(?:\s*[ap]m)?)(?:[^\d]{0,12}(\d+(?:\.\d+)?)\s*m)?"
        ),
    ]
    for pattern in patterns:
        events = [
            {
                "kind": kind.lower(),
                "time": _normalize_clock_time(tide_time),
                "height_m": float(height) if height else None,
            }
            for kind, tide_time, height in pattern.findall(html)
        ]
        if events:
            return events
    return []


def fetch_tides() -> list[dict[str, str | float | None]]:
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
    rows = _parse_harbour_table_rows(html)
    ships: list[str] = []

    if rows:
        # Identify header row to find column indices
        header_row = rows[0]
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

        for row in rows[1:]:
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


def _is_time_in_window(value: str, start: int, end: int) -> bool:
    minutes = _time_to_minutes(value)
    if start <= end:
        return start <= minutes <= end
    return minutes >= start or minutes <= end


def _extract_vessel_movements(
    html: str,
    reference_time: str | None = None,
) -> list[dict[str, str]]:
    rows = _parse_harbour_table_rows(html)
    if not rows:
        return []

    headers = [header.lower() for header in rows[0]]

    def _col(names: list[str]) -> int:
        for name in names:
            for idx, header in enumerate(headers):
                if name in header:
                    return idx
        return -1

    name_col = _col(["vessel", "ship", "name"])
    berth_col = _col(["berth"])
    type_col = _col(["type"])
    eta_col = _col(["eta", "arrival"])
    etd_col = _col(["etd", "departure"])
    reference = _normalize_clock_time(reference_time or datetime.now().strftime("%H:%M"))
    reference_minutes = _time_to_minutes(reference)
    start = (reference_minutes - 60) % 1440
    end = (reference_minutes + 180) % 1440

    movements: list[dict[str, str]] = []
    for row in rows[1:]:
        if not row:
            continue
        vessel_name = row[name_col].strip() if 0 <= name_col < len(row) else ""
        vessel_type = row[type_col].strip() if 0 <= type_col < len(row) else ""
        berth = row[berth_col].strip() if 0 <= berth_col < len(row) else ""
        eta = row[eta_col].strip() if 0 <= eta_col < len(row) else ""
        etd = row[etd_col].strip() if 0 <= etd_col < len(row) else ""

        labels: list[str] = []
        if eta:
            eta_time = re.search(r"\d{1,2}:\d{2}(?:\s*[ap]m)?", eta)
            if eta_time and _is_time_in_window(eta_time.group(0), start, end):
                labels.append(f"Arr { _normalize_clock_time(eta_time.group(0)) }")
        if etd:
            etd_time = re.search(r"\d{1,2}:\d{2}(?:\s*[ap]m)?", etd)
            if etd_time and _is_time_in_window(etd_time.group(0), start, end):
                labels.append(f"Dep { _normalize_clock_time(etd_time.group(0)) }")

        if vessel_name and labels:
            movements.append(
                {
                    "name": vessel_name,
                    "type": vessel_type or "Vessel",
                    "berth": berth or "TBC",
                    "window": " · ".join(labels),
                }
            )

    return movements


def fetch_vessel_movements(reference_time: str | None = None) -> list[dict[str, str]]:
    try:
        html = _fetch_text(BELFAST_HARBOUR_URL)
        return _extract_vessel_movements(html, reference_time=reference_time)
    except Exception:  # noqa: BLE001
        return []


def fetch_cruise_ships() -> str:
    """Fetch and return cruise ship names from Belfast Harbour movements page."""
    try:
        html = _fetch_text(BELFAST_HARBOUR_URL)
        return _extract_cruise_ships(html)
    except Exception:  # noqa: BLE001
        return "None"


def build_message(
    weather: dict,
    tides: list[dict[str, str | float | None]],
    cruise_ship: str | None = None,
    vessel_movements: list[dict[str, str]] | None = None,
) -> str:
    rain_desc = weather.get("rain_description", "Yes" if weather["raining"] else "None")
    wind_dir = weather.get("wind_direction", "")
    wind_arrow = _direction_to_arrow(str(wind_dir))
    wind_str = f"{weather['wind_kts']:.1f} kts {wind_arrow} {wind_dir}".strip()
    gusts_str = f"{weather.get('wind_gusts_kts', weather['wind_kts']):.1f} kts"
    vessel_movements = vessel_movements or []
    if cruise_ship and not vessel_movements and cruise_ship != "None":
        vessel_movements = [{"name": cruise_ship, "type": "Cruise Ship", "berth": "D1C", "window": "In port"}]

    tide_curve = _sparkline(
        [
            float(tide["height_m"]) if tide.get("height_m") is not None else (1.0 if tide["kind"] == "high" else 0.0)
            for tide in tides
        ]
    )
    content_lines = [
        "🌅 BT19 DAILY",
        f"🕒 Collected {weather.get('collected_at', '')}".rstrip(),
        f"🌄 Sunrise {weather['sunrise']}",
    ]
    if weather.get("sunset"):
        content_lines.append(f"🌇 Sunset {weather['sunset']}")
        content_lines.append(f"☀️ Daylight {_daylight_bar(weather['sunrise'], weather['sunset'], width=18)}")
    content_lines.extend(
        [
            f"🌡️ Temp {weather['temperature_c']:.1f}°C",
            f"💨 Wind {wind_str}",
            f"💨 Gusts {gusts_str}",
            f"🌧️ Rain {rain_desc}",
            f"🌊 Tides (Belfast) {tide_curve}".rstrip(),
        ]
    )
    content_lines.extend(
        (
            f"{'🌊' if tide['kind'] == 'high' else '🏖️'} {str(tide['kind']).title()} "
            f"{tide['time']}"
            f"{(' ' + format(float(tide['height_m']), '.1f') + 'm') if tide.get('height_m') is not None else ''}"
        )
        for tide in tides
    )
    if vessel_movements:
        content_lines.append("🚢 Movements")
        content_lines.extend(
            f"• {movement['window']} {movement['name']} ({movement['type']}, {movement['berth']})"
            for movement in vessel_movements
        )
    else:
        content_lines.append("🚢 Movements None")
    width = max(len(line) for line in content_lines)

    def boxed(line: str) -> str:
        return f"║ {line:<{width}} ║"

    divider = f"╠{'═' * (width + 2)}╣"

    return "\n".join(
        [
            "📋 Summary",
            f"╔{'═' * (width + 2)}╗",
            boxed("🌅  BT19 DAILY"),
            divider,
            boxed(f"🕒 Collected {weather.get('collected_at', '')}".rstrip()),
            divider,
            boxed(f"🌄 Sunrise {weather['sunrise']}"),
            *([boxed(f"🌇 Sunset {weather['sunset']}"), boxed(f"☀️ Daylight {_daylight_bar(weather['sunrise'], weather['sunset'], width=18)}")] if weather.get("sunset") else []),
            divider,
            boxed(f"🌡️ Temp {weather['temperature_c']:.1f}°C"),
            boxed(f"💨 Wind {wind_str}"),
            boxed(f"💨 Gusts {gusts_str}"),
            boxed(f"🌧️ Rain {rain_desc}"),
            divider,
            boxed(f"🌊 Tides (Belfast) {tide_curve}".rstrip()),
            *[
                boxed(
                    f"{'🌊' if tide['kind'] == 'high' else '🏖️'} {tide['kind'].title()} "
                    f"{tide['time']}"
                    + (f" {float(tide['height_m']):.1f}m" if tide.get('height_m') is not None else "")

                )
                for tide in tides
            ],
            divider,
            boxed("🚢 Movements" if vessel_movements else "🚢 Movements None"),
            *[
                boxed(f"• {movement['window']} {movement['name']} ({movement['type']}, {movement['berth']})")
                for movement in vessel_movements
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
        "sunset": _format_time(payload["daily"]["sunset"][0]) if payload["daily"].get("sunset") else "",
        "collected_at": _format_time(current["time"]) if current.get("time") else "00:00",
        "temperature_c": round(float(current["temperature_2m"]), 1),
        "wind_kts": round(float(current["wind_speed_10m"]) / 1.852, 1),
        "wind_gusts_kts": round(float(current.get("wind_gusts_10m", current["wind_speed_10m"])) / 1.852, 1),
        "wind_direction": _degrees_to_cardinal(wind_dir_deg),
        "weather_code": int(current.get("weather_code", 0)),
        "raining": rain_mm > 0 or precipitation_mm > 0,
        "rain_description": _rain_description(morning_precip),
    }


def _load_tides_from_file(path: str) -> list[dict[str, str | float | None]]:
    events = _extract_tide_events(Path(path).read_text(encoding="utf-8"))
    if len(events) < 2:
        raise DataError("Unable to find Belfast tide times")
    return events[:4]

def _load_cruise_ships_from_file(path: str) -> str:
    """Return cruise ship names parsed from a saved harbour movements HTML file."""
    return _extract_cruise_ships(Path(path).read_text(encoding="utf-8"))

def build_html(message, weather=None, tides=None, cruise=None, vessel_movements=None):
    weather = weather or {}
    tides = tides or []
    vessel_movements = vessel_movements or []
    weather_icon = _SVG_ICONS[_weather_icon_name(weather or {"weather_code": 0, "raining": False})]
    updated_icon = _SVG_ICONS["updated"]
    daylight_icon = _SVG_ICONS["daylight"]
    tide_icon = _SVG_ICONS["tide"]
    vessel_icon = _SVG_ICONS["vessel"]
    tide_curve = _sparkline(
        [
            float(tide["height_m"]) if tide.get("height_m") is not None else (1.0 if tide["kind"] == "high" else 0.0)
            for tide in tides
        ]
    )
    
    
    tide_rows = "".join(
        (
            "<li>"
            f"<strong>{escape(str(tide['kind']).title())}</strong> "
            f"{escape(str(tide['time']))}"
            f"{(' · ' + format(float(tide['height_m']), '.1f') + 'm') if tide.get('height_m') is not None else ''}"
            "</li>"
        )
        for tide in tides
    )

    movement_rows = "".join(
        (
            "<li>"
            f"<strong>{escape(movement['window'])}</strong> "
            f"{escape(movement['name'])}"
            f" <span class='muted'>({escape(movement['type'])}, {escape(movement['berth'])})</span>"
            "</li>"
        )
        for movement in vessel_movements
    ) or "<li>None in the current window</li>"
    summary_lines = "<br>\n".join(escape(line) for line in str(message).splitlines())
    return f"""
    <html>
    <head>
        <title>PJ's Daily Numbers</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(180deg, #eef5fb 0%, #f7fbff 100%);
                color: #1d2a36;
            }}

            .container {{
                max-width: 960px;
                margin: auto;
            }}

            .hero {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                margin-bottom: 20px;
            }}

            h1 {{
                margin: 0;
                font-size: 32px;
                color: #1a73e8;
            }}

            .card {{
                background: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}

            .summary-box {{
                margin: 0;
                white-space: pre-wrap;
                overflow-x: auto;
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
                font-size: 16px;
                line-height: 1.5;
            }}

            .meta {{
                display: flex;
                align-items: center;
                gap: 10px;
                color: #5a6b7b;
                font-size: 15px;
            }}

            .card-title {{
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 22px;
                margin-bottom: 10px;
                font-weight: 600;
            }}

            .card-body {{
                font-size: 18px;
                line-height: 1.6;
            }}

            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 20px;
            }}

            .icon {{
                width: 28px;
                height: 28px;
                flex: 0 0 28px;
            }}

            .icon svg {{
                width: 100%;
                height: 100%;
                display: block;
            }}

            .daylight-bar {{
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
                font-size: 20px;
                letter-spacing: 1px;
                color: #f39c12;
            }}

            ul {{
                margin: 0;
                padding-left: 20px;
            }}

            .muted {{
                color: #6b7b8c;
            }}

            footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 14px;
                color: #777;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="hero">
                <div>
                    <h1>PJ's Daily Numbers</h1>
                    <div class="meta">
                        <span class="icon">{updated_icon}</span>
                        <span>Data collected at {escape(str(weather.get("collected_at", "Unknown")))}</span>
                    </div>
                </div>
                <div class="icon" style="width:56px;height:56px;">{weather_icon}</div>
            </div>

            <div class="card">
                <div class="card-title">📋 Summary</div>
                <div class="summary-box" role="region" aria-label="Daily summary">{summary_lines}</div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="card-title"><span class="icon">{daylight_icon}</span><span>Sunrise / Sunset</span></div>
                    <div class="card-body">
                        <div>{escape(str(weather.get("sunrise", "--:--")))} → {escape(str(weather.get("sunset", "--:--")))}</div>
                        <div class="daylight-bar">{escape(_daylight_bar(str(weather.get("sunrise", "")), str(weather.get("sunset", "")), width=24))}</div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title"><span class="icon">{tide_icon}</span><span>Tide curve</span></div>
                    <div class="card-body">
                        <div class="daylight-bar" style="color:#2e86de;">{escape(tide_curve)}</div>
                        <ul>{tide_rows}</ul>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title"><span class="icon">{vessel_icon}</span><span>Vessel movements (now -1h to +3h)</span></div>
                    <div class="card-body">
                        <ul>{movement_rows}</ul>
                    </div>
                </div>
            </div>

            <footer>Updated automatically by GitHub Actions</footer>
        </div>
    </body>
    </html>
    """



def main(
    weather_path: str | None = None,
    tide_path: str | None = None,
    harbour_path: str | None = None,
    output_path: str = "docs/index.html",
):
    weather = _load_weather_from_file(weather_path) if weather_path else fetch_weather()
    tides = _load_tides_from_file(tide_path) if tide_path else fetch_tides()
    if harbour_path:
        vessel_movements = _extract_vessel_movements(
            Path(harbour_path).read_text(encoding="utf-8"),
            reference_time=weather.get("collected_at"),
        )
    else:
        vessel_movements = fetch_vessel_movements(weather.get("collected_at"))

    message = build_message(weather, tides, vessel_movements=vessel_movements)

    html_path = Path(output_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(
        build_html(message, weather, tides, vessel_movements=vessel_movements),
        encoding="utf-8"
    )

    return message


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the BT19 daily summary.")
    parser.add_argument("--weather-json", help="Use a saved Open-Meteo response.")
    parser.add_argument("--tide-html", help="Use a saved Belfast tide page.")
    parser.add_argument("--harbour-html", help="Use a saved Belfast Harbour movements page.")
    parser.add_argument("--output", default="docs/index.html", help="HTML output path.")
    args = parser.parse_args()
    print(main(args.weather_json, args.tide_html, args.harbour_html, args.output))
