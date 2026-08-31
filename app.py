from flask import Flask, Response
from daily_summary import build_html

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route('/static/<path:filename>')
def staticfiles(filename):
    return app.send_static_file(filename)

@app.route("/")
def index():
    try:
        html = build_html()
        return Response(html, mimetype="text/html")
    except Exception as e:
        return f"<p>Error generating page: {e}</p>"
