import base64
import botocore
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

s3_client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=aws_region
)

# Helper Function to Call Transport NSW API and Get CSV Data
def fetch_traffic_data(suburb, numDays, queryType, format):
    if not suburb:
        return json.dumps({"error": "Suburb is required", "code": 400})
    elif not numDays:
        return json.dumps({"error": "Number of days is required", "code": 400})
    elif not numDays.isdigit():
        return json.dumps({"error": "Number of days must be a valid integer!", "code": 400})
    
    numDays = int(numDays)
    query = ""

    if queryType == 'single':
        query = f"""
        SELECT rt.date, SUM(rt.daily_total) AS total_daily_traffic
        FROM road_traffic_counts_hourly_permanent rt
        JOIN road_traffic_counts_station_reference rc 
            ON rt.station_key = rc.station_key
        WHERE rc.suburb ILIKE '{suburb}'
        GROUP BY rt.date
        ORDER BY rt.date DESC
        LIMIT {numDays};
        """
    else:
        formatted_list = ', '.join(f"'{item}'" for item in suburb)
        query = f"""
        WITH ranked_traffic AS (
            SELECT 
                rc.suburb, 
                rt.date, 
                SUM(rt.daily_total) AS total_daily_traffic,
                ROW_NUMBER() OVER (
                    PARTITION BY rc.suburb 
                    ORDER BY rt.date DESC
                ) AS rn
            FROM 
                road_traffic_counts_hourly_permanent rt
            JOIN 
                road_traffic_counts_station_reference rc 
                ON rt.station_key = rc.station_key
            WHERE 
                rc.suburb IN ({formatted_list})
            GROUP BY 
                rc.suburb, rt.date
        )
        SELECT 
            suburb, date, total_daily_traffic
        FROM 
            ranked_traffic
        WHERE 
            rn <= {numDays}
        ORDER BY 
            suburb, date DESC;
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
        message = response.text.get("ErrorDetails", {}).get("Message", "No message found")
        raise Exception(f"Failed to fetch data: {message}")

    csv_file = StringIO(response.text)
    reader = csv.DictReader(csv_file)
    rows = []

    for row in reader:
        if 'date' in row and row['date']:
            try:
                parsed_date = parser.parse(row['date'])
                row['date'] = parsed_date.strftime('%d-%b-%Y')
            except (ValueError, TypeError):
                pass
        
        if 'total_daily_traffic' in row:
            try:
                row['total_daily_traffic'] = int(row['total_daily_traffic'])
            except ValueError:
                row['total_daily_traffic'] = 0

        rows.append(row)

    csv_file_out = StringIO()
    writer = csv.DictWriter(csv_file_out, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    if format == 'csv':
        return json.dumps({
            "csv_file_download_link (valid for 5 mins only)": upload_to_s3(csv_file_out.getvalue(), suburb, format)
        })


    return json.dumps(rows)

# Helper Function to Upload CSV Data to S3 bucket
def upload_to_s3(csv_data, suburb, format):
    file_name = f"{suburb}_traffic_data_{random.randint(10, 100)}.csv"
    try:
        # s3_client.Bucket(S3_BUCKET_NAME).put_object(Key=file_name, Body=csv_data)
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=file_name, Body=csv_data)
        
        # Generate pre-signed URL that expires in 5 mins
        if format == 'csv':
            url = s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': S3_BUCKET_NAME, 'Key': file_name},
                ExpiresIn=300
            )
            print(url)
        return url

    except (NoCredentialsError, ClientError) as e:
        raise Exception(f"S3 Upload Failed: {str(e)}")
    

def upload_user_file_to_s3(base64_image, filename):
    try:
        image_bytes = base64.b64decode(base64_image)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=filename,
            Body=image_bytes,
            ContentType='image/png'
        )
        return json.dumps({'message': 'Image uploaded', 'filename': filename})
    except Exception as e:
        raise Exception(f"Failed to upload image: {e}")


def download_user_file_from_s3(username):
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=f"{username}-")
        items = response.get('Contents', [])

        images = []
        for item in items:
            key = item['Key']
            s3_response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
            image_data = s3_response['Body'].read()
            base64_encoded = base64.b64encode(image_data).decode('utf-8')
            images.append({
                'filename': key,
                'base64_image': base64_encoded
            })

        return json.dumps({'images': images})
    except Exception as e:
        raise Exception(f"Failed to download image: {e}")


# Helper Function to get the rank of the given suburb based on total traffic count
def fetch_traffic_rank_data(suburb):
    if not suburb:
        return json.dumps({"error": "Suburb is required", "code": 400})
    
    query = f"""
    WITH traffic_totals AS (
        SELECT 
            rc.suburb,
            SUM(rt.daily_total) AS total_traffic
        FROM road_traffic_counts_hourly_permanent rt
        JOIN road_traffic_counts_station_reference rc 
            ON rt.station_key = rc.station_key
        WHERE rt.date >= CURRENT_DATE - INTERVAL '5 years'
        GROUP BY rc.suburb
    ),
    ranked_suburbs AS (
        SELECT 
            suburb,
            total_traffic,
            RANK() OVER (ORDER BY total_traffic DESC) AS traffic_rank
        FROM traffic_totals
    )
    SELECT 
        suburb,
        total_traffic,
        traffic_rank
    FROM ranked_suburbs
    WHERE suburb ILIKE '{suburb}';
    """

    headers = {
        "Authorization": f"apikey {TRANSPORT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        TRAFFIC_API_ENDPOINT,
        params={"format": "json", "q": query},
        headers=headers
    )
    
    if response.status_code != 200:
        message = response.text.get("ErrorDetails", {}).get("Message", "No message found")
        raise Exception(f"Failed to fetch data: {message}")
    
    result = json.loads(response.text)
    if not result["rows"]:
        return json.dumps({"error": f"There is no traffic data for {suburb}", "code": 400})

    return_obj = {
        "rank": result["rows"][0]["traffic_rank"],
        "traffic_count": result["rows"][0]["total_traffic"]
    }
    
    return json.dumps(return_obj)


def fetch_yearly_avg_traffic(suburbs, start_year, end_year):
    try:
        formatted_suburbs = ', '.join(f"'{s}'" for s in suburbs)

        query = f"""
        SELECT 
            rc.suburb,
            rt.year, 
            SUM(rt.traffic_count) AS traffic_count
        FROM road_traffic_counts_yearly_summary rt
        JOIN road_traffic_counts_station_reference rc 
            ON rt.station_key = rc.station_key
        WHERE rc.suburb IN ({formatted_suburbs})
          AND rt.year BETWEEN {start_year} AND {end_year}
        GROUP BY rc.suburb, rt.year
        ORDER BY rc.suburb, rt.year;
        """

        headers = {
            "Authorization": f"apikey {TRANSPORT_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            TRAFFIC_API_ENDPOINT,
            params={"format": "json", "q": query},
            headers=headers
        )

        if response.status_code != 200:
            message = response.text.get("ErrorDetails", {}).get("Message", "No message found")
            raise Exception(f"Failed to fetch data: {message}")

        result = json.loads(response.text)
        rows = result.get("rows", [])

        # Build { suburb: {year: traffic_count} }
        data_by_suburb = {}
        for row in rows:
            suburb = row["suburb"]
            year = row["year"]
            traffic = row["traffic_count"]
            data_by_suburb.setdefault(suburb, {})[year] = traffic

        # Create the final structured output
        suburbs_output = []
        for suburb in suburbs:
            yearly_data = data_by_suburb.get(suburb, {})
            years_range = list(range(start_year, end_year + 1))
            traffic_counts = [yearly_data.get(year, 0) for year in years_range]

            suburbs_output.append({
                "suburb": suburb,
                "avg_traffic": traffic_counts,
                "years": years_range
            })

        return json.dumps({ "suburbsAvgTraffic": suburbs_output })

    except Exception as e:
        return json.dumps({"error": str(e), "code": 500})


def delete_user_file_from_s3(token, provided_username, title):
    try:
        cognito_client = boto3.client('cognito-idp', region_name=aws_region)
        user_response = cognito_client.get_user(AccessToken=token)

        token_username = None
        for attr in user_response['UserAttributes']:
            if attr['Name'] == 'sub':
                token_username = attr['Value']
                break

        if not token_username:
            return json.dumps({'error': 'Username (name) not found in token', 'code': 401})

        if token_username != provided_username:
            return json.dumps({'error': 'You are not authorized to delete this file', 'code': 403})

        filename = title

        # Check if file exists
        try:
            s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=filename)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return json.dumps({'error': 'File does not exist', 'code': 404})
            else:
                return json.dumps({'error': 'Error accessing S3', 'code': 500})

        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=filename)
        return json.dumps({'message': 'File deleted successfully'})

    except cognito_client.exceptions.NotAuthorizedException:
        return json.dumps({'error': 'Invalid or expired token', 'code': 401})
    except Exception as e:
        return json.dumps({'error': str(e), 'code': 500})
