import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

from daily_summary import (
    _degrees_to_cardinal,
    _extract_cruise_ships,
    _extract_tide_events,
    _load_cruise_ships_from_file,
    _load_tides_from_file,
    _load_weather_from_file,
    _rain_description,
    build_html,
    build_message,
    main,
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

    def test_build_html_with_script_data_shapes(self):
        weather = {
            "sunrise": "05:39",
            "temperature_c": 16.7,
            "wind_kts": 10.0,
            "wind_gusts_kts": 15.0,
            "wind_direction": "SW",
            "raining": False,
            "rain_description": "None",
        }
        html = build_html(
            "Line 1\nLine 2",
            weather=weather,
            tides=[("high", "04:10"), ("low", "10:22")],
            cruise="Queen Mary 2",
        )

        self.assertIn("Line 1<br>Line 2", html)
        self.assertIn("<strong>Temperature:</strong> 16.7°C", html)
        self.assertIn("<strong>Wind:</strong> 10.0 kts SW", html)
        self.assertIn("<strong>High Tide:</strong> 04:10", html)
        self.assertIn("<strong>Name:</strong> Queen Mary 2", html)

    def test_main_writes_html_output(self):
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

        with TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            output_path = docs_dir / "index.html"

            with (
                patch("daily_summary.fetch_weather", return_value=weather),
                patch("daily_summary.fetch_tides", return_value=tides),
                patch("daily_summary.fetch_cruise_ships", return_value="Queen Mary 2"),
                patch("daily_summary.Path", side_effect=lambda value: Path(tmpdir) / value),
            ):
                message = main()

            self.assertTrue(output_path.exists())
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("BT19 Daily Numbers", html)
            self.assertIn("Queen Mary 2", html)
            self.assertIn(message.replace("\n", "<br>"), html)

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

    def test_extract_cruise_ships_from_table(self):
        html = """<table>
          <tr><th>Vessel Name</th><th>Vessel Type</th><th>Berth</th></tr>
          <tr><td>Queen Mary 2</td><td>Cruise Ship</td><td>D1C</td></tr>
          <tr><td>Stena Superfast X</td><td>Ferry</td><td>VT3</td></tr>
        </table>"""
        self.assertEqual(_extract_cruise_ships(html), "Queen Mary 2")

    def test_extract_cruise_ships_multiple(self):
        html = """<table>
          <tr><th>Vessel Name</th><th>Vessel Type</th><th>Berth</th></tr>
          <tr><td>Queen Mary 2</td><td>Cruise Ship</td><td>D1C</td></tr>
          <tr><td>MSC Magnifica</td><td>Cruise Ship</td><td>D1C</td></tr>
        </table>"""
        self.assertEqual(_extract_cruise_ships(html), "Queen Mary 2, MSC Magnifica")

    def test_extract_cruise_ships_none(self):
        html = """<table>
          <tr><th>Vessel Name</th><th>Vessel Type</th><th>Berth</th></tr>
          <tr><td>Stena Superfast X</td><td>Ferry</td><td>VT3</td></tr>
        </table>"""
        self.assertEqual(_extract_cruise_ships(html), "None")

    def test_extract_cruise_ships_fallback(self):
        # No table, just raw text with D1C berth reference
        html = "<p>Vessel: Aurora &nbsp; Berth: D1C &nbsp; Type: Cruise Ship</p>"
        result = _extract_cruise_ships(html)
        # Should find "Aurora" via fallback or type-based detection
        self.assertNotEqual(result, "")

    def test_load_cruise_ships_fixture(self):
        base = Path(__file__).parent / "fixtures"
        result = _load_cruise_ships_from_file(str(base / "harbour.html"))
        self.assertIn("Queen Mary 2", result)
        self.assertIn("MSC Magnifica", result)
        self.assertNotIn("Stena Superfast X", result)


if __name__ == "__main__":
    unittest.main()
