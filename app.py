from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
import time, traceback, json
from logger import logger
from functions import AutomationHelper
import promoter_partner, authorized_signatory
import requests

# --- Flask & Swagger UI Setup ---
app = Flask(__name__)
CORS(app)  # Enable CORS for all origins

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

# --- Helper Function for Dimmer-Safe Clicking ---
def safe_click_with_dimmer_wait(driver, xpath, description="button"):
    """
    Safely click a button while handling dimmer overlay issues
    """
    try:
        # Wait for any dimmer to disappear
        wait = WebDriverWait(driver, 15)
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "dimmer-holder")))
        
        # Now try to click the button
        button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        button.click()
        logger.info(f"{description} clicked successfully")
        return True
        
    except (TimeoutException, Exception) as e:
        logger.warning(f"Normal click failed for {description}, trying JavaScript click: {e}")
        # Fallback: Use JavaScript click to bypass the overlay
        try:
            button = driver.find_element(By.XPATH, xpath)
            driver.execute_script("arguments[0].click();", button)
            logger.info(f"{description} clicked with JavaScript")
            return True
        except Exception as js_error:
            logger.error(f"All click methods failed for {description}: {js_error}")
            return False

# --- Main Automation Logic ---
def run_full_automation(config):
    """
    This function contains the entire automation flow, corrected to handle
    OTP and TRN verification sequentially and reliably.
    """
    # Overwrite the main config file so that the imported modules can use it
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)
    
    logger.info("Starting automation with the provided configuration.")
    options = Options()
    # Run in visible mode for debugging and monitoring
    # options.add_argument('--headless')  # Disabled to show browser window
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Firefox(options=options)
    
    try:
        # --- Start of Corrected Flow ---
        driver.get("https://reg.gst.gov.in/registration/")
        helper = AutomationHelper(driver, logger) # Renamed variable for professionalism
        time.sleep(5)

        # 1. Initial Registration (Part A)
        time.sleep(2)
        logger.info("Filling Part A: Initial Registration Details...")
        registration = config['initial_registration_details']
        values_to_click = [registration['selected_taxpayer_type'], registration['selected_state']]
        for val in values_to_click:
            helper.click_element((By.XPATH, f"//*[text()='{val}']"))
        time.sleep(2)
        helper.click_element((By.XPATH, f"//*[text()='{registration['selected_district']}']"))
        helper.send_text((By.ID, "bnm"), registration['business_name'])
        helper.send_text((By.ID, "pan_card"), registration['pan_card'])
        helper.send_text((By.ID, "email"), registration['email'])
        helper.send_text((By.ID, "mobile"), registration['mobile_number'])
        helper.solve_and_enter_captcha()
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[2]/div/div[2]/div/form/div[2]/div/div[2]/div/button", "Submit button")
        time.sleep(2)
        safe_click_with_dimmer_wait(driver, "/html/body/table-view/div/div/div/div/div[2]/a[2]", "Continue link")

        # 2. Handle Mobile and Email OTP
        logger.info("Waiting for Mobile and Email OTP submission...")
        mobile_otp = helper.poll_for_otp("mobile_otp")
        helper.send_text((By.ID, "mobile_otp"), mobile_otp)
        
        email_otp = helper.poll_for_otp("email_otp")
        helper.send_text((By.ID, "email-otp"), email_otp)

        time.sleep(2)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div/form/div/div/button", "Proceed after OTPs button") # Proceed after OTPs

        # 3. Handle TRN (Temporary Reference Number)
        logger.info("Waiting for TRN submission to log in...")
        time.sleep(5) # Wait for TRN success page to load
        
        # Proceed to login page
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div/div[2]/div/a", "Login page link") 
        
        trn = helper.poll_for_otp("trn")
        helper.send_text((By.ID, "trnno"), trn)
        helper.handle_initial_captcha()
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[2]/div/div[2]/div/form/div[2]/div/div[2]/div/button", "Proceed with TRN button") # Proceed with TRN

        # 4. Handle Post-TRN Login OTP
        logger.info("Waiting for OTP after TRN login...")
        login_otp = helper.poll_for_otp("mobile_otp") # GST portal asks for mobile/email OTP again
        helper.send_text((By.ID, "mobile_otp"), login_otp)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div/form/div/div/button", "Final proceed button") # Proceed

        # 5. Continue with Part B of the application
        logger.info("Successfully logged in. Starting Part B...")
        time.sleep(5)
        # Click the "Action" button on the dashboard with dimmer safety
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[1]/div/div[3]/div[2]/div/div/table/tbody/tr/td[6]/button", "Action button")

        # Business Details
        logger.info("Filling Part B: Business Details...")
        business_details = config['business_details']
        time.sleep(5)
        helper.send_text((By.ID, "tnm"), business_details['trade_name'])
        helper.click_element((By.XPATH, f"//*[text()='{business_details['constitution_of_business']}']"))
        if business_details.get('specific_other_constitution'):
            helper.send_text((By.ID, "bd_ConstBuss_oth"), business_details['specific_other_constitution'])
        helper.click_element((By.XPATH, f"//*[text()='{business_details['reason_to_obtain_registration']}']"))
        helper.send_text((By.ID, "bd_cmbz"), business_details['date_of_commencement_of_business'])
        
        # Handle optional registration type fields
        if business_details.get('type_of_registration'):
            type_of_registration = business_details['type_of_registration']
            if type_of_registration != "Others (Please Specify)":
                helper.click_element((By.ID, "exty"))
                helper.click_element((By.XPATH, f"//option[text()='{type_of_registration}']"))   
            else:
                helper.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/fieldset/div[1]/div[8]/div/div[1]/select/option[16]"))
                time.sleep(2)
                helper.send_text((By.ID, "bd_othrReg"), business_details['other_registration_type'])
            
        if business_details.get('other_registration_number'):
            helper.send_text((By.ID, "exno"), business_details['other_registration_number'])
            
        if business_details.get('date_of_registration'):
            helper.send_text((By.ID, "exdt"), business_details['date_of_registration'])
        
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/fieldset/div[1]/div[8]/div/div[4]/button[1]", "Business details Save & Continue button") # Save & Continue

        # Handle Registration Certificate Upload
        helper.click_element((By.XPATH, f"//*[text()='{business_details['Proof_of_Constitution_of_Business']}']"))
        time.sleep(2)
        
        if business_details.get('proof_of_consititution'):
            driver.find_element(By.CSS_SELECTOR,"data-file-model.ng-pristine:nth-child(4) > input:nth-child(1)").send_keys(business_details['proof_of_consititution'])
        
        time.sleep(2)
        driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]").click()

        # Promoter/Partner Details
        logger.info("Filling Promoter/Partner Details...")
        try:
            promoter_partner.fill_promoter_partner_details(driver)
            logger.info("✅ Promoter/Partner details filled successfully")
        except Exception as promoter_error:
            logger.error(f"❌ Failed to fill promoter/partner details: {promoter_error}")
            logger.info("🔄 Continuing with automation despite promoter error...")
        
        # Authorized Signatory
        logger.info("Filling Authorized Signatory Details...")
        authorized_signatory.fill_authorized_signatory_details(driver)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[3]/div/button[3]", "Authorized Signatory Save & Continue button") # Save & Continue


        time.sleep(3)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]", "Principal Place Save & Continue button") # Save & Continue

        # Principal Place of Business
        logger.info("Filling Principal Place of Business Details...")
        principal_details = config['principal_place_of_business_details']
        time.sleep(5)
        
        # Handle map search with better error handling
        try:
            # Search for address
            time.sleep(3) 
            helper.send_text((By.ID, "onMapSerachId"), principal_details['address_map_search'])
             # Give more time for search results to load
            
            # Click on search result
            time.sleep(3) 
            helper.click_element((By.XPATH, f"//*[text()='{principal_details['address_map_search']}']"))
             # Wait for map to update
            
            # Try to confirm map query with multiple approaches
            logger.info("Attempting to confirm map query...")
            
            # Method 1: Wait longer and try normal click
            try:
                wait = WebDriverWait(driver, 15)  # Increased wait time
                confirm_button = wait.until(EC.element_to_be_clickable((By.ID, "confirm-mapquery-btn3")))
                confirm_button.click()
                logger.info("Map query confirmed successfully with normal click")
                
            except TimeoutException:
                logger.warning("Normal click failed, trying JavaScript click...")
                # Method 2: JavaScript click fallback
                try:
                    confirm_button = driver.find_element(By.ID, "confirm-mapquery-btn3")
                    driver.execute_script("arguments[0].click();", confirm_button)
                    logger.info("Map query confirmed successfully with JavaScript click")
                    
                except Exception as js_error:
                    logger.warning(f"JavaScript click also failed: {js_error}")
                    # Method 3: Try alternative selectors
                    try:
                        # Try clicking by CSS selector
                        confirm_button = driver.find_element(By.CSS_SELECTOR, "#confirm-mapquery-btn3")
                        driver.execute_script("arguments[0].click();", confirm_button)
                        logger.info("Map query confirmed with CSS selector")
                    except Exception as css_error:
                        logger.warning(f"CSS selector click failed: {css_error}")
                        # Method 4: Skip map confirmation if all methods fail
                        logger.warning("All map confirmation methods failed - proceeding without map confirmation")
                        
        except Exception as map_error:
            logger.error(f"Map search failed: {map_error}")
            logger.info("Proceeding without map search - will fill address manually")
        

        # Fill additional address details
        if principal_details.get('pincode'):
            pin = principal_details['pincode']
            helper.send_text((By.ID, "pncd"), pin)

        time.sleep(2)
        if principal_details.get('district'):
            District = principal_details['district']
            helper.send_text((By.ID, "dst"), District)

        time.sleep(2)
        if principal_details.get('city_town_village'):
            City = principal_details['city_town_village']
            try:
                helper.send_text((By.ID, "loc"), City)
            except Exception as loc_error:
                logger.warning(f"Normal send_text failed for 'loc' field, trying JavaScript approach: {loc_error}")
                try:
                    # Use JavaScript to handle disabled field
                    loc_element = driver.find_element(By.ID, "loc")
                    driver.execute_script("arguments[0].removeAttribute('disabled');", loc_element)
                    driver.execute_script("arguments[0].removeAttribute('readonly');", loc_element)
                    driver.execute_script("arguments[0].value = arguments[1];", loc_element, City)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", loc_element)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", loc_element)
                    logger.info("✓ City/Town/Village field filled via JavaScript")
                except Exception as js_error:
                    logger.error(f"JavaScript approach also failed for 'loc' field: {js_error}")
                    logger.info("Continuing automation despite 'loc' field failure...")

        time.sleep(2)
        if principal_details.get('street'):
            Street = principal_details['street']
            helper.send_text((By.ID, "st"), Street)

        time.sleep(2)
        if principal_details.get('building_no'):
            Building_no = principal_details['building_no']
            helper.send_text((By.ID, "bno"), Building_no)

        time.sleep(5)
        helper.click_element((By.ID, "bp_flrnum"))

        # Handle jurisdiction details
        if principal_details.get('jurisdiction'):
            jurisdiction = principal_details['jurisdiction']
            
            time.sleep(2)
            if jurisdiction.get('ward'):
                start_jurisdiction = jurisdiction['ward']
                helper.click_element((By.XPATH, f"//*[text()='{start_jurisdiction}']"))

            time.sleep(1)
            if jurisdiction.get('commissionerate'):
                Commissionerate = jurisdiction['commissionerate']
                helper.click_element((By.XPATH, f"//*[text()='{Commissionerate}']"))

            time.sleep(2)
            if jurisdiction.get('division'):
                Division = jurisdiction['division']
                helper.click_element((By.XPATH, f"//*[text()='{Division}']"))

            time.sleep(2)
            if jurisdiction.get('range'):
                Range = jurisdiction['range']
                helper.click_element((By.XPATH, f"//*[text()='{Range}']"))

        # Handle nature of possession
        time.sleep(2)
        if principal_details.get('nature_of_possession_of_premises'):
            select = principal_details['nature_of_possession_of_premises']
            helper.click_element((By.XPATH, f"//*[text()='{select}']"))

        # Handle document proof
        time.sleep(2)
        if principal_details.get('document_proof'):
            principal_place = principal_details['document_proof']
            helper.click_element((By.XPATH, f"//*[text()='{principal_place}']"))

        # Handle document upload
        time.sleep(2)
        if principal_details.get('document_upload'):
            driver.find_element(By.XPATH,'//*[@id="bp_upload"]').send_keys(principal_details['document_upload'])

        time.sleep(2)
        if principal_details.get('document_upload_2'):
            driver.find_element(By.ID,'bp_upload').send_keys(principal_details['document_upload_2'])
        
        # Nature of Business with robust error handling
        nature_list = principal_details.get("nature_of_business", [])
        logger.info(f"Processing {len(nature_list)} nature of business items: {nature_list}")
        
        for item in nature_list:
            try:
                logger.info(f"Processing nature of business item: {item}")
                label_xpath = f"//label[contains(text(), '{item}')]"
                label_element = driver.find_element(By.XPATH, label_xpath)
                checkbox_id = label_element.get_attribute("for")
                
                if checkbox_id:
                    logger.info(f"Found checkbox ID: {checkbox_id}")
                    
                    # Method 1: Scroll element into view first
                    try:
                        checkbox_element = driver.find_element(By.ID, checkbox_id)
                        driver.execute_script("arguments[0].scrollIntoView(true);", checkbox_element)
                        time.sleep(1)  # Wait for scroll to complete
                        
                        # Method 2: Wait for element to be clickable
                        wait = WebDriverWait(driver, 10)
                        clickable_checkbox = wait.until(EC.element_to_be_clickable((By.ID, checkbox_id)))
                        clickable_checkbox.click()
                        logger.info(f"Successfully clicked checkbox {checkbox_id} with normal click")
                        
                    except (TimeoutException, ElementNotInteractableException) as click_error:
                        logger.warning(f"Normal click failed for {checkbox_id}: {click_error}")
                        
                        # Method 3: JavaScript click fallback
                        try:
                            checkbox_element = driver.find_element(By.ID, checkbox_id)
                            driver.execute_script("arguments[0].click();", checkbox_element)
                            logger.info(f"Successfully clicked checkbox {checkbox_id} with JavaScript")
                            
                        except Exception as js_error:
                            logger.warning(f"JavaScript click failed for {checkbox_id}: {js_error}")
                            
                            # Method 4: Click the label instead
                            try:
                                driver.execute_script("arguments[0].click();", label_element)
                                logger.info(f"Successfully clicked label for {item}")
                                
                            except Exception as label_error:
                                logger.error(f"All click methods failed for {item}: {label_error}")
                                continue
                else:
                    # No checkbox ID found, click the label directly
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", label_element)
                        time.sleep(1)
                        label_element.click()
                        logger.info(f"Clicked label directly for {item}")
                    except Exception as label_error:
                        logger.error(f"Failed to click label for {item}: {label_error}")
                        continue
                        
                time.sleep(0.5)  # Small delay between selections
                
            except Exception as item_error:
                logger.error(f"Failed to process nature of business item '{item}': {item_error}")
                continue  # Skip this item and continue with the next one

        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]", "Nature of Business Save & Continue button") # Save & Continue

        # Additional Place of Business (Continue if none)
        time.sleep(1)
        
        # Handle dimmer overlay for Additional Place of Business button
        try:
            # Wait for any dimmer to disappear
            wait = WebDriverWait(driver, 15)
            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "dimmer-holder")))
            
            # Now try to click the button
            button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div[2]/div/button[2]")))
            button.click()
            logger.info("Additional Place of Business button clicked successfully")
            
        except (TimeoutException, Exception) as e:
            logger.warning(f"Normal click failed for Additional Place of Business button, trying JavaScript click: {e}")
            # Fallback: Use JavaScript click to bypass the overlay
            button = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div[2]/div/button[2]")
            driver.execute_script("arguments[0].click();", button)
            logger.info("Additional Place of Business button clicked with JavaScript")

        # Goods & Services Details
        logger.info("Filling Goods and Services Details...")
        gst_details = config['goods_services_details']
        driver.find_element(By.ID, "gs_hsn_value").send_keys(gst_details['hsn_value'])
        time.sleep(2)
        driver.find_element(By.XPATH, f"//*[text()='{gst_details['hsn_value']}']").click()
        time.sleep(2)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div[2]/div/button", "Goods Services Save & Continue button") # Save & Continue
        

        time.sleep(1)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div[2]/div/button[2]", "Additional form continue button")

        time.sleep(2)
        safe_click_with_dimmer_wait(driver, "//*[@type='submit']", "Submit button")


        # Pop Up handling with dimmer safety
        # time.sleep(3)
        # safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/div[2]/div/div/div[2]/button", "Popup button 1")

        # time.sleep(3)
        # safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div[2]/div/div/button", "Form button 1")

        time.sleep(3)
        # Checkbox click - usually doesn't need dimmer protection
        driver.find_element(By.ID, "chkboxop0").click()
        logger.info("Checkbox chkboxop0 clicked")

        time.sleep(3)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div/button", "Form button 2")

        time.sleep(3)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/div[2]/div/div/div[2]/button", "Final submission button")

        # Final submission steps would continue here...
        logger.info("Automation flow completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred during the automation process: {e}")
        logger.error(traceback.format_exc())
        # You might want to re-raise the exception to have it caught by the API endpoint
        raise

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
    # Check if we should run direct automation or API server (default)
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--direct':
        # Run direct automation using config.json
        print("Running GST automation directly using config.json...")
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            run_full_automation(config)
            print("✅ GST automation completed successfully!")
            
        except FileNotFoundError:
            print("❌ Error: config.json file not found!")
            print("Please ensure config.json exists in the same directory.")
        except Exception as e:
            print(f"❌ Error during automation: {e}")
            logger.error(f"Automation failed: {e}")
            logger.error(traceback.format_exc())
    else:
        # Default: Start Flask API server
        print("Starting GST Automation API on http://localhost:8001")
        print("Swagger UI is available at http://localhost:8001/docs/")
        print("To run automation directly, use: python3 app.py --direct")
        app.run(host='0.0.0.0', port=8001, debug=True)
