# coding: utf-8
#!/usr/bin/env python3
"""Build a daily environment summary for BT19/Belfast."""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Location coordinates for BT19 (Bangor)
_LAT = 54.6658
_LON = -5.6948

BELFAST_TIDE_URL = "https://www.tidetimes.org.uk/belfast-tide-times"
BELFAST_HARBOUR_URL = "https://www.belfast-harbour.co.uk/port-info/harbour-movements/"

_CRUISE_BERTHS = {"d1c", "d1", "d3", "d4"}

_CARDINAL_DIRS = [
    "N","NNE","NE","ENE","E","ESE","SE","SSE",
    "S","SSW","SW","WSW","W","WNW","NW","NNW",
]

_DIRECTION_ARROWS = {
    "N":"↑","NNE":"↗","NE":"↗","ENE":"↗","E":"→","ESE":"↘","SE":"↘","SSE":"↘",
    "S":"↓","SSW":"↙","SW":"↙","WSW":"↙","W":"←","WNW":"↖","NW":"↖","NNW":"↖",
}

class DataError(RuntimeError):
    pass

def _degrees_to_cardinal(d) -> str:
    if d is None:
        return "N"
    try:
        degrees = float(d)
        idx = int((degrees + 11.25) / 22.5) % 16
        return _CARDINAL_DIRS[idx]
    except (ValueError, TypeError):
        return "N"

def _rain_description(precip_mm: float) -> str:
    if precip_mm <= 0:
        return "No rain expected"
    elif precip_mm < 1.0:
        return "Light drizzle expected"
    elif precip_mm < 4.0:
        return "Moderate rain expected"
    return "Heavy rain expected"

def _fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")

def _fetch_json(url: str) -> dict:
    text = _fetch_text(url)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise DataError("API down or returned invalid JSON.") from e

def _format_time(value: str) -> str:
    try:
        if "T" in value:
            return value.split("T")[1][:5]
        return value
    except Exception:
        return value

def _normalize_clock_time(value: str) -> str:
    clean = value.strip().upper().replace(" ", "")
    if clean.endswith(("AM","PM")):
        return datetime.strptime(clean, "%I:%M%p").strftime("%H:%M")
    return datetime.strptime(clean, "%H:%M").strftime("%H:%M")

def _direction_to_arrow(direction: str) -> str:
    return _DIRECTION_ARROWS.get(direction.upper(), "•")

def _extract_tide_events(html: str):
    matches = re.findall(r'<tr>\s*<td>(High|Low)</td>\s*<td>(\d{2}:\d{2})</td>\s*<td>([^<]+)</td>', html, re.DOTALL | re.IGNORECASE)
    tide_list = []
    for kind, time_str, height in matches:
        try:
            formatted_time = _normalize_clock_time(time_str)
            tide_list.append({"kind": kind.title(), "time": formatted_time, "height_m": height.strip()})
        except Exception:
            continue
    return tide_list

def _extract_morning_precip(payload: dict) -> float:
    try:
        times = payload["hourly"]["time"]
        precip = payload["hourly"]["precipitation"]
    except KeyError:
        return 0.0
    vals = [p for t,p in zip(times,precip) if "T05:" <= t[11:] <= "T07:59"]
    return max(vals, default=0.0)

def fetch_weather() -> dict:
    params = urlencode({
        "latitude": _LAT,
        "longitude": _LON,
        "daily": "sunrise,sunset",
        "current": "temperature_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation,rain,weather_code",
        "hourly": "precipitation",
        "timezone": "Europe/London",
        "forecast_days": 1,
    })
    payload = _fetch_json(f"https://api.open-meteo.com/v1/forecast?{params}")

    try:
        sunrise = payload["daily"]["sunrise"][0]
        current = payload["current"]
        temp = float(current["temperature_2m"])
        wind = float(current["wind_speed_10m"])
        gusts = float(current.get("wind_gusts_10m", wind))
        wind_dir = float(current.get("wind_direction_10m", 0))
        rain_mm = float(current.get("rain", 0))
        precip_mm = float(current.get("precipitation", 0))
        code = int(current.get("weather_code", 0))
    except Exception as exc:
        raise DataError("Unexpected weather data format") from exc

    morning = _extract_morning_precip(payload)

    return {
        "sunrise": _format_time(sunrise),
        "temperature_c": round(temp,1),
        "wind_kts": round(wind/1.852,1),
        "wind_gusts_kts": round(gusts/1.852,1),
        "wind_direction": _degrees_to_cardinal(wind_dir),
        "weather_code": code,
        "raining": rain_mm>0 or precip_mm>0,
        "rain_description": _rain_description(morning),
    }

def fetch_tides():
    try:
        html = _fetch_text(BELFAST_TIDE_URL)
        events = _extract_tide_events(html)
        return events[:4] if events else [{"kind": "High", "time": "See Web", "height_m": "--"}]
    except Exception:
        return [{"kind": "Error", "time": "Unavailable", "height_m": "--"}]

def _parse_harbour_table_rows(html: str) -> list[list[str]]:
    from html.parser import HTMLParser
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows = []
            self.current_row = None
            self.current_cell = None
            self.in_cell = False
        def handle_starttag(self, tag, attrs):
            if tag == "tr": 
                self.current_row = []
            elif tag in {"td", "th"}:
                self.current_cell = []
                self.in_cell = True
        def handle_endtag(self, tag):
            if tag in {"td", "th"} and self.current_cell is not None:
                self.current_row.append(" ".join(self.current_cell).strip())
                self.current_cell = None
                self.in_cell = False
            elif tag == "tr" and self.current_row is not None:
                self.rows.append(self.current_row)
                self.current_row = None
        def handle_data(self, data):
            if self.in_cell and self.current_cell is not None:
                self.current_cell.append(data.strip())
    p = Parser()
    p.feed(html)
    return [r for r in p.rows if r]

def fetch_cruise_ships():
    return "None Currently"

def fetch_vessel_movements():
    try:
        html = _fetch_text(BELFAST_HARBOUR_URL)
        rows = _parse_harbour_table_rows(html)
        movements_list = []
        for row in rows:
            clean_row = [cell for cell in row if cell.strip()]
            if len(clean_row) >= 4:
                movements_list.append({
                    "window": clean_row[0],
                    "name": clean_row[1],
                    "type": clean_row[2],
                    "berth": clean_row[3]
                })
        return movements_list[:5]
    except Exception:
        return []

def build_message(weather: dict, tides: list, cruise: str, vessels: list) -> str:
    return f"Summary for BT19: Temp {weather['temperature_c']}C"

def build_html(message: str, weather: dict, tides: list, cruise: str, vessels: list) -> str:
    from flask import render_template_string
    
    tide_html_rows = "".join(
        f"<div class='list-item'><strong>{t['kind']} Tide</strong> <span>{t['time']} <small class='muted'>({t['height_m']})</small></span></div>" 
        for t in tides
    )
    
    ship_html_rows = "".join(
        f"<div class='list-item'><strong>{escape(m['name'])}</strong> <span>{escape(m['window'])} <small class='muted'>({escape(m['berth'])})</small></span></div>" 
        for m in vessels
    ) or "<div class='list-item muted'>No active shipping assignments found.</div>"
    
    arrow = _direction_to_arrow(weather['wind_direction'])
    
    with open("dashboard.html", "r", encoding="utf-8") as f:
        template_content = f.read()
        
    return render_template_string(
        template_content,
        sunrise=weather['sunrise'],
        temperature_c=weather['temperature_c'],
        wind_kts=weather['wind_kts'],
        arrow=arrow,
        wind_direction=weather['wind_direction'],
        wind_gusts_kts=weather['wind_gusts_kts'],
        rain_status="Raining" if weather['raining'] else "Dry",
        rain_description=weather['rain_description'],
        tide_rows=tide_html_rows,
        cruise=escape(cruise),
        ship_rows=ship_html_rows
    )
