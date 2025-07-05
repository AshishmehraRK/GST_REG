from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.firefox.options import Options
from functions import (
    AutomationHelper,
    handle_confirmation_dialog,
    wait_for_overlay_to_disappear,
    safe_click,
    safe_fill_field,
    wait_for_page_load,
    wait_for_form_ready,
    wait_for_ajax_complete,
    wait_for_element_stable,
    smart_wait_and_click
)
import time
from logger import logger
import json

# --- Helper functions are now imported from functions.py ---

def fill_promoter_partner_details(driver):
    with open('config.json', 'r') as f:
        config = json.load(f)

    promoters_list = config.get('promoter_partner_details')
    
    # Debug: Show what we found in config
    logger.info(f"🔍 Raw promoter_partner_details from config: {type(promoters_list)} = {promoters_list}")
    
    if not isinstance(promoters_list, list):
        # If it's not a list, wrap it in a list for consistent processing
        logger.info("📝 Converting single promoter to list format")
        promoters_list = [promoters_list]

    nigga = AutomationHelper(driver, logger)

    if not promoters_list:
        logger.error("❌ No 'promoter_partner_details' list found in config.json. Aborting.")
        return
        
    logger.info(f"📋 Processing {len(promoters_list)} promoter(s) total:")
    for idx, promoter in enumerate(promoters_list):
        name = f"{promoter.get('first_name', 'Unknown')} {promoter.get('last_name', 'Unknown')}"
        logger.info(f"   Promoter {idx+1}: {name}")
    
    if len(promoters_list) == 1:
        logger.warning("⚠️  Only 1 promoter found - 'Add New' button will NOT be clicked")
    else:
        logger.info(f"✅ Multiple promoters detected - 'Add New' will be clicked for promoters 2-{len(promoters_list)}")

    for i, promoter_data in enumerate(promoters_list):
        logger.info(f"Processing promoter {i+1}/{len(promoters_list)}: {promoter_data.get('first_name', 'Unknown')} {promoter_data.get('last_name', 'Unknown')}")
        
        # STEP 1: Fill details for current promoter
        fill_single_promoter_details(driver, nigga, logger, promoter_data)
        
        # STEP 2: Check if this is the last promoter
        is_last_promoter = (i == len(promoters_list) - 1)
        
        if not is_last_promoter:
            # More promoters remaining - click "Add New" to prepare for next promoter
            logger.info(f"More promoters remaining. Clicking 'Add New' for promoter {i+1}...")
            try:
                wait_for_overlay_to_disappear(driver)
                
                # Multiple strategies to find and click the "Add New" button
                add_new_clicked = False
                
                # Strategy 1: Use the provided XPath
                logger.info("Strategy 1: Trying provided XPath...")
                try:
                    add_new_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[2]"))
                    )
                    
                    # Check if button is actually visible and enabled
                    if add_new_button.is_displayed() and add_new_button.is_enabled():
                        add_new_button.click()
                        logger.info("✅ Successfully clicked 'Add New' button (Strategy 1)")
                        # Handle confirmation dialog if it appears
                        handle_confirmation_dialog(driver, logger)
                        add_new_clicked = True
                    else:
                        logger.warning("⚠️ Button found but not clickable (hidden or disabled)")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Strategy 1 failed: {e}")
                
                # Strategy 2: Use Angular-specific selectors
                if not add_new_clicked:
                    logger.info("Strategy 2: Trying Angular-specific selectors...")
                    angular_selectors = [
                        "button[data-ng-click=\"addPromoter('savenew')\"]",
                        "button[data-ng-bind='trans.LBL_SAVE_ADDNEW']",
                        "button[title='Add New']"
                    ]
                    
                    for selector in angular_selectors:
                        try:
                            add_new_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            if add_new_button.is_displayed() and add_new_button.is_enabled():
                                add_new_button.click()
                                logger.info(f"✅ Successfully clicked 'Add New' button (Strategy 2: {selector})")
                                # Handle confirmation dialog if it appears
                                handle_confirmation_dialog(driver, logger)
                                add_new_clicked = True
                                break
                        except Exception as e:
                            logger.warning(f"⚠️ Selector {selector} failed: {e}")
                            continue
                
                # Strategy 3: Find by text content
                if not add_new_clicked:
                    logger.info("Strategy 3: Trying to find by text content...")
                    try:
                        buttons = driver.find_elements(By.CSS_SELECTOR, "button.btn.btn-primary")
                        for btn in buttons:
                            if "Add New" in btn.text and btn.is_displayed() and btn.is_enabled():
                                btn.click()
                                logger.info(f"✅ Successfully clicked 'Add New' button (Strategy 3: text match)")
                                # Handle confirmation dialog if it appears
                                handle_confirmation_dialog(driver, logger)
                                add_new_clicked = True
                                break
                    except Exception as e:
                        logger.warning(f"⚠️ Strategy 3 failed: {e}")
                
                # Strategy 4: JavaScript click with debugging
                if not add_new_clicked:
                    logger.info("Strategy 4: Trying JavaScript click with debugging...")
                    try:
                        # First, let's debug what buttons are available
                        buttons = driver.find_elements(By.CSS_SELECTOR, "button")
                        logger.info(f"Found {len(buttons)} buttons on page:")
                        
                        for idx, btn in enumerate(buttons):
                            try:
                                text = btn.text.strip()
                                classes = btn.get_attribute("class") or "no-class"
                                title = btn.get_attribute("title") or "no-title"
                                ng_click = btn.get_attribute("data-ng-click") or "no-ng-click"
                                displayed = btn.is_displayed()
                                enabled = btn.is_enabled()
                                
                                logger.info(f"  Button {idx}: '{text}' | title:'{title}' | class:'{classes}' | ng-click:'{ng_click}' | displayed:{displayed} | enabled:{enabled}")
                                
                                # Try to click if this looks like our button
                                if ("Add New" in text or "Add New" in title) and displayed and enabled:
                                    driver.execute_script("arguments[0].click();", btn)
                                    logger.info(f"✅ Successfully clicked 'Add New' button (Strategy 4: JavaScript on button {idx})")
                                    # Handle confirmation dialog if it appears
                                    handle_confirmation_dialog(driver, logger)
                                    add_new_clicked = True
                                    break
                            except Exception as debug_error:
                                logger.warning(f"⚠️ Error debugging button {idx}: {debug_error}")
                                continue
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Strategy 4 failed: {e}")
                
                # Strategy 5: Force click on the original XPath with JavaScript
                if not add_new_clicked:
                    logger.info("Strategy 5: Force JavaScript click on original XPath...")
                    try:
                        add_new_button = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[2]")
                        driver.execute_script("arguments[0].click();", add_new_button)
                        logger.info("✅ Successfully clicked 'Add New' button (Strategy 5: Force JavaScript)")
                        # Handle confirmation dialog if it appears
                        handle_confirmation_dialog(driver, logger)
                        add_new_clicked = True
                    except Exception as e:
                        logger.warning(f"⚠️ Strategy 5 failed: {e}")
                
                if not add_new_clicked:
                    logger.error(f"❌ All strategies failed to click 'Add New' button after promoter {i+1}")
                    break
                
                # Wait for form to be ready for next promoter
                logger.info("Waiting for form to clear for next promoter...")
                WebDriverWait(driver, 10).until(
                    EC.text_to_be_present_in_element_value((By.ID, "fnm"), "")
                )
                logger.info("✅ Form cleared for next promoter.")
                
            except TimeoutException:
                logger.error(f"Timed out waiting for 'Add New' button or form to clear. Aborting.")
                break
            except Exception as e:
                logger.error(f"Error clicking 'Add New' after promoter {i+1}: {e}. Aborting.")
                break
        
        else:
            # This is the last promoter - click "Save & Continue" to move to next section
            logger.info(f"Last promoter ({i+1}) processed. Clicking 'Save & Continue' to proceed to next section...")
            
            # Try multiple strategies to click the Save & Continue button
            save_continue_clicked = False
            
            # Strategy 1: Try the provided XPath
            try:
                wait_for_overlay_to_disappear(driver)
                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[3]"))
                )
                button.click()
                logger.info(f"✅ Save & Continue clicked for last promoter (Strategy 1)")
                # Handle confirmation dialog if it appears
                handle_confirmation_dialog(driver, logger)
                save_continue_clicked = True
            except Exception as e:
                logger.warning(f"⚠️ Strategy 1 failed for last promoter: {e}")
            
            # Strategy 2: Try alternative button XPaths
            if not save_continue_clicked:
                alternative_xpaths = [
                    "//button[contains(text(), 'Save & Continue')]",
                    "//button[contains(@class, 'btn') and contains(text(), 'Save')]",
                    "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[last()]",
                    "//form//button[contains(text(), 'Continue')]"
                ]
                
                for xpath in alternative_xpaths:
                    try:
                        wait_for_overlay_to_disappear(driver)
                        button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        button.click()
                        logger.info(f"✅ Save & Continue clicked for last promoter (Strategy 2: {xpath})")
                        # Handle confirmation dialog if it appears
                        handle_confirmation_dialog(driver, logger)
                        save_continue_clicked = True
                        break
                    except Exception as e:
                        logger.warning(f"⚠️ Alternative XPath failed: {xpath} - {e}")
            
            # Strategy 3: JavaScript click fallback
            if not save_continue_clicked:
                try:
                    # Try to find any Save/Continue button and click with JavaScript
                    button = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[3]")
                    driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    wait_for_element_stable(driver, (By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[3]"))  # Replace time.sleep(1)
                    driver.execute_script("arguments[0].click();", button)
                    logger.info(f"✅ Save & Continue clicked for last promoter (Strategy 3: JavaScript)")
                    # Handle confirmation dialog if it appears
                    handle_confirmation_dialog(driver, logger)
                    save_continue_clicked = True
                except Exception as e:
                    logger.warning(f"⚠️ JavaScript click also failed: {e}")
            
            # Strategy 4: Debug - List all buttons to understand the structure
            if not save_continue_clicked:
                logger.error(f"❌ All strategies failed for last promoter. Debugging button structure...")
                try:
                    buttons = driver.find_elements(By.XPATH, "//button")
                    logger.info(f"Found {len(buttons)} buttons on the page:")
                    for idx, btn in enumerate(buttons):
                        try:
                            text = btn.text.strip()
                            classes = btn.get_attribute("class")
                            xpath = f"//button[{idx+1}]"
                            logger.info(f"  Button {idx+1}: '{text}' (class: {classes})")
                        except:
                            logger.info(f"  Button {idx+1}: Could not read details")
                    
                    # Try clicking the last button in the form
                    form_buttons = driver.find_elements(By.XPATH, "//form//button")
                    if form_buttons:
                        last_button = form_buttons[-1]
                        driver.execute_script("arguments[0].click();", last_button)
                        logger.info(f"✅ Clicked last form button as fallback")
                        # Handle confirmation dialog if it appears
                        handle_confirmation_dialog(driver, logger)
                        save_continue_clicked = True
                        
                except Exception as debug_error:
                    logger.error(f"❌ Debug attempt failed: {debug_error}")
            
            if save_continue_clicked:
                wait_for_ajax_complete(driver)  # Replace time.sleep(2)  # Wait for the action to complete
                logger.info("✅ Successfully moved to next section after processing all promoters")
            else:
                logger.error(f"❌ Could not click Save & Continue for last promoter - may affect next section")

    logger.info("✅ All promoters processed successfully")

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
                wait_for_ajax_complete(driver)  # Replace time.sleep(2)
                nigga.send_text((By.ID, "onMapSerachId"), address)
                logger.info("✓ Address search field filled")
                safe_click(driver, (By.XPATH, f"//*[text()='{address}']"))
                logger.info("✓ Address suggestion clicked")
                wait_for_element_stable(driver, (By.ID, "confirm-mapquery-btn1"))  # Replace time.sleep(1)
                safe_click(driver, (By.ID, "confirm-mapquery-btn1"))
                logger.info("✓ Address confirmation clicked")
        except Exception as e:
            logger.error(f"✗ Failed to fill address: {e}")


                # Country (Dropdown selection) - Note: ID has a space at the end
        logger.info("Selecting country...")
        try:
            country = promoter_data_item.get('country', 'India')
            # Wait for the dropdown to be present (note the space in ID)
            country_dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "pd_cntry "))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", country_dropdown)
            wait_for_element_stable(driver, (By.ID, "pd_cntry "))  # Replace time.sleep(1)
            
            # Use Select class for proper dropdown handling
            from selenium.webdriver.support.ui import Select
            select = Select(country_dropdown)
            
            # Try to select by value first (IND for India)
            try:
                if country.lower() == 'india':
                    select.select_by_value("IND")
                    logger.info(f"✓ Country 'India' selected by value")
                else:
                    select.select_by_visible_text(country)
                    logger.info(f"✓ Country '{country}' selected by text")
            except:
                # If that fails, ensure India is selected (default)
                try:
                    select.select_by_value("IND")
                    logger.info(f"✓ Country 'India' selected as fallback")
                except:
                    logger.warning(f"⚠️ Country selection failed, using default")
                    
        except Exception as e:
            logger.error(f"✗ Failed to select country: {e}")

        # Step 1: Fill PIN code first to trigger auto-population
        logger.info("Step 1: Filling PIN code to trigger auto-population...")
        pin_filled = safe_fill_field(driver, "pncd", promoter_data_item.get('pincode', ''), "PIN Code")
        wait_for_element_stable(driver, (By.ID, "pncd"))  # Replace time.sleep(2)
        safe_click(driver, (By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/fieldset/div[5]/div[1]/div/div[2]/div/ul/li"))
        
        wait_for_element_stable(driver, (By.ID, "pncd"))  # Replace time.sleep(2)
        if pin_filled:
            # Wait for auto-population to complete
            logger.info("⏳ Waiting for auto-population to complete...")
            wait_for_element_stable(driver, (By.ID, "pncd"))  # Replace time.sleep(3)
            
            # Trigger any change events that might be needed
            try:
                pin_element = driver.find_element(By.ID, "pncd")
                driver.execute_script("arguments[0].blur();", pin_element)
                wait_for_element_stable(driver, (By.ID, "pncd"))  # Replace time.sleep(2)
            except:
                pass
            
            # Step 2: Wait for and verify auto-populated fields
            logger.info("Step 2: Checking auto-populated fields...")
            
            # Check if state got auto-populated
            try:
                state_element = driver.find_element(By.ID, "pd_state")
                state_value = state_element.get_attribute("value")
                if state_value:
                    logger.info(f"✓ State auto-populated: {state_value}")
                else:
                    logger.info("📝 State not auto-populated, filling manually...")
                    safe_fill_field(driver, "pd_state", promoter_data_item.get('state', ''), "State")
            except:
                logger.warning("⚠️ State field not found")
            
            # Check if district got auto-populated
            try:
                district_element = driver.find_element(By.ID, "dst")
                district_value = district_element.get_attribute("value")
                if district_value:
                    logger.info(f"✓ District auto-populated: {district_value}")
                else:
                    logger.info("📝 District not auto-populated, filling manually...")
                    safe_fill_field(driver, "dst", promoter_data_item.get('district', ''), "District")
            except:
                logger.warning("⚠️ District field not found")
            
            # Check if city got auto-populated
            try:
                city_element = driver.find_element(By.ID, "city")
                city_value = city_element.get_attribute("value")
                if city_value:
                    logger.info(f"✓ City auto-populated: {city_value}")
                else:
                    logger.info("📝 City not auto-populated, filling manually...")
                    safe_fill_field(driver, "city", promoter_data_item.get('city', ''), "City/Village")
            except:
                logger.warning("⚠️ City field not found")
            
            # Step 3: Wait a bit more for fields to be enabled
            logger.info("Step 3: Waiting for fields to be enabled...")
            wait_for_element_stable(driver, (By.ID, "pncd"))  # Replace time.sleep(2)
            
            # Step 4: Fill the remaining address fields efficiently
            logger.info("Step 4: Filling remaining address fields...")
            
            # Fill all address fields without individual waits (safe_fill_field handles stability)
            fields_to_fill = [
                ("pd_locality", promoter_data_item.get('locality', ''), "Locality"),
                ("pd_road", promoter_data_item.get('street', ''), "Street/Road"),
                ("pd_bdname", promoter_data_item.get('Building', ''), "Building Name"),
                ("pd_bdnum", promoter_data_item.get('building_flat_door_no', ''), "Building Number"),
                ("pd_flrnum", promoter_data_item.get('floor_number', ''), "Floor Number"),
                ("pd_landmark", promoter_data_item.get('nearby_landmark', ''), "Nearby Landmark")
            ]
            
            filled_count = 0
            for field_id, value, field_name in fields_to_fill:
                if safe_fill_field(driver, field_id, value, field_name):
                    filled_count += 1
            
            # Single wait for form validation/processing after all fields are filled
            if filled_count > 0:
                logger.info(f"✅ Filled {filled_count} address fields, waiting for form validation...")
                try:
                    # Wait for any form validation or processing to complete
                    wait_for_ajax_complete(driver)
                    
                    # Verify critical fields are properly filled and stable
                    critical_fields = ["pd_locality", "pd_road", "pd_bdnum"]
                    for field_id in critical_fields:
                        try:
                            element = driver.find_element(By.ID, field_id)
                            if element.get_attribute("value"):
                                logger.debug(f"✓ {field_id} value confirmed")
                        except:
                            pass  # Field might not exist or be visible
                    
                    logger.info("✅ Address form validation completed")
                except Exception as validation_error:
                    logger.warning(f"⚠️ Form validation wait failed: {validation_error}")
            else:
                logger.info("ℹ️ No address fields filled - skipping validation wait")
        else:
            logger.error("❌ PIN code filling failed, skipping address fields")
            
        logger.info("✅ Address filling process completed")
        
        
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

