import unittest
from pathlib import Path

from daily_summary import (
    _degrees_to_cardinal,
    _extract_tide_events,
    _load_tides_from_file,
    _load_weather_from_file,
    _rain_description,
    build_message,
)


class DailySummaryTests(unittest.TestCase):
    def test_extract_tides(self):
        html = "High Tide 04:10 Low Tide 10:22 High Tide 16:35 Low Tide 22:48"
        self.assertEqual(
            _extract_tide_events(html)[:4],
            [("high", "04:10"), ("low", "10:22"), ("high", "16:35"), ("low", "22:48")],
        )

    def test_build_message(self):
        weather = {
            "sunrise": "05:39",
            "temperature_c": 16.7,
            "wind_kts": 10.0,
            "wind_gusts_kts": 15.0,
            "wind_direction": "SW",
            "raining": False,
            "rain_description": "None",
        }
        tides = [("high", "04:10"), ("low", "10:22")]
        message = build_message(weather, tides)
        self.assertIn("05:39", message)
        self.assertIn("16.7°C", message)
        self.assertIn("10.0 kts SW", message)
        self.assertIn("15.0 kts", message)
        self.assertIn("None", message)
        self.assertIn("04:10", message)
        self.assertIn("🚢 Cruise   None", message)
        lines = message.splitlines()
        body_lines = [line for line in lines[1:-1] if line.startswith("║")]
        self.assertTrue(body_lines)
        self.assertTrue(all(line.endswith("║") for line in body_lines))
        self.assertEqual(len({len(line) for line in lines}), 1)

    def test_build_message_with_cruise_ship(self):
        weather = {
            "sunrise": "05:39",
            "temperature_c": 16.7,
            "wind_kts": 10.0,
            "wind_gusts_kts": 15.0,
            "wind_direction": "SW",
            "raining": False,
            "rain_description": "None",
        }
        tides = [("high", "04:10"), ("low", "10:22")]
        message = build_message(weather, tides, cruise_ship="Queen Mary 2")
        self.assertIn("🚢 Cruise   Queen Mary 2", message)
        lines = message.splitlines()
        self.assertEqual(len({len(line) for line in lines}), 1)

    def test_loaders_with_fixtures(self):
        base = Path(__file__).parent / "fixtures"
        weather = _load_weather_from_file(str(base / "weather.json"))
        tides = _load_tides_from_file(str(base / "tides.html"))

        self.assertEqual(weather["sunrise"], "05:39")
        self.assertFalse(weather["raining"])
        self.assertEqual(weather["wind_direction"], "SW")
        self.assertEqual(weather["wind_gusts_kts"], 15.0)
        self.assertEqual(weather["rain_description"], "None")
        self.assertEqual(tides[0], ("high", "04:10"))

    def test_degrees_to_cardinal(self):
        self.assertEqual(_degrees_to_cardinal(0), "N")
        self.assertEqual(_degrees_to_cardinal(90), "E")
        self.assertEqual(_degrees_to_cardinal(180), "S")
        self.assertEqual(_degrees_to_cardinal(270), "W")
        self.assertEqual(_degrees_to_cardinal(225), "SW")

    def test_rain_description(self):
        self.assertEqual(_rain_description(0.0), "None")
        self.assertEqual(_rain_description(0.3), "Drizzle")
        self.assertEqual(_rain_description(1.0), "Light Rain")
        self.assertEqual(_rain_description(5.0), "Moderate Rain")
        self.assertEqual(_rain_description(10.0), "Heavy Rain")


if __name__ == "__main__":
    unittest.main()
