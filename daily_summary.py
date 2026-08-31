from __future__ import annotations
import datetime

def build_html():
    today = datetime.date.today().strftime("%A %d %B %Y")

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Numbers</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>

    <body>
        <div class="container">

            <header>
                <h1>Daily Numbers</h1>
                <p class="date">{today}</p>
            </header>

            <section class="card">
                <h2>Weather</h2>
                <p>Sunrise, sunset, and tide curve removed as requested.</p>
            </section>

            <section class="card">
                <h2>Daylight</h2>
                <p>Clean modern layout. No ASCII bars.</p>
            </section>

            <section class="card">
                <h2>Summary</h2>
                <p>Your daily summary goes here.</p>
            </section>

        </div>
    </body>
    </html>
    """

    return html
