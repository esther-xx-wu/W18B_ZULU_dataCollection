from flask import Flask, jsonify, request
import awsgi
from collection import fetch_traffic_data, upload_to_s3

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify(message="Hello from Flask on AWS Lambda!")

@app.route('/upload_traffic_data', methods=['GET'])
def upload_traffic_data():
    try:
        suburb = request.args.get('suburb')  # Get query parameter from URL
        if not suburb:
            return jsonify({"error": "Suburb is required"}), 400
        
        # Fetch CSV Data from Transport API
        csv_data = fetch_traffic_data(suburb)
        
        # Upload CSV to S3
        # s3_url = upload_to_s3(csv_data, suburb)
        
        return csv_data
        
        # return jsonify({"message": "Data uploaded successfully", "s3_url": s3_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def lambda_handler(event, context):
    return awsgi.response(app, event, context, base64_content_types={"image/png"})

if __name__ == "__main__":
    app.run()
