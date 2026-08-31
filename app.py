from flask import Flask, Response, make_response
from daily_summary import build_html

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route('/static/<path:filename>')
def staticfiles(filename):
    return app.send_static_file(filename)

@app.route("/")
def index():
    html = build_html()
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response
