# GEM — AI Macro Investment Analyst

See `docs/ARCHITECTURE.md` for the full design, `docs/AUDIT_REPORT.md`
for the bug audit and reasoning behind every architectural decision,
and `docs/CHANGELOG.md` for what changed in this rebuild.

## Quick start

```bash
pip install -r requirements.txt
python -m pytest tests/ -v              # confirm everything is wired correctly
python reports/report_generator.py      # print today's analyst report
streamlit run dashboard/app.py          # interactive dashboard
python engines/alert_engine.py          # check for warnings (run on a schedule)
```

If running in Google Colab, place this whole folder at
`/content/drive/MyDrive/GEM_PROJECT` — `config/settings.py`
auto-detects Colab and sets the base path accordingly.

## Status at a glance

Current regime as of the last data point (2026-06-30): **Growth Risk-On**
(confidence 64.8/100 — moderately close to a boundary, see the
dashboard's regime probability panel for the full distribution).

7 original project goals — 5 of 7 have real, working implementations;
2 are explicit scaffolds (Indonesia macro layer, live Telegram
delivery). Full breakdown in `docs/AUDIT_REPORT.md`.
