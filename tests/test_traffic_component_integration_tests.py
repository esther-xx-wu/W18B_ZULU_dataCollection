import unittest
import json
import boto3
import os
import sys
from unittest.mock import patch, MagicMock
from moto import mock_aws
import requests_mock

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

try:
    from src.app import app
except ImportError:
    unittest.skip(reason="could not import fetch_traffic_data", allow_module_level=True)

class TestLambdaFunction(unittest.TestCase):
    @mock_aws
    def setUp(self):
        self.app = app.test_client()

        # Mock environment variables for testing
        os.environ["TRANSPORT_API_KEY"] = "fake-api-key"
        os.environ["S3_BUCKET_NAME"] = "test-bucket"
        os.environ["AWS_ACCESS_KEY_ID"] = "fake-access-key"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "fake-secret-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-2"
        
        self.sample_data = [
            {"date": "01-Apr-2025", "total_daily_traffic": 15000},
            {"date": "31-Mar-2025", "total_daily_traffic": 14500}
        ]
        self.raw_csv_data = "date,total_daily_traffic\n2025-04-01T00:00:00,15000\n2025-03-31T00:00:00,14500"

        import importlib
        import src.collection
        importlib.reload(src.collection)


    @mock_aws
    @patch.dict(os.environ, {
      "TRANSPORT_API_KEY": "fake-api-key",
      "S3_BUCKET_NAME": "test-bucket",
      "AWS_ACCESS_KEY_ID": "fake-access-key",
      "AWS_SECRET_ACCESS_KEY": "fake-secret-key",
      "AWS_DEFAULT_REGION": "us-east-2"
    })
    def test_successful_api_call(self):
        """Test successful API call and S3 upload"""
        s3 = boto3.resource(
            "s3",
            aws_access_key_id="fake-access-key",
            aws_secret_access_key="fake-secret-key",
            region_name="us-east-2"
        )
        
        # Mock S3 bucket
        bucket_name = "test-bucket"
        s3.create_bucket(
            Bucket=bucket_name, 
            CreateBucketConfiguration={"LocationConstraint": "us-east-2"}
        )

        with patch('src.collection.s3_client', s3):
            with requests_mock.Mocker() as m:
                m.get('https://api.transport.nsw.gov.au/v1/traffic_volume', 
                      text=self.raw_csv_data)
              
                response = self.app.get('/traffic/single/v1?suburb=Hornsby&numDays=2')
                
                print(response.data)
                
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Content-Type'], 'application/json')
                
                response_json = json.loads(response.data.decode('utf-8'))
                self.assertIsInstance(response_json, list)
                self.assertEqual(len(response_json), 2)
                self.assertIn('date', response_json[0])
                self.assertIn('total_daily_traffic', response_json[0])

                bucket = s3.Bucket('test-bucket')
                files = list(bucket.objects.all())
                self.assertEqual(len(files), 1)
                self.assertTrue(files[0].key.startswith('Hornsby_traffic_data_'))
                self.assertTrue(files[0].key.endswith('.csv'))

    @patch('src.collection.requests.get')
    def test_transport_api_error(self, mock_get):
        """Test handling of Transport API errors"""
        mock_get.return_value.status_code = 403
        mock_get.return_value.text = "API key invalid"
        
        response = self.app.get('/traffic/single/v1?suburb=Chatswood&numDays=2')
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('Failed to fetch data', data['error'])

    @mock_aws
    @patch('src.collection.requests.get')
    @patch('src.collection.s3_client.Bucket')
    def test_s3_upload_error(self, mock_s3_bucket, mock_get):
        """Test handling of S3 upload errors"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = self.raw_csv_data
        

        mock_bucket = MagicMock()
        mock_bucket.put_object.side_effect = boto3.exceptions.Boto3Error("S3 error")
        mock_s3_bucket.return_value = mock_bucket
        
        response = self.app.get('/traffic/single/v1?suburb=Hornsby&numDays=2')
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('S3 error', data['error'])

if __name__ == '__main__':
    unittest.main()