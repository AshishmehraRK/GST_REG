from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException, NoSuchElementException
import time, traceback, json
from logger import logger
from functions import (
    AutomationHelper,
    safe_checkbox_click,
    handle_confirmation_dialog,
    safe_click_with_dimmer_wait,
    safe_dropdown_select,
    wait_for_page_load,
    wait_for_form_ready,
    wait_for_navigation,
    wait_for_ajax_complete,
    smart_wait_and_click,
    smart_wait_and_send_keys,
    wait_for_suggestions
)
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

# --- Helper functions are now imported from functions.py ---

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
        wait_for_page_load(driver)  # Replace time.sleep(5)

        # 1. Initial Registration (Part A)
        wait_for_form_ready(driver)  # Replace time.sleep(2)
        logger.info("Filling Part A: Initial Registration Details...")
        registration = config['initial_registration_details']
        
        # Handle taxpayer type dropdown
        safe_dropdown_select(
            driver, 
            (By.ID, "applnType"), 
            registration['selected_taxpayer_type'], 
            "Taxpayer Type dropdown"
        )
        
        # Handle state dropdown  
        safe_dropdown_select(
            driver,
            (By.ID, "applnState"),
            registration['selected_state'],
            "State dropdown"
        )
        
        wait_for_ajax_complete(driver)  # Wait for state selection to load districts
        
        # Handle district dropdown
        safe_dropdown_select(
            driver,
            (By.ID, "applnDistr"), 
            registration['selected_district'],
            "District dropdown"
        )
        
        helper.send_text((By.ID, "bnm"), registration['business_name'])
        helper.send_text((By.ID, "pan_card"), registration['pan_card'])
        helper.send_text((By.ID, "email"), registration['email'])
        helper.send_text((By.ID, "mobile"), registration['mobile_number'])
        helper.solve_and_enter_captcha()
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[2]/div/div[2]/div/form/div[2]/div/div[2]/div/button", "Submit button")
        
        # Wait for page transition instead of arbitrary sleep
        wait_for_navigation(driver, timeout=5)  # Replace time.sleep(0.7)
        safe_click_with_dimmer_wait(driver, "/html/body/table-view/div/div/div/div/div[2]/a[2]", "Continue link")

        # 2. Handle Mobile and Email OTP
        logger.info("Waiting for Mobile and Email OTP submission...")
        mobile_otp = helper.poll_for_otp("mobile_otp")
        helper.send_text((By.ID, "mobile_otp"), mobile_otp)
        
        email_otp = helper.poll_for_otp("email_otp")
        helper.send_text((By.ID, "email-otp"), email_otp)

        wait_for_ajax_complete(driver)  # Replace time.sleep(2)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div/form/div/div/button", "Proceed after OTPs button") # Proceed after OTPs

        # 3. Handle TRN (Temporary Reference Number)
        logger.info("Waiting for TRN submission to log in...")
        wait_for_page_load(driver)  # Replace time.sleep(5) # Wait for TRN success page to load
        
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
        wait_for_page_load(driver)  # Replace time.sleep(5)
        # Click the "Action" button on the dashboard with dimmer safety
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div[1]/div/div[3]/div[2]/div/div/table/tbody/tr/td[6]/button", "Action button")

        # Business Details
        logger.info("Filling Part B: Business Details...")
        business_details = config['business_details']
        wait_for_form_ready(driver)  # Replace time.sleep(5)
        helper.send_text((By.ID, "tnm"), business_details['trade_name'])
        safe_click_with_dimmer_wait(driver, f"//*[text()='{business_details['constitution_of_business']}']", f"Constitution of business: {business_details['constitution_of_business']}")
        if business_details.get('specific_other_constitution'):
            helper.send_text((By.ID, "bd_ConstBuss_oth"), business_details['specific_other_constitution'])
        safe_click_with_dimmer_wait(driver, f"//*[text()='{business_details['reason_to_obtain_registration']}']", f"Reason for registration: {business_details['reason_to_obtain_registration']}")
        helper.send_text((By.ID, "bd_cmbz"), business_details['date_of_commencement_of_business'])
        
        # Handle optional registration type fields
        if business_details.get('type_of_registration'):
            type_of_registration = business_details['type_of_registration']
            if type_of_registration != "Others (Please Specify)":
                safe_dropdown_select(
                    driver,
                    (By.ID, "exty"),
                    type_of_registration,
                    "Registration Type dropdown"
                )
            else:
                safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/fieldset/div[1]/div[8]/div/div[1]/select/option[16]", "Other registration type option")
                wait_for_ajax_complete(driver)  # Replace time.sleep(2)
                helper.send_text((By.ID, "bd_othrReg"), business_details['other_registration_type'])
            
        if business_details.get('other_registration_number'):
            helper.send_text((By.ID, "exno"), business_details['other_registration_number'])
            
        if business_details.get('date_of_registration'):
            helper.send_text((By.ID, "exdt"), business_details['date_of_registration'])
        
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/fieldset/div[1]/div[8]/div/div[4]/button[1]", "Business details Save & Continue button") # Save & Continue

        # Handle Registration Certificate Upload with validation and error handling
        safe_click_with_dimmer_wait(driver, f"//*[text()='{business_details['Proof_of_Constitution_of_Business']}']", f"Proof of constitution: {business_details['Proof_of_Constitution_of_Business']}")
        wait_for_ajax_complete(driver)  # Replace time.sleep(2)
        
        # Business Constitution Proof Upload
        if business_details.get('proof_of_consititution'):
            proof_file = business_details['proof_of_consititution']
            logger.info(f"📄 Processing business constitution proof document: {proof_file}")
            
            # File existence validation
            import os
            if not os.path.exists(proof_file):
                logger.error(f"❌ Business proof document file not found: {proof_file}")
                logger.warning("⚠️ Skipping business proof upload - file does not exist")
            elif not os.path.isfile(proof_file):
                logger.error(f"❌ Business proof document path is not a file: {proof_file}")
                logger.warning("⚠️ Skipping business proof upload - path is not a valid file")
            else:
                # File exists, proceed with upload
                logger.info(f"✓ Business proof document file validated: {proof_file}")
                try:
                    upload_element = driver.find_element(By.CSS_SELECTOR,"data-file-model.ng-pristine:nth-child(4) > input:nth-child(1)")
                    upload_element.send_keys(proof_file)
                    logger.info("✅ Business constitution proof document uploaded successfully")
                    
                except NoSuchElementException:
                    logger.error("❌ Business proof upload field not found (CSS selector: data-file-model.ng-pristine:nth-child(4) > input:nth-child(1))")
                    
                except ElementNotInteractableException:
                    logger.error("❌ Business proof upload field not interactable - may be disabled or hidden")
                    
                except PermissionError:
                    logger.error(f"❌ Permission denied accessing business proof file: {proof_file}")
                    
                except Exception as upload_error:
                    logger.error(f"❌ Unexpected error during business proof upload: {type(upload_error).__name__}: {upload_error}")
        else:
            logger.info("ℹ️ No business proof document specified in config - skipping upload")
        
        wait_for_ajax_complete(driver)
        driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]").click()

        # Promoter/Partner Details with enhanced error handling
        logger.info("📋 Starting Promoter/Partner Details processing...")
        try:
            promoter_partner.fill_promoter_partner_details(driver)
            logger.info("✅ Promoter/Partner details filled successfully")
            
        except TimeoutException as timeout_error:
            logger.error(f"⏰ Timeout occurred while filling promoter/partner details: {timeout_error}")
            logger.warning("🔄 Continuing with automation despite timeout - promoter section may be incomplete")
            
        except NoSuchElementException as element_error:
            logger.error(f"🔍 Required element not found in promoter/partner section: {element_error}")
            logger.warning("🔄 Continuing with automation despite missing element")
            
        except ElementNotInteractableException as interaction_error:
            logger.error(f"🚫 Element not interactable in promoter/partner section: {interaction_error}")
            logger.warning("🔄 Continuing with automation despite interaction issue")
            
        except Exception as promoter_error:
            logger.error(f"❌ Unexpected error in promoter/partner details: {type(promoter_error).__name__}: {promoter_error}")
            logger.warning("🔄 Continuing with automation despite promoter error...")
        
        # Authorized Signatory with enhanced error handling
        logger.info("📋 Starting Authorized Signatory Details processing...")
        try:
            authorized_signatory.fill_authorized_signatory_details(driver)
            logger.info("✅ Authorized Signatory details filled successfully")
            
        except TimeoutException as timeout_error:
            logger.error(f"⏰ Timeout occurred while filling authorized signatory details: {timeout_error}")
            logger.warning("🔄 Continuing with automation despite timeout - signatory section may be incomplete")
            
        except NoSuchElementException as element_error:
            logger.error(f"🔍 Required element not found in authorized signatory section: {element_error}")
            logger.warning("🔄 Continuing with automation despite missing element")
            
        except ElementNotInteractableException as interaction_error:
            logger.error(f"🚫 Element not interactable in authorized signatory section: {interaction_error}")
            logger.warning("🔄 Continuing with automation despite interaction issue")
            
        except Exception as signatory_error:
            logger.error(f"❌ Unexpected error in authorized signatory details: {type(signatory_error).__name__}: {signatory_error}")
            logger.warning("🔄 Continuing with automation despite signatory error...")
            
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[3]/div/button[3]", "Authorized Signatory Save & Continue button") # Save & Continue


        wait_for_ajax_complete(driver)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]", "Principal Place Save & Continue button") # Save & Continue

        # Principal Place of Business
        logger.info("Filling Principal Place of Business Details...")
        principal_details = config['principal_place_of_business_details']
        wait_for_form_ready(driver)  # Replace time.sleep(5)
        
        # Handle map search with better error handling
        try:
            # Search for address
            wait_for_ajax_complete(driver) 
            helper.send_text((By.ID, "onMapSerachId"), principal_details['address_map_search'])
             # Give more time for search results to load
            
            # Click on search result
            wait_for_ajax_complete(driver) 
            safe_click_with_dimmer_wait(driver, f"//*[text()='{principal_details['address_map_search']}']", f"Address search result: {principal_details['address_map_search']}")
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

        wait_for_ajax_complete(driver)
        if principal_details.get('district'):
            District = principal_details['district']
            helper.send_text((By.ID, "dst"), District)

        wait_for_ajax_complete(driver)
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

        wait_for_ajax_complete(driver)
        if principal_details.get('street'):
            Street = principal_details['street']
            helper.send_text((By.ID, "st"), Street)

        wait_for_ajax_complete(driver)
        if principal_details.get('building_no'):
            Building_no = principal_details['building_no']
            helper.send_text((By.ID, "bno"), Building_no)

        wait_for_ajax_complete(driver)
        helper.click_element((By.ID, "bp_flrnum"))

        # Handle jurisdiction details
        if principal_details.get('jurisdiction'):
            jurisdiction = principal_details['jurisdiction']
            
            wait_for_ajax_complete(driver)
            if jurisdiction.get('ward'):
                start_jurisdiction = jurisdiction['ward']
                logger.info(f"📍 Selecting Ward: {start_jurisdiction}")
                # Try multiple possible IDs for ward dropdown
                ward_selected = safe_dropdown_select(
                    driver, 
                    ["wdcd", "wardcd", "ward", "jurisdiction_ward"], 
                    start_jurisdiction, 
                    "Ward"
                )
                if not ward_selected:
                    logger.warning(f"⚠️ Ward dropdown not found, trying text-based selection")
                    helper.click_element((By.XPATH, f"//*[text()='{start_jurisdiction}']"))

            wait_for_ajax_complete(driver)
            if jurisdiction.get('commissionerate'):
                Commissionerate = jurisdiction['commissionerate']
                logger.info(f"📍 Selecting Commissionerate: {Commissionerate}")
                # Try multiple possible IDs for commissionerate dropdown
                comm_selected = safe_dropdown_select(
                    driver, 
                    ["cmcd", "commcd", "commissionerate", "jurisdiction_comm"], 
                    Commissionerate, 
                    "Commissionerate"
                )
                if not comm_selected:
                    logger.warning(f"⚠️ Commissionerate dropdown not found, trying text-based selection")
                    helper.click_element((By.XPATH, f"//*[text()='{Commissionerate}']"))

            wait_for_ajax_complete(driver)
            if jurisdiction.get('division'):
                Division = jurisdiction['division']
                logger.info(f"📍 Selecting Division: {Division}")
                # Try multiple possible IDs for division dropdown
                div_selected = safe_dropdown_select(
                    driver, 
                    ["dvcd", "divcd", "division", "jurisdiction_div"], 
                    Division, 
                    "Division"
                )
                if not div_selected:
                    logger.warning(f"⚠️ Division dropdown not found, trying text-based selection")
                    helper.click_element((By.XPATH, f"//*[text()='{Division}']"))

            wait_for_ajax_complete(driver)
            if jurisdiction.get('range'):
                Range = jurisdiction['range']
                logger.info(f"📍 Selecting Range: {Range}")
                # We know range dropdown ID is "rgcd"
                range_selected = safe_dropdown_select(
                    driver, 
                    ["rgcd", "rangecd", "range", "jurisdiction_range"], 
                    Range, 
                    "Range"
                )
                if not range_selected:
                    logger.warning(f"⚠️ Range dropdown not found, trying text-based selection")
                    helper.click_element((By.XPATH, f"//*[text()='{Range}']"))

        # Handle nature of possession
        wait_for_ajax_complete(driver)
        if principal_details.get('nature_of_possession_of_premises'):
            select = principal_details['nature_of_possession_of_premises']
            logger.info(f"📍 Selecting Nature of Possession: {select}")
            # Try multiple possible IDs for nature of possession dropdown
            possession_selected = safe_dropdown_select(
                driver, 
                ["natposs", "nature_possession", "possession", "bp_natposs"], 
                select, 
                "Nature of Possession"
            )
            if not possession_selected:
                logger.warning(f"⚠️ Nature of possession dropdown not found, trying text-based selection")
                helper.click_element((By.XPATH, f"//*[text()='{select}']"))

        # Handle document proof
        wait_for_ajax_complete(driver)
        if principal_details.get('document_proof'):
            principal_place = principal_details['document_proof']
            logger.info(f"📍 Selecting Document Proof: {principal_place}")
            # Try multiple possible IDs for document proof dropdown
            proof_selected = safe_dropdown_select(
                driver, 
                ["docproof", "document_proof", "bp_docproof", "proof_type"], 
                principal_place, 
                "Document Proof"
            )
            if not proof_selected:
                logger.warning(f"⚠️ Document proof dropdown not found, trying text-based selection")
                helper.click_element((By.XPATH, f"//*[text()='{principal_place}']"))

        # Principal Place Document Uploads with validation and error handling
        logger.info("📁 Starting principal place document upload process...")
        
        # First document upload
        if principal_details.get('document_upload'):
            document1 = principal_details['document_upload']
            logger.info(f"📄 Processing principal place document 1: {document1}")
            
            # File existence validation
            import os
            if not os.path.exists(document1):
                logger.error(f"❌ Principal place document 1 file not found: {document1}")
                logger.warning("⚠️ Skipping document 1 upload - file does not exist")
            elif not os.path.isfile(document1):
                logger.error(f"❌ Principal place document 1 path is not a file: {document1}")
                logger.warning("⚠️ Skipping document 1 upload - path is not a valid file")
            else:
                # File exists, proceed with upload
                logger.info(f"✓ Principal place document 1 file validated: {document1}")
                try:
                    upload_element = driver.find_element(By.XPATH,'//*[@id="bp_upload"]')
                    upload_element.send_keys(document1)
                    logger.info("✅ Principal place document 1 uploaded successfully")
                    
                except NoSuchElementException:
                    logger.error("❌ Principal place upload field not found (XPath: //*[@id='bp_upload'])")
                    
                except ElementNotInteractableException:
                    logger.error("❌ Principal place upload field not interactable - may be disabled or hidden")
                    
                except PermissionError:
                    logger.error(f"❌ Permission denied accessing principal place document 1: {document1}")
                    
                except Exception as upload_error:
                    logger.error(f"❌ Unexpected error during principal place document 1 upload: {type(upload_error).__name__}: {upload_error}")
        else:
            logger.info("ℹ️ No principal place document 1 specified in config - skipping upload")

        wait_for_ajax_complete(driver)
        
        # Second document upload
        if principal_details.get('document_upload_2'):
            document2 = principal_details['document_upload_2']
            logger.info(f"📄 Processing principal place document 2: {document2}")
            
            # File existence validation
            import os
            if not os.path.exists(document2):
                logger.error(f"❌ Principal place document 2 file not found: {document2}")
                logger.warning("⚠️ Skipping document 2 upload - file does not exist")
            elif not os.path.isfile(document2):
                logger.error(f"❌ Principal place document 2 path is not a file: {document2}")
                logger.warning("⚠️ Skipping document 2 upload - path is not a valid file")
            else:
                # File exists, proceed with upload
                logger.info(f"✓ Principal place document 2 file validated: {document2}")
                try:
                    upload_element = driver.find_element(By.ID,'bp_upload')
                    upload_element.send_keys(document2)
                    logger.info("✅ Principal place document 2 uploaded successfully")
                    
                except NoSuchElementException:
                    logger.error("❌ Principal place upload field not found (ID: bp_upload)")
                    
                except ElementNotInteractableException:
                    logger.error("❌ Principal place upload field not interactable - may be disabled or hidden")
                    
                except PermissionError:
                    logger.error(f"❌ Permission denied accessing principal place document 2: {document2}")
                    
                except Exception as upload_error:
                    logger.error(f"❌ Unexpected error during principal place document 2 upload: {type(upload_error).__name__}: {upload_error}")
        else:
            logger.info("ℹ️ No principal place document 2 specified in config - skipping upload")
            
        logger.info("📁 Principal place document upload process completed")
        
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
                        wait_for_ajax_complete(driver)  # Replace time.sleep(1)
                        
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
                        label_element.click()
                        logger.info(f"Clicked label directly for {item}")
                    except Exception as label_error:
                        logger.error(f"Failed to click label for {item}: {label_error}")
                        continue
                        
                wait_for_ajax_complete(driver)  # Replace time.sleep(0.5)
                
            except Exception as item_error:
                logger.error(f"Failed to process nature of business item '{item}': {item_error}")
                continue  # Skip this item and continue with the next one

        wait_for_ajax_complete(driver)
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div/button[2]", "Nature of Business Save & Continue button") # Save & Continue

        # Additional Place of Business (Continue if none)
        wait_for_ajax_complete(driver)
        
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
        try:
            driver.find_element(By.ID, "gs_hsn_value").send_keys(gst_details['hsn_value'])
            wait_for_ajax_complete(driver) 
            try:
                safe_click_with_dimmer_wait(driver, f"//*[text()='{gst_details['hsn_value']}']", "HSN exact match")
            except Exception as e:
                logger.error(f"Failed to click HSN exact match: {e}")
                driver.find_element(By.ID, "gs_hsn_value").send_keys(gst_details['hsn_value'])
                wait_for_ajax_complete(driver) 
                safe_click_with_dimmer_wait(driver, f"//*[text()='{gst_details['hsn_value']}']", "HSN exact match")
        except Exception as e:
            logger.error(f"Failed to click HSN exact match: {e}")

        wait_for_ajax_complete(driver) 
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div[2]/div/button", "Goods Services Save & Continue button") # Save & Continue
        

        # wait_for_ajax_complete(driver)  # Replace time.sleep(1)
        # safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div[2]/div/button[2]", "Additional form continue button")

        safe_click_with_dimmer_wait(driver, "//*[@type='submit']", "Submit button")

        # Checkbox click with dimmer protection
        # safe_checkbox_click(driver, "chkboxop0", "Agreement checkbox")

        ## GOOD AND SERVICE SAVE AND CONTINUE
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div/div/button", "Final submission button") # Save & Continue


        ## Pop Up
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/div[2]/div/div/div[2]/button", "Pop Up button") # Save & Continue

        # Check BOX
        safe_checkbox_click(driver, "authveri", "Here BY")

        ## Name of Authorized Signatory
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div[2]/fieldset/div[2]/div/div[1]/select/option[2]", "Name of Authorized Signatory")

        ## Place
        
        helper.send_text((By.ID, "veriPlace"), "India")

        ## Submit Button
        safe_click_with_dimmer_wait(driver, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[1]/div/div/fieldset/span/button", "Submit button") # Save & Continue

        # Final submission steps would continue here...
        logger.info("Automation flow completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred during the automation process: {e}")
        logger.error(traceback.format_exc())
        # You might want to re-raise the exception to have it caught by the API endpoint
        raise

    finally:
        logger.info("🎉 Automation process finished. Browser will remain open for your review.")
        logger.info("ℹ️ You can now manually review the filled form and submit it when ready.")
        logger.info("🌐 To close the browser, simply close the browser window manually.")
        # driver.quit()  # Browser will stay open for user review

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
