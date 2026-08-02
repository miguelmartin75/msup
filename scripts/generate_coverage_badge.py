#!/usr/bin/env python3

import json
import sys
from pathlib import Path


def badge_color(percentage: int) -> str:
    if percentage >= 90:
        result = "#4c1"
    elif percentage >= 75:
        result = "#97ca00"
    elif percentage >= 50:
        result = "#dfb317"
    else:
        result = "#e05d44"
    return result


def generate_badge(coverage_path: Path, badge_path: Path) -> None:
    data = json.loads(coverage_path.read_text())
    percentage = round(data["totals"]["percent_covered"])
    color = badge_color(percentage)
    badge_path.parent.mkdir(parents=True, exist_ok=True)
    badge_path.write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20" role="img" aria-label="coverage: {percentage}%">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-opacity=".1" stop-color="#fff"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a">
    <rect width="112" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#a)">
    <rect width="67" height="20" fill="#555"/>
    <rect x="67" width="45" height="20" fill="{color}"/>
    <rect width="112" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
    <text x="33.5" y="15" fill="#010101" fill-opacity=".3">coverage</text>
    <text x="33.5" y="14">coverage</text>
    <text x="88.5" y="15" fill="#010101" fill-opacity=".3">{percentage}%</text>
    <text x="88.5" y="14">{percentage}%</text>
  </g>
</svg>
''',
        encoding="utf-8",
    )


def main() -> None:
    repo_root = Path(__file__).parent.parent
    coverage_path = repo_root / "coverage-artifacts/coverage.json"
    badge_path = repo_root / "coverage-artifacts/site/coverage.svg"
    if len(sys.argv) == 3:
        coverage_path = Path(sys.argv[1])
        badge_path = Path(sys.argv[2])
    elif len(sys.argv) != 1:
        raise SystemExit("usage: generate_coverage_badge.py [coverage.json coverage.svg]")
    generate_badge(coverage_path, badge_path)


if __name__ == "__main__":
    main()
