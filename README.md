# Daily-Numbers

Daily environment summary for a single iPhone-friendly message each morning:

1. Sunrise time for BT19 (UK)
2. Tide times for Belfast
3. Current outside air temperature
4. Current wind speed in knots
5. Wind gusts in knots
6. Whether it is raining

---

## Quick start — access on any phone

The easiest way to use this on any iPhone or Android is to **deploy it once to Render** (free) and then **add a home-screen icon** on your phone.

### Deploy to Render (one click)

1. Go to [render.com](https://render.com) and sign in with your GitHub account.
2. Click **New → Web Service** and select the `Daily-Numbers` repository.
3. Render detects the `render.yaml` file automatically — just click **Create Web Service**.
4. After ~2 minutes you'll have a public URL such as `https://daily-numbers.onrender.com`.

Add that URL to your phone's home screen (see steps below) and you'll have an app icon that opens the live daily numbers.

---

## Usage (local / command line)

```bash
pip install -r requirements.txt
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

### 1. Install dependencies

```bash
pip install -r requirements.txt
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
| **[Render](https://render.com)** | Connect this GitHub repo — the included `render.yaml` configures everything automatically. Render deploys on every push. Free tier available. |
| **[PythonAnywhere](https://www.pythonanywhere.com)** | Free tier supports one Flask web app. Upload `daily_summary.py` and `app.py`, set the WSGI entry point to `app.py`, and you get a permanent public URL. |

Once deployed, bookmark the public URL, then follow step 3 above to pin it to
your home screen.
