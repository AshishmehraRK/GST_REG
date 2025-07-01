from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.firefox.options import Options
from functions import AutomationHelper
import time
from logger import logger
import json

def is_element_editable(driver, locator):
    """Check if an element is enabled and not readonly/disabled"""
    try:
        element = driver.find_element(*locator)
        is_enabled = element.is_enabled()
        is_readonly = element.get_attribute("readonly") is not None
        is_disabled = element.get_attribute("disabled") is not None
        return is_enabled and not is_readonly and not is_disabled
    except:
        return False

def safe_send_text(nigga, driver, locator, value):
    """Safely send text to a field only if it's editable, silently skip if not"""
    if not value or str(value).strip() == "":
        return
    
    if is_element_editable(driver, locator):
        try:
            nigga.send_text(locator, value)
        except:
            pass  # Silently continue

def safe_click_element(nigga, driver, locator):
    """Safely click an element only if it's enabled, silently skip if not"""
    try:
        element = driver.find_element(*locator)
        if element.is_enabled() and not element.get_attribute("disabled"):
            nigga.click_element(locator)
    except:
        pass  # Silently continue

def fill_authorized_signatory_details(driver):
    """
    Main function to orchestrate filling details for all authorized signatories.
    It assumes the driver is on the page that lists the signatories.
    """
    with open('config.json', 'r') as f:
        config = json.load(f)

    signatories_data = config.get('authorized_signatory_details', [])
    nigga = AutomationHelper(driver, logger)

    if not signatories_data:
        logger.error("No 'authorized_signatory_details' found in config.json. Aborting.")
        return

    # Handle both single dictionary and list of dictionaries
    if isinstance(signatories_data, dict):
        # If it's a single dictionary, convert it to a list
        signatories_list = [signatories_data]
    else:
        # If it's already a list, use it as is
        signatories_list = signatories_data

    logger.info(f"Starting to fill details for {len(signatories_list)} authorized signatories")

    # --- Logic to handle multiple signatories ---
    for i, signatory_data in enumerate(signatories_list):
        is_last_signatory = (i == len(signatories_list) - 1)
        logger.info(f"Processing signatory {i+1}/{len(signatories_list)}: {signatory_data.get('first_name', 'Unknown')}")

        # For the very first signatory, we might need to click "Add New" from the list view
        if i == 0:
            try:
                # Check if the form is already displayed, if not, click 'Add New'
                form_header = driver.find_elements(By.XPATH, "//h4[contains(., 'Details of Authorized Signatory')]")
                if not form_header or not form_header[0].is_displayed():
                     logger.info("Signatory list view detected. Clicking 'Add New' to open form.")
                     add_new_list_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add New')]"))
                     )
                     add_new_list_button.click()
                     time.sleep(2)  # Wait for form to load
            except Exception as e:
                logger.warning(f"Could not find or click 'Add New' from list view, assuming form is already open. Error: {e}")

        # Fill the details for the current signatory
        fill_single_signatory_details(driver, nigga, signatory_data)

        # Decide whether to 'Save & Add New' or 'Save & Continue'
        if not is_last_signatory:
            logger.info("Not the last signatory. Clicking 'Save & Add New'.")
            try:
                # Try the specific button first
                save_and_add_new_button = None
                try:
                    save_and_add_new_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@data-ng-click=\"addAuthourized('savenew')\"]"))
                    )
                except TimeoutException:
                    # Fallback to generic text search
                    save_and_add_new_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add New')]"))
                    )
                
                save_and_add_new_button.click()
                # Wait for form to be ready for next entry
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "fnm")))
                time.sleep(2)  # Additional wait for form to clear
                logger.info("Form cleared for next signatory.")
            except TimeoutException:
                logger.error("Timed out waiting for 'Save & Add New' button or form to clear. Aborting.")
                break
        else:
            logger.info("Last signatory processed. Clicking final 'Save & Continue'.")
            try:
                # Try the specific button first
                save_and_continue_button = None
                try:
                    save_and_continue_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@data-ng-bind=\"trans.LBL_SAVE_CONTINUE\"]"))
                    )
                except TimeoutException:
                    # Fallback to generic text search
                    save_and_continue_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Save & Continue')]"))
                    )
                
                save_and_continue_button.click()
                logger.info("Successfully clicked final 'Save & Continue' for Authorized Signatory section.")
                time.sleep(3)  # Wait for next page to load
            except Exception as e:
                logger.error(f"Could not click the final 'Save & Continue' button: {e}")

    logger.info("Completed authorized signatory details filling process")


def fill_single_signatory_details(driver, nigga, signatory_data):
    """
    Fills the form fields for a single authorized signatory.
    """
    logger.info(f"Filling details for signatory: {signatory_data.get('first_name', '')} {signatory_data.get('last_name', '')}")
    
    try:
        # Primary Authorized Signatory Checkbox
        if signatory_data.get('is_primary_signatory') == "Yes":
            safe_click_element(nigga, driver, (By.ID, "auth_prim"))

        # Personal Information
        safe_send_text(nigga, driver, (By.ID, "fnm"), signatory_data.get('first_name', ''))
        safe_send_text(nigga, driver, (By.ID, "as_mname"), signatory_data.get('middle_name', ''))
        safe_send_text(nigga, driver, (By.ID, "as_lname"), signatory_data.get('last_name', ''))
        safe_send_text(nigga, driver, (By.ID, "ffname"), signatory_data.get('father_first_name', ''))
        safe_send_text(nigga, driver, (By.ID, "as_fmname"), signatory_data.get('father_middle_name', ''))
        safe_send_text(nigga, driver, (By.ID, "as_flname"), signatory_data.get('father_last_name', ''))
        safe_send_text(nigga, driver, (By.ID, "dob"), signatory_data.get('date_of_birth', ''))
        safe_send_text(nigga, driver, (By.ID, "mbno"), signatory_data.get('mobile_number', ''))
        safe_send_text(nigga, driver, (By.ID, "em"), signatory_data.get('email', ''))

        # Gender
        gender = signatory_data.get('gender')
        if gender == "Male":
            safe_click_element(nigga, driver, (By.ID, "radiomale"))
        elif gender == "Female":
            safe_click_element(nigga, driver, (By.ID, "radiofemale"))
        else:
            safe_click_element(nigga, driver, (By.ID, "radiotrans"))
        time.sleep(1)

        # Identity Information
        safe_send_text(nigga, driver, (By.ID, "dg"), signatory_data.get('designation_status', ''))
        safe_send_text(nigga, driver, (By.ID, "din"), signatory_data.get('director_identification_number', ''))

        # Citizenship and PAN/Passport
        is_citizen_of_india = signatory_data.get('is_citizen_of_india', 'Yes')
        
        try:
            citizen_checkbox = driver.find_element(By.ID, "as_cit_ind")
            is_checked = citizen_checkbox.get_attribute("checked") is not None
            
            if is_citizen_of_india == "No":
                # Need to uncheck (set to No)
                if is_checked:
                    safe_click_element(nigga, driver, (By.ID, "as_cit_ind"))
                time.sleep(0.5)
                safe_send_text(nigga, driver, (By.ID, "ppno"), signatory_data.get('passport_number', ''))
            else:
                # Need to check (set to Yes) - this is usually the default
                if not is_checked:
                    safe_click_element(nigga, driver, (By.ID, "as_cit_ind"))
                time.sleep(0.5)
                safe_send_text(nigga, driver, (By.ID, "pan"), signatory_data.get('pan_number', ''))
        except:
            pass  # Silently continue

        # Residential Address
        address_pin = signatory_data.get('pincode_map_search')
        if address_pin:
            try:
                safe_send_text(nigga, driver, (By.ID, "onMapSerachId"), address_pin)
                time.sleep(2)  # Wait for suggestions to load
                
                # Try different XPath patterns for address suggestions
                suggestion_clicked = False
                xpath_patterns = [
                    f"//div[@class='as-results']//li/span[contains(text(),'{address_pin}')]",
                    f"//*[contains(text(),'{address_pin}')]",
                    f"//li[contains(text(),'{address_pin}')]"
                ]
                
                for xpath in xpath_patterns:
                    try:
                        suggestion = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        suggestion.click()
                        suggestion_clicked = True
                        break
                    except TimeoutException:
                        continue
                
                if suggestion_clicked:
                    time.sleep(1)
                    # Try to click confirm button if it exists
                    try:
                        nigga.click_element((By.ID, "confirm-mapquery-btn2"))
                        time.sleep(1)
                    except:
                        pass  # Silently continue
                    
            except:
                pass  # Silently continue
        
        safe_send_text(nigga, driver, (By.ID, "bno"), signatory_data.get('building_flat_door_no', ''))

        # Type of Authorization Dropdown
        auth_type = signatory_data.get('type_of_authorization')
        if auth_type:
            try:
                if auth_type == "Letter of Authorization":
                    nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/fieldset[2]/div/div[2]/div/fieldset/div/select/option[2]"))
                else:
                    nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/fieldset[2]/div/div[2]/div/fieldset/div/select/option[3]"))
            except:
                pass  # Silently continue

        # Document Uploads
        # Photo upload
        try:
                driver.find_element(By.ID,"as_upload_sign").send_keys(signatory_data.get('document_upload1'))
        except:
                pass  # Silently continue

        # Proof of details upload

        try:
                driver.find_element(By.ID,"as_upload_sign").send_keys(signatory_data.get('document_upload2'))
        except:
                pass  # Silently continue

    except (TimeoutException, NoSuchElementException) as e:
        logger.error(f"Element not found or timeout for signatory {signatory_data.get('first_name', 'Unknown')}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred for {signatory_data.get('first_name', 'Unknown')}: {e}")