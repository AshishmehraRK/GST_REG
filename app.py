from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
import time
import json
import traceback
from logger import logger
from functions import AutomationHelper
import promoter_partner
import authorized_signatory

# --- Flask & Swagger UI Setup ---
app = Flask(__name__)
api = Api(
    app,
    version='1.0',
    title='GST Registration Automation API',
    description='An API to automate the GST registration process using a JSON configuration.',
    doc='/docs/',
    prefix='/api/v1'
)

# --- API Models (for Swagger UI) ---
config_model = api.model('GSTConfig', {
    'initial_registration_details': fields.Raw(required=True, description='Details for the initial registration page'),
    'business_details': fields.Raw(required=True, description='Details for the business information page'),
    'promoter_partner_details': fields.Raw(required=True, description='Details for all promoters/partners'),
    'authorized_signatory_details': fields.Raw(required=True, description='Details for all authorized signatories'),
    'principal_place_of_business_details': fields.Raw(required=True, description='Details for the main place of business'),
    'goods_services_details': fields.Raw(required=True, description='Details for HSN codes (goods and services)')
})

response_model = api.model('Response', {
    'status': fields.String(required=True, description='The status of the operation (e.g., success, error)'),
    'message': fields.String(required=True, description='A descriptive message about the result'),
    'errors': fields.List(fields.String, description='A list of errors, if any occurred'),
    'traceback': fields.String(description='The full error traceback for debugging purposes')
})

# --- Main Automation Logic ---
def run_full_automation(config):
    """
    This function contains the entire automation flow,
    copied from the main.ipynb notebook.
    """
    # Overwrite the main config file so that the imported modules can use it
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)
    
    logger.info("Starting automation with the provided configuration.")
    options = Options()
    # Run in headless mode for Docker environment
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Firefox(options=options)
    
    try:
        # --- Start of Notebook Flow ---
        driver.get("https://reg.gst.gov.in/registration/")
        nigga = AutomationHelper(driver, logger)
        time.sleep(5)

        # Initial Registration
        logger.info("Filling Part A: Initial Registration Details...")
        registration = config['initial_registration_details']
        values_to_click = [registration['selected_taxpayer_type'], registration['selected_state']]
        for val in values_to_click:
            nigga.click_element((By.XPATH, f"//*[text()='{val}']"))
        time.sleep(5)
        nigga.click_element((By.XPATH, f"//*[text()='{registration['selected_district']}']"))
        nigga.send_text((By.ID, "bnm"), registration['business_name'])
        nigga.send_text((By.ID, "pan_card"), registration['pan_card'])
        nigga.send_text((By.ID, "email"), registration['email'])
        nigga.send_text((By.ID, "mobile"), registration['mobile_number'])
        nigga.solve_and_enter_captcha()
        nigga.click_element((By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/form/div[2]/div/div[2]/div/button"))

        # NOTE: The following steps require manual OTP entry.
        # The API will pause here.
        logger.info("PAUSING FOR OTP: Please complete the OTP verification in the browser. Pausing for 60 seconds.")
        time.sleep(60)

        # Assuming OTP is done and user is on dashboard to start application
        nigga.click_element((By.XPATH, "/html/body/div[2]/div[1]/div/div[3]/div[2]/div/div/table/tbody/tr/td[6]/button"))

        # Business Details
        logger.info("Filling Part B: Business Details...")
        business_details = config['business_details']
        time.sleep(5)
        nigga.send_text((By.ID, "tnm"), business_details['trade_name'])
        nigga.click_element((By.XPATH, f"//*[text()='{business_details['constitution_of_business']}']"))
        if business_details.get('specific_other_constitution'):
            nigga.send_text((By.ID, "bd_ConstBuss_oth"), business_details['specific_other_constitution'])
        nigga.click_element((By.XPATH, f"//*[text()='{business_details['reason_to_obtain_registration']}']"))
        nigga.send_text((By.ID, "bd_cmbz"), business_details['date_of_commencement_of_business'])
        # (Additional fields for business details would go here if any)
        nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]")) # Save & Continue

        # Promoter/Partner Details
        logger.info("Filling Promoter/Partner Details...")
        promoter_partner.fill_promoter_partner_details(driver)
        
        # Authorized Signatory
        logger.info("Filling Authorized Signatory Details...")
        authorized_signatory.fill_authorized_signatory_details(driver)
        nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]")) # Save & Continue

        # Principal Place of Business
        logger.info("Filling Principal Place of Business Details...")
        principal_details = config['principal_place_of_business_details']
        nigga.send_text((By.ID, "onMapSerachId"), principal_details['address_map_search'])
        time.sleep(2)
        nigga.click_element((By.XPATH, f"//*[text()='{principal_details['address_map_search']}']"))
        time.sleep(1)
        nigga.click_element((By.ID, "confirm-mapquery-btn3"))
        # (Additional address fields would go here)
        
        # Nature of Business
        nature_list = principal_details.get("nature_of_business", [])
        for item in nature_list:
            nigga.click_element((By.XPATH, f"//*[contains(text(), '{item}')]"))
            time.sleep(1)
        nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]")) # Save & Continue

        # Additional Place of Business (Continue if none)
        nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div[2]/div/button[2]"))

        # Goods & Services Details
        logger.info("Filling Goods and Services Details...")
        gst_details = config['goods_services_details']
        driver.find_element(By.ID, "gs_hsn_value").send_keys(gst_details['hsn_value'])
        time.sleep(2)
        driver.find_element(By.XPATH, f"//*[text()='{gst_details['hsn_value']}']").click()
        nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div/button")) # Save & Continue
        
        # Final Verification Steps
        # ... (final submission clicks)

        logger.info("Automation flow completed successfully!")
        # --- End of Notebook Flow ---

    finally:
        logger.info("Automation process finished. Browser will close in 30 seconds.")
        time.sleep(30)
        driver.quit()

# --- API Endpoints ---
@api.route('/automate-gst-registration')
class GSTAutomation(Resource):
    @api.expect(config_model)
    @api.marshal_with(response_model)
    def post(self):
        """
        Accepts a JSON payload and runs the full GST registration automation.
        """
        try:
            config = request.get_json()
            # Basic validation
            required_sections = [
                'initial_registration_details', 'business_details', 'promoter_partner_details',
                'authorized_signatory_details', 'principal_place_of_business_details', 'goods_services_details'
            ]
            if not all(key in config for key in required_sections):
                api.abort(400, 'Missing one or more required sections in the JSON payload.', errors=f"Required: {required_sections}")

            run_full_automation(config)
            
            return {'status': 'success', 'message': 'GST automation process completed.'}

        except Exception as e:
            logger.error(f"A critical error occurred in the API: {e}")
            tb = traceback.format_exc()
            logger.error(tb)
            # Use api.abort for proper error response formatting
            api.abort(500, 'An unexpected error occurred during automation.', errors=[str(e)], traceback=tb)

@api.route('/health')
class HealthCheck(Resource):
    def get(self):
        """Provides a simple health check for the API."""
        return {'status': 'ok', 'message': 'API is running.'}, 200

if __name__ == '__main__':
    print("Starting GST Automation API on http://localhost:8001")
    print("Swagger UI is available at http://localhost:8001/docs/")
    app.run(host='0.0.0.0', port=8001, debug=True) 