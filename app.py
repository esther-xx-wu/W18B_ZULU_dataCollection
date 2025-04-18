from flask import Flask, jsonify, request, make_response
import awsgi
import json
from src.collection import fetch_traffic_data

app = Flask(__name__)

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
    
@app.route('/traffic/multiple/v1', methods=['POST'])
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
