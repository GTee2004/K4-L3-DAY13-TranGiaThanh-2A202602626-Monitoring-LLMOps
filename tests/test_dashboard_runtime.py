from __future__ import annotations

from datetime import datetime, timezone

from dashboard.app import dashboard_metrics, render


def test_retrieval_success_uses_all_events_with_tool_success() -> None:
    now = datetime(2026, 9, 30, 4, 0, tzinfo=timezone.utc)
    timestamp = now.isoformat().replace("+00:00", "Z")
    records = [
        {"ts": timestamp, "event": "request_received"},
        {"ts": timestamp, "event": "request_received"},
        {"ts": timestamp, "event": "response_sent", "tool_success": True},
        {"ts": timestamp, "event": "request_failed", "tool_success": False},
    ]

    metrics = dashboard_metrics(records, now=now)

    assert metrics["tool_events"] == 2
    assert metrics["retrieval_success"] == 50.0
    assert metrics["error_rate"] == 50.0


def test_dashboard_renders_exactly_six_panels() -> None:
    page = render([])

    assert page.count('<section class="panel">') == 6
    assert page.count('class="threshold"') == 6
    assert 'http-equiv="refresh" content="30"' in page
