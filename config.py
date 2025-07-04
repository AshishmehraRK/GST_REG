# File: config.py
#
# Configuration file containing element locators for the GST registration automation
# Updated with working element IDs based on GST website structure

ELEMENTS = {
    # Login CAPTCHA elements
    "LOGIN_CAPTCHA_IMAGE": "imgCaptcha",
    "LOGIN_CAPTCHA_INPUT": "captcha",
    
    # Navigation buttons
    "NEXT_BUTTON": "btn_proceed",
    
    # Email OTP elements
    "EMAIL_OTP_BUTTON": "btn_send_email_otp",
    "EMAIL_OTP_INPUT": "email-otp",
    "REMARK_INPUT": "btn_verify_email",
    
    # Mobile OTP elements (for consistency)
    "MOBILE_OTP_INPUT": "mobile_otp",
    "MOBILE_OTP_BUTTON": "btn_send_mobile_otp",
    "VALIDATE_OTP_BUTTON": "btn_validate_otp",
    
    # TRN elements
    "TRN_INPUT": "trnno",
    
    # Form elements
    "APPLY_USING_BUTTON": "btn_apply_using",
    "PAN_NUMBER_INPUT": "pan_card",
    
    # Password elements
    "PASSWORD_INPUT": "password",
    "CONFIRM_PASSWORD_INPUT": "confirm_password"
} 