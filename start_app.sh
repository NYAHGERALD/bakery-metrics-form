#!/bin/bash

# Bakery Metrics Flask App Startup Script
# This ensures the app always runs with the correct virtual environment

# Change to the app directory
cd /Users/geraldnyah/bakery-metrics-form

# Activate the virtual environment
source venv/bin/activate

# Check if required packages are installed
echo "Checking Google API packages..."
python -c "import google.oauth2.service_account; import googleapiclient.discovery; print('✅ Google API packages are available')" || {
    echo "❌ Google API packages not found. Installing..."
    pip install google-api-python-client google-auth
}

# Start the Flask application
echo "Starting Flask application..."
python app.py
