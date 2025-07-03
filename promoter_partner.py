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

def safe_fill_field(driver, field_id, value, field_name):
    """Safely fill a form field, handling disabled/readonly states"""
    try:
        if not value:
            logger.info(f"⏭️ Skipping {field_name} - no value provided")
            return True
            
        element = driver.find_element(By.ID, field_id)
        
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)
        
        # Check current value - if already filled (auto-populated), don't override
        current_value = element.get_attribute("value")
        if current_value and current_value.strip():
            logger.info(f"ℹ️ {field_name} already has value '{current_value}' - keeping existing value")
            return True
        
        # Check if element is enabled and editable
        is_enabled = element.is_enabled()
        is_readonly = element.get_attribute("readonly")
        is_disabled = element.get_attribute("disabled")
        
        if not is_enabled or is_readonly or is_disabled:
            logger.warning(f"⚠️ {field_name} field is disabled/readonly - trying JavaScript approach")
            try:
                # Enable the field temporarily and fill it
                driver.execute_script("arguments[0].removeAttribute('disabled');", element)
                driver.execute_script("arguments[0].removeAttribute('readonly');", element)
                driver.execute_script("arguments[0].value = arguments[1];", element, value)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
                driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", element)
                logger.info(f"✓ {field_name} filled via JavaScript (was disabled)")
                return True
            except Exception as js_error:
                logger.warning(f"⚠️ JavaScript fill also failed for {field_name}: {js_error}")
                return False
        else:
            # Normal filling for enabled fields
            try:
                element.clear()
                element.send_keys(value)
                # Trigger events to ensure proper validation
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
                driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", element)
                logger.info(f"✓ {field_name} filled normally")
                return True
            except Exception as fill_error:
                logger.warning(f"⚠️ Normal fill failed for {field_name}, trying JavaScript: {fill_error}")
                try:
                    driver.execute_script("arguments[0].value = arguments[1];", element, value)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", element)
                    logger.info(f"✓ {field_name} filled via JavaScript fallback")
                    return True
                except Exception as js_fallback_error:
                    logger.error(f"✗ All fill methods failed for {field_name}: {js_fallback_error}")
                    return False
            
    except NoSuchElementException:
        logger.warning(f"⚠️ {field_name} field not found (ID: {field_id})")
        return False
    except Exception as e:
        logger.error(f"✗ Failed to fill {field_name}: {e}")
        return False

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
        if i > 0:
            logger.info(f"Adding new promoter {i+1}...")
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
                        add_new_clicked = True
                    except Exception as e:
                        logger.warning(f"⚠️ Strategy 5 failed: {e}")
                
                if not add_new_clicked:
                    logger.error(f"❌ All strategies failed to click 'Add New' button for promoter {i+1}")
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
                logger.error(f"Error clicking 'Add New': {e}. Aborting.")
                break
        
        fill_single_promoter_details(driver, nigga, logger, promoter_data)
        
        # Click Save & Continue after filling each promoter's details
        logger.info(f"Attempting to click Save & Continue for promoter {i+1}...")
        
        # Try multiple strategies to click the Save & Continue button
        save_continue_clicked = False
        
        # Strategy 1: Try the provided XPath
        try:
            wait_for_overlay_to_disappear(driver)
            button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[2]/div/button[3]"))
            )
            button.click()
            logger.info(f"✅ Save & Continue clicked for promoter {i+1} (Strategy 1)")
            save_continue_clicked = True
        except Exception as e:
            logger.warning(f"⚠️ Strategy 1 failed for promoter {i+1}: {e}")
        
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
                    logger.info(f"✅ Save & Continue clicked for promoter {i+1} (Strategy 2: {xpath})")
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
                time.sleep(1)
                driver.execute_script("arguments[0].click();", button)
                logger.info(f"✅ Save & Continue clicked for promoter {i+1} (Strategy 3: JavaScript)")
                save_continue_clicked = True
            except Exception as e:
                logger.warning(f"⚠️ JavaScript click also failed: {e}")
        
        # Strategy 4: Debug - List all buttons to understand the structure
        if not save_continue_clicked:
            logger.error(f"❌ All strategies failed for promoter {i+1}. Debugging button structure...")
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
                    save_continue_clicked = True
                    
            except Exception as debug_error:
                logger.error(f"❌ Debug attempt failed: {debug_error}")
        
        if save_continue_clicked:
            time.sleep(2)  # Wait for the action to complete
        else:
            logger.error(f"❌ Could not click Save & Continue for promoter {i+1} - continuing anyway")

    logger.info("All promoters processed. Clicking final Save & Continue button.")
    
    # Try multiple strategies to find and click the Save & Continue button
    save_continue_clicked = False
    
    # Strategy 1: Try the original XPath
    try:
        wait_for_overlay_to_disappear(driver, 15)
        final_save_continue_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[3]/form/div[2]/div[3]/div/button[3]"))
        )
        final_save_continue_button.click()
        logger.info("✅ Successfully clicked final Save & Continue (Strategy 1)")
        save_continue_clicked = True
    except Exception as e:
        logger.warning(f"⚠️ Strategy 1 failed: {e}")
    
    # Strategy 2: Try alternative button selectors
    if not save_continue_clicked:
        logger.info("Strategy 2: Trying alternative selectors...")
        alternative_selectors = [
            "//button[contains(text(), 'Save & Continue')]",
            "//button[contains(@class, 'btn') and contains(text(), 'Continue')]",
            "//button[contains(@class, 'btn') and contains(text(), 'Save')]",
            "//form//button[last()]",
            "/html/body/div[2]/div/div/div[3]/form//button[contains(text(), 'Continue')]"
        ]
        
        for selector in alternative_selectors:
            try:
                wait_for_overlay_to_disappear(driver, 5)
                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                button.click()
                logger.info(f"✅ Successfully clicked final Save & Continue (Strategy 2: {selector})")
                save_continue_clicked = True
                break
            except Exception as e:
                logger.warning(f"⚠️ Selector {selector} failed: {e}")
                continue
    
    # Strategy 3: Try JavaScript click on any found button
    if not save_continue_clicked:
        logger.info("Strategy 3: Trying JavaScript click on found buttons...")
        try:
            # Find all buttons and look for Save & Continue
            buttons = driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"Found {len(buttons)} buttons on page")
            
            for idx, btn in enumerate(buttons):
                try:
                    text = btn.text.strip()
                    if ("Save" in text and "Continue" in text) or "Continue" in text:
                        logger.info(f"Attempting to click button {idx}: '{text}'")
                        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", btn)
                        logger.info(f"✅ Successfully clicked final Save & Continue (Strategy 3: Button {idx})")
                        save_continue_clicked = True
                        break
                except Exception as btn_error:
                    logger.warning(f"⚠️ Failed to click button {idx}: {btn_error}")
                    continue
        except Exception as e:
            logger.warning(f"⚠️ Strategy 3 failed: {e}")
    
    if not save_continue_clicked:
        logger.error("❌ All strategies failed to click final Save & Continue button")
        logger.error("The automation may not proceed to the next section properly")
    else:
        logger.info("✅ Final Save & Continue button clicked successfully")

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
                time.sleep(2)
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


                # Country (Dropdown selection) - Note: ID has a space at the end
        logger.info("Selecting country...")
        try:
            country = promoter_data_item.get('country', 'India')
            # Wait for the dropdown to be present (note the space in ID)
            country_dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "pd_cntry "))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", country_dropdown)
            time.sleep(1)
            
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
        
        if pin_filled:
            # Wait for auto-population to complete
            logger.info("⏳ Waiting for auto-population to complete...")
            time.sleep(3)
            
            # Trigger any change events that might be needed
            try:
                pin_element = driver.find_element(By.ID, "pncd")
                driver.execute_script("arguments[0].blur();", pin_element)
                time.sleep(2)
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
            time.sleep(2)
            
            # Step 4: Fill the remaining address fields
            logger.info("Step 4: Filling remaining address fields...")
            safe_fill_field(driver, "pd_locality", promoter_data_item.get('locality', ''), "Locality")
            safe_fill_field(driver, "pd_road", promoter_data_item.get('street', ''), "Street/Road")
            safe_fill_field(driver, "pd_bdname", promoter_data_item.get('Building', ''), "Building Name")
            safe_fill_field(driver, "pd_bdnum", promoter_data_item.get('building_flat_door_no', ''), "Building Number")
            safe_fill_field(driver, "pd_flrnum", promoter_data_item.get('floor_number', ''), "Floor Number")
            safe_fill_field(driver, "pd_landmark", promoter_data_item.get('nearby_landmark', ''), "Nearby Landmark")
            
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

