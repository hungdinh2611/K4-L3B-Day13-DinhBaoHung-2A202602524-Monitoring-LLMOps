from __future__ import annotations

import argparse
import html
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_dashboard import load_dashboard_config

COLORS = ("#4f46e5", "#0f9d75", "#d97706")
PLOT_WIDTH = 720
PLOT_HEIGHT = 210


def _percentile(values: list[float], percent: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _read_recent_records(
    log_path: Path, *, now: datetime, window_minutes: int
) -> list[tuple[datetime, dict[str, Any]]]:
    if not log_path.is_file():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    cutoff = now - timedelta(minutes=window_minutes)
    records: list[tuple[datetime, dict[str, Any]]] = []
    for line_number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid structured log at {log_path}:{line_number}") from exc
        if not isinstance(record, dict) or timestamp.tzinfo is None:
            raise ValueError(f"Invalid structured log at {log_path}:{line_number}")
        timestamp = timestamp.astimezone(timezone.utc)
        if cutoff <= timestamp <= now:
            records.append((timestamp, record))
    return records


def _bucket_index(timestamp: datetime, start: datetime) -> int:
    return max(0, min(59, int((timestamp - start).total_seconds() // 60)))


def _count_by_minute(
    records: list[tuple[datetime, dict[str, Any]]],
    *,
    event: str,
    start: datetime,
) -> list[float]:
    buckets = [0.0] * 60
    for timestamp, record in records:
        if record.get("event") == event:
            buckets[_bucket_index(timestamp, start)] += 1
    return buckets


def _values_by_minute(
    records: list[tuple[datetime, dict[str, Any]]],
    *,
    event: str,
    field: str,
    start: datetime,
) -> list[list[float]]:
    buckets: list[list[float]] = [[] for _ in range(60)]
    for timestamp, record in records:
        value = record.get(field)
        if record.get("event") == event and isinstance(value, (int, float)):
            buckets[_bucket_index(timestamp, start)].append(float(value))
    return buckets


def _sum_by_minute(
    records: list[tuple[datetime, dict[str, Any]]],
    *,
    event: str,
    field: str,
    start: datetime,
) -> list[float]:
    buckets = [0.0] * 60
    for timestamp, record in records:
        value = record.get(field)
        if record.get("event") == event and isinstance(value, (int, float)):
            buckets[_bucket_index(timestamp, start)] += float(value)
    return buckets


def _cumulative(values: list[float]) -> list[float]:
    total = 0.0
    result = []
    for value in values:
        total += value
        result.append(total)
    return result


def _format_value(value: float | None, unit: str) -> str:
    if value is None:
        return "No data"
    if unit == "usd":
        return f"${value:.6f}"
    if unit == "percent":
        return f"{value:.2f}%"
    if unit == "ms":
        return f"{value:.1f} ms"
    if unit == "score_0_to_1":
        return f"{value:.3f}"
    if unit == "requests_per_minute":
        return f"{value:.2f} requests/min"
    if unit == "count":
        return f"{value:,.0f} requests"
    return f"{value:,.0f} tokens"


def build_dashboard(
    log_path: Path,
    config_path: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    config = load_dashboard_config(config_path)["dashboard"]
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window_minutes = config["time_range_minutes"]
    start = now.replace(second=0, microsecond=0) - timedelta(minutes=window_minutes - 1)
    records = _read_recent_records(
        log_path, now=now, window_minutes=window_minutes
    )

    received = _count_by_minute(records, event="request_received", start=start)
    failed = _count_by_minute(records, event="request_failed", start=start)
    error_rate = [
        (failure / count * 100) if count else None
        for failure, count in zip(failed, received)
    ]
    tool_samples: list[list[bool]] = [[] for _ in range(60)]
    for timestamp, record in records:
        value = record.get("tool_success")
        if isinstance(value, bool):
            tool_samples[_bucket_index(timestamp, start)].append(value)
    retrieval_by_minute = [
        (sum(samples) / len(samples) * 100) if samples else None
        for samples in tool_samples
    ]
    tool_values = [value for samples in tool_samples for value in samples]
    retrieval_success = (
        sum(tool_values) / len(tool_values) * 100 if tool_values else None
    )
    request_count = sum(received)
    error_count = sum(failed)

    latency = _values_by_minute(
        records, event="response_sent", field="latency_ms", start=start
    )
    ttft = _values_by_minute(
        records, event="response_sent", field="ttft_ms", start=start
    )
    cost = _sum_by_minute(records, event="response_sent", field="cost_usd", start=start)
    tokens_in = _sum_by_minute(
        records, event="response_sent", field="tokens_in", start=start
    )
    tokens_out = _sum_by_minute(
        records, event="response_sent", field="tokens_out", start=start
    )
    quality = _values_by_minute(
        records, event="response_sent", field="quality_score", start=start
    )

    latency_values = [value for bucket in latency for value in bucket]
    ttft_values = [value for bucket in ttft for value in bucket]
    quality_values = [value for bucket in quality for value in bucket]
    cost_total = sum(cost)
    token_total = sum(tokens_in) + sum(tokens_out)
    quality_mean = (
        sum(quality_values) / len(quality_values) if quality_values else None
    )

    raw_panels: dict[str, dict[str, Any]] = {
        "latency": {
            "summary": [
                ("P50", _percentile(latency_values, 50)),
                ("P95", _percentile(latency_values, 95)),
                ("P99", _percentile(latency_values, 99)),
                ("TTFT P95", _percentile(ttft_values, 95)),
            ],
            "series": [
                {
                    "label": "Latency P95",
                    "values": [_percentile(bucket, 95) for bucket in latency],
                },
                {
                    "label": "TTFT P95",
                    "values": [_percentile(bucket, 95) for bucket in ttft],
                },
            ],
        },
        "traffic": {
            "summary": [("Requests", request_count), ("Rate", request_count / window_minutes)],
            "series": [{"label": "Requests/min", "values": received}],
        },
        "errors": {
            "summary": [
                ("Error rate", error_count / request_count * 100 if request_count else None),
                ("Retrieval success", retrieval_success),
            ],
            "series": [
                {"label": "Error rate", "values": error_rate},
                {"label": "Retrieval success", "values": retrieval_by_minute},
            ],
        },
        "cost": {
            "summary": [("Window total", cost_total)],
            "series": [{"label": "Cumulative cost", "values": _cumulative(cost)}],
        },
        "tokens": {
            "summary": [("Input", sum(tokens_in)), ("Output", sum(tokens_out)), ("Total", token_total)],
            "series": [
                {"label": "Input tokens (cumulative)", "values": _cumulative(tokens_in)},
                {"label": "Output tokens (cumulative)", "values": _cumulative(tokens_out)},
            ],
        },
        "quality": {
            "summary": [("Mean quality", quality_mean)],
            "series": [
                {
                    "label": "Quality proxy",
                    "values": [
                        sum(bucket) / len(bucket) if bucket else None
                        for bucket in quality
                    ],
                }
            ],
        },
    }

    panels = []
    for panel in config["panels"]:
        values = raw_panels[panel["id"]]
        panels.append(
            {
                **panel,
                **values,
                "now": now.isoformat(),
            }
        )
    return {
        "title": config["title"],
        "window_minutes": window_minutes,
        "refresh_seconds": config["refresh_seconds"],
        "records_in_window": len(records),
        "panels": panels,
    }


def _svg_chart(panel: dict[str, Any]) -> str:
    chart_width, chart_height = PLOT_WIDTH, PLOT_HEIGHT
    left, right, top, bottom = 50, chart_width - 14, 14, chart_height - 34
    threshold = float(panel["threshold"]["value"])
    all_values = [
        value
        for series in panel["series"]
        for value in series["values"]
        if value is not None
    ]
    maximum = max([threshold, *all_values], default=1.0)
    minimum = min([0.0, *all_values], default=0.0)
    if panel["id"] == "quality":
        maximum = max(1.0, maximum)
        minimum = 0.0
    if maximum <= minimum:
        maximum = minimum + 1
    else:
        maximum *= 1.08

    def x_for(index: int, count: int) -> float:
        return left + (right - left) * index / max(1, count - 1)

    def y_for(value: float) -> float:
        return bottom - (value - minimum) / (maximum - minimum) * (bottom - top)

    elements = [
        f'<svg viewBox="0 0 {chart_width} {chart_height}" role="img" '
        f'aria-label="{html.escape(panel["title"])} chart">'
    ]
    for fraction in (0, 0.5, 1):
        y = bottom - (bottom - top) * fraction
        label = minimum + (maximum - minimum) * fraction
        elements.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="gridline"/>'
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="axis">'
            f'{html.escape(_format_value(label, panel["unit"]))}</text>'
        )

    threshold_y = y_for(threshold)
    elements.append(
        f'<line x1="{left}" y1="{threshold_y:.1f}" x2="{right}" y2="{threshold_y:.1f}" '
        f'class="threshold"/>'
    )
    for series_index, series in enumerate(panel["series"]):
        color = COLORS[series_index % len(COLORS)]
        points = []
        for index, value in enumerate(series["values"]):
            if value is None:
                if points:
                    elements.append(
                        f'<polyline points="{" ".join(points)}" fill="none" '
                        f'stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
                    )
                    points = []
                continue
            points.append(f"{x_for(index, len(series['values'])):.1f},{y_for(value):.1f}")
        if points:
            elements.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
            )
    elements.extend(
        [
            f'<text x="{left}" y="{chart_height - 8}" class="axis">60m ago</text>',
            f'<text x="{right}" y="{chart_height - 8}" text-anchor="end" class="axis">now (UTC)</text>',
            "</svg>",
        ]
    )
    return "".join(elements)


def render_dashboard(data: dict[str, Any]) -> str:
    cards = []
    for panel in data["panels"]:
        summary_items = []
        for label, value in panel["summary"]:
            unit = panel["unit"]
            if panel["id"] == "traffic" and label == "Requests":
                unit = "count"
            summary_items.append(
                '<div class="stat"><span>'
                f'{html.escape(label)}</span><strong>'
                f'{html.escape(_format_value(value, unit))}</strong></div>'
            )
        summary = "".join(summary_items)
        legend = "".join(
            f'<span><i style="background:{COLORS[index % len(COLORS)]}"></i>'
            f'{html.escape(series["label"])}</span>'
            for index, series in enumerate(panel["series"])
        )
        display_unit = {
            "requests_per_minute": "requests/min",
            "score_0_to_1": "score (0-1)",
        }.get(panel["unit"], panel["unit"])
        threshold = panel["threshold"]
        threshold_text = (
            f'{threshold["aggregation"]} {threshold["operator"]} '
            f'{_format_value(float(threshold["value"]), panel["unit"])}'
        )
        cards.append(
            f'<article class="panel" id="{html.escape(panel["id"])}">'
            f'<div class="panel-head"><div><h2>{html.escape(panel["title"])}</h2>'
            f'<span class="unit">{html.escape(display_unit)}</span></div>'
            f'<span class="threshold-label">Threshold: {html.escape(threshold_text)}</span></div>'
            f'<div class="stats">{summary}</div>{_svg_chart(panel)}'
            f'<div class="legend">{legend}<span class="threshold-key">Threshold</span></div>'
            "</article>"
        )
    updated = datetime.fromisoformat(data["panels"][0]["now"]).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{data['refresh_seconds']}">
<title>{html.escape(data['title'])}</title>
<style>
:root {{ color-scheme: light; font-family: Inter, Segoe UI, sans-serif; color: #172033; background: #f3f5f9; }}
body {{ margin: 0; padding: 28px; }}
header {{ max-width: 1500px; margin: 0 auto 20px; }}
h1 {{ margin: 0 0 8px; font-size: 25px; }}
.meta,.unit {{ color: #68748a; font-size: 13px; }}
.card-grid {{ max-width: 1500px; margin: auto; display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; }}
.panel {{ background: white; border: 1px solid #e1e6ef; border-radius: 12px; padding: 18px; box-shadow: 0 4px 16px #23395d0a; min-width: 0; }}
.panel-head {{ display: flex; justify-content: space-between; align-items: start; gap: 12px; }}
h2 {{ margin: 0 0 4px; font-size: 17px; }}
.threshold-label {{ color: #a23c36; font-size: 12px; text-align: right; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 12px 22px; padding: 14px 0 4px; }}
.stat span {{ display: block; color: #68748a; font-size: 11px; }}
.stat strong {{ display: block; font-size: 17px; margin-top: 3px; }}
svg {{ width: 100%; height: auto; overflow: visible; }}
.gridline {{ stroke: #e8ebf1; stroke-width: 1; }}
.threshold {{ stroke: #dc4c45; stroke-width: 1.8; stroke-dasharray: 6 5; }}
.axis {{ fill: #758097; font-size: 10px; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 14px; color: #647087; font-size: 11px; }}
.legend i {{ display:inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; }}
.threshold-key::before {{ content:""; display:inline-block; width:14px; border-top:2px dashed #dc4c45; margin:0 5px 3px 0; }}
@media(max-width: 850px) {{ body {{ padding: 14px; }} .card-grid {{ grid-template-columns: 1fr; }} .panel-head {{ flex-direction: column; }} .threshold-label {{ text-align:left; }} }}
</style>
</head>
<body>
<header><h1>{html.escape(data["title"])}</h1><div class="meta">
Window: last {data["window_minutes"]} minutes · Refresh: {data["refresh_seconds"]} seconds ·
Updated: {html.escape(updated)} · {data["records_in_window"]} log events</div></header>
<main class="card-grid">{''.join(cards)}</main>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    log_path = REPO_ROOT / "data" / "logs.jsonl"
    config_path = REPO_ROOT / "config" / "dashboard.yaml"

    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        try:
            data = build_dashboard(self.log_path, self.config_path)
            content = render_dashboard(data).encode("utf-8")
        except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
            content = (
                "<!doctype html><meta charset=utf-8><h1>Dashboard data error</h1><pre>"
                + html.escape(str(exc))
                + "</pre>"
            ).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local LLMOps dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--log-path", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    args = parser.parse_args()
    handler = type(
        "ConfiguredDashboardHandler",
        (DashboardHandler,),
        {"log_path": args.log_path, "config_path": args.config},
    )
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f"Dashboard available at http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
