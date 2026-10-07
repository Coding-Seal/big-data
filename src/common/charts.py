"""
Gold layer: turn a question's result into a chart *spec*, not an image.

Vega-Lite specs separate encoding (which data fields map to which visual
channels -- x, y, color, ...) from mark (the chart type -- bar, line,
point, area, ...). Keeping those separate here is the whole point: changing
a chart's type is changing one string (see config.yaml's `gold:` section),
not touching a question's data or field layout. The same spec also renders
as either a static image or a fully interactive chart (vega-embed) with no
backend -- how these actually get displayed isn't decided yet, and nothing
here commits to a renderer.
"""
from typing import Any


def to_vega_lite(
    rows: list[dict[str, Any]],
    encoding: dict[str, Any],
    mark: str = "bar",
    title: str | None = None,
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": rows},
        "mark": mark,
        "encoding": encoding,
    }
    if title:
        spec["title"] = title
    return spec
