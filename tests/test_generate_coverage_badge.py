import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.generate_coverage_badge import generate_badge


class GenerateCoverageBadgeTests(unittest.TestCase):
    def generate_svg(self, percentage: float) -> str:
        with TemporaryDirectory() as directory:
            coverage_path = Path(directory) / "coverage.json"
            badge_path = Path(directory) / "site" / "coverage.svg"
            coverage_path.write_text(
                json.dumps(
                    {
                        "totals": {
                            "percent_covered": percentage,
                            "percent_covered_display": f"{percentage:.0f}",
                        }
                    }
                ),
                encoding="utf-8",
            )
            generate_badge(coverage_path, badge_path)
            result = badge_path.read_text(encoding="utf-8")
        return result

    def test_generates_a_whole_number_percentage(self):
        coverage_path = Path(__file__).parent / "fixtures" / "coverage_94_851.json"
        with TemporaryDirectory() as directory:
            badge_path = Path(directory) / "site" / "coverage.svg"
            generate_badge(coverage_path, badge_path)
            svg = badge_path.read_text(encoding="utf-8")

        self.assertIn('aria-label="coverage: 95%"', svg)
        self.assertIn(">95%</text>", svg)

    def test_uses_expected_colors_at_threshold_boundaries(self):
        expected_colors = [
            (90, "#4c1"),
            (89, "#97ca00"),
            (75, "#97ca00"),
            (74, "#dfb317"),
            (50, "#dfb317"),
            (49, "#e05d44"),
        ]

        for percentage, color in expected_colors:
            with self.subTest(percentage=percentage):
                svg = self.generate_svg(percentage)

                self.assertIn(f'fill="{color}"', svg)
                self.assertIn(f">{percentage}%</text>", svg)


if __name__ == "__main__":
    unittest.main()
