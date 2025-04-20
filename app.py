from flask import Flask, jsonify, request, make_response
import awsgi
import json
from src.auth import validate_token
from src.collection import fetch_traffic_data, fetch_traffic_rank_data, upload_user_file_to_s3, download_user_file_from_s3
from functools import wraps

app = Flask(__name__)

# Decorator for protected routes
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                token = auth_header
        
        if not token:
            return jsonify({'message': 'access_token is missing'}), 401
        
        valid, message = validate_token(token)
        if not valid:
            return jsonify({'message': f'Invalid access_token: {message}'}), 401
            
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def home():
    return jsonify(message="Traffic Collection Microservice is active!")

@app.route('/traffic/single/v1', methods=['GET'])
def handle_single_suburb_traffic():
    """
    Collects and retrieves traffic data for given suburbs for the number of days provided.

    Args:
        suburbs (suburb): Name of suburb.
        numDays (int): Number of days to retrieve data for.

    Returns:
        Response: JSON data.
    """
    try:
        suburb = request.args.get('suburb')
        numDays = request.args.get('numDays')
        traffic_data = fetch_traffic_data(suburb, numDays, 'single', 'json')
        traffic_data_json = json.loads(traffic_data)
        if "error" in traffic_data_json:
            return jsonify({"error": traffic_data_json["error"]}), traffic_data_json["code"]

        resp = make_response(traffic_data)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json'
        return resp

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/traffic/multiple/v1', methods=['GET'])
def handle_multiple_suburb_traffic():
    """
    Collects and retrieves traffic data for given suburbs for the number of days provided.

    Args:
        suburbs (list[str]): List of suburb names (in request body).
        numDays (int): Number of days to retrieve data for.
        format (str): Output format. Options: 'json', 'csv'.

    Returns:
        Response: JSON or temp download link.
    """
    try:
        suburbs = request.get_json().get('suburbs', [])
        numDays = request.args.get('numDays')
        format = request.args.get('format')

        if format != 'csv' and format != 'json':
            return jsonify({"error": "Invalid or unsupported format provided"}), 400
        
        if not isinstance(suburbs, list):
            return jsonify({'error': 'Expected a list of suburbs'}), 400
        
        if len(suburbs) > 10:
            return jsonify({'error': 'More than 10 suburbs provided'}), 400

        traffic_data = fetch_traffic_data(suburbs, numDays, 'multiple', format)
        traffic_data_json = json.loads(traffic_data)
        if "error" in traffic_data_json:
            return jsonify({"error": traffic_data_json["error"]}), traffic_data_json["code"]

        resp = make_response(traffic_data)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json'
        return resp

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/traffic/rank/v1', methods=['POST'])
def handle_suburb_traffic_rank():
    """
    Calculates and returns the rank of the given suburb in terms of total traffic count.

    Args:
        suburbs (str): Suburb for which data is requested.

    Returns:
        Response: JSON.
    """
    try:
        suburb = request.args.get('suburb')

        traffic_rank_data = fetch_traffic_rank_data(suburb)
        traffic_rank_data_json = json.loads(traffic_rank_data)
        if "error" in traffic_rank_data_json:
            return jsonify({"error": traffic_rank_data_json["error"]}), traffic_rank_data_json["code"]

        resp = make_response(traffic_rank_data)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json'
        return resp

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/upload-graph/v1', methods=['POST'])
@token_required
def upload_graph():
    data = request.json
    base64_image = data.get('image-base64')
    suburbs = data.get('suburbs')
    print(suburbs)
    username = data.get('username')

    if not all([base64_image, username, suburbs]):
        return jsonify({'error': 'Missing fields'}), 400

    filename = f"{username}-{suburbs}.png"

    try:
        return_data = upload_user_file_to_s3(base64_image, filename)
        return_data_json = json.loads(return_data)
        if "error" in return_data_json:
            return jsonify({"error": return_data_json["error"]}), return_data_json["code"]

        resp = make_response(return_data)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json'
        return resp
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download-graphs/v1', methods=['GET'])
@token_required
def download_graphs():
    username = request.args.get('username')

    if not username:
        return jsonify({'error': 'Missing username'}), 400

    try:
        return_data = download_user_file_from_s3(username)
        return_data_json = json.loads(return_data)
        if "error" in return_data_json:
            return jsonify({"error": return_data_json["error"]}), return_data_json["code"]

        resp = make_response(return_data)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json'
        return resp
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def lambda_handler(event, context):
    if 'httpMethod' not in event:
        if 'requestContext' in event and 'http' in event['requestContext']:
            # Convert API Gateway v2 format to the format awsgi expects
            return awsgi.response(app, convert_v2_to_v1(event), context, base64_content_types={"image/png"})
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'This endpoint should be accessed through API Gateway'})
        }
    return awsgi.response(app, event, context, base64_content_types={"image/png"})

def convert_v2_to_v1(event):
    v1_event = {
        'httpMethod': event['requestContext']['http']['method'],
        'path': event['requestContext']['http']['path'],
        'headers': event['headers'],
        'queryStringParameters': event.get('queryStringParameters', {}),
        'body': event.get('body', ''),
        'isBase64Encoded': event.get('isBase64Encoded', False)
    }
    return v1_event

if __name__ == "__main__":
    app.run()
