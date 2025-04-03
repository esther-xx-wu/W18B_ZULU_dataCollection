# from flask import Flask, request, jsonify
import requests
import boto3
import os
from dotenv import load_dotenv
import random
from botocore.exceptions import NoCredentialsError, ClientError
import pandas as pd
from io import StringIO

load_dotenv()

# Environment Variables
TRANSPORT_API_KEY = os.getenv("TRANSPORT_API_KEY")
TRAFFIC_API_ENDPOINT = "https://api.transport.nsw.gov.au/v1/traffic_volume"
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-2")

s3_client = boto3.resource(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=aws_region
)

# Helper Function to Call Transport NSW API and Get CSV Data
def fetch_traffic_data(suburb, numDays):
    query = f"""
    SELECT rt.date, SUM(rt.daily_total) AS total_daily_traffic
    FROM road_traffic_counts_hourly_permanent rt
    JOIN road_traffic_counts_station_reference rc 
        ON rt.station_key = rc.station_key
    WHERE rc.suburb = '{suburb}'
    GROUP BY rt.date
    ORDER BY rt.date DESC
    LIMIT {numDays};
    """

    headers = {
        "Authorization": f"apikey {TRANSPORT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        TRAFFIC_API_ENDPOINT,
        params={"format": "csv", "q": query},
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.status_code} - {response.text}")
    

    csv_data = pd.read_csv(StringIO(response.text))
    
    # Format date column to remove redundant time element
    csv_data['date'] = pd.to_datetime(csv_data['date']).dt.strftime('%d-%b-%Y')
    
    return csv_data.to_csv(index=False)

# Helper Function to Upload CSV Data to S3 bucket
def upload_to_s3(csv_data, suburb):
    file_name = f"{suburb}_traffic_data_{random.randint(10, 100)}.csv"
    try:
        # s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=file_name, Body=csv_data)
        s3_client.Bucket(S3_BUCKET_NAME).put_object(Key=file_name, Body=csv_data)
        return f"s3://{S3_BUCKET_NAME}/{file_name}"
    except (NoCredentialsError, ClientError) as e:
        raise Exception(f"S3 Upload Failed: {str(e)}")