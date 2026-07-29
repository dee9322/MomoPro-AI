import pandas as pd

from position_sizing import calculate_position_size
from symbol_context import attach_cached_metadata


def test_position_sizing_long_and_short():
    long_result = calculate_position_size(10000, 1, 10, 9, direction="Long")
    short_result = calculate_position_size(10000, 1, 10, 11, direction="Short")
    assert long_result["risk_per_share"] == 1
    assert short_result["risk_per_share"] == 1
    assert long_result["final_shares"] == short_result["final_shares"] == 100


def test_invalid_short_stop():
    result = calculate_position_size(10000, 1, 10, 9, direction="Short")
    assert result["final_shares"] == 0
    assert "short trade" in result["error"].lower()


def test_metadata_attachment_keeps_scan_rows():
    frame = pd.DataFrame([{"Symbol": "AAPL", "Score": 80}])
    result = attach_cached_metadata(frame)
    assert len(result) == 1
    assert "Sector" in result.columns
