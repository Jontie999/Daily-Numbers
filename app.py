from flask import Flask
from daily_summary import (
    fetch_weather,
    fetch_tides,
    fetch_cruise_ships,
    fetch_vessel_movements,
    build_message,
    build_html
)

app = Flask(__name__)

@app.route("/")
def index():
    weather = fetch_weather()
    tides = fetch_tides()
    cruise = fetch_cruise_ships()
    vessels = fetch_vessel_movements()

    message = build_message(weather, tides, cruise, vessels)

    return build_html(message, weather, tides, cruise, vessels)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
