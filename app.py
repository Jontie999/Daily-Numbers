from flask import Flask, Response
from daily_summary import build_html

app = Flask(__name__, static_folder='static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route("/")
from flask import Flask, Response
from daily_summary import build_html

app = Flask(__name__, static_folder='static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route("/")
def index():
    try:
        html = build_html()
        return Response(html, mimetype="text/html")
    except Exception as e:
        return f"<p>Error generating page: {e}</p>"
