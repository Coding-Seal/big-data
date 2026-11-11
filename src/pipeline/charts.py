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
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _jsonable(value: Any) -> Any:
    """Spark types that json.dumps refuses, mapped to what Vega-Lite wants.

    A TimestampType column arrives as a `datetime`, and a `"type":
    "temporal"` encoding expects ISO-8601 -- which is exactly
    `datetime.isoformat()`, so this is a conversion, not a lossy fallback.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def to_vega_lite(
    rows: list[dict[str, Any]],
    encoding: dict[str, Any],
    mark: str = "bar",
    title: str | None = None,
) -> dict[str, Any]:
    values = [{k: _jsonable(v) for k, v in row.items()} for row in rows]
    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": values},
        "mark": mark,
        "encoding": encoding,
    }
    if title:
        spec["title"] = title
    return spec
