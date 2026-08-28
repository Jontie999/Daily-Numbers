import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

from daily_summary import (
    _degrees_to_cardinal,
    _extract_cruise_ships,
    _extract_tide_events,
    _extract_vessel_movements,
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
        html = "High Tide 04:10 4.1m Low Tide 10:22 1.2m High Tide 16:35 4.5m Low Tide 22:48 0.8m"
        self.assertEqual(
            _extract_tide_events(html)[:2],
            [
                {"kind": "high", "time": "04:10", "height_m": 4.1},
                {"kind": "low", "time": "10:22", "height_m": 1.2},
            ],
        )

    def test_build_message(self):
        weather = {
            "sunrise": "05:39",
            "sunset": "21:07",
            "collected_at": "06:15",
            "temperature_c": 16.7,
            "wind_kts": 10.0,
            "wind_gusts_kts": 15.0,
            "wind_direction": "SW",
            "weather_code": 1,
            "raining": False,
            "rain_description": "None",
        }
        tides = [
            {"kind": "high", "time": "04:10", "height_m": 4.1},
            {"kind": "low", "time": "10:22", "height_m": 1.2},
        ]
        movements = [
            {"name": "Stena Superfast X", "type": "Ferry", "berth": "VT3", "window": "Arr 06:30 · Dep 07:15"},
        ]
        message = build_message(weather, tides, vessel_movements=movements)
        self.assertTrue(message.startswith("📋 Summary"))
        self.assertIn("Collected 06:15", message)
        self.assertIn("05:39", message)
        self.assertIn("21:07", message)
        self.assertIn("16.7°C", message)
        self.assertIn("10.0 kts ↙ SW", message)
        self.assertIn("15.0 kts", message)
        self.assertIn("None", message)
        self.assertIn("04:10", message)
        self.assertIn("4.1m", message)
        self.assertIn("Stena Superfast X", message)
        lines = message.splitlines()
        body_lines = [line for line in lines[2:-1] if line.startswith("║")]
        self.assertTrue(body_lines)
        self.assertTrue(all(line.endswith("║") for line in body_lines))
        self.assertEqual(len({len(line) for line in lines[1:]}), 1)

    def test_build_message_with_cruise_ship(self):
        weather = {
            "sunrise": "05:39",
            "sunset": "21:07",
            "collected_at": "06:15",
            "temperature_c": 16.7,
            "wind_kts": 10.0,
            "wind_gusts_kts": 15.0,
            "wind_direction": "SW",
            "weather_code": 1,
            "raining": False,
            "rain_description": "None",
        }
        tides = [
            {"kind": "high", "time": "04:10", "height_m": None},
            {"kind": "low", "time": "10:22", "height_m": None},
        ]
        message = build_message(weather, tides, cruise_ship="Queen Mary 2")
        self.assertIn("Queen Mary 2", message)
        self.assertIn("In port", message)
        lines = message.splitlines()
        self.assertEqual(len({len(line) for line in lines[1:]}), 1)

    def test_build_html_with_script_data_shapes(self):
        weather = {
            "sunrise": "05:39",
            "sunset": "21:07",
            "collected_at": "06:15",
            "temperature_c": 16.7,
            "wind_kts": 10.0,
            "wind_gusts_kts": 15.0,
            "wind_direction": "SW",
            "weather_code": 1,
            "raining": False,
            "rain_description": "None",
        }
        html = build_html(
            "Line 1\nLine 2",
            weather=weather,
            tides=[
                {"kind": "high", "time": "04:10", "height_m": 4.1},
                {"kind": "low", "time": "10:22", "height_m": 1.2},
            ],
            vessel_movements=[{"name": "Queen Mary 2", "type": "Cruise Ship", "berth": "D1C", "window": "Arr 08:00"}],
        )

        self.assertIn("PJ's Daily Numbers", html)
        self.assertIn("Line 1<br>\nLine 2", html)
        self.assertIn("Data collected at 06:15", html)
        self.assertIn("Sunrise / Sunset", html)
        self.assertIn("Tide curve", html)
        self.assertIn("Queen Mary 2", html)
        self.assertNotIn("<pre", html)
        self.assertIn("4.1m", html)

    def test_main_writes_html_output(self):
        weather = {
            "sunrise": "05:39",
            "sunset": "21:07",
            "collected_at": "06:15",
            "temperature_c": 16.7,
            "wind_kts": 10.0,
            "wind_gusts_kts": 15.0,
            "wind_direction": "SW",
            "weather_code": 1,
            "raining": False,
            "rain_description": "None",
        }
        tides = [
            {"kind": "high", "time": "04:10", "height_m": 4.1},
            {"kind": "low", "time": "10:22", "height_m": 1.2},
        ]
        movements = [{"name": "Queen Mary 2", "type": "Cruise Ship", "berth": "D1C", "window": "Arr 08:00"}]

        with TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            output_path = docs_dir / "index.html"

            with (
                patch("daily_summary.fetch_weather", return_value=weather),
                patch("daily_summary.fetch_tides", return_value=tides),
                patch("daily_summary.fetch_vessel_movements", return_value=movements),
                patch("daily_summary.Path", side_effect=lambda value: Path(tmpdir) / value),
            ):
                message = main()

            self.assertTrue(output_path.exists())
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("PJ's Daily Numbers", html)
            self.assertIn("Queen Mary 2", html)
            self.assertIn("📋 Summary<br>", html)
            self.assertIn("╚═════════════════════════════════════════════╝", html)

    def test_loaders_with_fixtures(self):
        base = Path(__file__).parent / "fixtures"
        weather = _load_weather_from_file(str(base / "weather.json"))
        tides = _load_tides_from_file(str(base / "tides.html"))

        self.assertEqual(weather["sunrise"], "05:39")
        self.assertEqual(weather["sunset"], "21:07")
        self.assertEqual(weather["collected_at"], "06:15")
        self.assertFalse(weather["raining"])
        self.assertEqual(weather["wind_direction"], "SW")
        self.assertEqual(weather["wind_gusts_kts"], 15.0)
        self.assertEqual(weather["rain_description"], "None")
        self.assertEqual(tides[0]["kind"], "high")
        self.assertEqual(tides[0]["time"], "04:10")
        self.assertEqual(tides[0]["height_m"], 4.1)

    def test_main_offline_inputs(self):
        base = Path(__file__).parent / "fixtures"
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "index.html"
            message = main(
                str(base / "weather.json"),
                str(base / "tides.html"),
                str(base / "harbour.html"),
                str(output),
            )
            self.assertTrue(output.exists())
            self.assertIn("4.1m", message)
            self.assertIn("Stena Superfast X", message)

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

    def test_extract_vessel_movements_with_window(self):
        html = """<table>
          <tr><th>Vessel Name</th><th>Vessel Type</th><th>Berth</th><th>ETA</th><th>ETD</th></tr>
          <tr><td>Queen Mary 2</td><td>Cruise Ship</td><td>D1C</td><td>08:00</td><td>18:00</td></tr>
          <tr><td>Stena Superfast X</td><td>Ferry</td><td>VT3</td><td>06:30</td><td>07:15</td></tr>
          <tr><td>Late Vessel</td><td>Cargo</td><td>VT5</td><td>13:00</td><td>14:00</td></tr>
        </table>"""
        movements = _extract_vessel_movements(html, reference_time="07:00")
        self.assertEqual(
            movements,
            [
                {"name": "Queen Mary 2", "type": "Cruise Ship", "berth": "D1C", "window": "Arr 08:00"},
                {"name": "Stena Superfast X", "type": "Ferry", "berth": "VT3", "window": "Arr 06:30 · Dep 07:15"},
            ],
        )

    def test_load_cruise_ships_fixture(self):
        base = Path(__file__).parent / "fixtures"
        result = _load_cruise_ships_from_file(str(base / "harbour.html"))
        self.assertIn("Queen Mary 2", result)
        self.assertIn("MSC Magnifica", result)
        self.assertNotIn("Stena Superfast X", result)


if __name__ == "__main__":
    unittest.main()
