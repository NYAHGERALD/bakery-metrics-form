# Environment Setup Guide

## To prevent Google API import issues in the future:

### 1. Always use the virtual environment
```bash
# Activate virtual environment
source venv/bin/activate

# Verify you're in the right environment
which python
# Should show: /Users/geraldnyah/bakery-metrics-form/venv/bin/python
```

### 2. Use the startup script
Instead of running `python app.py` directly, use:
```bash
./start_app.sh
```

### 3. Check environment before running
```bash
python check_environment.py
```

### 4. If packages are missing, reinstall them
```bash
pip install -r requirements.txt
```

### 5. For production deployment
Make sure your production environment (Render, etc.) uses the exact same requirements.txt

## Troubleshooting

### If you get "Google API libraries not available" error:
1. Stop the Flask app
2. Run `./check_environment.py` to verify packages
3. If packages are missing: `pip install google-api-python-client google-auth`
4. Restart with `./start_app.sh`

### If running on a different machine:
1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install requirements: `pip install -r requirements.txt`
5. Use the startup script: `./start_app.sh`

## Key Files for Environment Management:
- `requirements.txt` - All Python dependencies
- `start_app.sh` - Startup script that ensures correct environment
- `check_environment.py` - Environment verification script
