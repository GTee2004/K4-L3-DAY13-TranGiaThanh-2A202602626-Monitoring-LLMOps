from __future__ import annotations

import argparse
import html
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(
        timezone.utc
    )


def percentile(values: Iterable[float], percent: int) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    return ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)]


def load_records(path: Path = LOG_PATH) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def minute(record: dict) -> str | None:
    timestamp = parse_timestamp(record.get("ts"))
    return timestamp.strftime("%H:%M") if timestamp else None


def numeric(record: dict, field: str) -> float | None:
    value = record.get(field)
    return float(value) if isinstance(value, (int, float)) else None


def sum_by_minute(records: list[dict], field: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for record in records:
        key, value = minute(record), numeric(record, field)
        if key is not None and value is not None:
            totals[key] += value
    return dict(sorted(totals.items()))


def mean_by_minute(records: list[dict], field: str) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for record in records:
        key, value = minute(record), numeric(record, field)
        if key is not None and value is not None:
            values[key].append(value)
    return {key: sum(items) / len(items) for key, items in sorted(values.items())}


def dashboard_metrics(records: list[dict], now: datetime | None = None) -> dict:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = current - timedelta(minutes=60)
    window = [
        record
        for record in records
        if (timestamp := parse_timestamp(record.get("ts"))) is not None
        and start <= timestamp <= current
    ]
    requests = [record for record in window if record.get("event") == "request_received"]
    responses = [record for record in window if record.get("event") == "response_sent"]
    failures = [record for record in window if record.get("event") == "request_failed"]
    tool_events = [record for record in window if "tool_success" in record]
    latencies = [value for record in responses if (value := numeric(record, "latency_ms")) is not None]
    ttfts = [value for record in responses if (value := numeric(record, "ttft_ms")) is not None]
    traffic: dict[str, float] = defaultdict(float)
    for record in requests:
        if key := minute(record):
            traffic[key] += 1
    tokens_in = sum(value for record in responses if (value := numeric(record, "tokens_in")) is not None)
    tokens_out = sum(value for record in responses if (value := numeric(record, "tokens_out")) is not None)
    quality = [value for record in responses if (value := numeric(record, "quality_score")) is not None]
    return {
        "start": start,
        "end": current,
        "records": len(window),
        "latency": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "p99": percentile(latencies, 99), "ttft_p95": percentile(ttfts, 95)},
        "traffic": dict(sorted(traffic.items())),
        "error_rate": len(failures) / len(requests) * 100 if requests else 0.0,
        "retrieval_success": sum(record.get("tool_success") is True for record in tool_events) / len(tool_events) * 100 if tool_events else 0.0,
        "tool_events": len(tool_events),
        "cost_total": sum(value for record in responses if (value := numeric(record, "cost_usd")) is not None),
        "cost_series": sum_by_minute(responses, "cost_usd"),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "quality_mean": sum(quality) / len(quality) if quality else 0.0,
        "quality_series": mean_by_minute(responses, "quality_score"),
    }


def thresholds() -> dict[str, float]:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return {panel["id"]: float(panel["threshold"]["value"]) for panel in payload["dashboard"]["panels"]}


def chart(series: dict[str, float], threshold: float, label: str, color: str) -> str:
    labels, values = list(series) or ["no data"], list(series.values()) or [0.0]
    width, height, left, bottom = 580, 190, 42, 32
    top, right = 16, 14
    maximum = max(max(values), threshold, 1.0) * 1.12
    plot_width, plot_height = width - left - right, height - top - bottom
    x = lambda index: left + plot_width * index / max(1, len(values) - 1)
    y = lambda value: top + plot_height - plot_height * value / maximum
    points = " ".join(f"{x(i):.1f},{y(value):.1f}" for i, value in enumerate(values))
    step = max(1, math.ceil(len(labels) / 5))
    ticks = "".join(
        f'<text x="{x(i):.1f}" y="{height - 10}" text-anchor="middle">{html.escape(item)}</text>'
        for i, item in enumerate(labels) if i % step == 0 or i == len(labels) - 1
    )
    return f'''<svg viewBox="0 0 {width} {height}" aria-label="chart">
      <line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"/>
      <line class="axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"/>
      <line class="threshold" x1="{left}" y1="{y(threshold):.1f}" x2="{width-right}" y2="{y(threshold):.1f}"/>
      <text class="threshold-label" x="{width-right}" y="{max(12, y(threshold)-5):.1f}" text-anchor="end">{html.escape(label)}</text>
      <polyline class="line" style="stroke:{color}" points="{points}"/>
      <text x="4" y="{top+5}">{maximum:.2f}</text>{ticks}
    </svg>'''


def panel(title: str, unit: str, summary: str, graph: str) -> str:
    return f'<section class="panel"><header><h2>{title}</h2><span>{unit}</span></header><div class="summary">{summary}</div>{graph}</section>'


def render(records: list[dict] | None = None) -> str:
    metrics = dashboard_metrics(records if records is not None else load_records())
    config = thresholds()
    latency = metrics["latency"]
    panels = [
        panel("Latency", "ms", f'P50 <b>{latency["p50"]:.0f}</b> · P95 <b>{latency["p95"]:.0f}</b> · P99 <b>{latency["p99"]:.0f}</b> · TTFT P95 <b>{latency["ttft_p95"]:.0f}</b>', chart({"P50": latency["p50"], "P95": latency["p95"], "P99": latency["p99"], "TTFT P95": latency["ttft_p95"]}, config["latency"], f'SLO ≤ {config["latency"]:.0f} ms', "#69db7c")),
        panel("Traffic", "requests/minute", f'Requests <b>{sum(metrics["traffic"].values()):.0f}</b>', chart(metrics["traffic"], config["traffic"], f'baseline ≥ {config["traffic"]:.0f}/min', "#74c0fc")),
        panel("Errors", "percent", f'Error rate <b>{metrics["error_rate"]:.2f}%</b> · Retrieval success <b>{metrics["retrieval_success"]:.2f}%</b> ({metrics["tool_events"]} tool events)', chart({"Error rate": metrics["error_rate"], "Retrieval success": metrics["retrieval_success"]}, config["errors"], f'error rate ≤ {config["errors"]:.0f}%', "#ff8787")),
        panel("Cost", "USD", f'Total <b>${metrics["cost_total"]:.6f}</b>', chart(metrics["cost_series"], config["cost"], f'budget ≤ ${config["cost"]:.2f}', "#ffd43b")),
        panel("Tokens", "tokens", f'Input <b>{metrics["tokens_in"]:.0f}</b> · Output <b>{metrics["tokens_out"]:.0f}</b>', chart({"Input": metrics["tokens_in"], "Output": metrics["tokens_out"]}, config["tokens"], f'guardrail ≤ {config["tokens"]:.0f}', "#b197fc")),
        panel("Quality", "score 0–1", f'Mean <b>{metrics["quality_mean"]:.3f}</b>', chart(metrics["quality_series"], config["quality"], f'target ≥ {config["quality"]:.2f}', "#63e6be")),
    ]
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="30"><title>LLMOps Dashboard</title><style>
    body{{background:#0b1020;color:#edf2ff;font:14px system-ui;margin:0;padding:26px}}main{{max-width:1320px;margin:auto}}h1{{margin:0}}.meta{{color:#aab5d6;margin:8px 0 22px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.panel{{background:#151c31;border:1px solid #2b3658;border-radius:12px;padding:16px}}header{{display:flex;justify-content:space-between}}h2{{font-size:18px;margin:0}}header span{{color:#91a7ff}}.summary{{margin:10px 0;color:#dbe4ff}}.summary b{{color:#fff;font-size:17px}}svg{{background:#10172a;border-radius:8px;width:100%}}svg text{{fill:#98a5c9;font-size:10px}}.axis{{stroke:#465473}}.threshold{{stroke:#ff6b6b;stroke-width:1.5;stroke-dasharray:6 4}}.threshold-label{{fill:#ff8787}}.line{{fill:none;stroke-width:3;stroke-linejoin:round;stroke-linecap:round}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}body{{padding:12px}}}}</style></head><body><main><h1>K4-L3B Monitoring & LLMOps</h1><div class="meta">UTC window: last 60 minutes · {metrics["records"]} log records · auto refresh: 30 seconds · source: data/logs.jsonl</div><div class="grid">{"".join(panels)}</div></main></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body, content_type = b'{"ok": true}', "application/json"
        else:
            body, content_type = render().encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    options = parser.parse_args()
    server = ThreadingHTTPServer((options.host, options.port), Handler)
    print(f"Dashboard: http://{options.host}:{options.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
