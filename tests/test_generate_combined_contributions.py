from __future__ import annotations

import importlib.util
import unittest
from datetime import date
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "generate_combined_contributions.py"
)
SPEC = importlib.util.spec_from_file_location("combined_contributions", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load contribution generator")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CombinedContributionsTests(unittest.TestCase):
    def test_parses_daily_counts(self) -> None:
        document = """
        <td data-date="2026-08-09" id="day-1" class="ContributionCalendar-day"></td>
        <tool-tip for="day-1">No contributions on August 9th.</tool-tip>
        <td data-date="2026-08-10" id="day-2" class="ContributionCalendar-day"></td>
        <tool-tip for="day-2">1,234 contributions on August 10th.</tool-tip>
        """

        self.assertEqual(
            MODULE.parse_contributions(document),
            {date(2026, 8, 9): 0, date(2026, 8, 10): 1234},
        )

    def test_merges_calendars_by_date(self) -> None:
        first = {date(2026, 8, 10): 2, date(2026, 8, 11): 1}
        second = {date(2026, 8, 10): 5, date(2026, 8, 12): 3}

        self.assertEqual(
            MODULE.merge_contributions([first, second]),
            {
                date(2026, 8, 10): 7,
                date(2026, 8, 11): 1,
                date(2026, 8, 12): 3,
            },
        )

    def test_renders_accessible_combined_svg(self) -> None:
        counts = {
            date(2026, 8, 9): 0,
            date(2026, 8, 10): 7,
            date(2026, 8, 11): 2,
        }

        svg = MODULE.render_svg(counts, ["sxfivglz", "SofiaNeurya"])

        self.assertIn("Combined GitHub contribution activity", svg)
        self.assertIn("sxfivglz and SofiaNeurya", svg)
        self.assertIn('data-date="2026-08-10"', svg)
        self.assertIn('data-count="7"', svg)
        self.assertIn("7 combined contributions on 2026-08-10", svg)
        self.assertIn("prefers-color-scheme:dark", svg)

    def test_rejects_invalid_username(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.validate_username("invalid/user")


if __name__ == "__main__":
    unittest.main()
