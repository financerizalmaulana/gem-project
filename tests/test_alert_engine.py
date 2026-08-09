"""
Tests for engines/alert_engine.py's Telegram delivery logic.
Network is mocked — api.telegram.org is unreachable from this sandbox
(see module docstring). What IS verified here: payload format, and
that retry/backoff actually retries the right number of times and
reports failure honestly rather than silently swallowing it.
"""

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.alert_engine import AlertEngine


def test_build_telegram_payload_format():
    alerts = [
        {"type": "REGIME_CHANGE", "severity": "high", "message": "Regime changed: A -> B"},
        {"type": "LOW_CONFIDENCE_REGIME", "severity": "medium", "message": "Confidence is low"},
    ]
    payload = AlertEngine.build_telegram_payload(chat_id="12345", alerts=alerts)
    assert payload["chat_id"] == "12345"
    assert "[HIGH] Regime changed: A -> B" in payload["text"]
    assert "[MEDIUM] Confidence is low" in payload["text"]


def test_send_via_telegram_no_alerts_is_a_noop():
    result = AlertEngine.send_via_telegram("fake-token", "12345", [])
    assert result["sent"] is False
    assert "no alerts" in result["reason"]


@patch("time.sleep", return_value=None)  # skip real backoff delay in test
def test_send_via_telegram_succeeds_on_first_try(mock_sleep):
    alerts = [{"type": "X", "severity": "high", "message": "test"}]
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        result = AlertEngine.send_via_telegram("fake-token", "12345", alerts)
    assert result["sent"] is True
    assert result["attempt"] == 1
    assert mock_post.call_count == 1


@patch("time.sleep", return_value=None)
def test_send_via_telegram_retries_on_failure(mock_sleep):
    alerts = [{"type": "X", "severity": "high", "message": "test"}]
    with patch("requests.post") as mock_post:
        mock_post.side_effect = ConnectionError("simulated network failure")
        result = AlertEngine.send_via_telegram("fake-token", "12345", alerts, max_retries=2)
    assert result["sent"] is False
    assert mock_post.call_count == 3  # initial attempt + 2 retries
    assert "simulated network failure" in result["reason"]


def test_check_data_freshness_fires_when_stale():
    from datetime import datetime, timedelta
    old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
    with patch.object(AlertEngine, "__init__", lambda self: None):
        engine = AlertEngine()
    alerts = engine.check_data_freshness({"date": old_date})
    assert len(alerts) == 1
    assert alerts[0]["type"] == "DATA_STALE"
    assert alerts[0]["severity"] == "high"


def test_check_data_freshness_silent_when_recent():
    from datetime import datetime, timedelta
    recent_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    with patch.object(AlertEngine, "__init__", lambda self: None):
        engine = AlertEngine()
    alerts = engine.check_data_freshness({"date": recent_date})
    assert alerts == []


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
