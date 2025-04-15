from flask import Flask, jsonify, request, make_response
import awsgi
import json
from src.collection import fetch_traffic_data

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify(message="Collection Microservice is active!")

@app.route('/traffic/single/v1', methods=['GET'])
def handle_single_suburb_traffic():
    try:
        suburb = request.args.get('suburb')
        numDays = request.args.get('numDays')
        traffic_data = fetch_traffic_data(suburb, numDays)
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
