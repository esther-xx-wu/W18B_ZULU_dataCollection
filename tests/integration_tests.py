import unittest
import json
import boto3
import os
import pandas as pd
from io import StringIO
from unittest.mock import patch, MagicMock
from moto import mock_aws
import requests_mock
from src.app import app


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
        
        self.sample_csv_data = "date,total_daily_traffic\n01-Apr-2025,15000\n31-Mar-2025,14500"
        self.raw_csv_data = "date,total_daily_traffic\n2025-04-01T00:00:00,15000\n2025-03-31T00:00:00,14500"
        
        # Reload the module to pick up new environment variables
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
        
        # Create the mock S3 bucket
        bucket_name = "test-bucket"
        s3.create_bucket(
            Bucket=bucket_name, 
            CreateBucketConfiguration={"LocationConstraint": "us-east-2"}
        )
        # Patch the s3_client in collection module
        with patch('src.collection.s3_client', s3):
            with requests_mock.Mocker() as m:
                m.get('https://api.transport.nsw.gov.au/v1/traffic_volume', 
                      text=self.raw_csv_data)
              
                response = self.app.get('/traffic/single/v1?suburb=Hornsby&numDays=2')
                
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Content-Type'], 'text/csv')
                
                response_csv = pd.read_csv(StringIO(response.data.decode('utf-8')))
                self.assertEqual(len(response_csv), 2)
                self.assertIn('date', response_csv.columns)
                self.assertIn('total_daily_traffic', response_csv.columns)
                
                # Check S3 bucket for uploaded file
                bucket = s3.Bucket('test-bucket')
                files = list(bucket.objects.all())
                self.assertEqual(len(files), 1)
                self.assertTrue(files[0].key.startswith('Hornsby_traffic_data_'))
                self.assertTrue(files[0].key.endswith('.csv'))

    def test_missing_suburb_parameter(self):
        """Test API validates missing suburb parameter"""
        response = self.app.get('/traffic/single/v1?numDays=2')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Suburb is required')

    def test_missing_numDays_parameter(self):
        """Test API validates missing numDays parameter"""
        response = self.app.get('/traffic/single/v1?suburb=Sydney')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Number of days is required')

    def test_invalid_numDays_parameter(self):
        """Test API validates invalid numDays parameter"""
        response = self.app.get('/traffic/single/v1?suburb=Sydney&numDays=abc')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Number of days must be a valid integer!')

    @patch('src.collection.requests.get')
    def test_transport_api_error(self, mock_get):
        """Test handling of Transport API errors"""
        mock_get.return_value.status_code = 403
        mock_get.return_value.text = "API key invalid"
        
        response = self.app.get('/traffic/single/v1?suburb=Hornsby&numDays=2')
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
        
        # Mock S3 error
        mock_bucket = MagicMock()
        mock_bucket.put_object.side_effect = boto3.exceptions.Boto3Error("S3 error")
        mock_s3_bucket.return_value = mock_bucket
        
        response = self.app.get('/traffic/single/v1?suburb=Hornsby&numDays=2')
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('S3 error', data['error'])

if __name__ == '__main__':
    unittest.main()