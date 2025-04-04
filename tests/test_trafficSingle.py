import unittest
import json
import pandas as pd
from unittest.mock import patch, MagicMock
from src.collection import fetch_traffic_data

class TestFetchTrafficData(unittest.TestCase):

    @patch("src.collection.requests.get")
    @patch("src.collection.upload_to_s3")
    def test_fetch_traffic_data_success(self, mock_upload, mock_requests):
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
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIn("date", result[0])
        self.assertIn("total_daily_traffic", result[0])

        self.assertEqual(result[0]["date"], "01-Apr-2025")
        self.assertEqual(result[0]["total_daily_traffic"], 15000)

        mock_upload.assert_called_once()

    def test_fetch_traffic_data_missing_suburb(self):
        """Test missing suburb"""
        result_json = fetch_traffic_data("", "5")
        result = json.loads(result_json)
        self.assertEqual(result["error"], "Suburb is required")
        self.assertEqual(result["code"], 400)

    def test_fetch_traffic_data_missing_numDays(self):
        """Test missing numDays"""
        result_json = fetch_traffic_data("Liverpool", "")
        result = json.loads(result_json)
        self.assertEqual(result["error"], "Number of days is required")
        self.assertEqual(result["code"], 400)

    def test_fetch_traffic_data_invalid_numDays(self):
        """Test non-numeric numDays"""
        result_json = fetch_traffic_data("Liverpool", "abc")
        result = json.loads(result_json)
        self.assertEqual(result["error"], "Number of days must be a valid integer!")
        self.assertEqual(result["code"], 400)
        
    def test_fetch_traffic_data_invalid_params_multiple(self):
        """Test multiple invalid params"""
        result_json = fetch_traffic_data("", "abc")
        result = json.loads(result_json)
        self.assertEqual(result["error"], "Suburb is required")
        self.assertEqual(result["code"], 400)

if __name__ == "__main__":
    unittest.main()
