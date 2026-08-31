from datetime import datetime, timedelta
import json
import os

DATA_FILE = "data.json"

def load_data():
    """Load your stored daily numbers from JSON."""
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def get_today_key():
    return datetime.now().strftime("%Y-%m-%d")

def get_yesterday_key():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_summary(data):
    today = get_today_key()
    yesterday = get_yesterday_key()

    today_total = data.get(today, 0)
    yesterday_total = data.get(yesterday, 0)

    diff = today_total - yesterday_total

    if diff > 0:
        change_text = f"Up by {diff} compared to yesterday."
    elif diff < 0:
        change_text = f"Down by {abs(diff)} compared to yesterday."
    else:
        change_text = "No change compared to yesterday."

    return f"Today's total is {today_total}. {change_text}"

def get_running_total(data):
    total = sum(data.values())
    return f"Running total across all days: {total}"

def get_notes(data):
    if not data:
        return "No data available yet. Your system is ready and waiting for new entries."
    return "Data loaded successfully. No issues detected."

def build_html():
    data = load_data()

    today = datetime.now().strftime("%A %d %B %Y")
    summary_text = get_summary(data)
    running_text = get_running_total(data)
    notes_text = get_notes(data)

    html = f"""
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
                <p class="date">{today}</p>
            </header>

            <section class="card">
                <h2>Summary</h2>
                <p>{summary_text}</p>
            </section>

            <section class="card">
                <h2>Running Total</h2>
                <p>{running_text}</p>
            </section>

            <section class="card">
                <h2>Notes</h2>
                <p>{notes_text}</p>
            </section>

        </div>
    </body>
    </html>
    """

    return html
