# GST Registration Automation API

A Flask API with Swagger UI that automates the GST registration process by accepting JSON configuration and running the complete automation flow.

## Features

- **Swagger UI Documentation** - Interactive API documentation at `/docs/`
- **JSON Configuration** - Send your complete GST registration data as JSON payload
- **Same Automation Flow** - Uses the exact same logic as your Jupyter notebook
- **Error Handling** - Comprehensive error handling and logging
- **Health Check** - Built-in health check endpoint

## Installation

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the API:**
   ```bash
   python app.py
   ```

3. **Access Swagger UI:**
   Open your browser and go to: `http://localhost:8001/docs/`

## API Endpoints

### 1. Automate GST Registration
- **URL:** `POST /api/v1/automate-gst-registration`
- **Description:** Automates the complete GST registration process
- **Content-Type:** `application/json`

### 2. Health Check
- **URL:** `GET /api/v1/health`
- **Description:** Check if the API is running

## Usage

### Using Swagger UI (Recommended)

1. Go to `http://localhost:8001/docs/`
2. Click on the **POST /automate-gst-registration** endpoint
3. Click **"Try it out"**
4. Copy the content from `example_config.json` into the request body
5. Modify the values according to your requirements
6. Click **"Execute"**

### Using curl

```bash
curl -X POST "http://localhost:8001/api/v1/automate-gst-registration" \
     -H "Content-Type: application/json" \
     -d @example_config.json
```

### Using Python requests

```python
import requests
import json

# Load your configuration
with open('example_config.json', 'r') as f:
    config = json.load(f)

# Make the API call
response = requests.post(
    'http://localhost:8001/api/v1/automate-gst-registration',
    json=config
)

print(response.json())
```

## JSON Configuration Structure

The API expects a JSON payload with the following sections:

```json
{
    "initial_registration_details": { ... },
    "business_details": { ... },
    "promoter_partner_details": { ... },
    "authorized_signatory_details": { ... },
    "principal_place_of_business_details": { ... },
    "goods_services_details": { ... }
}
```

See `example_config.json` for a complete example with all required fields.

## Response Format

### Success Response

```json
{
    "status": "success",
    "message": "GST registration automation completed successfully",
    "data": {
        "steps_completed": [
            "Initial registration details",
            "Business details",
            "Promoter/Partner details",
            "Authorized signatory details",
            "Principal place of business details",
            "Goods and services details"
        ]
    }
}
```

### Error Response

```json
{
    "status": "error",
    "message": "Error description",
    "errors": ["Detailed error messages"],
    "data": {
        "traceback": "Full error traceback for debugging"
    }
}
```

## Important Notes

1. **Manual Intervention Required:** The automation process includes OTP verification steps that require manual intervention. The API will pause at these points.

2. **Browser Window:** The Firefox browser window will open and remain open for manual verification of the process.

3. **File Paths:** Update file paths in your JSON configuration to match your local system paths for document uploads.

4. **Captcha Solving:** The API uses TrueCaptcha API for automatic captcha solving. Make sure your captcha service is properly configured.

5. **Logging:** All automation steps are logged. Check the console output and log files for detailed information.

## Configuration Tips

- **Document Uploads:** Ensure all file paths in your JSON configuration exist and are accessible
- **Phone/Email:** Use valid phone numbers and email addresses as OTP will be sent to these
- **Business Details:** Verify all business information is accurate before running
- **Address Information:** Ensure pincode and address details are correct

## Error Handling

The API includes comprehensive error handling:

- **Validation Errors:** Missing required JSON sections
- **Selenium Errors:** Element not found, timeout issues
- **Automation Errors:** Captcha solving failures, form submission issues
- **System Errors:** File not found, network issues

## Health Check

Check if the API is running:

```bash
curl http://localhost:8001/api/v1/health
```

## Development

To run in development mode with debug enabled:

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)
```

## Headless Mode

To run the browser in headless mode (no GUI), uncomment this line in `app.py`:

```python
options.add_argument('--headless')
```

## Support

For issues or questions:
1. Check the logs for detailed error information
2. Verify your JSON configuration matches the expected structure
3. Ensure all required dependencies are installed
4. Make sure Firefox is installed and accessible 