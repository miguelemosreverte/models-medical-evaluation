"""WSJ-style SVG chart utilities."""

from pathlib import Path


def get_chart_script() -> str:
    """Load the custom SVG charting JavaScript."""
    chart_js_path = Path(__file__).parent / "wsj_svg_charts.js"
    with open(chart_js_path, 'r') as f:
        return f.read()
