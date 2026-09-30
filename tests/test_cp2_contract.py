from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_slo_error_budget_is_explicit_and_calculated() -> None:
    config = yaml.safe_load(
        (REPO_ROOT / "config" / "slo.yaml").read_text(encoding="utf-8")
    )
    slo = config["primary_slo"]

    assert slo["target_percent"] == 99.5
    assert slo["error_budget_percent"] == 100 - slo["target_percent"]
    assert (
        slo["error_budget_requests"]
        == slo["error_budget_basis_requests"] * slo["error_budget_percent"] / 100
    )


def test_alerts_have_conditions_owners_durations_channels_and_runbooks() -> None:
    config = yaml.safe_load(
        (REPO_ROOT / "config" / "alert_rules.yaml").read_text(encoding="utf-8")
    )
    alerts = config["alerts"]

    assert len(alerts) == 3
    for number, alert in enumerate(alerts, start=1):
        assert alert["type"] == "symptom-based"
        assert alert["condition"]
        assert alert["duration"]
        assert alert["severity"] in {"warning", "critical"}
        assert alert["owner"]
        assert alert["channel"].startswith("#")
        assert alert["runbook"] == f"docs/alerts.md#alert-{number}"


def test_retrieval_success_includes_success_and_failure_events() -> None:
    config = yaml.safe_load(
        (REPO_ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8")
    )
    error_panel = next(
        panel for panel in config["dashboard"]["panels"] if panel["id"] == "errors"
    )

    assert "response_sent" in error_panel["events"]
    assert "request_failed" in error_panel["events"]
