from flask import Flask
from daily_summary import build_html

app = Flask(__name__, static_folder='static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route("/")
def index():
    try:
        return build_html()
    except Exception as e:
        return f"<p>Error generating page: {e}</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
