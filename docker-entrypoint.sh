#!/bin/bash
set -e

echo "🚀 Starting GST Automation API in Docker..."

# Create necessary directories
mkdir -p /app/logs /app/uploads /app/downloads

# Start Xvfb for headless browser display
echo "📺 Starting virtual display..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
export DISPLAY=:99

# Wait for Xvfb to start
sleep 3

# Check if Firefox is accessible
echo "🦊 Checking Firefox installation..."
firefox --version || echo "Warning: Firefox version check failed"

# Check if geckodriver is accessible
echo "🔧 Checking Geckodriver installation..."
geckodriver --version || echo "Warning: Geckodriver version check failed"

# Set permissions for log directory
chmod -R 755 /app/logs 2>/dev/null || true

# Print environment info
echo "🌐 Environment Information:"
echo "   - Python version: $(python --version)"
echo "   - Working directory: $(pwd)"
echo "   - Display: $DISPLAY"
echo "   - Timezone: ${TZ:-UTC}"

# Health check for dependencies
echo "🔍 Checking Python dependencies..."
python -c "import selenium, flask, flask_restx; print('✅ Core dependencies OK')" || {
    echo "❌ Dependency check failed"
    exit 1
}

# Start the Flask application
echo "🌟 Starting Flask API server..."
echo "📋 API will be available at: http://localhost:8001"
echo "📖 Swagger UI available at: http://localhost:8001/docs/"

exec python app.py 