import time
import os
import requests
import logging
import base64
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
    NoSuchElementException
)
import platform
import subprocess
import time
from config import ELEMENTS
from logger import logger
from typing import Callable, Tuple, Optional, Any

# --- Environment Variables for APIs ---
from dotenv import load_dotenv
load_dotenv()
TRUECAPTCHA_USER = os.getenv('TRUECAPTCHA_USER')
TRUECAPTCHA_KEY = os.getenv('TRUECAPTCHA_KEY')
OTP_SERVER_URL = "http://127.0.0.1:3000"

# --- Custom Exceptions for Clear Error Handling ---
class AutomationError(Exception):
    pass

class VerificationStepFailed(AutomationError):
    pass

# --- Helper Functions for Safe UI Interactions ---

def safe_checkbox_click(driver, checkbox_id, description="checkbox"):
    """
    Safely click a checkbox while handling dimmer overlay issues
    """
    try:
        # Wait for any dimmer to disappear first
        wait = WebDriverWait(driver, 15)
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "dimmer-holder")))
        
        # Wait for checkbox to be clickable
        checkbox = wait.until(EC.element_to_be_clickable((By.ID, checkbox_id)))
        checkbox.click()
        logger.info(f"{description} ({checkbox_id}) clicked successfully")
        return True
        
    except (TimeoutException, Exception) as e:
        logger.warning(f"Normal {description} click failed, trying JavaScript click: {e}")
        try:
            # Fallback: JavaScript click
            checkbox = driver.find_element(By.ID, checkbox_id)
            driver.execute_script("arguments[0].click();", checkbox)
            logger.info(f"{description} ({checkbox_id}) clicked with JavaScript")
            return True
        except Exception as js_error:
            logger.error(f"All {description} click methods failed: {js_error}")
            return False

def handle_confirmation_dialog(driver, logger, timeout=10):
    """
    Handle confirmation dialogs that appear after clicking buttons.
    Clicks the Cancel button to dismiss the dialog.
    Returns True if dialog was handled, False if no dialog appeared.
    """
    try:
        # Wait for the confirmation dialog to appear
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="confirmDialogue_cancel_btn"]'))
        )
        
        # Click Cancel button to dismiss the dialog
        logger.info("🔄 Confirmation dialog detected, clicking Cancel...")
        cancel_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="confirmDialogue_cancel_btn"]'))
        )
        cancel_button.click()
        logger.info("✅ Confirmation dialog dismissed by clicking Cancel")
        
        # Wait for dialog to disappear
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.XPATH, '//*[@id="confirmDialogue_cancel_btn"]'))
        )
        
        return True
        
    except TimeoutException:
        # If no dialog appears within timeout, it's not an error
        logger.info("ℹ️ No confirmation dialog appeared")
        return False
    except Exception as e:
        logger.warning(f"⚠️ Error handling confirmation dialog: {e}")
        return False

def safe_click_with_dimmer_wait(driver, xpath, description="button", handle_dialog=True):
    """
    Safely click a button while handling dimmer overlay issues and confirmation dialogs
    """
    try:
        # Wait for any dimmer to disappear
        wait = WebDriverWait(driver, 15)
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "dimmer-holder")))
        
        # Now try to click the button
        button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        button.click()
        logger.info(f"{description} clicked successfully")
        
        # Handle confirmation dialog if it appears
        if handle_dialog:
            handle_confirmation_dialog(driver, logger)
        
        return True
        
    except (TimeoutException, Exception) as e:
        logger.warning(f"Normal click failed for {description}, trying JavaScript click: {e}")
        # Fallback: Use JavaScript click to bypass the overlay
        try:
            button = driver.find_element(By.XPATH, xpath)
            driver.execute_script("arguments[0].click();", button)
            logger.info(f"{description} clicked with JavaScript")
            
            # Handle confirmation dialog if it appears
            if handle_dialog:
                handle_confirmation_dialog(driver, logger)
            
            return True
        except Exception as js_error:
            logger.error(f"All click methods failed for {description}: {js_error}")
            return False

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
    """Safely fill a field only if it has a value, with enhanced error handling and logging"""
    try:
        if not value or str(value).strip() == "":
            logger.info(f"⏭️ Skipping {field_name} - no value provided")
            return True
            
        element = driver.find_element(By.ID, field_id)
        
        # Scroll element into view and wait for it to be stable
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        # Wait for element to be stable after scrolling instead of arbitrary sleep
        WebDriverWait(driver, 5).until(
            lambda d: d.find_element(By.ID, field_id).is_displayed()
        )
        
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

def debug_file_upload_fields(driver, logger):
    """Debug function to identify available file upload fields on the page"""
    try:
        logger.info("🔍 Debugging file upload fields...")
        file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
        
        if file_inputs:
            logger.info(f"Found {len(file_inputs)} file input field(s):")
            for i, file_input in enumerate(file_inputs):
                try:
                    input_id = file_input.get_attribute("id") or "no-id"
                    input_name = file_input.get_attribute("name") or "no-name"
                    input_class = file_input.get_attribute("class") or "no-class"
                    is_displayed = file_input.is_displayed()
                    is_enabled = file_input.is_enabled()
                    
                    logger.info(f"  File Input {i+1}: ID='{input_id}', Name='{input_name}', Class='{input_class}', Visible={is_displayed}, Enabled={is_enabled}")
                except Exception as e:
                    logger.warning(f"  File Input {i+1}: Could not read attributes - {e}")
        else:
            logger.warning("⚠️ No file input fields found on the page")
            
    except Exception as e:
        logger.error(f"✗ Error debugging file upload fields: {e}")

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

# --- End of Helper Functions ---

# --- Advanced WebDriverWait Helper Functions to Replace time.sleep() ---

def wait_for_page_load(driver, timeout=30):
    """Wait for page to fully load using document.readyState and absence of loading indicators"""
    try:
        # Wait for document to be ready
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Wait for any loading overlays to disappear
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "dimmer-holder"))
        )
        
        # Wait for common loading indicators to disappear
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".loading, .spinner, .loader"))
        )
        
        logger.info("✅ Page fully loaded")
        return True
        
    except TimeoutException:
        logger.warning("⚠️ Page load timeout - continuing anyway")
        return False

def wait_for_element_stable(driver, locator, timeout=10):
    """Wait for element to be present, visible, and stable (not moving/changing)"""
    try:
        # Wait for element to be present
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        
        # Wait for element to be visible
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located(locator)
        )
        
        # Enhanced stability check - wait for element position to stabilize
        max_stability_checks = 3
        stable_count = 0
        
        previous_location = element.location
        previous_size = element.size
        
        for check in range(max_stability_checks):
            try:
                # Use WebDriverWait with a very short timeout instead of time.sleep
                WebDriverWait(driver, 0.2).until(
                    lambda d: d.find_element(*locator).is_displayed()
                )
                
                current_element = driver.find_element(*locator)
                current_location = current_element.location
                current_size = current_element.size
                
                # Check if position and size are stable
                if (current_location == previous_location and 
                    current_size == previous_size and
                    current_element.is_displayed() and
                    current_element.is_enabled()):
                    stable_count += 1
                    if stable_count >= 2:  # Require 2 consecutive stable checks
                        logger.debug(f"✅ Element {locator} is stable and ready")
                        return current_element
                else:
                    stable_count = 0  # Reset if element changed
                    
                previous_location = current_location
                previous_size = current_size
                
            except (StaleElementReferenceException, NoSuchElementException):
                # Element is still changing, wait a bit more
                logger.debug(f"⚠️ Element {locator} still changing, continuing stability check...")
                stable_count = 0
                try:
                    element = driver.find_element(*locator)
                    previous_location = element.location
                    previous_size = element.size
                except:
                    pass
        
        # If we get here, element might still be moving but we'll return it anyway
        logger.debug(f"⚠️ Element {locator} stability check completed (may still be moving)")
        return driver.find_element(*locator)
            
    except TimeoutException:
        logger.warning(f"⚠️ Element {locator} not stable within {timeout}s")
        return None

def wait_for_form_ready(driver, form_identifier=None, timeout=15):
    """Wait for form to be ready for input (no disabled state, overlays gone)"""
    try:
        # Wait for page to be ready
        wait_for_page_load(driver, timeout//3)
        
        # If specific form identifier provided, wait for it
        if form_identifier:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(form_identifier)
            )
        
        # Wait for common form loading states to complete
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".form-loading, .form-disabled"))
        )
        
        # Wait for Angular/React forms to initialize (if applicable)
        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return (typeof angular !== 'undefined' ? angular.element(document).injector().get('$http').pendingRequests.length === 0 : true)")
            )
        except:
            pass  # Not an Angular app or different setup
        
        logger.info("✅ Form ready for input")
        return True
        
    except TimeoutException:
        logger.warning(f"⚠️ Form not ready within {timeout}s - continuing anyway")
        return False

def wait_for_dropdown_options(driver, dropdown_locator, timeout=10):
    """Wait for dropdown options to populate"""
    try:
        # Wait for dropdown to be present
        dropdown = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(dropdown_locator)
        )
        
        # Wait for options to be populated (more than just empty/default option)
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, f"{dropdown_locator[1]} option")) > 1
        )
        
        logger.info(f"✅ Dropdown {dropdown_locator} options loaded")
        return True
        
    except TimeoutException:
        logger.warning(f"⚠️ Dropdown {dropdown_locator} options not loaded within {timeout}s")
        return False

def wait_for_suggestions(driver, input_locator, timeout=10):
    """Wait for autocomplete/suggestion dropdown to appear"""
    try:
        # First trigger the input to ensure suggestions appear
        input_element = driver.find_element(*input_locator)
        input_element.click()
        
        # Wait for suggestion container to appear
        suggestion_selectors = [
            ".suggestions", ".autocomplete", ".dropdown-menu", 
            ".search-results", ".typeahead", "[role='listbox']"
        ]
        
        for selector in suggestion_selectors:
            try:
                WebDriverWait(driver, timeout//len(suggestion_selectors)).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                logger.info(f"✅ Suggestions appeared for {input_locator}")
                return True
            except TimeoutException:
                continue
        
        logger.warning(f"⚠️ No suggestions found for {input_locator}")
        return False
        
    except Exception as e:
        logger.warning(f"⚠️ Error waiting for suggestions: {e}")
        return False

def wait_for_navigation(driver, expected_url_part=None, timeout=30):
    """Wait for page navigation to complete"""
    try:
        if expected_url_part:
            # Wait for URL to contain expected part
            WebDriverWait(driver, timeout).until(
                EC.url_contains(expected_url_part)
            )
            logger.info(f"✅ Navigated to page containing '{expected_url_part}'")
        else:
            # Just wait for any navigation (URL change)
            current_url = driver.current_url
            WebDriverWait(driver, timeout).until(
                lambda d: d.current_url != current_url
            )
            logger.info(f"✅ Navigation completed to {driver.current_url}")
        
        # Wait for new page to load
        wait_for_page_load(driver, timeout//2)
        return True
        
    except TimeoutException:
        logger.warning(f"⚠️ Navigation timeout after {timeout}s")
        return False

def wait_for_ajax_complete(driver, timeout=15):
    """Wait for AJAX/XHR requests to complete"""
    try:
        # Wait for jQuery AJAX if jQuery is present
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return typeof jQuery !== 'undefined' ? jQuery.active === 0 : true")
            )
        except:
            pass
        
        # Wait for Angular HTTP requests if Angular is present
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return typeof angular !== 'undefined' ? angular.element(document).injector().get('$http').pendingRequests.length === 0 : true")
            )
        except:
            pass
        
        # Wait for fetch requests to complete (modern browsers)
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return window.performance.getEntriesByType('navigation')[0].loadEventEnd > 0")
            )
        except:
            pass
        
        logger.info("✅ AJAX requests completed")
        return True
        
    except TimeoutException:
        logger.warning(f"⚠️ AJAX completion timeout after {timeout}s")
        return False

def wait_for_button_clickable(driver, button_locator, timeout=15):
    """Wait for button to be clickable and not disabled"""
    try:
        # Wait for button to be present and visible
        button = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located(button_locator)
        )
        
        # Wait for button to be enabled (not disabled)
        WebDriverWait(driver, timeout).until(
            lambda d: not d.find_element(*button_locator).get_attribute("disabled")
        )
        
        # Wait for button to be clickable
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(button_locator)
        )
        
        logger.info(f"✅ Button {button_locator} is clickable")
        return True
        
    except TimeoutException:
        logger.warning(f"⚠️ Button {button_locator} not clickable within {timeout}s")
        return False

def smart_wait_and_click(driver, locator, description="element", timeout=15):
    """Enhanced click function that waits for optimal conditions"""
    try:
        # Wait for overlays to disappear
        wait_for_overlay_to_disappear(driver, 5)
        
        # Wait for element to be stable and clickable
        wait_for_element_stable(driver, locator, timeout//2)
        
        # Wait for button to be clickable
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        
        # Small stability wait
        WebDriverWait(driver, 2).until(
            lambda d: d.find_element(*locator).is_displayed()
        )
        
        # Attempt click
        element.click()
        logger.info(f"✅ Successfully clicked {description}")
        return True
        
    except TimeoutException:
        logger.warning(f"⚠️ Smart click timeout for {description}, trying JavaScript click")
        try:
            element = driver.find_element(*locator)
            driver.execute_script("arguments[0].click();", element)
            logger.info(f"✅ JavaScript click successful for {description}")
            return True
        except Exception as e:
            logger.error(f"❌ All click methods failed for {description}: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ Smart click failed for {description}: {e}")
        return False

def smart_wait_and_send_keys(driver, locator, text, description="field", timeout=15):
    """Enhanced text input function that waits for optimal conditions"""
    try:
        # Wait for form to be ready
        wait_for_form_ready(driver, timeout=timeout//2)
        
        # Wait for element to be present and interactable
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        
        # Clear and input text
        element.clear()
        element.send_keys(text)
        
        # Trigger events for frameworks
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
        
        logger.info(f"✅ Successfully entered text in {description}")
        return True
        
    except TimeoutException:
        logger.warning(f"⚠️ Smart text input timeout for {description}")
        return False
    except Exception as e:
        logger.error(f"❌ Smart text input failed for {description}: {e}")
        return False

# --- End of Advanced WebDriverWait Helper Functions ---

def safe_dropdown_select(driver, dropdown_locator, option_text, description="dropdown", timeout=15):
    """Safely select dropdown option with overlay protection and proper Select class usage"""
    from selenium.webdriver.support.ui import Select
    
    try:
        logger.info(f"🔽 Attempting to select '{option_text}' from {description}")
        
        # Step 1: Wait for any overlays to disappear
        wait_for_overlay_to_disappear(driver, timeout=10)
        
        # Step 2: Wait for dropdown to be present and clickable
        if isinstance(dropdown_locator, str):
            # If it's an XPath string, convert to tuple
            locator = (By.XPATH, dropdown_locator)
        else:
            locator = dropdown_locator
            
        dropdown_element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        
        # Step 3: Scroll into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_element)
        
        # Step 4: Wait for element to be stable
        wait_for_element_stable(driver, locator, timeout=5)
        
        # Step 5: Use Select class for proper dropdown handling
        select = Select(dropdown_element)
        
        # Try to select by visible text
        try:
            select.select_by_visible_text(option_text)
            logger.info(f"✅ Successfully selected '{option_text}' from {description}")
            return True
            
        except NoSuchElementException:
            # If exact text doesn't work, try partial match
            logger.warning(f"⚠️ Exact text match failed, trying partial match for '{option_text}'")
            options = select.options
            for option in options:
                if option_text.lower() in option.text.lower():
                    option.click()
                    logger.info(f"✅ Successfully selected '{option.text}' (partial match) from {description}")
                    return True
            
            logger.error(f"❌ No option found containing '{option_text}' in {description}")
            logger.info(f"Available options: {[opt.text for opt in options]}")
            return False
        
    except TimeoutException:
        logger.warning(f"⚠️ Dropdown {description} not ready, trying JavaScript approach")
        try:
            # Fallback: Try JavaScript approach
            element = driver.find_element(*locator)
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            wait_for_ajax_complete(driver, 3)
            
            # Try clicking the dropdown first to open it
            driver.execute_script("arguments[0].click();", element)
            wait_for_ajax_complete(driver, 2)
            
            # Then try to find and click the option
            option_xpath = f"//option[contains(text(), '{option_text}')]"
            option_element = driver.find_element(By.XPATH, option_xpath)
            driver.execute_script("arguments[0].click();", option_element)
            
            logger.info(f"✅ JavaScript fallback successful for {description}")
            return True
            
        except Exception as js_error:
            logger.error(f"❌ JavaScript fallback also failed for {description}: {js_error}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Unexpected error selecting from {description}: {e}")
        return False

class AutomationHelper:
    def __init__(self, driver: WebDriver, logger: logging.Logger, default_timeout: int = 30, default_retries: int = 5):
        self.driver = driver
        self.logger = logger
        self.default_timeout = default_timeout
        self.default_retries = default_retries
        self.task: Optional[Any] = None

    def wait_for_document_ready(self):
        WebDriverWait(self.driver, self.default_timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        self.logger.info("Document is in 'complete' ready state.")

    def set_task(self, task: Any):
        self.task = task

    def _update_task_state(self, status: str):
        if self.task:
            # Assuming self.task.request.id is still valid and not tied directly to a 'job_id' parameter
            self.task.update_state(state='PROGRESS', meta={'status': status})
            self.logger.info(f"Task {self.task.request.id}: Status updated to '{status}'")

    def _save_screenshot_on_error(self, step_name: str):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"error_{step_name}_{timestamp}.png"
        try:
            self.driver.save_screenshot(filename)
            self.logger.info(f"Saved error screenshot to: {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save screenshot: {e}")

    def wait_for_element_visible(self, locator: Tuple[str, str], timeout: Optional[int] = None):
        self.wait_for_document_ready()
        wait_time = timeout if timeout is not None else self.default_timeout
        try:
            self.logger.info(f"Waiting for element {locator} to be visible...")
            WebDriverWait(self.driver, wait_time).until(
                EC.visibility_of_element_located(locator)
            )
            self.logger.info(f"Element {locator} is now visible.")
        except TimeoutException:
            self.logger.error(f"Synchronization failed: Element {locator} did not become visible within {wait_time}s.")
            raise

    def send_text(self, locator: Tuple[str, str], keys: str, clear_first: bool = True, timeout: Optional[int] = None):
        self.wait_for_document_ready()
        wait_time = timeout if timeout is not None else self.default_timeout
        for attempt in range(self.default_retries):
            try:
                element = WebDriverWait(self.driver, wait_time).until(
                    EC.visibility_of_element_located(locator)
                )
                if clear_first:
                    element.clear()
                element.send_keys(keys)
                self.logger.info(f"Successfully sent text to {locator}.")
                return
            except StaleElementReferenceException:
                self.logger.warning(f"Stale element on send_text to {locator}, attempt {attempt + 1}.")
                # Wait for element to become stable again instead of arbitrary sleep
                try:
                    WebDriverWait(self.driver, 2).until(
                        EC.visibility_of_element_located(locator)
                    )
                except TimeoutException:
                    pass  # Element might still be stale, will retry in next iteration
            except TimeoutException:
                self.logger.error(f"Element {locator} not visible within {wait_time}s.")
                break
        raise ElementNotInteractableException(f"Failed to send text to {locator} after {self.default_retries} retries.")

    def click_element(self, locator: Tuple[str, str], timeout: Optional[int] = None):
        self.wait_for_document_ready()
        wait_time = timeout if timeout is not None else self.default_timeout
        for attempt in range(self.default_retries):
            try:
                element = WebDriverWait(self.driver, wait_time).until(
                    EC.element_to_be_clickable(locator)
                )
                try:
                    element.click()
                except ElementNotInteractableException:
                    self.driver.execute_script("arguments[0].click();", element)
                self.logger.info(f"Successfully clicked {locator}.")
                return
            except StaleElementReferenceException:
                self.logger.warning(f"Stale element on click_element {locator}, attempt {attempt + 1}.")
                # Wait for element to become clickable again instead of arbitrary sleep
                try:
                    WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable(locator)
                    )
                except TimeoutException:
                    pass  # Element might still be stale, will retry in next iteration
            except TimeoutException:
                self.logger.error(f"Element {locator} not clickable within {wait_time}s.")
                break
        raise ElementNotInteractableException(f"Failed to click {locator} after {self.default_retries} retries.")

    def _execute_verification_step(self, step_name: str, action_callable: Callable, submit_callable: Callable, success_condition: Callable, failure_condition: Callable, recovery_callable: Optional[Callable] = None, max_retries: int = 10, wait_timeout: int = 10):
        num_retries = max_retries if max_retries is not None else self.default_retries
        for attempt in range(num_retries):
            self.logger.info(f"--- Starting {step_name}: Attempt {attempt + 1}/{num_retries} ---")
            try:
                if attempt > 0 and recovery_callable:
                    self.logger.info(f"Performing recovery action for {step_name}...")
                    recovery_callable()
                action_callable()
                submit_callable()
                wait = WebDriverWait(self.driver, wait_timeout)
                wait.until(EC.any_of(success_condition, failure_condition))
                try:
                    WebDriverWait(self.driver, 0.1).until(success_condition)
                    self.logger.info(f"SUCCESS: {step_name} completed successfully on attempt {attempt + 1}.")
                    return
                except TimeoutException:
                    self.logger.warning(f"FAILURE: {step_name} failed on attempt {attempt + 1}. Retrying...")
            except Exception as e:
                self.logger.warning(f"Caught exception during {step_name} attempt {attempt + 1}: {type(e).__name__}. Retrying...")
            
            # Wait for page to be ready before retrying instead of arbitrary sleep
            if attempt < num_retries - 1:  # Don't wait after the last attempt
                try:
                    # Wait for document to be ready and any ongoing processes to complete
                    WebDriverWait(self.driver, 3).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    # Also wait for any AJAX calls to complete
                    try:
                        WebDriverWait(self.driver, 2).until(
                            lambda d: d.execute_script("return typeof jQuery !== 'undefined' ? jQuery.active === 0 : true")
                        )
                    except:
                        pass  # jQuery might not be available
                except TimeoutException:
                    pass  # Continue anyway if document doesn't stabilize
        
        self.logger.critical(f"FINAL FAILURE: {step_name} failed after {num_retries} attempts.")
        self._save_screenshot_on_error(step_name)
        raise VerificationStepFailed(f"{step_name} could not be completed after {num_retries} attempts.")

    def solve_and_enter_captcha(self):
        self.wait_for_document_ready()
        self.logger.info("Solving captcha via TrueCaptcha API...")

        if not TRUECAPTCHA_USER or not TRUECAPTCHA_KEY:
            raise AutomationError("TrueCaptcha credentials (TRUECAPTCHA_USER, TRUECAPTCHA_KEY) are missing. Please ensure they are loaded.")

        try:
            # Locate the CAPTCHA image using its specific ID from the HTML
            # HTML: <img id="imgCaptcha" ...>
            captcha_element = WebDriverWait(self.driver, self.default_timeout).until(
                EC.presence_of_element_located((By.ID, "imgCaptcha"))
            )
            self.logger.info(f"Found captcha image element with ID 'imgCaptcha'.")

            # Take screenshot of the captcha element
            encoded_string = captcha_element.screenshot_as_base64

            # Send to TrueCaptcha API
            response = requests.post(
                'https://api.apitruecaptcha.org/one/gettext',
                json={'userid': TRUECAPTCHA_USER, 'apikey': TRUECAPTCHA_KEY, 'data': encoded_string, 'numeric': True, 'mode': 'human'},
                timeout=70 # API call timeout
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            result = response.json()

            captcha_text = ""
            if 'result' in result and result['result']:
                captcha_text = result['result'].strip()
                self.logger.info(f"CAPTCHA solved by API: {captcha_text}")
            else:
                raise AutomationError(f"Failed to get CAPTCHA result from API. Response: {result}")

            # Enter the solved CAPTCHA text using its specific ID from the HTML
            # HTML: <input ... id="captcha" name="captcha" ...>
            self.send_text(locator=(By.ID, "captcha"), keys=captcha_text)
            self.logger.info("CAPTCHA text entered successfully.")

        except requests.exceptions.RequestException as req_err:
            raise AutomationError(f"Network or API error during captcha verification: {req_err}")
        except TimeoutException as te:
            # Capture the element not found case specifically
            raise AutomationError(f"CAPTCHA image or input field not found within timeout: {te}")
        except Exception as e:
            # Catch any other unexpected errors
            raise AutomationError(f"An unexpected error occurred during captcha solving and entry: {e}")

    def poll_for_otp(self, otp_type: str, timeout: int = 120, poll_interval: int = 3) -> str:
        self.wait_for_document_ready()
        self._update_task_state(f"awaiting_{otp_type}")
        self.logger.info(f"Polling for {otp_type} from OTP server (timeout: {timeout}s)...")
        start_time = time.time()
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while time.time() - start_time < timeout:
            try:
                url = f"{OTP_SERVER_URL}/get-otp?type={otp_type}"
                response = requests.get(url, timeout=5)

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    otp_value = data.get("otp")
                    if otp_value:
                        self.logger.info(f"OTP '{otp_value}' received for type '{otp_type}'!")
                        return otp_value
                    consecutive_failures = 0  # Reset failure count on successful connection
                else:
                    consecutive_failures += 1
                    
            except requests.exceptions.RequestException:
                consecutive_failures += 1
                self.logger.warning(f"Could not connect to OTP server. Retrying... (failure #{consecutive_failures})")
            
            # Adaptive wait time - increase interval if there are consecutive failures
            current_interval = poll_interval
            if consecutive_failures >= max_consecutive_failures:
                current_interval = min(poll_interval * 2, 10)  # Cap at 10 seconds
                self.logger.info(f"Increasing poll interval to {current_interval}s due to connection issues")
            
            # Use WebDriverWait-based approach instead of time.sleep for better integration
            end_wait_time = time.time() + current_interval
            while time.time() < end_wait_time:
                try:
                    # Check if browser is still alive during waiting
                    self.driver.current_url  # This will throw if browser is closed
                    # Short wait increment to allow for interruption
                    remaining_wait = end_wait_time - time.time()
                    if remaining_wait > 0:
                        wait_increment = min(0.5, remaining_wait)
                        try:
                            WebDriverWait(self.driver, wait_increment).until(
                                lambda d: False  # This will always timeout, giving us controlled wait
                            )
                        except TimeoutException:
                            pass  # Expected timeout for our wait mechanism
                except Exception:
                    # Browser might be closed or in bad state
                    self.logger.warning("Browser connection lost during OTP polling")
                    break
                    
        raise TimeoutException(f"Timed out waiting for {otp_type} from local server.")

    def handle_initial_captcha(self):
        self.wait_for_document_ready()
        self.logger.info("Solving captcha via TrueCaptcha API...")

        if not TRUECAPTCHA_USER or not TRUECAPTCHA_KEY:
            raise AutomationError("TrueCaptcha credentials (TRUECAPTCHA_USER, TRUECAPTCHA_KEY) are missing.")

        try:
            # Wait for CAPTCHA image to be visible
            captcha_element = WebDriverWait(self.driver, self.default_timeout).until(
                EC.visibility_of_element_located((By.ID, "imgCaptcha"))
            )
            self.logger.info("Found visible CAPTCHA image with ID 'imgCaptcha'.")

            # Screenshot as base64
            encoded_string = captcha_element.screenshot_as_base64

            # Solve CAPTCHA using API
            response = requests.post(
                'https://api.apitruecaptcha.org/one/gettext',
                json={
                    'userid': TRUECAPTCHA_USER,
                    'apikey': TRUECAPTCHA_KEY,
                    'data': encoded_string,
                    'numeric': True,
                    'mode': 'human'
                },
                timeout=70
            )
            response.raise_for_status()
            result = response.json()

            if 'result' not in result or not result['result']:
                raise AutomationError(f"Invalid CAPTCHA API response: {result}")

            captcha_text = result['result'].strip()
            self.logger.info(f"CAPTCHA solved: {captcha_text}")

            # Wait for the input field with ID 'captchatrn' to be ready
            input_element = WebDriverWait(self.driver, self.default_timeout).until(
                EC.element_to_be_clickable((By.ID, "captchatrn"))
            )
            self.send_text(locator=(By.ID, "captchatrn"), keys=captcha_text)
            self.logger.info("CAPTCHA entered successfully into input with ID 'captchatrn'.")

        except requests.exceptions.RequestException as req_err:
            raise AutomationError(f"Network/API error while solving CAPTCHA: {req_err}")
        except TimeoutException as te:
            raise AutomationError(f"CAPTCHA image or input not found or not visible within timeout: {te}")
        except Exception as e:
            raise AutomationError(f"Unexpected error during CAPTCHA handling: {e}")

    def handle_mobile_otp(self, **kwargs):
        self.logger.info("Starting Mobile OTP verification step...")

        self._execute_verification_step(
            step_name="Mobile OTP",

            action_callable=lambda: self.send_text(
                locator=(By.ID, "mobile_otp"),
                keys=self.poll_for_otp("mobile_otp")  # Fetch OTP when field is ready
            ),

            submit_callable=lambda: self.click_element(
                locator=(By.XPATH, "/html/body/section/div[2]/div/form/div[4]/div/button")
            ),

            success_condition=EC.url_contains("/Account/DscOptions"),

            failure_condition=EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, 'jq-toast-single') and not(contains(@class, 'jq-icon-success'))]")
            ),

            **kwargs
        )

    def handle_email_otp(self, **kwargs):
        # Removed job_id parameter, adjusted poll_for_otp call
        def _get_and_enter_otp():
            self.click_element(locator=(By.ID, ELEMENTS["EMAIL_OTP_BUTTON"]))
            email_otp = self.poll_for_otp("email_otp")
            self.send_text(locator=(By.ID, ELEMENTS["EMAIL_OTP_INPUT"]), keys=email_otp)
        self._execute_verification_step(step_name="Email OTP", action_callable=_get_and_enter_otp, submit_callable=lambda: self.click_element(locator=(By.ID, ELEMENTS["REMARK_INPUT"])), success_condition=EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Mail Verify Successfully')]")), failure_condition=EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Your email has not been verified yet')]")), recovery_callable=lambda: self.click_element(locator=(By.ID, ELEMENTS["EMAIL_OTP_BUTTON"])), **kwargs)

    def handle_aadhaar_otp(self, **kwargs):
        # Removed job_id parameter, adjusted poll_for_otp call
        mobile_mail_otp = self.poll_for_otp("mobile_mail")
        self._execute_verification_step(
            step_name="Mobile/Email OTP",
            action_callable=lambda: self.send_text(
                locator=(By.ID, "mobile_otp"), keys=mobile_mail_otp
            ),
            submit_callable=lambda: self.click_element(
                locator=(By.ID, ELEMENTS["VALIDATE_OTP_BUTTON"])
            ),
            success_condition=EC.url_contains("/OnlineAadharKyc/AadharKycLogin"),
            failure_condition=EC.presence_of_element_located(
                (By.XPATH, "//*[@id='modal-message' and contains(text(), 'Invalid OTP value.')]")
            ),
            recovery_callable=lambda: self.click_element(locator=(By.ID, "btn-dialog-ok")),
            **kwargs
        )

    def handle_trn(self, **kwargs):
        """Handles entering the Temporary Reference Number (TRN)."""
        trn = self.poll_for_otp("trn")
        self._execute_verification_step(
            step_name="TRN Input",
            action_callable=lambda: self.send_text(
                locator=(By.ID, ELEMENTS["TRN_INPUT"]), keys=trn
            ),
            # NOTE: Assuming a 'Proceed' button is clicked. You may need to update this locator.
            submit_callable=lambda: self.click_element(
                locator=(By.XPATH, "//button[normalize-space(text())='Proceed']")
            ),
            # NOTE: Assuming success is the appearance of a captcha. You may need to update this.
            success_condition=EC.presence_of_element_located((By.ID, "captchatrn")),
            # NOTE: Assuming a generic failure message. You may need to update this.
            failure_condition=EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(), 'Invalid TRN')]")
            ),
            **kwargs
        )

    def handle_final_captcha(self, ekyc_password: str, **kwargs):
        # Removed job_id parameter
        def action():
            self.send_text(locator=(By.ID, ELEMENTS["PASSWORD_INPUT"]), keys=ekyc_password, clear_first=False)
            self.send_text(locator=(By.ID, ELEMENTS["CONFIRM_PASSWORD_INPUT"]), keys=ekyc_password, clear_first=False)
            self.solve_and_enter_captcha()
        def recovery():
            self.send_text(locator=(By.ID, ELEMENTS["PASSWORD_INPUT"]), keys=ekyc_password)
            self.send_text(locator=(By.ID, ELEMENTS["CONFIRM_PASSWORD_INPUT"]), keys=ekyc_password)
        self._execute_verification_step(
            step_name="Final Password/CAPTCHA",
            action_callable=action,
            submit_callable=lambda: self.click_element(locator=(By.ID, ELEMENTS["NEXT_BUTTON"])),
            success_condition=EC.url_contains("/UploadVerification/VideoUpload"),
            failure_condition=EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Invalid Captcha Code')]")),
            recovery_callable=recovery,
            max_retries=15,
            **kwargs
        )
    
    