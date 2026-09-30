# SLO Alert Runbooks

All alerts are symptom-based and follow the investigation path **Metrics -> Logs -> Traces**. The on-call owner is `student-2A202602626`, and notifications go to Slack `#k4-l3b-alerts`.

## Alert 1

### HighLatencyOrTTFT

1. **Trigger:** Fires at `warning` when response latency P95 exceeds 3000 ms or TTFT P95 exceeds 1000 ms continuously for 5 minutes. Users may wait too long for the first token or complete response.
2. **Metrics:** Open the **Latency percentiles and TTFT** dashboard panel with the 60-minute range. Confirm when P95/P99 or TTFT P95 crossed its threshold, and compare the interval with the Traffic panel to detect load correlation.
3. **Logs:** Filter `data/logs.jsonl` to `event == "response_sent"` in the affected UTC interval. Sort or inspect `latency_ms` and `ttft_ms`, then copy one slow request's `correlation_id`. Also check its matching `request_received` event.
4. **Traces:** In Langfuse, search trace metadata for that `correlation_id`. Compare the durations of the `retrieval` and `generation` spans, and check generation model, prompt version, token usage, and status without exposing raw input/output.
5. **Mitigation:** Reduce incoming concurrency or rate-limit nonessential traffic. If the regression aligns with a recent prompt/model/config rollout, restore the last known-good version; keep serving requests when latency remains tolerable.
6. **Prevention/follow-up:** Record the slow correlation IDs and interval, determine which span consumed the time, add a regression/load test for that path, and adjust capacity or prompt/token limits before the next rollout. Revisit thresholds only with a new measured baseline.

## Alert 2

### ErrorsOrRetrievalDegradation

1. **Trigger:** Fires at `critical` when request error rate exceeds 2% or retrieval success falls below 90% continuously for 5 minutes. This represents failed requests or answers produced without dependable context.
2. **Metrics:** Open the **Error rate and retrieval success** panel over the last 60 minutes. Check both series and the Traffic panel so a low-volume sample is not mistaken for a broad incident.
3. **Logs:** Filter `data/logs.jsonl` for `event == "request_failed"` and for every event containing `tool_success`. Retrieval success must use all events with that field, including `response_sent` and `request_failed`. Select a failed or `tool_success == false` record and copy its `correlation_id`; inspect `error_type` and `tool_name`.
4. **Traces:** Search Langfuse by the selected `correlation_id`. Inspect the `retrieval` span first for status, duration, and `docs_found`, then verify whether `generation` ran and whether its status or safe metadata is abnormal.
5. **Mitigation:** Temporarily reduce traffic to the affected feature, retry only transient failures with a bounded policy, and use the last known-good retrieval configuration. If safe for the product, return a controlled fallback response instead of an ungrounded answer.
6. **Prevention/follow-up:** Classify failures by `error_type`, preserve representative correlation IDs, add tests for the failing retrieval case, and improve timeout/retry/fallback controls. Verify recovery above 90% retrieval success and below 2% errors before closing the incident.

## Alert 3

### CostOrQualityDegradation

1. **Trigger:** Fires at `warning` when daily cost exceeds USD 2.50 or average response quality score stays below 0.75 for 10 minutes. Users may receive lower-quality answers while spend grows beyond the daily guardrail.
2. **Metrics:** Open the **Cost over time**, **Input and output tokens**, and **Quality proxy** panels with the 60-minute range. Compare the change point across cost, token volume, quality, traffic, model, and prompt version.
3. **Logs:** Filter `data/logs.jsonl` to `event == "response_sent"` in the degraded UTC interval. Inspect `cost_usd`, `tokens_in`, `tokens_out`, `quality_score`, `model`, and prompt metadata; copy a high-cost or low-quality record's `correlation_id`.
4. **Traces:** Find the trace in Langfuse using that `correlation_id`. Inspect `generation` usage/cost and prompt name, label, and version, then compare `retrieval.docs_found` to determine whether weak context coincides with the quality drop.
5. **Mitigation:** Cap input/output tokens and rate-limit expensive traffic. If degradation began after a prompt or model change, roll the production label/configuration back to the last known-good version; avoid disabling PII protections or trace safety controls.
6. **Prevention/follow-up:** Compare cost and quality by prompt version/model, add budget and token regression checks to rollout gates, expand the quality evaluation set, and document the rollback result. Tune the threshold only after collecting a representative baseline.
