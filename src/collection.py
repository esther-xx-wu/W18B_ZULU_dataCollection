import requests
import boto3
import os
from dotenv import load_dotenv
import random
from botocore.exceptions import NoCredentialsError, ClientError
from io import StringIO
import json
import csv
from dateutil import parser


load_dotenv()

# Environment Variables
TRANSPORT_API_KEY = os.getenv("TRANSPORT_API_KEY")
TRAFFIC_API_ENDPOINT = "https://api.transport.nsw.gov.au/v1/traffic_volume"
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
aws_access_key = os.getenv("ACCESS_KEY")
aws_secret_key = os.getenv("SECRET_KEY")
aws_region = os.getenv("REGION", "us-east-2")

s3_client = boto3.resource(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=aws_region
)

# Helper Function to Call Transport NSW API and Get CSV Data
def fetch_traffic_data(suburb, numDays):
    if not suburb:
        return json.dumps({"error": "Suburb is required", "code": 400})
    elif not numDays:
        return json.dumps({"error": "Number of days is required", "code": 400})
    elif not numDays.isdigit():
        return json.dumps({"error": "Number of days must be a valid integer!", "code": 400})
    
    numDays = int(numDays)
    
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
    
    csv_file = StringIO(response.text)
    reader = csv.DictReader(csv_file)
    rows = []

    for row in reader:
        # Format the date field
        if 'date' in row and row['date']:
            try:
                parsed_date = parser.parse(row['date'])
                row['date'] = parsed_date.strftime('%d %b %Y')  # e.g. 25 Oct 2021
            except (ValueError, TypeError):
                pass  # leave it unchanged if parsing fails

        rows.append(row)

    # Convert back to CSV string for upload
    csv_file_out = StringIO()
    writer = csv.DictWriter(csv_file_out, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    upload_to_s3(csv_file_out.getvalue(), suburb)

    return json.dumps(rows)

# Helper Function to Upload CSV Data to S3 bucket
def upload_to_s3(csv_data, suburb):
    file_name = f"{suburb}_traffic_data_{random.randint(10, 100)}.csv"
    try:
        # s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=file_name, Body=csv_data)
        s3_client.Bucket(S3_BUCKET_NAME).put_object(Key=file_name, Body=csv_data)
        return f"s3://{S3_BUCKET_NAME}/{file_name}"
    except (NoCredentialsError, ClientError) as e:
        raise Exception(f"S3 Upload Failed: {str(e)}")