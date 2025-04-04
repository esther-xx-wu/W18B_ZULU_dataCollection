from flask import Flask, jsonify, request, make_response, Response
import awsgi
import json
from src.collection import fetch_traffic_data, upload_to_s3

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify(message="Hello from Flask on AWS Lambda!")

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
    return awsgi.response(app, event, context, base64_content_types={"image/png"})

if __name__ == "__main__":
    app.run()
