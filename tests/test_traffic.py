import unittest
from unittest.mock import patch, Mock
import os

# Adjust the import to reflect the module's location
from src.collection import fetch_traffic_data

class TestTrafficModule(unittest.TestCase):

    @patch('src.collection.requests.get')  # Mocking the requests.get method
    def test_fetch_traffic_data_success(self, mock_get):
        # Mock the response from the requests.get call
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "date,total_daily_traffic\n2023-10-01,1000\n2023-10-02,1500"
        mock_get.return_value = mock_response
        
        # Call the function with a test suburb
        suburb = "TestSuburb"
        result = fetch_traffic_data(suburb)
        
        # Check that the result is as expected
        expected_result = "date,total_daily_traffic\n2023-10-01,1000\n2023-10-02,1500"
        self.assertEqual(result, expected_result)
        
        # Check that the requests.get was called with the correct parameters
        mock_get.assert_called_once()
        self.assertIn(suburb, mock_get.call_args[1]['params']['q'])

    @patch('src.collection.requests.get')  # Mocking the requests.get method
    def test_fetch_traffic_data_failure(self, mock_get):
        # Mock a failed response from the requests.get call
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response
        
        # Call the function with a test suburb and assert that it raises an exception
        suburb = "TestSuburb"
        with self.assertRaises(Exception) as context:
            fetch_traffic_data(suburb)
        
        self.assertEqual(str(context.exception), "Failed to fetch data: 404 - Not Found")

if __name__ == '__main__':
    unittest.main()