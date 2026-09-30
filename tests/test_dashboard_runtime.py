from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.dashboard import build_dashboard, render_dashboard


def test_dashboard_aggregates_logs_and_renders_six_threshold_panels(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
    earlier = now - timedelta(minutes=1)
    records = [
        {
            "ts": earlier.isoformat(),
            "event": "request_received",
            "correlation_id": "req-11111111",
        },
        {
            "ts": earlier.isoformat(),
            "event": "response_sent",
            "latency_ms": 1000,
            "ttft_ms": 100,
            "tokens_in": 100,
            "tokens_out": 50,
            "cost_usd": 0.001,
            "quality_score": 0.8,
            "tool_success": True,
        },
        {
            "ts": now.isoformat(),
            "event": "request_received",
            "correlation_id": "req-22222222",
        },
        {
            "ts": now.isoformat(),
            "event": "request_failed",
            "error_type": "RuntimeError",
            "tool_success": False,
        },
    ]
    logs = tmp_path / "logs.jsonl"
    logs.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    config = Path(__file__).resolve().parents[1] / "config" / "dashboard.yaml"

    data = build_dashboard(logs, config, now=now)
    rendered = render_dashboard(data)
    panels = {panel["id"]: panel for panel in data["panels"]}

    assert len(panels) == 6
    assert data["records_in_window"] == 4
    assert panels["traffic"]["summary"][0] == ("Requests", 2.0)
    assert panels["errors"]["summary"][0] == ("Error rate", 50.0)
    assert panels["errors"]["summary"][1] == ("Retrieval success", 50.0)
    assert panels["cost"]["summary"][0] == ("Window total", 0.001)
    assert "60 minutes" in rendered
    assert "2 requests" in rendered
    assert "Threshold:" in rendered
    assert rendered.count('class="panel"') == 6
    assert "req-11111111" not in rendered
