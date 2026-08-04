# Daily-Numbers

Daily environment summary for a single iPhone-friendly message each morning:

1. Sunrise time for BT19 (UK)
2. Tide times for Belfast
3. Current outside air temperature
4. Current wind speed in knots
5. Wind gusts in knots
6. Whether it is raining

## Usage

```bash
python3 daily_summary.py
```

The script prints a compact multi-line message that can be sent by your preferred notification tool/automation.

### Offline/manual verification mode

```bash
python3 daily_summary.py \
  --weather-json tests/fixtures/weather.json \
  --tide-html tests/fixtures/tides.html
```

---

## Running as a web app (shortcut on Safari / Android)

`app.py` is a small Flask web app that serves the daily summary as a page you can
pin to your phone's home screen — just like a native app.

### 1. Install the extra dependency

```bash
pip install flask
```

### 2. Run the server

```bash
python3 app.py
```

The app listens on **port 5000** by default. Open `http://<your-host>:5000` in a
browser to see the daily numbers.

### 3. Add to home screen

**Safari (iOS)**

1. Open the URL in Safari.
2. Tap the Share button (□↑).
3. Scroll down and tap **Add to Home Screen**.
4. Tap **Add** — an icon appears on your home screen.

**Android (Chrome)**

1. Open the URL in Chrome.
2. Tap the three-dot menu (⋮).
3. Tap **Add to Home screen**.
4. Tap **Add** — an icon appears on your home screen.

### 4. Free hosting options

Because the app fetches live data it needs a server. Two easy free options:

| Option | Notes |
|---|---|
| **[PythonAnywhere](https://www.pythonanywhere.com)** | Free tier supports one Flask web app. Upload `daily_summary.py` and `app.py`, set the WSGI entry point to `app.py`, and you get a permanent public URL. |
| **[Render](https://render.com)** | Connect this GitHub repo, set the start command to `python app.py`, and Render deploys automatically on every push. Free tier available. |

Once deployed, bookmark the public URL, then follow step 3 above to pin it to
your home screen.
