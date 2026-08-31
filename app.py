from flask import Flask, Response, make_response
from daily_summary import build_html

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route('/static/<path:filename>')
def staticfiles(filename):
    return app.send_static_file(filename)

@app.route("/")
def index():
    weather = fetch_weather()
    tides = fetch_tides()
    cruise = fetch_cruise_ships()
    vessels = fetch_vessel_movements()

    message = build_message(weather, tides, cruise, vessels)

    return build_html(message, weather, tides, cruise, vessels)
