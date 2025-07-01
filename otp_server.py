# File: otp_server.py
# Handles OTPs using a persistent Redis store, now with a robust CORS configuration.

from flask import Flask, request, jsonify, render_template
from redis import from_url, exceptions
import os
from flask_cors import CORS
import logging

# --- Configure Logger ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] [OTP_SERVER] %(message)s')
logger = logging.getLogger(__name__)

# --- Flask App & Redis Connection ---
app = Flask(__name__)

CORS(app)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_client = from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info(f"Successfully connected to Redis at {REDIS_URL}")
except exceptions.ConnectionError as e:
    logger.critical(f"FATAL: Could not connect to Redis at {REDIS_URL}. Error: {e}")
    exit(1)

def _submit_otp_logic(otp_type: str):
    """Generic logic for submitting any OTP, with standardized JSON responses."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "data": {"message": "Error: Request body must be JSON."}}), 400

        otp_value = data.get(otp_type, '').strip()
        
        # Updated validation to handle different OTP/TRN formats
        if otp_type == 'trn':
            if not (otp_value and len(otp_value) == 15 and otp_value.endswith('TRN')):
                message = "Error: TRN must be 15 characters long and end with 'TRN'."
                return jsonify({"success": False, "data": {"message": message}}), 400
        elif not (otp_value and otp_value.isdigit() and 4 <= len(otp_value) <= 6):
            message = f"Error: {otp_type.replace('_', ' ').title()} must be a 4-6 digit number."
            return jsonify({"success": False, "data": {"message": message}}), 400

        redis_client.set(otp_type, otp_value)
            
        message = f"Success: {otp_type.replace('_', ' ').title()} received."
        logger.info(f"{otp_type.upper()} OTP set.")
        return jsonify({"success": True, "data": {"message": message}}), 200

    except Exception as e:
        logger.error(f"Error in submission route for {otp_type}_otp: {e}", exc_info=True)
        message = "An internal server error occurred."
        return jsonify({"success": False, "data": {"message": message}}), 500

# --- UI Route ---
@app.route('/')
def index():
    """Serves the main OTP submission UI."""
    return render_template('index.html')

# --- Standardized Routes ---
@app.route('/submit-mobile-otp', methods=['POST'])
def submit_mobile_otp_route():
    return _submit_otp_logic('mobile_otp')

@app.route('/submit-email-otp', methods=['POST'])
def submit_email_otp_route():
    return _submit_otp_logic('email_otp')


@app.route('/submit-mobile-mail-otp', methods=['POST'])
def submit_mobile_mail_otp_route():
    return _submit_otp_logic('mobile_mail')

@app.route('/submit-trn', methods=['POST'])
def submit_trn_route():
    return _submit_otp_logic('trn')

@app.route('/get-otp', methods=['GET'])
def get_otp_route():
    otp_type = request.args.get('type')
    
    if not otp_type:
        return jsonify({"success": False, "data": {"message": "Invalid or missing 'type' parameter."}}), 400
    
    otp_value = redis_client.get(otp_type)
    
    if otp_value:
        redis_client.delete(otp_type)
        logger.info(f"OTP of type '{otp_type}' was fetched and cleared.")
    
    return jsonify({"success": True, "data": {"otp": otp_value}})

if __name__ == '__main__':
    port = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=False)