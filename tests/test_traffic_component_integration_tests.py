import os
import sys
import json
import boto3
import pytest
import requests_mock
from unittest.mock import patch
from moto import mock_aws
import importlib

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

try:
    from app import app
    import src.collection
except ImportError:
    pytest.skip(reason="could not import fetch_traffic_data", allow_module_level=True)

@pytest.fixture
def client():
    """Pytest fixture to provide test client."""
    return app.test_client()

@pytest.fixture(autouse=True)
def set_env_vars():
    """Fixture to set environment variables and reload app for testing."""
    os.environ["TRANSPORT_API_KEY"] = "fake-api-key"
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
    os.environ["ACCESS_KEY"] = "fake-access-key"
    os.environ["SECRET_KEY"] = "fake-secret-key"
    os.environ["REGION"] = "us-east-2"

    importlib.reload(src.collection)

@pytest.fixture
def sample_data():
    return [
        {"date": "01-Apr-2025", "total_daily_traffic": 15000},
        {"date": "31-Mar-2025", "total_daily_traffic": 14500}
    ]

@pytest.fixture
def raw_csv_data():
    return "date,total_daily_traffic\n2025-04-01T00:00:00,15000\n2025-03-31T00:00:00,14500"

@mock_aws
def test_successful_api_call(client, raw_csv_data):
    """Test successful API call."""
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.transport.nsw.gov.au/v1/traffic_volume",
            text=raw_csv_data
        )

        response = client.get('/traffic/single/v1?suburb=Hornsby&numDays=2')

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/json"

        response_json = json.loads(response.data.decode("utf-8"))
        assert isinstance(response_json, list)
        assert len(response_json) == 2
        assert "date" in response_json[0]
        assert "total_daily_traffic" in response_json[0]

@mock_aws
@patch("src.collection.requests.get")
def test_transport_api_error(mock_get, client):
    s3 = boto3.resource(
        "s3",
        aws_access_key_id="fake-access-key",
        aws_secret_access_key="fake-secret-key",
        region_name="us-east-2"
    )

    bucket_name = "test-bucket"
    s3.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "us-east-2"}
    )
    
    s3_client = boto3.client(
        "s3",
        aws_access_key_id="fake-access-key",
        aws_secret_access_key="fake-secret-key",
        region_name="us-east-2"
    )
    
    with patch("src.collection.s3_client", s3_client):
        """Test handling of Transport API errors."""
        mock_get.return_value.status_code = 403
        mock_get.return_value.text = {
            "ErrorDetails": {
                "Message": "The calling application is unauthenticated.",
                "RequestMethod": "GET"
            }
        }
        response = client.get('/traffic/single/v1?suburb=Chatswood&numDays=2')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert "Failed to fetch data" in data["error"]
