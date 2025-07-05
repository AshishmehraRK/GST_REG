from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException
from selenium.webdriver.firefox.options import Options
from functions import (
    AutomationHelper,
    debug_file_upload_fields,
    is_element_editable,
    safe_send_text,
    safe_click_element,
    wait_for_page_load,
    wait_for_form_ready,
    wait_for_ajax_complete,
    wait_for_element_stable,
    wait_for_suggestions,
    smart_wait_and_click
)
import time
from logger import logger
import json

# --- Helper functions are now imported from functions.py ---

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
                     wait_for_form_ready(driver)  # Replace time.sleep(2)  # Wait for form to load
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
                wait_for_form_ready(driver)  # Replace time.sleep(2)  # Additional wait for form to clear
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
                wait_for_ajax_complete(driver)  # Replace time.sleep(3)  # Wait for next page to load
            except Exception as e:
                logger.error(f"Could not click the final 'Save & Continue' button: {e}")

    logger.info("Completed authorized signatory details filling process")


def fill_single_signatory_details(driver, nigga, signatory_data):
    """
    Fills the form fields for a single authorized signatory.
    """
    logger.info(f"Filling details for signatory: {signatory_data.get('first_name', '')} {signatory_data.get('last_name', '')}")
    

    
    try:
        # Primary Authorized Signatory Checkbox with robust error handling
        if signatory_data.get('is_primary_signatory') == "Yes":
            logger.info("🔘 Attempting to select Primary Authorized Signatory checkbox...")
            
            # Multi-strategy approach for clicking auth_prim checkbox
            checkbox_clicked = False
            
            # Strategy 1: Wait for overlay to disappear and try normal click
            try:
                # Wait for any dimmer overlays to disappear
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located((By.CLASS_NAME, "dimmer-holder"))
                )
                
                # Wait for checkbox to be clickable
                checkbox = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "auth_prim"))
                )
                checkbox.click()
                logger.info("✅ Primary Signatory checkbox clicked (Strategy 1: Normal click)")
                checkbox_clicked = True
                
            except Exception as e:
                logger.warning(f"⚠️ Strategy 1 failed: {e}")
                
            # Strategy 2: JavaScript click if normal click failed
            if not checkbox_clicked:
                try:
                    checkbox = driver.find_element(By.ID, "auth_prim")
                    driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                    wait_for_element_stable(driver, (By.ID, "auth_prim"))  # Replace time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", checkbox)
                    logger.info("✅ Primary Signatory checkbox clicked (Strategy 2: JavaScript)")
                    checkbox_clicked = True
                    
                except Exception as e:
                    logger.warning(f"⚠️ Strategy 2 failed: {e}")
            
            # Strategy 3: Try alternative selectors
            if not checkbox_clicked:
                alternative_selectors = [
                    "//input[@id='auth_prim']",
                    "//input[@name='auth_prim']",
                    "//input[contains(@class, 'auth')]",
                    "//input[@type='checkbox'][contains(@id, 'auth')]"
                ]
                
                for selector in alternative_selectors:
                    try:
                        checkbox = driver.find_element(By.XPATH, selector)
                        driver.execute_script("arguments[0].click();", checkbox)
                        logger.info(f"✅ Primary Signatory checkbox clicked (Strategy 3: {selector})")
                        checkbox_clicked = True
                        break
                        
                    except Exception as e:
                        logger.debug(f"⚪ Selector {selector} failed: {e}")
                        continue
            
            if checkbox_clicked:
                wait_for_element_stable(driver, (By.ID, "auth_prim"))  # Replace time.sleep(0.5)  # Small delay after successful click
                logger.info("✅ Primary Authorized Signatory status set successfully")
            else:
                logger.warning("⚠️ Could not click Primary Signatory checkbox - continuing anyway")
                
        else:
            logger.info("ℹ️ Not a primary signatory - skipping auth_prim checkbox")

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
        wait_for_element_stable(driver, (By.ID, "radiomale"))  # Replace time.sleep(1)

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
                wait_for_element_stable(driver, (By.ID, "as_cit_ind"))  # Replace time.sleep(0.5)
                safe_send_text(nigga, driver, (By.ID, "ppno"), signatory_data.get('passport_number', ''))
            else:
                # Need to check (set to Yes) - this is usually the default
                if not is_checked:
                    safe_click_element(nigga, driver, (By.ID, "as_cit_ind"))
                wait_for_element_stable(driver, (By.ID, "as_cit_ind"))  # Replace time.sleep(0.5)
                safe_send_text(nigga, driver, (By.ID, "pan"), signatory_data.get('pan_number', ''))
        except:
            pass  # Silently continue

        # Residential Address
        address_pin = signatory_data.get('pincode_map_search')
        if address_pin:
            try:
                safe_send_text(nigga, driver, (By.ID, "onMapSerachId"), address_pin)
                wait_for_suggestions(driver, (By.ID, "onMapSerachId"))  # Replace time.sleep(2)  # Wait for suggestions to load
                
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
                    wait_for_ajax_complete(driver)  # Replace time.sleep(1)
                    # Try to click confirm button if it exists
                    try:
                        nigga.click_element((By.ID, "confirm-mapquery-btn2"))
                        wait_for_element_stable(driver, (By.ID, "confirm-mapquery-btn2"))  # Replace time.sleep(1)
                    except:
                        pass  # Silently continue
                    
            except:
                pass  # Silently continue
        
        safe_send_text(nigga, driver, (By.ID, "bno"), signatory_data.get('building_flat_door_no', ''))

        # Type of Authorization Dropdown
        auth_type = signatory_data.get('type_of_authorization')
        if auth_type:
            logger.info(f"Selecting type of authorization: {auth_type}")
            try:
                # First, locate the dropdown element
                dropdown_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/fieldset[2]/div/div[2]/div/fieldset/div/select"))
                )
                
                # Use Select class for proper dropdown handling
                from selenium.webdriver.support.ui import Select
                select = Select(dropdown_element)
                
                # Select based on authorization type
                if auth_type == "Letter of Authorization":
                    select.select_by_index(1)  # Second option (index 1)
                    logger.info("✓ 'Letter of Authorization' selected")
                else:
                    select.select_by_index(2)  # Third option (index 2)
                    logger.info(f"✓ '{auth_type}' selected")
                    
            except TimeoutException:
                logger.warning("⚠️ Type of Authorization dropdown not found")
            except Exception as e:
                logger.error(f"✗ Failed to select type of authorization: {e}")

        # Document Uploads with proper validation and error handling
        logger.info("📁 Starting document upload process...")
        
        # Photo/Signature upload with validation
        document1 = signatory_data.get('document_upload1')
        if document1:
            logger.info(f"📄 Processing photo/signature document: {document1}")
            
            # File existence validation
            import os
            if not os.path.exists(document1):
                logger.error(f"❌ Photo document file not found: {document1}")
                logger.warning("⚠️ Skipping photo upload - file does not exist")
            elif not os.path.isfile(document1):
                logger.error(f"❌ Photo document path is not a file: {document1}")
                logger.warning("⚠️ Skipping photo upload - path is not a valid file")
            else:
                # File exists, proceed with upload
                logger.info(f"✓ Photo document file validated: {document1}")
                try:
                    photo_upload = driver.find_element(By.ID, "as_upload_sign")
                    photo_upload.send_keys(document1)
                    logger.info("✅ Photo/Signature document uploaded successfully")
                    
                except NoSuchElementException:
                    logger.error("❌ Photo upload field not found (ID: as_upload_sign)")
                    debug_file_upload_fields(driver, logger)
                    
                except ElementNotInteractableException:
                    logger.error("❌ Photo upload field not interactable - may be disabled or hidden")
                    
                except PermissionError:
                    logger.error(f"❌ Permission denied accessing file: {document1}")
                    
                except Exception as upload_error:
                    logger.error(f"❌ Unexpected error during photo upload: {type(upload_error).__name__}: {upload_error}")
        else:
            logger.info("ℹ️ No photo document specified in config - skipping photo upload")

        # Proof document upload with validation and multiple ID attempts
        document2 = signatory_data.get('document_upload2') 
        if document2:
            logger.info(f"📄 Processing proof document: {document2}")
            
            # File existence validation
            import os
            if not os.path.exists(document2):
                logger.error(f"❌ Proof document file not found: {document2}")
                logger.warning("⚠️ Skipping proof upload - file does not exist")
            elif not os.path.isfile(document2):
                logger.error(f"❌ Proof document path is not a file: {document2}")
                logger.warning("⚠️ Skipping proof upload - path is not a valid file")
            else:
                # File exists, proceed with upload attempts
                logger.info(f"✓ Proof document file validated: {document2}")
                upload_success = False
                possible_ids = [
                    "as_upload_sign",
                    "as_upload_proof",
                    "as_upload_doc", 
                    "as_upload_identity",
                    "as_upload_details",
                    "as_upload_2"
                ]
                
                logger.info(f"🔄 Attempting proof upload with {len(possible_ids)} possible field IDs...")
                
                for upload_id in possible_ids:
                    try:
                        proof_upload = driver.find_element(By.ID, upload_id)
                        proof_upload.send_keys(document2)
                        logger.info(f"✅ Proof document uploaded successfully (Field ID: {upload_id})")
                        upload_success = True
                        break
                        
                    except NoSuchElementException:
                        logger.debug(f"⚪ Upload field not found: {upload_id}")
                        continue
                        
                    except ElementNotInteractableException:
                        logger.warning(f"⚠️ Upload field not interactable: {upload_id}")
                        continue
                        
                    except PermissionError:
                        logger.error(f"❌ Permission denied accessing file: {document2}")
                        break  # Don't try other fields if file permission issue
                        
                    except Exception as field_error:
                        logger.warning(f"⚠️ Upload failed with field {upload_id}: {type(field_error).__name__}: {field_error}")
                        continue
                
                # If specific IDs failed, try generic file input approach
                if not upload_success:
                    logger.warning("⚠️ All specific upload field IDs failed. Trying generic file input approach...")
                    debug_file_upload_fields(driver, logger)
                    
                    try:
                        file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
                        if len(file_inputs) > 1:
                            logger.info(f"📋 Found {len(file_inputs)} file input fields, using second one...")
                            file_inputs[1].send_keys(document2)
                            logger.info("✅ Proof document uploaded via generic file input (second field)")
                            upload_success = True
                        else:
                            logger.error(f"❌ Insufficient file input fields found (expected ≥2, found {len(file_inputs)})")
                            
                    except IndexError:
                        logger.error("❌ Index error accessing second file input field")
                        
                    except ElementNotInteractableException:
                        logger.error("❌ Generic file input field not interactable")
                        
                    except Exception as generic_error:
                        logger.error(f"❌ Generic file input approach failed: {type(generic_error).__name__}: {generic_error}")
                
                # Final status logging
                if upload_success:
                    logger.info("🎉 Proof document upload completed successfully")
                else:
                    logger.error("💥 All proof document upload methods failed")
                    logger.warning("⚠️ Continuing automation without proof document upload")
        else:
            logger.info("ℹ️ No proof document specified in config - skipping proof upload")
            
        logger.info("📁 Document upload process completed")

    except (TimeoutException, NoSuchElementException) as e:
        logger.error(f"Element not found or timeout for signatory {signatory_data.get('first_name', 'Unknown')}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred for {signatory_data.get('first_name', 'Unknown')}: {e}")