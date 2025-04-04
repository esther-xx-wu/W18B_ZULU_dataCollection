import os
import sys
import pytest
import json
from unittest.mock import patch, MagicMock

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
sys.path.append(parent_dir)

try:
    from collection import fetch_traffic_data
except ImportError:
    pytest.skip(reason="could not import fetch_traffic_data", allow_module_level=True)

@pytest.fixture
def mock_requests():
    """Fixture to mock requests.get"""
    with patch("collection.requests.get") as mock:
        yield mock

@pytest.fixture
def mock_upload():
    """Fixture to mock upload_to_s3"""
    with patch("collection.upload_to_s3") as mock:
        yield mock

def test_fetch_traffic_data_success(mock_requests, mock_upload):
    """Test successful data retrieval"""
    suburb = "Liverpool"
    numDays = "2"

    # Mock API response
    mock_csv = "date,total_daily_traffic\n2025-04-01,15000\n2025-03-31,14500"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = mock_csv
    mock_requests.return_value = mock_response

    result_json = fetch_traffic_data(suburb, numDays)
    result = json.loads(result_json)

    assert isinstance(result, list)
    assert len(result) == 2
    assert "date" in result[0]
    assert "total_daily_traffic" in result[0]

    assert result[0]["date"] == "01-Apr-2025"
    assert result[0]["total_daily_traffic"] == 15000

    mock_upload.assert_called_once()

def test_fetch_traffic_data_missing_suburb():
    """Test missing suburb"""
    result_json = fetch_traffic_data("", "5")
    result = json.loads(result_json)
    assert result["error"] == "Suburb is required"
    assert result["code"] == 400

def test_fetch_traffic_data_missing_numDays():
    """Test missing numDays"""
    result_json = fetch_traffic_data("Liverpool", "")
    result = json.loads(result_json)
    assert result["error"] == "Number of days is required"
    assert result["code"] == 400

def test_fetch_traffic_data_invalid_numDays():
    """Test non-numeric numDays"""
    result_json = fetch_traffic_data("Liverpool", "abc")
    result = json.loads(result_json)
    assert result["error"] == "Number of days must be a valid integer!"
    assert result["code"] == 400

def test_fetch_traffic_data_invalid_params_multiple():
    """Test multiple invalid params"""
    result_json = fetch_traffic_data("", "abc")
    result = json.loads(result_json)
    assert result["error"] == "Suburb is required"
    assert result["code"] == 400