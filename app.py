#!/usr/bin/env python3
"""Simple Flask web app that serves the BT19 daily summary as a web page."""

from __future__ import annotations

from flask import Flask, render_template_string

from daily_summary import build_message, fetch_cruise_ships, fetch_tides, fetch_weather

app = Flask(__name__)

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="default" />
  <meta name="apple-mobile-web-app-title" content="BT19 Daily" />
  <meta name="theme-color" content="#1a73e8" />
  <link rel="manifest" href="/manifest.json" />
  <title>BT19 Daily Numbers</title>
  <style>
    body {
      font-family: monospace;
      background: #0d1117;
      color: #c9d1d9;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      min-height: 100vh;
      margin: 0;
      padding: 1rem;
      box-sizing: border-box;
    }
    h1 { font-size: 1.1rem; color: #58a6ff; margin-bottom: 0.5rem; }
    pre {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 1rem;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 0.95rem;
      line-height: 1.5;
      max-width: 100%;
    }
    .error { color: #f85149; }
    .reload {
      margin-top: 1rem;
      padding: 0.5rem 1.2rem;
      background: #1a73e8;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 1rem;
      cursor: pointer;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <h1>🌅 BT19 Daily Numbers</h1>
  {% if error %}
    <pre class="error">{{ error }}</pre>
  {% else %}
    <pre>{{ message }}</pre>
  {% endif %}
  <a class="reload" href="/">🔄 Refresh</a>
</body>
</html>
"""


@app.route("/")
def index():
    try:
        weather = fetch_weather()
        tides = fetch_tides()
        cruise_ship = fetch_cruise_ships()
        message = build_message(weather, tides, cruise_ship=cruise_ship)
        return render_template_string(_HTML, message=message, error=None)
    except Exception as exc:  # noqa: BLE001
        return render_template_string(_HTML, message=None, error=str(exc)), 500


@app.route("/manifest.json")
def manifest():
    from flask import jsonify

    return jsonify(
        {
            "name": "BT19 Daily Numbers",
            "short_name": "BT19 Daily",
            "description": "Daily environment summary for BT19/Belfast",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0d1117",
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
