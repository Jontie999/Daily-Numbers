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
python3 /home/runner/work/Daily-Numbers/Daily-Numbers/daily_summary.py
```

The script prints a compact multi-line message that can be sent by your preferred notification tool/automation.

### Offline/manual verification mode

```bash
python3 /home/runner/work/Daily-Numbers/Daily-Numbers/daily_summary.py \
  --weather-json /home/runner/work/Daily-Numbers/Daily-Numbers/tests/fixtures/weather.json \
  --tide-html /home/runner/work/Daily-Numbers/Daily-Numbers/tests/fixtures/tides.html
```
