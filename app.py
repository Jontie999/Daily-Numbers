#!/usr/bin/env python3
"""Simple Flask web app that serves the BT19 daily summary as a web page."""

from __future__ import annotations

from flask import Flask, jsonify

from daily_summary import build_html, build_message, fetch_tides, fetch_vessel_movements, fetch_weather

app = Flask(__name__)

@app.route("/")
def index():
    try:
        weather = fetch_weather()
        tides = fetch_tides()
        vessel_movements = fetch_vessel_movements(weather.get("collected_at"))
        message = build_message(weather, tides, vessel_movements=vessel_movements)
        return build_html(message, weather, tides, vessel_movements=vessel_movements)
    except Exception:  # noqa: BLE001
        return (
            "<html><head><title>PJ's Daily Numbers</title></head>"
            "<body><pre>Unable to load the latest daily numbers right now.</pre></body></html>",
            500,
        )


@app.route("/manifest.json")
def manifest():
    return jsonify(
        {
            "name": "PJ's Daily Numbers",
            "short_name": "PJ Daily",
            "description": "Daily environment summary for BT19/Belfast",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#eef5fb",
            "theme_color": "#1a73e8",
            "icons": [
                {
                    "src": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f305.png",
                    "sizes": "72x72",
                    "type": "image/png",
                },
                {
                    "src": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f305.png",
                    "sizes": "192x192",
                    "type": "image/png",
                },
            ],
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
