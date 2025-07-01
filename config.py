# File: config.py
#
# Configuration file containing element locators for the GST registration automation
# All element IDs are dummy values and should be replaced with actual element IDs

ELEMENTS = {
    # Login CAPTCHA elements
    "LOGIN_CAPTCHA_IMAGE": "imgCaptcha",
    "LOGIN_CAPTCHA_INPUT": "captcha",
    
    # Navigation buttons
    "NEXT_BUTTON": "next-button-id",
    
    # Email OTP elements
    "EMAIL_OTP_BUTTON": "email-otp-button-id",
    "EMAIL_OTP_INPUT": "email-otp",
    "REMARK_INPUT": "remark-input-id",
    
    # TRN elements
    "TRN_INPUT": "trnno",
    
    # Form elements
    "APPLY_USING_BUTTON": "apply-using-button-id",
    "PAN_NUMBER_INPUT": "pan-number-input-id",
    
    
    # Password elements
    "PASSWORD_INPUT": "password-input-id",
    "CONFIRM_PASSWORD_INPUT": "confirm-password-input-id"
} 