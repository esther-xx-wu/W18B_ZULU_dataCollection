from flask import Flask, jsonify, request, make_response
import awsgi
from collection import fetch_traffic_data, upload_to_s3

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify(message="Hello from Flask on AWS Lambda!")

@app.route('/traffic/single/v1', methods=['GET'])
def handle_single_suburb_traffic():
    try:
        suburb = request.args.get('suburb')  
        if not suburb:
            return jsonify({"error": "Suburb is required"}), 400
        elif not request.args.get('numDays'):
            return jsonify({"error": "Number of days is required"}), 400
        elif not (request.args.get('numDays')).isdigit():
            return jsonify({"error": "Number of days must be a valid integer!"}), 400
        
        numDays = int(request.args.get('numDays'))

        csv_data = fetch_traffic_data(suburb, numDays)
        # s3_url = upload_to_s3(csv_data, suburb)

        resp = make_response(csv_data)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'text/csv'
        return resp

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

def lambda_handler(event, context):
    return awsgi.response(app, event, context, base64_content_types={"image/png"})

if __name__ == "__main__":
    app.run()
