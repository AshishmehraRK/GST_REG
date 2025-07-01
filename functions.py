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
    ElementNotInteractableException
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
                time.sleep(1)
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
                time.sleep(1)
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
            time.sleep(2)
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
            except requests.exceptions.RequestException:
                self.logger.warning(f"Could not connect to OTP server. Retrying...")
            time.sleep(poll_interval)
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

