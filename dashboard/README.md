# Local dashboard

This dashboard reads `data/logs.jsonl` directly, filters a 60-minute UTC window,
refreshes every 30 seconds, and renders the six panels in `config/dashboard.yaml`.

```powershell
python dashboard/app.py
```

Open `http://127.0.0.1:8501`.
