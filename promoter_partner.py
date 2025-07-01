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

def wait_for_overlay_to_disappear(driver, timeout=10):
    """Wait for loading overlays or dimmer elements to disappear"""
    try:
        # Wait for common overlay/dimmer elements to disappear
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".dimmer-holder"))
        )
    except TimeoutException:
        pass  # Continue if overlay doesn't disappear within timeout
    
    try:
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".loading"))
        )
    except TimeoutException:
        pass
    
    try:
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".overlay"))
        )
    except TimeoutException:
        pass

def safe_click(driver, locator, timeout=10):
    """Safely click an element with multiple fallback strategies"""
    try:
        # Wait for overlay to disappear first
        wait_for_overlay_to_disappear(driver)
        
        # Wait for element to be clickable
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        element.click()
        return True
        
    except ElementClickInterceptedException:
        logger.warning(f"Element {locator} is obscured, trying JavaScript click...")
        try:
            element = driver.find_element(*locator)
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            logger.error(f"JavaScript click also failed for {locator}: {e}")
            return False
            
    except TimeoutException:
        logger.error(f"Element {locator} not clickable within {timeout} seconds")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error clicking {locator}: {e}")
        return False

def fill_promoter_partner_details(driver):
    with open('config.json', 'r') as f:
        config = json.load(f)

    promoters_list = config.get('promoter_partner_details')
    if not isinstance(promoters_list, list):
        # If it's not a list, wrap it in a list for consistent processing
        promoters_list = [promoters_list]

    nigga = AutomationHelper(driver, logger)

    if not promoters_list:
        logger.error("No 'promoter_partner_details' list found in config.json. Aborting.")
        return

    for i, promoter_data in enumerate(promoters_list):
        if i > 0:
            logger.info(f"Adding new promoter {i+1}...")
            try:
                wait_for_overlay_to_disappear(driver)
                add_new_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add New')]"))
                )
                add_new_button.click()
                WebDriverWait(driver, 10).until(
                    EC.text_to_be_present_in_element_value((By.ID, "fnm"), "")
                )
                logger.info("Form cleared for next promoter.")

                
            except TimeoutException:
                logger.error(f"Timed out waiting for 'Add New' button or form to clear. Aborting.")
                break
            except Exception as e:
                logger.error(f"Error clicking 'Add New': {e}. Aborting.")
                break
        
        fill_single_promoter_details(driver, nigga, logger, promoter_data)
        
        # Click Save & Continue after filling each promoter's details
        try:
            nigga.click_element((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[3]"))
            logger.info(f"Successfully clicked Save & Continue for promoter {i+1}")
            time.sleep(2)  # Wait for the action to complete
        except Exception as e:
            logger.error(f"Failed to click Save & Continue for promoter {i+1}: {e}")

    logger.info("All promoters processed. Clicking final Save & Continue button.")
    try:
        wait_for_overlay_to_disappear(driver, 15)
        final_save_continue_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[3]/div/button[3]"))
        )
        final_save_continue_button.click()
        logger.info("Successfully clicked final Save & Continue.")
    except ElementClickInterceptedException:
        logger.warning("Save & Continue button obscured, trying JavaScript click...")
        try:
            button = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[3]/div/button[3]")
            driver.execute_script("arguments[0].click();", button)
            logger.info("Successfully clicked final Save & Continue via JavaScript.")
        except Exception as e:
            logger.error(f"JavaScript click also failed: {e}")
    except Exception as e:
        logger.error(f"Could not click the final 'Save & Continue' button: {e}")

def fill_single_promoter_details(driver, nigga, logger, promoter_data_item):
    """Fills the form fields for a single promoter."""
    logger.info(f"Filling details for promoter: {promoter_data_item.get('first_name')} {promoter_data_item.get('last_name')}")
    try:
        # Wait for any overlays to disappear before starting
        wait_for_overlay_to_disappear(driver)
        
        # Personal Information
        logger.info("Filling personal information...")
        try:
            nigga.send_text((By.ID, "fnm"), promoter_data_item.get('first_name', ''))
            logger.info("✓ First name filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill first name: {e}")
            
        try:
            nigga.send_text((By.ID, "pd_mname"), promoter_data_item.get('middle_name', ''))
            logger.info("✓ Middle name filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill middle name: {e}")
            
        try:
            nigga.send_text((By.ID, "pd_lname"), promoter_data_item.get('last_name', ''))
            logger.info("✓ Last name filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill last name: {e}")

        # Father Details
        logger.info("Filling father details...")
        try:
            nigga.send_text((By.ID, "ffname"), promoter_data_item.get('father_first_name', ''))
            logger.info("✓ Father first name filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill father first name: {e}")
            
        try:
            nigga.send_text((By.ID, "pd_fmname"), promoter_data_item.get('father_middle_name', ''))
            logger.info("✓ Father middle name filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill father middle name: {e}")
            
        try:
            nigga.send_text((By.ID, "pd_flname"), promoter_data_item.get('father_last_name', ''))
            logger.info("✓ Father last name filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill father last name: {e}")

        # Additional details
        logger.info("Filling additional personal details...")
        try:
            nigga.send_text((By.ID, "dob"), promoter_data_item.get('date_of_birth', ''))
            logger.info("✓ Date of birth filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill date of birth: {e}")
            
        try:
            nigga.send_text((By.ID, "mbno"), promoter_data_item.get('mobile_number', ''))
            logger.info("✓ Mobile number filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill mobile number: {e}")
            
        try:
            nigga.send_text((By.ID, "pd_email"), promoter_data_item.get('email', ''))
            logger.info("✓ Email filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill email: {e}")

        # Gender - Use safe_click for radio buttons
        logger.info("Selecting gender...")
        gender = promoter_data_item.get('gender')
        try:
            if gender == "Male":
                if not safe_click(driver, (By.CSS_SELECTOR, "div.tbl-format:nth-child(2) > div:nth-child(4) > div:nth-child(1) > div:nth-child(1) > fieldset:nth-child(1) > label:nth-child(3)")):
                    logger.warning("Failed to select Male gender option")
                else:
                    logger.info("✓ Male gender selected")
            elif gender == "Female":
                if not safe_click(driver, (By.CSS_SELECTOR, "div.tbl-format:nth-child(2) > div:nth-child(4) > div:nth-child(1) > div:nth-child(1) > fieldset:nth-child(1) > label:nth-child(5) > span:nth-child(2)")):
                    logger.warning("Failed to select Female gender option")
                else:
                    logger.info("✓ Female gender selected")
            else:
                if not safe_click(driver, (By.CSS_SELECTOR, "div.tbl-format:nth-child(2) > div:nth-child(4) > div:nth-child(1) > div:nth-child(1) > fieldset:nth-child(1) > label:nth-child(7) > span:nth-child(2)")):
                    logger.warning("Failed to select Other gender option")
                else:
                    logger.info("✓ Other gender selected")
        except Exception as e:
            logger.error(f"✗ Failed to select gender: {e}")

        # Professional details
        logger.info("Filling professional details...")
        try:
            nigga.send_text((By.ID, "dg"), promoter_data_item.get('designation_status', ''))
            logger.info("✓ Designation filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill designation: {e}")
            
        try:
            nigga.send_text((By.ID, "din"), promoter_data_item.get('director_identification_number', ''))
            logger.info("✓ Director ID filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill director ID: {e}")

        # Citizenship
        logger.info("Handling citizenship details...")
        try:
            citizen_of_india = promoter_data_item.get('is_citizen_of_india', 'Yes')
            if citizen_of_india == "No":
                safe_click(driver, (By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/fieldset/div[2]/div[1]/div/div[3]/label"))
                nigga.send_text((By.ID, "ppno"), promoter_data_item.get('passport_number', ''))
                logger.info("✓ Non-Indian citizen details filled")
            else:
                nigga.send_text((By.ID, "pan"), promoter_data_item.get('pan_number', ''))
                logger.info("✓ PAN number filled")
        except Exception as e:
            logger.error(f"✗ Failed to handle citizenship details: {e}")

        # Address
        logger.info("Filling address details...")
        try:
            address = promoter_data_item.get('pincode_map_search', '')
            if address:
                nigga.send_text((By.ID, "onMapSerachId"), address)
                logger.info("✓ Address search field filled")
                time.sleep(2)  # Wait for suggestions to load
                safe_click(driver, (By.XPATH, f"//*[text()='{address}']"))
                logger.info("✓ Address suggestion clicked")
                time.sleep(2)
                safe_click(driver, (By.ID, "confirm-mapquery-btn1"))
                logger.info("✓ Address confirmation clicked")
        except Exception as e:
            logger.error(f"✗ Failed to fill address: {e}")

        # Building number
        logger.info("Filling building details...")
        try:
            nigga.send_text((By.ID, "pd_bdnum"), promoter_data_item.get('building_flat_door_no', ''))
            logger.info("✓ Building number filled")
        except Exception as e:
            logger.error(f"✗ Failed to fill building number: {e}")
        
        # Document upload
        logger.info("Uploading document...")
        try:
            upload_image = promoter_data_item.get('document_upload', '')
            if upload_image:
                nigga.send_text((By.ID, "pd_upload"), upload_image)
                logger.info("✓ Document uploaded")
        except Exception as e:
            logger.error(f"✗ Failed to upload document: {e}")
            
        # Authorized signatory checkbox
        logger.info("Handling authorized signatory option...")
        try:
            if promoter_data_item.get('is_also_authorized_signatory') == "Yes":
                safe_click(driver, (By.CSS_SELECTOR, "div.tbl-format:nth-child(13) > div:nth-child(1) > div:nth-child(1) > label:nth-child(1)"))
                logger.info("✓ Authorized signatory option selected")
        except Exception as e:
            logger.error(f"✗ Failed to select authorized signatory option: {e}")

        logger.info(f"Successfully completed filling details for {promoter_data_item.get('first_name')} {promoter_data_item.get('last_name')}")

    except (TimeoutException, NoSuchElementException) as e:
        logger.error(f"An error occurred while filling details for {promoter_data_item.get('first_name')}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred for {promoter_data_item.get('first_name')}: {e}")

