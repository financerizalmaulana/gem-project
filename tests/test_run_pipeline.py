"""
Tests for run_pipeline.py orchestration logic. Every external step is
mocked (no network) — what's verified is that steps run in the right
order, failures in one step don't crash the others, the overall status
accurately reflects what happened, and the monthly-digest delivery
decision (see run_pipeline.py docstring) fires exactly when it should.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_pipeline

NOT_A_NEW_MONTH = {"is_new_month": False, "date_updated": "2026-06-30", "regime": "Growth Risk-On"}
IS_A_NEW_MONTH = {"is_new_month": True, "date_updated": "2026-07-31", "regime": "Growth Risk-On"}


def test_skips_data_refresh_without_api_key():
    with patch("run_pipeline.update_asset_prices", return_value={"returns_written": {}}), \
         patch("run_pipeline.AlertEngine") as MockAlertEngine, \
         patch("run_pipeline.generate_report", return_value="# fake report"):
        MockAlertEngine.return_value.run_all_checks.return_value = []
        result = run_pipeline.run(fred_api_key=None)
    assert result["steps"]["data_refresh"]["status"] == "skipped"
    assert result["steps"]["notification"]["status"] == "skipped"
    assert result["steps"]["notification"]["reason"] == "nothing to notify"
    assert result["overall_status"] == "ok"


def test_data_refresh_failure_does_not_block_report_or_alerts():
    with patch("run_pipeline.update_master_dataset", side_effect=RuntimeError("simulated FRED outage")), \
         patch("run_pipeline.update_asset_prices", return_value={"returns_written": {}}), \
         patch("run_pipeline.AlertEngine") as MockAlertEngine, \
         patch("run_pipeline.generate_report", return_value="# fake report"):
        MockAlertEngine.return_value.run_all_checks.return_value = []
        result = run_pipeline.run(fred_api_key="fake-key")
    assert result["steps"]["data_refresh"]["status"] == "failed"
    assert "simulated FRED outage" in result["steps"]["data_refresh"]["error"]
    assert result["steps"]["report"]["status"] == "ok", "report should still generate even if data refresh failed"
    assert result["overall_status"] == "partial_failure"


def test_asset_price_refresh_failure_does_not_block_other_steps():
    with patch("run_pipeline.update_master_dataset", return_value=NOT_A_NEW_MONTH), \
         patch("run_pipeline.update_asset_prices", side_effect=RuntimeError("simulated stooq outage")), \
         patch("run_pipeline.AlertEngine") as MockAlertEngine, \
         patch("run_pipeline.generate_report", return_value="# fake report"):
        MockAlertEngine.return_value.run_all_checks.return_value = []
        result = run_pipeline.run(fred_api_key="fake-key")
    assert result["steps"]["asset_price_refresh"]["status"] == "failed"
    assert result["steps"]["report"]["status"] == "ok"
    assert result["overall_status"] == "partial_failure"


def test_alerts_trigger_notification_when_credentials_present():
    fake_alerts = [{"type": "X", "severity": "high", "message": "test alert"}]
    with patch("run_pipeline.update_master_dataset", return_value=NOT_A_NEW_MONTH), \
         patch("run_pipeline.update_asset_prices", return_value={"returns_written": {}}), \
         patch("run_pipeline.AlertEngine") as MockAlertEngine, \
         patch("run_pipeline.generate_report", return_value="# fake report"):
        MockAlertEngine.return_value.run_all_checks.return_value = fake_alerts
        MockAlertEngine.send_via_telegram.return_value = {"sent": True, "attempt": 1}
        result = run_pipeline.run(fred_api_key="fake-key", telegram_bot_token="tok", telegram_chat_id="123")
    assert result["steps"]["alerts"]["count"] == 1
    assert result["steps"]["notification"]["status"] == "ok"
    MockAlertEngine.send_via_telegram.assert_called_once()
    sent_notifications = MockAlertEngine.send_via_telegram.call_args[0][2]
    assert len(sent_notifications) == 1  # just the alert, no digest — not a new month
    assert "monthly_digest" not in result["steps"]


def test_monthly_digest_sent_on_new_month_even_with_zero_alerts():
    """The delivery decision documented in run_pipeline.py: a new month
    landing should notify even with no alerts, so the system doesn't
    stay silent every month a real update happens."""
    with patch("run_pipeline.update_master_dataset", return_value=IS_A_NEW_MONTH), \
         patch("run_pipeline.update_asset_prices", return_value={"returns_written": {}}), \
         patch("run_pipeline.AlertEngine") as MockAlertEngine, \
         patch("run_pipeline.generate_report", return_value="# fake report"):
        MockAlertEngine.return_value.run_all_checks.return_value = []  # zero alerts
        MockAlertEngine.send_via_telegram.return_value = {"sent": True, "attempt": 1}
        result = run_pipeline.run(fred_api_key="fake-key", telegram_bot_token="tok", telegram_chat_id="123")
    assert result["steps"]["monthly_digest"]["status"] == "ok"
    assert result["steps"]["notification"]["status"] == "ok"
    sent_notifications = MockAlertEngine.send_via_telegram.call_args[0][2]
    assert any(n["type"] == "MONTHLY_DIGEST" for n in sent_notifications)


def test_no_digest_and_no_notification_when_same_month_and_no_alerts():
    with patch("run_pipeline.update_master_dataset", return_value=NOT_A_NEW_MONTH), \
         patch("run_pipeline.update_asset_prices", return_value={"returns_written": {}}), \
         patch("run_pipeline.AlertEngine") as MockAlertEngine, \
         patch("run_pipeline.generate_report", return_value="# fake report"):
        MockAlertEngine.return_value.run_all_checks.return_value = []
        result = run_pipeline.run(fred_api_key="fake-key", telegram_bot_token="tok", telegram_chat_id="123")
    assert "monthly_digest" not in result["steps"]
    assert result["steps"]["notification"]["status"] == "skipped"
    assert result["steps"]["notification"]["reason"] == "nothing to notify"


def test_report_failure_is_isolated_and_recorded():
    with patch("run_pipeline.update_master_dataset", return_value=NOT_A_NEW_MONTH), \
         patch("run_pipeline.update_asset_prices", return_value={"returns_written": {}}), \
         patch("run_pipeline.AlertEngine") as MockAlertEngine, \
         patch("run_pipeline.generate_report", side_effect=RuntimeError("simulated report bug")):
        MockAlertEngine.return_value.run_all_checks.return_value = []
        result = run_pipeline.run(fred_api_key="fake-key")
    assert result["steps"]["report"]["status"] == "failed"
    assert result["overall_status"] == "partial_failure"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
