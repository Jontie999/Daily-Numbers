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

# Location
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

def _fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Daily-Numbers/1.0"})
    with urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")

def _fetch_json(url: str) -> dict:
    return json.loads(_fetch_text(url))

def _format_time(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%H:%M")

def _normalize_clock_time(value: str) -> str:
    clean = value.strip().upper().replace(" ", "")
    if clean.endswith(("AM","PM")):
        return datetime.strptime(clean, "%I:%M%p").strftime("%H:%M")
    return datetime.strptime(clean, "%H:%M").strftime("%H:%M")

def _time_to_minutes(value: str) -> int:
    h,m = map(int, _normalize_clock_time(value).split(":"))
    return h*60 + m

def _direction_to_arrow(direction: str) -> str:
    return _DIRECTION_ARROWS.get(direction.upper(), "•")

def _sparkline(values: list[float]) -> str:
    if not values: return ""
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if hi == lo:
        return bars[4] * len(values)
    return "".join(bars[round(((v-lo)/(hi-lo))*(len(bars)-1))] for v in values)

def _daylight_bar(sunrise: str, sunset: str, width=24) -> str:
    if not sunrise or not sunset: return ""
    start = _time_to_minutes(sunrise)
    end = _time_to_minutes(sunset)
    out = []
    for i in range(width):
        minute = (i/width)*1440
        out.append("█" if start <= minute <= end else "░")
    return "".join(out)

def _parse_harbour_table_rows(html: str) -> list[list[str]]:
    from html.parser import HTMLParser
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows=[]
            self.row=None
            self.cell=None
            self.in_cell=False
        def handle_starttag(self, tag, attrs):
            if tag=="tr": self.row=[]
            elif tag in {"td","th"} and self.row is not None:
                self.cell=[]
                self.in_cell=True
        def handle_endtag(self, tag):
            if tag in {"td","th"} and self.cell is not None:
                self.row.append(" ".join(self.cell).strip())
                self.cell=None
                self.in_cell=False
            elif tag=="tr" and self.row:
                self.rows.append(self.row)
                self.row=None
        def handle_data(self, data):
            if self.in_cell and self.cell is not None:
                self.cell.append(data.strip())
    p=Parser()
    p.feed(html)
    return p.rows

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
        sunset = payload["daily"]["sunset"][0]
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
        "sunset": _format_time(sunset),
        "collected_at": _format_time(current.get("time", datetime.now().isoformat())),
        "temperature_c": round(temp,1),
        "wind_kts": round(wind/1.852,1),
        "wind_gusts_kts": round(gusts/1.852,1),
        "wind_direction": _degrees_to_cardinal(wind_dir),
        "weather_code": code,
        "raining": rain_mm>0 or precip_mm>0,
        "rain_description": _rain_description(morning),
    }

def _extract_tide_events(html: str):
    patterns = [
        re.compile(r"(?i)\b(high|low)\s+tide\b[^\d]*(\d{1,2}:\d{2}(?:\s*[ap]m)?)(?:[^\d]{0,12}(\d+(?:\.\d+)?)\s*m)?"),
        re.compile(r"(?i)\b(high|low)\b[^\d]*(\d{1,2}:\d{2}(?:\s*[ap]m)?)(?:[^\d]{0,12}(\d+(?:\.\d+)?)\s*m)?"),
    ]
    for pat in patterns:
        events = [
            {"kind":k.lower(),"time":_normalize_clock_time(t),"height_m":float(h) if h else None}
            for k,t,h in pat.findall(html)
        ]
        if events:
            return events
    return []

def fetch_tides():
    html = _fetch_text(BELFAST_TIDE_URL)
    events = _extract_tide_events(html)
    if len(events)<2:
        raise DataError("Unable to find Belfast tide times")
    return events[:4]

def _extract_cruise_ships(html: str) -> str:
    rows = _parse_harbour_table_rows(html)
    ships=[]
    if rows:
        headers=[h.lower() for h in rows[0]]
        def col(names):
            for name in names:
                for i,h in enumerate(headers):
                    if name in h:
                        return i
            return -1
        name_col=col(["vessel","ship","name"])
        berth_col=col(["berth"])
        type_col=col(["type"])
        for row in rows[1:]:
            if not row: continue
            name=row[name_col].strip() if 0<=name_col<len(row) else ""
            berth=row[berth_col].strip().lower() if 0<=berth_col<len(row) else ""
            typ=row[type_col].strip().lower() if 0<=type_col<len(row) else ""
            if berth in _CRUISE_BERTHS or "cruise" in typ:
                if name and name not in ships:
                    ships.append(name)
    if not ships:
        bpat=re.compile(r"\bD1C\b[^\n<]{0,60}?([A-Z][A-Za-z0-9 .'-]{3,})", re.I)
        for m in bpat.finditer(html):
            ships.append(m.group(1).strip())
        cpat=re.compile(r"cruise\s+ship\s*[:\-]?\s*([A-Z][A-Za-z0-9 .'-]{3,})", re.I)
        for m in cpat.finditer(html):
            ships.append(m.group(1).strip())
    return ", ".join(ships) if ships else "None"

def fetch_cruise_ships():
    try:
        html=_fetch_text(BELFAST_HARBOUR_URL)
        return _extract_cruise_ships(html)
    except Exception:
        return "None"

def _is_time_in_window(value: str, start: int, end: int) -> bool:
    m=_time_to_minutes(value)
    if start<=end:
        return start<=m<=end
    return m>=start or m<=end

def _extract_vessel_movements(html: str, reference_time=None):
    rows=_parse_harbour_table_rows(html)
    if not rows: return []
    headers=[h.lower() for h in rows[0]]
    def col(names):
        for name in names:
            for i,h in enumerate(headers):
                if name in h:
                    return i
        return -1
    name_col=col(["vessel","ship","name"])
    berth_col=col(["berth"])
    type_col=col(["type"])
    eta_col=col(["eta","arrival"])
    etd_col=col(["etd","departure"])
    ref=_normalize_clock_time(reference_time or datetime.now().strftime("%H:%M"))
    ref_m=_time_to_minutes(ref)
    start=(ref_m-60)%1440
    end=(ref_m+180)%1440
    out=[]
    for row in rows[1:]:
        if not row: continue
        name=row[name_col].strip() if 0<=name_col<len(row) else ""
        typ=row[type_col].strip() if 0<=type_col<len(row) else ""
        berth=row[berth_col].strip() if 0<=berth_col<len(row) else ""
        eta=row[eta_col].strip() if 0<=eta_col<len(row) else ""
        etd=row[etd_col].strip() if 0<=etd_col<len(row) else ""
        labels=[]
        if eta:
            m=re.search(r"\d{1,2}:\d{2}(?:\s*[ap]m)?", eta)
            if m and _is_time_in_window(m.group(0), start, end):
                labels.append(f"Arr {_normalize_clock_time(m.group(0))}")
        if etd:
            m=re.search(r"\d{1,2}:\d{2}(?:\s*[ap]m)?", etd)
            if m and _is_time_in_window(m.group(0), start, end):
                labels.append(f"Dep {_normalize_clock_time(m.group(0))}")
        if name and labels:
            out.append({
                "name":name,
                "type":typ or "Vessel",
                "berth":berth or "TBC",
                "window":" · ".join(labels),
            })
    return out

def fetch_vessel_movements(reference_time=None):
    try:
        html=_fetch_text(BELFAST_HARBOUR_URL)
        return _extract_vessel_movements(html, reference_time)
    except Exception:
        return []

def build_message(weather, tides, cruise_ship=None, vessel_movements=None):
    rain_desc = weather.get("rain_description", "Yes" if weather.get("raining") else "None")
    wind_dir = weather.get("wind_direction", "")
    wind_arrow = _direction_to_arrow(wind_dir)
    wind_str = f"{weather['wind_kts']:.1f} kts {wind_arrow} {wind_dir}".strip()
    gusts_str = f"{weather.get('wind_gusts_kts', weather['wind_kts']):.1f} kts"

    vessel_movements = vessel_movements or []
    if cruise_ship and not vessel_movements and cruise_ship != "None":
        vessel_movements = [{"name": cruise_ship, "type": "Cruise Ship", "berth": "D1C", "window": "In port"}]

    tide_curve = _sparkline([
        float(t["height_m"]) if t.get("height_m") is not None else (1.0 if t["kind"]=="high" else 0.0)
        for t in tides
    ])

    lines = [
        "🌅 BT19 DAILY",
        f"🕒 Collected {weather.get('collected_at','')}",
        f"🌄 Sunrise {weather['sunrise']}",
        f"🌇 Sunset {weather['sunset']}",
        f"☀️ Daylight {_daylight_bar(weather['sunrise'], weather['sunset'], width=18)}",
        f"🌡️ Temp {weather['temperature_c']:.1f}°C",
        f"💨 Wind {wind_str}",
        f"💨 Gusts {gusts_str}",
        f"🌧️ Rain {rain_desc}",
        f"🌊 Tides (Belfast) {tide_curve}",
    ]

    lines.extend(
        f"{'🌊' if t['kind']=='high' else '🏖️'} {t['kind'].title()} {t['time']}"
        + (f" {float(t['height_m']):.1f}m" if t.get("height_m") is not None else "")
        for t in tides
    )

    if vessel_movements:
        lines.append("🚢 Movements")
        lines.extend(
            f"• {m['window']} {m['name']} ({m['type']}, {m['berth']})"
            for m in vessel_movements
        )
    else:
        lines.append("🚢 Movements None")

    return "\n".join(lines)

def build_html(message, weather=None, tides=None, cruise=None, vessel_movements=None):
    weather = weather or {}
    tides = tides or []
    vessel_movements = vessel_movements or []

    sunrise = weather.get("sunrise", "--:--")
    sunset = weather.get("sunset", "--:--")
    collected = weather.get("collected_at", "Unknown")
    temp = weather.get("temperature_c", "--")
    wind_dir = weather.get("wind_direction", "")
    wind_kts = weather.get("wind_kts", "--")
    gusts_kts = weather.get("wind_gusts_kts", "--")
    rain_desc = weather.get("rain_description", "None")

    tide_rows = "".join(
        f"<li><strong>{t['kind'].title()}</strong> {t['time']}"
        + (f" · {float(t['height_m']):.1f}m" if t.get("height_m") is not None else "")
        + "</li>"
        for t in tides
    )

    movement_rows = "".join(
        f"<li><strong>{m['window']}</strong> {m['name']} "
        f"<span class='muted'>({m['type']}, {m['berth']})</span></li>"
        for m in vessel_movements
    ) or "<li>None in the current window</li>"

    summary_lines = "<br>".join(escape(line) for line in str(message).splitlines())

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Numbers</title>
        <link rel="stylesheet" href="/static/style.css?v=3">
    </head>

    <body>
        <div class="container">

            <header>
                <h1>Daily Numbers</h1>
                <p class="date">Collected at {escape(collected)}</p>
            </header>

            <section class="card">
                <h2>Summary</h2>
                <p>{summary_lines}</p>
            </section>

            <section class="card">
                <h2>Sunrise / Sunset</h2>
                <p>{escape(sunrise)} → {escape(sunset)}</p>
            </section>

            <section class="card">
                <h2>Weather</h2>
                <p>Temperature: {temp}°C</p>
                <p>Wind: {wind_kts} kts {wind_dir}</p>
                <p>Gusts: {gusts_kts} kts</p>
                <p>Rain: {
