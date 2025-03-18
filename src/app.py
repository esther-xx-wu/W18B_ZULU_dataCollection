from flask import Flask, jsonify, request
import awsgi
from src.collection import fetch_traffic_data, upload_to_s3

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify(message="Hello from Flask on AWS Lambda!")

@app.route('/upload_traffic_data', methods=['GET'])
def upload_traffic_data():
    try:
        suburb = request.args.get('suburb')
        if not suburb:
            return jsonify({"error": "Suburb is required"}), 400
        
        csv_data = fetch_traffic_data(suburb)
        s3_url = upload_to_s3(csv_data, suburb)
        return jsonify({"message": "Data uploaded successfully", "s3_url": s3_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def lambda_handler(event, context):
    return awsgi.response(app, event, context, base64_content_types={"image/png"})

if __name__ == "__main__":
    app.run()
