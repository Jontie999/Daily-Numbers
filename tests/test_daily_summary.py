import unittest
from pathlib import Path

from daily_summary import _extract_tide_events, _load_tides_from_file, _load_weather_from_file, build_message


class DailySummaryTests(unittest.TestCase):
    def test_extract_tides(self):
        html = "High Tide 04:10 Low Tide 10:22 High Tide 16:35 Low Tide 22:48"
        self.assertEqual(
            _extract_tide_events(html)[:4],
            [("high", "04:10"), ("low", "10:22"), ("high", "16:35"), ("low", "22:48")],
        )

    def test_build_message(self):
        weather = {"sunrise": "05:39", "temperature_c": 16.7, "wind_kts": 10.0, "raining": False}
        tides = [("high", "04:10"), ("low", "10:22")]
        message = build_message(weather, tides)
        self.assertIn("BT19 Sunrise: 05:39", message)
        self.assertIn("Air Temp Now: 16.7°C", message)
        self.assertIn("Wind Now: 10.0 kts", message)
        self.assertIn("Raining: No", message)

    def test_loaders_with_fixtures(self):
        base = Path(__file__).parent / "fixtures"
        weather = _load_weather_from_file(str(base / "weather.json"))
        tides = _load_tides_from_file(str(base / "tides.html"))

        self.assertEqual(weather["sunrise"], "05:39")
        self.assertFalse(weather["raining"])
        self.assertEqual(tides[0], ("high", "04:10"))


if __name__ == "__main__":
    unittest.main()
