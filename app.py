# Enhanced Flask App with PostgreSQL Integration
# Professional authentication with password hashing and session management

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from flask_mail import Mail, Message
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import re
import io
import uuid
import json
from functools import wraps
import logging
from contextlib import contextmanager
import time
import threading
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
import tempfile

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Flask App Configuration
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', '')
app.permanent_session_lifetime = timedelta(hours=2)

# Email Configuration (Flask-Mail)
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', '')

# Initialize Flask-Mail
mail = Mail(app)

# Database Configuration
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', ''),
    'database': os.getenv('DB_NAME', ''),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': os.getenv('DB_PORT', ''),
    'connect_timeout': 10,  # 10 second timeout
    'sslmode': 'require'  # Use 'disable' for localhost, 'require' for production
}

# Google Drive Configuration (for image uploads)
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID', '')

# Database Connection Pool
@contextmanager
def get_db_connection():
    """Context manager for database connections with automatic cleanup."""
    conn = None
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_database():
    """Initialize database connection and create tables on startup."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                
                # Create production_reports table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS production_reports (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL,
                        submitted_by VARCHAR(255) NOT NULL,
                        day_of_week VARCHAR(20) NOT NULL,
                        shift VARCHAR(20) NOT NULL,
                        item_no VARCHAR(100) NOT NULL,
                        cases_scheduled INTEGER NOT NULL,
                        cases_produced INTEGER NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        waste_lbs DECIMAL(10,2) NOT NULL,
                        std DECIMAL(10,2) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                
        logger.info("Database connection successful and tables initialized")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

# Authentication Helpers
def hash_password(password):
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Check if this is an API request
            if request.path.startswith('/api/') or request.headers.get('Accept', '').startswith('application/json'):
                return jsonify({
                    'success': False,
                    'message': 'Authentication required',
                    'error': 'not_authenticated'
                }), 401
            else:
                # Store the intended destination for redirect after login
                session['next_url'] = request.url
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/') or request.headers.get('Accept', '').startswith('application/json'):
                return jsonify({
                    'success': False,
                    'message': 'Authentication required',
                    'error': 'not_authenticated'
                }), 401
            else:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('home'))
        elif session.get('user_role') != 'admin':
            if request.path.startswith('/api/') or request.headers.get('Accept', '').startswith('application/json'):
                return jsonify({
                    'success': False,
                    'message': 'Admin access required',
                    'error': 'insufficient_privileges'
                }), 403
            else:
                flash("Admin access required.", "danger")
                return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_or_supervisor_required(f):
    """Decorator to require admin or supervisor role for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/') or request.headers.get('Accept', '').startswith('application/json'):
                return jsonify({
                    'success': False,
                    'message': 'Authentication required',
                    'error': 'not_authenticated'
                }), 401
            else:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('home'))
        elif session.get('user_role') not in ['admin', 'supervisor']:
            if request.path.startswith('/api/') or request.headers.get('Accept', '').startswith('application/json'):
                return jsonify({
                    'success': False,
                    'message': 'Admin or Supervisor access required',
                    'error': 'insufficient_privileges'
                }), 403
            else:
                flash("Admin or Supervisor access required.", "danger")
                return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function

def password_change_required(f):
    """Decorator to enforce password change for users with temporary passwords."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip this check for certain routes that should always be accessible
        skip_routes = [
            'login', 'logout', 'home', 'set_password', 'first_time_password_setup', 'password_success',
            'static', 'privacy_policy', 'terms_of_service', 'support'
        ]
        
        # Skip for static files and specific routes
        if request.endpoint in skip_routes or (request.endpoint and request.endpoint.startswith('static')):
            return f(*args, **kwargs)
        
        # Only check if user is logged in
        if 'user_id' in session:
            user_id = session.get('user_id')
            
            try:
                with get_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        # First check if the password_change_required column exists
                        cur.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'users' AND column_name = 'password_change_required'
                        """)
                        column_exists = cur.fetchone()
                        
                        if column_exists:
                            # Column exists, check if password change is required
                            cur.execute("""
                                SELECT password_change_required 
                                FROM users 
                                WHERE id = %s
                            """, (user_id,))
                            user = cur.fetchone()
                            
                            if user and user.get('password_change_required', False):
                                # User must change password before accessing any other functionality
                                if request.path.startswith('/api/') or request.headers.get('Accept', '').startswith('application/json'):
                                    return jsonify({
                                        'success': False,
                                        'message': 'Password change required before accessing this resource',
                                        'error': 'password_change_required',
                                        'redirect_url': url_for('set_password')
                                    }), 403
                                else:
                                    flash("You must change your password before accessing the dashboard.", "warning")
                                    return redirect(url_for('set_password'))
                        else:
                            # Column doesn't exist yet - skip password change enforcement
                            # This allows the app to function while waiting for database migration
                            logger.info("password_change_required column not found - skipping password change enforcement")
                            
            except Exception as e:
                logger.error(f"Error checking password change requirement: {e}")
                # On error, allow access to prevent system lockout
                pass
        
        return f(*args, **kwargs)
    return decorated_function


def add_cache_control_headers(f):
    """Decorator to add cache control headers to prevent caching of protected pages."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function

@app.before_request
def make_session_permanent():
    session.permanent = True

# Google Sheets Configuration (for legacy compatibility if needed)
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from googleapiclient.discovery import build
    
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', '/etc/secrets/credentials.json')
    
    if os.path.exists(credentials_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
        client = gspread.authorize(creds)
        drive_service = build('drive', 'v3', credentials=creds)
        SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID', '15YC7uMlrecjNDuwyT1fzRhipxmtjjzhfibxnLxoYkoQ')
        SHEET_NAME = "Foreign Material Reports"
        SPREADSHEET_NAME = 'BAKERY METRICS_2024-2025'
        
        # Helper to get latest week sheet name
        def get_latest_week_sheet():
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            sheet_names = spreadsheet.worksheets()
            pattern = re.compile(r"(\d{2}-\d{2}-\d{4})_\d{2}-\d{2}-\d{4}")

            def extract_date(sheet):
                match = pattern.match(sheet.title)
                if match:
                    return datetime.strptime(match.group(1), "%m-%d-%Y")
                return datetime.min

            sorted_sheets = sorted(sheet_names, key=extract_date, reverse=True)
            return sorted_sheets[0].title if sorted_sheets else ""
    else:
        logger.warning("Google credentials not found, Google Sheets functionality disabled")
        client = None
        drive_service = None
        
except ImportError:
    logger.warning("Google API libraries not installed, Google Sheets functionality disabled")
    client = None
    drive_service = None

# Helper Functions
def log_submission(user_id, user_name, user_email, submission_type, message, week_sheet=None, day_of_week=None, success=True):
    """Log form submissions for audit trail."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First, check if the user_id exists in the users table
                if user_id:
                    cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                    user_exists = cur.fetchone() is not None
                    
                    # If user doesn't exist, set user_id to None to avoid foreign key constraint
                    if not user_exists:
                        logger.warning(f"User ID {user_id} not found in users table, logging without user_id reference")
                        user_id = None
                
                cur.execute("""
                    INSERT INTO submission_logs
                    (user_id, user_name, user_email, submission_type, message, week_sheet, day_of_week, success)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id, user_name, user_email, submission_type, message, week_sheet, day_of_week, success))
                conn.commit()
    except Exception as e:
        logger.error(f"Failed to log submission: {e}")

def get_user_by_email(email):
    """Get user by email address."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, email, first_name, last_name, password_hash, phone, role, is_active, last_login
                    FROM users WHERE email = %s AND is_active = true
                """, (email.lower(),))
                return cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None

def get_user_by_email_with_status(email):
    """Get user by email address including inactive users for status checking."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, email, first_name, last_name, password_hash, phone, role, is_active, last_login
                    FROM users WHERE email = %s
                """, (email.lower(),))
                return cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None

def update_last_login(user_id):
    """Update user's last login timestamp."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users SET last_login = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
    except Exception as e:
        logger.error(f"Failed to update last login: {e}")

def get_latest_week_sheet():
    """Get the most recent week sheet."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT sheet_name
                    FROM weekly_sheets
                    WHERE is_active = true
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = cur.fetchone()
                return result['sheet_name'] if result else ""
    except Exception as e:
        logger.error(f"Error getting latest week sheet: {e}")
        return ""

def get_all_week_sheets():
    """Get all week sheets ordered by date."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT sheet_name, week_start, week_end
                    FROM weekly_sheets
                    WHERE is_active = true
                    ORDER BY created_at DESC
                """)
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Error getting week sheets: {e}")
        return []

# Email notification functions
def get_all_active_users():
    """Get all active users for email notifications."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, email, first_name, last_name
                    FROM users 
                    WHERE is_active = true AND email IS NOT NULL AND email != ''
                    ORDER BY first_name, last_name
                """)
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching active users: {e}")
        return []

def create_simple_metrics_email_html(recipient_name):
    """Create simple HTML email for metrics notification with PDF attachments."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily and Weekly Bakery Metrics</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .content {{
                padding: 30px;
                text-align: left;
            }}
            .greeting {{
                font-size: 16px;
                margin-bottom: 20px;
                color: #333;
            }}
            .message {{
                font-size: 16px;
                margin-bottom: 20px;
                color: #333;
                line-height: 1.8;
            }}
            .link {{
                color: #0066cc;
                text-decoration: none;
            }}
            .link:hover {{
                text-decoration: underline;
            }}
            .signature {{
                font-size: 16px;
                margin-top: 30px;
                color: #333;
            }}
            @media (max-width: 600px) {{
                .container {{
                    margin: 10px;
                }}
                .content {{
                    padding: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <div class="greeting">
                    Good morning {recipient_name},
                </div>
                
                <div class="message">
                    Please find attached the daily and weekly Bakery Metrics PDFs below for your review. For more detailed insights, important updates, and interactive chart visualizations, kindly visit our web app at: <a href="http://www.nyabeatz.com" class="link">http://www.nyabeatz.com</a>.
                </div>
                
                <div class="signature">
                    Best regards,<br>
                    Bakery Metrics Administrator.
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def send_metrics_notification_async(recipients, subject, html_content, week_name, day_of_week):
    """Send email notification asynchronously with PDF attachments."""
    def send_email():
        daily_pdf_path = None
        weekly_pdf_path = None
        
        try:
            with app.app_context():
                # Create PDF attachments
                daily_pdf_path = create_daily_metrics_pdf(week_name, day_of_week)
                weekly_pdf_path = create_weekly_summary_pdf(week_name)
                
                # Create email message
                msg = Message(
                    subject=subject,
                    recipients=recipients,
                    html=html_content,
                    sender=app.config['MAIL_DEFAULT_SENDER']
                )
                
                # Attach PDFs if they were created successfully
                if daily_pdf_path and os.path.exists(daily_pdf_path):
                    with open(daily_pdf_path, 'rb') as f:
                        msg.attach(
                            filename=f"Daily_Metrics_{week_name}_{day_of_week}.pdf",
                            content_type="application/pdf",
                            data=f.read()
                        )
                    logger.info(f"Attached daily metrics PDF for {week_name} {day_of_week}")
                
                if weekly_pdf_path and os.path.exists(weekly_pdf_path):
                    with open(weekly_pdf_path, 'rb') as f:
                        msg.attach(
                            filename=f"Weekly_Summary_{week_name}.pdf",
                            content_type="application/pdf",
                            data=f.read()
                        )
                    logger.info(f"Attached weekly summary PDF for {week_name}")
                
                # Send email
                mail.send(msg)
                logger.info(f"Metrics notification email with PDF attachments sent successfully to {len(recipients)} recipients")
                
                # Log the email activity
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO email_activity_log 
                                (type, week_name, day_of_week, recipient_count, status, sent_at)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                'automatic', week_name, day_of_week, len(recipients), 
                                'sent', datetime.now()
                            ))
                        conn.commit()
                except Exception as log_error:
                    logger.warning(f"Failed to log email activity: {log_error}")
                
        except Exception as e:
            logger.error(f"Failed to send metrics notification email: {e}")
            # Log the failed attempt
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO email_activity_log 
                            (type, week_name, day_of_week, recipient_count, status, sent_at, error_message)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            'automatic', week_name, day_of_week, len(recipients), 
                            'failed', datetime.now(), str(e)
                        ))
                    conn.commit()
            except:
                pass
        finally:
            # Clean up temporary PDF files
            for pdf_path in [daily_pdf_path, weekly_pdf_path]:
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        os.unlink(pdf_path)
                    except Exception as e:
                        logger.warning(f"Failed to clean up PDF file {pdf_path}: {e}")
    
    # Start email sending in a separate thread to not block the main request
    thread = threading.Thread(target=send_email)
    thread.daemon = True
    thread.start()

def send_metrics_notification(metrics_data, week_name, day_of_week, submitted_by):
    """Send metrics notification to users with enabled email preferences and PDF attachments."""
    try:
        # Get users with enabled email preferences instead of all active users
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        u.id,
                        u.email,
                        u.first_name,
                        u.last_name
                    FROM users u
                    JOIN email_notification_preferences enp 
                        ON u.id = enp.user_id 
                    WHERE u.is_active = true 
                        AND enp.is_enabled = true 
                        AND enp.preference_type = 'automatic'
                    ORDER BY u.first_name, u.last_name, u.email
                """)
                users = cur.fetchall()
        
        if not users:
            logger.warning("No users with enabled email preferences found for email notification")
            return False
        
        # Prepare email content with simplified message
        subject = "Daily and Weekly Bakery Metrics"
        
        # Send individual emails to each user with their name
        for user in users:
            # Get user's first name for personalization
            first_name = user.get('first_name', '').strip()
            last_name = user.get('last_name', '').strip()
            
            if first_name:
                user_name = first_name
            elif first_name and last_name:
                user_name = f"{first_name} {last_name}".strip()
            else:
                # Fallback to extracting name from email if no name is available
                email_name = user['email'].split('@')[0].replace('.', ' ').replace('_', ' ').title()
                user_name = email_name
            
            html_content = create_simple_metrics_email_html(user_name)
            
            # Send email asynchronously with PDF attachments
            send_metrics_notification_async([user['email']], subject, html_content, week_name, day_of_week)
        
        logger.info(f"Initiated simplified metrics notification emails with PDF attachments to {len(users)} users with enabled preferences")
        return True
        
    except Exception as e:
        logger.error(f"Error sending metrics notification: {e}")
        return False

# PDF Generation Functions (Global)

def create_daily_metrics_pdf(week_name, day_of_week):
    """Create simple, well-formatted PDF table for daily metrics."""
    # Get data from both_shifts_metrics table for combined totals
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        ws.submitted_by,
                        ws.created_at as submitted_at,
                        -- First shift data
                        fs.die_cut1_oee_pct as first_die_cut1_oee_pct,
                        fs.die_cut2_oee_pct as first_die_cut2_oee_pct,
                        fs.die_cut1_lbs as first_die_cut1_lbs,
                        fs.die_cut2_lbs as first_die_cut2_lbs,
                        fs.pounds_total as first_shift_pounds_total,
                        fs.die_cut1_waste_pct,
                        fs.die_cut2_waste_pct,
                        fs.oee_avg_pct as first_shift_oee_avg,
                        fs.waste_avg_pct as first_shift_waste_percent,
                        -- Second shift data
                        ss.die_cut1_oee_pct as second_die_cut1_oee_pct,
                        ss.die_cut2_oee_pct as second_die_cut2_oee_pct,
                        ss.die_cut1_lbs as second_die_cut1_lbs,
                        ss.die_cut2_lbs as second_die_cut2_lbs,
                        ss.pounds_total as second_shift_pounds_total,
                        ss.die_cut1_waste_pct as second_die_cut1_waste_pct,
                        ss.die_cut2_waste_pct as second_die_cut2_waste_pct,
                        ss.oee_avg_pct as second_shift_oee_avg,
                        ss.waste_avg_pct as second_shift_waste_percent,
                        -- Both shifts combined data
                        bs.die_cut1_oee_pct as both_die_cut1_oee_pct,
                        bs.die_cut2_oee_pct as both_die_cut2_oee_pct,
                        bs.oee_avg_pct as both_oee_avg_pct,
                        bs.die_cut1_lbs as both_die_cut1_lbs,
                        bs.die_cut2_lbs as both_die_cut2_lbs,
                        bs.pounds_total as both_pounds_total,
                        bs.die_cut1_waste_pct as both_die_cut1_waste_pct,
                        bs.die_cut2_waste_pct as both_die_cut2_waste_pct,
                        bs.waste_avg_pct as both_waste_avg_pct
                    FROM week_submissions ws
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    WHERE ws.week_name = %s AND ws.day_of_week = %s
                    ORDER BY ws.created_at DESC
                    LIMIT 1
                """, (week_name, day_of_week))
                metrics_data = cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching daily metrics data: {e}")
        return None

    if not metrics_data:
        return None
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    
    try:
        # Create PDF document with portrait orientation
        doc = SimpleDocTemplate(temp_file.name, pagesize=letter,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=72)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Helper functions
        def format_value(value, value_type='number'):
            """Format values with proper units."""
            if value is None or value == '':
                return 'N/A'
            try:
                num_value = float(value)
                if value_type == 'percentage':
                    return f"{num_value:.2f}%"
                elif value_type == 'pounds':
                    return f"{num_value:,.0f}"
                else:
                    return f"{num_value:,.1f}"
            except (ValueError, TypeError):
                return 'N/A'
        
        def get_status_and_color(value, metric_type, target_type):
            """Get status text and background color based on targets."""
            if value is None or value == '':
                return 'N/A', colors.white
            
            try:
                num_value = float(value)
                if metric_type == 'OEE':
                    if num_value >= 70:
                        return 'ON TARGET', colors.green
                    else:
                        return 'BELOW TARGET', colors.red
                elif metric_type == 'VOLUME':
                    if target_type == 'die_cut':
                        target = 6000
                    else:  # total
                        target = 12000
                    if num_value >= target:
                        return 'TARGET MET', colors.green
                    else:
                        return 'BELOW TARGET', colors.red
                elif metric_type == 'WASTE':
                    if num_value <= 3.75:
                        return 'ON TARGET', colors.green
                    else:
                        return 'BELOW TARGET', colors.red
            except (ValueError, TypeError):
                pass
            
            return 'N/A', colors.white
        
        # Header information
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        elements.append(Paragraph("DAILY METRICS REPORT", title_style))
        
        # Report metadata
        header_info = [
            ['Date:', f"{week_name} - {day_of_week}"],
            ['Submitted By:', metrics_data.get('submitted_by', 'N/A')],
            ['Time:', metrics_data.get('submitted_at', datetime.now()).strftime('%I:%M %p')],
            ['Title:', 'Bakery Production Metrics']
        ]
        
        header_table = Table(header_info, colWidths=[1.5*inch, 4*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 30))
        
        # Main metrics table
        table_data = [
            ['Key Performance Indicator', 'Targets', 'First Shift', 'Second Shift', 'Both Shift', 'Status']
        ]
        
        # OEE Section
        table_data.append(['OEE', '', '', '', '', ''])
        
        # OEE Die Cut 1 - use database column values instead of calculations
        first_oee1 = metrics_data.get('first_die_cut1_oee_pct')
        second_oee1 = metrics_data.get('second_die_cut1_oee_pct')
        both_die_cut1_oee = metrics_data.get('both_die_cut1_oee_pct')
        
        status_text, status_color = get_status_and_color(both_die_cut1_oee, 'OEE', 'die_cut')
        
        table_data.append([
            'Die Cut 1',
            '≥ 70%',
            format_value(first_oee1, 'percentage'),
            format_value(second_oee1, 'percentage'),
            format_value(both_die_cut1_oee, 'percentage'),
            status_text
        ])
        
        # OEE Die Cut 2 - use database column values instead of calculations
        first_oee2 = metrics_data.get('first_die_cut2_oee_pct')
        second_oee2 = metrics_data.get('second_die_cut2_oee_pct')
        both_die_cut2_oee = metrics_data.get('both_die_cut2_oee_pct')
        
        status_text, status_color = get_status_and_color(both_die_cut2_oee, 'OEE', 'die_cut')
        
        table_data.append([
            'Die Cut 2',
            '≥ 70%',
            format_value(first_oee2, 'percentage'),
            format_value(second_oee2, 'percentage'),
            format_value(both_die_cut2_oee, 'percentage'),
            status_text
        ])
        
        # OEE Total - use database column values instead of calculations
        first_shift_oee_avg = metrics_data.get('first_shift_oee_avg')
        second_shift_oee_avg = metrics_data.get('second_shift_oee_avg')
        both_oee_avg = metrics_data.get('both_oee_avg_pct')
        
        status_text, status_color = get_status_and_color(both_oee_avg, 'OEE', 'total')
        
        table_data.append([
            'Total',
            '≥ 70%',
            format_value(first_shift_oee_avg, 'percentage'),
            format_value(second_shift_oee_avg, 'percentage'),
            format_value(both_oee_avg, 'percentage'),
            status_text
        ])
        
        # VOLUME Section
        table_data.append(['VOLUME', '', '', '', '', ''])
        
        # Volume Die Cut 1 - use database column values instead of calculations
        first_vol1 = metrics_data.get('first_die_cut1_lbs')
        second_vol1 = metrics_data.get('second_die_cut1_lbs')
        both_die_cut1_lbs = metrics_data.get('both_die_cut1_lbs')
        
        status_text, status_color = get_status_and_color(both_die_cut1_lbs, 'VOLUME', 'die_cut')
        
        table_data.append([
            'Die Cut 1',
            '≥ 6,000 lbs',
            format_value(first_vol1, 'pounds'),
            format_value(second_vol1, 'pounds'),
            format_value(both_die_cut1_lbs, 'pounds'),
            status_text
        ])
        
        # Volume Die Cut 2 - use database column values instead of calculations
        first_vol2 = metrics_data.get('first_die_cut2_lbs')
        second_vol2 = metrics_data.get('second_die_cut2_lbs')
        both_die_cut2_lbs = metrics_data.get('both_die_cut2_lbs')
        
        status_text, status_color = get_status_and_color(both_die_cut2_lbs, 'VOLUME', 'die_cut')
        
        table_data.append([
            'Die Cut 2',
            '≥ 6,000 lbs',
            format_value(first_vol2, 'pounds'),
            format_value(second_vol2, 'pounds'),
            format_value(both_die_cut2_lbs, 'pounds'),
            status_text
        ])
        
        # Volume Total - use database column values instead of calculations
        first_shift_pounds_total = metrics_data.get('first_shift_pounds_total')
        second_shift_pounds_total = metrics_data.get('second_shift_pounds_total')
        both_pounds_total = metrics_data.get('both_pounds_total')
        
        status_text, status_color = get_status_and_color(both_pounds_total, 'VOLUME', 'total')
        
        table_data.append([
            'Total',
            '≥ 12,000 lbs',
            format_value(first_shift_pounds_total, 'pounds'),
            format_value(second_shift_pounds_total, 'pounds'),
            format_value(both_pounds_total, 'pounds'),
            status_text
        ])
        
        # WASTE Section
        table_data.append(['WASTE', '', '', '', '', ''])
        
        # Waste Die Cut 1 - use database column values instead of calculations
        first_waste1 = metrics_data.get('die_cut1_waste_pct')
        second_waste1 = metrics_data.get('second_die_cut1_waste_pct')
        both_die_cut1_waste_pct = metrics_data.get('both_die_cut1_waste_pct')
        
        status_text, status_color = get_status_and_color(both_die_cut1_waste_pct, 'WASTE', 'die_cut')
        
        table_data.append([
            'Die Cut 1',
            '≤ 3.75%',
            format_value(first_waste1, 'percentage'),
            format_value(second_waste1, 'percentage'),
            format_value(both_die_cut1_waste_pct, 'percentage'),
            status_text
        ])
        
        # Waste Die Cut 2 - use database column values instead of calculations
        first_waste2 = metrics_data.get('die_cut2_waste_pct')
        second_waste2 = metrics_data.get('second_die_cut2_waste_pct')
        both_die_cut2_waste_pct = metrics_data.get('both_die_cut2_waste_pct')
        
        status_text, status_color = get_status_and_color(both_die_cut2_waste_pct, 'WASTE', 'die_cut')
        
        table_data.append([
            'Die Cut 2',
            '≤ 3.75%',
            format_value(first_waste2, 'percentage'),
            format_value(second_waste2, 'percentage'),
            format_value(both_die_cut2_waste_pct, 'percentage'),
            status_text
        ])
        
        # Waste Total - use database column values instead of manual calculations
        first_shift_waste_total = metrics_data.get('first_shift_waste_percent')
        second_shift_waste_total = metrics_data.get('second_shift_waste_percent')
        both_waste_avg = metrics_data.get('both_waste_avg_pct')
        
        status_text, status_color = get_status_and_color(both_waste_avg, 'WASTE', 'total')
        
        table_data.append([
            'Total',
            '≤ 3.75%',
            format_value(first_shift_waste_total, 'percentage'),
            format_value(second_shift_waste_total, 'percentage'),
            format_value(both_waste_avg, 'percentage'),
            status_text
        ])
        
        # Create table
        table = Table(table_data, colWidths=[2.2*inch, 1.2*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.3*inch])
        
        # Apply table styling
        table_style = [
            # Header row - colorful gradient-like colors
            ('BACKGROUND', (0, 0), (0, 0), colors.Color(0.4, 0.5, 0.9)),  # Blue for KPI column
            ('BACKGROUND', (1, 0), (1, 0), colors.Color(0.5, 0.6, 0.8)),  # Light blue for Targets
            ('BACKGROUND', (2, 0), (2, 0), colors.Color(0.2, 0.7, 0.9)),  # Cyan for First Shift
            ('BACKGROUND', (3, 0), (3, 0), colors.Color(0.3, 0.6, 0.9)),  # Medium blue for Second Shift
            ('BACKGROUND', (4, 0), (4, 0), colors.Color(0.6, 0.3, 0.9)),  # Purple for Both Shift
            ('BACKGROUND', (5, 0), (5, 0), colors.Color(0.9, 0.5, 0.2)),  # Orange for Status
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Category headers (OEE, VOLUME, WASTE) - vibrant colors
            ('BACKGROUND', (0, 1), (-1, 1), colors.Color(0.2, 0.8, 0.4)),  # Green for OEE
            ('BACKGROUND', (0, 5), (-1, 5), colors.Color(0.9, 0.6, 0.1)),  # Orange for VOLUME
            ('BACKGROUND', (0, 9), (-1, 9), colors.Color(0.8, 0.2, 0.3)),  # Red for WASTE
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.white),
            ('TEXTCOLOR', (0, 5), (-1, 5), colors.white),
            ('TEXTCOLOR', (0, 9), (-1, 9), colors.white),
            ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
            ('FONTNAME', (0, 5), (0, 5), 'Helvetica-Bold'),
            ('FONTNAME', (0, 9), (0, 9), 'Helvetica-Bold'),
            
            # Data rows
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 2), (-1, 4), [colors.white, colors.lightgrey]),
            ('ROWBACKGROUNDS', (0, 6), (-1, 8), [colors.white, colors.lightgrey]),
            ('ROWBACKGROUNDS', (0, 10), (-1, 12), [colors.white, colors.lightgrey]),
        ]
        
        # Add conditional formatting for status colors
        for i, row in enumerate(table_data[1:], 1):  # Skip header
            if len(row) > 5 and row[5] in ['ON TARGET', 'TARGET MET']:
                table_style.append(('BACKGROUND', (5, i), (5, i), colors.green))
                table_style.append(('TEXTCOLOR', (5, i), (5, i), colors.white))
            elif len(row) > 5 and row[5] == 'BELOW TARGET':
                table_style.append(('BACKGROUND', (5, i), (5, i), colors.red))
                table_style.append(('TEXTCOLOR', (5, i), (5, i), colors.white))
        
        table.setStyle(TableStyle(table_style))
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        return temp_file.name
        
    except Exception as e:
        logger.error(f"Error creating daily metrics PDF: {e}")
        # Clean up temp file on error
        try:
            os.unlink(temp_file.name)
        except:
            pass
        return None

def create_weekly_summary_pdf(week_name):
    """Create simple, well-formatted PDF table for weekly summary."""
    # Get data for each day of the week
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        ws.day_of_week,
                        ws.submitted_by,
                        ws.created_at as submitted_at,
                        -- Both shifts combined data
                        bs.oee_avg_pct,
                        bs.pounds_total,
                        bs.waste_avg_pct,
                        -- Individual Die Cut data from both shifts
                        bs.die_cut1_oee_pct as both_die_cut1_oee_pct,
                        bs.die_cut2_oee_pct as both_die_cut2_oee_pct,
                        bs.die_cut1_lbs as both_die_cut1_lbs,
                        bs.die_cut2_lbs as both_die_cut2_lbs,
                        bs.die_cut1_waste_pct as both_die_cut1_waste_pct,
                        bs.die_cut2_waste_pct as both_die_cut2_waste_pct
                    FROM week_submissions ws
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    WHERE ws.week_name = %s
                    ORDER BY 
                        CASE ws.day_of_week 
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                            WHEN 'Saturday' THEN 6
                            WHEN 'Sunday' THEN 7
                        END
                """, (week_name,))
                weekly_data = cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching weekly summary data: {e}")
        return None

    if not weekly_data:
        return None
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    
    try:
        # Create PDF document with portrait orientation
        doc = SimpleDocTemplate(temp_file.name, pagesize=letter,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=72)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Helper functions
        def format_value(value, value_type='number'):
            """Format values with proper units."""
            if value is None or value == '':
                return 'N/A'
            try:
                num_value = float(value)
                if value_type == 'percentage':
                    return f"{num_value:.2f}%"
                elif value_type == 'pounds':
                    return f"{num_value:,.0f}"
                else:
                    return f"{num_value:,.1f}"
            except (ValueError, TypeError):
                return 'N/A'
        
        def get_status_and_color(value, metric_type, target_type='total'):
            """Get status text and background color based on targets."""
            if value is None or value == '':
                return 'N/A', colors.white
            
            try:
                num_value = float(value)
                if metric_type == 'OEE':
                    if num_value >= 70:
                        return 'ON TARGET', colors.green
                    else:
                        return 'BELOW TARGET', colors.red
                elif metric_type == 'VOLUME':
                    if num_value >= 12000:  # Weekly target
                        return 'TARGET MET', colors.green
                    else:
                        return 'BELOW TARGET', colors.red
                elif metric_type == 'WASTE':
                    if num_value <= 3.75:
                        return 'ON TARGET', colors.green
                    else:
                        return 'BELOW TARGET', colors.red
            except (ValueError, TypeError):
                pass
            
            return 'N/A', colors.white
        
        # Header information
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        elements.append(Paragraph("WEEKLY SUMMARY REPORT", title_style))
        
        # Report metadata
        header_info = [
            ['Date:', week_name],
            ['Submitted By:', weekly_data[0].get('submitted_by', 'N/A') if weekly_data else 'N/A'],
            ['Time:', weekly_data[0].get('submitted_at', datetime.now()).strftime('%I:%M %p') if weekly_data else datetime.now().strftime('%I:%M %p')],
            ['Title:', 'Bakery Production Weekly Summary']
        ]
        
        header_table = Table(header_info, colWidths=[1.5*inch, 4*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 30))
        
        # Daily breakdown table
        table_data = [
            ['Day', 'OEE %', 'Volume (lbs)', 'Waste %', 'Status']
        ]
        
        # Process each day's data
        for day_data in weekly_data:
            day = day_data.get('day_of_week', 'N/A')
            oee = day_data.get('oee_avg_pct')
            volume = day_data.get('pounds_total')
            waste = day_data.get('waste_avg_pct')
            
            # Determine overall status for the day
            overall_status = 'GOOD'
            if oee is not None and float(oee) < 70:
                overall_status = 'NEEDS ATTENTION'
            if volume is not None and float(volume) < 12000:
                overall_status = 'NEEDS ATTENTION'
            if waste is not None and float(waste) > 3.75:
                overall_status = 'NEEDS ATTENTION'
            
            table_data.append([
                day,
                format_value(oee, 'percentage'),
                format_value(volume, 'pounds'),
                format_value(waste, 'percentage'),
                overall_status
            ])
        
        # Calculate weekly averages/totals for summary
        oee_values = [float(d.get('oee_avg_pct', 0)) for d in weekly_data if d.get('oee_avg_pct')]
        volume_values = [float(d.get('pounds_total', 0)) for d in weekly_data if d.get('pounds_total')]
        waste_values = [float(d.get('waste_avg_pct', 0)) for d in weekly_data if d.get('waste_avg_pct')]
        
        avg_oee = sum(oee_values) / len(oee_values) if oee_values else 0
        total_volume = sum(volume_values) if volume_values else 0
        avg_waste = sum(waste_values) / len(waste_values) if waste_values else 0
        
        # Add summary row
        table_data.append(['', '', '', '', ''])  # Empty separator row
        table_data.append([
            'WEEKLY SUMMARY',
            format_value(avg_oee, 'percentage'),
            format_value(total_volume, 'pounds'),
            format_value(avg_waste, 'percentage'),
            'SUMMARY'
        ])
        
        # Create table
        table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        
        # Apply table styling
        table_style = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Summary row
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            
            # Data rows
            ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -3), [colors.white, colors.lightgrey]),
        ]
        
        # Add conditional formatting for status colors
        for i, row in enumerate(table_data[1:-2], 1):  # Skip header and summary rows
            if len(row) > 4:
                if row[4] == 'GOOD':
                    table_style.append(('BACKGROUND', (4, i), (4, i), colors.green))
                    table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.white))
                elif row[4] == 'NEEDS ATTENTION':
                    table_style.append(('BACKGROUND', (4, i), (4, i), colors.red))
                    table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.white))
        
        table.setStyle(TableStyle(table_style))
        elements.append(table)
        
        elements.append(Spacer(1, 30))
        
        # Weekly KPI Summary Table
        summary_title_style = ParagraphStyle(
            'SummaryTitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=15,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        elements.append(Paragraph("WEEKLY KPI SUMMARY", summary_title_style))
        
        # Weekly summary table similar to daily format with die cut details
        kpi_table_data = [
            ['Key Performance Indicator', 'Targets', 'Weekly Average/Total', 'Status']
        ]
        
        # Calculate die cut values first for reuse
        dc1_oee_values = [float(d.get('both_die_cut1_oee_pct', 0)) for d in weekly_data if d.get('both_die_cut1_oee_pct')]
        dc1_avg_oee = sum(dc1_oee_values) / len(dc1_oee_values) if dc1_oee_values else 0
        dc2_oee_values = [float(d.get('both_die_cut2_oee_pct', 0)) for d in weekly_data if d.get('both_die_cut2_oee_pct')]
        dc2_avg_oee = sum(dc2_oee_values) / len(dc2_oee_values) if dc2_oee_values else 0
        
        dc1_volume_values = [float(d.get('both_die_cut1_lbs', 0)) for d in weekly_data if d.get('both_die_cut1_lbs')]
        dc1_total_volume = sum(dc1_volume_values) if dc1_volume_values else 0
        dc2_volume_values = [float(d.get('both_die_cut2_lbs', 0)) for d in weekly_data if d.get('both_die_cut2_lbs')]
        dc2_total_volume = sum(dc2_volume_values) if dc2_volume_values else 0
        
        dc1_waste_values = [float(d.get('both_die_cut1_waste_pct', 0)) for d in weekly_data if d.get('both_die_cut1_waste_pct')]
        dc1_avg_waste = sum(dc1_waste_values) / len(dc1_waste_values) if dc1_waste_values else 0
        dc2_waste_values = [float(d.get('both_die_cut2_waste_pct', 0)) for d in weekly_data if d.get('both_die_cut2_waste_pct')]
        dc2_avg_waste = sum(dc2_waste_values) / len(dc2_waste_values) if dc2_waste_values else 0
        
        # OEE Summary - Die Cut 1, Die Cut 2, then Overall
        dc1_oee_status, _ = get_status_and_color(dc1_avg_oee, 'OEE')
        kpi_table_data.append([
            'OEE Average (Die Cut 1)',
            '≥ 70%',
            format_value(dc1_avg_oee, 'percentage'),
            dc1_oee_status
        ])
        
        dc2_oee_status, _ = get_status_and_color(dc2_avg_oee, 'OEE')
        kpi_table_data.append([
            'OEE Average (Die Cut 2)',
            '≥ 70%',
            format_value(dc2_avg_oee, 'percentage'),
            dc2_oee_status
        ])
        
        oee_status, _ = get_status_and_color(avg_oee, 'OEE')
        kpi_table_data.append([
            'OEE Average (Overall)',
            '≥ 70%',
            format_value(avg_oee, 'percentage'),
            oee_status
        ])
        
        # Volume Summary - Die Cut 1, Die Cut 2, then Overall
        dc1_volume_status, _ = get_status_and_color(dc1_total_volume / 7, 'VOLUME')  # Daily average
        kpi_table_data.append([
            'Total Volume (Die Cut 1)',
            '≥ 42,000 lbs/week',
            format_value(dc1_total_volume, 'pounds'),
            dc1_volume_status
        ])
        
        dc2_volume_status, _ = get_status_and_color(dc2_total_volume / 7, 'VOLUME')  # Daily average
        kpi_table_data.append([
            'Total Volume (Die Cut 2)',
            '≥ 42,000 lbs/week',
            format_value(dc2_total_volume, 'pounds'),
            dc2_volume_status
        ])
        
        volume_status, _ = get_status_and_color(total_volume / 7, 'VOLUME')  # Daily average
        kpi_table_data.append([
            'Total Volume (Weekly)',
            '≥ 84,000 lbs/week',
            format_value(total_volume, 'pounds'),
            volume_status
        ])
        
        # Waste Summary - Die Cut 1, Die Cut 2, then Overall
        dc1_waste_status, _ = get_status_and_color(dc1_avg_waste, 'WASTE')
        kpi_table_data.append([
            'Waste Average (Die Cut 1)',
            '≤ 3.75%',
            format_value(dc1_avg_waste, 'percentage'),
            dc1_waste_status
        ])
        
        dc2_waste_status, _ = get_status_and_color(dc2_avg_waste, 'WASTE')
        kpi_table_data.append([
            'Waste Average (Die Cut 2)',
            '≤ 3.75%',
            format_value(dc2_avg_waste, 'percentage'),
            dc2_waste_status
        ])
        
        waste_status, _ = get_status_and_color(avg_waste, 'WASTE')
        kpi_table_data.append([
            'Waste Average (Overall)',
            '≤ 3.75%',
            format_value(avg_waste, 'percentage'),
            waste_status
        ])
        
        # Create KPI summary table
        kpi_table = Table(kpi_table_data, colWidths=[2.5*inch, 1.5*inch, 2*inch, 1.5*inch])
        
        kpi_table_style = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Data rows
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]
        
        # Add conditional formatting for KPI status colors
        for i, row in enumerate(kpi_table_data[1:], 1):  # Skip header
            if len(row) > 3:
                if row[3] in ['ON TARGET', 'TARGET MET']:
                    kpi_table_style.append(('BACKGROUND', (3, i), (3, i), colors.green))
                    kpi_table_style.append(('TEXTCOLOR', (3, i), (3, i), colors.white))
                elif row[3] == 'BELOW TARGET':
                    kpi_table_style.append(('BACKGROUND', (3, i), (3, i), colors.red))
                    kpi_table_style.append(('TEXTCOLOR', (3, i), (3, i), colors.white))
        
        kpi_table.setStyle(TableStyle(kpi_table_style))
        elements.append(kpi_table)
        
        # Add page break before detailed breakdown sections
        from reportlab.platypus import PageBreak
        elements.append(PageBreak())
        
        # DIE CUT 1 DETAILED BREAKDOWN
        die_cut_title_style = ParagraphStyle(
            'DieCutTitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=15,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        elements.append(Paragraph("DIE CUT 1 - DETAILED BREAKDOWN", die_cut_title_style))
        
        # Die Cut 1 breakdown table
        dc1_table_data = [
            ['Day', 'OEE %', 'Volume (lbs)', 'Waste %', 'Status']
        ]
        
        # Process each day's Die Cut 1 data
        dc1_oee_values = []
        dc1_volume_values = []
        dc1_waste_values = []
        
        for day_data in weekly_data:
            day = day_data.get('day_of_week', 'N/A')
            dc1_oee = day_data.get('both_die_cut1_oee_pct')
            dc1_volume = day_data.get('both_die_cut1_lbs')
            dc1_waste = day_data.get('both_die_cut1_waste_pct')
            
            # Collect values for summary calculation
            if dc1_oee is not None:
                dc1_oee_values.append(float(dc1_oee))
            if dc1_volume is not None:
                dc1_volume_values.append(float(dc1_volume))
            if dc1_waste is not None:
                dc1_waste_values.append(float(dc1_waste))
            
            # Determine status for Die Cut 1
            dc1_status = 'GOOD'
            if dc1_oee is not None and float(dc1_oee) < 70:
                dc1_status = 'NEEDS ATTENTION'
            if dc1_volume is not None and float(dc1_volume) < 6000:
                dc1_status = 'NEEDS ATTENTION'
            if dc1_waste is not None and float(dc1_waste) > 3.75:
                dc1_status = 'NEEDS ATTENTION'
            
            dc1_table_data.append([
                day,
                format_value(dc1_oee, 'percentage'),
                format_value(dc1_volume, 'pounds'),
                format_value(dc1_waste, 'percentage'),
                dc1_status
            ])
        
        # Calculate Die Cut 1 weekly averages/totals
        dc1_avg_oee = sum(dc1_oee_values) / len(dc1_oee_values) if dc1_oee_values else 0
        dc1_total_volume = sum(dc1_volume_values) if dc1_volume_values else 0
        dc1_avg_waste = sum(dc1_waste_values) / len(dc1_waste_values) if dc1_waste_values else 0
        
        # Add Die Cut 1 summary row
        dc1_table_data.append(['', '', '', '', ''])  # Empty separator row
        dc1_table_data.append([
            'DIE CUT 1 SUMMARY',
            format_value(dc1_avg_oee, 'percentage'),
            format_value(dc1_total_volume, 'pounds'),
            format_value(dc1_avg_waste, 'percentage'),
            'SUMMARY'
        ])
        
        # Create Die Cut 1 table
        dc1_table = Table(dc1_table_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        
        # Apply Die Cut 1 table styling
        dc1_table_style = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Summary row
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            
            # Data rows
            ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -3), [colors.white, colors.lightblue]),
        ]
        
        # Add conditional formatting for Die Cut 1 status colors
        for i, row in enumerate(dc1_table_data[1:-2], 1):  # Skip header and summary rows
            if len(row) > 4:
                if row[4] == 'GOOD':
                    dc1_table_style.append(('BACKGROUND', (4, i), (4, i), colors.green))
                    dc1_table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.white))
                elif row[4] == 'NEEDS ATTENTION':
                    dc1_table_style.append(('BACKGROUND', (4, i), (4, i), colors.red))
                    dc1_table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.white))
        
        dc1_table.setStyle(TableStyle(dc1_table_style))
        elements.append(dc1_table)
        
        elements.append(Spacer(1, 30))
        
        # DIE CUT 2 DETAILED BREAKDOWN
        elements.append(Paragraph("DIE CUT 2 - DETAILED BREAKDOWN", die_cut_title_style))
        
        # Die Cut 2 breakdown table
        dc2_table_data = [
            ['Day', 'OEE %', 'Volume (lbs)', 'Waste %', 'Status']
        ]
        
        # Process each day's Die Cut 2 data
        dc2_oee_values = []
        dc2_volume_values = []
        dc2_waste_values = []
        
        for day_data in weekly_data:
            day = day_data.get('day_of_week', 'N/A')
            dc2_oee = day_data.get('both_die_cut2_oee_pct')
            dc2_volume = day_data.get('both_die_cut2_lbs')
            dc2_waste = day_data.get('both_die_cut2_waste_pct')
            
            # Collect values for summary calculation
            if dc2_oee is not None:
                dc2_oee_values.append(float(dc2_oee))
            if dc2_volume is not None:
                dc2_volume_values.append(float(dc2_volume))
            if dc2_waste is not None:
                dc2_waste_values.append(float(dc2_waste))
            
            # Determine status for Die Cut 2
            dc2_status = 'GOOD'
            if dc2_oee is not None and float(dc2_oee) < 70:
                dc2_status = 'NEEDS ATTENTION'
            if dc2_volume is not None and float(dc2_volume) < 6000:
                dc2_status = 'NEEDS ATTENTION'
            if dc2_waste is not None and float(dc2_waste) > 3.75:
                dc2_status = 'NEEDS ATTENTION'
            
            dc2_table_data.append([
                day,
                format_value(dc2_oee, 'percentage'),
                format_value(dc2_volume, 'pounds'),
                format_value(dc2_waste, 'percentage'),
                dc2_status
            ])
        
        # Calculate Die Cut 2 weekly averages/totals
        dc2_avg_oee = sum(dc2_oee_values) / len(dc2_oee_values) if dc2_oee_values else 0
        dc2_total_volume = sum(dc2_volume_values) if dc2_volume_values else 0
        dc2_avg_waste = sum(dc2_waste_values) / len(dc2_waste_values) if dc2_waste_values else 0
        
        # Add Die Cut 2 summary row
        dc2_table_data.append(['', '', '', '', ''])  # Empty separator row
        dc2_table_data.append([
            'DIE CUT 2 SUMMARY',
            format_value(dc2_avg_oee, 'percentage'),
            format_value(dc2_total_volume, 'pounds'),
            format_value(dc2_avg_waste, 'percentage'),
            'SUMMARY'
        ])
        
        # Create Die Cut 2 table
        dc2_table = Table(dc2_table_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        
        # Apply Die Cut 2 table styling
        dc2_table_style = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Summary row
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            
            # Data rows
            ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -3), [colors.white, colors.lightgreen]),
        ]
        
        # Add conditional formatting for Die Cut 2 status colors
        for i, row in enumerate(dc2_table_data[1:-2], 1):  # Skip header and summary rows
            if len(row) > 4:
                if row[4] == 'GOOD':
                    dc2_table_style.append(('BACKGROUND', (4, i), (4, i), colors.green))
                    dc2_table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.white))
                elif row[4] == 'NEEDS ATTENTION':
                    dc2_table_style.append(('BACKGROUND', (4, i), (4, i), colors.red))
                    dc2_table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.white))
        
        dc2_table.setStyle(TableStyle(dc2_table_style))
        elements.append(dc2_table)
        
        # Build PDF
        doc.build(elements)
        return temp_file.name
        
    except Exception as e:
        logger.error(f"Error creating weekly summary PDF: {e}")
        # Clean up temp file on error
        try:
            os.unlink(temp_file.name)
        except:
            pass
        return None

# Google Drive image upload function (keeping existing functionality)
def upload_image_to_drive(image_file):
    """Upload image to Google Drive and return public URL."""
    try:
        # Import Google API components only when needed
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseUpload
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError as import_error:
            logger.error(f"Google API libraries not available: {import_error}")
            raise Exception("Google Drive upload functionality is not available due to missing dependencies")
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', '/etc/secrets/credentials.json')
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        drive_service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': f"{uuid.uuid4()}_{image_file.filename}",
            'parents': [GOOGLE_DRIVE_FOLDER_ID]
        }

        image_stream = io.BytesIO(image_file.read())
        media = MediaIoBaseUpload(image_stream, mimetype=image_file.mimetype)

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        # Make the image public
        drive_service.permissions().create(
            fileId=uploaded_file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return f"https://drive.google.com/uc?id={uploaded_file['id']}"

    except Exception as e:
        logger.error(f"Image upload error: {e}")
        raise

# Routes
@app.route('/')
def home():
    """Landing page with server-side rendered reviews as fallback"""
    try:
        # Get some reviews to display server-side as fallback
        reviews_data = {
            'reviews': [],
            'average_rating': 0,
            'total_reviews': 0
        }
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get first 6 approved reviews for display
                    cur.execute("""
                        SELECT 
                            ur.id, ur.rating, ur.review_text, ur.category,
                            ur.is_anonymous, ur.is_featured, ur.created_at,
                            u.first_name, u.last_name
                        FROM user_reviews ur
                        LEFT JOIN users u ON ur.user_id = u.id
                        WHERE ur.is_approved = true
                        ORDER BY ur.is_featured DESC, ur.created_at DESC
                        LIMIT 6
                    """)
                    
                    reviews = cur.fetchall()
                    
                    # Get total count and average rating
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_count,
                            AVG(rating)::NUMERIC(3,2) as avg_rating
                        FROM user_reviews
                        WHERE is_approved = true
                    """)
                    
                    stats = cur.fetchone()
                    
                    # Format reviews for template
                    formatted_reviews = []
                    for review in reviews:
                        # Determine author display name
                        if review['is_anonymous']:
                            author_name = 'Anonymous Customer'
                        elif review['first_name'] and review['last_name']:
                            author_name = f"{review['first_name']} {review['last_name']}"
                        else:
                            author_name = 'Verified Customer'
                        
                        formatted_reviews.append({
                            'id': str(review['id']),
                            'rating': review['rating'],
                            'review_text': review['review_text'],
                            'category': review['category'],
                            'is_featured': review['is_featured'],
                            'author_name': author_name,
                            'created_at': review['created_at'].strftime('%B %Y') if review['created_at'] else 'Recently'
                        })
                    
                    reviews_data = {
                        'reviews': formatted_reviews,
                        'average_rating': round(float(stats['avg_rating']), 1) if stats['avg_rating'] else 0,
                        'total_reviews': stats['total_count']
                    }
        except Exception as e:
            logger.warning(f"Could not load reviews for landing page: {e}")
            # Keep default empty values
            pass
        
        return render_template('index.html', reviews_data=reviews_data)
        
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        return render_template('index.html', reviews_data={'reviews': [], 'average_rating': 0, 'total_reviews': 0})

@app.route('/info')
def public_info():
    """Public information page with announcements (no authentication required)"""
    try:
        # You can add any additional context data here
        context = {
            'page_title': 'Information Center',
            'current_page': 'info'
        }
        
        return render_template('infor.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading info page: {e}")
        return render_template('index.html'), 500


@app.route('/sw.js')
def service_worker():
    """Serve the service worker file"""
    try:
        return app.send_static_file('sw.js')
    except Exception as e:
        logger.error(f"Error serving service worker: {e}")
        return "Service worker not found", 404
      

@app.route('/verify-email', methods=['POST'])
def verify_email():
    """Legacy route for compatibility - redirects to login"""
    return redirect(url_for('login'), code=307)



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template('login.html')

    # First, get user regardless of active status to check account status
    user = get_user_by_email_with_status(email)
    if not user:
        flash("Invalid email or password.", "danger")
        return render_template('login.html')

    # Check account status BEFORE password verification
    if not user.get('is_active', False):
        flash("Sorry! Your account is deactivated. Contact your system administrator for assistance.", "danger")
        return render_template('login.html')

    # Now proceed with password verification
    if not verify_password(password, user['password_hash']):
        flash("Invalid email or password.", "danger")
        return render_template('login.html')

    # Set session variables
    session['user_id'] = str(user['id'])
    session['email'] = user['email']
    
    # Handle case where last_name might contain email (data integrity issue)
    last_name = user['last_name']
    if last_name and '@' in last_name:
        # If last_name looks like an email, just use first_name
        session['user_full_name'] = user['first_name']
        logger.warning(f"User {user['id']} has email in last_name field: {last_name}")
    else:
        session['user_full_name'] = f"{user['first_name']} {user['last_name']}" if last_name else user['first_name']
    
    session['user_role'] = user['role']
    session['verified'] = True

    # Check if this is the first time login (last_login is NULL)
    is_first_login = user['last_login'] is None
    
    # Update last login
    update_last_login(user['id'])

    # Log successful login
    log_submission(
        user['id'], 
        session['user_full_name'], 
        user['email'], 
        'login', 
        f'Successful login {"(first time)" if is_first_login else ""}'
    )

    # For first-time login, set password_change_required flag and redirect to password reset
    if is_first_login:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check if password_change_required column exists and set it
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'users' AND column_name = 'password_change_required'
                    """)
                    column_exists = cur.fetchone()
                    
                    if column_exists:
                        cur.execute("""
                            UPDATE users 
                            SET password_change_required = true, updated_at = CURRENT_TIMESTAMP 
                            WHERE id = %s
                        """, (user['id'],))
                        conn.commit()
        except Exception as e:
            logger.error(f"Error setting password_change_required flag: {e}")
        
        flash(f"Welcome {user['first_name']}! Please set a new password for your account.", "info")
        session['first_time_login'] = True  # Flag to allow password change without old password
        return redirect(url_for('first_time_password_setup'))

    flash(f"Welcome back, {user['first_name']}!", "success")
    
    # Check if there's a next_url to redirect to after login
    next_url = session.pop('next_url', None)
    if next_url and next_url != url_for('login'):
        return redirect(next_url)
    
    return redirect(url_for('startup'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    # Get form data
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    # Validation
    if not all([first_name, last_name, email, password, confirm_password]):
        flash("All fields are required.", "danger")
        return render_template('register.html')

    if password != confirm_password:
        flash("Passwords do not match.", "danger")
        return render_template('register.html')

    # Password strength validation
    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "danger")
        return render_template('register.html')

    if not re.search(r"[A-Z]", password):
        flash("Password must contain at least one uppercase letter.", "danger")
        return render_template('register.html')

    if not re.search(r"[a-z]", password):
        flash("Password must contain at least one lowercase letter.", "danger")
        return render_template('register.html')

    if not re.search(r"[0-9]", password):
        flash("Password must contain at least one number.", "danger")
        return render_template('register.html')

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        flash("Password must contain at least one special character.", "danger")
        return render_template('register.html')

    # Email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        flash("Please enter a valid email address.", "danger")
        return render_template('register.html')

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if email already exists
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    flash("This email is already registered.", "warning")
                    return render_template('register.html')

                # Hash password and create user
                password_hash = hash_password(password)
                user_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO users (id, email, first_name, last_name, password_hash, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, email, first_name, last_name, password_hash, 'user'))
                
                conn.commit()

                # Log registration
                log_submission(
                    user_id, 
                    f"{first_name} {last_name}", 
                    email, 
                    'registration', 
                    'New user registered'
                )

                flash(f"Registration successful! Welcome {first_name}!", "success")
                return render_template('registration_confirmation.html', success=True, name=first_name)

    except Exception as e:
        logger.error(f"Registration error: {e}")
        flash(f"An error occurred during registration: {str(e)}", "danger")
        return render_template('register.html')
    

# Registration confirmation route
@app.route('/registration-confirmation')
def registration_confirmation():
    # Get name from session or request args
    name = session.get('registered_name') or request.args.get('name', 'User')
    
    return render_template('registration_confirmation.html', name=name)



@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template('admin_login.html')

    # First, get user regardless of active status to check account status
    user = get_user_by_email_with_status(email)
    if not user or user['role'] != 'admin':
        flash("Invalid admin credentials.", "danger")
        return render_template('admin_login.html')

    # Check account status BEFORE password verification
    if not user.get('is_active', False):
        flash("Sorry! Your account is deactivated. Contact your system administrator for assistance.", "danger")
        return render_template('admin_login.html')

    # Now proceed with password verification
    if not verify_password(password, user['password_hash']):
        flash("Invalid admin credentials.", "danger")
        return render_template('admin_login.html')

    # Set admin session
    session['user_id'] = str(user['id'])
    session['email'] = user['email']
    
    # Handle case where last_name might contain email (data integrity issue)
    last_name = user['last_name']
    if last_name and '@' in last_name:
        # If last_name looks like an email, just use first_name
        session['user_full_name'] = user['first_name']
        logger.warning(f"Admin user {user['id']} has email in last_name field: {last_name}")
    else:
        session['user_full_name'] = f"{user['first_name']} {user['last_name']}" if last_name else user['first_name']
    
    session['user_role'] = user['role']
    session['is_admin'] = True  # Add this for API endpoints
    session['admin_verified'] = True
    session['verified'] = True

    update_last_login(user['id'])
    
    log_submission(
        user['id'], 
        session['user_full_name'], 
        user['email'], 
        'admin_login', 
        'Admin login successful'
    )

    return redirect(url_for('administration'))

@app.route('/administration')
@admin_required
def administration():
    return render_template('administration.html')

@app.route('/dashboard')
@login_required
@password_change_required
@add_cache_control_headers
def dashboard():
    return render_template('dashboard.html', user_full_name=session.get('user_full_name', 'User'))


@app.route('/startup')
@login_required
@password_change_required
@add_cache_control_headers
def startup():
    """Startup navigation hub - loads after successful login"""
    user_role = session.get('user_role', 'user')  # Get user role from session (stored during login)
    return render_template('startup.html', user_full_name=session.get('user_full_name', 'User'), user_role=user_role)


@app.route('/production-dashboard')
def production_dashboard():
    """Production dashboard - accessible without login for demonstration purposes"""
    return render_template('production-dash.html', user_full_name=session.get('user_full_name', 'Demo User'))


@app.route('/vacation-hub')
@login_required
def vacation_hub():
    """Vacation management dashboard for supervisors"""
    user_full_name = session.get('user_full_name', 'User')
    user_role = session.get('user_role', 'Employee')
    
    # Get initials from full name
    name_parts = user_full_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[1][0]}".upper()
    else:
        initials = user_full_name[:2].upper() if len(user_full_name) >= 2 else user_full_name[0].upper()
    
    return render_template('vacation-hub.html', 
                         user_full_name=user_full_name,
                         user_role=user_role,
                         user_initials=initials)


@app.route('/user-first')
@login_required
def user_first():
    """Employee vacation dashboard - simplified view for regular users"""
    user_full_name = session.get('user_full_name', 'User')
    user_role = session.get('user_role', 'Employee')
    user_id = session.get('user_id')
    
    # Get employee ID from user_id
    employee_id = None
    if user_id:
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id FROM employees WHERE user_id = %s
                    """, (user_id,))
                    employee = cur.fetchone()
                    if employee:
                        employee_id = employee['id']
        except Exception as e:
            logger.error(f"Error fetching employee for user {user_id}: {e}")
    
    # Get initials from full name
    name_parts = user_full_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[1][0]}".upper()
    else:
        initials = user_full_name[:2].upper() if len(user_full_name) >= 2 else user_full_name[0].upper()
    
    return render_template('user-first.html', 
                         user_full_name=user_full_name,
                         user_role=user_role,
                         user_initials=initials,
                         employee_id=employee_id)



@app.route('/sidebar-test')
def sidebar_test():
    """Test route for sidebar functionality"""
    return render_template('sidebar_test.html')


@app.route('/submit-report', methods=['GET', 'POST'])
def submit_report():
    """Submit production report - accessible without login for demonstration purposes"""
    if request.method == 'POST':
        try:
            # Extract form data
            date = request.form.get('date')
            submitted_by = request.form.get('submitted_by', '').strip()
            day_of_week = request.form.get('day_of_week')
            shift = request.form.get('shift')
            item_no = request.form.get('item_no', '').strip()
            cases_scheduled = request.form.get('cases_scheduled')
            cases_produced = request.form.get('cases_produced')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            waste_lbs = request.form.get('waste_lbs')
            std = request.form.get('std')

            # Validate required fields
            required_fields = {
                'date': date,
                'submitted_by': submitted_by,
                'day_of_week': day_of_week,
                'shift': shift,
                'item_no': item_no,
                'cases_scheduled': cases_scheduled,
                'cases_produced': cases_produced,
                'start_time': start_time,
                'end_time': end_time,
                'waste_lbs': waste_lbs,
                'std': std
            }

            missing_fields = [field for field, value in required_fields.items() if not value]
            
            if missing_fields:
                flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
                return render_template('Submit-report.html', 
                                     user_full_name=session.get('user_full_name', 'Demo User'),
                                     current_date=datetime.now().strftime('%Y-%m-%d'),
                                     form_data=request.form)

            # Store the submission in database
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO production_reports 
                        (date, submitted_by, day_of_week, shift, item_no, cases_scheduled, 
                         cases_produced, start_time, end_time, waste_lbs, std, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (date, submitted_by, day_of_week, shift, item_no, cases_scheduled,
                          cases_produced, start_time, end_time, waste_lbs, std))
                    conn.commit()

            # Log the submission
            log_submission(
                user_id=session.get('user_id'),
                user_name=submitted_by,
                user_email=session.get('user_email', ''),
                submission_type='production_report',
                message=f"Production report submitted for {date} - {shift} shift",
                success=True
            )

            flash("Production report submitted successfully!", "success")
            return redirect(url_for('submit_report'))

        except Exception as e:
            logger.error(f"Error submitting production report: {e}")
            flash("An error occurred while submitting the report. Please try again.", "error")
            return render_template('Submit-report.html', 
                                 user_full_name=session.get('user_full_name', 'Demo User'),
                                 current_date=datetime.now().strftime('%Y-%m-%d'),
                                 form_data=request.form)

    # GET request - display the form
    return render_template('Submit-report.html', 
                         user_full_name=session.get('user_full_name', 'Demo User'),
                         current_date=datetime.now().strftime('%Y-%m-%d'))


@app.route('/user-management')
@admin_required
def user_management():
    """Render the user management page"""
    try:
        return render_template('user_management.html', user_full_name=session.get('user_full_name', 'User'))
    except Exception as e:
        print(f"Error rendering user management page: {e}")
        return render_template('dashboard.html', user_full_name=session.get('user_full_name', 'User'))



@app.route('/profile', methods=['GET', 'POST'])
@login_required
@password_change_required
@add_cache_control_headers
def profile():
    user_id = session.get('user_id')
    message = None

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if request.method == 'POST':
                    phone = request.form.get('phone', '').strip()
                    
                    if phone:
                        # Basic phone validation
                        phone_pattern = r'^\+1\d{10}$|^\(\d{3}\)\s*\d{3}-\d{4}$|^\d{3}-\d{3}-\d{4}$'
                        if not re.match(phone_pattern, phone):
                            message = "⚠️ Please enter a valid phone number"
                        else:
                            cur.execute("""
                                UPDATE users SET phone = %s, updated_at = CURRENT_TIMESTAMP 
                                WHERE id = %s
                            """, (phone, user_id))
                            conn.commit()
                            message = "✅ Phone number updated successfully"

                # Get current user data
                cur.execute("""
                    SELECT email, first_name, last_name, phone 
                    FROM users WHERE id = %s
                """, (user_id,))
                user_data = cur.fetchone()

                return render_template('profile.html', 
                                     email=user_data['email'],
                                     first_name=user_data['first_name'],
                                     last_name=user_data['last_name'], 
                                     phone=user_data['phone'] or '',
                                     message=message)

    except Exception as e:
        logger.error(f"Profile error: {e}")
        return render_template('profile.html', 
                             email=session.get('email', ''),
                             phone='', 
                             message="An error occurred.")

@app.route('/first-time-password-setup', methods=['GET', 'POST'])
@login_required
def first_time_password_setup():
    """Allow first-time users to set their password without providing old password"""
    # Only allow this for first-time login users
    if not session.get('first_time_login'):
        flash("This page is only accessible for first-time password setup.", "warning")
        return redirect(url_for('dashboard'))
    
    if request.method == 'GET':
        return render_template('set_password.html', first_time=True)

    user_id = session.get('user_id')
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not all([new_password, confirm_password]):
        flash("Both password fields are required.", "danger")
        return render_template('set_password.html', first_time=True)

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return render_template('set_password.html', first_time=True)

    # Password strength validation
    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "danger")
        return render_template('set_password.html', first_time=True)

    if not re.search(r"[A-Z]", new_password):
        flash("Password must contain at least one uppercase letter.", "danger")
        return render_template('set_password.html', first_time=True)

    if not re.search(r"[a-z]", new_password):
        flash("Password must contain at least one lowercase letter.", "danger")
        return render_template('set_password.html', first_time=True)

    if not re.search(r"[0-9]", new_password):
        flash("Password must contain at least one number.", "danger")
        return render_template('set_password.html', first_time=True)

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
        flash("Password must contain at least one special character.", "danger")
        return render_template('set_password.html', first_time=True)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Update password and clear password_change_required flag
                new_password_hash = hash_password(new_password)
                
                # Check if password_change_required column exists and update accordingly
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'password_change_required'
                """)
                column_exists = cur.fetchone()
                
                if column_exists:
                    cur.execute("""
                        UPDATE users SET 
                            password_hash = %s, 
                            password_change_required = false,
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (new_password_hash, user_id))
                else:
                    cur.execute("""
                        UPDATE users SET 
                            password_hash = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (new_password_hash, user_id))
                
                conn.commit()

                # Log the password change
                log_submission(
                    user_id, 
                    session.get('user_full_name'), 
                    session.get('email'), 
                    'password_change', 
                    'First-time password setup completed'
                )

                # Clear session to force re-authentication with new password
                session.clear()
                
                # Redirect to congratulatory success page
                return redirect(url_for('password_success'))

    except Exception as e:
        logger.error(f"First-time password setup error: {e}")
        flash("An error occurred while setting your password.", "danger")
        return render_template('set_password.html', first_time=True)

@app.route('/password-success')
def password_success():
    """Display congratulatory page after successful first-time password setup"""
    return render_template('password_success.html')

@app.route('/set-password', methods=['GET', 'POST'])
@login_required
def set_password():
    """Allow users to change their password"""
    if request.method == 'GET':
        return render_template('set_password.html')

    user_id = session.get('user_id')
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not all([old_password, new_password, confirm_password]):
        flash("All fields are required.", "danger")
        return render_template('set_password.html')

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return render_template('set_password.html')

    # Password strength validation
    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "danger")
        return render_template('set_password.html')

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get current password hash
                cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
                user_data = cur.fetchone()
                
                if not user_data or not verify_password(old_password, user_data[0]):
                    flash("Current password is incorrect.", "danger")
                    return render_template('set_password.html')

                # Update password and mark password change as completed (if column exists)
                new_password_hash = hash_password(new_password)
                
                # Check if password_change_required column exists
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'password_change_required'
                """)
                column_exists = cur.fetchone()
                
                if column_exists:
                    # Column exists, update password and mark as completed
                    cur.execute("""
                        UPDATE users SET 
                            password_hash = %s, 
                            password_change_required = false,
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (new_password_hash, user_id))
                else:
                    # Column doesn't exist yet, just update password
                    cur.execute("""
                        UPDATE users SET 
                            password_hash = %s,
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (new_password_hash, user_id))
                
                conn.commit()

                flash("Password updated successfully! Please log in again with your new password.", "success")
                
                # Clear session to force re-authentication
                session.clear()
                
                # Redirect to login page
                return redirect(url_for('login'))

    except Exception as e:
        logger.error(f"Password change error: {e}")
        flash("An error occurred while updating password.", "danger")
        return render_template('set_password.html')

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@app.route('/form')
@login_required
@password_change_required
@add_cache_control_headers
def form():
    latest_week = get_latest_week_sheet()
    all_weeks = get_all_week_sheets()
    week_options = [ws['sheet_name'] for ws in all_weeks] if all_weeks else []
    
    user_full_name = session.get('user_full_name', 'User')
    user_id = session.get('user_id')
    user_role = session.get('user_role', 'user')
    
    logger.info(f"Form page accessed - user_id: {user_id}, user_full_name: '{user_full_name}', user_role: '{user_role}'")
    
    return render_template('form.html',
                          latest_week=latest_week,
                          week_options=week_options,
                          user_full_name=user_full_name,
                          user_role=user_role)

@app.route('/submit', methods=['POST'])
@login_required
@password_change_required
def submit():
    user_id = session.get('user_id')
    user_name = session.get('user_full_name')
    user_email = session.get('email')
    user_role = session.get('user_role', 'user')
    
    logger.info(f"Form submission started by user {user_name} ({user_id}) with role: {user_role}")
    
    # Role-based access control - prevent users with 'user' role from submitting
    if user_role == 'user':
        logger.warning(f"Access denied: User {user_name} ({user_id}) with 'user' role attempted to submit metrics data")
        
        # Check if this is an AJAX request
        is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                   'application/json' in request.headers.get('Accept', '') or
                   request.headers.get('Content-Type') == 'application/json')
        
        if is_ajax:
            return jsonify({
                'success': False,
                'error': 'Access denied: You do not have permission to submit bakery metrics data. Please contact your supervisor.'
            }), 403
        else:
            flash('Access denied: You do not have permission to submit bakery metrics data. Please contact your supervisor.', 'error')
            return redirect(url_for('form'))
    
    # Check if this is an AJAX request
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
               'application/json' in request.headers.get('Accept', '') or
               request.headers.get('Content-Type', '').startswith('multipart/form-data'))
    
    logger.info(f"Request type: {'AJAX' if is_ajax else 'HTML'}")
    logger.info(f"Form data keys: {list(request.form.keys())}")
    
    # Get form data using new field names
    week_name = request.form.get('week_name')
    day_of_week = request.form.get('day_of_week')
    submitted_by = request.form.get('submitted_by', user_name)
    local_timestamp = request.form.get('local_timestamp')
    
    logger.info(f"Basic form data - Week: {week_name}, Day: {day_of_week}, Submitted by: {submitted_by}")

    if not week_name or not day_of_week:
        error_msg = "Invalid week or day provided."
        if is_ajax:
            return jsonify({'success': False, 'message': error_msg}), 400
        else:
            flash(error_msg, "danger")
            return redirect(url_for('form'))

    # Validate day
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if day_of_week not in valid_days:
        error_msg = "Invalid day provided."
        if is_ajax:
            return jsonify({'success': False, 'message': error_msg}), 400
        else:
            flash(error_msg, "danger")
            return redirect(url_for('form'))

    # New field mapping for the updated database schema
    first_shift_fields = [
        'first_die_cut1_oee_pct', 'first_die_cut2_oee_pct',
        'first_die_cut1_pounds', 'first_die_cut2_pounds',
        'first_die_cut1_waste_lbs', 'first_die_cut2_waste_lbs'
    ]
    
    second_shift_fields = [
        'second_die_cut1_oee_pct', 'second_die_cut2_oee_pct',
        'second_die_cut1_pounds', 'second_die_cut2_pounds',
        'second_die_cut1_waste_lbs', 'second_die_cut2_waste_lbs'
    ]

    try:
        logger.info("Starting database transaction")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if a record already exists for this day and week
                logger.info(f"Checking for existing record with: week_name={week_name}, day_of_week={day_of_week}")
                
                cur.execute("""
                    SELECT id FROM week_submissions
                    WHERE week_name = %s AND day_of_week = %s
                """, (week_name, day_of_week))
                
                existing_record = cur.fetchone()
                
                if existing_record:
                    error_msg = f"A record already exists for {day_of_week} in week {week_name}. Submission blocked to prevent data overwriting."
                    logger.warning(f"Submission blocked: {error_msg}")
                    
                    if is_ajax:
                        return jsonify({
                            'success': False,
                            'message': error_msg,
                            'error_type': 'duplicate_record'
                        }), 409  # 409 Conflict status code
                    else:
                        flash(error_msg, "error")
                        return redirect(url_for('form'))
                
                # No existing record found, proceed with insertion
                logger.info(f"No existing record found. Creating new week submission for: week_name={week_name}, day_of_week={day_of_week}")
                
                cur.execute("""
                    INSERT INTO week_submissions (week_name, day_of_week, week_start, week_end, submitted_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (week_name, day_of_week, '2024-01-01', '2024-01-07', user_name))
                
                week_submission_id = cur.fetchone()[0]
                logger.info(f"Week submission ID: {week_submission_id}")
                
                updated = False
                processed_metrics = []

                # Process first shift metrics
                first_shift_data = {}
                for field_name in first_shift_fields:
                    value = request.form.get(field_name)
                    if value and value.strip() and value.strip() != "0":
                        first_shift_data[field_name] = float(value)
                        processed_metrics.append({
                            'field': field_name,
                            'shift': 'first',
                            'value': float(value)
                        })

                if first_shift_data:
                    logger.info(f"Processing first shift data: {first_shift_data}")
                    # Insert/update first shift metrics (using correct column names)
                    try:
                        cur.execute("""
                            INSERT INTO first_shift_metrics (
                                week_submission_id, die_cut1_oee_pct, die_cut2_oee_pct,
                                die_cut1_lbs, die_cut2_lbs,
                                die_cut1_waste_lb, die_cut2_waste_lb,
                                submitted_by
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s
                            ) ON CONFLICT (week_submission_id) DO UPDATE SET
                                die_cut1_oee_pct = COALESCE(EXCLUDED.die_cut1_oee_pct, first_shift_metrics.die_cut1_oee_pct),
                                die_cut2_oee_pct = COALESCE(EXCLUDED.die_cut2_oee_pct, first_shift_metrics.die_cut2_oee_pct),
                                die_cut1_lbs = COALESCE(EXCLUDED.die_cut1_lbs, first_shift_metrics.die_cut1_lbs),
                                die_cut2_lbs = COALESCE(EXCLUDED.die_cut2_lbs, first_shift_metrics.die_cut2_lbs),
                                die_cut1_waste_lb = COALESCE(EXCLUDED.die_cut1_waste_lb, first_shift_metrics.die_cut1_waste_lb),
                                die_cut2_waste_lb = COALESCE(EXCLUDED.die_cut2_waste_lb, first_shift_metrics.die_cut2_waste_lb),
                                submitted_by = EXCLUDED.submitted_by
                        """, (
                            week_submission_id,
                            first_shift_data.get('first_die_cut1_oee_pct'),
                            first_shift_data.get('first_die_cut2_oee_pct'),
                            first_shift_data.get('first_die_cut1_pounds'),
                            first_shift_data.get('first_die_cut2_pounds'),
                            first_shift_data.get('first_die_cut1_waste_lbs'),
                            first_shift_data.get('first_die_cut2_waste_lbs'),
                            user_name
                        ))
                        logger.info("First shift metrics inserted successfully")
                        updated = True
                    except Exception as e:
                        logger.error(f"Error inserting first shift metrics: {e}")
                        raise

                # Process second shift metrics
                second_shift_data = {}
                for field_name in second_shift_fields:
                    value = request.form.get(field_name)
                    if value and value.strip() and value.strip() != "0":
                        second_shift_data[field_name] = float(value)
                        processed_metrics.append({
                            'field': field_name,
                            'shift': 'second',
                            'value': float(value)
                        })

                if second_shift_data:
                    logger.info(f"Processing second shift data: {second_shift_data}")
                    # Insert/update second shift metrics (using correct column names)
                    try:
                        cur.execute("""
                            INSERT INTO second_shift_metrics (
                                week_submission_id, die_cut1_oee_pct, die_cut2_oee_pct,
                                die_cut1_lbs, die_cut2_lbs,
                                die_cut1_waste_lb, die_cut2_waste_lb,
                                submitted_by
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s
                            ) ON CONFLICT (week_submission_id) DO UPDATE SET
                                die_cut1_oee_pct = COALESCE(EXCLUDED.die_cut1_oee_pct, second_shift_metrics.die_cut1_oee_pct),
                                die_cut2_oee_pct = COALESCE(EXCLUDED.die_cut2_oee_pct, second_shift_metrics.die_cut2_oee_pct),
                                die_cut1_lbs = COALESCE(EXCLUDED.die_cut1_lbs, second_shift_metrics.die_cut1_lbs),
                                die_cut2_lbs = COALESCE(EXCLUDED.die_cut2_lbs, second_shift_metrics.die_cut2_lbs),
                                die_cut1_waste_lb = COALESCE(EXCLUDED.die_cut1_waste_lb, second_shift_metrics.die_cut1_waste_lb),
                                die_cut2_waste_lb = COALESCE(EXCLUDED.die_cut2_waste_lb, second_shift_metrics.die_cut2_waste_lb),
                                submitted_by = EXCLUDED.submitted_by
                        """, (
                            week_submission_id,
                            second_shift_data.get('second_die_cut1_oee_pct'),
                            second_shift_data.get('second_die_cut2_oee_pct'),
                            second_shift_data.get('second_die_cut1_pounds'),
                            second_shift_data.get('second_die_cut2_pounds'),
                            second_shift_data.get('second_die_cut1_waste_lbs'),
                            second_shift_data.get('second_die_cut2_waste_lbs'),
                            user_name
                        ))
                        logger.info("Second shift metrics inserted successfully")
                        updated = True
                    except Exception as e:
                        logger.error(f"Error inserting second shift metrics: {e}")
                        raise

                logger.info("Committing database transaction")
                conn.commit()
                logger.info("Database transaction committed successfully")

                message = "✅ Submission successful." if updated else "⚠️ No new data submitted."
                
                # Log submission
                log_submission(
                    user_id, user_name, user_email, 'metrics',
                    message, week_sheet=week_name, day_of_week=day_of_week, success=updated
                )

                logger.info(f"Form submission completed successfully: {message}")

                # Send email notification to all users if submission was successful
                if updated:
                    try:
                        # Prepare metrics data for email
                        email_metrics_data = {
                            'first_shift': first_shift_data,
                            'second_shift': second_shift_data
                        }
                        send_metrics_notification(email_metrics_data, week_name, day_of_week, submitted_by)
                        logger.info("Email notification initiated for metrics submission")
                    except Exception as email_error:
                        # Don't let email errors affect the main submission
                        logger.error(f"Email notification failed (submission still successful): {email_error}")

                # Always return JSON response for the enhanced form
                return jsonify({
                    'success': updated,
                    'message': message,
                    'data': {
                        'week': week_name,
                        'day': day_of_week,
                        'submitted_by': submitted_by,
                        'timestamp': local_timestamp,
                        'processed_metrics': processed_metrics
                    }
                })

    except Exception as e:
        logger.error(f"Submission error: {e}", exc_info=True)
        error_msg = f"An error occurred during submission: {str(e)}"
        
        # Log failed submission
        log_submission(
            user_id, user_name, user_email, 'metrics',
            f"Submission failed: {error_msg}", week_sheet=week_name, day_of_week=day_of_week, success=False
        )
        
        return jsonify({'success': False, 'message': error_msg}), 500


# Test route for email functionality (can be removed in production)
@app.route('/test-email')
@login_required
def test_email():
    """Test route to verify email functionality - REMOVE IN PRODUCTION"""
    try:
        # Test data
        test_metrics = {
            'first_shift': {
                'first_die_cut1_oee_pct': 85.5,
                'first_die_cut2_oee_pct': 78.2,
                'first_die_cut1_pounds': 5500,
                'first_die_cut2_pounds': 4800,
                'first_die_cut1_waste_lbs': 120,
                'first_die_cut2_waste_lbs': 95
            },
            'second_shift': {
                'second_die_cut1_oee_pct': 82.1,
                'second_die_cut2_oee_pct': 75.9,
                'second_die_cut1_pounds': 5200,
                'second_die_cut2_pounds': 4600,
                'second_die_cut1_waste_lbs': 110,
                'second_die_cut2_waste_lbs': 88
            }
        }
        
        # Send test email
        success = send_metrics_notification(
            test_metrics, 
            "Test Week", 
            "Monday", 
            "Test User"
        )
        
        return jsonify({
            'success': success,
            'message': 'Test email sent' if success else 'Test email failed'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500



@app.route('/inventory')
@login_required
def inventory():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT item_code, item_name 
                    FROM inventory_items 
                    WHERE is_active = true 
                    ORDER BY item_code
                """)
                inventory_items = cur.fetchall()

        return render_template("inventory.html", sheet_options=inventory_items)

    except Exception as e:
        logger.error(f"Inventory page error: {e}")
        flash("Error loading inventory page.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/submit-inventory', methods=['POST'])
@login_required
def submit_inventory():
    user_id = session.get('user_id')
    user_email = session.get('email')

    try:
        # Get form data
        inventory_type = request.form.get("inventoryType", "received")
        item_code = request.form.get("item")
        shift = request.form.get("shift")
        lot_number = request.form.get("lotNumber", "")
        num_boxes = int(request.form.get("numBoxes", 0) or 0)
        num_bags = int(request.form.get("numBags", 0) or 0)
        dough_qty = float(request.form.get("doughQty", 0) or 0)
        beta_qty = float(request.form.get("betaQty", 0) or 0)

        current_time = datetime.now()
        weekday = current_time.strftime('%A')
        transaction_date = current_time.date()
        transaction_time = current_time.time()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get item ID
                cur.execute("""
                    SELECT id FROM inventory_items WHERE item_code = %s AND is_active = true
                """, (item_code,))
                
                item_result = cur.fetchone()
                if not item_result:
                    flash(f"Invalid inventory item: {item_code}", "danger")
                    return redirect(url_for('inventory'))

                item_id = item_result[0]

                # Insert inventory transaction (quantity will be calculated by trigger)
                cur.execute("""
                    INSERT INTO inventory_transactions (
                        item_id, transaction_type, shift_type, lot_number,
                        num_boxes, num_bags, dough_qty, beta_qty,
                        transaction_date, transaction_time, day_of_week, created_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    item_id, inventory_type, shift, lot_number,
                    num_boxes, num_bags, dough_qty, beta_qty,
                    transaction_date, transaction_time, weekday, user_id
                ))

                conn.commit()

                # Log submission
                log_submission(
                    user_id, session.get('user_full_name'), user_email, 'inventory',
                    f"Inventory {inventory_type}: {item_code}"
                )

                return render_template("confirmation.html", 
                                     success=True, 
                                     name=session.get('user_full_name'),
                                     timestamp=current_time.strftime('%I:%M:%S %p'))

    except Exception as e:
        logger.error(f"Inventory submission error: {e}")
        return render_template("confirmation.html", 
                             success=False, 
                             name=session.get('user_full_name', 'Unknown'),
                             timestamp=datetime.now().strftime('%I:%M:%S %p'))

@app.route('/report')
@login_required
def report():
    week_sheets = get_all_week_sheets()
    default_week = week_sheets[0]['sheet_name'] if week_sheets else ""
    
    return render_template('report.html', 
                          week_names=[ws['sheet_name'] for ws in week_sheets],
                          default_week=default_week,
                          user_full_name=session.get('user_full_name', 'User'))

@app.route('/inventory-overview')
@login_required
def inventory_overview():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT item_code, item_name
                    FROM inventory_items
                    WHERE is_active = true
                    ORDER BY item_code
                """)
                inventory_items = cur.fetchall()

        return render_template("inventory_overview.html",
                             sheet_names=[item['item_code'] for item in inventory_items])

    except Exception as e:
        logger.error(f"Inventory overview error: {e}")
        flash("Error loading inventory overview.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/issues')
@login_required
def issues():
    return render_template('issues.html')

# API Routes for Admin Functions
@app.route('/api/register-key', methods=['POST'])
@admin_required
def api_register_key():
    """Legacy API for access key registration - now creates user invitation"""
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    
    if not all([email, first_name, last_name]):
        return jsonify({"message": "Email, first name, and last name are required.", "status": "danger"})

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user already exists
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    return jsonify({"message": "User already exists with this email.", "status": "warning"})

                # Create user with temporary password (they'll need to set it on first login)
                temp_password = str(uuid.uuid4())[:12] + "Temp!"
                password_hash = hash_password(temp_password)
                user_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO users (id, email, first_name, last_name, password_hash, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, email, first_name, last_name, password_hash, 'user'))
                
                conn.commit()

                return jsonify({
                    "message": f"User invitation sent to {email}. Temporary password: {temp_password}",
                    "status": "success"
                })

    except Exception as e:
        logger.error(f"User registration error: {e}")
        return jsonify({"message": f"Error: {str(e)}", "status": "danger"})

@app.route('/api/users', methods=['GET', 'POST'])
@admin_required
def api_users():
    if request.method == 'GET':
        try:
            # Check if we should filter by role (for employee linking)
            # Supports single role or comma-separated roles (e.g., 'user,employee')
            role_filter = request.args.get('role', None)
            
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Build query based on role filter
                    if role_filter:
                        # Support comma-separated roles
                        roles = [r.strip() for r in role_filter.split(',')]
                        if len(roles) > 1:
                            # Multiple roles - use IN clause
                            placeholders = ','.join(['%s'] * len(roles))
                            cur.execute(f"""
                                SELECT id, email, first_name, last_name, phone, role, created_at, last_login, is_active
                                FROM users 
                                WHERE role IN ({placeholders}) AND is_active = TRUE
                                ORDER BY email
                            """, roles)
                        else:
                            # Single role
                            cur.execute("""
                                SELECT id, email, first_name, last_name, phone, role, created_at, last_login, is_active
                                FROM users 
                                WHERE role = %s AND is_active = TRUE
                                ORDER BY email
                            """, (roles[0],))
                    else:
                        cur.execute("""
                            SELECT id, email, first_name, last_name, phone, role, created_at, last_login, is_active
                            FROM users 
                            ORDER BY created_at DESC
                        """)
                    
                    users = cur.fetchall()

                    formatted_users = []
                    dropdown = []
                    
                    for user in users:
                        # Debug logging for phone data
                        if user['email'] == 'geraldnyah4@gmail.com':
                            logger.info(f"DEBUG: User {user['email']} phone data: '{user['phone']}'")
                            logger.info(f"DEBUG: User object keys: {list(user.keys())}")
                        
                        formatted_users.append({
                            "id": str(user['id']),
                            "email": user['email'],
                            "first": user['first_name'],
                            "last": user['last_name'],
                            "first_name": user['first_name'],  # Add for employee linking
                            "last_name": user['last_name'],    # Add for employee linking
                            "phone": user['phone'],
                            "role": user['role'],
                            "created": user['created_at'].strftime('%Y-%m-%d') if user['created_at'] else '',
                            "last_login": user['last_login'].strftime('%Y-%m-%d %H:%M') if user['last_login'] else 'Never',
                            "is_active": user['is_active']
                        })
                        dropdown.append(f"{user['email']}_{user['last_name']}")

                    response_data = {
                        "success": True,  # Add success flag for consistency
                        "users": formatted_users, 
                        "dropdown": dropdown
                    }
                    response = jsonify(response_data)
                    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                    response.headers['Pragma'] = 'no-cache'
                    response.headers['Expires'] = '0'
                    return response

        except Exception as e:
            logger.error(f"Get users error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Debug logging
            logger.info(f"Received user creation data: {data}")
            
            # Validate required fields
            required_fields = ['first_name', 'last_name', 'email', 'role', 'password']
            for field in required_fields:
                if not data.get(field):
                    logger.warning(f"Missing required field: {field}, received data: {data}")
                    return jsonify({
                        'success': False,
                        'message': f'Missing required field: {field}'
                    }), 400
            
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone', '').strip() or None
            role = data.get('role', '').strip()
            password = data.get('password', '').strip()
            is_active = data.get('is_active', True)  # Default to True if not provided
            
            # Validate that required fields are not empty after trimming
            if not first_name:
                return jsonify({
                    'success': False,
                    'message': 'First name is required'
                }), 400
            if not last_name:
                return jsonify({
                    'success': False,
                    'message': 'Last name is required'
                }), 400
            if not email:
                return jsonify({
                    'success': False,
                    'message': 'Email is required'
                }), 400
            if not role:
                return jsonify({
                    'success': False,
                    'message': 'Role is required'
                }), 400
            if not password:
                return jsonify({
                    'success': False,
                    'message': 'Password is required'
                }), 400
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return jsonify({
                    'success': False,
                    'message': 'Invalid email format'
                }), 400
            
            # No password restrictions for admin-created accounts
            # Users will be prompted to create secure passwords on first login
            # Just log the creation for security audit
            logger.info(f"Admin creating temporary password for user: {email}")
            
            # Validate role
            valid_roles = ['admin', 'user', 'supervisor', 'employee']
            if role not in valid_roles:
                return jsonify({
                    'success': False,
                    'message': f'Invalid role. Must be one of: {", ".join(valid_roles)}'
                }), 400
            
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check if email already exists
                    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cur.fetchone():
                        return jsonify({
                            'success': False,
                            'message': 'Email already exists'
                        }), 400
                    
                    # Hash the password using bcrypt for enhanced security
                    import bcrypt
                    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
                    hashed_password_str = hashed_password.decode('utf-8')
                    
                    # Insert new user
                    cur.execute("""
                        INSERT INTO users (first_name, last_name, email, phone, role, password_hash, is_active, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        RETURNING id
                    """, (first_name, last_name, email, phone, role, hashed_password_str, is_active))
                    
                    user_id = cur.fetchone()[0]
                    conn.commit()
                    
                    # Log the user creation
                    current_user_id = session.get('user_id')
                    current_user_name = session.get('user_full_name')
                    current_user_email = session.get('email')
                    
                    log_submission(
                        current_user_id, current_user_name, current_user_email,
                        'user_create',
                        f'User created: {first_name} {last_name} ({email}) with role {role}'
                    )
                    
                    return jsonify({
                        'success': True,
                        'message': f'User created successfully with secure password',
                        'user_id': str(user_id)
                    })
                    
        except Exception as e:
            logger.error(f"Create user error: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to create user: {str(e)}'
                    }), 500

# Debug route to test API authentication and response format
@app.route('/api/debug-auth', methods=['GET', 'POST'])
@admin_required
def debug_auth():
    """Debug endpoint to test API authentication and response format"""
    try:
        return jsonify({
            'success': True,
            'message': 'Authentication working',
            'user_id': session.get('user_id'),
            'user_role': session.get('user_role'),
            'is_admin': session.get('is_admin'),
            'admin_verified': session.get('admin_verified'),
            'verified': session.get('verified'),
            'content_type': request.headers.get('Content-Type'),
            'accept': request.headers.get('Accept')
        })
    except Exception as e:
        logger.error(f"Debug auth error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========================================================
# EMAIL MANAGEMENT API ENDPOINTS
# ========================================================

@app.route('/api/email-recipients', methods=['GET'])
@admin_required
def get_email_recipients():
    """Get saved email recipients preferences."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get users with their email preferences
                cur.execute("""
                    SELECT 
                        u.id,
                        u.email,
                        u.first_name,
                        u.last_name,
                        COALESCE(enp.is_enabled, true) as email_notifications_enabled
                    FROM users u
                    LEFT JOIN email_notification_preferences enp 
                        ON u.id = enp.user_id AND enp.preference_type = 'automatic'
                    WHERE u.is_active = true
                    ORDER BY u.first_name, u.last_name, u.email
                """)
                
                users_preferences = cur.fetchall()
                
                return jsonify({
                    "success": True,
                    "users": [dict(user) for user in users_preferences]
                })
        
    except Exception as e:
        logger.error(f"Error getting email recipients: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to get email recipients: {str(e)}"
        }), 500

@app.route('/api/email-recipients', methods=['POST'])
@admin_required
def save_email_recipients():
    """Save email notification preferences for users."""
    try:
        data = request.get_json()
        preferences = data.get('preferences', [])
        current_user_id = session.get('user_id')
        
        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "User not authenticated"
            }), 401
        
        if not preferences:
            return jsonify({
                "success": False,
                "message": "No preferences provided"
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Update or insert preferences for each user
                for pref in preferences:
                    user_id = pref.get('user_id')
                    enabled = pref.get('enabled', False)
                    
                    if not user_id:
                        continue
                    
                    cur.execute("""
                        INSERT INTO email_notification_preferences 
                        (user_id, is_enabled, preference_type, created_by)
                        VALUES (%s, %s, 'automatic', %s)
                        ON CONFLICT (user_id, preference_type) 
                        DO UPDATE SET 
                            is_enabled = %s,
                            updated_at = CURRENT_TIMESTAMP,
                            created_by = %s
                    """, (user_id, enabled, current_user_id, enabled, current_user_id))
                
                conn.commit()
                
                enabled_count = sum(1 for pref in preferences if pref.get('enabled', False))
                
                return jsonify({
                    "success": True,
                    "message": f"Email preferences updated successfully ({enabled_count} users will receive notifications)"
                })
        
    except Exception as e:
        logger.error(f"Error saving email recipients: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to save email recipients: {str(e)}"
        }), 500

@app.route('/api/send-manual-email', methods=['POST'])
@admin_required
def send_manual_email_alert():
    """Send manual email alert for specific day with PDF attachments."""
    try:
        logger.info(f"Manual email request received from user: {session.get('user_id')}")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Session data: user_id={session.get('user_id')}, role={session.get('user_role')}")
        
        # Validate session first
        if not session.get('user_id'):
            logger.warning("No user_id in session for manual email request")
            return jsonify({
                "success": False,
                "message": "Authentication required - no user session"
            }), 401
        
        if session.get('user_role') != 'admin':
            logger.warning(f"Non-admin user {session.get('user_id')} attempted manual email")
            return jsonify({
                "success": False,
                "message": "Admin access required"
            }), 403
        
        # Capture user_id from session before starting background thread
        current_user_id = session.get('user_id')
        
        data = request.get_json()
        if not data:
            logger.warning("No JSON data received in manual email request")
            return jsonify({
                "success": False,
                "message": "No data received - ensure Content-Type is application/json"
            }), 400
        
        week_name = data.get('week_name')
        day_of_week = data.get('day_of_week')
        recipient_ids = data.get('recipient_ids', [])
        include_daily_pdf = data.get('include_daily_pdf', True)
        include_weekly_pdf = data.get('include_weekly_pdf', True)
        
        logger.info(f"Manual email parameters: week={week_name}, day={day_of_week}, recipients={len(recipient_ids)}")
        
        if not week_name or not day_of_week:
            return jsonify({
                "success": False,
                "message": "Week name and day of week are required"
            }), 400
            
        if not recipient_ids:
            return jsonify({
                "success": False,
                "message": "At least one recipient must be selected"
            }), 400
        
        # Get the metrics data for the specified day
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        ws.id, ws.week_name, ws.day_of_week, ws.created_at as submitted_at,
                        ws.submitted_by,
                        -- First shift data
                        fs.die_cut1_oee_pct as first_die_cut1_oee_pct,
                        fs.die_cut2_oee_pct as first_die_cut2_oee_pct,
                        fs.die_cut1_lbs as first_die_cut1_pounds,
                        fs.die_cut2_lbs as first_die_cut2_pounds,
                        fs.die_cut1_waste_lb as first_die_cut1_waste_lbs,
                        fs.die_cut2_waste_lb as first_die_cut2_waste_lbs,
                        -- Second shift data
                        ss.die_cut1_oee_pct as second_die_cut1_oee_pct,
                        ss.die_cut2_oee_pct as second_die_cut2_oee_pct,
                        ss.die_cut1_lbs as second_die_cut1_pounds,
                        ss.die_cut2_lbs as second_die_cut2_pounds,
                        ss.die_cut1_waste_lb as second_die_cut1_waste_lbs,
                        ss.die_cut2_waste_lb as second_die_cut2_waste_lbs
                    FROM week_submissions ws
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    WHERE ws.week_name = %s AND ws.day_of_week = %s
                    ORDER BY ws.created_at DESC
                    LIMIT 1
                """, (week_name, day_of_week))
                metrics_data = cur.fetchone()
        
        if not metrics_data:
            return jsonify({
                "success": False,
                "message": f"No metrics data found for {week_name} - {day_of_week}"
            }), 404
        
        # Get recipient details including names for personalization
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                placeholders = ','.join(['%s'] * len(recipient_ids))
                cur.execute(f"""
                    SELECT id, email, first_name, last_name FROM users 
                    WHERE id IN ({placeholders}) AND is_active = true
                """, recipient_ids)
                recipient_users = cur.fetchall()
        
        if not recipient_users:
            return jsonify({
                "success": False,
                "message": "No valid recipients found"
            }), 400
        
        # Convert metrics_data to the format expected by email function
        email_metrics_data = {
            'first_shift': {
                'first_die_cut1_oee_pct': metrics_data.get('first_die_cut1_oee_pct'),
                'first_die_cut2_oee_pct': metrics_data.get('first_die_cut2_oee_pct'),
                'first_die_cut1_pounds': metrics_data.get('first_die_cut1_pounds'),
                'first_die_cut2_pounds': metrics_data.get('first_die_cut2_pounds'),
                'first_die_cut1_waste_lbs': metrics_data.get('first_die_cut1_waste_lbs'),
                'first_die_cut2_waste_lbs': metrics_data.get('first_die_cut2_waste_lbs')
            },
            'second_shift': {
                'second_die_cut1_oee_pct': metrics_data.get('second_die_cut1_oee_pct'),
                'second_die_cut2_oee_pct': metrics_data.get('second_die_cut2_oee_pct'),
                'second_die_cut1_pounds': metrics_data.get('second_die_cut1_pounds'),
                'second_die_cut2_pounds': metrics_data.get('second_die_cut2_pounds'),
                'second_die_cut1_waste_lbs': metrics_data.get('second_die_cut1_waste_lbs'),
                'second_die_cut2_waste_lbs': metrics_data.get('second_die_cut2_waste_lbs')
            }
        }
        
        # Create email content with simplified format
        subject = "Daily and Weekly Bakery Metrics"
        
        # Send email with PDF attachments
        def send_email():
            daily_pdf_path = None
            weekly_pdf_path = None
            
            try:
                with app.app_context():
                    # Create PDF attachments if requested
                    if include_daily_pdf:
                        daily_pdf_path = create_daily_metrics_pdf(week_name, day_of_week)
                    if include_weekly_pdf:
                        weekly_pdf_path = create_weekly_summary_pdf(week_name)
                    
                    # Send personalized emails to each recipient
                    for user in recipient_users:
                        # Get user's full name or use first name as fallback
                        first_name = user.get('first_name', '').strip()
                        last_name = user.get('last_name', '').strip()
                        
                        if first_name:
                            recipient_name = first_name
                        elif first_name and last_name:
                            recipient_name = f"{first_name} {last_name}".strip()
                        else:
                            # Fallback to extracting name from email if no name is available
                            email_name = user['email'].split('@')[0].replace('.', ' ').replace('_', ' ').title()
                            recipient_name = email_name
                        
                        # Create personalized email content
                        html_content = create_simple_metrics_email_html(recipient_name)
                        
                        # Create email message for this specific recipient
                        msg = Message(
                            subject=subject,
                            recipients=[user['email']],
                            html=html_content,
                            sender=app.config['MAIL_DEFAULT_SENDER']
                        )
                        
                        # Attach PDFs if they were created successfully
                        if daily_pdf_path and os.path.exists(daily_pdf_path):
                            with open(daily_pdf_path, 'rb') as f:
                                msg.attach(
                                    filename=f"Daily_Metrics_{week_name}_{day_of_week}.pdf",
                                    content_type="application/pdf",
                                    data=f.read()
                                )
                            logger.info(f"Attached daily metrics PDF for {week_name} {day_of_week}")
                        
                        if weekly_pdf_path and os.path.exists(weekly_pdf_path):
                            with open(weekly_pdf_path, 'rb') as f:
                                msg.attach(
                                    filename=f"Weekly_Summary_{week_name}.pdf",
                                    content_type="application/pdf",
                                    data=f.read()
                                )
                            logger.info(f"Attached weekly summary PDF for {week_name}")
                        
                        # Send email to this recipient
                        mail.send(msg)
                        logger.info(f"Manual email alert sent to {user['email']} (as {recipient_name})")
                    
                    logger.info(f"Manual email alert sent successfully to {len(recipient_users)} recipients")
                    
                    # Log the email activity
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO email_activity_log 
                                (type, week_name, day_of_week, recipient_count, status, sent_at, sent_by)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                'manual', week_name, day_of_week, len(recipient_users), 
                                'sent', datetime.now(), current_user_id
                            ))
                        conn.commit()
                    
            except Exception as e:
                logger.error(f"Failed to send manual email alert: {e}")
                # Log the failed attempt
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO email_activity_log 
                                (type, week_name, day_of_week, recipient_count, status, sent_at, sent_by, error_message)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                'manual', week_name, day_of_week, len(recipient_users), 
                                'failed', datetime.now(), current_user_id, str(e)
                            ))
                        conn.commit()
                except:
                    pass
            finally:
                # Clean up temporary PDF files
                for pdf_path in [daily_pdf_path, weekly_pdf_path]:
                    if pdf_path and os.path.exists(pdf_path):
                        try:
                            os.unlink(pdf_path)
                        except Exception as e:
                            logger.warning(f"Failed to clean up PDF file {pdf_path}: {e}")
        
        # Start email sending in a separate thread
        thread = threading.Thread(target=send_email)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "message": f"Email alert initiated for {len(recipient_users)} recipients"
        })
        
    except Exception as e:
        logger.error(f"Error sending manual email alert: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to send email alert: {str(e)}"
        }), 500

@app.route('/api/email-activity-log', methods=['GET'])
@admin_required
def get_email_activity_log():
    """Get email activity log with pagination."""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 5))
        offset = (page - 1) * per_page
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get total count
                cur.execute("SELECT COUNT(*) as total FROM email_activity_log")
                total_result = cur.fetchone()
                total_count = total_result['total'] if total_result else 0
                
                # Get paginated activities with user names
                cur.execute("""
                    SELECT 
                        eal.id,
                        eal.type as email_type,
                        eal.recipient_count as recipients_count,
                        eal.week_name,
                        eal.day_of_week,
                        eal.sent_at as sent_date,
                        eal.status,
                        eal.error_message,
                        eal.sent_by,
                        u.first_name,
                        u.last_name,
                        u.email as sent_by_email
                    FROM email_activity_log eal
                    LEFT JOIN users u ON eal.sent_by = u.id
                    ORDER BY eal.sent_at DESC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
                
                activities = cur.fetchall()
                
                # Convert to list of dictionaries with proper formatting
                activity_list = []
                for activity in activities:
                    # Format recipients display (since we don't have recipients_list, show count)
                    recipients_display = f"{activity['recipients_count']} recipients"
                    
                    # Format date/time
                    sent_date_formatted = activity['sent_date'].strftime('%Y-%m-%d %H:%M:%S') if activity['sent_date'] else 'N/A'
                    
                    # Determine type display
                    type_display = {
                        'automatic': 'Automatic',
                        'manual': 'Manual',
                        'test': 'Test'
                    }.get(activity['email_type'], activity['email_type'])
                    
                    # Status styling
                    status_class = {
                        'sent': 'success',
                        'failed': 'error',
                        'pending': 'warning'
                    }.get(activity['status'], 'default')
                    
                    # Format sent by name
                    sent_by_name = 'System'
                    if activity['first_name'] and activity['last_name']:
                        sent_by_name = f"{activity['first_name']} {activity['last_name']}"
                    elif activity['first_name']:
                        sent_by_name = activity['first_name']
                    
                    # Format week display
                    week_display = activity['week_name'] or 'N/A'
                    if activity['day_of_week']:
                        week_display += f" - {activity['day_of_week']}"
                    
                    activity_list.append({
                        'id': str(activity['id']),
                        'type': type_display,
                        'type_raw': activity['email_type'],
                        'recipients': recipients_display,
                        'recipients_count': activity['recipients_count'],
                        'week_name': week_display,
                        'sent_date': sent_date_formatted,
                        'sent_date_raw': activity['sent_date'].isoformat() if activity['sent_date'] else None,
                        'status': activity['status'],
                        'status_class': status_class,
                        'error_message': activity['error_message'],
                        'sent_by_name': sent_by_name,
                        'sent_by_email': activity['sent_by_email']
                    })
                
                # Calculate pagination info
                total_pages = (total_count + per_page - 1) // per_page
                has_next = page < total_pages
                has_prev = page > 1
                
                return jsonify({
                    "success": True,
                    "activities": activity_list,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total_count,
                        "total_pages": total_pages,
                        "has_next": has_next,
                        "has_prev": has_prev
                    }
                })
        
    except Exception as e:
        logger.error(f"Error getting email activity log: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to get email activity log: {str(e)}"
        }), 500

@app.route('/api/setup-email-activity-log', methods=['POST'])
@admin_required
def setup_email_activity_log():
    """Set up the email activity log table and populate with sample data."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Create the email_activity_log table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS email_activity_log (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email_type VARCHAR(20) NOT NULL CHECK (email_type IN ('automatic', 'manual', 'test')),
                        recipients_count INTEGER NOT NULL DEFAULT 0,
                        recipients_list TEXT[], -- Array of email addresses
                        week_name VARCHAR(100), -- For automatic emails, e.g., "Week of 2024-01-01"
                        sent_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
                        error_message TEXT, -- If status is 'failed'
                        email_subject TEXT,
                        pdf_attachments TEXT[], -- Array of PDF file paths/names
                        sent_by UUID REFERENCES users(id), -- Who initiated the email (NULL for automatic)
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Check if table has any data
                cur.execute("SELECT COUNT(*) FROM email_activity_log")
                count = cur.fetchone()[0]
                
                if count == 0:
                    # Get a sample user ID for testing
                    cur.execute("SELECT id FROM users WHERE is_active = true LIMIT 1")
                    user_result = cur.fetchone()
                    user_id = user_result[0] if user_result else None
                    
                    # Insert sample data
                    sample_data = [
                        ('automatic', 3, ['user1@example.com', 'user2@example.com', 'user3@example.com'], 
                         'Week of 2024-01-08', 'sent', None, 'Weekly Bakery Metrics Report - Week of 2024-01-08', 
                         ['weekly_report_2024-01-08.pdf'], None),
                        ('manual', 2, ['admin@bakery.com', 'manager@bakery.com'], 
                         None, 'sent', None, 'Monthly Performance Review', 
                         ['monthly_review.pdf'], user_id),
                        ('automatic', 4, ['user1@example.com', 'user2@example.com', 'user3@example.com', 'user4@example.com'], 
                         'Week of 2024-01-01', 'sent', None, 'Weekly Bakery Metrics Report - Week of 2024-01-01', 
                         ['weekly_report_2024-01-01.pdf'], None),
                        ('manual', 1, ['test@bakery.com'], 
                         None, 'failed', 'SMTP connection timeout', 'Test Email Notification', 
                         [], user_id),
                        ('test', 1, ['admin@bakery.com'], 
                         None, 'sent', None, 'Email System Test', 
                         [], user_id)
                    ]
                    
                    for data_row in sample_data:
                        cur.execute("""
                            INSERT INTO email_activity_log 
                            (email_type, recipients_count, recipients_list, week_name, status, 
                             error_message, email_subject, pdf_attachments, sent_by) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, data_row)
                
                conn.commit()
                
                return jsonify({
                    "success": True,
                    "message": "Email activity log table created successfully",
                    "table_created": True,
                    "sample_data_added": count == 0
                })
        
    except Exception as e:
        logger.error(f"Error setting up email activity log: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to set up email activity log: {str(e)}"
        }), 500

@app.route('/api/remove-user', methods=['POST'])
@admin_required
def api_remove_user():
    data = request.get_json()
    user_id = data.get("user_id") or data.get("key")  # Support legacy key parameter

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Deactivate user instead of deleting
                cur.execute("""
                    UPDATE users SET is_active = false, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s OR email = %s
                """, (user_id, user_id))
                
                if cur.rowcount > 0:
                    conn.commit()
                    return jsonify({"message": "User has been deactivated.", "status": "success"})
                else:
                    return jsonify({"message": "User not found.", "status": "danger"})

    except Exception as e:
        logger.error(f"Remove user error: {e}")
        return jsonify({"message": f"Error: {str(e)}", "status": "danger"})

@app.route('/api/users/<user_id>', methods=['DELETE'])
@admin_required
def api_delete_user(user_id):
    """API endpoint to delete a user"""
    try:
        # Validate UUID format
        import uuid
        try:
            uuid.UUID(user_id)
        except ValueError:
            logger.error(f"Invalid UUID format for user_id: {user_id}")
            return jsonify({
                'success': False,
                'message': f'Invalid user ID format: {user_id}'
            }), 400
            
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First check if user exists and get info for logging
                cur.execute("""
                    SELECT first_name, last_name, email
                    FROM users
                    WHERE id = %s
                """, (user_id,))
                
                user_info = cur.fetchone()
                if not user_info:
                    logger.error(f"User not found for ID: {user_id}")
                    return jsonify({
                        'success': False,
                        'message': 'User not found'
                    }), 404
                
                # Check if user has any associated submissions or data
                cur.execute("""
                    SELECT COUNT(*) FROM week_submissions WHERE submitted_by = %s
                """, (user_info[2],))  # Using email as submitted_by
                
                submissions_count = cur.fetchone()[0]
                if submissions_count > 0:
                    return jsonify({
                        'success': False,
                        'message': f'Cannot delete user with {submissions_count} associated submissions. Consider deactivating instead.'
                    }), 400
                
                # Deactivate user instead of hard delete to preserve references
                cur.execute("""
                    UPDATE users
                    SET is_active = false, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to delete user'
                    }), 500
                
                conn.commit()
                
                # Log the deletion
                current_user_id = session.get('user_id')
                current_user_name = session.get('user_full_name')
                current_user_email = session.get('email')
                
                log_submission(
                    current_user_id, current_user_name, current_user_email,
                    'user_delete',
                    f'User deactivated: {user_info[0]} {user_info[1]} ({user_info[2]})'
                )
                
                return jsonify({
                    'success': True,
                    'message': 'User deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete user error for user_id {user_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to delete user: {str(e)}'
        }), 500

@app.route('/api/users/<user_id>', methods=['PUT'])
@admin_required
def api_update_user(user_id):
    """API endpoint to update a user"""
    try:
        # Validate UUID format
        import uuid
        try:
            uuid.UUID(user_id)
        except ValueError:
            logger.error(f"Invalid UUID format for user_id: {user_id}")
            return jsonify({
                'success': False,
                'message': f'Invalid user ID format: {user_id}'
            }), 400
            
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        first_name = data.get('first_name').strip()
        last_name = data.get('last_name').strip()
        email = data.get('email').strip().lower()
        phone = data.get('phone', '').strip() or None
        role = data.get('role')
        is_active = data.get('is_active', True)
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                'success': False,
                'message': 'Invalid email format'
            }), 400
        
        # Validate role
        valid_roles = ['admin', 'user', 'supervisor', 'employee']
        if role not in valid_roles:
            return jsonify({
                'success': False,
                'message': f'Invalid role. Must be one of: {", ".join(valid_roles)}'
            }), 400
            
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
                existing_user = cur.fetchone()
                if not existing_user:
                    return jsonify({
                        'success': False,
                        'message': 'User not found'
                    }), 404
                
                # Check if email already exists for a different user
                cur.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
                if cur.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Email already exists'
                    }), 400
                
                # Update user
                cur.execute("""
                    UPDATE users 
                    SET first_name = %s, last_name = %s, email = %s, phone = %s, 
                        role = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (first_name, last_name, email, phone, role, is_active, user_id))
                
                conn.commit()
                
                # Log the user update
                current_user_id = session.get('user_id')
                current_user_name = session.get('user_full_name')
                current_user_email = session.get('email')
                
                log_submission(
                    current_user_id, current_user_name, current_user_email,
                    'user_update',
                    f'User updated: {first_name} {last_name} ({email}) with role {role}'
                )
                
                return jsonify({
                    'success': True,
                    'message': 'User updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Update user error for user_id {user_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to update user: {str(e)}'
        }), 500

@app.route('/admin/report')
@admin_required
def admin_to_report():
    return redirect(url_for('report'))

# API Routes
@app.route('/api/submission-logs')
@admin_required
def get_submission_logs():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        sl.user_name as name,
                        sl.user_email as email,
                        sl.created_at as timestamp,
                        sl.message,
                        sl.week_sheet as week,
                        sl.day_of_week as day,
                        sl.submission_type,
                        sl.success
                    FROM submission_logs sl
                    ORDER BY sl.created_at DESC
                    LIMIT 1000
                """)
                logs = cur.fetchall()

                # Format timestamps for frontend
                formatted_logs = []
                for log in logs:
                    formatted_log = dict(log)
                    if formatted_log['timestamp']:
                        formatted_log['timestamp'] = formatted_log['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    formatted_logs.append(formatted_log)

                return jsonify({"logs": formatted_logs})

    except Exception as e:
        logger.error(f"Error fetching submission logs: {e}")
        return jsonify({"logs": [], "error": str(e)})

@app.route('/api/weekly-metrics')
@login_required
@password_change_required
def get_weekly_metrics():
    """API endpoint for weekly metrics data with filtering support"""
    week = request.args.get('week', 'latest')
    date_range = request.args.get('date_range')
    shift = request.args.get('shift', 'all')
    department = request.args.get('department', 'all')
    line = request.args.get('line', 'all')
    area = request.args.get('area', 'all')

    logger.info(f"Weekly metrics API call: week={week}, filters: date_range={date_range}, shift={shift}, department={department}, line={line}, area={area}")

    if week == "latest":
        week = get_latest_week_sheet()

    if not week:
        return jsonify({'error': 'No valid week found'}), 404

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get combined metrics data from the both_shifts_metrics table (auto-calculated)
                query = """
                    SELECT
                        ws.day_of_week,
                        -- Combined auto-calculated data from both_shifts_metrics
                        bs.die_cut1_oee_pct as combined_die_cut1_oee_pct,
                        bs.die_cut2_oee_pct as combined_die_cut2_oee_pct,
                        bs.oee_avg_pct as combined_oee_avg,
                        bs.die_cut1_lbs as combined_die_cut1_pounds,
                        bs.die_cut2_lbs as combined_die_cut2_pounds,
                        bs.pounds_total as combined_pounds_total,
                        bs.die_cut1_waste_lb as combined_die_cut1_waste_lbs,
                        bs.die_cut2_waste_lb as combined_die_cut2_waste_lbs,
                        bs.die_cut1_waste_pct as combined_die_cut1_waste_pct,
                        bs.die_cut2_waste_pct as combined_die_cut2_waste_pct,
                        bs.waste_avg_pct as combined_waste_avg,
                        -- Individual shift data for detailed breakdown
                        fs.die_cut1_oee_pct as first_die_cut1_oee_pct,
                        fs.die_cut2_oee_pct as first_die_cut2_oee_pct,
                        fs.die_cut1_lbs as first_die_cut1_pounds,
                        fs.die_cut2_lbs as first_die_cut2_pounds,
                        fs.die_cut1_waste_lb as first_die_cut1_waste_lbs,
                        fs.die_cut2_waste_lb as first_die_cut2_waste_lbs,
                        ss.die_cut1_oee_pct as second_die_cut1_oee_pct,
                        ss.die_cut2_oee_pct as second_die_cut2_oee_pct,
                        ss.die_cut1_lbs as second_die_cut1_pounds,
                        ss.die_cut2_lbs as second_die_cut2_pounds,
                        ss.die_cut1_waste_lb as second_die_cut1_waste_lbs,
                        ss.die_cut2_waste_lb as second_die_cut2_waste_lbs,
                        ss.waste_avg_pct as second_shift_waste_db_avg,
                        ss.oee_avg_pct as second_shift_oee_db_avg
                    FROM week_submissions ws
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    WHERE ws.week_name = %s
                    ORDER BY
                        CASE ws.day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                        END
                """
                
                cur.execute(query, [week])
                metrics_data = cur.fetchall()

                # Organize data for response
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                
                # Initialize data structures with float values
                oee_data = [0.0] * 5
                waste_data = [0.0] * 5
                oee_first_shift = [0.0] * 5
                waste_first_shift = [0.0] * 5
                oee_second_shift = [0.0] * 5
                waste_second_shift = [0.0] * 5
                pounds_first_shift = [0.0] * 5
                pounds_second_shift = [0.0] * 5

                # Process metrics data using auto-calculated values where available
                for metric in metrics_data:
                    if metric['day_of_week'] not in days:
                        continue
                        
                    day_idx = days.index(metric['day_of_week'])
                    
                    # Use auto-calculated combined values from both_shifts_metrics if available
                    if metric['combined_oee_avg'] is not None:
                        # Use the database's auto-calculated combined OEE average
                        oee_data[day_idx] = float(metric['combined_oee_avg'])
                    else:
                        # Fallback to manual calculation if combined data not available
                        first_oee1 = float(metric['first_die_cut1_oee_pct'] or 0)
                        first_oee2 = float(metric['first_die_cut2_oee_pct'] or 0)
                        second_oee1 = float(metric['second_die_cut1_oee_pct'] or 0)
                        second_oee2 = float(metric['second_die_cut2_oee_pct'] or 0)
                        
                        first_avg_oee = (first_oee1 + first_oee2) / 2 if first_oee1 > 0 and first_oee2 > 0 else (first_oee1 or first_oee2)
                        second_avg_oee = (second_oee1 + second_oee2) / 2 if second_oee1 > 0 and second_oee2 > 0 else (second_oee1 or second_oee2)
                        combined_oee = (first_avg_oee + second_avg_oee) / 2 if first_avg_oee > 0 and second_avg_oee > 0 else (first_avg_oee or second_avg_oee)
                        oee_data[day_idx] = combined_oee
                    
                    # Use auto-calculated combined waste percentage if available
                    if metric['combined_waste_avg'] is not None:
                        waste_data[day_idx] = float(metric['combined_waste_avg'])
                        logger.info(f"🔧 DEBUG Weekly Metrics - Day: {metric['day_of_week']}, Using DB combined_waste: {metric['combined_waste_avg']}%")
                    else:
                        # Fallback to manual calculation
                        first_pounds1 = float(metric['first_die_cut1_pounds'] or 0)
                        first_pounds2 = float(metric['first_die_cut2_pounds'] or 0)
                        second_pounds1 = float(metric['second_die_cut1_pounds'] or 0)
                        second_pounds2 = float(metric['second_die_cut2_pounds'] or 0)
                        first_waste1 = float(metric['first_die_cut1_waste_lbs'] or 0)
                        first_waste2 = float(metric['first_die_cut2_waste_lbs'] or 0)
                        second_waste1 = float(metric['second_die_cut1_waste_lbs'] or 0)
                        second_waste2 = float(metric['second_die_cut2_waste_lbs'] or 0)
                        
                        first_total_pounds = first_pounds1 + first_pounds2
                        second_total_pounds = second_pounds1 + second_pounds2
                        first_total_waste = first_waste1 + first_waste2
                        second_total_waste = second_waste1 + second_waste2
                        
                        first_waste_pct = (first_total_waste / first_total_pounds * 100) if first_total_pounds > 0 else 0
                        second_waste_pct = (second_total_waste / second_total_pounds * 100) if second_total_pounds > 0 else 0
                        combined_waste = (first_waste_pct + second_waste_pct) / 2 if first_waste_pct > 0 and second_waste_pct > 0 else (first_waste_pct or second_waste_pct)
                        waste_data[day_idx] = combined_waste
                    
                    # Calculate individual shift data for breakdown charts
                    first_oee1 = float(metric['first_die_cut1_oee_pct'] or 0)
                    first_oee2 = float(metric['first_die_cut2_oee_pct'] or 0)
                    second_oee1 = float(metric['second_die_cut1_oee_pct'] or 0)
                    second_oee2 = float(metric['second_die_cut2_oee_pct'] or 0)
                    
                    first_avg_oee = (first_oee1 + first_oee2) / 2 if first_oee1 > 0 and first_oee2 > 0 else (first_oee1 or first_oee2)
                    second_avg_oee = (second_oee1 + second_oee2) / 2 if second_oee1 > 0 and second_oee2 > 0 else (second_oee1 or second_oee2)
                    
                    oee_first_shift[day_idx] = first_avg_oee
                    oee_second_shift[day_idx] = second_avg_oee
                    
                    # Calculate production totals
                    first_pounds1 = float(metric['first_die_cut1_pounds'] or 0)
                    first_pounds2 = float(metric['first_die_cut2_pounds'] or 0)
                    second_pounds1 = float(metric['second_die_cut1_pounds'] or 0)
                    second_pounds2 = float(metric['second_die_cut2_pounds'] or 0)
                    
                    pounds_first_shift[day_idx] = first_pounds1 + first_pounds2
                    pounds_second_shift[day_idx] = second_pounds1 + second_pounds2
                    
                    # Calculate waste percentages for individual shifts
                    first_waste1 = float(metric['first_die_cut1_waste_lbs'] or 0)
                    first_waste2 = float(metric['first_die_cut2_waste_lbs'] or 0)
                    second_waste1 = float(metric['second_die_cut1_waste_lbs'] or 0)
                    second_waste2 = float(metric['second_die_cut2_waste_lbs'] or 0)
                    
                    first_total_pounds = first_pounds1 + first_pounds2
                    second_total_pounds = second_pounds1 + second_pounds2
                    first_total_waste = first_waste1 + first_waste2
                    second_total_waste = second_waste1 + second_waste2
                    
                    first_waste_pct = (first_total_waste / first_total_pounds * 100) if first_total_pounds > 0 else 0
                    second_waste_pct = (second_total_waste / second_total_pounds * 100) if second_total_pounds > 0 else 0
                    
                    # Get database auto-calculated second shift waste for comparison
                    db_second_waste = metric.get('second_shift_waste_db_avg')
                    
                    # DEBUG: Log second shift waste calculations for accuracy verification
                    logger.info(f"🔧 DEBUG Second Shift Waste - Day: {metric['day_of_week']}, "
                               f"DC1_waste: {second_waste1}lbs, DC2_waste: {second_waste2}lbs, "
                               f"Total_waste: {second_total_waste}lbs, Total_pounds: {second_total_pounds}lbs, "
                               f"Manual_Calc_%: {second_waste_pct:.3f}, DB_Auto_Calc_%: {db_second_waste}, "
                               f"Difference: {abs(second_waste_pct - float(db_second_waste or 0)):.3f} percentage points")
                    
                    waste_first_shift[day_idx] = first_waste_pct
                    waste_second_shift[day_idx] = second_waste_pct

                # Calculate averages
                def calculate_avg(data_list):
                    non_zero_values = [x for x in data_list if x != 0]
                    return round(sum(non_zero_values) / len(non_zero_values), 2) if non_zero_values else 0

                # Calculate derived metrics
                total_production = sum(pounds_first_shift) + sum(pounds_second_shift)
                avg_oee = calculate_avg(oee_data)
                avg_waste = calculate_avg(waste_data)

                return jsonify({
                    'week': week,
                    'oee': [round(x, 1) for x in oee_data],
                    'waste': [round(x, 2) for x in waste_data],
                    'oeeAvg': avg_oee,
                    'wasteAvg': avg_waste,
                    'oeeFirstShift': [round(x, 1) for x in oee_first_shift],
                    'wasteFirstShift': [round(x, 2) for x in waste_first_shift],
                    'oeeSecondShift': [round(x, 1) for x in oee_second_shift],
                    'wasteSecondShift': [round(x, 2) for x in waste_second_shift],
                    'downtimeRatio': round(100 - avg_oee * 0.948, 1) if avg_oee > 0 else 0,
                    'productionRate': round(min(avg_oee * 1.03, 100), 1) if avg_oee > 0 else 0,
                    'totalProduction': round(total_production, 1)
                })

    except Exception as e:
        logger.error(f"Weekly metrics error: {e}")
        # Return empty data structure instead of error to show clean empty dashboard
        return jsonify({
            'week': week or 'No Week',
            'oee': [0.0] * 5,
            'waste': [0.0] * 5,
            'oeeAvg': 0,
            'wasteAvg': 0,
            'oeeFirstShift': [0.0] * 5,
            'wasteFirstShift': [0.0] * 5,
            'oeeSecondShift': [0.0] * 5,
            'wasteSecondShift': [0.0] * 5,
            'downtimeRatio': 0,
            'productionRate': 0,
            'totalProduction': 0
        })

@app.route('/api/inventory-sheets')
@login_required
def get_inventory_sheet_names():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT item_code 
                    FROM inventory_items 
                    WHERE is_active = true 
                    ORDER BY item_code
                """)
                items = cur.fetchall()

                return jsonify({"sheets": [item['item_code'] for item in items]})

    except Exception as e:
        logger.error(f"Error fetching inventory sheet names: {e}")
        return jsonify({"sheets": [], "error": str(e)})

@app.route('/api/inventory-overview-data')
@login_required
@password_change_required
def inventory_overview_data():
    item_code = request.args.get('sheet')
    day_filter = request.args.get('day')
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')

    if not item_code:
        return jsonify(rows=[])

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        it.calculated_quantity as quantity,
                        it.lot_number as lot,
                        it.shift_type as shift,
                        it.day_of_week as day,
                        it.transaction_date as date,
                        it.transaction_time as time,
                        u.first_name || ' ' || u.last_name as user,
                        it.transaction_type as status,
                        ii.item_code as item
                    FROM inventory_transactions it
                    JOIN inventory_items ii ON it.item_id = ii.id
                    LEFT JOIN users u ON it.created_by = u.id
                    WHERE ii.item_code = %s
                """
                
                params = [item_code]

                if day_filter:
                    query += " AND LOWER(it.day_of_week) = LOWER(%s)"
                    params.append(day_filter)

                if status_filter and status_filter != "all":
                    if status_filter in ["received", "returned"]:
                        query += " AND it.transaction_type = %s"
                        params.append(status_filter)
                    elif status_filter in ["first shift", "second shift"]:
                        shift_type = status_filter.split()[0]  # "first" or "second"
                        query += " AND it.shift_type = %s"
                        params.append(shift_type)

                if date_filter:
                    query += " AND it.transaction_date = %s"
                    params.append(date_filter)

                query += " ORDER BY it.transaction_date DESC, it.created_at DESC"

                cur.execute(query, params)
                rows = cur.fetchall()

                # Format the response
                formatted_rows = []
                for row in rows:
                    formatted_rows.append({
                        "quantity": float(row['quantity']) if row['quantity'] else 0,
                        "lot": row['lot'] or "",
                        "shift": row['shift'] or "",
                        "day": row['day'] or "",
                        "date": row['date'].strftime('%Y-%m-%d') if row['date'] else "",
                        "time": row['time'].strftime('%H:%M:%S') if row['time'] else "",
                        "user": row['user'] or "",
                        "status": row['status'] or "",
                        "item": row['item'] or ""
                    })

                return jsonify(rows=formatted_rows)

    except Exception as e:
        logger.error(f"Inventory overview data error: {e}")
        return jsonify(rows=[], error=str(e)), 500

@app.route('/api/dashboard-kpis')
@login_required
@password_change_required
def get_dashboard_kpis():
    """API endpoint for additional dashboard KPIs with filtering support and trend calculations"""
    date_range = request.args.get('date_range', 'current_week')
    shift = request.args.get('shift', 'all')
    department = request.args.get('department', 'all')
    line = request.args.get('line', 'all')
    area = request.args.get('area', 'all')
    
    logger.info(f"Dashboard KPIs API call: date_range={date_range}, shift={shift}, department={department}, line={line}, area={area}")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get current week and previous week from weekly_sheets
                cur.execute("""
                    SELECT DISTINCT sheet_name as week_name, week_start, week_end
                    FROM weekly_sheets
                    WHERE is_active = true
                    ORDER BY week_start DESC
                    LIMIT 2
                """)
                weeks = cur.fetchall()
                
                current_week = weeks[0]['week_name'] if weeks else None
                previous_week = weeks[1]['week_name'] if len(weeks) > 1 else None
                
                def get_week_kpis(week_name):
                    """Helper function to get KPIs for a specific week using both_shifts_metrics table"""
                    if not week_name:
                        return {'avg_oee': 0, 'avg_waste': 0, 'total_production': 0}
                    
                    # Get auto-calculated data from both_shifts_metrics table
                    query = """
                        SELECT
                            bs.oee_avg_pct,
                            bs.waste_avg_pct,
                            bs.pounds_total
                        FROM week_submissions ws
                        LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                        WHERE ws.week_name = %s
                        AND bs.oee_avg_pct IS NOT NULL
                    """
                    
                    cur.execute(query, [week_name])
                    results = cur.fetchall()
                    
                    if not results:
                        return {'avg_oee': 0, 'avg_waste': 0, 'total_production': 0}
                    
                    total_oee = 0
                    total_waste = 0
                    total_production = 0
                    count = len(results)
                    
                    for row in results:
                        total_oee += float(row['oee_avg_pct'] or 0)
                        total_waste += float(row['waste_avg_pct'] or 0)
                        total_production += float(row['pounds_total'] or 0)
                    
                    avg_oee = total_oee / count if count > 0 else 0
                    avg_waste = total_waste / count if count > 0 else 0
                    
                    return {
                        'avg_oee': avg_oee,
                        'avg_waste': avg_waste,
                        'total_production': total_production
                    }
                
                # Get current and previous week data
                current_data = get_week_kpis(current_week)
                previous_data = get_week_kpis(previous_week)
                
                # Calculate trends (week-over-week changes)
                def calculate_trend(current, previous):
                    """Calculate percentage change from previous to current"""
                    if previous == 0:
                        return 0.0 if current == 0 else 100.0
                    return round(((current - previous) / previous) * 100, 1)
                
                # Calculate trend indicators
                oee_trend = calculate_trend(current_data['avg_oee'], previous_data['avg_oee'])
                waste_trend = calculate_trend(current_data['avg_waste'], previous_data['avg_waste'])
                production_trend = calculate_trend(current_data['total_production'], previous_data['total_production'])
                
                # Define performance targets/goals
                GOALS = {
                    'oee_target': 70.0,          # 70% OEE target
                    'waste_target': 2.5,         # 2.5% waste target
                    'production_target': 15000,   # 15,000 lbs weekly target
                    'availability_target': 95.0,  # 95% availability target
                    'performance_target': 90.0,   # 90% performance target
                    'quality_target': 97.5        # 97.5% quality target (100 - 2.5% waste)
                }
                
                # Calculate additional KPIs
                avg_oee = current_data['avg_oee']
                avg_waste = current_data['avg_waste']
                total_production = current_data['total_production']
                
                # Calculate derived KPIs
                availability = max(100 - (avg_waste * 2.5), 0) if avg_waste > 0 else 0
                performance = min(avg_oee, 100) if avg_oee > 0 else 0
                quality = max(100 - avg_waste, 0) if avg_waste > 0 else 0
                downtime_ratio = max(100 - availability, 0) if availability > 0 else 0
                production_rate = min(avg_oee * 1.03, 100) if avg_oee > 0 else 0
                
                # Calculate performance vs goals indicators
                def get_goal_indicator(current_value, target_value, higher_is_better=True):
                    """Calculate goal performance indicator"""
                    if target_value == 0:
                        return {'status': 'unknown', 'percentage': 0, 'variance': 0}
                    
                    if higher_is_better:
                        percentage = (current_value / target_value) * 100
                        variance = current_value - target_value
                    else:  # Lower is better (like waste)
                        percentage = (target_value / max(current_value, 0.1)) * 100
                        variance = target_value - current_value
                    
                    if percentage >= 100:
                        status = 'above_target'
                    elif percentage >= 90:
                        status = 'on_target'
                    elif percentage >= 75:
                        status = 'below_target'
                    else:
                        status = 'critical'
                    
                    return {
                        'status': status,
                        'percentage': round(percentage, 1),
                        'variance': round(variance, 2)
                    }
                
                # Calculate downtime trend
                prev_availability = max(100 - (previous_data['avg_waste'] * 2.5), 0) if previous_data['avg_waste'] > 0 else 0
                prev_downtime_ratio = max(100 - prev_availability, 0) if prev_availability > 0 else 0
                downtime_trend = calculate_trend(downtime_ratio, prev_downtime_ratio)
                
                # Calculate production rate trend
                prev_production_rate = min(previous_data['avg_oee'] * 1.03, 100) if previous_data['avg_oee'] > 0 else 0
                production_rate_trend = calculate_trend(production_rate, prev_production_rate)
                
                # Calculate goal indicators
                oee_goal = get_goal_indicator(avg_oee, GOALS['oee_target'], True)
                waste_goal = get_goal_indicator(avg_waste, GOALS['waste_target'], False)
                production_goal = get_goal_indicator(total_production, GOALS['production_target'], True)
                availability_goal = get_goal_indicator(availability, GOALS['availability_target'], True)
                performance_goal = get_goal_indicator(performance, GOALS['performance_target'], True)
                quality_goal = get_goal_indicator(quality, GOALS['quality_target'], True)

                kpis = {
                    'avgOEE': round(avg_oee, 1),
                        # Provide the average waste percentage directly to the dashboard. This represents the percentage
                        # of waste relative to total production and is used when calculating waste performance targets.
                        'avgWaste': round(avg_waste, 1),
                        # Keep totalWaste (in lbs) for other dashboard components if needed. It represents the total
                        # waste pounds (production * waste percent / 100) and is not used for the waste target gauge.
                        'totalWaste': round(total_production * avg_waste / 100, 1) if avg_waste and total_production else 0,
                        'downtimeRatio': round(downtime_ratio, 1),
                        'productionRate': round(production_rate, 1),
                        'availability': round(availability, 1),
                        'performance': round(performance, 1),
                        'quality': round(quality, 1),
                        'plannedDowntime': 0,  # Will be calculated from actual downtime data when available
                        'unplannedDowntime': round(max(downtime_ratio, 0), 1),
                        'totalProduction': round(total_production, 1),
                    
                    # Goal targets
                    'goals': {
                        'oee_target': GOALS['oee_target'],
                        'waste_target': GOALS['waste_target'],
                        'production_target': GOALS['production_target'],
                        'availability_target': GOALS['availability_target'],
                        'performance_target': GOALS['performance_target'],
                        'quality_target': GOALS['quality_target']
                    },
                    
                    # Goal performance indicators
                    'goalIndicators': {
                        'oee': oee_goal,
                        'waste': waste_goal,
                        'production': production_goal,
                        'availability': availability_goal,
                        'performance': performance_goal,
                        'quality': quality_goal
                    },
                    
                    # Trend indicators (preserved from original)
                    'trends': {
                        'oee': {
                            'value': oee_trend,
                            'direction': 'up' if oee_trend > 0 else 'down' if oee_trend < 0 else 'stable',
                            'icon': 'trending-up' if oee_trend > 0 else 'trending-down' if oee_trend < 0 else 'minus'
                        },
                        'waste': {
                            'value': waste_trend,
                            'direction': 'down' if waste_trend < 0 else 'up' if waste_trend > 0 else 'stable',  # Lower waste is good
                            'icon': 'trending-down' if waste_trend < 0 else 'trending-up' if waste_trend > 0 else 'minus'
                        },
                        'downtime': {
                            'value': downtime_trend,
                            'direction': 'up' if downtime_trend > 0 else 'down' if downtime_trend < 0 else 'stable',
                            'icon': 'minus' if downtime_trend == 0 else 'trending-up' if downtime_trend > 0 else 'trending-down'
                        },
                        'production': {
                            'value': production_rate_trend,
                            'direction': 'up' if production_rate_trend > 0 else 'down' if production_rate_trend < 0 else 'stable',
                            'icon': 'trending-up' if production_rate_trend > 0 else 'trending-down' if production_rate_trend < 0 else 'minus'
                        }
                    }
                }
                
                return jsonify(kpis)
                
    except Exception as e:
        logger.error(f"Dashboard KPIs error: {e}")
        # Return zero values on error instead of hardcoded fallbacks
        return jsonify({
            'avgOEE': 0,
            'totalWaste': 0,
            'downtimeRatio': 0,
            'productionRate': 0,
            'availability': 0,
            'performance': 0,
            'quality': 0,
            'plannedDowntime': 0,
            'unplannedDowntime': 0,
            'totalProduction': 0,
            'trends': {
                'oee': {'value': 0, 'direction': 'stable', 'icon': 'minus'},
                'waste': {'value': 0, 'direction': 'stable', 'icon': 'minus'},
                'downtime': {'value': 0, 'direction': 'stable', 'icon': 'minus'},
                'production': {'value': 0, 'direction': 'stable', 'icon': 'minus'}
            }
        })


@app.route('/api/system-info')
@login_required
def get_system_info():
    """Get real system information for dashboard with improved error handling"""
    try:
        # Make psutil import optional to prevent HTTP 500 errors
        try:
            import psutil
            psutil_available = True
        except ImportError:
            psutil_available = False
            logger.warning("psutil not available - system metrics will be limited")
        
        import time
        from datetime import datetime, timedelta
        
        uptime_seconds = 0
        last_update = None
        
        # Get database connectivity and metrics
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Test database connectivity
                    cursor.execute("SELECT 1")
                    db_status = "Real-time"
                    db_healthy = True
                    
                    # Get today's record count from all relevant tables
                    today = datetime.now().date()
                    
                    # Count submissions from the new metrics system
                    cursor.execute("""
                        SELECT 
                            (SELECT COUNT(*) FROM week_submissions WHERE DATE(created_at) = %s) +
                            (SELECT COUNT(*) FROM first_shift_metrics WHERE DATE(created_at) = %s) +
                            (SELECT COUNT(*) FROM second_shift_metrics WHERE DATE(created_at) = %s) +
                            (SELECT COUNT(*) FROM inventory_transactions WHERE DATE(created_at) = %s) +
                            (SELECT COUNT(*) FROM issues WHERE DATE(created_at) = %s) +
                            (SELECT COUNT(*) FROM submission_logs WHERE DATE(created_at) = %s) as total_count
                    """, (today, today, today, today, today, today))
                    
                    result = cursor.fetchone()
                    records_today = result[0] if result and result[0] else 0
                    
                    # Get last database update time from multiple tables
                    cursor.execute("""
                        SELECT GREATEST(
                            COALESCE((SELECT MAX(created_at) FROM week_submissions), '1900-01-01'::timestamp),
                            COALESCE((SELECT MAX(created_at) FROM first_shift_metrics), '1900-01-01'::timestamp),
                            COALESCE((SELECT MAX(created_at) FROM second_shift_metrics), '1900-01-01'::timestamp),
                            COALESCE((SELECT MAX(created_at) FROM inventory_transactions), '1900-01-01'::timestamp),
                            COALESCE((SELECT MAX(created_at) FROM issues), '1900-01-01'::timestamp),
                            COALESCE((SELECT MAX(created_at) FROM submission_logs), '1900-01-01'::timestamp)
                        ) as last_update
                    """)
                    
                    last_update_row = cursor.fetchone()
                    if last_update_row and last_update_row[0] and last_update_row[0].year > 1900:
                        last_update = last_update_row[0]
                        
        except Exception as e:
            logger.error(f"Database connectivity error: {e}")
            db_status = "Offline"
            db_healthy = False
            records_today = 0
        
        # Get actual system uptime (in seconds since boot)
        if psutil_available:
            try:
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time
                uptime_hours = uptime_seconds / 3600
                uptime_days = uptime_hours / 24
                
                if uptime_days >= 1:
                    uptime_display = f"{int(uptime_days)}d {int(uptime_hours % 24)}h"
                else:
                    uptime_display = f"{int(uptime_hours)}h {int((uptime_seconds % 3600) / 60)}m"
            except Exception as e:
                logger.warning(f"Failed to get system uptime: {e}")
                uptime_display = "Unknown"
        else:
            # Calculate application uptime as fallback
            app_start_time = app.config.get('APP_START_TIME', time.time())
            app_uptime = time.time() - app_start_time
            uptime_hours = app_uptime / 3600
            if uptime_hours >= 24:
                uptime_display = f"{int(uptime_hours / 24)}d {int(uptime_hours % 24)}h"
            else:
                uptime_display = f"{int(uptime_hours)}h {int((app_uptime % 3600) / 60)}m"
            
        # Calculate last update display
        if last_update:
            time_diff = datetime.now() - last_update.replace(tzinfo=None)
            if time_diff.total_seconds() < 60:  # Less than 1 minute
                last_update_display = "Just now"
            elif time_diff.total_seconds() < 3600:  # Less than 1 hour
                minutes = int(time_diff.total_seconds() / 60)
                last_update_display = f"{minutes}m ago"
            elif time_diff.total_seconds() < 86400:  # Less than 1 day
                hours = int(time_diff.total_seconds() / 3600)
                last_update_display = f"{hours}h ago"
            else:
                days = int(time_diff.total_seconds() / 86400)
                last_update_display = f"{days}d ago"
        else:
            last_update_display = "No data"
        
        # Get system resource usage if available
        system_health = "Healthy"
        cpu_percent = 0
        memory_percent = 0
        disk_percent = 0
        
        if psutil_available:
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                memory_percent = memory.percent
                disk_percent = disk.percent
                
                # Determine system health based on resource usage
                if cpu_percent > 80 or memory_percent > 80 or disk_percent > 80:
                    system_health = "Warning"
                if cpu_percent > 95 or memory_percent > 95 or disk_percent > 90:
                    system_health = "Critical"
            except Exception as e:
                logger.warning(f"Failed to get system metrics: {e}")
                system_health = "Limited"
        
        # Return simplified structure that matches frontend expectations
        return jsonify({
            'success': True,
            'data': {
                'dataSync': {
                    'status': db_status,
                    'healthy': db_healthy,
                    'display': db_status
                },
                'systemUptime': {
                    'display': uptime_display,
                    'seconds': uptime_seconds
                },
                'recordsToday': {
                    'count': records_today,
                    'display': str(records_today)
                },
                'lastUpdate': {
                    'display': last_update_display,
                    'timestamp': last_update.isoformat() if last_update else None
                },
                'systemHealth': {
                    'status': system_health,
                    'cpu': round(cpu_percent, 1),
                    'memory': round(memory_percent, 1),
                    'disk': round(disk_percent, 1)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"System info error: {e}")
        return jsonify({
            'success': False,
            'message': f'Error fetching system information: {str(e)}',
            'data': {
                'dataSync': {'display': 'Error', 'healthy': False},
                'systemUptime': {'display': 'Error'},
                'recordsToday': {'display': 'Error'},
                'lastUpdate': {'display': 'Error'},
                'systemHealth': {'status': 'Error'}
            }
        }), 500


# New API endpoint to retrieve a list of recent activities for the dashboard.
# This endpoint consolidates events from week_submissions, weekly_sheets, and inventory_transactions tables.
# It returns the most recent 10 activities with a type, human-readable description, and a relative time.
@app.route('/api/recent-activities')
@login_required
def get_recent_activities():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Combine activities from metrics submissions, weekly report generation, and inventory transactions.
                # We select description text and type here to simplify processing in Python.
                cur.execute("""
                    SELECT type, description, created_at FROM (
                        SELECT 'metrics' AS type,
                               'Metrics submitted for ' || ws.day_of_week AS description,
                               ws.created_at
                        FROM week_submissions ws
                        WHERE ws.created_at IS NOT NULL
                        UNION ALL
                        SELECT 'weekly_report' AS type,
                               'Weekly report generated' AS description,
                               w.created_at
                        FROM weekly_sheets w
                        WHERE w.created_at IS NOT NULL
                        UNION ALL
                        SELECT 'inventory' AS type,
                               'Inventory ' || it.transaction_type AS description,
                               it.created_at
                        FROM inventory_transactions it
                        WHERE it.created_at IS NOT NULL
                    ) acts
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                rows = cur.fetchall()

                activities = []
                # Use UTC now for time difference calculation; times are converted to naive for subtraction.
                from datetime import datetime
                now = datetime.utcnow()

                for row in rows:
                    created_at = row['created_at']
                    # Normalize timestamp to naive datetime for difference calculation
                    if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
                        naive_created = created_at.replace(tzinfo=None)
                    else:
                        naive_created = created_at
                    diff = now - naive_created
                    seconds = diff.total_seconds()
                    # Generate human-readable relative time string
                    if seconds < 60:
                        time_ago = 'just now'
                    elif seconds < 3600:
                        minutes = int(seconds / 60)
                        time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    elif seconds < 86400:
                        hours = int(seconds / 3600)
                        time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
                    else:
                        days = int(seconds / 86400)
                        time_ago = f"{days} day{'s' if days != 1 else ''} ago"

                    activities.append({
                        'type': row['type'],
                        'description': row['description'],
                        'time_ago': time_ago
                    })

        return jsonify({'activities': activities})
    except Exception as e:
        logger.error(f"Recent activities error: {e}")
        return jsonify({
            'activities': [],
            'error': str(e)
        }), 500


@app.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """API endpoint for real-time notifications from database events"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                notifications = []
                
                # 1. Recent form submissions (last 7 days)
                cur.execute("""
                    SELECT 
                        'form_submission' as type,
                        CASE 
                            WHEN success = true THEN 'Metrics submitted for ' || COALESCE(day_of_week, 'Unknown day')
                            ELSE 'Submission failed: ' || COALESCE(message, 'Unknown error')
                        END as description,
                        created_at,
                        success
                    FROM submission_logs 
                    WHERE submission_type = 'metrics' 
                    AND created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                    ORDER BY created_at DESC 
                    LIMIT 8
                """)
                
                for row in cur.fetchall():
                    notifications.append({
                        'type': row['type'],
                        'description': row['description'],
                        'created_at': row['created_at'],
                        'success': row['success']
                    })
                
                # 2. Recent issues (last 14 days)
                cur.execute("""
                    SELECT 
                        'issue_report' as type,
                        'Issue reported: ' || line || ' - ' || LEFT(title, 40) || 
                        CASE WHEN LENGTH(title) > 40 THEN '...' ELSE '' END as description,
                        created_at,
                        true as success
                    FROM issues 
                    WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '14 days'
                    ORDER BY created_at DESC 
                    LIMIT 6
                """)
                
                for row in cur.fetchall():
                    notifications.append({
                        'type': row['type'],
                        'description': row['description'],
                        'created_at': row['created_at'],
                        'success': row['success']
                    })
                
                # 3. Inventory alerts (recent transactions)
                cur.execute("""
                    SELECT 
                        'inventory_alert' as type,
                        'Inventory ' || transaction_type || ': ' || ii.item_name as description,
                        it.created_at,
                        true as success
                    FROM inventory_transactions it
                    JOIN inventory_items ii ON it.item_id = ii.id
                    WHERE it.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                    ORDER BY it.created_at DESC 
                    LIMIT 5
                """)
                
                for row in cur.fetchall():
                    notifications.append({
                        'type': row['type'],
                        'description': row['description'],
                        'created_at': row['created_at'],
                        'success': row['success']
                    })
                
                # 4. KPI threshold alerts (OEE below 70%, waste above 3.75%)
                cur.execute("""
                    SELECT 
                        'kpi_alert' as type,
                        CASE 
                            WHEN bs.oee_avg_pct < 70 THEN 
                                'OEE below target: ' || ROUND(bs.oee_avg_pct, 1) || '% vs goal 70%'
                            WHEN bs.waste_avg_pct > 3.75 THEN 
                                'Waste above target: ' || ROUND(bs.waste_avg_pct, 2) || '% vs goal 3.75%'
                        END as description,
                        bs.created_at,
                        false as success
                    FROM both_shifts_metrics bs
                    JOIN week_submissions ws ON bs.week_submission_id = ws.id
                    WHERE bs.created_at >= CURRENT_TIMESTAMP - INTERVAL '14 days'
                    AND (bs.oee_avg_pct < 70 OR bs.waste_avg_pct > 3.75)
                    ORDER BY bs.created_at DESC 
                    LIMIT 4
                """)
                
                for row in cur.fetchall():
                    notifications.append({
                        'type': row['type'],
                        'description': row['description'],
                        'created_at': row['created_at'],
                        'success': row['success']
                    })
                
                # 5. Week updates (new week sheets created)
                cur.execute("""
                    SELECT 
                        'week_update' as type,
                        'New week sheet created: ' || sheet_name as description,
                        created_at,
                        true as success
                    FROM weekly_sheets 
                    WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
                    ORDER BY created_at DESC 
                    LIMIT 3
                """)
                
                for row in cur.fetchall():
                    notifications.append({
                        'type': row['type'],
                        'description': row['description'],
                        'created_at': row['created_at'],
                        'success': row['success']
                    })
                
                # Sort all notifications by created_at descending and limit to 25
                notifications.sort(key=lambda x: x['created_at'], reverse=True)
                notifications = notifications[:25]
                
                # Calculate time ago for each notification
                from datetime import datetime
                now = datetime.now()
                
                for notification in notifications:
                    created_at = notification['created_at']
                    if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
                        naive_created = created_at.replace(tzinfo=None)
                    else:
                        naive_created = created_at
                    
                    diff = now - naive_created
                    seconds = diff.total_seconds()
                    
                    if seconds < 60:
                        time_ago = 'just now'
                    elif seconds < 3600:
                        minutes = int(seconds / 60)
                        time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    elif seconds < 86400:
                        hours = int(seconds / 3600)
                        time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
                    else:
                        days = int(seconds / 86400)
                        time_ago = f"{days} day{'s' if days != 1 else ''} ago"
                    
                    notification['time_ago'] = time_ago
                
                return jsonify({
                    'success': True,
                    'notifications': notifications,
                    'count': len(notifications)
                })
                
    except Exception as e:
        logger.error(f"Notifications error: {e}")
        return jsonify({
            'success': False,
            'notifications': [],
            'count': 0,
            'error': str(e)
        }), 500





@app.route('/api/report')
@login_required
@password_change_required
def api_report():
    week = request.args.get('week')
    day = request.args.get('day')
    shift = request.args.get('shift')

    # Validate parameters
    valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    valid_shifts = ['first', 'second', 'both']

    if not week or day not in valid_days or shift not in valid_shifts:
        return jsonify({"error": "invalid parameters"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get weekly sheet ID
                cur.execute("""
                    SELECT id FROM weekly_sheets WHERE sheet_name = %s
                """, (week,))
                
                sheet_result = cur.fetchone()
                if not sheet_result:
                    return jsonify({"error": "Week sheet not found"}), 404

                weekly_sheet_id = sheet_result['id']

                # Get metrics for the specific day and shift
                cur.execute("""
                    SELECT metric_type, value
                    FROM metrics
                    WHERE weekly_sheet_id = %s
                    AND day_of_week = %s
                    AND shift_type = %s
                """, (weekly_sheet_id, day, shift))
                
                metrics = cur.fetchall()
                
                # Initialize response with defaults
                response = {
                    "oee1": "-", "oee2": "-", "oeeTotal": "-",
                    "pounds1": "-", "pounds2": "-", "poundsTotal": "-",
                    "waste1": "-", "waste2": "-", "wasteTotal": "-",
                    "oee1Avg": "-", "oee2Avg": "-", "oeeTotalAvg": "-",
                    "pounds1Avg": "-", "pounds2Avg": "-", "poundsTotalAvg": "-",
                    "waste1Avg": "-", "waste2Avg": "-", "wasteTotalAvg": "-"
                }

                # Fill in actual values
                for metric in metrics:
                    metric_type = metric['metric_type']
                    value = str(metric['value']) if metric['value'] is not None else "-"
                    
                    if metric_type == 'oee_die_cut_1':
                        response['oee1'] = value
                    elif metric_type == 'oee_die_cut_2':
                        response['oee2'] = value
                    elif metric_type == 'pounds_die_cut_1':
                        response['pounds1'] = value
                    elif metric_type == 'pounds_die_cut_2':
                        response['pounds2'] = value
                    elif metric_type == 'waste_die_cut_1':
                        response['waste1'] = value
                    elif metric_type == 'waste_die_cut_2':
                        response['waste2'] = value

                # Calculate totals (simplified - you may want more complex logic)
                try:
                    if response['oee1'] != "-" and response['oee2'] != "-":
                        response['oeeTotal'] = str((float(response['oee1']) + float(response['oee2'])) / 2)
                    if response['pounds1'] != "-" and response['pounds2'] != "-":
                        response['poundsTotal'] = str(float(response['pounds1']) + float(response['pounds2']))
                    if response['waste1'] != "-" and response['waste2'] != "-":
                        response['wasteTotal'] = str(float(response['waste1']) + float(response['waste2']))
                except (ValueError, TypeError):
                    pass  # Keep defaults if calculation fails

                return jsonify(response)

    except Exception as e:
        logger.error(f"API report error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/comprehensive-report')
@login_required
def api_comprehensive_report():
    """Comprehensive API endpoint for report page with all metrics, charts, and table data"""
    week = request.args.get('week', 'latest')
    day = request.args.get('day', 'All')
    shift = request.args.get('shift', 'both')
    metric_type = request.args.get('metric', 'all')
    
    logger.info(f"Comprehensive report API call: week={week}, day={day}, shift={shift}, metric={metric_type}")
    
    # Get the latest week from week_submissions if needed
    if week == "latest":
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT sheet_name as week_name
                        FROM weekly_sheets
                        WHERE is_active = true
                        ORDER BY created_at DESC
                        LIMIT 1
                    """)
                    result = cur.fetchone()
                    week = result['week_name'] if result else None
        except Exception as e:
            logger.error(f"Error getting latest week: {e}")
            week = None
    
    if not week:
        return jsonify({'error': 'No valid week found'}), 404
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Use the correct schema - get data from week_submissions and shift metrics tables
                query_conditions = ["ws.week_name = %s"]
                query_params = [week]
                
                if day != 'All':
                    query_conditions.append("ws.day_of_week = %s")
                    query_params.append(day)
                
                where_clause = " AND ".join(query_conditions)
                
                # Get combined metrics data from the current database schema
                cur.execute(f"""
                    SELECT
                        ws.day_of_week,
                        -- Combined auto-calculated data from both_shifts_metrics
                        bs.die_cut1_oee_pct as combined_die_cut1_oee_pct,
                        bs.die_cut2_oee_pct as combined_die_cut2_oee_pct,
                        bs.oee_avg_pct as combined_oee_avg,
                        bs.die_cut1_lbs as combined_die_cut1_pounds,
                        bs.die_cut2_lbs as combined_die_cut2_pounds,
                        bs.pounds_total as combined_pounds_total,
                        bs.die_cut1_waste_lb as combined_die_cut1_waste_lbs,
                        bs.die_cut2_waste_lb as combined_die_cut2_waste_lbs,
                        bs.die_cut1_waste_pct as combined_die_cut1_waste_pct,
                        bs.die_cut2_waste_pct as combined_die_cut2_waste_pct,
                        bs.waste_avg_pct as combined_waste_avg,
                        -- Individual shift data for detailed breakdown
                        fs.die_cut1_oee_pct as first_die_cut1_oee_pct,
                        fs.die_cut2_oee_pct as first_die_cut2_oee_pct,
                        fs.die_cut1_lbs as first_die_cut1_pounds,
                        fs.die_cut2_lbs as first_die_cut2_pounds,
                        fs.die_cut1_waste_lb as first_die_cut1_waste_lbs,
                        fs.die_cut2_waste_lb as first_die_cut2_waste_lbs,
                        ss.die_cut1_oee_pct as second_die_cut1_oee_pct,
                        ss.die_cut2_oee_pct as second_die_cut2_oee_pct,
                        ss.die_cut1_lbs as second_die_cut1_pounds,
                        ss.die_cut2_lbs as second_die_cut2_pounds,
                        ss.die_cut1_waste_lb as second_die_cut1_waste_lbs,
                        ss.die_cut2_waste_lb as second_die_cut2_waste_lbs
                    FROM week_submissions ws
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    WHERE {where_clause}
                    ORDER BY
                        CASE ws.day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                        END
                """, query_params)
                
                metrics_data = cur.fetchall()
                
                # Process data for response
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                
                # Initialize data structures with float values
                oee_data = [0.0] * 5
                waste_data = [0.0] * 5
                oee_first_shift = [0.0] * 5
                waste_first_shift = [0.0] * 5
                oee_second_shift = [0.0] * 5
                waste_second_shift = [0.0] * 5
                pounds_first_shift = [0.0] * 5
                pounds_second_shift = [0.0] * 5

                # Process metrics data using auto-calculated values where available
                for metric in metrics_data:
                    if metric['day_of_week'] not in days:
                        continue
                        
                    day_idx = days.index(metric['day_of_week'])
                    
                    # Use auto-calculated combined values from both_shifts_metrics if available
                    if metric['combined_oee_avg'] is not None:
                        # Use the database's auto-calculated combined OEE average
                        oee_data[day_idx] = float(metric['combined_oee_avg'])
                    else:
                        # Fallback to manual calculation if combined data not available
                        first_oee1 = float(metric['first_die_cut1_oee_pct'] or 0)
                        first_oee2 = float(metric['first_die_cut2_oee_pct'] or 0)
                        second_oee1 = float(metric['second_die_cut1_oee_pct'] or 0)
                        second_oee2 = float(metric['second_die_cut2_oee_pct'] or 0)
                        
                        first_avg_oee = (first_oee1 + first_oee2) / 2 if first_oee1 > 0 and first_oee2 > 0 else (first_oee1 or first_oee2)
                        second_avg_oee = (second_oee1 + second_oee2) / 2 if second_oee1 > 0 and second_oee2 > 0 else (second_oee1 or second_oee2)
                        combined_oee = (first_avg_oee + second_avg_oee) / 2 if first_avg_oee > 0 and second_avg_oee > 0 else (first_avg_oee or second_avg_oee)
                        oee_data[day_idx] = combined_oee
                    
                    # Use auto-calculated combined waste percentage if available
                    if metric['combined_waste_avg'] is not None:
                        waste_data[day_idx] = float(metric['combined_waste_avg'])
                        logger.info(f"🔧 DEBUG Combined Waste - Day: {metric['day_of_week']}, Using DB auto-calculated: {metric['combined_waste_avg']}%")
                    else:
                        # Fallback to manual calculation
                        first_pounds1 = float(metric['first_die_cut1_pounds'] or 0)
                        first_pounds2 = float(metric['first_die_cut2_pounds'] or 0)
                        second_pounds1 = float(metric['second_die_cut1_pounds'] or 0)
                        second_pounds2 = float(metric['second_die_cut2_pounds'] or 0)
                        first_waste1 = float(metric['first_die_cut1_waste_lbs'] or 0)
                        first_waste2 = float(metric['first_die_cut2_waste_lbs'] or 0)
                        second_waste1 = float(metric['second_die_cut1_waste_lbs'] or 0)
                        second_waste2 = float(metric['second_die_cut2_waste_lbs'] or 0)
                        
                        first_total_pounds = first_pounds1 + first_pounds2
                        second_total_pounds = second_pounds1 + second_pounds2
                        first_total_waste = first_waste1 + first_waste2
                        second_total_waste = second_waste1 + second_waste2
                        
                        first_waste_pct = (first_total_waste / first_total_pounds * 100) if first_total_pounds > 0 else 0
                        second_waste_pct = (second_total_waste / second_total_pounds * 100) if second_total_pounds > 0 else 0
                        combined_waste = (first_waste_pct + second_waste_pct) / 2 if first_waste_pct > 0 and second_waste_pct > 0 else (first_waste_pct or second_waste_pct)
                        waste_data[day_idx] = combined_waste
                    
                    # Calculate individual shift data for breakdown charts
                    first_oee1 = float(metric['first_die_cut1_oee_pct'] or 0)
                    first_oee2 = float(metric['first_die_cut2_oee_pct'] or 0)
                    second_oee1 = float(metric['second_die_cut1_oee_pct'] or 0)
                    second_oee2 = float(metric['second_die_cut2_oee_pct'] or 0)
                    
                    first_avg_oee = (first_oee1 + first_oee2) / 2 if first_oee1 > 0 and first_oee2 > 0 else (first_oee1 or first_oee2)
                    second_avg_oee = (second_oee1 + second_oee2) / 2 if second_oee1 > 0 and second_oee2 > 0 else (second_oee1 or second_oee2)
                    
                    oee_first_shift[day_idx] = first_avg_oee
                    oee_second_shift[day_idx] = second_avg_oee
                    
                    # Calculate production totals
                    first_pounds1 = float(metric['first_die_cut1_pounds'] or 0)
                    first_pounds2 = float(metric['first_die_cut2_pounds'] or 0)
                    second_pounds1 = float(metric['second_die_cut1_pounds'] or 0)
                    second_pounds2 = float(metric['second_die_cut2_pounds'] or 0)
                    
                    pounds_first_shift[day_idx] = first_pounds1 + first_pounds2
                    pounds_second_shift[day_idx] = second_pounds1 + second_pounds2
                    
                    # Calculate waste percentages for individual shifts
                    first_waste1 = float(metric['first_die_cut1_waste_lbs'] or 0)
                    first_waste2 = float(metric['first_die_cut2_waste_lbs'] or 0)
                    second_waste1 = float(metric['second_die_cut1_waste_lbs'] or 0)
                    second_waste2 = float(metric['second_die_cut2_waste_lbs'] or 0)
                    
                    first_total_pounds = first_pounds1 + first_pounds2
                    second_total_pounds = second_pounds1 + second_pounds2
                    first_total_waste = first_waste1 + first_waste2
                    second_total_waste = second_waste1 + second_waste2
                    
                    first_waste_pct = (first_total_waste / first_total_pounds * 100) if first_total_pounds > 0 else 0
                    second_waste_pct = (second_total_waste / second_total_pounds * 100) if second_total_pounds > 0 else 0
                    
                    # DEBUG: Log second shift waste calculations for accuracy verification
                    logger.info(f"🔧 DEBUG Second Shift Waste - Day: {metric['day_of_week']}, "
                               f"DC1_waste: {second_waste1}, DC2_waste: {second_waste2}, "
                               f"Total_waste: {second_total_waste}, Total_pounds: {second_total_pounds}, "
                               f"Calculated_%: {second_waste_pct}, DB_avg_%: {metric.get('second_shift_avg_waste', 'N/A')}")
                    
                    waste_first_shift[day_idx] = first_waste_pct
                    waste_second_shift[day_idx] = second_waste_pct

                # Calculate averages
                def calculate_avg(data_list):
                    non_zero_values = [x for x in data_list if x != 0]
                    return round(sum(non_zero_values) / len(non_zero_values), 2) if non_zero_values else 0

                # Calculate derived metrics
                total_production = sum(pounds_first_shift) + sum(pounds_second_shift)
                avg_oee = calculate_avg(oee_data)
                avg_waste = calculate_avg(waste_data)

                # Calculate efficiency score (0-10 scale based on OEE, waste, production)
                efficiency_score = 0
                if avg_oee > 0:
                    oee_score = (avg_oee / 100) * 4  # Max 4 points for OEE
                    waste_score = max(0, (1 - avg_waste / 3.75)) * 3  # Max 3 points for waste (3.75% target)
                    production_score = min((total_production / 15000), 1) * 3  # Max 3 points for production
                    efficiency_score = min(10, oee_score + waste_score + production_score)
                
                # Get individual line data for detailed table (use most recent data)
                line_data = {
                    'oee1': 0.0, 'oee2': 0.0, 'pounds1': 0.0, 'pounds2': 0.0, 'waste1': 0.0, 'waste2': 0.0,
                    'oee1Avg': 0.0, 'oee2Avg': 0.0, 'pounds1Avg': 0.0, 'pounds2Avg': 0.0, 'waste1Avg': 0.0, 'waste2Avg': 0.0
                }
                
                # Calculate line-specific metrics by averaging across available days
                oee1_values = []
                oee2_values = []
                pounds1_values = []
                pounds2_values = []
                waste1_values = []
                waste2_values = []
                
                for metric in metrics_data:
                    if metric['combined_die_cut1_oee_pct'] is not None:
                        oee1_values.append(float(metric['combined_die_cut1_oee_pct']))
                    if metric['combined_die_cut2_oee_pct'] is not None:
                        oee2_values.append(float(metric['combined_die_cut2_oee_pct']))
                    if metric['combined_die_cut1_pounds'] is not None:
                        pounds1_values.append(float(metric['combined_die_cut1_pounds']))
                    if metric['combined_die_cut2_pounds'] is not None:
                        pounds2_values.append(float(metric['combined_die_cut2_pounds']))
                    if metric['combined_die_cut1_waste_lbs'] is not None:
                        waste1_values.append(float(metric['combined_die_cut1_waste_lbs']))
                    if metric['combined_die_cut2_waste_lbs'] is not None:
                        waste2_values.append(float(metric['combined_die_cut2_waste_lbs']))
                
                line_data['oee1'] = calculate_avg(oee1_values)
                line_data['oee2'] = calculate_avg(oee2_values)
                line_data['pounds1'] = sum(pounds1_values)
                line_data['pounds2'] = sum(pounds2_values)
                line_data['waste1'] = sum(waste1_values)
                line_data['waste2'] = sum(waste2_values)
                
                # Averages are same as current values in this case
                line_data['oee1Avg'] = line_data['oee1']
                line_data['oee2Avg'] = line_data['oee2']
                line_data['pounds1Avg'] = line_data['pounds1']
                line_data['pounds2Avg'] = line_data['pounds2']
                line_data['waste1Avg'] = line_data['waste1']
                line_data['waste2Avg'] = line_data['waste2']
                
                # Find best and worst performing days
                oee_best_idx = oee_data.index(max(oee_data)) if max(oee_data) > 0 else 0
                oee_worst_idx = oee_data.index(min([x for x in oee_data if x > 0])) if any(x > 0 for x in oee_data) else 0
                
                waste_best_idx = waste_data.index(min([x for x in waste_data if x > 0])) if any(x > 0 for x in waste_data) else 0
                waste_worst_idx = waste_data.index(max(waste_data)) if max(waste_data) > 0 else 0
                
                # Build comprehensive response
                response_data = {
                    # Basic info
                    'week': week,
                    'period': day,
                    'shift': shift,
                    
                    # Key metrics for cards
                    'oeeCurrentValue': avg_oee,
                    'wasteCurrentValue': avg_waste,
                    'productionCurrentValue': round(total_production, 0),
                    'efficiencyCurrentValue': round(efficiency_score, 1),
                    
                    # Chart data
                    'oeeChartData': [round(x, 1) for x in oee_data],
                    'wasteChartData': [round(x, 2) for x in waste_data],
                    'oeeFirstShift': [round(x, 1) for x in oee_first_shift],
                    'oeeSecondShift': [round(x, 1) for x in oee_second_shift],
                    'wasteFirstShift': [round(x, 2) for x in waste_first_shift],
                    'wasteSecondShift': [round(x, 2) for x in waste_second_shift],
                    'poundsFirstShift': [round(x, 1) for x in pounds_first_shift],
                    'poundsSecondShift': [round(x, 1) for x in pounds_second_shift],
                    
                    # Chart insights
                    'oeeBestDay': f"{days[oee_best_idx]} - {oee_data[oee_best_idx]:.1f}%",
                    'oeeWorstDay': f"{days[oee_worst_idx]} - {oee_data[oee_worst_idx]:.1f}%",
                    'wasteBestDay': f"{days[waste_best_idx]} - {waste_data[waste_best_idx]:.2f}%",
                    'wasteWorstDay': f"{days[waste_worst_idx]} - {waste_data[waste_worst_idx]:.2f}%",
                    
                    # Detailed table data
                    'oee1': round(line_data['oee1'], 1),
                    'oee2': round(line_data['oee2'], 1),
                    'oeeTotal': avg_oee,
                    'pounds1': round(line_data['pounds1'], 0),
                    'pounds2': round(line_data['pounds2'], 0),
                    'poundsTotal': round(total_production, 0),
                    'waste1': f"{round(line_data['waste1'], 1)} lbs",
                    'waste2': f"{round(line_data['waste2'], 1)} lbs",
                    'wasteTotal': f"{avg_waste}%",
                    'oee1Avg': round(line_data['oee1Avg'], 1),
                    'oee2Avg': round(line_data['oee2Avg'], 1),
                    'oeeTotalAvg': avg_oee,
                    'pounds1Avg': round(line_data['pounds1Avg'], 0),
                    'pounds2Avg': round(line_data['pounds2Avg'], 0),
                    'poundsTotalAvg': round(total_production, 0),
                    'waste1Avg': f"{round(line_data['waste1Avg'], 1)} lbs",
                    'waste2Avg': f"{round(line_data['waste2Avg'], 1)} lbs",
                    'wasteTotalAvg': f"{avg_waste}%",
                    
                    # Status calculations
                    'oeeStatus': 'On Target' if avg_oee >= 70 else 'Below Target',
                    'wasteStatus': 'Below Target' if avg_waste <= 3.75 else 'Above Target',
                    'productionStatus': 'Normal',
                    'efficiencyStatus': 'Good' if efficiency_score >= 7 else 'Fair'
                }
                
                return jsonify(response_data)
                
    except Exception as e:
        logger.error(f"Comprehensive report API error: {e}")
        return jsonify({'error': f'Unable to generate report: {str(e)}'}), 500

@app.route('/api/weekly-metrics-charts')
@login_required
def get_weekly_metrics_charts():
    """API endpoint for weekly metrics data specifically formatted for report.html charts"""
    week = request.args.get('week', 'latest')
    
    logger.info(f"Weekly metrics charts API call: week={week}")
    
    if week == "latest":
        week = get_latest_week_sheet()
    
    if not week:
        return jsonify({'error': 'No valid week found'}), 404
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get combined metrics data from the both_shifts_metrics table
                query = """
                    SELECT
                        ws.day_of_week,
                        -- First shift specific data
                        fs.die_cut1_oee_pct as first_shift_oee,
                        fs.die_cut2_oee_pct as first_shift_oee2,
                        fs.die_cut1_lbs + fs.die_cut2_lbs as first_shift_total_lbs,
                        fs.die_cut1_waste_lb + fs.die_cut2_waste_lb as first_shift_total_waste,
                        fs.oee_avg_pct as first_shift_avg_oee,
                        fs.waste_avg_pct as first_shift_avg_waste,
                        -- Second shift specific data
                        ss.die_cut1_oee_pct as second_shift_oee,
                        ss.die_cut2_oee_pct as second_shift_oee2,
                        ss.die_cut1_lbs + ss.die_cut2_lbs as second_shift_total_lbs,
                        ss.die_cut1_waste_lb + ss.die_cut2_waste_lb as second_shift_total_waste,
                        ss.oee_avg_pct as second_shift_avg_oee,
                        ss.waste_avg_pct as second_shift_avg_waste,
                        -- Combined (both shifts) data
                        bs.oee_avg_pct as total_oee,
                        bs.waste_avg_pct as total_waste,
                        bs.pounds_total as total_production
                    FROM week_submissions ws
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    WHERE ws.week_name = %s
                    ORDER BY
                        CASE ws.day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                        END
                """
                
                cur.execute(query, [week])
                metrics_data = cur.fetchall()
                
                # Initialize data structures for all 5 weekdays
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                
                # Initialize arrays with default values
                first_shift_data = {
                    'oee': [0.0] * 5,
                    'waste': [0.0] * 5,
                    'production': [0.0] * 5
                }
                
                second_shift_data = {
                    'oee': [0.0] * 5,
                    'waste': [0.0] * 5,
                    'production': [0.0] * 5
                }
                
                both_shifts_data = {
                    'oee': [0.0] * 5,
                    'waste': [0.0] * 5,
                    'production': [0.0] * 5
                }
                
                # Process metrics data
                for metric in metrics_data:
                    if metric['day_of_week'] not in days:
                        continue
                        
                    day_idx = days.index(metric['day_of_week'])
                    
                    # First shift data
                    if metric['first_shift_avg_oee'] is not None:
                        first_shift_data['oee'][day_idx] = float(metric['first_shift_avg_oee'])
                    if metric['first_shift_avg_waste'] is not None:
                        first_shift_data['waste'][day_idx] = float(metric['first_shift_avg_waste'])
                    if metric['first_shift_total_lbs'] is not None:
                        first_shift_data['production'][day_idx] = float(metric['first_shift_total_lbs'])
                    
                    # Second shift data
                    if metric['second_shift_avg_oee'] is not None:
                        second_shift_data['oee'][day_idx] = float(metric['second_shift_avg_oee'])
                    if metric['second_shift_avg_waste'] is not None:
                        second_shift_data['waste'][day_idx] = float(metric['second_shift_avg_waste'])
                        logger.info(f"🔧 DEBUG Chart API Second Shift - Day: {metric['day_of_week']}, DB_waste_%: {metric['second_shift_avg_waste']}")
                    if metric['second_shift_total_lbs'] is not None:
                        second_shift_data['production'][day_idx] = float(metric['second_shift_total_lbs'])
                    
                    # Both shifts combined data
                    if metric['total_oee'] is not None:
                        both_shifts_data['oee'][day_idx] = float(metric['total_oee'])
                    if metric['total_waste'] is not None:
                        both_shifts_data['waste'][day_idx] = float(metric['total_waste'])
                    if metric['total_production'] is not None:
                        both_shifts_data['production'][day_idx] = float(metric['total_production'])
                
                # Calculate averages for summary
                def safe_avg(values):
                    non_zero = [v for v in values if v > 0]
                    return round(sum(non_zero) / len(non_zero), 2) if non_zero else 0
                
                response_data = {
                    'week': week,
                    'days': days,
                    'first_shift': {
                        'oee': [round(v, 1) for v in first_shift_data['oee']],
                        'waste': [round(v, 2) for v in first_shift_data['waste']],
                        'production': [round(v, 1) for v in first_shift_data['production']],
                        'averages': {
                            'oee': safe_avg(first_shift_data['oee']),
                            'waste': safe_avg(first_shift_data['waste']),
                            'production': safe_avg(first_shift_data['production'])
                        }
                    },
                    'second_shift': {
                        'oee': [round(v, 1) for v in second_shift_data['oee']],
                        'waste': [round(v, 2) for v in second_shift_data['waste']],
                        'production': [round(v, 1) for v in second_shift_data['production']],
                        'averages': {
                            'oee': safe_avg(second_shift_data['oee']),
                            'waste': safe_avg(second_shift_data['waste']),
                            'production': safe_avg(second_shift_data['production'])
                        }
                    },
                    'both_shifts': {
                        'oee': [round(v, 1) for v in both_shifts_data['oee']],
                        'waste': [round(v, 2) for v in both_shifts_data['waste']],
                        'production': [round(v, 1) for v in both_shifts_data['production']],
                        'averages': {
                            'oee': safe_avg(both_shifts_data['oee']),
                            'waste': safe_avg(both_shifts_data['waste']),
                            'production': safe_avg(both_shifts_data['production'])
                        }
                    }
                }
                
                return jsonify(response_data)
                
    except Exception as e:
        logger.error(f"Weekly metrics charts error: {e}")
        # Return empty data structure on error
        return jsonify({
            'week': week or 'No Week',
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'first_shift': {
                'oee': [0.0] * 5,
                'waste': [0.0] * 5,
                'production': [0.0] * 5,
                'averages': {'oee': 0, 'waste': 0, 'production': 0}
            },
            'second_shift': {
                'oee': [0.0] * 5,
                'waste': [0.0] * 5,
                'production': [0.0] * 5,
                'averages': {'oee': 0, 'waste': 0, 'production': 0}
            },
            'both_shifts': {
                'oee': [0.0] * 5,
                'waste': [0.0] * 5,
                'production': [0.0] * 5,
                'averages': {'oee': 0, 'waste': 0, 'production': 0}
            }
        })

@app.route('/api/both-shifts-records', methods=['GET'])
@login_required
def get_both_shifts_records():
    """API endpoint to get both_shifts_metrics records with filtering support"""
    try:
        # Get filter parameters from query string
        week_filter = request.args.get('week', '').strip()
        day_filter = request.args.get('day', '').strip()
        shift_filter = request.args.get('shift', '').strip()
        
        logger.info(f"🔍 Both-shifts API called with filters: week={week_filter}, day={day_filter}, shift={shift_filter}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build dynamic query with filtering
                base_query = """
                    SELECT
                        bs.id,
                        ws.week_name,
                        ws.day_of_week,
                        bs.created_at as submission_date,
                        -- Combined metrics from both_shifts_metrics
                        bs.die_cut1_oee_pct,
                        bs.die_cut2_oee_pct,
                        bs.oee_avg_pct as total_oee,
                        bs.die_cut1_lbs,
                        bs.die_cut2_lbs,
                        bs.pounds_total as total_production,
                        bs.die_cut1_waste_lb,
                        bs.die_cut2_waste_lb,
                        bs.die_cut1_waste_pct,
                        bs.die_cut2_waste_pct,
                        bs.waste_avg_pct as total_waste_percent,
                        -- First shift individual metrics
                        fs.die_cut1_oee_pct as first_shift_die_cut1_oee,
                        fs.die_cut2_oee_pct as first_shift_die_cut2_oee,
                        fs.oee_avg_pct as first_shift_oee,
                        fs.die_cut1_lbs as first_shift_die_cut1_lbs,
                        fs.die_cut2_lbs as first_shift_die_cut2_lbs,
                        fs.die_cut1_lbs + fs.die_cut2_lbs as first_shift_production,
                        fs.die_cut1_waste_lb as first_shift_die_cut1_waste,
                        fs.die_cut2_waste_lb as first_shift_die_cut2_waste,
                        fs.die_cut1_waste_pct as first_shift_die_cut1_waste_pct,
                        fs.die_cut2_waste_pct as first_shift_die_cut2_waste_pct,
                        fs.waste_avg_pct as first_shift_waste_percent,
                        -- Second shift individual metrics
                        ss.die_cut1_oee_pct as second_shift_die_cut1_oee,
                        ss.die_cut2_oee_pct as second_shift_die_cut2_oee,
                        ss.oee_avg_pct as second_shift_oee,
                        ss.die_cut1_lbs as second_shift_die_cut1_lbs,
                        ss.die_cut2_lbs as second_shift_die_cut2_lbs,
                        ss.die_cut1_lbs + ss.die_cut2_lbs as second_shift_production,
                        ss.die_cut1_waste_lb as second_shift_die_cut1_waste,
                        ss.die_cut2_waste_lb as second_shift_die_cut2_waste,
                        ss.die_cut1_waste_pct as second_shift_die_cut1_waste_pct,
                        ss.die_cut2_waste_pct as second_shift_die_cut2_waste_pct,
                        ss.waste_avg_pct as second_shift_waste_percent
                    FROM both_shifts_metrics bs
                    JOIN week_submissions ws ON bs.week_submission_id = ws.id
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                """
                
                # Build WHERE clause based on filters
                where_conditions = []
                query_params = []
                
                if week_filter and week_filter.lower() != 'all':
                    where_conditions.append("ws.week_name = %s")
                    query_params.append(week_filter)
                    logger.info(f"📊 Added week filter: {week_filter}")
                
                if day_filter and day_filter.lower() not in ['all', '']:
                    # Ensure exact case-sensitive matching for day names
                    valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                    if day_filter in valid_days:
                        where_conditions.append("TRIM(ws.day_of_week) = %s")
                        query_params.append(day_filter)
                        logger.info(f"🔧 DEBUG: Added day filter - requested_day: '{day_filter}'")
                    else:
                        logger.warning(f"🔧 DEBUG: Invalid day filter ignored: '{day_filter}'")
                
                # For shift filtering, we filter based on whether shift data exists
                if shift_filter and shift_filter.lower() not in ['all', 'both', '']:
                    if shift_filter.lower() in ['first', 'first shift']:
                        where_conditions.append("fs.id IS NOT NULL")
                        logger.info("📊 Added first shift filter")
                    elif shift_filter.lower() in ['second', 'second shift']:
                        where_conditions.append("ss.id IS NOT NULL")
                        logger.info("📊 Added second shift filter")
                
                # Add WHERE clause if there are conditions
                if where_conditions:
                    base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Add ORDER BY clause
                base_query += " ORDER BY bs.created_at DESC LIMIT 100"
                
                logger.info(f"📊 Executing filtered query with {len(query_params)} parameters")
                logger.info(f"🔧 DEBUG: Final SQL query: {base_query}")
                logger.info(f"🔧 DEBUG: Query parameters: {query_params}")
                cur.execute(base_query, query_params)
                
                records = cur.fetchall()
                logger.info(f"📊 Retrieved {len(records)} filtered records")
                
                # Add detailed logging of what data we actually got
                for i, record in enumerate(records[:3]):  # Log first 3 records
                    logger.info(f"🔧 DEBUG Record {i+1}: day='{record.get('day_of_week')}', week='{record.get('week_name')}', waste={record.get('total_waste_percent')}")
                
                # Format records for frontend
                formatted_records = []
                for record in records:
                    formatted_records.append({
                        'id': str(record['id']),
                        'week_name': record['week_name'],
                        'day_of_week': record['day_of_week'],
                        'submission_date': record['submission_date'].isoformat() if record['submission_date'] else None,
                        # Combined totals
                        'total_oee': float(record['total_oee']) if record['total_oee'] else 0,
                        'total_waste_percent': float(record['total_waste_percent']) if record['total_waste_percent'] else 0,
                        'total_production': float(record['total_production']) if record['total_production'] else 0,
                        # First shift individual die cut values
                        'first_shift_die_cut1_oee': float(record['first_shift_die_cut1_oee']) if record['first_shift_die_cut1_oee'] else 0,
                        'first_shift_die_cut2_oee': float(record['first_shift_die_cut2_oee']) if record['first_shift_die_cut2_oee'] else 0,
                        'first_shift_oee': float(record['first_shift_oee']) if record['first_shift_oee'] else 0,
                        'first_shift_die_cut1_lbs': float(record['first_shift_die_cut1_lbs']) if record['first_shift_die_cut1_lbs'] else 0,
                        'first_shift_die_cut2_lbs': float(record['first_shift_die_cut2_lbs']) if record['first_shift_die_cut2_lbs'] else 0,
                        'first_shift_production': float(record['first_shift_production']) if record['first_shift_production'] else 0,
                        'first_shift_die_cut1_waste': float(record['first_shift_die_cut1_waste']) if record['first_shift_die_cut1_waste'] else 0,
                        'first_shift_die_cut2_waste': float(record['first_shift_die_cut2_waste']) if record['first_shift_die_cut2_waste'] else 0,
                        'first_shift_die_cut1_waste_pct': float(record['first_shift_die_cut1_waste_pct']) if record['first_shift_die_cut1_waste_pct'] else 0,
                        'first_shift_die_cut2_waste_pct': float(record['first_shift_die_cut2_waste_pct']) if record['first_shift_die_cut2_waste_pct'] else 0,
                        'first_shift_waste_percent': float(record['first_shift_waste_percent']) if record['first_shift_waste_percent'] else 0,
                        # Second shift individual die cut values
                        'second_shift_die_cut1_oee': float(record['second_shift_die_cut1_oee']) if record['second_shift_die_cut1_oee'] else 0,
                        'second_shift_die_cut2_oee': float(record['second_shift_die_cut2_oee']) if record['second_shift_die_cut2_oee'] else 0,
                        'second_shift_oee': float(record['second_shift_oee']) if record['second_shift_oee'] else 0,
                        'second_shift_die_cut1_lbs': float(record['second_shift_die_cut1_lbs']) if record['second_shift_die_cut1_lbs'] else 0,
                        'second_shift_die_cut2_lbs': float(record['second_shift_die_cut2_lbs']) if record['second_shift_die_cut2_lbs'] else 0,
                        'second_shift_production': float(record['second_shift_production']) if record['second_shift_production'] else 0,
                        'second_shift_die_cut1_waste': float(record['second_shift_die_cut1_waste']) if record['second_shift_die_cut1_waste'] else 0,
                        'second_shift_die_cut2_waste': float(record['second_shift_die_cut2_waste']) if record['second_shift_die_cut2_waste'] else 0,
                        'second_shift_die_cut1_waste_pct': float(record['second_shift_die_cut1_waste_pct']) if record['second_shift_die_cut1_waste_pct'] else 0,
                        'second_shift_die_cut2_waste_pct': float(record['second_shift_die_cut2_waste_pct']) if record['second_shift_die_cut2_waste_pct'] else 0,
                        'second_shift_waste_percent': float(record['second_shift_waste_percent']) if record['second_shift_waste_percent'] else 0,
                        # Combined die cut values
                        'both_shift_die_cut1_oee': float(record['die_cut1_oee_pct']) if record['die_cut1_oee_pct'] else 0,
                        'both_shift_die_cut2_oee': float(record['die_cut2_oee_pct']) if record['die_cut2_oee_pct'] else 0,
                        'both_shift_die_cut1_lbs': float(record['die_cut1_lbs']) if record['die_cut1_lbs'] else 0,
                        'both_shift_die_cut2_lbs': float(record['die_cut2_lbs']) if record['die_cut2_lbs'] else 0,
                        'both_shift_die_cut1_waste': float(record['die_cut1_waste_lb']) if record['die_cut1_waste_lb'] else 0,
                        'both_shift_die_cut2_waste': float(record['die_cut2_waste_lb']) if record['die_cut2_waste_lb'] else 0,
                        'both_shift_die_cut1_waste_pct': float(record['die_cut1_waste_pct']) if record['die_cut1_waste_pct'] else 0,
                        'both_shift_die_cut2_waste_pct': float(record['die_cut2_waste_pct']) if record['die_cut2_waste_pct'] else 0
                    })
                
                logger.info(f"📊 DEBUG: Retrieved {len(formatted_records)} both-shifts records with individual die cut values")
                return jsonify(formatted_records)
                
    except Exception as e:
        logger.error(f"📊 ERROR: Both shifts records error: {e}")
        return jsonify([]), 500

@app.route('/api/both-shifts-record/<record_id>', methods=['GET'])
@login_required
def get_both_shifts_record_by_id(record_id):
    """API endpoint to get a specific both_shifts_metrics record by ID"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        bs.id,
                        ws.week_name,
                        ws.day_of_week,
                        bs.created_at as submission_date,
                        -- Combined metrics from both_shifts_metrics
                        bs.die_cut1_oee_pct,
                        bs.die_cut2_oee_pct,
                        bs.oee_avg_pct as total_oee,
                        bs.die_cut1_lbs,
                        bs.die_cut2_lbs,
                        bs.pounds_total as total_production,
                        bs.die_cut1_waste_lb,
                        bs.die_cut2_waste_lb,
                        bs.die_cut1_waste_pct,
                        bs.die_cut2_waste_pct,
                        bs.waste_avg_pct as total_waste_percent,
                        -- First shift individual metrics
                        fs.die_cut1_oee_pct as first_shift_die_cut1_oee,
                        fs.die_cut2_oee_pct as first_shift_die_cut2_oee,
                        fs.oee_avg_pct as first_shift_oee,
                        fs.die_cut1_lbs as first_shift_die_cut1_lbs,
                        fs.die_cut2_lbs as first_shift_die_cut2_lbs,
                        fs.die_cut1_lbs + fs.die_cut2_lbs as first_shift_production,
                        fs.die_cut1_waste_lb as first_shift_die_cut1_waste,
                        fs.die_cut2_waste_lb as first_shift_die_cut2_waste,
                        fs.die_cut1_waste_pct as first_shift_die_cut1_waste_pct,
                        fs.die_cut2_waste_pct as first_shift_die_cut2_waste_pct,
                        fs.waste_avg_pct as first_shift_waste_percent,
                        -- Second shift individual metrics
                        ss.die_cut1_oee_pct as second_shift_die_cut1_oee,
                        ss.die_cut2_oee_pct as second_shift_die_cut2_oee,
                        ss.oee_avg_pct as second_shift_oee,
                        ss.die_cut1_lbs as second_shift_die_cut1_lbs,
                        ss.die_cut2_lbs as second_shift_die_cut2_lbs,
                        ss.die_cut1_lbs + ss.die_cut2_lbs as second_shift_production,
                        ss.die_cut1_waste_lb as second_shift_die_cut1_waste,
                        ss.die_cut2_waste_lb as second_shift_die_cut2_waste,
                        ss.die_cut1_waste_pct as second_shift_die_cut1_waste_pct,
                        ss.die_cut2_waste_pct as second_shift_die_cut2_waste_pct,
                        ss.waste_avg_pct as second_shift_waste_percent
                    FROM both_shifts_metrics bs
                    JOIN week_submissions ws ON bs.week_submission_id = ws.id
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    WHERE bs.id = %s
                """, (record_id,))
                
                record = cur.fetchone()
                
                if not record:
                    logger.warning(f"📊 WARNING: Record {record_id} not found")
                    return jsonify({'error': 'Record not found'}), 404
                
                # Format record for frontend
                formatted_record = {
                    'id': str(record['id']),
                    'week_name': record['week_name'],
                    'day_of_week': record['day_of_week'],
                    'submission_date': record['submission_date'].isoformat() if record['submission_date'] else None,
                    # Combined totals
                    'total_oee': float(record['total_oee']) if record['total_oee'] else 0,
                    'total_waste_percent': float(record['total_waste_percent']) if record['total_waste_percent'] else 0,
                    'total_production': float(record['total_production']) if record['total_production'] else 0,
                    # First shift individual die cut values
                    'first_shift_die_cut1_oee': float(record['first_shift_die_cut1_oee']) if record['first_shift_die_cut1_oee'] else 0,
                    'first_shift_die_cut2_oee': float(record['first_shift_die_cut2_oee']) if record['first_shift_die_cut2_oee'] else 0,
                    'first_shift_oee': float(record['first_shift_oee']) if record['first_shift_oee'] else 0,
                    'first_shift_die_cut1_lbs': float(record['first_shift_die_cut1_lbs']) if record['first_shift_die_cut1_lbs'] else 0,
                    'first_shift_die_cut2_lbs': float(record['first_shift_die_cut2_lbs']) if record['first_shift_die_cut2_lbs'] else 0,
                    'first_shift_production': float(record['first_shift_production']) if record['first_shift_production'] else 0,
                    'first_shift_die_cut1_waste': float(record['first_shift_die_cut1_waste']) if record['first_shift_die_cut1_waste'] else 0,
                    'first_shift_die_cut2_waste': float(record['first_shift_die_cut2_waste']) if record['first_shift_die_cut2_waste'] else 0,
                    'first_shift_die_cut1_waste_pct': float(record['first_shift_die_cut1_waste_pct']) if record['first_shift_die_cut1_waste_pct'] else 0,
                    'first_shift_die_cut2_waste_pct': float(record['first_shift_die_cut2_waste_pct']) if record['first_shift_die_cut2_waste_pct'] else 0,
                    'first_shift_waste_percent': float(record['first_shift_waste_percent']) if record['first_shift_waste_percent'] else 0,
                    # Second shift individual die cut values
                    'second_shift_die_cut1_oee': float(record['second_shift_die_cut1_oee']) if record['second_shift_die_cut1_oee'] else 0,
                    'second_shift_die_cut2_oee': float(record['second_shift_die_cut2_oee']) if record['second_shift_die_cut2_oee'] else 0,
                    'second_shift_oee': float(record['second_shift_oee']) if record['second_shift_oee'] else 0,
                    'second_shift_die_cut1_lbs': float(record['second_shift_die_cut1_lbs']) if record['second_shift_die_cut1_lbs'] else 0,
                    'second_shift_die_cut2_lbs': float(record['second_shift_die_cut2_lbs']) if record['second_shift_die_cut2_lbs'] else 0,
                    'second_shift_production': float(record['second_shift_production']) if record['second_shift_production'] else 0,
                    'second_shift_die_cut1_waste': float(record['second_shift_die_cut1_waste']) if record['second_shift_die_cut1_waste'] else 0,
                    'second_shift_die_cut2_waste': float(record['second_shift_die_cut2_waste']) if record['second_shift_die_cut2_waste'] else 0,
                    'second_shift_die_cut1_waste_pct': float(record['second_shift_die_cut1_waste_pct']) if record['second_shift_die_cut1_waste_pct'] else 0,
                    'second_shift_die_cut2_waste_pct': float(record['second_shift_die_cut2_waste_pct']) if record['second_shift_die_cut2_waste_pct'] else 0,
                    'second_shift_waste_percent': float(record['second_shift_waste_percent']) if record['second_shift_waste_percent'] else 0,
                    # Combined die cut values
                    'both_shift_die_cut1_oee': float(record['die_cut1_oee_pct']) if record['die_cut1_oee_pct'] else 0,
                    'both_shift_die_cut2_oee': float(record['die_cut2_oee_pct']) if record['die_cut2_oee_pct'] else 0,
                    'both_shift_die_cut1_lbs': float(record['die_cut1_lbs']) if record['die_cut1_lbs'] else 0,
                    'both_shift_die_cut2_lbs': float(record['die_cut2_lbs']) if record['die_cut2_lbs'] else 0,
                    'both_shift_die_cut1_waste': float(record['die_cut1_waste_lb']) if record['die_cut1_waste_lb'] else 0,
                    'both_shift_die_cut2_waste': float(record['die_cut2_waste_lb']) if record['die_cut2_waste_lb'] else 0,
                    'both_shift_die_cut1_waste_pct': float(record['die_cut1_waste_pct']) if record['die_cut1_waste_pct'] else 0,
                    'both_shift_die_cut2_waste_pct': float(record['die_cut2_waste_pct']) if record['die_cut2_waste_pct'] else 0
                }
                
                logger.info(f"📊 DEBUG: Retrieved record {record_id} with individual die cut values")
                return jsonify(formatted_record)
                
    except Exception as e:
        logger.error(f"📊 ERROR: Both shifts record by ID error: {e}")
        return jsonify({'error': 'Failed to fetch record'}), 500



# Foreign Material Report API Routes
@app.route('/load-reports')
@login_required
def load_reports():
    """Legacy route for foreign material reports"""
    return redirect(url_for('get_report_names'))



@app.route('/get-report-names', methods=['GET'])
@login_required
def get_report_names():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT report_name, report_date 
                    FROM foreign_material_reports 
                    WHERE report_name IS NOT NULL AND report_name != ''
                    ORDER BY created_at DESC
                """)
                reports = cur.fetchall()

                report_list = []
                for report in reports:
                    name = report['report_name'].strip()
                    date = report['report_date'].strftime('%Y-%m-%d') if report['report_date'] else ''
                    if name and date:
                        report_list.append(f"{name}-{date}")

                return jsonify({"status": "success", "reports": report_list})

    except Exception as e:
        logger.error(f"Get report names error: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get-report-data', methods=['GET'])
@login_required
def get_report_data():
    try:
        report_key = request.args.get('report', '').strip()
        if not report_key:
            return jsonify({"status": "error", "message": "Missing report key."})

        report_name = report_key.split('-20')[0].strip()

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get report data
                cur.execute("""
                    SELECT * FROM foreign_material_reports 
                    WHERE report_name = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (report_name,))
                
                report = cur.fetchone()
                if not report:
                    return jsonify({"status": "error", "message": "Report not found."})

                # Get associated images
                cur.execute("""
                    SELECT image_url, image_name 
                    FROM fm_report_images 
                    WHERE report_id = %s
                    ORDER BY uploaded_at
                """, (report['id'],))
                
                images = [img['image_url'] for img in cur.fetchall()]
                
                # Convert report to dict and add images
                report_dict = dict(report)
                report_dict['images'] = images
                
                # Format dates and times for frontend
                if report_dict['report_date']:
                    report_dict['reportDate'] = report_dict['report_date'].strftime('%Y-%m-%d')
                if report_dict['time_reported']:
                    report_dict['time'] = report_dict['time_reported'].strftime('%H:%M')

                return jsonify({"status": "success", "data": report_dict})

    except Exception as e:
        logger.error(f"Get report data error: {e}")
        return jsonify({"status": "error", "message": str(e)})
    
    
@app.route('/api/submit-issue', methods=['POST'])
@login_required
def submit_issue():
    """API endpoint for submitting machine and quality issues"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'line', 'shift', 'issueDetails', 'reportDate', 'reportTime']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Get user information (keep as string for database compatibility)
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Unknown User')
        
        # Validate user_id exists
        if not user_id:
            logger.error("No user_id in session")
            return jsonify({
                'success': False,
                'message': 'Invalid user session'
            }), 400
        
        # Validate date and time format
        try:
            report_date = datetime.strptime(data['reportDate'], '%Y-%m-%d').date()
            report_time = datetime.strptime(data['reportTime'], '%H:%M').time()
        except ValueError as e:
            return jsonify({
                'success': False, 
                'message': 'Invalid date or time format'
            }), 400
            
        # Validate enum values
        valid_lines = ['Die-Cut 1', 'Die-Cut 2']
        valid_shifts = ['First Shift', 'Second Shift']
        
        if data['line'] not in valid_lines:
            return jsonify({
                'success': False, 
                'message': 'Invalid line selection'
            }), 400
            
        if data['shift'] not in valid_shifts:
            return jsonify({
                'success': False, 
                'message': 'Invalid shift selection'
            }), 400
            
        # Insert issue into database
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO issues (
                        title, line, shift, issue_details, submitted_by,
                        report_date, report_time, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data['title'],
                    data['line'],
                    data['shift'],
                    data['issueDetails'],
                    user_name,
                    report_date,
                    report_time,
                    user_id
                ))
                conn.commit()
                
                # Log the submission
                log_submission(
                    user_id, user_name, session.get('email', ''), 
                    'issue_report', 
                    f"Issue reported: {data['line']} - {data['shift']}"
                )
                
                logger.info(f"Issue submitted by {user_name}: {data['line']} - {data['shift']}")
                
                return jsonify({
                    'success': True,
                    'message': 'Issue report submitted successfully'
                })
                
    except Exception as e:
        logger.error(f"Submit issue error: {e}")
        return jsonify({
            'success': False, 
            'message': 'An error occurred while submitting the issue report'
        }), 500

@app.route('/api/issues', methods=['GET'])
@login_required
def get_issues():
    """API endpoint to retrieve issues table data with filtering support"""
    try:
        # Get filter parameters from query string
        line_filter = request.args.get('line', '').strip()
        shift_filter = request.args.get('shift', '').strip()
        date_filter = request.args.get('date', '').strip()
        submitter_filter = request.args.get('submitter', '').strip()
        
        # Build dynamic query based on filters
        base_query = """
            SELECT
                i.id,
                i.title,
                i.line,
                i.shift,
                i.issue_details,
                i.submitted_by,
                i.report_date,
                i.report_time,
                i.created_at,
                u.first_name || ' ' || u.last_name as created_by_name
            FROM issues i
            LEFT JOIN users u ON i.created_by = u.id
        """
        
        # Build WHERE clause
        where_conditions = []
        query_params = []
        
        if line_filter:
            where_conditions.append("i.line = %s")
            query_params.append(line_filter)
            
        if shift_filter:
            where_conditions.append("i.shift = %s")
            query_params.append(shift_filter)
            
        if date_filter:
            where_conditions.append("i.report_date = %s")
            query_params.append(date_filter)
            
        if submitter_filter:
            where_conditions.append("i.submitted_by ILIKE %s")
            query_params.append(f"%{submitter_filter}%")
        
        # Add WHERE clause if there are conditions
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        # Add ORDER BY clause
        base_query += " ORDER BY i.created_at DESC"
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(base_query, query_params)
                
                issues = cur.fetchall()
                
                # Format the data for frontend
                formatted_issues = []
                for issue in issues:
                    formatted_issues.append({
                        'id': str(issue['id']),
                        'title': issue['title'],
                        'line': issue['line'],
                        'shift': issue['shift'],
                        'issue_details': issue['issue_details'],
                        'submitted_by': issue['submitted_by'],
                        'report_date': issue['report_date'].strftime('%Y-%m-%d') if issue['report_date'] else '',
                        'report_time': issue['report_time'].strftime('%H:%M') if issue['report_time'] else '',
                        'created_at': issue['created_at'].strftime('%Y-%m-%d %H:%M:%S') if issue['created_at'] else '',
                        'created_by_name': issue['created_by_name'] or 'Unknown'
                    })
                
                return jsonify({
                    'success': True,
                    'data': formatted_issues,
                    'count': len(formatted_issues)
                })
                
    except Exception as e:
        logger.error(f"Get issues error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while retrieving issues'
        }), 500

@app.route('/api/issues/<issue_id>', methods=['GET'])
@login_required
def get_issue_by_id(issue_id):
    """API endpoint to retrieve a specific issue by ID"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        i.id,
                        i.title,
                        i.line,
                        i.shift,
                        i.issue_details,
                        i.submitted_by,
                        i.report_date,
                        i.report_time,
                        i.created_at
                    FROM issues i
                    WHERE i.id = %s
                """, (issue_id,))
                
                issue = cur.fetchone()
                
                if not issue:
                    return jsonify({
                        'success': False,
                        'message': 'Issue not found'
                    }), 404
                
                # Format the data for frontend
                formatted_issue = {
                    'id': str(issue['id']),
                    'title': issue['title'],
                    'line': issue['line'],
                    'shift': issue['shift'],
                    'issue_details': issue['issue_details'],
                    'submitted_by': issue['submitted_by'],
                    'report_date': issue['report_date'].strftime('%Y-%m-%d') if issue['report_date'] else '',
                    'report_time': issue['report_time'].strftime('%H:%M') if issue['report_time'] else '',
                    'created_at': issue['created_at'].strftime('%Y-%m-%d %H:%M:%S') if issue['created_at'] else ''
                }
                
                return jsonify({
                    'success': True,
                    'data': formatted_issue
                })
                
    except Exception as e:
        logger.error(f"Get issue by ID error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while retrieving the issue'
        }), 500

@app.route('/api/issues/<issue_id>', methods=['PUT'])
@login_required
def update_issue(issue_id):
    """API endpoint to update an issue (only by original submitter)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'line', 'shift', 'issueDetails', 'reportDate', 'reportTime']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        current_user = session.get('user_full_name', 'Unknown User')
        user_id = session.get('user_id')
        
        # Validate date and time format
        try:
            report_date = datetime.strptime(data['reportDate'], '%Y-%m-%d').date()
            report_time = datetime.strptime(data['reportTime'], '%H:%M').time()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date or time format'
            }), 400
            
        # Validate enum values
        valid_lines = ['Die-Cut 1', 'Die-Cut 2']
        valid_shifts = ['First Shift', 'Second Shift']
        
        if data['line'] not in valid_lines:
            return jsonify({
                'success': False,
                'message': 'Invalid line selection'
            }), 400
            
        if data['shift'] not in valid_shifts:
            return jsonify({
                'success': False,
                'message': 'Invalid shift selection'
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First check if the issue exists and get the current submitted_by value
                cur.execute("""
                    SELECT submitted_by FROM issues WHERE id = %s
                """, (issue_id,))
                
                result = cur.fetchone()
                if not result:
                    return jsonify({
                        'success': False,
                        'message': 'Issue not found'
                    }), 404
                    
                # Check if the current user is the one who submitted the issue
                if result[0] != current_user:
                    return jsonify({
                        'success': False,
                        'message': 'You do not have permission to edit this issue'
                    }), 403
                
                # Update the issue
                cur.execute("""
                    UPDATE issues
                    SET title = %s, line = %s, shift = %s, issue_details = %s,
                        report_date = %s, report_time = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    data['title'],
                    data['line'],
                    data['shift'],
                    data['issueDetails'],
                    report_date,
                    report_time,
                    issue_id
                ))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to update issue'
                    }), 500
                
                conn.commit()
                
                # Log the update
                log_submission(
                    user_id, current_user, session.get('email', ''),
                    'issue_update',
                    f"Issue updated: {data['line']} - {data['shift']}"
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Issue updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Update issue error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while updating the issue'
        }), 500

@app.route('/api/issues/<issue_id>', methods=['DELETE'])
@login_required
def delete_issue(issue_id):
    """API endpoint to delete an issue (only by original submitter)"""
    try:
        current_user = session.get('user_full_name', 'Unknown User')
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First check if the issue exists and get the current submitted_by value
                cur.execute("""
                    SELECT submitted_by FROM issues WHERE id = %s
                """, (issue_id,))
                
                result = cur.fetchone()
                if not result:
                    return jsonify({
                        'success': False,
                        'message': 'Issue not found'
                    }), 404
                    
                # Check if the current user is the one who submitted the issue
                if result[0] != current_user:
                    return jsonify({
                        'success': False,
                        'message': 'You do not have permission to delete this issue'
                    }), 403
                
                # Delete the issue
                cur.execute("""
                    DELETE FROM issues WHERE id = %s
                """, (issue_id,))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to delete issue'
                    }), 500
                
                conn.commit()
                
                # Log the deletion
                log_submission(
                    user_id, current_user, session.get('email', ''),
                    'issue_delete',
                    f"Issue deleted: {issue_id}"
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Issue deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete issue error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while deleting the issue'
        }), 500
# Week Management API Routes
@app.route('/api/weeks', methods=['GET'])
@admin_required
def api_get_weeks():
    """API endpoint to retrieve all weeks"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, sheet_name, week_start, week_end, is_active, created_at
                    FROM weekly_sheets
                    WHERE is_active = true
                    ORDER BY week_start DESC
                """)
                weeks = cur.fetchall()
                
                formatted_weeks = []
                for week in weeks:
                    formatted_weeks.append({
                        'id': str(week['id']),
                        'week_name': week['sheet_name'],
                        'start_date': week['week_start'].strftime('%m-%d-%Y') if week['week_start'] else None,
                        'end_date': week['week_end'].strftime('%m-%d-%Y') if week['week_end'] else None,
                        'created_at': week['created_at'].strftime('%Y-%m-%d %H:%M:%S') if week['created_at'] else ''
                    })
                
                return jsonify({
                    'success': True,
                    'weeks': formatted_weeks
                })
                
    except Exception as e:
        logger.error(f"Get weeks error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve weeks'
        }), 500

@app.route('/api/weeks', methods=['POST'])
@admin_required
def api_create_week():
    """API endpoint to create a new week"""
    try:
        data = request.get_json()
        
        # Validate required fields
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        week_name = data.get('week_name')
        
        if not all([start_date_str, end_date_str, week_name]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: start_date, end_date, week_name'
            }), 400
        
        # Validate date format (MM-DD-YYYY)
        try:
            start_date = datetime.strptime(start_date_str, '%m-%d-%Y').date()
            end_date = datetime.strptime(end_date_str, '%m-%d-%Y').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format. Use MM-DD-YYYY'
            }), 400
            
        # Validate that end date is after start date
        if end_date <= start_date:
            return jsonify({
                'success': False,
                'message': 'End date must be after start date'
            }), 400
        
        # Validate date logic
        if start_date >= end_date:
            return jsonify({
                'success': False,
                'message': 'End date must be after start date'
            }), 400
            
        # Check if week already exists
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM weekly_sheets
                    WHERE sheet_name = %s OR
                    (week_start <= %s AND week_end >= %s) OR
                    (week_start <= %s AND week_end >= %s)
                """, (week_name, start_date, start_date, end_date, end_date))
                
                existing = cur.fetchone()
                if existing:
                    return jsonify({
                        'success': False,
                        'message': 'Week already exists or overlaps with existing week'
                    }), 400
                
                # Generate sheet name based on MM-DD-YYYY format for consistency
                sheet_name = f"{start_date_str}_{end_date_str}"
                
                # Insert new week
                week_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO weekly_sheets (id, sheet_name, week_start, week_end)
                    VALUES (%s, %s, %s, %s)
                """, (week_id, sheet_name, start_date, end_date))
                
                conn.commit()
                
                # Log the creation
                user_id = session.get('user_id')
                user_name = session.get('user_full_name')
                user_email = session.get('email')
                
                log_submission(
                    user_id, user_name, user_email,
                    'week_create',
                    f'New week created: {week_name} ({start_date} to {end_date})'
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Week created successfully',
                    'week_id': week_id
                })
                
    except Exception as e:
        logger.error(f"Create week error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to create week'
        }), 500

@app.route('/api/weeks/<week_id>', methods=['DELETE'])
@admin_required
def api_delete_week(week_id):
    """API endpoint to delete a week"""
    try:
        # Validate UUID format
        import uuid
        try:
            uuid.UUID(week_id)
        except ValueError:
            logger.error(f"Invalid UUID format for week_id: {week_id}")
            return jsonify({
                'success': False,
                'message': f'Invalid week ID format: {week_id}'
            }), 400
            
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First check if week exists and get info for logging
                cur.execute("""
                    SELECT sheet_name, week_start, week_end
                    FROM weekly_sheets
                    WHERE id = %s
                """, (week_id,))
                
                week_info = cur.fetchone()
                if not week_info:
                    logger.error(f"Week not found for ID: {week_id}")
                    return jsonify({
                        'success': False,
                        'message': 'Week not found'
                    }), 404
                
                # Check if week has associated submissions and metrics
                cur.execute("""
                    SELECT COUNT(*) FROM week_submissions 
                    WHERE week_name = %s OR (week_start = %s AND week_end = %s)
                """, (week_info[0], week_info[1], week_info[2]))
                
                submissions_count = cur.fetchone()[0]
                if submissions_count > 0:
                    # Check for associated metrics in any of the metrics tables
                    cur.execute("""
                        SELECT 
                            (SELECT COUNT(*) FROM first_shift_metrics fsm 
                             JOIN week_submissions ws ON fsm.week_submission_id = ws.id 
                             WHERE ws.week_name = %s) +
                            (SELECT COUNT(*) FROM second_shift_metrics ssm 
                             JOIN week_submissions ws ON ssm.week_submission_id = ws.id 
                             WHERE ws.week_name = %s) +
                            (SELECT COUNT(*) FROM both_shifts_metrics bsm 
                             JOIN week_submissions ws ON bsm.week_submission_id = ws.id 
                             WHERE ws.week_name = %s) as total_metrics
                    """, (week_info[0], week_info[0], week_info[0]))
                    
                    total_metrics = cur.fetchone()[0]
                    if total_metrics > 0:
                        return jsonify({
                            'success': False,
                            'message': f'Cannot delete week with {submissions_count} submissions and {total_metrics} associated metrics. Please remove submissions and metrics first.'
                        }), 400
                
                # Delete the week (set to inactive instead of hard delete to preserve references)
                cur.execute("""
                    UPDATE weekly_sheets
                    SET is_active = false, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (week_id,))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to delete week'
                    }), 500
                
                conn.commit()
                
                # Log the deletion
                user_id = session.get('user_id')
                user_name = session.get('user_full_name')
                user_email = session.get('email')
                
                log_submission(
                    user_id, user_name, user_email,
                    'week_delete',
                    f'Week deleted: {week_info[0]} ({week_info[1]} to {week_info[2]})'
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Week deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete week error for week_id {week_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to delete week: {str(e)}'
        }), 500

@app.route('/api/item-info')
@login_required
def get_item_info():
    """API endpoint for item information - provides basic inventory items data"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get active inventory items with basic stats
                cur.execute("""
                    SELECT
                        ii.item_code,
                        ii.item_name,
                        COUNT(it.id) as transaction_count,
                        COALESCE(SUM(CASE WHEN it.transaction_type = 'received' THEN it.calculated_quantity ELSE 0 END), 0) as total_received,
                        COALESCE(SUM(CASE WHEN it.transaction_type = 'returned' THEN it.calculated_quantity ELSE 0 END), 0) as total_returned
                    FROM inventory_items ii
                    LEFT JOIN inventory_transactions it ON ii.id = it.item_id
                    WHERE ii.is_active = true
                    GROUP BY ii.id, ii.item_code, ii.item_name
                    ORDER BY ii.item_code
                """)
                
                items = cur.fetchall()
                
                # Format the response
                formatted_items = []
                for item in items:
                    formatted_items.append({
                        'item_code': item['item_code'],
                        'item_name': item['item_name'] or item['item_code'],
                        'transaction_count': int(item['transaction_count'] or 0),
                        'total_received': float(item['total_received'] or 0),
                        'total_returned': float(item['total_returned'] or 0),
                        'net_quantity': float((item['total_received'] or 0) - (item['total_returned'] or 0))
                    })
                
                return jsonify({
                    'success': True,
                    'data': {
                        'items': formatted_items,
                        'total_items': len(formatted_items)
                    }
                })
                
    except Exception as e:
        logger.error(f"Item info error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve item information',
            'data': {
                'items': [],
                'total_items': 0
            }
        }), 500

@app.route('/api/issue-titles')
@login_required
def get_issue_titles():
    """API endpoint to get issue titles for searchable dropdown"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all issue titles sorted alphabetically
                cur.execute("""
                    SELECT DISTINCT title
                    FROM issue_title
                    ORDER BY title ASC
                """)
                
                titles = cur.fetchall()
                
                # Extract just the title strings
                title_list = [row['title'] for row in titles]
                
                return jsonify({
                    'success': True,
                    'titles': title_list,
                    'count': len(title_list)
                })
                
    except Exception as e:
        logger.error(f"Issue titles error: {e}")
        return jsonify({
            'success': False,
            'titles': [],
            'count': 0,
            'message': 'Failed to retrieve issue titles'
        }), 500

@app.route('/api/production-insights', methods=['GET'])
@login_required
def get_production_insights():
    """Generate comprehensive production insights report using real data"""
    try:
        # Get optional time range parameter (default to last 30 days for more comprehensive analysis)
        days_back = int(request.args.get('days', 30))
        start_date = datetime.now() - timedelta(days=days_back)
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # 1. Get performance metrics for comparison
                cur.execute("""
                    SELECT
                        ws.day_of_week,
                        -- First shift data
                        fs.die_cut1_oee_pct as first_dc1_oee,
                        fs.die_cut2_oee_pct as first_dc2_oee,
                        fs.die_cut1_lbs as first_dc1_lbs,
                        fs.die_cut2_lbs as first_dc2_lbs,
                        fs.die_cut1_waste_lb as first_dc1_waste,
                        fs.die_cut2_waste_lb as first_dc2_waste,
                        fs.oee_avg_pct as first_oee_avg,
                        fs.waste_avg_pct as first_waste_avg,
                        -- Second shift data
                        ss.die_cut1_oee_pct as second_dc1_oee,
                        ss.die_cut2_oee_pct as second_dc2_oee,
                        ss.die_cut1_lbs as second_dc1_lbs,
                        ss.die_cut2_lbs as second_dc2_lbs,
                        ss.die_cut1_waste_lb as second_dc1_waste,
                        ss.die_cut2_waste_lb as second_dc2_waste,
                        ss.oee_avg_pct as second_oee_avg,
                        ss.waste_avg_pct as second_waste_avg,
                        -- Combined data
                        bs.oee_avg_pct as combined_oee_avg,
                        bs.waste_avg_pct as combined_waste_avg,
                        bs.pounds_total as combined_pounds_total
                    FROM week_submissions ws
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    WHERE ws.created_at >= %s
                    ORDER BY ws.created_at DESC
                """, (start_date,))
                
                metrics_data = cur.fetchall()
                
                # 2. Get recent issues by line and shift (use report_date for more accurate filtering)
                cur.execute("""
                    SELECT
                        line,
                        shift,
                        COUNT(*) as issue_count,
                        array_agg(DISTINCT title) as issue_titles,
                        array_agg(DISTINCT issue_details) as recent_details,
                        array_agg(DISTINCT report_date::text) as report_dates
                    FROM issues
                    WHERE report_date >= %s OR created_at >= %s
                    GROUP BY line, shift
                    ORDER BY issue_count DESC
                """, (start_date, start_date))
                
                issues_data = cur.fetchall()
                
                # 3. Get inventory efficiency metrics
                cur.execute("""
                    SELECT
                        ii.item_name,
                        SUM(CASE WHEN it.transaction_type = 'received' THEN it.calculated_quantity ELSE 0 END) as total_received,
                        SUM(CASE WHEN it.transaction_type = 'returned' THEN it.calculated_quantity ELSE 0 END) as total_returned,
                        COUNT(*) as transaction_count
                    FROM inventory_transactions it
                    JOIN inventory_items ii ON it.item_id = ii.id
                    WHERE it.created_at >= %s
                    GROUP BY ii.id, ii.item_name
                    HAVING SUM(CASE WHEN it.transaction_type = 'received' THEN it.calculated_quantity ELSE 0 END) > 0
                    ORDER BY total_received DESC
                """, (start_date,))
                
                inventory_data = cur.fetchall()
                
                # 4. Calculate insights
                insights = calculate_production_insights(metrics_data, issues_data, inventory_data)
                
                return jsonify({
                    'success': True,
                    'period': f"Last {days_back} days",
                    'generated_at': datetime.now().isoformat(),
                    **insights
                })
                
    except Exception as e:
        logger.error(f"Production insights error: {e}")
        return jsonify({
            'success': False,
            'message': 'Error generating production insights'
        }), 500

def calculate_production_insights(metrics_data, issues_data, inventory_data):
    """Calculate production insights from real data"""
    
    # Initialize results
    line_performance = {
        'Die-Cut 1': {'first': [], 'second': []},
        'Die-Cut 2': {'first': [], 'second': []}
    }
    
    # Process metrics data
    for metric in metrics_data:
        if metric['first_dc1_oee'] is not None:
            line_performance['Die-Cut 1']['first'].append(float(metric['first_dc1_oee']))
        if metric['first_dc2_oee'] is not None:
            line_performance['Die-Cut 2']['first'].append(float(metric['first_dc2_oee']))
        if metric['second_dc1_oee'] is not None:
            line_performance['Die-Cut 1']['second'].append(float(metric['second_dc1_oee']))
        if metric['second_dc2_oee'] is not None:
            line_performance['Die-Cut 2']['second'].append(float(metric['second_dc2_oee']))
    
    # Calculate averages
    performance_averages = {}
    for line in line_performance:
        for shift in line_performance[line]:
            key = f"{line}-{shift}shift"
            values = line_performance[line][shift]
            performance_averages[key] = {
                'average': round(sum(values) / len(values), 1) if values else 0,
                'count': len(values)
            }
    
    # Find top performer and needs attention
    all_performances = [(k, v['average']) for k, v in performance_averages.items() if v['average'] > 0]
    all_performances.sort(key=lambda x: x[1], reverse=True)
    
    top_performer = None
    needs_attention = None
    
    if all_performances:
        # Top performer
        best = all_performances[0]
        parts = best[0].rsplit('-', 1)  # Split from right, only once
        line = parts[0] if len(parts) > 1 else best[0]
        shift = parts[1].replace('shift', ' shift').title() if len(parts) > 1 else 'Unknown'
        top_performer = {
            'line': line,
            'shift': shift,
            'value': best[1],
            'display': f"{line} - {shift}",
            'metric': f"{best[1]}% average OEE"
        }
        
        # Needs attention (lowest performer)
        worst = all_performances[-1]
        parts = worst[0].rsplit('-', 1)  # Split from right, only once
        line = parts[0] if len(parts) > 1 else worst[0]
        shift = parts[1].replace('shift', ' shift').title() if len(parts) > 1 else 'Unknown'
        needs_attention = {
            'line': line,
            'shift': shift,
            'value': worst[1],
            'display': f"{line} - {shift}",
            'metric': f"{worst[1]}% average OEE"
        }
    
    # Calculate waste reduction savings
    total_waste_lbs = 0
    total_production_lbs = 0
    
    for metric in metrics_data:
        if metric['combined_pounds_total']:
            total_production_lbs += float(metric['combined_pounds_total'])
        # Calculate waste from individual shifts
        for shift_prefix in ['first', 'second']:
            dc1_waste = metric.get(f'{shift_prefix}_dc1_waste')
            dc2_waste = metric.get(f'{shift_prefix}_dc2_waste')
            if dc1_waste:
                total_waste_lbs += float(dc1_waste)
            if dc2_waste:
                total_waste_lbs += float(dc2_waste)
    
    # Assume $2 per lb waste cost and calculate savings from waste reduction
    waste_cost_per_lb = 2.0
    potential_waste_reduction = total_waste_lbs * 0.1  # Assume 10% reduction is achievable
    cost_savings = round(potential_waste_reduction * waste_cost_per_lb)
    
    # Generate recommendations based on real issues and performance
    recommendations = generate_recommendations(issues_data, performance_averages, total_waste_lbs)
    
    # Calculate production statistics
    avg_oee = round(sum([p[1] for p in all_performances]) / len(all_performances), 1) if all_performances else 0
    total_production = round(total_production_lbs, 0)
    waste_percentage = round((total_waste_lbs / total_production_lbs * 100), 2) if total_production_lbs > 0 else 0
    
    return {
        'top_performer': top_performer or {
            'display': 'No data available',
            'metric': '0% average OEE'
        },
        'needs_attention': needs_attention or {
            'display': 'No data available',
            'metric': '0% average OEE'
        },
        'cost_savings': {
            'amount': cost_savings,
            'display': f"${cost_savings:,} this period",
            'source': 'From waste reduction'
        },
        'recommendations': recommendations,
        'summary_stats': {
            'avg_oee': avg_oee,
            'total_production': total_production,
            'waste_percentage': waste_percentage,
            'total_waste_lbs': round(total_waste_lbs, 1),
            'data_points': len(metrics_data)
        }
    }

def generate_recommendations(issues_data, performance_averages, total_waste_lbs):
    """Generate actionable recommendations based on real data"""
    recommendations = []
    
    # Debug logging
    logger.info(f"🔧 DEBUG: Issues data received: {issues_data}")
    logger.info(f"🔧 DEBUG: Performance averages: {performance_averages}")
    
    # Issue-based recommendations - Group by line only (not by shift)
    line_issues = {}
    for issue in issues_data:
        line = issue['line']
        if line not in line_issues:
            line_issues[line] = 0
        line_issues[line] += issue['issue_count']
    
    logger.info(f"🔧 DEBUG: Line issues grouped: {line_issues}")
    
    # Generate recommendations for each line
    for line, count in line_issues.items():
        if count >= 2:  # Multiple issues on same line across shifts
            priority = 'high' if count >= 3 else 'medium'
            recommendations.append({
                'priority': priority,
                'title': f"Schedule {line} maintenance",
                'description': f"Multiple issues reported ({count} incidents) affecting quality and speed",
                'action': f"Implement preventive maintenance schedule for {line}"
            })
            logger.info(f"🔧 DEBUG: Added recommendation for {line} with {count} issues")
    
    # Performance-based recommendations
    low_performers = [(k, v) for k, v in performance_averages.items() if v['average'] < 60 and v['count'] > 0]
    high_performers = [(k, v) for k, v in performance_averages.items() if v['average'] > 75 and v['count'] > 0]
    
    if low_performers and high_performers:
        low_line = low_performers[0][0].rsplit('-', 1)[0]
        high_line = high_performers[0][0].rsplit('-', 1)[0]
        recommendations.append({
            'priority': 'medium',
            'title': f"Optimize {low_line} procedures",
            'description': f"Consider cross-training from {high_line} best practices",
            'action': f"Implement knowledge transfer between shifts and lines"
        })
    
    # Waste-based recommendations
    if total_waste_lbs > 100:  # If significant waste
        recommendations.append({
            'priority': 'high',
            'title': "Continue current waste reduction efforts",
            'description': f"Current waste level of {round(total_waste_lbs, 1)} lbs shows opportunity for improvement",
            'action': "Implement similar practices across all shifts to reduce waste"
        })
    
    # Ensure at least 3 recommendations
    if len(recommendations) < 3:
        recommendations.append({
            'priority': 'low',
            'title': "Monitor production consistency",
            'description': "Continue tracking metrics to identify improvement opportunities",
            'action': "Regular review of performance data and trends"
        })
    
    return recommendations[:5]  # Limit to top 5 recommendations
# ========================================================
# PREDICTIVE MAINTENANCE API ENDPOINTS
# ========================================================

@app.route('/api/predictive-maintenance', methods=['GET'])
@login_required
def get_predictive_maintenance():
    """API endpoint for predictive maintenance data using real database information"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get equipment health data
                cur.execute("""
                    SELECT 
                        equipment_name,
                        health_score,
                        last_service_date,
                        next_service_date,
                        operating_status,
                        vibration_level,
                        temperature_celsius,
                        pressure_psi,
                        runtime_hours,
                        last_inspection_date,
                        issues_detected,
                        updated_at
                    FROM equipment_health
                    ORDER BY equipment_name
                """)
                equipment_data = cur.fetchall()
                
                # Get recent issues related to equipment for enhanced predictions
                cur.execute("""
                    SELECT 
                        line,
                        COUNT(*) as issue_count,
                        array_agg(DISTINCT title) as recent_issues,
                        MAX(report_date) as last_issue_date
                    FROM issues
                    WHERE report_date >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY line
                    ORDER BY issue_count DESC
                """)
                issues_data = cur.fetchall()
                
                # Get active work orders
                cur.execute("""
                    SELECT 
                        equipment_name,
                        work_type,
                        priority,
                        title,
                        scheduled_date,
                        status,
                        estimated_hours
                    FROM work_orders
                    WHERE status IN ('scheduled', 'in_progress')
                    ORDER BY 
                        CASE priority 
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2 
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END,
                        scheduled_date
                """)
                work_orders_data = cur.fetchall()
                
                # Process equipment data for response
                equipment_list = []
                for eq in equipment_data:
                    # Calculate days until next service
                    days_until_service = None
                    if eq['next_service_date']:
                        days_until_service = (eq['next_service_date'] - datetime.now().date()).days
                    
                    # Determine status based on health score and issues
                    equipment_status = eq['operating_status']
                    if eq['health_score'] < 70:
                        equipment_status = 'critical'
                    elif eq['health_score'] < 85:
                        equipment_status = 'warning'
                    
                    # Get related issues for this equipment
                    related_issues = []
                    for issue in issues_data:
                        if issue['line'] == eq['equipment_name']:
                            related_issues = issue['recent_issues'][:3]  # Limit to 3 most recent
                            break
                    
                    equipment_list.append({
                        'name': eq['equipment_name'],
                        'health_score': int(eq['health_score']),
                        'status': equipment_status,
                        'last_service': eq['last_service_date'].strftime('%Y-%m-%d') if eq['last_service_date'] else None,
                        'next_service': eq['next_service_date'].strftime('%Y-%m-%d') if eq['next_service_date'] else None,
                        'days_until_service': days_until_service,
                        'runtime_hours': int(eq['runtime_hours'] or 0),
                        'issues': related_issues or eq['issues_detected'] or [],
                        'vibration': float(eq['vibration_level']) if eq['vibration_level'] else None,
                        'temperature': float(eq['temperature_celsius']) if eq['temperature_celsius'] else None,
                        'pressure': float(eq['pressure_psi']) if eq['pressure_psi'] else None
                    })
                
                # Process work orders for maintenance schedule
                maintenance_schedule = []
                for wo in work_orders_data:
                    days_until = (wo['scheduled_date'] - datetime.now().date()).days if wo['scheduled_date'] else 0
                    
                    # Determine schedule display
                    if days_until == 0:
                        schedule_display = "Today"
                    elif days_until == 1:
                        schedule_display = "Tomorrow"
                    elif days_until <= 7:
                        schedule_display = "Next Week"
                    else:
                        schedule_display = wo['scheduled_date'].strftime('%m/%d/%Y') if wo['scheduled_date'] else "TBD"
                    
                    maintenance_schedule.append({
                        'equipment': wo['equipment_name'],
                        'work_type': wo['work_type'],
                        'title': wo['title'],
                        'priority': wo['priority'].title(),
                        'scheduled_date': wo['scheduled_date'].strftime('%Y-%m-%d') if wo['scheduled_date'] else None,
                        'schedule_display': schedule_display,
                        'estimated_hours': float(wo['estimated_hours']) if wo['estimated_hours'] else 1.0,
                        'status': wo['status']
                    })
                
                # Generate equipment-specific recommendations
                recommendations = generate_maintenance_recommendations(equipment_list, issues_data)
                
                return jsonify({
                    'success': True,
                    'equipment': equipment_list,
                    'maintenance_schedule': maintenance_schedule,
                    'recommendations': recommendations,
                    'generated_at': datetime.now().isoformat()
                })
                
    except Exception as e:
        logger.error(f"Predictive maintenance error: {e}")
        return jsonify({
            'success': False,
            'message': 'Error retrieving predictive maintenance data'
        }), 500

@app.route('/api/work-orders', methods=['POST'])
@login_required
def create_work_order():
    """API endpoint to create new work orders from predictive maintenance system"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['equipment_name', 'work_type', 'priority', 'title', 'scheduled_date']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Validate equipment name
        valid_equipment = ['Die-Cut 1', 'Die-Cut 2']
        if data['equipment_name'] not in valid_equipment:
            return jsonify({
                'success': False,
                'message': 'Invalid equipment name'
            }), 400
            
        # Validate work type
        valid_work_types = ['routine_inspection', 'blade_replacement', 'preventive_maintenance', 'repair', 'calibration']
        if data['work_type'] not in valid_work_types:
            return jsonify({
                'success': False,
                'message': 'Invalid work type'
            }), 400
            
        # Validate priority
        valid_priorities = ['low', 'medium', 'high', 'critical']
        if data['priority'] not in valid_priorities:
            return jsonify({
                'success': False,
                'message': 'Invalid priority level'
            }), 400
        
        # Validate and parse scheduled date
        try:
            scheduled_date = datetime.strptime(data['scheduled_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'System User')
        user_email = session.get('email', '')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Insert new work order
                cur.execute("""
                    INSERT INTO work_orders (
                        equipment_name,
                        work_type,
                        priority,
                        title,
                        description,
                        scheduled_date,
                        estimated_hours,
                        assigned_to,
                        created_by_id,
                        created_by_name,
                        status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data['equipment_name'],
                    data['work_type'],
                    data['priority'],
                    data['title'],
                    data.get('description', ''),
                    scheduled_date,
                    data.get('estimated_hours', 1.0),
                    data.get('assigned_to', 'Maintenance Team'),
                    user_id,
                    user_name,
                    'scheduled'
                ))
                
                work_order_id = cur.fetchone()[0]
                conn.commit()
                
                # Log the work order creation
                log_submission(
                    user_id, user_name, user_email,
                    'work_order_create',
                    f"Work order created: {data['equipment_name']} - {data['title']}"
                )
                
                logger.info(f"Work order created by {user_name}: {data['equipment_name']} - {data['title']}")
                
                return jsonify({
                    'success': True,
                    'message': 'Work order created successfully',
                    'work_order_id': str(work_order_id)
                })
                
    except Exception as e:
        logger.error(f"Create work order error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while creating the work order'
        }), 500

@app.route('/api/work-orders', methods=['GET'])
@login_required
def get_work_orders():
    """API endpoint to retrieve work orders with filtering support"""
    try:
        # Get filter parameters
        status_filter = request.args.get('status', '').strip()
        equipment_filter = request.args.get('equipment', '').strip()
        priority_filter = request.args.get('priority', '').strip()
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build dynamic query
                base_query = """
                    SELECT
                        wo.id,
                        wo.equipment_name,
                        wo.work_type,
                        wo.priority,
                        wo.title,
                        wo.description,
                        wo.status,
                        wo.scheduled_date,
                        wo.estimated_hours,
                        wo.actual_hours,
                        wo.assigned_to,
                        wo.created_by_name,
                        wo.created_at,
                        wo.started_at,
                        wo.completed_at,
                        wo.notes
                    FROM work_orders wo
                """
                
                where_conditions = []
                query_params = []
                
                if status_filter:
                    where_conditions.append("wo.status = %s")
                    query_params.append(status_filter)
                    
                if equipment_filter:
                    where_conditions.append("wo.equipment_name = %s")
                    query_params.append(equipment_filter)
                    
                if priority_filter:
                    where_conditions.append("wo.priority = %s")
                    query_params.append(priority_filter)
                
                # Add WHERE clause if there are conditions
                if where_conditions:
                    base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Add ORDER BY clause
                base_query += """
                    ORDER BY 
                        CASE wo.priority 
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2 
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END,
                        wo.scheduled_date,
                        wo.created_at DESC
                """
                
                cur.execute(base_query, query_params)
                work_orders = cur.fetchall()
                
                # Format the data for frontend
                formatted_work_orders = []
                for wo in work_orders:
                    formatted_work_orders.append({
                        'id': str(wo['id']),
                        'equipment_name': wo['equipment_name'],
                        'work_type': wo['work_type'].replace('_', ' ').title(),
                        'priority': wo['priority'].title(),
                        'title': wo['title'],
                        'description': wo['description'] or '',
                        'status': wo['status'].replace('_', ' ').title(),
                        'scheduled_date': wo['scheduled_date'].strftime('%Y-%m-%d') if wo['scheduled_date'] else '',
                        'estimated_hours': float(wo['estimated_hours']) if wo['estimated_hours'] else 0,
                        'actual_hours': float(wo['actual_hours']) if wo['actual_hours'] else 0,
                        'assigned_to': wo['assigned_to'] or 'Unassigned',
                        'created_by_name': wo['created_by_name'],
                        'created_at': wo['created_at'].strftime('%Y-%m-%d %H:%M:%S') if wo['created_at'] else '',
                        'notes': wo['notes'] or ''
                    })
                
                return jsonify({
                    'success': True,
                    'data': formatted_work_orders,
                    'count': len(formatted_work_orders)
                })
                
    except Exception as e:
        logger.error(f"Get work orders error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while retrieving work orders'
        }), 500

@app.route('/api/work-orders/<work_order_id>', methods=['PUT'])
@login_required
def update_work_order(work_order_id):
    """API endpoint to update work order (edit or mark as completed)"""
    try:
        data = request.get_json()
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Unknown User')
        user_email = session.get('email', '')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First check if work order exists and get current info
                cur.execute("""
                    SELECT created_by_name, status, title, equipment_name
                    FROM work_orders WHERE id = %s
                """, (work_order_id,))
                
                work_order = cur.fetchone()
                if not work_order:
                    return jsonify({
                        'success': False,
                        'message': 'Work order not found'
                    }), 404
                
                # Check if user has permission to edit (only creator can edit details, anyone can complete)
                action_type = data.get('action_type', 'edit')
                
                if action_type == 'complete':
                    # Anyone can mark as completed
                    cur.execute("""
                        UPDATE work_orders
                        SET status = 'completed',
                            completed_at = CURRENT_TIMESTAMP,
                            actual_hours = COALESCE(%s, estimated_hours),
                            notes = COALESCE(%s, notes),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        data.get('actual_hours'),
                        data.get('completion_notes'),
                        work_order_id
                    ))
                    
                    action_description = f"Work order completed: {work_order['equipment_name']} - {work_order['title']}"
                    
                elif action_type == 'edit':
                    # Only creator can edit work order details
                    if work_order['created_by_name'] != user_name:
                        return jsonify({
                            'success': False,
                            'message': 'You can only edit work orders you created'
                        }), 403
                    
                    # Validate required fields for editing
                    required_fields = ['equipment_name', 'work_type', 'priority', 'title', 'scheduled_date']
                    for field in required_fields:
                        if not data.get(field):
                            return jsonify({
                                'success': False,
                                'message': f'Missing required field: {field}'
                            }), 400
                    
                    # Validate enum values
                    valid_equipment = ['Die-Cut 1', 'Die-Cut 2']
                    valid_work_types = ['routine_inspection', 'blade_replacement', 'preventive_maintenance', 'repair', 'calibration']
                    valid_priorities = ['low', 'medium', 'high', 'critical']
                    
                    if data['equipment_name'] not in valid_equipment:
                        return jsonify({'success': False, 'message': 'Invalid equipment name'}), 400
                    if data['work_type'] not in valid_work_types:
                        return jsonify({'success': False, 'message': 'Invalid work type'}), 400
                    if data['priority'] not in valid_priorities:
                        return jsonify({'success': False, 'message': 'Invalid priority'}), 400
                    
                    # Parse and validate date
                    try:
                        scheduled_date = datetime.strptime(data['scheduled_date'], '%Y-%m-%d').date()
                    except ValueError:
                        return jsonify({'success': False, 'message': 'Invalid date format'}), 400
                    
                    # Update work order details
                    cur.execute("""
                        UPDATE work_orders
                        SET equipment_name = %s,
                            work_type = %s,
                            priority = %s,
                            title = %s,
                            description = %s,
                            scheduled_date = %s,
                            estimated_hours = %s,
                            assigned_to = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        data['equipment_name'],
                        data['work_type'],
                        data['priority'],
                        data['title'],
                        data.get('description', ''),
                        scheduled_date,
                        data.get('estimated_hours', 1.0),
                        data.get('assigned_to', 'Maintenance Team'),
                        work_order_id
                    ))
                    
                    action_description = f"Work order updated: {data['equipment_name']} - {data['title']}"
                
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Invalid action type'
                    }), 400
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to update work order'
                    }), 500
                
                conn.commit()
                
                # Log the action
                log_submission(
                    user_id, user_name, user_email,
                    'work_order_update',
                    action_description
                )
                
                return jsonify({
                    'success': True,
                    'message': f'Work order {action_type}d successfully'
                })
                
    except Exception as e:
        logger.error(f"Update work order error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while updating the work order'
        }), 500

def generate_maintenance_recommendations(equipment_list, issues_data):
    """Generate maintenance recommendations based on equipment health and issues"""
    recommendations = []
    
    for equipment in equipment_list:
        name = equipment['name']
        health_score = equipment['health_score']
        issues = equipment['issues']
        days_until_service = equipment['days_until_service']
        
        # Critical health score recommendations
        if health_score < 70:
            recommendations.append({
                'priority': 'critical',
                'equipment': name,
                'title': f"Immediate {name} maintenance required",
                'description': f"Health score of {health_score}% indicates critical issues",
                'action': "Schedule emergency maintenance within 24 hours",
                'work_type': 'repair'
            })
        
        # Service overdue recommendations
        if days_until_service is not None and days_until_service < 0:
            recommendations.append({
                'priority': 'high',
                'equipment': name,
                'title': f"{name} service overdue",
                'description': f"Service was due {abs(days_until_service)} days ago",
                'action': "Schedule preventive maintenance immediately",
                'work_type': 'preventive_maintenance'
            })
        
        # Issue-based recommendations
        if issues and len(issues) >= 2:
            recommendations.append({
                'priority': 'medium',
                'equipment': name,
                'title': f"Address recurring {name} issues",
                'description': f"Multiple issues reported: {', '.join(issues[:2])}",
                'action': "Perform root cause analysis and corrective action",
                'work_type': 'routine_inspection'
            })
        
        # Upcoming service recommendations
        if days_until_service is not None and 0 <= days_until_service <= 7:
            recommendations.append({
                'priority': 'low',
                'equipment': name,
                'title': f"{name} service due soon",
                'description': f"Scheduled service in {days_until_service} days",
                'action': "Prepare for upcoming maintenance",
                'work_type': 'preventive_maintenance'
            })
    
    # Sort by priority and limit to top 5
    priority_order = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
    recommendations.sort(key=lambda x: priority_order.get(x['priority'], 5))
    
    return recommendations[:5]

@app.route('/api/report-dashboard-metrics', methods=['GET'])
@login_required
def get_report_dashboard_metrics():
    """API endpoint for report page dashboard metrics cards - provides real data from both_shifts table"""
    try:
        # Get filter parameters (same as other report endpoints)
        week_filter = request.args.get('week', '').strip()
        day_filter = request.args.get('day', '').strip()
        
        logger.info(f"📊 Report dashboard metrics called with filters: week={week_filter}, day={day_filter}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build filtered query to get recent metrics data
                base_query = """
                    SELECT
                        bs.oee_avg_pct,
                        bs.waste_avg_pct,
                        bs.pounds_total,
                        bs.die_cut1_oee_pct,
                        bs.die_cut2_oee_pct,
                        bs.die_cut1_waste_pct,
                        bs.die_cut2_waste_pct,
                        bs.die_cut1_lbs,
                        bs.die_cut2_lbs,
                        ws.day_of_week,
                        ws.week_name,
                        bs.created_at
                    FROM both_shifts_metrics bs
                    JOIN week_submissions ws ON bs.week_submission_id = ws.id
                """
                
                # Build WHERE clause based on filters
                where_conditions = []
                query_params = []
                
                if week_filter and week_filter.lower() not in ['latest', 'all', '']:
                    where_conditions.append("ws.week_name = %s")
                    query_params.append(week_filter)
                    logger.info(f"📊 Added week filter: {week_filter}")
                
                if day_filter and day_filter.lower() not in ['all', '']:
                    where_conditions.append("ws.day_of_week = %s")
                    query_params.append(day_filter)
                    logger.info(f"📊 Added day filter: {day_filter}")
                
                # Add WHERE clause if there are conditions
                if where_conditions:
                    base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Get most recent data first
                base_query += " ORDER BY bs.created_at DESC LIMIT 20"
                
                logger.info(f"📊 Executing dashboard metrics query with {len(query_params)} parameters")
                cur.execute(base_query, query_params)
                
                records = cur.fetchall()
                logger.info(f"📊 Retrieved {len(records)} dashboard metric records")
                
                if not records:
                    # Return default values if no data
                    logger.warning("📊 No data found for dashboard metrics, returning defaults")
                    return jsonify({
                        'success': True,
                        'data': {
                            'oeeCurrentValue': 0.0,
                            'oeeStatus': 'Below Target',
                            'oeeChange': '+0.0%',
                            'oeeVsTarget': '0% vs target (70%)',
                            'wasteCurrentValue': 0.0,
                            'wasteStatus': 'Above Target',
                            'wasteChange': '+0.0%',
                            'wasteVsTarget': '0% vs target (3.75%)',
                            'productionCurrentValue': 0,
                            'productionStatus': 'Normal',
                            'productionChange': '+0 lbs',
                            'productionDailyOutput': '0 lbs daily output',
                            'efficiencyCurrentValue': 0.0,
                            'efficiencyStatus': 'Fair',
                            'efficiencyChange': 'Stable',
                            'efficiencyPerformanceIndex': '0 performance index'
                        }
                    })
                
                # Calculate current metrics from the data
                oee_values = [float(r['oee_avg_pct']) for r in records if r['oee_avg_pct'] is not None]
                waste_values = [float(r['waste_avg_pct']) for r in records if r['waste_avg_pct'] is not None]
                production_values = [float(r['pounds_total']) for r in records if r['pounds_total'] is not None]
                
                # Calculate averages and totals
                current_oee = round(sum(oee_values) / len(oee_values), 1) if oee_values else 0.0
                current_waste = round(sum(waste_values) / len(waste_values), 2) if waste_values else 0.0
                total_production = round(sum(production_values), 0) if production_values else 0
                
                # Calculate daily average production
                unique_days = len(set(r['day_of_week'] for r in records if r['day_of_week']))
                daily_output = round(total_production / max(unique_days, 1), 0) if total_production > 0 else 0
                
                # Calculate efficiency score (0-10 scale)
                oee_score = (current_oee / 100) * 4 if current_oee > 0 else 0  # Max 4 points
                waste_score = max(0, (1 - current_waste / 3.75)) * 3 if current_waste > 0 else 3  # Max 3 points (lower waste is better)
                production_score = min((total_production / 15000), 1) * 3 if total_production > 0 else 0  # Max 3 points
                efficiency_score = round(min(10, oee_score + waste_score + production_score), 1)
                
                # Calculate status indicators
                oee_status = 'Target Met' if current_oee >= 70 else 'Below Target'
                waste_status = 'Below Target' if current_waste <= 3.75 else 'Above Target'
                production_status = 'Above Target' if total_production >= 12000 else 'Normal' if total_production >= 8000 else 'Below Target'
                efficiency_status = 'Excellent' if efficiency_score >= 8 else 'Good' if efficiency_score >= 6 else 'Fair'
                
                # Calculate change indicators (simplified - using difference from target)
                oee_change = f"+{current_oee - 70:.1f}%" if current_oee >= 70 else f"{current_oee - 70:.1f}%"
                waste_change = f"{current_waste - 3.75:+.2f}%" if current_waste != 3.75 else "0.0%"
                production_change = f"+{total_production - 12000:,.0f} lbs" if total_production >= 12000 else f"{total_production - 12000:,.0f} lbs"
                efficiency_change = 'Excellent' if efficiency_score >= 8 else 'Good' if efficiency_score >= 6 else 'Stable'
                
                # Performance index (simple calculation based on all metrics)
                performance_index = round((current_oee * 0.4) + ((100 - current_waste * 10) * 0.3) + ((total_production / 150) * 0.3), 1)
                performance_index = min(100, max(0, performance_index))  # Clamp between 0-100
                
                dashboard_metrics = {
                    'success': True,
                    'data': {
                        # OEE Card Data
                        'oeeCurrentValue': current_oee,
                        'oeeStatus': oee_status,
                        'oeeChange': oee_change,
                        'oeeVsTarget': f'{current_oee:.1f}% vs target (70%)',
                        
                        # Waste Card Data
                        'wasteCurrentValue': current_waste,
                        'wasteStatus': waste_status,
                        'wasteChange': waste_change,
                        'wasteVsTarget': f'{current_waste:.2f}% vs target (3.75%)',
                        
                        # Production Card Data
                        'productionCurrentValue': int(total_production),
                        'productionStatus': production_status,
                        'productionChange': production_change,
                        'productionDailyOutput': f'{daily_output:,.0f} lbs daily output',
                        
                        # Efficiency Card Data
                        'efficiencyCurrentValue': efficiency_score,
                        'efficiencyStatus': efficiency_status,
                        'efficiencyChange': efficiency_change,
                        'efficiencyPerformanceIndex': f'{performance_index:.1f} performance index',
                        
                        # Additional metadata
                        'recordCount': len(records),
                        'dataSource': 'both_shifts_metrics',
                        'calculatedAt': datetime.now().isoformat()
                    }
                }
                
                logger.info(f"📊 Dashboard metrics calculated: OEE={current_oee}%, Waste={current_waste}%, Production={total_production} lbs, Efficiency={efficiency_score}/10")
                return jsonify(dashboard_metrics)
                
    except Exception as e:
        logger.error(f"📊 ERROR: Report dashboard metrics error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to calculate dashboard metrics',
            'data': {
                'oeeCurrentValue': 0.0,
                'wasteCurrentValue': 0.0,
                'productionCurrentValue': 0,
                'efficiencyCurrentValue': 0.0
            }
        }), 500

@app.route('/api/ai-insights', methods=['GET'])
@login_required
def get_ai_insights():
    """API endpoint for AI-Powered Data Analysis & Insights using real database data"""
    try:
        # Get filter parameters (same as other report endpoints)
        week_filter = request.args.get('week', '').strip()
        day_filter = request.args.get('day', '').strip()
        
        logger.info(f"🤖 AI Insights API called with filters: week={week_filter}, day={day_filter}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build filtered query to get recent performance data for analysis
                base_query = """
                    SELECT
                        bs.oee_avg_pct,
                        bs.waste_avg_pct,
                        bs.pounds_total,
                        bs.die_cut1_oee_pct,
                        bs.die_cut2_oee_pct,
                        bs.die_cut1_waste_pct,
                        bs.die_cut2_waste_pct,
                        ws.day_of_week,
                        ws.week_name,
                        bs.created_at
                    FROM both_shifts_metrics bs
                    JOIN week_submissions ws ON bs.week_submission_id = ws.id
                """
                
                # Build WHERE clause based on filters
                where_conditions = []
                query_params = []
                
                if week_filter and week_filter.lower() not in ['latest', 'all', '']:
                    where_conditions.append("ws.week_name = %s")
                    query_params.append(week_filter)
                    logger.info(f"🤖 Added week filter: {week_filter}")
                
                if day_filter and day_filter.lower() not in ['all', '']:
                    where_conditions.append("ws.day_of_week = %s")
                    query_params.append(day_filter)
                    logger.info(f"🤖 Added day filter: {day_filter}")
                
                # Add WHERE clause if there are conditions
                if where_conditions:
                    base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Order by most recent first and limit results
                base_query += " ORDER BY bs.created_at DESC LIMIT 30"
                
                logger.info(f"🤖 Executing AI insights query with {len(query_params)} parameters")
                cur.execute(base_query, query_params)
                
                metrics_data = cur.fetchall()
                logger.info(f"🤖 Retrieved {len(metrics_data)} records for AI analysis")
                
                # Get recent issues for context
                cur.execute("""
                    SELECT
                        line, shift, title, issue_details, report_date,
                        COUNT(*) OVER (PARTITION BY line) as line_issue_count
                    FROM issues
                    WHERE report_date >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY report_date DESC
                    LIMIT 10
                """)
                issues_data = cur.fetchall()
                
                # Generate AI insights based on real data
                insights_result = generate_ai_insights_from_data(metrics_data, issues_data)
                
                return jsonify({
                    'success': True,
                    'data': insights_result,
                    'generated_at': datetime.now().isoformat(),
                    'data_points': len(metrics_data)
                })
                
    except Exception as e:
        logger.error(f"🤖 ERROR: AI insights error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate AI insights',
            'data': {
                'key_insights': [],
                'recommendations': [],
                'action_items': []
            }
        }), 500

def generate_ai_insights_from_data(metrics_data, issues_data):
    """
    Operations Analytics Assistant for Bakery Manufacturing Dashboard
    
    Analyzes real performance data to provide:
    1. Key Performance Insights (2-4 bullet points on current business state)
    2. Actionable Recommendations (2-3 specific improvement steps)
    3. Priority Action Items (2 tasks with priority levels and deadlines)
    
    Uses ONLY database data - never fabricates numbers.
    """
    
    if not metrics_data:
        return {
            'key_insights': [{
                'type': 'info',
                'title': 'Insufficient Data for Analysis',
                'description': 'No performance records available with current filters to analyze patterns or trends',
                'icon': 'info'
            }],
            'recommendations': [{
                'type': 'info',
                'title': 'Expand Data Collection',
                'description': 'Cannot provide specific recommendations without performance data',
                'action': 'Adjust filters or ensure data submission is current'
            }],
            'action_items': [{
                'id': 'data_verification',
                'title': 'Verify Data Availability',
                'description': 'Check if performance data exists for selected time period',
                'priority': 'Medium',
                'due': 'Today'
            }]
        }
    
    # Calculate performance statistics
    oee_values = [float(r['oee_avg_pct']) for r in metrics_data if r['oee_avg_pct'] is not None]
    waste_values = [float(r['waste_avg_pct']) for r in metrics_data if r['waste_avg_pct'] is not None]
    production_values = [float(r['pounds_total']) for r in metrics_data if r['pounds_total'] is not None]
    
    avg_oee = sum(oee_values) / len(oee_values) if oee_values else 0
    avg_waste = sum(waste_values) / len(waste_values) if waste_values else 0
    total_production = sum(production_values) if production_values else 0
    
    # Analyze day-of-week patterns
    day_performance = {}
    for record in metrics_data:
        day = record['day_of_week']
        if day and record['oee_avg_pct']:
            if day not in day_performance:
                day_performance[day] = []
            day_performance[day].append(float(record['oee_avg_pct']))
    
    # Find best and worst performing days
    day_averages = {day: sum(values) / len(values) for day, values in day_performance.items() if values}
    best_day = max(day_averages.keys(), key=lambda x: day_averages[x]) if day_averages else None
    worst_day = min(day_averages.keys(), key=lambda x: day_averages[x]) if day_averages else None
    
    # Analyze Die Cut performance
    dc1_oee = [float(r['die_cut1_oee_pct']) for r in metrics_data if r['die_cut1_oee_pct'] is not None]
    dc2_oee = [float(r['die_cut2_oee_pct']) for r in metrics_data if r['die_cut2_oee_pct'] is not None]
    
    avg_dc1_oee = sum(dc1_oee) / len(dc1_oee) if dc1_oee else 0
    avg_dc2_oee = sum(dc2_oee) / len(dc2_oee) if dc2_oee else 0
    
    # Generate key insights
    key_insights = []
    
    # OEE Performance Insight
    if avg_oee >= 70:
        key_insights.append({
            'type': 'success',
            'title': 'OEE Performance Strong',
            'description': f'Average OEE of {avg_oee:.1f}% exceeds 70% target consistently',
            'icon': 'trending-up'
        })
    else:
        key_insights.append({
            'type': 'warning',
            'title': 'OEE Below Target',
            'description': f'Average OEE of {avg_oee:.1f}% needs improvement to reach 70% target',
            'icon': 'alert-triangle'
        })
    
    # Waste Performance Insight
    if avg_waste <= 3.75:
        key_insights.append({
            'type': 'success',
            'title': 'Waste Control Excellent',
            'description': f'Material waste at {avg_waste:.2f}% is well below 3.75% target',
            'icon': 'check-circle'
        })
    else:
        key_insights.append({
            'type': 'warning',
            'title': 'Waste Above Target',
            'description': f'Material waste at {avg_waste:.2f}% exceeds 3.75% target',
            'icon': 'alert-circle'
        })
    
    # Day Pattern Insight
    if best_day and worst_day and len(day_averages) >= 3:
        best_avg = day_averages[best_day]
        worst_avg = day_averages[worst_day]
        difference = best_avg - worst_avg
        
        if difference > 5:  # Significant difference
            key_insights.append({
                'type': 'info',
                'title': f'{worst_day} Performance Dip',
                'description': f'{best_day} ({best_avg:.1f}%) outperforms {worst_day} ({worst_avg:.1f}%) by {difference:.1f}%',
                'icon': 'calendar'
            })
    
    # Die Cut Comparison Insight
    if avg_dc1_oee > 0 and avg_dc2_oee > 0:
        dc_diff = abs(avg_dc1_oee - avg_dc2_oee)
        if dc_diff > 5:
            better_dc = "Die Cut 1" if avg_dc1_oee > avg_dc2_oee else "Die Cut 2"
            worse_dc = "Die Cut 2" if avg_dc1_oee > avg_dc2_oee else "Die Cut 1"
            key_insights.append({
                'type': 'info',
                'title': 'Die Cut Performance Gap',
                'description': f'{better_dc} outperforming {worse_dc} by {dc_diff:.1f}% on average',
                'icon': 'bar-chart'
            })
    
    # Generate recommendations
    recommendations = []
    
    # OEE-based recommendations
    if avg_oee < 70:
        if avg_dc1_oee < avg_dc2_oee and avg_dc1_oee < 70:
            recommendations.append({
                'type': 'high',
                'title': 'Focus on Die Cut 1 Improvement',
                'description': f'Die Cut 1 averaging {avg_dc1_oee:.1f}% OEE needs attention',
                'action': 'Schedule maintenance inspection and operator training for Die Cut 1'
            })
        elif avg_dc2_oee < avg_dc1_oee and avg_dc2_oee < 70:
            recommendations.append({
                'type': 'high',
                'title': 'Focus on Die Cut 2 Improvement',
                'description': f'Die Cut 2 averaging {avg_dc2_oee:.1f}% OEE needs attention',
                'action': 'Schedule maintenance inspection and operator training for Die Cut 2'
            })
    
    # Waste-based recommendations
    if avg_waste > 3.75:
        recommendations.append({
            'type': 'medium',
            'title': 'Implement Waste Reduction Program',
            'description': f'Current waste of {avg_waste:.2f}% exceeds target',
            'action': 'Review material handling procedures and operator techniques'
        })
    
    # Day-pattern recommendations
    if worst_day and day_averages.get(worst_day, 0) < 65:
        recommendations.append({
            'type': 'medium',
            'title': f'Address {worst_day} Performance',
            'description': f'{worst_day} consistently shows lower performance',
            'action': f'Review {worst_day} shift procedures and staffing levels'
        })
    
    # Issue-based recommendations
    line_issues = {}
    for issue in issues_data:
        line = issue['line']
        if line:
            if line not in line_issues:
                line_issues[line] = 0
            line_issues[line] += 1
    
    for line, count in line_issues.items():
        if count >= 2:
            recommendations.append({
                'type': 'high',
                'title': f'Address {line} Reliability',
                'description': f'{count} issues reported for {line} recently',
                'action': f'Schedule comprehensive maintenance review for {line}'
            })
    
    # Add at least one recommendation if none generated
    if not recommendations:
        if avg_oee > 70 and avg_waste < 3.75:
            recommendations.append({
                'type': 'low',
                'title': 'Maintain Current Performance',
                'description': 'All metrics are meeting targets consistently',
                'action': 'Continue current procedures and monitor for any changes'
            })
        else:
            recommendations.append({
                'type': 'medium',
                'title': 'Focus on Continuous Improvement',
                'description': 'Identify opportunities for operational efficiency gains',
                'action': 'Conduct quarterly performance review and benchmarking'
            })
    
    # Generate action items
    action_items = []
    
    # High priority action based on worst performing metric
    if avg_oee < 60:
        action_items.append({
            'id': 'oee_critical',
            'title': 'Critical OEE Improvement Plan',
            'description': f'Develop action plan to improve OEE from {avg_oee:.1f}% to target',
            'priority': 'high',
            'due': 'This Week'
        })
    elif avg_oee < 70:
        action_items.append({
            'id': 'oee_improvement',
            'title': 'OEE Enhancement Initiative',
            'description': f'Implement improvements to reach 70% OEE target from current {avg_oee:.1f}%',
            'priority': 'medium',
            'due': 'Next Week'
        })
    
    # Waste action item
    if avg_waste > 4.5:
        action_items.append({
            'id': 'waste_critical',
            'title': 'Emergency Waste Reduction',
            'description': f'Immediate action needed - waste at {avg_waste:.2f}% vs 3.75% target',
            'priority': 'high',
            'due': 'Today'
        })
    elif avg_waste > 3.75:
        action_items.append({
            'id': 'waste_improvement',
            'title': 'Waste Reduction Initiative',
            'description': f'Reduce waste from {avg_waste:.2f}% to target 3.75%',
            'priority': 'medium',
            'due': 'This Week'
        })
    
    # Equipment-specific action items
    if avg_dc1_oee > 0 and avg_dc2_oee > 0:
        if avg_dc1_oee < 65:
            action_items.append({
                'id': 'dc1_maintenance',
                'title': 'Die Cut 1 Performance Review',
                'description': f'Investigate Die Cut 1 performance ({avg_dc1_oee:.1f}% OEE)',
                'priority': 'medium' if avg_dc1_oee > 60 else 'high',
                'due': 'This Week'
            })
        elif avg_dc2_oee < 65:
            action_items.append({
                'id': 'dc2_maintenance',
                'title': 'Die Cut 2 Performance Review',
                'description': f'Investigate Die Cut 2 performance ({avg_dc2_oee:.1f}% OEE)',
                'priority': 'medium' if avg_dc2_oee > 60 else 'high',
                'due': 'This Week'
            })
    
    # Add default action item if none generated
    if not action_items:
        if avg_oee > 70 and avg_waste < 3.75:
            action_items.append({
                'id': 'maintain_performance',
                'title': 'Document Best Practices',
                'description': 'Record current procedures that are achieving target performance',
                'priority': 'low',
                'due': 'Next Week'
            })
        else:
            action_items.append({
                'id': 'performance_review',
                'title': 'Quarterly Performance Review',
                'description': 'Analyze trends and identify improvement opportunities',
                'priority': 'medium',
                'due': 'End of Month'
            })
    
    return {
        'key_insights': key_insights[:4],  # Limit to top 4 insights
        'recommendations': recommendations[:3],  # Limit to top 3 recommendations
        'action_items': action_items[:3],  # Limit to top 3 action items
        'statistics': {
            'avg_oee': avg_oee,
            'avg_waste': avg_waste,
            'total_production': total_production,
            'data_points': len(metrics_data),
            'best_day': best_day,
            'worst_day': worst_day
        }
    }

@app.route('/api/check-existing-record', methods=['GET'])
@login_required
def check_existing_record():
    """API endpoint to check if a record already exists for a specific day and week"""
    try:
        week_name = request.args.get('week', '').strip()
        day_of_week = request.args.get('day', '').strip()
        
        if not week_name or not day_of_week:
            return jsonify({
                'success': False,
                'message': 'Week and day parameters are required',
                'exists': False
            }), 400
        
        # Validate day
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        if day_of_week not in valid_days:
            return jsonify({
                'success': False,
                'message': 'Invalid day provided',
                'exists': False
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if a record already exists
                cur.execute("""
                    SELECT id FROM week_submissions
                    WHERE week_name = %s AND day_of_week = %s
                """, (week_name, day_of_week))
                
                existing_record = cur.fetchone()
                record_exists = existing_record is not None
                
                logger.info(f"Record existence check: week={week_name}, day={day_of_week}, exists={record_exists}")
                
                return jsonify({
                    'success': True,
                    'exists': record_exists,
                    'message': f"Record {'exists' if record_exists else 'does not exist'} for {day_of_week} in week {week_name}"
                })
                
    except Exception as e:
        logger.error(f"Check existing record error: {e}")
        return jsonify({
            'success': False,
            'message': 'Error checking for existing records',
            'exists': False
        }), 500

@app.route('/api/recent-submissions', methods=['GET'])
@login_required
def get_recent_submissions():
    """API endpoint to get recent submissions for the current user"""
    try:
        user_id = session.get('user_id')
        user_name = session.get('user_full_name')
        
        logger.info(f"Recent submissions request - user_id: {user_id}, user_name: '{user_name}'")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First, let's see all submissions to debug
                cur.execute("""
                    SELECT submitted_by, COUNT(*) as count
                    FROM week_submissions
                    GROUP BY submitted_by
                """)
                all_submitters = cur.fetchall()
                logger.info(f"All submitters in database: {[dict(s) for s in all_submitters]}")
                
                # For now, show all submissions for testing (since user mismatch between "Riak Chot" and "Gerald")
                first_name = user_name.split()[0] if user_name else ''
                logger.info(f"Searching for submissions by: exact='{user_name}', first_name='{first_name}'")
                
                cur.execute("""
                    SELECT
                        ws.day_of_week,
                        ws.week_name,
                        ws.created_at,
                        ws.submitted_by,
                        CASE
                            WHEN bs.id IS NOT NULL THEN 'Completed'
                            ELSE 'Submitted'
                        END as status
                    FROM week_submissions ws
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    ORDER BY ws.created_at DESC
                    LIMIT 3
                """)
                
                submissions = cur.fetchall()
                logger.info(f"Query result: Found {len(submissions)} recent submissions")
                for sub in submissions:
                    logger.info(f"  - {sub['submitted_by']}: {sub['week_name']} {sub['day_of_week']}")
                
                # Format the submissions for frontend
                formatted_submissions = []
                for submission in submissions:
                    # Calculate time ago
                    time_diff = datetime.now() - submission['created_at'].replace(tzinfo=None)
                    
                    if time_diff.total_seconds() < 3600:  # Less than 1 hour
                        minutes = int(time_diff.total_seconds() / 60)
                        time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago" if minutes > 0 else "Just now"
                    elif time_diff.total_seconds() < 86400:  # Less than 1 day
                        hours = int(time_diff.total_seconds() / 3600)
                        time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
                    else:  # More than 1 day
                        days = int(time_diff.total_seconds() / 86400)
                        time_ago = f"{days} day{'s' if days != 1 else ''} ago"
                    
                    formatted_submissions.append({
                        'title': f"{submission['day_of_week']} Metrics",
                        'time_ago': time_ago,
                        'status': submission['status'],
                        'day': submission['day_of_week'],
                        'week': submission['week_name']
                    })
                
                return jsonify({
                    'success': True,
                    'submissions': formatted_submissions
                })
                
    except Exception as e:
        logger.error(f"Recent submissions error: {e}")
        return jsonify({
            'success': False,
            'submissions': []
        }), 500

@app.route('/api/all-submissions', methods=['GET'])
@login_required
def get_all_submissions():
    """API endpoint to get all detailed submissions for the current user"""
    try:
        user_id = session.get('user_id')
        user_name = session.get('user_full_name')
        
        logger.info(f"All submissions request - user_id: {user_id}, user_name: '{user_name}'")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # For now, show all submissions for testing (since user mismatch between "Riak Chot" and "Gerald")
                first_name = user_name.split()[0] if user_name else ''
                logger.info(f"Searching for detailed submissions by: exact='{user_name}', first_name='{first_name}'")
                logger.info(f"Note: Showing ALL submissions for testing due to user mismatch")
                
                cur.execute("""
                    SELECT
                        ws.id,
                        ws.day_of_week,
                        ws.week_name,
                        ws.created_at,
                        ws.submitted_by,
                        -- First shift metrics
                        fs.die_cut1_oee_pct as first_die_cut1_oee,
                        fs.die_cut2_oee_pct as first_die_cut2_oee,
                        fs.die_cut1_lbs as first_die_cut1_lbs,
                        fs.die_cut2_lbs as first_die_cut2_lbs,
                        fs.die_cut1_waste_lb as first_die_cut1_waste,
                        fs.die_cut2_waste_lb as first_die_cut2_waste,
                        fs.oee_avg_pct as first_shift_oee_avg,
                        fs.waste_avg_pct as first_shift_waste_avg,
                        -- Second shift metrics
                        ss.die_cut1_oee_pct as second_die_cut1_oee,
                        ss.die_cut2_oee_pct as second_die_cut2_oee,
                        ss.die_cut1_lbs as second_die_cut1_lbs,
                        ss.die_cut2_lbs as second_die_cut2_lbs,
                        ss.die_cut1_waste_lb as second_die_cut1_waste,
                        ss.die_cut2_waste_lb as second_die_cut2_waste,
                        ss.oee_avg_pct as second_shift_oee_avg,
                        ss.waste_avg_pct as second_shift_waste_avg,
                        -- Combined metrics
                        bs.oee_avg_pct as total_oee_avg,
                        bs.waste_avg_pct as total_waste_avg,
                        bs.pounds_total as total_production,
                        CASE
                            WHEN bs.id IS NOT NULL THEN 'Completed'
                            ELSE 'Submitted'
                        END as status
                    FROM week_submissions ws
                    LEFT JOIN first_shift_metrics fs ON ws.id = fs.week_submission_id
                    LEFT JOIN second_shift_metrics ss ON ws.id = ss.week_submission_id
                    LEFT JOIN both_shifts_metrics bs ON ws.id = bs.week_submission_id
                    ORDER BY ws.created_at DESC
                    LIMIT 20
                """)
                
                submissions = cur.fetchall()
                logger.info(f"Query result: Found {len(submissions)} detailed submissions")
                for sub in submissions:
                    logger.info(f"  - {sub['submitted_by']}: {sub['week_name']} {sub['day_of_week']}")
                
                # Format the detailed submissions for frontend
                formatted_submissions = []
                for submission in submissions:
                    # Format the submission timestamp
                    created_at = submission['created_at']
                    formatted_date = created_at.strftime('%B %d, %Y at %I:%M %p') if created_at else 'Unknown'
                    
                    formatted_submission = {
                        'id': str(submission['id']),
                        'week_name': submission['week_name'],
                        'day_of_week': submission['day_of_week'],
                        'submitted_by': submission['submitted_by'],
                        'submitted_at': formatted_date,
                        'status': submission['status'],
                        
                        # First shift metrics
                        'first_shift': {
                            'die_cut1_oee': f"{submission['first_die_cut1_oee']:.1f}%" if submission['first_die_cut1_oee'] else "N/A",
                            'die_cut2_oee': f"{submission['first_die_cut2_oee']:.1f}%" if submission['first_die_cut2_oee'] else "N/A",
                            'die_cut1_lbs': f"{submission['first_die_cut1_lbs']:.1f} lbs" if submission['first_die_cut1_lbs'] else "N/A",
                            'die_cut2_lbs': f"{submission['first_die_cut2_lbs']:.1f} lbs" if submission['first_die_cut2_lbs'] else "N/A",
                            'die_cut1_waste': f"{submission['first_die_cut1_waste']:.1f} lbs" if submission['first_die_cut1_waste'] else "N/A",
                            'die_cut2_waste': f"{submission['first_die_cut2_waste']:.1f} lbs" if submission['first_die_cut2_waste'] else "N/A",
                            'avg_oee': f"{submission['first_shift_oee_avg']:.1f}%" if submission['first_shift_oee_avg'] else "N/A",
                            'avg_waste': f"{submission['first_shift_waste_avg']:.2f}%" if submission['first_shift_waste_avg'] else "N/A"
                        },
                        
                        # Second shift metrics
                        'second_shift': {
                            'die_cut1_oee': f"{submission['second_die_cut1_oee']:.1f}%" if submission['second_die_cut1_oee'] else "N/A",
                            'die_cut2_oee': f"{submission['second_die_cut2_oee']:.1f}%" if submission['second_die_cut2_oee'] else "N/A",
                            'die_cut1_lbs': f"{submission['second_die_cut1_lbs']:.1f} lbs" if submission['second_die_cut1_lbs'] else "N/A",
                            'die_cut2_lbs': f"{submission['second_die_cut2_lbs']:.1f} lbs" if submission['second_die_cut2_lbs'] else "N/A",
                            'die_cut1_waste': f"{submission['second_die_cut1_waste']:.1f} lbs" if submission['second_die_cut1_waste'] else "N/A",
                            'die_cut2_waste': f"{submission['second_die_cut2_waste']:.1f} lbs" if submission['second_die_cut2_waste'] else "N/A",
                            'avg_oee': f"{submission['second_shift_oee_avg']:.1f}%" if submission['second_shift_oee_avg'] else "N/A",
                            'avg_waste': f"{submission['second_shift_waste_avg']:.2f}%" if submission['second_shift_waste_avg'] else "N/A"
                        },
                        
                        # Combined totals
                        'totals': {
                            'avg_oee': f"{submission['total_oee_avg']:.1f}%" if submission['total_oee_avg'] else "N/A",
                            'avg_waste': f"{submission['total_waste_avg']:.2f}%" if submission['total_waste_avg'] else "N/A",
                            'total_production': f"{submission['total_production']:.1f} lbs" if submission['total_production'] else "N/A"
                        }
                    }
                    
                    formatted_submissions.append(formatted_submission)
                
                return jsonify({
                    'success': True,
                    'submissions': formatted_submissions,
                    'total_count': len(formatted_submissions)
                })
                
    except Exception as e:
        logger.error(f"All submissions error: {e}")
        return jsonify({
            'success': False,
            'submissions': [],
            'total_count': 0
        }), 500

@app.route('/api/debug-submissions', methods=['GET'])
@login_required
def debug_submissions():
    """Debug endpoint to see all submissions in the database"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, week_name, day_of_week, submitted_by, created_at
                    FROM week_submissions
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                all_submissions = cur.fetchall()
                
                return jsonify({
                    'success': True,
                    'current_user': session.get('user_full_name'),
                    'current_user_id': session.get('user_id'),
                    'all_submissions': [dict(s) for s in all_submissions]
                })
    except Exception as e:
        logger.error(f"Debug submissions error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    


@app.route('/api/google-sheets', methods=['GET'])
@admin_or_supervisor_required
def get_google_sheets():
    """API endpoint to get list of sheet tabs from BAKERY METRICS spreadsheet matching the pattern mm-dd-yyyy_mm-dd-yyyy"""
    logger.info("=== Google Sheets API endpoint called ===")
    logger.info(f"User in session: {session.get('user_id', 'Not logged in')}")
    logger.info(f"Session data: {dict(session)}")
    
    try:
        # Import Google API components
        try:
            from googleapiclient.discovery import build
            from google.oauth2.service_account import Credentials
            logger.info("Google API libraries imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import Google API libraries: {e}")
            return jsonify({
                'success': False,
                'message': 'Google API libraries not available. Please ensure google-api-python-client and google-auth are installed.'
            }), 500
        
        # Check for credentials file
        creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
        logger.info(f"Looking for credentials at: {creds_path}")
        
        if not os.path.exists(creds_path):
            logger.error(f"Credentials file not found at: {creds_path}")
            return jsonify({
                'success': False,
                'message': f'Google credentials file not found at {creds_path}'
            }), 500
        
        # Authenticate with Google APIs using newer auth library
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            drive_service = build('drive', 'v3', credentials=creds)
            sheets_service = build('sheets', 'v4', credentials=creds)
            logger.info("Google APIs authenticated successfully")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google APIs: {e}")
            return jsonify({
                'success': False,
                'message': f'Google API authentication failed: {str(e)}'
            }), 500
        
        # Find the BAKERY METRICS spreadsheet
        try:
            query = "name='BAKERY METRICS_2024-2025' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            logger.info(f"Searching for BAKERY METRICS spreadsheet")
            results = drive_service.files().list(q=query, fields="files(id,name)").execute()
            files = results.get('files', [])
            
            if not files:
                logger.error("BAKERY METRICS_2024-2025 spreadsheet not found")
                return jsonify({
                    'success': False,
                    'message': 'BAKERY METRICS_2024-2025 spreadsheet not found'
                }), 404
            
            spreadsheet_id = files[0]['id']
            logger.info(f"Found BAKERY METRICS spreadsheet: {spreadsheet_id}")
            
        except Exception as e:
            logger.error(f"Failed to find BAKERY METRICS spreadsheet: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to find BAKERY METRICS spreadsheet: {str(e)}'
            }), 500
        
        # Get all sheet tabs from the spreadsheet
        try:
            spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            logger.info(f"Found {len(sheets)} sheet tabs")
        except Exception as e:
            logger.error(f"Failed to get sheet tabs: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to get sheet tabs: {str(e)}'
            }), 500
        
        # Filter sheet tabs that match the pattern mm-dd-yyyy_mm-dd-yyyy
        import re
        pattern = r'^\d{2}-\d{2}-\d{4}_\d{2}-\d{2}-\d{4}$'
        matching_sheets = []
        
        for sheet in sheets:
            sheet_name = sheet['properties']['title']
            if re.match(pattern, sheet_name):
                matching_sheets.append({
                    'id': spreadsheet_id,  # Same spreadsheet ID for all tabs
                    'name': sheet_name,
                    'tab_id': sheet['properties']['sheetId']
                })
                logger.info(f"Found matching sheet tab: {sheet_name}")
        
        logger.info(f"Found {len(matching_sheets)} sheet tabs matching pattern")
        
        # Sort by name (date order) - newest first
        matching_sheets.sort(key=lambda x: x['name'], reverse=True)
        
        return jsonify({
            'success': True,
            'sheets': matching_sheets,
            'total_tabs': len(sheets),
            'pattern_matches': len(matching_sheets),
            'spreadsheet_id': spreadsheet_id
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in get_google_sheets: {e}")
        return jsonify({
            'success': False,
            'message': f'An unexpected error occurred: {str(e)}'
        }), 500

@app.route('/api/google-sheets/<sheet_name>/day/<day>', methods=['GET'])
@admin_or_supervisor_required
def get_sheet_data_by_day(sheet_name, day):
    """API endpoint to get specific day data from a sheet tab in BAKERY METRICS spreadsheet"""
    try:
        # Import Google API components
        try:
            from googleapiclient.discovery import build
            from google.oauth2.service_account import Credentials
            logger.info("Google API libraries imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import Google API libraries: {e}")
            return jsonify({
                'success': False,
                'message': 'Google API libraries not available'
            }), 500
        
        # Check for credentials file
        creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
        logger.info(f"Looking for credentials at: {creds_path}")
        
        if not os.path.exists(creds_path):
            logger.error(f"Credentials file not found at: {creds_path}")
            return jsonify({
                'success': False,
                'message': f'Google credentials file not found at {creds_path}'
            }), 500
        
        # Authenticate with Google APIs using newer auth library
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            sheets_service = build('sheets', 'v4', credentials=creds)
            drive_service = build('drive', 'v3', credentials=creds)
            logger.info("Google APIs authenticated successfully")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google APIs: {e}")
            return jsonify({
                'success': False,
                'message': f'Google API authentication failed: {str(e)}'
            }), 500
        
        # Find the BAKERY METRICS spreadsheet
        try:
            query = "name='BAKERY METRICS_2024-2025' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            logger.info(f"Searching for BAKERY METRICS spreadsheet")
            results = drive_service.files().list(q=query, fields="files(id)").execute()
            files = results.get('files', [])
            
            if not files:
                logger.error("BAKERY METRICS_2024-2025 spreadsheet not found")
                return jsonify({
                    'success': False,
                    'message': 'BAKERY METRICS_2024-2025 spreadsheet not found'
                }), 404
            
            spreadsheet_id = files[0]['id']
            logger.info(f"Found BAKERY METRICS spreadsheet: {spreadsheet_id}")
        except Exception as e:
            logger.error(f"Failed to find BAKERY METRICS spreadsheet: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to find BAKERY METRICS spreadsheet: {str(e)}'
            }), 500
        
        # Validate the sheet tab name exists
        try:
            spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            sheet_exists = any(sheet['properties']['title'] == sheet_name for sheet in sheets)
            
            if not sheet_exists:
                logger.warning(f"Sheet tab '{sheet_name}' not found")
                return jsonify({
                    'success': False,
                    'message': f'Sheet tab "{sheet_name}" not found'
                }), 404
                
            logger.info(f"Found sheet tab: {sheet_name}")
        except Exception as e:
            logger.error(f"Failed to validate sheet tab: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to validate sheet tab: {str(e)}'
            }), 500
        
        # Define the mapping from your images
        day_column_mapping = {
            'Monday': 'D',
            'Tuesday': 'E',
            'Wednesday': 'F',
            'Thursday': 'G',
            'Friday': 'H'
        }
        
        if day not in day_column_mapping:
            return jsonify({
                'success': False,
                'message': 'Invalid day provided. Must be Monday, Tuesday, Wednesday, Thursday, or Friday.'
            }), 400
        
        col = day_column_mapping[day]
        logger.info(f"Using column {col} for {day} from sheet tab {sheet_name}")
        
        # Define the cell ranges based on the mapping from your images
        # Include sheet name in range to specify which tab to read from
        ranges = [
            f"'{sheet_name}'!{col}6",   # 1st Shift OEE Die-Cut 1
            f"'{sheet_name}'!{col}7",   # 1st Shift OEE Die-Cut 2
            f"'{sheet_name}'!{col}9",   # 1st Shift POUNDS Die-Cut 1
            f"'{sheet_name}'!{col}10",  # 1st Shift POUNDS Die-Cut 2
            f"'{sheet_name}'!{col}12",  # 1st Shift WASTE Die-Cut 1
            f"'{sheet_name}'!{col}13",  # 1st Shift WASTE Die-Cut 2
            f"'{sheet_name}'!{col}20",  # 2nd Shift OEE Die-Cut 1
            f"'{sheet_name}'!{col}21",  # 2nd Shift OEE Die-Cut 2
            f"'{sheet_name}'!{col}23",  # 2nd Shift POUNDS Die-Cut 1
            f"'{sheet_name}'!{col}24",  # 2nd Shift POUNDS Die-Cut 2
            f"'{sheet_name}'!{col}26",  # 2nd Shift WASTE Die-Cut 1
            f"'{sheet_name}'!{col}27"   # 2nd Shift WASTE Die-Cut 2
        ]
        
        # Get the data from Google Sheets
        try:
            logger.info(f"Fetching data from ranges: {ranges[:3]}...")  # Log first few ranges to avoid clutter
            result = sheets_service.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=ranges
            ).execute()
            
            value_ranges = result.get('valueRanges', [])
            logger.info(f"Retrieved {len(value_ranges)} value ranges")
        except Exception as e:
            logger.error(f"Failed to fetch sheet data: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to fetch sheet data: {str(e)}'
            }), 500
        
        # Helper function to safely get numeric value
        def safe_float(value_range, default=None):
            try:
                if value_range and 'values' in value_range and value_range['values']:
                    value = value_range['values'][0][0]
                    if value and str(value).strip():
                        return float(value)
            except (ValueError, IndexError):
                pass
            return default
        
        # Parse the data according to the mapping
        data = {
            'first_shift': {
                'die_cut1_oee_pct': safe_float(value_ranges[0]) if len(value_ranges) > 0 else None,
                'die_cut2_oee_pct': safe_float(value_ranges[1]) if len(value_ranges) > 1 else None,
                'die_cut1_pounds': safe_float(value_ranges[2]) if len(value_ranges) > 2 else None,
                'die_cut2_pounds': safe_float(value_ranges[3]) if len(value_ranges) > 3 else None,
                'die_cut1_waste_lbs': safe_float(value_ranges[4]) if len(value_ranges) > 4 else None,
                'die_cut2_waste_lbs': safe_float(value_ranges[5]) if len(value_ranges) > 5 else None,
            },
            'second_shift': {
                'die_cut1_oee_pct': safe_float(value_ranges[6]) if len(value_ranges) > 6 else None,
                'die_cut2_oee_pct': safe_float(value_ranges[7]) if len(value_ranges) > 7 else None,
                'die_cut1_pounds': safe_float(value_ranges[8]) if len(value_ranges) > 8 else None,
                'die_cut2_pounds': safe_float(value_ranges[9]) if len(value_ranges) > 9 else None,
                'die_cut1_waste_lbs': safe_float(value_ranges[10]) if len(value_ranges) > 10 else None,
                'die_cut2_waste_lbs': safe_float(value_ranges[11]) if len(value_ranges) > 11 else None,
            }
        }
        
        logger.info(f"Successfully parsed data for {day} from sheet tab {sheet_name}")
        return jsonify({
            'success': True,
            'data': data,
            'sheet_name': sheet_name,
            'day': day,
            'spreadsheet_id': spreadsheet_id
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in get_sheet_data_by_day: {e}")
        return jsonify({
            'success': False,
            'message': f'An unexpected error occurred: {str(e)}'
        }), 500

@app.route('/api/import-sheet-data', methods=['POST'])
@admin_or_supervisor_required
def import_sheet_data():
    """API endpoint to import data from Google Sheets to database"""
    try:
        data = request.get_json()
        
        user_id = session.get('user_id')
        user_name = session.get('user_full_name')
        user_email = session.get('email')
        
        sheet_name = data.get('sheet_name')
        day_of_week = data.get('day_of_week')
        import_data = data.get('data')
        
        if not all([sheet_name, day_of_week, import_data]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        # Validate day
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        if day_of_week not in valid_days:
            return jsonify({
                'success': False,
                'message': 'Invalid day provided'
            }), 400
        
        # Extract week name from sheet name
        week_name = sheet_name
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if record already exists
                cur.execute("""
                    SELECT id FROM week_submissions
                    WHERE week_name = %s AND day_of_week = %s
                """, (week_name, day_of_week))
                
                existing_record = cur.fetchone()
                if existing_record:
                    logger.warning(f"Import blocked: Record already exists for {day_of_week} in week {week_name}")
                    return jsonify({
                        'success': False,
                        'message': f'A record already exists for {day_of_week} in week {week_name}. Please delete the existing record first or choose a different day/week.',
                        'error_type': 'duplicate_record'
                    }), 409
                
                # Parse week dates from sheet name (format: mm-dd-yyyy_mm-dd-yyyy)
                try:
                    if '_' in sheet_name:
                        start_date_str, end_date_str = sheet_name.split('_')
                        week_start = datetime.strptime(start_date_str, '%m-%d-%Y').date()
                        week_end = datetime.strptime(end_date_str, '%m-%d-%Y').date()
                    else:
                        # Fallback dates if parsing fails
                        week_start = datetime.strptime('01-01-2024', '%m-%d-%Y').date()
                        week_end = datetime.strptime('01-07-2024', '%m-%d-%Y').date()
                        logger.warning(f"Could not parse dates from sheet name '{sheet_name}', using fallback dates")
                except ValueError:
                    # Fallback dates if parsing fails
                    week_start = datetime.strptime('01-01-2024', '%m-%d-%Y').date()
                    week_end = datetime.strptime('01-07-2024', '%m-%d-%Y').date()
                    logger.warning(f"Could not parse dates from sheet name '{sheet_name}', using fallback dates")
                
                # Ensure weekly_sheets record exists for this sheet
                cur.execute("""
                    INSERT INTO weekly_sheets (id, sheet_name, week_start, week_end, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (sheet_name) DO UPDATE SET
                        updated_at = CURRENT_TIMESTAMP,
                        is_active = true
                    RETURNING id
                """, (str(uuid.uuid4()), sheet_name, week_start, week_end, True))
                
                weekly_sheet_result = cur.fetchone()
                logger.info(f"Weekly sheet record ensured for '{sheet_name}' with dates {week_start} to {week_end}")
                
                # Create week submission
                cur.execute("""
                    INSERT INTO week_submissions (week_name, day_of_week, week_start, week_end, submitted_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (week_name, day_of_week, week_start, week_end, user_name))
                
                logger.info(f"Created week submission with submitted_by: {user_name}")
                
                week_submission_id = cur.fetchone()[0]
                
                # Insert first shift data if available
                first_shift = import_data['first_shift']
                if any(v is not None for v in first_shift.values()):
                    cur.execute("""
                        INSERT INTO first_shift_metrics (
                            week_submission_id, die_cut1_oee_pct, die_cut2_oee_pct,
                            die_cut1_lbs, die_cut2_lbs,
                            die_cut1_waste_lb, die_cut2_waste_lb,
                            submitted_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        week_submission_id,
                        first_shift['die_cut1_oee_pct'],
                        first_shift['die_cut2_oee_pct'],
                        first_shift['die_cut1_pounds'],  # Google Sheets field name
                        first_shift['die_cut2_pounds'],  # Google Sheets field name
                        first_shift['die_cut1_waste_lbs'],  # Google Sheets field name
                        first_shift['die_cut2_waste_lbs'],  # Google Sheets field name
                        user_name
                    ))
                    logger.info("First shift metrics inserted successfully")
                
                # Insert second shift data if available
                second_shift = import_data['second_shift']
                if any(v is not None for v in second_shift.values()):
                    cur.execute("""
                        INSERT INTO second_shift_metrics (
                            week_submission_id, die_cut1_oee_pct, die_cut2_oee_pct,
                            die_cut1_lbs, die_cut2_lbs,
                            die_cut1_waste_lb, die_cut2_waste_lb,
                            submitted_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        week_submission_id,
                        second_shift['die_cut1_oee_pct'],
                        second_shift['die_cut2_oee_pct'],
                        second_shift['die_cut1_pounds'],  # Google Sheets field name
                        second_shift['die_cut2_pounds'],  # Google Sheets field name
                        second_shift['die_cut1_waste_lbs'],  # Google Sheets field name
                        second_shift['die_cut2_waste_lbs'],  # Google Sheets field name
                        user_name
                    ))
                    logger.info("Second shift metrics inserted successfully")
                
                conn.commit()
                
                # Log the import
                log_submission(
                    user_id, user_name, user_email,
                    'sheet_import',
                    f'Imported data from sheet: {sheet_name} for {day_of_week}'
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Data imported successfully',
                    'week_submission_id': str(week_submission_id)
                })
                
    except Exception as e:
        logger.error(f"Import sheet data error: {e}")
        return jsonify({
            'success': False,
            'message': f'Import failed: {str(e)}'
        }), 500




# ========================================================
# USER REVIEWS API ENDPOINTS
# ========================================================

@app.route('/api/submit-review', methods=['POST'])
@login_required
def submit_review():
    """API endpoint for submitting user reviews"""
    try:
        logger.info("🔍 DEBUG: Review submission started")
        logger.info(f"🔍 DEBUG: Request method: {request.method}")
        logger.info(f"🔍 DEBUG: Request headers: {dict(request.headers)}")
        logger.info(f"🔍 DEBUG: Request content type: {request.content_type}")
        logger.info(f"🔍 DEBUG: Request is_json: {request.is_json}")
        
        # Debug session information
        logger.info(f"🔍 DEBUG: Session data: {dict(session)}")
        logger.info(f"🔍 DEBUG: Session keys: {list(session.keys())}")
        
        # Check request content type
        if not request.is_json:
            logger.error("❌ DEBUG: Request is not JSON")
            logger.error(f"❌ DEBUG: Content-Type was: {request.content_type}")
            return jsonify({
                'success': False,
                'message': 'Content-Type must be application/json'
            }), 400
        
        data = request.get_json()
        logger.info(f"📤 DEBUG: Request data received: {data}")
        logger.info(f"📤 DEBUG: Request data type: {type(data)}")
        
        # Get user information from session first
        user_id = session.get('user_id')  # This is a UUID string
        user_name = session.get('user_full_name', 'Anonymous User')
        user_email = session.get('email', '')
        
        logger.info(f"👤 DEBUG: User info - ID: {user_id}, Name: {user_name}, Email: {user_email}")
        logger.info(f"👤 DEBUG: User ID type: {type(user_id)}")
        
        # Validate required fields
        rating = data.get('rating')
        review_text = data.get('review_text', '').strip()
        
        logger.info(f"📝 Review data - Rating: {rating}, Text length: {len(review_text) if review_text else 0}")
        
        if not rating:
            logger.error("❌ Rating is missing")
            return jsonify({
                'success': False,
                'message': 'Rating is required'
            }), 400
            
        # Validate rating range
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                logger.error(f"❌ Rating {rating} out of range")
                return jsonify({
                    'success': False,
                    'message': 'Rating must be between 1 and 5 stars'
                }), 400
        except ValueError as e:
            logger.error(f"❌ Invalid rating value: {e}")
            return jsonify({
                'success': False,
                'message': 'Invalid rating value'
            }), 400
        
        # Optional fields
        category = data.get('category', 'general')
        is_anonymous = data.get('is_anonymous', False)
        
        logger.info(f"⚙️ Optional fields - Category: {category}, Anonymous: {is_anonymous}")
        
        # Validate review text if provided
        if review_text and len(review_text) > 1000:
            logger.error(f"❌ Review text too long: {len(review_text)} chars")
            return jsonify({
                'success': False,
                'message': 'Review text must be less than 1000 characters'
            }), 400
        
        logger.info("🔗 Connecting to database...")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Determine user_id based on is_anonymous setting
                review_user_id = None
                if not is_anonymous and user_id:
                    # If not anonymous, store the actual user UUID for proper foreign key relationship
                    review_user_id = user_id  # user_id is already a UUID string from session
                    logger.info(f"� Review submission: user_id={user_id}, user={user_name}, email={user_email}, anonymous={is_anonymous}")
                else:
                    # If anonymous, set to NULL so admin doesn't see who submitted
                    logger.info(f"👻 Anonymous review submission")
                    review_user_id = None
                
                logger.info("💾 Inserting review into database...")
                # Insert the review into the user_reviews table
                cur.execute("""
                    INSERT INTO user_reviews (
                        user_id, rating, review_text, category,
                        is_anonymous, is_approved, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                """, (
                    review_user_id,  # user_id based on is_anonymous setting
                    rating,
                    review_text if review_text else None,
                    category,
                    is_anonymous,
                    False  # Reviews require approval by default
                ))
                
                review_id = cur.fetchone()[0]
                logger.info(f"✅ Review inserted with ID: {review_id}")
                
                logger.info("💾 Committing transaction...")
                conn.commit()
                logger.info("✅ Transaction committed successfully")
                
                # Log the review submission
                logger.info("📋 Logging submission...")
                try:
                    log_submission(
                        user_id, user_name, user_email,
                        'user_review',
                        f'Review submitted: {rating} stars - {review_text[:50]}...' if review_text else f'Review submitted: {rating} stars'
                    )
                    logger.info("✅ Submission logged successfully")
                except Exception as log_error:
                    logger.warning(f"⚠️ Logging failed but review was saved: {log_error}")
                
                logger.info(f"🎉 Review submitted by {user_name}: {rating} stars")
                
                return jsonify({
                    'success': True,
                    'message': 'Thank you for your feedback! Your review has been submitted and will be reviewed for approval.',
                    'review_id': str(review_id),
                    'rating': rating
                })
                
    except Exception as e:
        logger.error(f"💥 Submit review error: {e}")
        import traceback
        logger.error(f"💥 Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'An error occurred while submitting your review: {str(e)}'
        }), 500

@app.route('/api/reviews', methods=['GET'])
@login_required
def get_reviews():
    """API endpoint to get approved reviews for display"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 reviews
        category_filter = request.args.get('category', '')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build query based on filters
                base_query = """
                    SELECT
                        id, rating, review_text, category,
                        is_anonymous, is_featured, created_at
                    FROM user_reviews
                    WHERE is_approved = true
                """
                
                params = []
                
                if category_filter:
                    base_query += " AND category = %s"
                    params.append(category_filter)
                
                base_query += " ORDER BY is_featured DESC, created_at DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(base_query, params)
                reviews = cur.fetchall()
                
                # Format reviews for frontend
                formatted_reviews = []
                for review in reviews:
                    formatted_reviews.append({
                        'id': str(review['id']),
                        'rating': review['rating'],
                        'review_text': review['review_text'],
                        'category': review['category'],
                        'is_anonymous': review['is_anonymous'],
                        'is_featured': review['is_featured'],
                        'created_at': review['created_at'].strftime('%B %d, %Y') if review['created_at'] else 'Unknown',
                        'author': 'Anonymous' if review['is_anonymous'] else 'Bakery User'
                    })
                
                # Get average rating
                cur.execute("""
                    SELECT AVG(rating)::NUMERIC(3,2) as avg_rating, COUNT(*) as total_reviews
                    FROM user_reviews
                    WHERE is_approved = true
                """)
                
                stats = cur.fetchone()
                avg_rating = float(stats['avg_rating']) if stats['avg_rating'] else 0
                total_reviews = stats['total_reviews'] if stats else 0
                
                return jsonify({
                    'success': True,
                    'reviews': formatted_reviews,
                    'count': len(formatted_reviews),
                    'average_rating': round(avg_rating, 1),
                    'total_reviews': total_reviews
                })
                
    except Exception as e:
        logger.error(f"Get reviews error: {e}")
        return jsonify({
            'success': False,
            'reviews': [],
            'count': 0,
            'average_rating': 0,
            'total_reviews': 0,
            'message': 'Error loading reviews'
        }), 500

@app.route('/api/public/reviews', methods=['GET'])
def get_public_reviews():
    """API endpoint to get approved reviews for public display on landing page"""
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 6)), 12)  # Max 12 reviews per page
        offset = (page - 1) * per_page
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get approved reviews with user information for public display
                cur.execute("""
                    SELECT 
                        ur.id, ur.rating, ur.review_text, ur.category,
                        ur.is_anonymous, ur.is_featured, ur.created_at,
                        u.first_name, u.last_name
                    FROM user_reviews ur
                    LEFT JOIN users u ON ur.user_id = u.id
                    WHERE ur.is_approved = true
                    ORDER BY ur.is_featured DESC, ur.created_at DESC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
                
                reviews = cur.fetchall()
                
                # Get total count for pagination
                cur.execute("""
                    SELECT COUNT(*) as total_count
                    FROM user_reviews
                    WHERE is_approved = true
                """)
                
                total_count = cur.fetchone()['total_count']
                total_pages = (total_count + per_page - 1) // per_page
                
                # Format reviews for public display
                formatted_reviews = []
                for review in reviews:
                    # Determine author display name
                    if review['is_anonymous']:
                        author_name = 'Anonymous Customer'
                    elif review['first_name'] and review['last_name']:
                        author_name = f"{review['first_name']} {review['last_name']}"
                    else:
                        author_name = 'Verified Customer'
                    
                    formatted_reviews.append({
                        'id': str(review['id']),
                        'rating': review['rating'],
                        'review_text': review['review_text'],
                        'category': review['category'],
                        'is_featured': review['is_featured'],
                        'author_name': author_name,
                        'created_at': review['created_at'].strftime('%B %Y') if review['created_at'] else 'Recently'
                    })
                
                # Get average rating for display
                cur.execute("""
                    SELECT AVG(rating)::NUMERIC(3,2) as avg_rating
                    FROM user_reviews
                    WHERE is_approved = true
                """)
                
                avg_rating_result = cur.fetchone()
                avg_rating = float(avg_rating_result['avg_rating']) if avg_rating_result['avg_rating'] else 0
                
                return jsonify({
                    'success': True,
                    'reviews': formatted_reviews,
                    'pagination': {
                        'current_page': page,
                        'per_page': per_page,
                        'total_pages': total_pages,
                        'total_count': total_count,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    },
                    'average_rating': round(avg_rating, 1),
                    'total_reviews': total_count
                })
                
    except Exception as e:
        logger.error(f"Get public reviews error: {e}")
        return jsonify({
            'success': False,
            'reviews': [],
            'pagination': {
                'current_page': 1,
                'per_page': per_page,
                'total_pages': 0,
                'total_count': 0,
                'has_next': False,
                'has_prev': False
            },
            'average_rating': 0,
            'total_reviews': 0,
            'message': 'Error loading reviews'
        }), 500

@app.route('/api/admin/reviews', methods=['GET'])
@admin_required
def get_admin_reviews():
    """API endpoint to get all reviews for admin management"""
    try:
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all reviews with user information using proper JOIN
                cur.execute("""
                    SELECT 
                        ur.id, ur.user_id, ur.rating, ur.review_text, ur.category,
                        ur.is_approved, ur.is_featured, ur.is_anonymous,
                        ur.created_at, ur.approved_at, ur.approved_by,
                        u.first_name, u.last_name, u.email
                    FROM user_reviews ur
                    LEFT JOIN users u ON ur.user_id = u.id
                    ORDER BY ur.created_at DESC
                """)
                reviews = cur.fetchall()
                
                # Format reviews for admin panel
                formatted_reviews = []
                for review in reviews:
                    # Determine author display name
                    if review['is_anonymous'] or review['user_id'] is None:
                        author_name = 'Anonymous'
                        author_email = None
                        user_reference = None
                    else:
                        # Show the actual user information
                        if review['first_name'] and review['last_name']:
                            author_name = f"{review['first_name']} {review['last_name']}"
                        else:
                            author_name = f"User {review['email']}" if review['email'] else f"User {review['user_id'][:8]}..."
                        author_email = review['email']
                        user_reference = str(review['user_id'])
                    
                    formatted_reviews.append({
                        'id': str(review['id']),
                        'user_id': user_reference,
                        'rating': review['rating'],
                        'review_text': review['review_text'] or '',
                        'category': review['category'] or 'general',
                        'is_approved': review['is_approved'],
                        'is_featured': review['is_featured'],
                        'is_anonymous': review['is_anonymous'],
                        'author_name': author_name,
                        'author_email': author_email,
                        'created_at': review['created_at'].strftime('%Y-%m-%d %H:%M:%S') if review['created_at'] else 'Unknown',
                        'approved_at': review['approved_at'].strftime('%Y-%m-%d %H:%M:%S') if review['approved_at'] else None,
                        'approved_by': review['approved_by']
                    })
                
                # Get review statistics
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_reviews,
                        COUNT(*) FILTER (WHERE is_approved = true) as approved_reviews,
                        COUNT(*) FILTER (WHERE is_approved = false) as pending_reviews,
                        COUNT(*) FILTER (WHERE is_featured = true) as featured_reviews,
                        AVG(rating)::NUMERIC(3,2) as avg_rating
                    FROM user_reviews
                """)
                stats = cur.fetchone()
                
                return jsonify({
                    'success': True,
                    'reviews': formatted_reviews,
                    'stats': {
                        'total_reviews': stats['total_reviews'] or 0,
                        'approved_reviews': stats['approved_reviews'] or 0,
                        'pending_reviews': stats['pending_reviews'] or 0,
                        'featured_reviews': stats['featured_reviews'] or 0,
                        'avg_rating': float(stats['avg_rating']) if stats['avg_rating'] else 0
                    }
                })
                
    except Exception as e:
        logger.error(f"Get admin reviews error: {e}")
        return jsonify({
            'success': False,
            'reviews': [],
            'message': f'Error loading reviews: {str(e)}'
        }), 500

@app.route('/api/admin/reviews/<review_id>', methods=['PUT'])
@admin_required
def update_review_status(review_id):
    """API endpoint to update review approval/featured status"""
    try:
        data = request.get_json()
        is_approved = data.get('is_approved')
        is_featured = data.get('is_featured')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Update review status
                update_fields = []
                params = []
                
                if is_approved is not None:
                    update_fields.append("is_approved = %s")
                    params.append(is_approved)
                    if is_approved:
                        update_fields.append("approved_at = CURRENT_TIMESTAMP")
                        update_fields.append("approved_by = %s")
                        params.append(session.get('username', 'admin'))
                
                if is_featured is not None:
                    update_fields.append("is_featured = %s")
                    params.append(is_featured)
                
                if not update_fields:
                    return jsonify({
                        'success': False,
                        'message': 'No valid fields to update'
                    }), 400
                
                params.append(review_id)
                query = f"UPDATE user_reviews SET {', '.join(update_fields)} WHERE id = %s"
                
                cur.execute(query, params)
                conn.commit()
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Review not found'
                    }), 404
                
                return jsonify({
                    'success': True,
                    'message': 'Review updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Update review status error: {e}")
        return jsonify({
            'success': False,
            'message': f'Error updating review: {str(e)}'
        }), 500

@app.route('/api/admin/reviews/<review_id>', methods=['DELETE'])
@admin_required
def delete_review(review_id):
    """API endpoint to delete a review"""
    try:
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_reviews WHERE id = %s", (review_id,))
                conn.commit()
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Review not found'
                    }), 404
                
                return jsonify({
                    'success': True,
                    'message': 'Review deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete review error: {e}")
        return jsonify({
            'success': False,
            'message': f'Error deleting review: {str(e)}'
        }), 500

# ========================================================
# SUPPORT CENTER API ENDPOINTS
# ========================================================

@app.route('/api/support/categories', methods=['GET'])
@login_required
def get_support_categories():
    """API endpoint to get all active support categories"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, description, icon, is_active
                    FROM support_categories
                    WHERE is_active = true
                    ORDER BY sort_order ASC, name ASC
                """)
                categories = cur.fetchall()
                
                formatted_categories = []
                for category in categories:
                    formatted_categories.append({
                        'id': str(category['id']),
                        'name': category['name'],
                        'description': category['description'] or '',
                        'icon': category['icon'] or 'help-circle'
                    })
                
                return jsonify({
                    'success': True,
                    'categories': formatted_categories,
                    'count': len(formatted_categories)
                })
                
    except Exception as e:
        logger.error(f"Get support categories error: {e}")
        return jsonify({
            'success': False,
            'categories': [],
            'message': 'Failed to load support categories'
        }), 500

@app.route('/api/support/tickets', methods=['POST'])
@login_required
def submit_support_ticket():
    """API endpoint to submit a new support ticket"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['category_id', 'subject', 'description', 'priority']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Unknown User')
        user_email = session.get('email', '')
        
        # Validate priority
        valid_priorities = ['low', 'medium', 'high', 'critical']
        if data['priority'] not in valid_priorities:
            return jsonify({
                'success': False,
                'message': 'Invalid priority level'
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify category exists and convert to integer
                category_id = int(data['category_id'])
                cur.execute("""
                    SELECT id FROM support_categories
                    WHERE id = %s AND is_active = true
                """, (category_id,))
                
                if not cur.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Invalid support category'
                    }), 400
                
                # First, let's add the user_id_string column if it doesn't exist
                try:
                    cur.execute("""
                        ALTER TABLE support_tickets
                        ADD COLUMN IF NOT EXISTS user_id_string VARCHAR(255)
                    """)
                    logger.info("Added user_id_string column to support_tickets table")
                except Exception as e:
                    logger.warning(f"Could not add user_id_string column (may already exist): {e}")
                
                logger.info(f"Creating support ticket for user_id: {user_id}")
                
                # First, verify the user exists and get their numeric ID
                cur.execute("SELECT id FROM users WHERE id::text = %s", (user_id,))
                user_record = cur.fetchone()
                
                if not user_record:
                    return jsonify({
                        'success': False,
                        'message': 'User not found in system'
                    }), 400
                
                # Insert the support ticket using both user_id_string and the UUID user_id
                cur.execute("""
                    INSERT INTO support_tickets (
                        category_id, user_id_string,
                        subject, description, priority, status
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, ticket_number
                """, (
                    category_id, user_id,
                    data['subject'], data['description'], data['priority'], 'open'
                ))
                
                result = cur.fetchone()
                ticket_id, ticket_number = result
                
                conn.commit()
                
                # Log the ticket submission
                log_submission(
                    user_id, user_name, user_email,
                    'support_ticket',
                    f'Support ticket submitted: {ticket_number} - {data["subject"]}'
                )
                
                logger.info(f"Support ticket created by {user_name}: {ticket_number}")
                
                return jsonify({
                    'success': True,
                    'message': 'Support ticket submitted successfully',
                    'ticket_id': str(ticket_id),
                    'ticket_number': ticket_number
                })
                
    except Exception as e:
        logger.error(f"Submit support ticket error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while submitting your support ticket'
        }), 500

@app.route('/api/support/tickets/recent', methods=['GET'])
@login_required
def get_recent_support_tickets():
    """API endpoint to get recent support tickets for the current user"""
    try:
        user_id = session.get('user_id')
        limit = min(int(request.args.get('limit', 5)), 20)  # Max 20 tickets
        
        logger.info(f"Recent tickets request - user_id from session: '{user_id}' (type: {type(user_id)})")
        
        # Ensure user_id_string column exists and query tickets
        logger.info(f"Getting recent tickets for user_id: {user_id}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Ensure the column exists
                try:
                    cur.execute("""
                        ALTER TABLE support_tickets
                        ADD COLUMN IF NOT EXISTS user_id_string VARCHAR(255)
                    """)
                    logger.info("Ensured user_id_string column exists")
                except Exception as e:
                    logger.warning(f"Column add attempt: {e}")
                
                # Check what tickets exist
                cur.execute("SELECT COUNT(*) as total_tickets FROM support_tickets")
                total_count = cur.fetchone()['total_tickets']
                logger.info(f"Total tickets in database: {total_count}")
                
                # Check existing user_ids
                cur.execute("""
                    SELECT DISTINCT user_id_string
                    FROM support_tickets
                    WHERE user_id_string IS NOT NULL
                    AND user_id_string != ''
                """)
                existing_user_ids = [row['user_id_string'] for row in cur.fetchall()]
                logger.info(f"Existing user_id_strings: {existing_user_ids}")
                
                cur.execute("""
                    SELECT
                        st.id,
                        st.ticket_number,
                        st.subject,
                        st.status,
                        st.priority,
                        st.created_at,
                        st.updated_at,
                        sc.name as category_name,
                        sc.icon as category_icon
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    WHERE st.user_id_string = %s
                    ORDER BY st.created_at DESC
                    LIMIT %s
                """, (user_id, limit))
                
                tickets = cur.fetchall()
                
                formatted_tickets = []
                for ticket in tickets:
                    # Calculate time ago
                    created_at = ticket['created_at']
                    if created_at:
                        time_diff = datetime.now() - created_at.replace(tzinfo=None)
                        if time_diff.total_seconds() < 3600:
                            minutes = int(time_diff.total_seconds() / 60)
                            time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago" if minutes > 0 else "Just now"
                        elif time_diff.total_seconds() < 86400:
                            hours = int(time_diff.total_seconds() / 3600)
                            time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
                        else:
                            days = int(time_diff.total_seconds() / 86400)
                            time_ago = f"{days} day{'s' if days != 1 else ''} ago"
                    else:
                        time_ago = "Unknown"
                    
                    formatted_tickets.append({
                        'id': str(ticket['id']),
                        'ticket_number': ticket['ticket_number'],
                        'subject': ticket['subject'],
                        'status': ticket['status'].title(),
                        'priority': ticket['priority'].title(),
                        'category': ticket['category_name'],
                        'category_icon': ticket['category_icon'] or 'help-circle',
                        'time_ago': time_ago,
                        'created_at': created_at.isoformat() if created_at else None
                    })
                
                return jsonify({
                    'success': True,
                    'tickets': formatted_tickets,
                    'count': len(formatted_tickets)
                })
                
    except Exception as e:
        logger.error(f"Get recent support tickets error: {e}")
        return jsonify({
            'success': False,
            'tickets': [],
            'message': 'Failed to load recent tickets'
        }), 500

@app.route('/api/support/tickets/<ticket_id>', methods=['GET'])
@login_required
def get_support_ticket_details(ticket_id):
    """API endpoint to get full details of a specific support ticket"""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        st.id,
                        st.ticket_number,
                        st.subject,
                        st.description,
                        st.status,
                        st.priority,
                        st.created_at,
                        st.updated_at,
                        sc.name as category_name,
                        sc.description as category_description,
                        sc.icon as category_icon
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    WHERE st.id = %s AND st.user_id_string = %s
                """, (ticket_id, user_id))
                
                ticket = cur.fetchone()
                
                if not ticket:
                    return jsonify({
                        'success': False,
                        'message': 'Ticket not found or access denied'
                    }), 404
                
                # Format the ticket data
                ticket_data = {
                    'id': str(ticket['id']),
                    'ticket_number': ticket['ticket_number'],
                    'subject': ticket['subject'],
                    'description': ticket['description'],
                    'status': ticket['status'].title(),
                    'priority': ticket['priority'].title(),
                    'category': {
                        'name': ticket['category_name'],
                        'description': ticket['category_description'] or '',
                        'icon': ticket['category_icon'] or 'help-circle'
                    },
                    'created_at': ticket['created_at'].isoformat() if ticket['created_at'] else None,
                    'updated_at': ticket['updated_at'].isoformat() if ticket['updated_at'] else None,
                    'created_date': ticket['created_at'].strftime('%B %d, %Y at %I:%M %p') if ticket['created_at'] else 'Unknown',
                    'updated_date': ticket['updated_at'].strftime('%B %d, %Y at %I:%M %p') if ticket['updated_at'] else 'Unknown'
                }
                
                return jsonify({
                    'success': True,
                    'ticket': ticket_data
                })
                
    except Exception as e:
        logger.error(f"Get support ticket details error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to load ticket details'
        }), 500

@app.route('/api/support/statistics', methods=['GET'])
@login_required
def get_support_statistics():
    """API endpoint to get support center statistics"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get overall statistics
                cur.execute("""
                    SELECT
                        COUNT(*) as total_tickets,
                        COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                        COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tickets,
                        COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_tickets,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_tickets,
                        COALESCE(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/60), 0) as avg_response_time_minutes
                    FROM support_tickets
                    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                """)
                
                stats = cur.fetchone()
                
                # Get availability percentage (assume 95% uptime as default)
                availability = 95.0
                
                # Get satisfaction rating (calculate from resolved tickets or use default)
                cur.execute("""
                    SELECT COUNT(*) as resolved_count
                    FROM support_tickets
                    WHERE status = 'resolved'
                    AND created_at >= CURRENT_DATE - INTERVAL '30 days'
                """)
                resolved_result = cur.fetchone()
                
                # Calculate satisfaction based on resolution rate (simple formula)
                total_tickets = stats['total_tickets'] if stats['total_tickets'] else 0
                resolved_tickets = resolved_result['resolved_count'] if resolved_result else 0
                
                if total_tickets > 0:
                    satisfaction = min(95, (resolved_tickets / total_tickets) * 100 + 75)  # Base 75% + resolution bonus
                else:
                    satisfaction = 90.0  # Default satisfaction
                
                # Calculate average response time in hours
                response_time_hours = round(stats['avg_response_time_minutes'] / 60, 1) if stats['avg_response_time_minutes'] else 2.5
                
                return jsonify({
                    'success': True,
                    'statistics': {
                        'availability': round(availability, 1),
                        'satisfaction': round(satisfaction, 1),
                        'response_time': response_time_hours,
                        'total_tickets': total_tickets,
                        'open_tickets': stats['open_tickets'] if stats else 0,
                        'resolved_tickets': resolved_tickets
                    }
                })
                
    except Exception as e:
        logger.error(f"Get support statistics error: {e}")
        return jsonify({
            'success': False,
            'statistics': {
                'availability': 95.0,
                'satisfaction': 90.0,
                'response_time': 2.5,
                'total_tickets': 0,
                'open_tickets': 0,
                'resolved_tickets': 0
            },
            'message': 'Using default statistics due to error'
        }), 500

@app.route('/api/support-tickets', methods=['GET'])
@admin_required
def get_all_support_tickets():
    """API endpoint for admin to get all support tickets"""
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(10, int(request.args.get('limit', 20))))
        status_filter = request.args.get('status', '').strip()
        priority_filter = request.args.get('priority', '').strip()
        search_query = request.args.get('search', '').strip()
        
        # Calculate offset for pagination
        offset = (page - 1) * limit
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build the WHERE clause based on filters
                where_conditions = []
                params = []
                
                if status_filter:
                    where_conditions.append("st.status = %s")
                    params.append(status_filter)
                
                if priority_filter:
                    where_conditions.append("st.priority = %s")
                    params.append(priority_filter)
                
                if search_query:
                    where_conditions.append("(st.subject ILIKE %s OR st.description ILIKE %s OR st.ticket_number ILIKE %s)")
                    search_param = f"%{search_query}%"
                    params.extend([search_param, search_param, search_param])
                
                where_clause = " AND ".join(where_conditions)
                if where_clause:
                    where_clause = "WHERE " + where_clause
                
                # Get total count for pagination
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    LEFT JOIN users u ON st.user_id_string = u.id::text
                    {where_clause}
                """
                
                cur.execute(count_query, params)
                total_tickets = cur.fetchone()['total']
                
                # Get tickets with pagination
                tickets_query = f"""
                    SELECT
                        st.id,
                        st.ticket_number,
                        st.subject,
                        st.description,
                        st.status,
                        st.priority,
                        st.created_at,
                        st.updated_at,
                        st.user_id_string,
                        sc.name as category_name,
                        sc.icon as category_icon,
                        COALESCE(u.first_name || ' ' || u.last_name, 'Unknown User') as user_name,
                        u.email as user_email
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    LEFT JOIN users u ON st.user_id_string = u.id::text
                    {where_clause}
                    ORDER BY st.created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                params.extend([limit, offset])
                cur.execute(tickets_query, params)
                tickets = cur.fetchall()
                
                # Format tickets data
                formatted_tickets = []
                for ticket in tickets:
                    # Calculate time ago
                    created_at = ticket['created_at']
                    if created_at:
                        time_diff = datetime.now() - created_at.replace(tzinfo=None)
                        if time_diff.total_seconds() < 3600:
                            minutes = int(time_diff.total_seconds() / 60)
                            time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago" if minutes > 0 else "Just now"
                        elif time_diff.total_seconds() < 86400:
                            hours = int(time_diff.total_seconds() / 3600)
                            time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
                        else:
                            days = int(time_diff.total_seconds() / 86400)
                            time_ago = f"{days} day{'s' if days != 1 else ''} ago"
                    else:
                        time_ago = "Unknown"
                    
                    formatted_tickets.append({
                        'id': str(ticket['id']),
                        'ticket_number': ticket['ticket_number'],
                        'subject': ticket['subject'],
                        'description': ticket['description'][:200] + ('...' if len(ticket['description']) > 200 else ''),
                        'full_description': ticket['description'],
                        'status': ticket['status'],
                        'priority': ticket['priority'],
                        'category_name': ticket['category_name'],
                        'category_icon': ticket['category_icon'] or 'help-circle',
                        'user_name': ticket['user_name'],
                        'user_email': ticket['user_email'] or 'No email',
                        'user_id_string': ticket['user_id_string'],
                        'created_at': ticket['created_at'].isoformat() if ticket['created_at'] else None,
                        'created_date': ticket['created_at'].strftime('%b %d, %Y %I:%M %p') if ticket['created_at'] else 'Unknown',
                        'time_ago': time_ago
                    })
                
                # Calculate pagination info
                total_pages = (total_tickets + limit - 1) // limit
                has_next = page < total_pages
                has_prev = page > 1
                
                return jsonify({
                    'success': True,
                    'tickets': formatted_tickets,
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total_tickets,
                        'total_pages': total_pages,
                        'has_next': has_next,
                        'has_prev': has_prev
                    }
                })
                
    except Exception as e:
        logger.error(f"Get all support tickets error: {e}")
        return jsonify({
            'success': False,
            'tickets': [],
            'message': 'Failed to load support tickets'
        }), 500

@app.route('/api/support-tickets/<int:ticket_id>', methods=['PUT'])
@admin_required 
def update_support_ticket(ticket_id):
    """API endpoint for admin to update support ticket status"""
    try:
        data = request.get_json()
        status = data.get('status', '').strip()
        
        # Validate status
        valid_statuses = ['open', 'in_progress', 'waiting', 'resolved', 'closed']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'message': 'Invalid status provided'
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Update the ticket status
                cur.execute("""
                    UPDATE support_tickets 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP,
                        resolved_at = CASE WHEN %s = 'resolved' THEN CURRENT_TIMESTAMP ELSE resolved_at END
                    WHERE id = %s
                    RETURNING ticket_number
                """, (status, status, ticket_id))
                
                result = cur.fetchone()
                if not result:
                    return jsonify({
                        'success': False,
                        'message': 'Ticket not found'
                    }), 404
                
                ticket_number = result[0]
                conn.commit()
                
                logger.info(f"Ticket {ticket_number} status updated to {status} by admin")
                
                return jsonify({
                    'success': True,
                    'message': f'Ticket {ticket_number} updated successfully',
                    'new_status': status
                })
                
    except Exception as e:
        logger.error(f"Update support ticket error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to update ticket'
        }), 500

@app.route('/api/support-tickets/<int:ticket_id>', methods=['DELETE'])
@admin_required
def delete_support_ticket(ticket_id):
    """API endpoint for admin to delete support ticket"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get ticket info before deletion
                cur.execute("SELECT ticket_number FROM support_tickets WHERE id = %s", (ticket_id,))
                result = cur.fetchone()
                
                if not result:
                    return jsonify({
                        'success': False,
                        'message': 'Ticket not found'
                    }), 404
                
                ticket_number = result[0]
                
                # Delete the ticket
                cur.execute("DELETE FROM support_tickets WHERE id = %s", (ticket_id,))
                conn.commit()
                
                logger.info(f"Ticket {ticket_number} deleted by admin")
                
                return jsonify({
                    'success': True,
                    'message': f'Ticket {ticket_number} deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete support ticket error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete ticket'
        }), 500

# ============================================================================
# ADMIN PROFILE API ENDPOINTS
# ============================================================================

@app.route('/api/admin/profile', methods=['GET'])
@admin_required
def get_admin_profile():
    """API endpoint to get admin profile information"""
    try:
        admin_id = session.get('user_id')
        logger.info(f"Admin profile request for user_id: {admin_id}")
        
        if not admin_id:
            logger.error("No user_id in session")
            return jsonify({
                'success': False,
                'message': 'User ID not found in session'
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get admin information
                cur.execute("""
                    SELECT 
                        id,
                        first_name,
                        last_name,
                        email,
                        role,
                        created_at,
                        updated_at,
                        last_login
                    FROM users 
                    WHERE id = %s AND role = 'admin'
                """, (admin_id,))
                
                admin = cur.fetchone()
                logger.info(f"Database query result: {admin is not None}")
                
                if not admin:
                    logger.error(f"Admin profile not found for user_id: {admin_id}")
                    return jsonify({
                        'success': False,
                        'message': 'Admin profile not found'
                    }), 404
                
                # Convert datetime objects to strings for JSON serialization
                admin_data = dict(admin)
                
                # Combine first and last name
                admin_data['full_name'] = f"{admin_data.get('first_name', '')} {admin_data.get('last_name', '')}".strip()
                
                if admin_data.get('created_at'):
                    admin_data['created_at'] = admin_data['created_at'].isoformat()
                if admin_data.get('updated_at'):
                    admin_data['updated_at'] = admin_data['updated_at'].isoformat()
                if admin_data.get('last_login'):
                    admin_data['last_login'] = admin_data['last_login'].isoformat()
                
                logger.info("Admin profile loaded successfully")
                return jsonify({
                    'success': True,
                    'admin': admin_data
                })
                
    except Exception as e:
        logger.error(f"Get admin profile error: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to load profile data: {str(e)}'
        }), 500

@app.route('/api/admin/reset-password', methods=['POST'])
@admin_required
def reset_admin_password():
    """API endpoint for admin to reset their password"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request data'
            }), 400
        
        current_password = data.get('current_password', '').strip()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        
        # Validate input
        if not all([current_password, new_password, confirm_password]):
            return jsonify({
                'success': False,
                'message': 'All password fields are required'
            }), 400
        
        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'message': 'New passwords do not match'
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': 'New password must be at least 6 characters long'
            }), 400
        
        admin_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get current admin data
                cur.execute("SELECT email, password_hash FROM users WHERE id = %s AND role = 'admin'", (admin_id,))
                result = cur.fetchone()
                
                if not result:
                    return jsonify({
                        'success': False,
                        'message': 'Admin account not found'
                    }), 404
                
                email, stored_password_hash = result
                
                # Verify current password
                if not bcrypt.checkpw(current_password.encode('utf-8'), stored_password_hash.encode('utf-8')):
                    return jsonify({
                        'success': False,
                        'message': 'Current password is incorrect'
                    }), 400
                
                # Hash new password
                hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                # Update password
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s, updated_at = %s 
                    WHERE id = %s
                """, (hashed_new_password, datetime.now(), admin_id))
                
                conn.commit()
                
                logger.info(f"Admin password updated successfully for user {admin_id}")
                
                return jsonify({
                    'success': True,
                    'message': 'Password updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Reset admin password error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to update password'
        }), 500

# ============================================================================
# SYSTEM STATUS API ENDPOINT
# ============================================================================

@app.route('/api/system-status', methods=['GET'])
@admin_required
def get_system_status():
    """Lightweight API endpoint for real-time system status in sidebar"""
    try:
        import time
        from datetime import datetime
        
        # Initialize status data
        status_data = {
            'health': 'Unknown',
            'health_color': 'red',
            'users_online': 0,
            'database_status': 'Unknown',
            'database_color': 'red',
            'uptime': 'Unknown',
            'cpu_usage': 0,
            'memory_usage': 0,
            'last_activity': 'Unknown'
        }
        
        # Check database connectivity
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Test database connection
                    cur.execute("SELECT 1")
                    status_data['database_status'] = 'Connected'
                    status_data['database_color'] = 'green'
                    
                    # Get active sessions (approximate users online)
                    # This is a rough estimate based on recent activity
                    cutoff_time = datetime.now() - timedelta(minutes=15)
                    cur.execute("""
                        SELECT COUNT(DISTINCT user_id) 
                        FROM submission_logs 
                        WHERE created_at > %s
                    """, (cutoff_time,))
                    
                    result = cur.fetchone()
                    status_data['users_online'] = result[0] if result and result[0] else 0
                    
                    # Get last activity time
                    cur.execute("""
                        SELECT MAX(created_at) 
                        FROM submission_logs
                    """)
                    
                    last_activity_result = cur.fetchone()
                    if last_activity_result and last_activity_result[0]:
                        last_activity = last_activity_result[0]
                        time_diff = datetime.now() - last_activity.replace(tzinfo=None)
                        
                        if time_diff.total_seconds() < 60:
                            status_data['last_activity'] = 'Just now'
                        elif time_diff.total_seconds() < 3600:
                            minutes = int(time_diff.total_seconds() / 60)
                            status_data['last_activity'] = f'{minutes}m ago'
                        elif time_diff.total_seconds() < 86400:
                            hours = int(time_diff.total_seconds() / 3600)
                            status_data['last_activity'] = f'{hours}h ago'
                        else:
                            days = int(time_diff.total_seconds() / 86400)
                            status_data['last_activity'] = f'{days}d ago'
                    else:
                        status_data['last_activity'] = 'No activity'
                        
        except Exception as e:
            logger.error(f"Database status check failed: {e}")
            status_data['database_status'] = 'Error'
            status_data['database_color'] = 'red'
        
        # Check system resources if psutil is available
        try:
            import psutil
            
            # Get system uptime
            try:
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time
                uptime_hours = uptime_seconds / 3600
                uptime_days = uptime_hours / 24
                
                if uptime_days >= 1:
                    status_data['uptime'] = f"{int(uptime_days)}d {int(uptime_hours % 24)}h"
                else:
                    status_data['uptime'] = f"{int(uptime_hours)}h {int((uptime_seconds % 3600) / 60)}m"
                    
            except Exception as e:
                logger.warning(f"Failed to get uptime: {e}")
                status_data['uptime'] = 'Unknown'
            
            # Get CPU and memory usage
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                
                status_data['cpu_usage'] = round(cpu_percent, 1)
                status_data['memory_usage'] = round(memory.percent, 1)
                
                # Determine overall health based on resources and database
                if status_data['database_status'] == 'Connected':
                    if cpu_percent < 70 and memory.percent < 70:
                        status_data['health'] = 'Optimal'
                        status_data['health_color'] = 'green'
                    elif cpu_percent < 85 and memory.percent < 85:
                        status_data['health'] = 'Good'
                        status_data['health_color'] = 'yellow'
                    else:
                        status_data['health'] = 'Warning'
                        status_data['health_color'] = 'orange'
                else:
                    status_data['health'] = 'Critical'
                    status_data['health_color'] = 'red'
                    
            except Exception as e:
                logger.warning(f"Failed to get system metrics: {e}")
                status_data['health'] = 'Limited'
                status_data['health_color'] = 'yellow'
                
        except ImportError:
            logger.warning("psutil not available - using basic status")
            # Fallback status based on database only
            if status_data['database_status'] == 'Connected':
                status_data['health'] = 'Good'
                status_data['health_color'] = 'green'
                status_data['uptime'] = 'Available'
            else:
                status_data['health'] = 'Warning'
                status_data['health_color'] = 'orange'
                status_data['uptime'] = 'Unknown'
        
        return jsonify({
            'success': True,
            'status': status_data
        })
        
    except Exception as e:
        logger.error(f"System status error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get system status',
            'status': {
                'health': 'Error',
                'health_color': 'red',
                'users_online': 0,
                'database_status': 'Error',
                'database_color': 'red',
                'uptime': 'Unknown',
                'cpu_usage': 0,
                'memory_usage': 0,
                'last_activity': 'Unknown'
            }
        }), 500

@app.route('/help')
@login_required
def help_center():
    """Render the help center page with documentation and support resources."""
    try:
        # Check if user is logged in (assuming you have session management)
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # You can add any additional context data here
        context = {
            'page_title': 'Help Center',
            'current_page': 'help'
        }
        
        return render_template('infor.html', **context)
        
    except Exception as e:
        flash('Error loading help center. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    
    
@app.route('/logout', methods=['POST'])
def logout():
    user_id = session.get('user_id')
    user_name = session.get('user_full_name')
    user_email = session.get('email')

    if user_id:
        log_submission(user_id, user_name, user_email, 'logout', 'User logged out')

    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('home'))

@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    """API endpoint to change user password."""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        user_id = session.get('user_id')

        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'message': 'Current password and new password are required.'
            }), 400

        # Validate new password length
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'message': 'New password must be at least 8 characters long.'
            }), 400

        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get current user's password hash
            cur.execute("""
                SELECT password_hash, email, first_name, last_name 
                FROM users 
                WHERE id = %s
            """, (user_id,))
            
            user = cur.fetchone()
            
            if not user:
                return jsonify({
                    'success': False,
                    'message': 'User not found.'
                }), 404

            # Verify current password
            if not verify_password(current_password, user['password_hash']):
                return jsonify({
                    'success': False,
                    'message': 'Current password is incorrect.'
                }), 401

            # Hash new password
            new_password_hash = hash_password(new_password)

            # Check if password_change_required column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'password_change_required'
            """)
            has_password_change_column = cur.fetchone() is not None

            # Update password (conditionally update password_change_required if column exists)
            if has_password_change_column:
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s,
                        password_change_required = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_password_hash, user_id))
            else:
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_password_hash, user_id))

            conn.commit()

            # Build full name for logging
            full_name = f"{user['first_name']} {user.get('last_name', '')}".strip()

            # Log the password change
            log_submission(
                user_id, 
                full_name, 
                user['email'], 
                'password_change', 
                'User changed their password'
            )

            logger.info(f"Password changed successfully for user: {user['email']}")

            return jsonify({
                'success': True,
                'message': 'Password changed successfully.'
            })

    except Exception as e:
        logger.error(f"Error in change_password endpoint: {e}")
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred.'
        }), 500

@app.route('/api/my-profile', methods=['GET'])
@login_required
def get_my_profile():
    """API endpoint to get current user's profile information."""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get user and employee information
            cur.execute("""
                SELECT 
                    u.id as user_id,
                    u.email,
                    u.first_name,
                    u.last_name,
                    u.role,
                    e.id as employee_id,
                    e.firstname,
                    e.lastname,
                    e.email as employee_email,
                    e.phonenumber,
                    e.shift,
                    e.department,
                    e.workline,
                    e.workarea,
                    e.supervisor,
                    e.manager,
                    e.role as employee_role,
                    e.date_of_employment,
                    e.allocated_vacation_hours,
                    e.annual_allocation,
                    e.max_accumulated_hours,
                    e.years_of_employment,
                    e.months_of_employment
                FROM users u
                LEFT JOIN employees e ON e.user_id = u.id
                WHERE u.id = %s
            """, (user_id,))
            
            profile = cur.fetchone()
            
            if not profile:
                return jsonify({
                    'success': False,
                    'message': 'Profile not found.'
                }), 404

            # Convert to dict and handle None values
            profile_data = dict(profile) if profile else {}
            
            # Combine first_name and last_name into full_name
            if profile_data.get('first_name'):
                last_name = profile_data.get('last_name', '')
                if last_name and '@' not in last_name:
                    profile_data['full_name'] = f"{profile_data['first_name']} {last_name}"
                else:
                    profile_data['full_name'] = profile_data['first_name']
            
            # Format date_of_employment if it exists
            if profile_data.get('date_of_employment'):
                profile_data['date_of_employment'] = profile_data['date_of_employment'].strftime('%Y-%m-%d')
            
            return jsonify({
                'success': True,
                'profile': profile_data
            })

    except Exception as e:
        logger.error(f"Error in get_my_profile endpoint: {e}")
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred.'
        }), 500

@app.route('/api/my-notifications', methods=['GET'])
@login_required
def get_my_notifications():
    """API endpoint to get current user's notifications."""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get employee_id from user_id
            cur.execute("""
                SELECT id FROM employees WHERE user_id = %s
            """, (user_id,))
            
            employee = cur.fetchone()
            
            if not employee:
                return jsonify({
                    'success': True,
                    'notifications': []
                })
            
            employee_id = employee['id']
            
            # Get notifications for this employee from the last 30 days
            cur.execute("""
                SELECT 
                    id,
                    user_id as employee_id,
                    notification_type as type,
                    title,
                    message,
                    is_read,
                    created_at,
                    related_vacation_id as vacation_id
                FROM notifications
                WHERE user_id = %s
                    AND created_at >= NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC
                LIMIT 50
            """, (employee_id,))
            
            notifications = cur.fetchall()
            
            # Convert to list of dicts
            notifications_list = []
            for notif in notifications:
                notif_dict = dict(notif)
                if notif_dict.get('created_at'):
                    notif_dict['created_at'] = notif_dict['created_at'].isoformat()
                notifications_list.append(notif_dict)
            
            return jsonify({
                'success': True,
                'notifications': notifications_list
            })

    except Exception as e:
        logger.error(f"Error in get_my_notifications endpoint: {e}")
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred.'
        }), 500

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read."""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get employee_id from user_id
            cur.execute("""
                SELECT id FROM employees WHERE user_id = %s
            """, (user_id,))
            
            employee = cur.fetchone()
            
            if not employee:
                return jsonify({
                    'success': False,
                    'message': 'Employee not found.'
                }), 404
            
            employee_id = employee['id']
            
            # Update notification as read (only if it belongs to this employee)
            cur.execute("""
                UPDATE notifications
                SET is_read = TRUE,
                    read_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
            """, (notification_id, employee_id))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Notification marked as read.'
            })

    except Exception as e:
        logger.error(f"Error in mark_notification_read endpoint: {e}")
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred.'
        }), 500

@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for current user."""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get employee_id from user_id
            cur.execute("""
                SELECT id FROM employees WHERE user_id = %s
            """, (user_id,))
            
            employee = cur.fetchone()
            
            if not employee:
                return jsonify({
                    'success': False,
                    'message': 'Employee not found.'
                }), 404
            
            employee_id = employee['id']
            
            # Update all unread notifications
            cur.execute("""
                UPDATE notifications
                SET is_read = TRUE,
                    read_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND is_read = FALSE
            """, (employee_id,))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'All notifications marked as read.'
            })

    except Exception as e:
        logger.error(f"Error in mark_all_notifications_read endpoint: {e}")
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred.'
        }), 500

# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('500.html'), 500

# Initialize database on startup
try:
    init_database()
    logger.info("Flask app initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    logger.warning("App will continue running with limited functionality - database unavailable")
    # Don't exit - allow app to run for frontend demonstration

app.config['APP_START_TIME'] = time.time()


# ========================================================
# FAQ API ENDPOINTS
# ========================================================

@app.route('/api/faqs', methods=['GET'])
@admin_required
def get_faqs():
    """API endpoint to retrieve all FAQs with filtering support"""
    try:
        # Get filter parameters
        category_filter = request.args.get('category', '').strip()
        search_query = request.args.get('search', '').strip()
        active_only = request.args.get('active', 'true').lower() == 'true'
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build dynamic query using existing faq_items table
                base_query = """
                    SELECT
                        f.id,
                        f.question,
                        f.answer,
                        COALESCE(c.name, 'general') as category,
                        COALESCE(f.sort_order, 0) as display_order,
                        COALESCE(f.is_active, true) as is_active,
                        f.created_at,
                        f.updated_at,
                        'System' as created_by_name,
                        'System' as updated_by_name
                    FROM faq_items f
                    LEFT JOIN faq_categories c ON f.category_id = c.id
                """
                
                where_conditions = []
                query_params = []
                
                # Filter by active status
                if active_only:
                    where_conditions.append("COALESCE(f.is_active, true) = %s")
                    query_params.append(True)
                
                # Filter by category
                if category_filter:
                    where_conditions.append("c.name = %s")
                    query_params.append(category_filter)
                
                # Search in question and answer
                if search_query:
                    where_conditions.append("(f.question ILIKE %s OR f.answer ILIKE %s)")
                    query_params.extend([f"%{search_query}%", f"%{search_query}%"])
                
                # Add WHERE clause if there are conditions
                if where_conditions:
                    base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Add ORDER BY clause
                base_query += " ORDER BY COALESCE(f.sort_order, 0) ASC, f.created_at DESC"
                
                cur.execute(base_query, query_params)
                faqs = cur.fetchall()
                
                # Format the data for frontend
                formatted_faqs = []
                for faq in faqs:
                    formatted_faqs.append({
                        'id': str(faq['id']),
                        'question': faq['question'],
                        'answer': faq['answer'],
                        'category': faq['category'],
                        'display_order': faq['display_order'],
                        'is_active': faq['is_active'],
                        'created_at': faq['created_at'].strftime('%Y-%m-%d %H:%M:%S') if faq['created_at'] else '',
                        'updated_at': faq['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if faq['updated_at'] else '',
                        'created_by': faq['created_by_name'] or 'Unknown',
                        'updated_by': faq['updated_by_name'] or 'Unknown'
                    })
                
                return jsonify({
                    'success': True,
                    'faqs': formatted_faqs,
                    'count': len(formatted_faqs)
                })
                
    except Exception as e:
        logger.error(f"Get FAQs error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve FAQs',
            'faqs': []
        }), 500

@app.route('/api/faqs', methods=['POST'])
@admin_required
def create_faq():
    """API endpoint to create a new FAQ"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['question', 'answer']
        for field in required_fields:
            if not data.get(field, '').strip():
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Admin User')
        user_email = session.get('email', '')
        
        # Extract and validate data
        question = data['question'].strip()
        answer = data['answer'].strip()
        category = data.get('category', 'general').strip()
        display_order = int(data.get('order', 0))
        is_active = bool(data.get('is_active', True))
        
        # Validate lengths
        if len(question) > 500:
            return jsonify({
                'success': False,
                'message': 'Question must be less than 500 characters'
            }), 400
        
        if len(answer) > 2000:
            return jsonify({
                'success': False,
                'message': 'Answer must be less than 2000 characters'
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Insert new FAQ
                # First, get or create category
                cur.execute("""
                    INSERT INTO faq_categories (name, description, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (category, f"Questions about {category}", True))
                category_id = cur.fetchone()[0]
                
                # Insert FAQ item
                cur.execute("""
                    INSERT INTO faq_items (
                        question, answer, category_id, sort_order,
                        is_active, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id
                """, (
                    question, answer, category_id, display_order,
                    is_active
                ))
                
                faq_id = cur.fetchone()[0]
                conn.commit()
                
                # Log the creation
                log_submission(
                    user_id, user_name, user_email,
                    'faq_create',
                    f'FAQ created: {question[:50]}...' if len(question) > 50 else question
                )
                
                logger.info(f"FAQ created by {user_name}: {question[:50]}...")
                
                return jsonify({
                    'success': True,
                    'message': 'FAQ created successfully',
                    'faq_id': str(faq_id)
                })
                
    except Exception as e:
        logger.error(f"Create FAQ error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to create FAQ'
        }), 500

@app.route('/api/faqs/<faq_id>', methods=['PUT'])
@admin_required
def update_faq(faq_id):
    """API endpoint to update an existing FAQ with enhanced error handling"""
    try:
        logger.info(f"🔧 FAQ Update: Starting update for FAQ ID: {faq_id}")
        
        # Validate FAQ ID format
        try:
            faq_id_int = int(faq_id)
            logger.info(f"🔧 FAQ Update: Valid FAQ ID: {faq_id_int}")
        except ValueError:
            logger.error(f"🔧 FAQ Update: Invalid FAQ ID format: {faq_id}")
            return jsonify({
                'success': False,
                'message': 'Invalid FAQ ID format'
            }), 400
        
        # Get and validate JSON data
        if not request.is_json:
            logger.error(f"🔧 FAQ Update: Request is not JSON, content-type: {request.content_type}")
            return jsonify({
                'success': False,
                'message': 'Request must be JSON format'
            }), 400
            
        data = request.get_json()
        if not data:
            logger.error("🔧 FAQ Update: Empty JSON data received")
            return jsonify({
                'success': False,
                'message': 'Empty request data'
            }), 400
        
        logger.info(f"🔧 FAQ Update: Received data keys: {list(data.keys()) if data else 'None'}")
        
        # Validate required fields with better error messages
        required_fields = ['question', 'answer']
        for field in required_fields:
            field_value = data.get(field)
            if not field_value or not str(field_value).strip():
                logger.error(f"🔧 FAQ Update: Missing/empty required field: {field}, value: {field_value}")
                return jsonify({
                    'success': False,
                    'message': f'Field "{field}" is required and cannot be empty'
                }), 400
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Admin User')
        user_email = session.get('email', '')
        logger.info(f"🔧 FAQ Update: User info - ID: {user_id}, Name: {user_name}")
        
        # Extract and validate data with better error handling
        try:
            question = str(data['question']).strip()
            answer = str(data['answer']).strip()
            category = str(data.get('category', 'general')).strip() or 'general'
            
            # Handle display_order with proper fallback
            order_value = data.get('order', 0)
            if order_value is None or order_value == '':
                display_order = 0
            else:
                try:
                    display_order = int(order_value)
                except (ValueError, TypeError):
                    logger.warning(f"🔧 FAQ Update: Invalid order value: {order_value}, using 0")
                    display_order = 0
            
            # Handle is_active with proper boolean conversion
            active_value = data.get('is_active', True)
            if isinstance(active_value, str):
                is_active = active_value.lower() in ['true', '1', 'yes', 'on']
            else:
                is_active = bool(active_value)
                
            logger.info(f"🔧 FAQ Update: Parsed data - Question: {len(question)} chars, Answer: {len(answer)} chars, Category: {category}, Order: {display_order}, Active: {is_active}")
            
        except Exception as parse_error:
            logger.error(f"🔧 FAQ Update: Data parsing error: {parse_error}")
            return jsonify({
                'success': False,
                'message': f'Data parsing error: {str(parse_error)}'
            }), 400
        
        # Validate lengths
        if len(question) > 500:
            logger.error(f"🔧 FAQ Update: Question too long: {len(question)} characters")
            return jsonify({
                'success': False,
                'message': f'Question is too long ({len(question)} characters). Maximum is 500 characters.'
            }), 400
        
        if len(answer) > 2000:
            logger.error(f"🔧 FAQ Update: Answer too long: {len(answer)} characters")
            return jsonify({
                'success': False,
                'message': f'Answer is too long ({len(answer)} characters). Maximum is 2000 characters.'
            }), 400
        
        # Database operations with enhanced error handling
        logger.info("🔧 FAQ Update: Starting database transaction")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    # Check if FAQ exists
                    logger.info(f"🔧 FAQ Update: Checking if FAQ {faq_id_int} exists")
                    cur.execute("SELECT id, question FROM faq_items WHERE id = %s", (faq_id_int,))
                    existing_faq = cur.fetchone()
                    
                    if not existing_faq:
                        logger.error(f"🔧 FAQ Update: FAQ {faq_id_int} not found in database")
                        return jsonify({
                            'success': False,
                            'message': f'FAQ with ID {faq_id_int} not found'
                        }), 404
                    
                    logger.info(f"🔧 FAQ Update: Found existing FAQ: {existing_faq[1][:50]}...")
                    
                    # Get or create category with better error handling
                    logger.info(f"🔧 FAQ Update: Processing category: {category}")
                    try:
                        cur.execute("""
                            INSERT INTO faq_categories (name, description, is_active, created_at, updated_at)
                            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT (name) DO UPDATE SET
                                updated_at = CURRENT_TIMESTAMP,
                                is_active = EXCLUDED.is_active
                            RETURNING id
                        """, (category, f"Questions about {category}", True))
                        
                        category_result = cur.fetchone()
                        if not category_result:
                            raise Exception("Failed to get category ID")
                        category_id = category_result[0]
                        logger.info(f"🔧 FAQ Update: Category ID: {category_id}")
                        
                    except Exception as cat_error:
                        logger.error(f"🔧 FAQ Update: Category error: {cat_error}")
                        return jsonify({
                            'success': False,
                            'message': f'Category processing failed: {str(cat_error)}'
                        }), 500
                    
                    # Update FAQ item with detailed logging
                    logger.info(f"🔧 FAQ Update: Updating FAQ item {faq_id_int}")
                    update_query = """
                        UPDATE faq_items SET
                            question = %s,
                            answer = %s,
                            category_id = %s,
                            sort_order = %s,
                            is_active = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    update_params = (question, answer, category_id, display_order, is_active, faq_id_int)
                    logger.info(f"🔧 FAQ Update: Update params: question={len(question)}chars, answer={len(answer)}chars, cat_id={category_id}, order={display_order}, active={is_active}, faq_id={faq_id_int}")
                    
                    cur.execute(update_query, update_params)
                    rows_affected = cur.rowcount
                    logger.info(f"🔧 FAQ Update: Rows affected: {rows_affected}")
                    
                    if rows_affected == 0:
                        logger.error(f"🔧 FAQ Update: No rows updated for FAQ {faq_id_int}")
                        return jsonify({
                            'success': False,
                            'message': f'No changes were made to FAQ {faq_id_int}. Please verify the data.'
                        }), 500
                    
                    # Commit transaction
                    logger.info("🔧 FAQ Update: Committing transaction")
                    conn.commit()
                    logger.info("🔧 FAQ Update: Transaction committed successfully")
                    
                except Exception as db_error:
                    logger.error(f"🔧 FAQ Update: Database error: {db_error}")
                    conn.rollback()
                    return jsonify({
                        'success': False,
                        'message': f'Database error: {str(db_error)}'
                    }), 500
                
                # Log the update (outside transaction for safety)
                try:
                    log_submission(
                        user_id, user_name, user_email,
                        'faq_update',
                        f'FAQ updated: {question[:50]}...' if len(question) > 50 else question
                    )
                    logger.info("🔧 FAQ Update: Update logged successfully")
                except Exception as log_error:
                    logger.warning(f"🔧 FAQ Update: Logging failed but update succeeded: {log_error}")
                
                logger.info(f"🔧 FAQ Update: Successfully updated FAQ {faq_id_int}")
                return jsonify({
                    'success': True,
                    'message': 'FAQ updated successfully',
                    'faq_id': str(faq_id_int)
                })
                
    except Exception as e:
        logger.error(f"🔧 FAQ Update: Unexpected error: {e}")
        import traceback
        logger.error(f"🔧 FAQ Update: Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'Update failed: {str(e)}'
        }), 500

@app.route('/api/faqs/<faq_id>', methods=['DELETE'])
@admin_required
def delete_faq(faq_id):
    """API endpoint to delete an FAQ"""
    try:
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Admin User')
        user_email = session.get('email', '')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get FAQ info for logging
                cur.execute("SELECT question FROM faq_items WHERE id = %s", (faq_id,))
                faq_info = cur.fetchone()
                
                if not faq_info:
                    return jsonify({
                        'success': False,
                        'message': 'FAQ not found'
                    }), 404
                
                # Delete FAQ
                cur.execute("DELETE FROM faq_items WHERE id = %s", (faq_id,))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to delete FAQ'
                    }), 500
                
                conn.commit()
                
                # Log the deletion
                log_submission(
                    user_id, user_name, user_email,
                    'faq_delete',
                    f'FAQ deleted: {faq_info[0][:50]}...' if len(faq_info[0]) > 50 else faq_info[0]
                )
                
                logger.info(f"FAQ deleted by {user_name}: {faq_info[0][:50]}...")
                
                return jsonify({
                    'success': True,
                    'message': 'FAQ deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete FAQ error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete FAQ'
        }), 500

@app.route('/api/faqs/categories', methods=['GET'])
@admin_required
def get_faq_categories():
    """API endpoint to get available FAQ categories"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get distinct categories from existing FAQs
                cur.execute("""
                    SELECT DISTINCT c.name as category, COUNT(f.id) as faq_count
                    FROM faq_categories c
                    LEFT JOIN faq_items f ON c.id = f.category_id AND COALESCE(f.is_active, true) = true
                    WHERE c.is_active = true
                    GROUP BY c.name
                    ORDER BY c.name
                """)
                
                categories_data = cur.fetchall()
                
                # Format categories
                categories = []
                for cat in categories_data:
                    categories.append({
                        'value': cat['category'],
                        'label': cat['category'].title(),
                        'count': cat['faq_count']
                    })
                
                # Add default categories if they don't exist
                default_categories = [
                    {'value': 'general', 'label': 'General', 'count': 0},
                    {'value': 'forms', 'label': 'Forms', 'count': 0},
                    {'value': 'reports', 'label': 'Reports', 'count': 0},
                    {'value': 'troubleshooting', 'label': 'Troubleshooting', 'count': 0},
                    {'value': 'account', 'label': 'Account', 'count': 0},
                    {'value': 'technical', 'label': 'Technical', 'count': 0}
                ]
                
                # Add default categories that aren't already present
                existing_values = [cat['value'] for cat in categories]
                for default_cat in default_categories:
                    if default_cat['value'] not in existing_values:
                        categories.append(default_cat)
                
                return jsonify({
                    'success': True,
                    'categories': categories
                })
                
    except Exception as e:
        logger.error(f"Get FAQ categories error: {e}")
        return jsonify({
            'success': False,
            'categories': [],
            'message': 'Failed to retrieve FAQ categories'
        }), 500

# Public FAQ Endpoint (No Authentication Required)
@app.route('/api/public/faqs', methods=['GET'])
def get_public_faqs():
    """Public API endpoint to retrieve active FAQs for information page"""
    try:
        # Get filter parameters
        category_filter = request.args.get('category', '').strip()
        search_query = request.args.get('search', '').strip()
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Query to get only active FAQs from faq_items table
                base_query = """
                    SELECT
                        f.id,
                        f.question,
                        f.answer,
                        COALESCE(c.name, 'general') as category,
                        COALESCE(f.sort_order, 0) as display_order,
                        COALESCE(f.is_active, true) as is_active,
                        f.created_at,
                        f.updated_at
                    FROM faq_items f
                    LEFT JOIN faq_categories c ON f.category_id = c.id
                """
                
                where_conditions = ["COALESCE(f.is_active, true) = %s"]
                query_params = [True]
                
                # Filter by category
                if category_filter:
                    where_conditions.append("c.name = %s")
                    query_params.append(category_filter)
                
                # Search in question and answer
                if search_query:
                    where_conditions.append("(f.question ILIKE %s OR f.answer ILIKE %s)")
                    query_params.extend([f"%{search_query}%", f"%{search_query}%"])
                
                # Add WHERE clause
                base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Add ORDER BY clause
                base_query += " ORDER BY COALESCE(f.sort_order, 0) ASC, f.created_at DESC"
                
                cur.execute(base_query, query_params)
                faqs = cur.fetchall()
                
                # Format the data for frontend
                formatted_faqs = []
                for faq in faqs:
                    formatted_faqs.append({
                        'id': str(faq['id']),
                        'question': faq['question'],
                        'answer': faq['answer'],
                        'category': faq['category'],
                        'display_order': faq['display_order']
                    })
                
                return jsonify({
                    'success': True,
                    'faqs': formatted_faqs,
                    'count': len(formatted_faqs)
                })
                
    except psycopg2.Error as db_error:
        logger.error(f"Database error in get_public_faqs: {db_error}")
        # Try fallback to 'faqs' table if 'faq_items' doesn't exist
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    fallback_query = """
                        SELECT
                            id, question, answer, category,
                            COALESCE(display_order, 0) as display_order
                        FROM faqs
                        WHERE is_active = true
                        ORDER BY display_order ASC, created_at DESC
                    """
                    cur.execute(fallback_query)
                    faqs = cur.fetchall()
                    
                    formatted_faqs = []
                    for faq in faqs:
                        formatted_faqs.append({
                            'id': str(faq['id']),
                            'question': faq['question'],
                            'answer': faq['answer'],
                            'category': faq.get('category', 'general'),
                            'display_order': faq['display_order']
                        })
                    
                    return jsonify({
                        'success': True,
                        'faqs': formatted_faqs,
                        'count': len(formatted_faqs)
                    })
        except Exception as fallback_error:
            logger.error(f"Fallback query also failed: {fallback_error}")
            return jsonify({
                'success': False,
                'message': 'Database temporarily unavailable',
                'faqs': []
            }), 503
                
    except Exception as e:
        logger.error(f"Get public FAQs error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve FAQs',
            'faqs': []
        }), 500

# ========================================================
# ANNOUNCEMENTS API ENDPOINTS

@app.route('/api/global-announcements', methods=['GET'])
@login_required
def get_global_announcements():
    """API endpoint to retrieve active global announcements for display on login/dashboard"""
    try:
        logger.info("Global announcements API call for logged-in user")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get only active global announcements that haven't expired
                query = """
                    SELECT
                        id, title, content, announcement_type, priority, icon,
                        color_scheme, author, created_at
                    FROM announcements
                    WHERE is_active = TRUE 
                    AND is_global_announcement = TRUE
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END ASC,
                        created_at DESC
                    LIMIT 10
                """
                
                logger.info("Executing global announcements query")
                cur.execute(query)
                announcements = cur.fetchall()
                
                # Format announcements for frontend
                formatted_announcements = []
                for announcement in announcements:
                    formatted_announcements.append({
                        'id': str(announcement['id']),
                        'title': announcement['title'],
                        'content': announcement['content'],
                        'type': announcement['announcement_type'] or 'info',
                        'priority': announcement['priority'],
                        'icon': announcement['icon'] or 'megaphone',
                        'color_scheme': announcement['color_scheme'] or 'blue',
                        'author': announcement['author'] or 'System',
                        'created_at': announcement['created_at'].strftime('%Y-%m-%d %H:%M:%S') if announcement['created_at'] else '',
                        'display_date': announcement['created_at'].strftime('%B %d, %Y at %I:%M %p') if announcement['created_at'] else 'Unknown'
                    })
                
                logger.info(f"Retrieved {len(formatted_announcements)} global announcements")
                
                return jsonify({
                    'success': True,
                    'announcements': formatted_announcements,
                    'count': len(formatted_announcements)
                })
                
    except Exception as e:
        logger.error(f"Get global announcements error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve global announcements',
            'announcements': [],
            'count': 0
        }), 500
# ========================================================

@app.route('/api/announcements', methods=['GET'])
@admin_required
def get_announcements():
    """API endpoint to retrieve announcements with filtering support"""
    try:
        # Get filter parameters
        status_filter = request.args.get('status', '').strip()
        priority_filter = request.args.get('priority', '').strip()
        search_query = request.args.get('search', '').strip()
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 announcements
        
        logger.info(f"Announcements API call with filters: status={status_filter}, priority={priority_filter}, search={search_query}, limit={limit}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build dynamic query
                base_query = """
                    SELECT
                        id, title, content, announcement_type, priority, icon,
                        color_scheme, is_active, is_featured, author,
                        created_at, updated_at, expires_at, view_count,
                        is_global_announcement
                    FROM announcements
                """
                
                where_conditions = []
                query_params = []
                
                # Filter by active status
                if status_filter:
                    if status_filter == 'active':
                        where_conditions.append("is_active = %s")
                        query_params.append(True)
                    elif status_filter == 'inactive':
                        where_conditions.append("is_active = %s")
                        query_params.append(False)
                    elif status_filter == 'expired':
                        where_conditions.append("expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP")
                    elif status_filter == 'featured':
                        where_conditions.append("is_featured = %s AND is_active = %s")
                        query_params.extend([True, True])
                
                # Filter by priority
                if priority_filter:
                    valid_priorities = ['low', 'medium', 'high', 'critical']
                    if priority_filter in valid_priorities:
                        where_conditions.append("priority = %s")
                        query_params.append(priority_filter)
                
                # Search in title and content
                if search_query:
                    where_conditions.append("(title ILIKE %s OR content ILIKE %s)")
                    query_params.extend([f"%{search_query}%", f"%{search_query}%"])
                
                # Add WHERE clause if there are conditions
                if where_conditions:
                    base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Add ORDER BY clause (featured first, then by priority and creation date)
                base_query += """
                    ORDER BY
                        is_featured DESC,
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END ASC,
                        created_at DESC
                    LIMIT %s
                """
                query_params.append(limit)
                
                logger.info(f"Executing announcements query with {len(query_params)} parameters")
                cur.execute(base_query, query_params)
                announcements = cur.fetchall()
                
                # Format announcements for frontend
                formatted_announcements = []
                for announcement in announcements:
                    # Check if announcement is expired
                    is_expired = False
                    if announcement['expires_at']:
                        is_expired = announcement['expires_at'] < datetime.now()
                    
                    formatted_announcements.append({
                        'id': str(announcement['id']),
                        'title': announcement['title'],
                        'content': announcement['content'],
                        'type': announcement['announcement_type'] or 'info',
                        'priority': announcement['priority'],
                        'icon': announcement['icon'] or 'info',
                        'color_scheme': announcement['color_scheme'] or 'blue',
                        'is_active': announcement['is_active'],
                        'is_featured': announcement['is_featured'],
                        'is_global_announcement': announcement.get('is_global_announcement', False),
                        'is_expired': is_expired,
                        'author': announcement['author'] or 'System',
                        'view_count': announcement['view_count'] or 0,
                        'created_at': announcement['created_at'].strftime('%Y-%m-%d %H:%M:%S') if announcement['created_at'] else '',
                        'updated_at': announcement['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if announcement['updated_at'] else '',
                        'expires_at': announcement['expires_at'].strftime('%Y-%m-%d %H:%M:%S') if announcement['expires_at'] else None,
                        'display_date': announcement['created_at'].strftime('%B %d, %Y at %I:%M %p') if announcement['created_at'] else 'Unknown'
                    })
                
                logger.info(f"Retrieved {len(formatted_announcements)} announcements")
                
                return jsonify({
                    'success': True,
                    'announcements': formatted_announcements,
                    'count': len(formatted_announcements),
                    'total_found': len(formatted_announcements)
                })
                
    except Exception as e:
        logger.error(f"Get announcements error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve announcements',
            'announcements': [],
            'count': 0
        }), 500

@app.route('/api/announcements', methods=['POST'])
@admin_required
def create_announcement():
    """API endpoint to create a new announcement"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            logger.info(f"Create announcement JSON request data: {data}")
        else:
            # Convert form data to dict for consistent handling
            data = request.form.to_dict()
            logger.info(f"Create announcement form request data: {data}")
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['title', 'content', 'priority']
        for field in required_fields:
            if not data.get(field, '').strip():
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Admin User')
        user_email = session.get('email', '')

        # Helper to safely get and strip string-like values from incoming data
        def _safe_str(key, default=''):
            val = data.get(key, default)
            if val is None:
                return default
            return str(val).strip()

        # Helper to parse boolean-like values from multiple possible keys
        def _parse_bool(key, alt_key, default=False):
            val = data.get(key, data.get(alt_key, default))
            if isinstance(val, bool):
                return val
            if val is None:
                return default
            sval = str(val).strip().lower()
            return sval in ('true', '1', 'yes', 'on')

        # Extract and validate data (use safe parsing)
        title = _safe_str('title')
        content = _safe_str('content')
        # Support both 'announcement_type' and legacy 'type' key
        announcement_type = _safe_str('announcement_type', _safe_str('type', 'general')).lower()
        priority = _safe_str('priority').lower()
        icon = _safe_str('icon', 'info').lower()
        color_scheme = _safe_str('color_scheme', 'blue').lower()
        is_active = _parse_bool('active', 'is_active', True)
        is_featured = _parse_bool('featured', 'is_featured', False)
        is_global_announcement = _parse_bool('is_global_announcement', 'global_announcement', False)
        expires_at = _safe_str('expires_at', '')
        
        # Validate field lengths
        if len(title) > 200:
            return jsonify({
                'success': False,
                'message': 'Title must be less than 200 characters'
            }), 400
        
        if len(content) > 1000:
            return jsonify({
                'success': False,
                'message': 'Content must be less than 1000 characters'
            }), 400
        
        # Validate enum values (must match database check constraints)
        valid_types = ['system', 'maintenance', 'feature', 'general']
        valid_priorities = ['low', 'medium', 'high', 'critical']
        valid_colors = ['blue', 'green', 'yellow', 'red', 'purple', 'gray']
        
        if announcement_type not in valid_types:
            return jsonify({
                'success': False,
                'message': f'Invalid announcement type. Must be one of: {", ".join(valid_types)}'
            }), 400
        
        if priority not in valid_priorities:
            return jsonify({
                'success': False,
                'message': f'Invalid priority. Must be one of: {", ".join(valid_priorities)}'
            }), 400
        
        if color_scheme not in valid_colors:
            return jsonify({
                'success': False,
                'message': f'Invalid color scheme. Must be one of: {", ".join(valid_colors)}'
            }), 400
        
        # Parse expiration date if provided
        expires_datetime = None
        if expires_at:
            try:
                expires_datetime = datetime.strptime(expires_at, '%Y-%m-%d %H:%M')
                # Ensure expiration is in the future
                if expires_datetime <= datetime.now():
                    return jsonify({
                        'success': False,
                        'message': 'Expiration date must be in the future'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid expiration date format. Use YYYY-MM-DD HH:MM'
                }), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Insert new announcement
                cur.execute("""
                    INSERT INTO announcements (
                        title, content, announcement_type, priority, icon,
                        color_scheme, is_active, is_featured, is_global_announcement, author,
                        expires_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                """, (
                    title, content, announcement_type, priority, icon,
                    color_scheme, is_active, is_featured, is_global_announcement, user_name,
                    expires_datetime
                ))
                
                announcement_id = cur.fetchone()[0]
                conn.commit()
                
                # Log the creation
                log_submission(
                    user_id, user_name, user_email,
                    'announcement_create',
                    f'Announcement created: {title[:50]}...' if len(title) > 50 else title
                )
                
                logger.info(f"Announcement created by {user_name}: {title}")
                
                return jsonify({
                    'success': True,
                    'message': 'Announcement created successfully',
                    'announcement_id': str(announcement_id)
                })
                
    except Exception as e:
        logger.error(f"Create announcement error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to create announcement'
        }), 500

@app.route('/api/announcements/<announcement_id>', methods=['PUT'])
@admin_required
def update_announcement(announcement_id):
    """API endpoint to update an existing announcement"""
    try:
        data = request.get_json()
        
        logger.info(f"Update announcement {announcement_id} request data: {data}")
        
        # Validate required fields
        required_fields = ['title', 'content', 'priority']
        for field in required_fields:
            if not data.get(field, '').strip():
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Admin User')
        user_email = session.get('email', '')
        
        # Extract and validate data (same validation as create)
        title = data['title'].strip()
        content = data['content'].strip()
        announcement_type = data.get('type', 'general').strip()
        priority = data['priority'].strip()
        icon = data.get('icon', 'info').strip()
        color_scheme = data.get('color_scheme', 'blue').strip()
        is_active = bool(data.get('active', True))
        is_featured = bool(data.get('featured', False))
        is_global_announcement = bool(data.get('is_global_announcement', False))
        expires_at = data.get('expires_at', '').strip()
        
        # Validate field lengths and enum values (same as create)
        if len(title) > 200:
            return jsonify({'success': False, 'message': 'Title must be less than 200 characters'}), 400
        if len(content) > 1000:
            return jsonify({'success': False, 'message': 'Content must be less than 1000 characters'}), 400
        
        # Parse expiration date if provided
        expires_datetime = None
        if expires_at:
            try:
                expires_datetime = datetime.strptime(expires_at, '%Y-%m-%d %H:%M')
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid expiration date format'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if announcement exists
                cur.execute("SELECT id, title FROM announcements WHERE id = %s", (announcement_id,))
                existing = cur.fetchone()
                
                if not existing:
                    return jsonify({
                        'success': False,
                        'message': 'Announcement not found'
                    }), 404
                
                # Update announcement
                cur.execute("""
                    UPDATE announcements SET
                        title = %s, content = %s, announcement_type = %s,
                        priority = %s, icon = %s, color_scheme = %s,
                        is_active = %s, is_featured = %s, is_global_announcement = %s, expires_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    title, content, announcement_type, priority, icon,
                    color_scheme, is_active, is_featured, is_global_announcement, expires_datetime,
                    announcement_id
                ))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to update announcement'
                    }), 500
                
                conn.commit()
                
                # Log the update
                log_submission(
                    user_id, user_name, user_email,
                    'announcement_update',
                    f'Announcement updated: {title[:50]}...' if len(title) > 50 else title
                )
                
                logger.info(f"Announcement updated by {user_name}: {title}")
                
                return jsonify({
                    'success': True,
                    'message': 'Announcement updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Update announcement error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to update announcement'
        }), 500

@app.route('/api/announcements/<announcement_id>', methods=['DELETE'])
@admin_required
def delete_announcement(announcement_id):
    """API endpoint to delete an announcement"""
    try:
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Admin User')
        user_email = session.get('email', '')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get announcement info for logging
                cur.execute("SELECT title FROM announcements WHERE id = %s", (announcement_id,))
                announcement_info = cur.fetchone()
                
                if not announcement_info:
                    return jsonify({
                        'success': False,
                        'message': 'Announcement not found'
                    }), 404
                
                # Delete announcement
                cur.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to delete announcement'
                    }), 500
                
                conn.commit()
                
                # Log the deletion
                log_submission(
                    user_id, user_name, user_email,
                    'announcement_delete',
                    f'Announcement deleted: {announcement_info[0][:50]}...' if len(announcement_info[0]) > 50 else announcement_info[0]
                )
                
                logger.info(f"Announcement deleted by {user_name}: {announcement_info[0][:50]}...")
                
                return jsonify({
                    'success': True,
                    'message': 'Announcement deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete announcement error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete announcement'
        }), 500

@app.route('/api/announcements/<announcement_id>/toggle-global', methods=['POST'])
@admin_required
def toggle_global_announcement(announcement_id):
    """API endpoint to toggle the global announcement status"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Get the desired global status from request
        is_global = bool(data.get('is_global', False))
        
        # Get user information
        user_id = session.get('user_id')
        user_name = session.get('user_full_name', 'Admin User')
        user_email = session.get('email', '')
        
        logger.info(f"Toggle global announcement {announcement_id} to {is_global} by {user_name}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if announcement exists and get current info
                cur.execute("SELECT id, title, is_global_announcement FROM announcements WHERE id = %s", (announcement_id,))
                announcement = cur.fetchone()
                
                if not announcement:
                    return jsonify({
                        'success': False,
                        'message': 'Announcement not found'
                    }), 404
                
                current_global_status = announcement[2] if len(announcement) > 2 else False
                
                # Update the global announcement status
                cur.execute("""
                    UPDATE announcements 
                    SET is_global_announcement = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (is_global, announcement_id))
                
                if cur.rowcount == 0:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to update announcement'
                    }), 500
                
                conn.commit()
                
                # Log the toggle action
                log_submission(
                    user_id, user_name, user_email,
                    'announcement_toggle_global',
                    f'Announcement "{announcement[1]}" global status changed from {current_global_status} to {is_global}'
                )
                
                status_text = "enabled" if is_global else "disabled"
                logger.info(f"Global announcement {status_text} for: {announcement[1]}")
                
                return jsonify({
                    'success': True,
                    'message': f'Global announcement {status_text} successfully',
                    'is_global': is_global
                })
                
    except Exception as e:
        logger.error(f"Toggle global announcement error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to toggle global announcement status'
        }), 500

@app.route('/api/public/announcements', methods=['GET'])
def get_public_announcements():
    """Public API endpoint to retrieve active announcements for public display"""
    try:
        # Get filter parameters
        limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 announcements for public
        
        logger.info(f"Public announcements API call with limit: {limit}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get only active, non-expired announcements
                query = """
                    SELECT
                        id, title, content, announcement_type, priority, icon,
                        color_scheme, is_featured, author, created_at
                    FROM announcements
                    WHERE is_active = TRUE 
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                    ORDER BY
                        is_featured DESC,
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END ASC,
                        created_at DESC
                    LIMIT %s
                """
                
                logger.info(f"Executing public announcements query with limit: {limit}")
                cur.execute(query, (limit,))
                announcements = cur.fetchall()
                
                # Format announcements for frontend
                formatted_announcements = []
                for announcement in announcements:
                    formatted_announcements.append({
                        'id': str(announcement['id']),
                        'title': announcement['title'],
                        'content': announcement['content'],
                        'type': announcement['announcement_type'] or 'info',
                        'priority': announcement['priority'],
                        'icon': announcement['icon'] or 'megaphone',
                        'color_scheme': announcement['color_scheme'] or 'blue',
                        'is_featured': announcement['is_featured'],
                        'author': announcement['author'] or 'System',
                        'created_at': announcement['created_at'].strftime('%Y-%m-%d %H:%M:%S') if announcement['created_at'] else '',
                        'display_date': announcement['created_at'].strftime('%B %d, %Y') if announcement['created_at'] else 'Unknown',
                        'display_time': announcement['created_at'].strftime('%I:%M %p') if announcement['created_at'] else ''
                    })
                
                logger.info(f"Retrieved {len(formatted_announcements)} public announcements")
                
                return jsonify({
                    'success': True,
                    'announcements': formatted_announcements,
                    'count': len(formatted_announcements)
                })
                
    except Exception as e:
        logger.error(f"Get public announcements error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve announcements',
            'announcements': [],
            'count': 0
        }), 500
    


@app.route('/api/support-tickets/count', methods=['GET'])
@admin_required
def get_support_tickets_count():
    """API endpoint to get the count of support tickets by status"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get total count
                cur.execute("""
                    SELECT COUNT(*) as total
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                """)
                total_count = cur.fetchone()['total']
                
                # Get count by status
                cur.execute("""
                    SELECT 
                        status,
                        COUNT(*) as count
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    GROUP BY status
                    ORDER BY status
                """)
                status_counts = cur.fetchall()
                
                # Get count by priority for additional context
                cur.execute("""
                    SELECT 
                        priority,
                        COUNT(*) as count
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    GROUP BY priority
                    ORDER BY 
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                            ELSE 5
                        END
                """)
                priority_counts = cur.fetchall()
                
                # Count open tickets (non-resolved statuses)
                cur.execute("""
                    SELECT COUNT(*) as open_count
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    WHERE st.status IN ('open', 'in_progress', 'waiting')
                """)
                open_count = cur.fetchone()['open_count']
                
                # Count urgent tickets (high priority or critical priority)
                cur.execute("""
                    SELECT COUNT(*) as urgent_count
                    FROM support_tickets st
                    JOIN support_categories sc ON st.category_id = sc.id
                    WHERE st.priority IN ('critical', 'high')
                    AND st.status IN ('open', 'in_progress', 'waiting')
                """)
                urgent_count = cur.fetchone()['urgent_count']
                
                # Format response
                response_data = {
                    'total': total_count,
                    'open': open_count,
                    'urgent': urgent_count,
                    'by_status': {row['status']: row['count'] for row in status_counts},
                    'by_priority': {row['priority']: row['count'] for row in priority_counts}
                }
                
                return jsonify({
                    'status': 'success',
                    'data': response_data
                })
                
    except Exception as e:
        logger.error(f"Support tickets count error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch support tickets count',
            'error': str(e)
        }), 500

# Contact Information Management API Endpoints

@app.route('/api/contact-information', methods=['GET', 'POST'])
@login_required
def manage_contact_information():
    """API endpoint to manage contact information"""
    if request.method == 'GET':
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            id,
                            contact_type,
                            title,
                            value,
                            description,
                            icon,
                            availability,
                            response_time,
                            is_active,
                            is_primary,
                            sort_order,
                            created_at
                        FROM contact_information 
                        ORDER BY sort_order ASC, created_at DESC
                    """)
                    contacts = cur.fetchall()
                    
                    return jsonify({
                        'success': True,
                        'contacts': [dict(contact) for contact in contacts]
                    })
                    
        except Exception as e:
            logger.error(f"Get contacts error: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to fetch contact information'
            }), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['contact_type', 'title', 'value']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({
                        'success': False,
                        'message': f'Missing required field: {field}'
                    }), 400
            
            # Validate contact type constraint
            contact_type = data['contact_type']
            allowed_types = ['phone', 'email', 'chat']
            if contact_type not in allowed_types:
                return jsonify({
                    'success': False,
                    'message': f'Invalid contact type. Allowed types: {", ".join(allowed_types)}'
                }), 400
            
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check if contact type already exists
                    cur.execute("""
                        SELECT COUNT(*) as count 
                        FROM contact_information 
                        WHERE contact_type = %s
                    """, (contact_type,))
                    
                    result = cur.fetchone()
                    if result['count'] > 0:
                        type_names = {
                            'phone': 'Phone Support',
                            'email': 'Email Support',
                            'chat': 'Live Chat'
                        }
                        return jsonify({
                            'success': False,
                            'message': f'{type_names.get(contact_type, contact_type)} contact already exists! Only one contact of each type is allowed.'
                        }), 400
                    
                    # If this is set as primary, unset other primary contacts of same type
                    if data.get('is_primary', False):
                        cur.execute("""
                            UPDATE contact_information 
                            SET is_primary = FALSE 
                            WHERE contact_type = %s
                        """, (data['contact_type'],))
                    
                    cur.execute("""
                        INSERT INTO contact_information 
                        (contact_type, title, value, description, icon, availability, 
                         response_time, is_active, is_primary, sort_order)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        data['contact_type'],
                        data['title'],
                        data['value'],
                        data.get('description', ''),
                        data.get('icon', 'phone'),
                        data.get('availability', ''),
                        data.get('response_time', ''),
                        data.get('is_active', True),
                        data.get('is_primary', False),
                        data.get('sort_order', 0)
                    ))
                    
                    result = cur.fetchone()
                    contact_id = result['id']
                    conn.commit()
                    
                    logger.info(f"Contact information created: {data['title']} ({data['contact_type']})")
                    
                    return jsonify({
                        'success': True,
                        'message': 'Contact information added successfully',
                        'contact_id': contact_id
                    })
                    
        except Exception as e:
            logger.error(f"Create contact error: {e}")
            try:
                logger.error(f"Request data: {data}")
            except:
                logger.error("Request data not available")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return jsonify({
                'success': False,
                'message': f'Failed to add contact information: {str(e)}'
            }), 500

@app.route('/api/contact-information/<int:contact_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def manage_single_contact(contact_id):
    """API endpoint to manage individual contact information"""
    if request.method == 'GET':
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            id,
                            contact_type,
                            title,
                            value,
                            description,
                            icon,
                            availability,
                            response_time,
                            is_active,
                            is_primary,
                            sort_order,
                            created_at
                        FROM contact_information 
                        WHERE id = %s
                    """, (contact_id,))
                    
                    contact = cur.fetchone()
                    if not contact:
                        return jsonify({
                            'success': False,
                            'message': 'Contact information not found'
                        }), 404
                    
                    return jsonify({
                        'success': True,
                        'contact': dict(contact)
                    })
                    
        except Exception as e:
            logger.error(f"Get contact error: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to fetch contact information'
            }), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['contact_type', 'title', 'value']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({
                        'success': False,
                        'message': f'Missing required field: {field}'
                    }), 400
            
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check if contact exists
                    cur.execute("SELECT id FROM contact_information WHERE id = %s", (contact_id,))
                    if not cur.fetchone():
                        return jsonify({
                            'success': False,
                            'message': 'Contact information not found'
                        }), 404
                    
                    # If this is set as primary, unset other primary contacts of same type
                    if data.get('is_primary', False):
                        cur.execute("""
                            UPDATE contact_information 
                            SET is_primary = FALSE 
                            WHERE contact_type = %s AND id != %s
                        """, (data['contact_type'], contact_id))
                    
                    cur.execute("""
                        UPDATE contact_information 
                        SET contact_type = %s,
                            title = %s,
                            value = %s,
                            description = %s,
                            icon = %s,
                            availability = %s,
                            response_time = %s,
                            is_active = %s,
                            is_primary = %s,
                            sort_order = %s
                        WHERE id = %s
                    """, (
                        data['contact_type'],
                        data['title'],
                        data['value'],
                        data.get('description', ''),
                        data.get('icon', 'phone'),
                        data.get('availability', ''),
                        data.get('response_time', ''),
                        data.get('is_active', True),
                        data.get('is_primary', False),
                        data.get('sort_order', 0),
                        contact_id
                    ))
                    
                    conn.commit()
                    
                    logger.info(f"Contact information updated: {data['title']} ({data['contact_type']})")
                    
                    return jsonify({
                        'success': True,
                        'message': 'Contact information updated successfully'
                    })
                    
        except Exception as e:
            logger.error(f"Update contact error: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to update contact information'
            }), 500
    
    elif request.method == 'DELETE':
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check if contact exists
                    cur.execute("SELECT title, contact_type FROM contact_information WHERE id = %s", (contact_id,))
                    contact = cur.fetchone()
                    if not contact:
                        return jsonify({
                            'success': False,
                            'message': 'Contact information not found'
                        }), 404
                    
                    cur.execute("DELETE FROM contact_information WHERE id = %s", (contact_id,))
                    conn.commit()
                    
                    logger.info(f"Contact information deleted: {contact['title']} ({contact['contact_type']})")
                    
                    return jsonify({
                        'success': True,
                        'message': 'Contact information deleted successfully'
                    })
                    
        except Exception as e:
            logger.error(f"Delete contact error: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to delete contact information'
            }), 500

@app.route('/api/contact-information/stats', methods=['GET'])
@login_required
def get_contact_stats():
    """API endpoint to get contact information statistics"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get total count
                cur.execute("SELECT COUNT(*) as total FROM contact_information")
                total = cur.fetchone()['total']
                
                # Get counts by type
                cur.execute("""
                    SELECT 
                        contact_type,
                        COUNT(*) as count
                    FROM contact_information 
                    GROUP BY contact_type
                """)
                type_counts = cur.fetchall()
                
                stats = {
                    'total': total,
                    'phone': 0,
                    'email': 0,
                    'chat': 0
                }
                
                for type_count in type_counts:
                    stats[type_count['contact_type']] = type_count['count']
                
                return jsonify({
                    'success': True,
                    'stats': stats
                })
                
    except Exception as e:
        logger.error(f"Get contact stats error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch contact statistics'
        }), 500

@app.route('/api/public/contact-information', methods=['GET'])
def get_public_contact_info():
    """Public API endpoint to get active contact information for the info page"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        contact_type,
                        title,
                        value,
                        description,
                        icon,
                        availability,
                        response_time,
                        is_primary,
                        sort_order
                    FROM contact_information 
                    WHERE is_active = TRUE
                    ORDER BY sort_order ASC, is_primary DESC, created_at DESC
                """)
                contacts = cur.fetchall()
                
                return jsonify({
                    'success': True,
                    'contacts': [dict(contact) for contact in contacts]
                })
                
    except Exception as e:
        logger.error(f"Get public contact info error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch contact information',
            'error': str(e)
        }), 500

# ========================================================
# LEGAL DOCUMENTS API ENDPOINTS
# ========================================================

@app.route('/api/legal-documents/<document_type>', methods=['GET'])
def get_legal_document(document_type):
    """Get active legal document by type"""
    try:
        # Validate document type
        valid_types = ['privacy', 'terms', 'cookie', 'security', 'compliance']
        if document_type not in valid_types:
            return jsonify({
                'success': False,
                'message': 'Invalid document type'
            }), 400
        
        # Map document type to table name
        table_mapping = {
            'privacy': 'privacy_policy',
            'terms': 'terms_of_service',
            'cookie': 'cookie_policy',
            'security': 'security_policy',
            'compliance': 'compliance_policy'
        }
        
        table_name = table_mapping[document_type]
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT 
                        id,
                        version,
                        title,
                        content,
                        effective_date,
                        is_active,
                        created_at,
                        updated_at
                    FROM {table_name}
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                document = cur.fetchone()
                
                if document:
                    return jsonify({
                        'success': True,
                        'id': str(document['id']),
                        'version': document['version'],
                        'title': document['title'],
                        'content': document['content'],
                        'effective_date': document['effective_date'].isoformat() if document['effective_date'] else None,
                        'is_active': document['is_active'],
                        'created_at': document['created_at'].isoformat() if document['created_at'] else None,
                        'updated_at': document['updated_at'].isoformat() if document['updated_at'] else None
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': f'No active {document_type} document found'
                    }), 404
                
    except Exception as e:
        logger.error(f"Get legal document error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch legal document',
            'error': str(e)
        }), 500

@app.route('/api/legal-documents/<document_type>', methods=['POST'])
@login_required
def update_legal_document(document_type):
    """Update legal document (admin only)"""
    try:
        # Check if user is admin
        if session.get('user_role') != 'admin':
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        # Validate document type
        valid_types = ['privacy', 'terms', 'cookie', 'security', 'compliance']
        if document_type not in valid_types:
            return jsonify({
                'success': False,
                'message': 'Invalid document type'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['version', 'title', 'content', 'effective_date']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Map document type to table name
        table_mapping = {
            'privacy': 'privacy_policy',
            'terms': 'terms_of_service',
            'cookie': 'cookie_policy',
            'security': 'security_policy',
            'compliance': 'compliance_policy'
        }
        
        table_name = table_mapping[document_type]
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Deactivate current active version
                cur.execute(f"""
                    UPDATE {table_name} 
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE is_active = TRUE
                """)
                
                # Insert new version (always create a new record)
                cur.execute(f"""
                    INSERT INTO {table_name} 
                    (version, title, content, effective_date, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id, version, title, content, effective_date, is_active, created_at, updated_at
                """, (
                    data['version'],
                    data['title'],
                    data['content'],
                    data['effective_date']
                ))
                
                new_document = cur.fetchone()
                conn.commit()
                
                # Log the update
                user_name = session.get('user_name', 'Unknown')
                logger.info(f"Legal document updated by {user_name}: {document_type} v{data['version']}")
                
                return jsonify({
                    'success': True,
                    'message': f'{document_type.title()} document updated successfully',
                    'id': str(new_document['id']),
                    'version': new_document['version'],
                    'title': new_document['title'],
                    'content': new_document['content'],
                    'effective_date': new_document['effective_date'].isoformat() if new_document['effective_date'] else None,
                    'is_active': new_document['is_active'],
                    'created_at': new_document['created_at'].isoformat() if new_document['created_at'] else None,
                    'updated_at': new_document['updated_at'].isoformat() if new_document['updated_at'] else None
                })
                
    except Exception as e:
        logger.error(f"Update legal document error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to update legal document',
            'error': str(e)
        }), 500

@app.route('/api/legal-documents', methods=['GET'])
def get_all_legal_documents():
    """Get all active legal documents"""
    try:
        documents = {}
        
        # Document types and their table mappings
        table_mapping = {
            'privacy': 'privacy_policy',
            'terms': 'terms_of_service',
            'cookie': 'cookie_policy',
            'security': 'security_policy',
            'compliance': 'compliance_policy'
        }
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for doc_type, table_name in table_mapping.items():
                    cur.execute(f"""
                        SELECT 
                            id,
                            version,
                            title,
                            content,
                            effective_date,
                            is_active,
                            created_at,
                            updated_at
                        FROM {table_name}
                        WHERE is_active = TRUE
                        ORDER BY created_at DESC
                        LIMIT 1
                    """)
                    
                    document = cur.fetchone()
                    
                    if document:
                        documents[doc_type] = {
                            'id': str(document['id']),
                            'version': document['version'],
                            'title': document['title'],
                            'content': document['content'],
                            'effective_date': document['effective_date'].isoformat() if document['effective_date'] else None,
                            'is_active': document['is_active'],
                            'created_at': document['created_at'].isoformat() if document['created_at'] else None,
                            'updated_at': document['updated_at'].isoformat() if document['updated_at'] else None
                        }
                    else:
                        documents[doc_type] = None
        
        return jsonify({
            'success': True,
            'documents': documents
        })
                
    except Exception as e:
        logger.error(f"Get all legal documents error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch legal documents',
            'error': str(e)
        }), 500

@app.route('/api/legal-documents/next-version', methods=['GET'])
@login_required
def get_next_version():
    """Get the next version number for legal documents (admin only)"""
    try:
        # Check if user is admin
        if session.get('user_role') != 'admin':
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        document_types = ['privacy', 'terms', 'cookie', 'security', 'compliance']
        table_mapping = {
            'privacy': 'privacy_policy',
            'terms': 'terms_of_service',
            'cookie': 'cookie_policy',
            'security': 'security_policy',
            'compliance': 'compliance_policy'
        }
        
        max_version = 0.0
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for doc_type in document_types:
                    table_name = table_mapping[doc_type]
                    cur.execute(f"""
                        SELECT MAX(CAST(version AS FLOAT)) as max_version
                        FROM {table_name}
                        WHERE version ~ '^[0-9]+(\\.[0-9]+)?$'
                    """)
                    
                    result = cur.fetchone()
                    if result and result['max_version']:
                        table_max = float(result['max_version'])
                        if table_max > max_version:
                            max_version = table_max
                
                # Increment by 0.1 and format to one decimal place
                next_version = f"{max_version + 0.1:.1f}"
                
                return jsonify({
                    'success': True,
                    'next_version': next_version,
                    'current_max': f"{max_version:.1f}"
                })
                
    except Exception as e:
        logger.error(f"Get next version error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get next version',
            'error': str(e)
        }), 500

@app.route('/api/legal-documents/<document_type>/history', methods=['GET'])
@login_required
def get_legal_document_history(document_type):
    """Get version history for a legal document (admin only)"""
    try:
        # Check if user is admin
        if session.get('user_role') != 'admin':
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        # Validate document type
        valid_types = ['privacy', 'terms', 'cookie', 'security', 'compliance']
        if document_type not in valid_types:
            return jsonify({
                'success': False,
                'message': 'Invalid document type'
            }), 400
        
        # Map document type to table name
        table_mapping = {
            'privacy': 'privacy_policy',
            'terms': 'terms_of_service',
            'cookie': 'cookie_policy',
            'security': 'security_policy',
            'compliance': 'compliance_policy'
        }
        
        table_name = table_mapping[document_type]
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT 
                        id,
                        version,
                        title,
                        effective_date,
                        is_active,
                        created_at,
                        updated_at,
                        LENGTH(content) as content_length
                    FROM {table_name}
                    ORDER BY created_at DESC
                """)
                
                history = cur.fetchall()
                
                return jsonify({
                    'success': True,
                    'history': [{
                        'id': str(doc['id']),
                        'version': doc['version'],
                        'title': doc['title'],
                        'effective_date': doc['effective_date'].isoformat() if doc['effective_date'] else None,
                        'is_active': doc['is_active'],
                        'created_at': doc['created_at'].isoformat() if doc['created_at'] else None,
                        'updated_at': doc['updated_at'].isoformat() if doc['updated_at'] else None,
                        'content_length': doc['content_length']
                    } for doc in history]
                })
                
    except Exception as e:
        logger.error(f"Get legal document history error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch document history',
            'error': str(e)
        }), 500


# ========================================================
# LEGAL DOCUMENTS PAGES
# ========================================================

@app.route('/privacy-policy')
def privacy_policy():
    """Display privacy policy page"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        version,
                        title,
                        content,
                        effective_date,
                        created_at,
                        updated_at
                    FROM privacy_policy
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                document = cur.fetchone()
                
                if document:
                    return render_template('legal_document.html', 
                                         document=document, 
                                         document_type='Privacy Policy')
                else:
                    return render_template('legal_document.html', 
                                         document=None, 
                                         document_type='Privacy Policy',
                                         error='Privacy Policy not found')
                
    except Exception as e:
        logger.error(f"Privacy policy page error: {e}")
        return render_template('legal_document.html', 
                             document=None, 
                             document_type='Privacy Policy',
                             error='Failed to load Privacy Policy')

@app.route('/terms-of-service')
def terms_of_service():
    """Display terms of service page"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        version,
                        title,
                        content,
                        effective_date,
                        created_at,
                        updated_at
                    FROM terms_of_service
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                document = cur.fetchone()
                
                if document:
                    return render_template('legal_document.html', 
                                         document=document, 
                                         document_type='Terms of Service')
                else:
                    return render_template('legal_document.html', 
                                         document=None, 
                                         document_type='Terms of Service',
                                         error='Terms of Service not found')
                
    except Exception as e:
        logger.error(f"Terms of service page error: {e}")
        return render_template('legal_document.html', 
                             document=None, 
                             document_type='Terms of Service',
                             error='Failed to load Terms of Service')

@app.route('/cookie-policy')
def cookie_policy():
    """Display cookie policy page"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        version,
                        title,
                        content,
                        effective_date,
                        created_at,
                        updated_at
                    FROM cookie_policy
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                document = cur.fetchone()
                
                if document:
                    return render_template('legal_document.html', 
                                         document=document, 
                                         document_type='Cookie Policy')
                else:
                    return render_template('legal_document.html', 
                                         document=None, 
                                         document_type='Cookie Policy',
                                         error='Cookie Policy not found')
                
    except Exception as e:
        logger.error(f"Cookie policy page error: {e}")
        return render_template('legal_document.html', 
                             document=None, 
                             document_type='Cookie Policy',
                             error='Failed to load Cookie Policy')

@app.route('/security-policy')
def security_policy():
    """Display security policy page"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        version,
                        title,
                        content,
                        effective_date,
                        created_at,
                        updated_at
                    FROM security_policy
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                document = cur.fetchone()
                
                if document:
                    return render_template('legal_document.html', 
                                         document=document, 
                                         document_type='Security Policy')
                else:
                    return render_template('legal_document.html', 
                                         document=None, 
                                         document_type='Security Policy',
                                         error='Security Policy not found')
                
    except Exception as e:
        logger.error(f"Security policy page error: {e}")
        return render_template('legal_document.html', 
                             document=None, 
                             document_type='Security Policy',
                             error='Failed to load Security Policy')
    


@app.route('/line-tool-demo')
def line_tool_demo():
    """Demo page for the new line tool"""
    return render_template('line_tool_demo.html')



@app.route('/compliance-policy')
def compliance_policy():
    """Display compliance policy page"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        version,
                        title,
                        content,
                        effective_date,
                        created_at,
                        updated_at
                    FROM compliance_policy
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                document = cur.fetchone()
                
                if document:
                    return render_template('legal_document.html', 
                                         document=document, 
                                         document_type='Compliance Policy')
                else:
                    return render_template('legal_document.html', 
                                         document=None, 
                                         document_type='Compliance Policy',
                                         error='Compliance Policy not found')
                
    except Exception as e:
        logger.error(f"Compliance policy page error: {e}")
        return render_template('legal_document.html', 
                             document=None, 
                             document_type='Compliance Policy',
                             error='Failed to load Compliance Policy')


@app.route('/api/user-status')
@login_required
def get_user_status():
    """API endpoint to check if user needs to change password (client-side fallback)"""
    user_id = session.get('user_id')
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if password_change_required column exists
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'password_change_required'
                """)
                column_exists = cur.fetchone()
                
                if column_exists:
                    # Column exists, check if password change is required
                    cur.execute("""
                        SELECT password_change_required 
                        FROM users 
                        WHERE id = %s
                    """, (user_id,))
                    user = cur.fetchone()
                    
                    return jsonify({
                        'success': True,
                        'password_change_required': user.get('password_change_required', False) if user else False,
                        'user_id': user_id
                    })
                else:
                    # Column doesn't exist yet
                    return jsonify({
                        'success': True,
                        'password_change_required': False,
                        'user_id': user_id
                    })
                    
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
        return jsonify({
            'success': False,
            'message': 'Error checking user status'
        }), 500


@app.route('/api/week-average', methods=['GET'])
@login_required
@password_change_required
def get_week_average():
    """API endpoint to calculate and return weekly averages for OEE, Volume, and Waste"""
    try:
        week = request.args.get('week')
        
        if not week:
            return jsonify({"error": "Week parameter is required"}), 400

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get weekly sheet ID
                cur.execute("""
                    SELECT id, week_start, week_end FROM weekly_sheets WHERE sheet_name = %s
                """, (week,))
                
                sheet_result = cur.fetchone()
                if not sheet_result:
                    return jsonify({"error": "Week sheet not found"}), 404

                weekly_sheet_id = sheet_result['id']
                
                # Get week submissions for this week
                cur.execute("""
                    SELECT id, day_of_week FROM week_submissions 
                    WHERE week_name = %s 
                    AND day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')
                """, (week,))
                
                week_submissions = cur.fetchall()
                
                if not week_submissions:
                    return jsonify({
                        "success": False,
                        "error": "No data found for the selected week"
                    }), 404
                
                submission_ids = [sub['id'] for sub in week_submissions]
                submission_ids_placeholder = ','.join(['%s'] * len(submission_ids))
                
                # Get first shift metrics
                cur.execute(f"""
                    SELECT 
                        die_cut1_oee_pct, die_cut2_oee_pct, oee_avg_pct,
                        die_cut1_lbs, die_cut2_lbs, pounds_total,
                        die_cut1_waste_lb, die_cut2_waste_lb,
                        die_cut1_waste_pct, die_cut2_waste_pct, waste_avg_pct
                    FROM first_shift_metrics
                    WHERE week_submission_id IN ({submission_ids_placeholder})
                    AND die_cut1_oee_pct IS NOT NULL
                """, submission_ids)
                
                first_shift_data = cur.fetchall()
                
                # Get second shift metrics
                cur.execute(f"""
                    SELECT 
                        die_cut1_oee_pct, die_cut2_oee_pct, oee_avg_pct,
                        die_cut1_lbs, die_cut2_lbs, pounds_total,
                        die_cut1_waste_lb, die_cut2_waste_lb,
                        die_cut1_waste_pct, die_cut2_waste_pct, waste_avg_pct
                    FROM second_shift_metrics
                    WHERE week_submission_id IN ({submission_ids_placeholder})
                    AND die_cut1_oee_pct IS NOT NULL
                """, submission_ids)
                
                second_shift_data = cur.fetchall()
                
                # Get both shifts metrics (combined data)
                cur.execute(f"""
                    SELECT 
                        oee_avg_pct,
                        pounds_total,
                        die_cut1_waste_lb,
                        die_cut2_waste_lb
                    FROM both_shifts_metrics
                    WHERE week_submission_id IN ({submission_ids_placeholder})
                    AND oee_avg_pct IS NOT NULL
                """, submission_ids)
                
                both_shifts_data = cur.fetchall()
                
                # Calculate averages and totals
                def safe_avg(values):
                    filtered = [v for v in values if v is not None]
                    return sum(filtered) / len(filtered) if filtered else 0
                
                def safe_total(values):
                    filtered = [v for v in values if v is not None]
                    return sum(filtered) if filtered else 0
                
                # FIRST SHIFT CALCULATIONS
                # Die Cut 1 - First Shift
                first_dc1_oee_avg = safe_avg([row['die_cut1_oee_pct'] for row in first_shift_data])
                first_dc1_volume_total = safe_total([row['die_cut1_lbs'] for row in first_shift_data])
                first_dc1_waste_total = safe_total([row['die_cut1_waste_lb'] for row in first_shift_data])
                
                # Die Cut 2 - First Shift
                first_dc2_oee_avg = safe_avg([row['die_cut2_oee_pct'] for row in first_shift_data])
                first_dc2_volume_total = safe_total([row['die_cut2_lbs'] for row in first_shift_data])
                first_dc2_waste_total = safe_total([row['die_cut2_waste_lb'] for row in first_shift_data])
                
                # Total - First Shift
                first_total_oee_avg = safe_avg([row['oee_avg_pct'] for row in first_shift_data])
                first_total_volume_total = safe_total([row['pounds_total'] for row in first_shift_data])
                first_total_waste_total = first_dc1_waste_total + first_dc2_waste_total
                
                # SECOND SHIFT CALCULATIONS
                # Die Cut 1 - Second Shift
                second_dc1_oee_avg = safe_avg([row['die_cut1_oee_pct'] for row in second_shift_data])
                second_dc1_volume_total = safe_total([row['die_cut1_lbs'] for row in second_shift_data])
                second_dc1_waste_total = safe_total([row['die_cut1_waste_lb'] for row in second_shift_data])
                
                # Die Cut 2 - Second Shift
                second_dc2_oee_avg = safe_avg([row['die_cut2_oee_pct'] for row in second_shift_data])
                second_dc2_volume_total = safe_total([row['die_cut2_lbs'] for row in second_shift_data])
                second_dc2_waste_total = safe_total([row['die_cut2_waste_lb'] for row in second_shift_data])
                
                # Total - Second Shift
                second_total_oee_avg = safe_avg([row['oee_avg_pct'] for row in second_shift_data])
                second_total_volume_total = safe_total([row['pounds_total'] for row in second_shift_data])
                second_total_waste_total = second_dc1_waste_total + second_dc2_waste_total
                
                # BOTH SHIFTS CALCULATIONS
                # Die Cut 1 - Both Shifts (combine first and second shift data)
                both_dc1_oee_avg = safe_avg([row['die_cut1_oee_pct'] for row in first_shift_data + second_shift_data])
                both_dc1_volume_total = first_dc1_volume_total + second_dc1_volume_total
                both_dc1_waste_total = first_dc1_waste_total + second_dc1_waste_total
                
                # Die Cut 2 - Both Shifts
                both_dc2_oee_avg = safe_avg([row['die_cut2_oee_pct'] for row in first_shift_data + second_shift_data])
                both_dc2_volume_total = first_dc2_volume_total + second_dc2_volume_total
                both_dc2_waste_total = first_dc2_waste_total + second_dc2_waste_total
                
                # Total - Both Shifts
                both_total_oee_avg = safe_avg([row['oee_avg_pct'] for row in both_shifts_data])
                both_total_volume_total = safe_total([row['pounds_total'] for row in both_shifts_data])
                both_total_waste_total = both_dc1_waste_total + both_dc2_waste_total
                
                # Format response data with separate Die Cut calculations
                response = {
                    "success": True,
                    "week": week,
                    "period": f"{sheet_result['week_start']} to {sheet_result['week_end']}",
                    "averages": {
                        "oee": {
                            "die_cut_1": {
                                "first_shift": round(first_dc1_oee_avg, 1) if first_dc1_oee_avg > 0 else 0,
                                "second_shift": round(second_dc1_oee_avg, 1) if second_dc1_oee_avg > 0 else 0,
                                "both_shifts": round(both_dc1_oee_avg, 1) if both_dc1_oee_avg > 0 else 0
                            },
                            "die_cut_2": {
                                "first_shift": round(first_dc2_oee_avg, 1) if first_dc2_oee_avg > 0 else 0,
                                "second_shift": round(second_dc2_oee_avg, 1) if second_dc2_oee_avg > 0 else 0,
                                "both_shifts": round(both_dc2_oee_avg, 1) if both_dc2_oee_avg > 0 else 0
                            },
                            "total": {
                                "first_shift": round(first_total_oee_avg, 1) if first_total_oee_avg > 0 else 0,
                                "second_shift": round(second_total_oee_avg, 1) if second_total_oee_avg > 0 else 0,
                                "both_shifts": round(both_total_oee_avg, 1) if both_total_oee_avg > 0 else 0
                            }
                        },
                        "volume": {
                            "die_cut_1": {
                                "first_shift": round(first_dc1_volume_total, 0) if first_dc1_volume_total > 0 else 0,
                                "second_shift": round(second_dc1_volume_total, 0) if second_dc1_volume_total > 0 else 0,
                                "both_shifts": round(both_dc1_volume_total, 0) if both_dc1_volume_total > 0 else 0
                            },
                            "die_cut_2": {
                                "first_shift": round(first_dc2_volume_total, 0) if first_dc2_volume_total > 0 else 0,
                                "second_shift": round(second_dc2_volume_total, 0) if second_dc2_volume_total > 0 else 0,
                                "both_shifts": round(both_dc2_volume_total, 0) if both_dc2_volume_total > 0 else 0
                            },
                            "total": {
                                "first_shift": round(first_total_volume_total, 0) if first_total_volume_total > 0 else 0,
                                "second_shift": round(second_total_volume_total, 0) if second_total_volume_total > 0 else 0,
                                "both_shifts": round(both_total_volume_total, 0) if both_total_volume_total > 0 else 0
                            }
                        },
                        "waste": {
                            "pounds": {
                                "die_cut_1": {
                                    "first_shift": round(first_dc1_waste_total, 1) if first_dc1_waste_total > 0 else 0,
                                    "second_shift": round(second_dc1_waste_total, 1) if second_dc1_waste_total > 0 else 0,
                                    "both_shifts": round(both_dc1_waste_total, 1) if both_dc1_waste_total > 0 else 0
                                },
                                "die_cut_2": {
                                    "first_shift": round(first_dc2_waste_total, 1) if first_dc2_waste_total > 0 else 0,
                                    "second_shift": round(second_dc2_waste_total, 1) if second_dc2_waste_total > 0 else 0,
                                    "both_shifts": round(both_dc2_waste_total, 1) if both_dc2_waste_total > 0 else 0
                                },
                                "total": {
                                    "first_shift": round(first_total_waste_total, 1) if first_total_waste_total > 0 else 0,
                                    "second_shift": round(second_total_waste_total, 1) if second_total_waste_total > 0 else 0,
                                    "both_shifts": round(both_total_waste_total, 1) if both_total_waste_total > 0 else 0
                                }
                            },
                            "percentage": {
                                "die_cut_1": {
                                    "first_shift": round((first_dc1_waste_total / first_dc1_volume_total * 100), 1) if first_dc1_volume_total > 0 else 0,
                                    "second_shift": round((second_dc1_waste_total / second_dc1_volume_total * 100), 1) if second_dc1_volume_total > 0 else 0,
                                    "both_shifts": round((both_dc1_waste_total / both_dc1_volume_total * 100), 1) if both_dc1_volume_total > 0 else 0
                                },
                                "die_cut_2": {
                                    "first_shift": round((first_dc2_waste_total / first_dc2_volume_total * 100), 1) if first_dc2_volume_total > 0 else 0,
                                    "second_shift": round((second_dc2_waste_total / second_dc2_volume_total * 100), 1) if second_dc2_volume_total > 0 else 0,
                                    "both_shifts": round((both_dc2_waste_total / both_dc2_volume_total * 100), 1) if both_dc2_volume_total > 0 else 0
                                },
                                "total": {
                                    "first_shift": round((first_total_waste_total / first_total_volume_total * 100), 1) if first_total_volume_total > 0 else 0,
                                    "second_shift": round((second_total_waste_total / second_total_volume_total * 100), 1) if second_total_volume_total > 0 else 0,
                                    "both_shifts": round((both_total_waste_total / both_total_volume_total * 100), 1) if both_total_volume_total > 0 else 0
                                }
                            }
                        }
                    },
                    "data_points": {
                        "first_shift_count": len(first_shift_data),
                        "second_shift_count": len(second_shift_data),
                        "both_shifts_count": len(both_shifts_data),
                        "week_submissions": len(week_submissions)
                    }
                }
                
                logger.info(f"Week average calculated for {week}: {response['averages']}")
                return jsonify(response)

    except Exception as e:
        logger.error(f"Week average calculation error: {e}")
        return jsonify({
            "success": False,
            "error": f"Failed to calculate week average: {str(e)}"
        }), 500


# ==================== EMPLOYEE MANAGEMENT API ====================

@app.route('/api/employees', methods=['GET'])
@login_required
def get_employees():
    """Get all employees"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Use lowercase column names as they exist in the database
                cur.execute("""
                    SELECT 
                        e.id,
                        e.firstname,
                        e.lastname,
                        e.email,
                        e.phonenumber,
                        e.department,
                        e.role,
                        e.shift,
                        e.workline,
                        e.workarea,
                        e.supervisor,
                        e.manager,
                        e.user_id,
                        e.created_at,
                        e.updated_at,
                        u.first_name as user_first_name,
                        u.last_name as user_last_name,
                        u.email as user_email,
                        e.date_of_employment,
                        e.allocated_vacation_hours,
                        e.max_accumulated_hours,
                        e.years_of_employment,
                        e.months_of_employment,
                        e.vacation_schedule_years,
                        e.vacation_schedule_hours
                    FROM employees e
                    LEFT JOIN users u ON e.user_id = u.id
                    ORDER BY e.created_at DESC
                """)
                
                employees = []
                for row in cur.fetchall():
                    employees.append({
                        'id': row[0],
                        'firstname': row[1],
                        'lastname': row[2],
                        'email': row[3],
                        'phonenumber': row[4],
                        'department': row[5],
                        'role': row[6],
                        'shift': row[7],
                        'workline': row[8],
                        'workarea': row[9],
                        'supervisor': row[10],
                        'manager': row[11],
                        'user_id': str(row[12]) if row[12] else None,
                        'createdAt': row[13].isoformat() if row[13] else None,
                        'updatedAt': row[14].isoformat() if row[14] else None,
                        'userFirstName': row[15],
                        'userLastName': row[16],
                        'userEmail': row[17],
                        'dateOfEmployment': row[18].isoformat() if row[18] else None,
                        'vacationHours': float(row[19]) if row[19] is not None else 0,
                        'maxAccumulatedHours': float(row[20]) if row[20] is not None else None,
                        'yearsOfEmployment': row[21] if row[21] is not None else 0,
                        'monthsOfEmployment': row[22] if row[22] is not None else 0,
                        'vacationScheduleYears': list(row[23]) if row[23] else [],
                        'vacationScheduleHours': list(row[24]) if row[24] else []
                    })
        
        return jsonify({
            'success': True,
            'employees': employees
        })
        
    except Exception as e:
        logger.error(f"Get employees error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/employees/<int:employee_id>', methods=['GET'])
@login_required
def get_employee(employee_id):
    """Get single employee by ID"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Use lowercase column names as they exist in the database
                cur.execute("""
                    SELECT 
                        e.id,
                        e.firstname,
                        e.lastname,
                        e.email,
                        e.phonenumber,
                        e.department,
                        e.role,
                        e.shift,
                        e.workline,
                        e.workarea,
                        e.supervisor,
                        e.manager,
                        e.user_id,
                        e.created_at,
                        e.updated_at,
                        u.first_name as user_first_name,
                        u.last_name as user_last_name,
                        u.email as user_email,
                        e.date_of_employment,
                        e.allocated_vacation_hours,
                        e.max_accumulated_hours,
                        e.years_of_employment,
                        e.months_of_employment,
                        e.vacation_schedule_years,
                        e.vacation_schedule_hours
                    FROM employees e
                    LEFT JOIN users u ON e.user_id = u.id
                    WHERE e.id = %s
                """, (employee_id,))
                
                row = cur.fetchone()
                
                if not row:
                    return jsonify({
                        'success': False,
                        'message': 'Employee not found'
                    }), 404
                
                employee = {
                    'id': row[0],
                    'firstname': row[1],
                    'lastname': row[2],
                    'email': row[3],
                    'phonenumber': row[4],
                    'department': row[5],
                    'role': row[6],
                    'shift': row[7],
                    'workline': row[8],
                    'workarea': row[9],
                    'supervisor': row[10],
                    'manager': row[11],
                    'user_id': str(row[12]) if row[12] else None,
                    'createdAt': row[13].isoformat() if row[13] else None,
                    'updatedAt': row[14].isoformat() if row[14] else None,
                    'userFirstName': row[15],
                    'userLastName': row[16],
                    'userEmail': row[17],
                    'date_of_employment': row[18].isoformat() if row[18] else None,
                    'vacation_hours': float(row[19]) if row[19] else None,
                    'max_accumulated_hours': float(row[20]) if row[20] else None,
                    'years_of_employment': row[21] if row[21] is not None else 0,
                    'months_of_employment': row[22] if row[22] is not None else 0,
                    'vacation_schedule_years': list(row[23]) if row[23] else [],
                    'vacation_schedule_hours': list(row[24]) if row[24] else []
                }
        
        return jsonify({
            'success': True,
            'employee': employee
        })
        
    except Exception as e:
        logger.error(f"Get employee error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/employees', methods=['POST'])
@login_required
def create_employee():
    """Create a new employee"""
    try:
        data = request.get_json()
        
        # Validate required fields (support both camelCase from frontend)
        firstname = data.get('firstname') or data.get('firstName')
        lastname = data.get('lastname') or data.get('lastName')
        
        if not firstname or not lastname:
            return jsonify({
                'success': False,
                'message': 'First name and last name are required'
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Convert user_id to UUID if provided
                user_id = data.get('user_id') or data.get('userId') or None
                
                # Get supervisor and manager names from frontend
                supervisor_name = data.get('supervisor')
                manager_name = data.get('manager')
                
                logger.info(f"CREATE EMPLOYEE: Received supervisor='{supervisor_name}', manager='{manager_name}'")
                
                # Lookup supervisor_id and manager_id UUIDs from users table
                supervisor_id = None
                manager_id = None
                
                if supervisor_name:
                    # Try to find user by email or full name matching supervisor name
                    cur.execute("""
                        SELECT id FROM users 
                        WHERE email = %s OR CONCAT(first_name, ' ', last_name) = %s
                        LIMIT 1
                    """, (supervisor_name, supervisor_name))
                    supervisor_result = cur.fetchone()
                    if supervisor_result:
                        supervisor_id = supervisor_result[0]
                        logger.info(f"CREATE: Found supervisor UUID {supervisor_id} for name '{supervisor_name}'")
                    else:
                        logger.warning(f"CREATE: Could not find supervisor user for name '{supervisor_name}'")
                        # Show what supervisor users exist
                        cur.execute("""
                            SELECT id, email, CONCAT(first_name, ' ', last_name) as full_name 
                            FROM users 
                            WHERE role = 'supervisor'
                            LIMIT 3
                        """)
                        existing_supervisors = cur.fetchall()
                        logger.warning(f"CREATE: Available supervisors: {existing_supervisors}")
                
                if manager_name:
                    # Try to find user by email or full name matching manager name
                    cur.execute("""
                        SELECT id FROM users 
                        WHERE email = %s OR CONCAT(first_name, ' ', last_name) = %s
                        LIMIT 1
                    """, (manager_name, manager_name))
                    manager_result = cur.fetchone()
                    if manager_result:
                        manager_id = manager_result[0]
                        logger.info(f"CREATE: Found manager UUID {manager_id} for name '{manager_name}'")
                    else:
                        logger.warning(f"CREATE: Could not find manager user for name '{manager_name}'")
                
                # Use lowercase column names as they exist in the database
                cur.execute("""
                    INSERT INTO employees (
                        firstname, lastname, email, phonenumber, department, 
                        role, shift, workline, workarea, supervisor, manager, user_id,
                        supervisor_id, manager_id,
                        date_of_employment, allocated_vacation_hours, max_accumulated_hours,
                        vacation_schedule_years, vacation_schedule_hours
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, created_at
                """, (
                    firstname,
                    lastname,
                    data.get('email') or None,
                    data.get('phonenumber') or data.get('phone') or None,
                    data.get('department') or None,
                    data.get('role') or None,
                    data.get('shift') or None,
                    data.get('workline') or None,
                    data.get('workarea') or None,
                    supervisor_name,  # Text field for display
                    manager_name,     # Text field for display
                    user_id,
                    supervisor_id,    # UUID looked up from users table
                    manager_id,       # UUID looked up from users table
                    data.get('date_of_employment') or data.get('dateOfEmployment') or None,
                    data.get('allocated_vacation_hours') or data.get('vacation_hours') or 0,
                    data.get('max_accumulated_hours') or data.get('maxAccumulatedHours') or None,
                    data.get('vacation_schedule_years', []),
                    data.get('vacation_schedule_hours', [])
                ))
                
                employee_id, created_at = cur.fetchone()
                conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Employee created successfully',
            'employeeId': employee_id,
            'createdAt': created_at.isoformat() if created_at else None
        }), 201
        
    except Exception as e:
        logger.error(f"Create employee error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/employees/<int:employee_id>', methods=['PUT'])
@login_required
def update_employee(employee_id):
    """Update an existing employee"""
    try:
        data = request.get_json()
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if employee exists
                cur.execute("SELECT id FROM employees WHERE id = %s", (employee_id,))
                if not cur.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Employee not found'
                    }), 404
                
                # Support both camelCase field names from frontend
                firstname = data.get('firstname') or data.get('firstName')
                lastname = data.get('lastname') or data.get('lastName')
                user_id = data.get('user_id') or data.get('userId') or None
                
                # Get supervisor and manager names from frontend
                supervisor_name = data.get('supervisor')
                manager_name = data.get('manager')
                
                # Lookup supervisor_id and manager_id UUIDs from users table
                supervisor_id = None
                manager_id = None
                
                if supervisor_name:
                    # Try to find user by email or full name matching supervisor name
                    cur.execute("""
                        SELECT id FROM users 
                        WHERE email = %s OR CONCAT(first_name, ' ', last_name) = %s
                        LIMIT 1
                    """, (supervisor_name, supervisor_name))
                    supervisor_result = cur.fetchone()
                    if supervisor_result:
                        supervisor_id = supervisor_result[0]
                        logger.info(f"UPDATE: Found supervisor UUID {supervisor_id} for name '{supervisor_name}'")
                    else:
                        logger.warning(f"UPDATE: Could not find supervisor user for name '{supervisor_name}'")
                
                if manager_name:
                    # Try to find user by email or full name matching manager name
                    cur.execute("""
                        SELECT id FROM users 
                        WHERE email = %s OR CONCAT(first_name, ' ', last_name) = %s
                        LIMIT 1
                    """, (manager_name, manager_name))
                    manager_result = cur.fetchone()
                    if manager_result:
                        manager_id = manager_result[0]
                        logger.info(f"UPDATE: Found manager UUID {manager_id} for name '{manager_name}'")
                    else:
                        logger.warning(f"UPDATE: Could not find manager user for name '{manager_name}'")
                
                # Use lowercase column names as they exist in the database
                cur.execute("""
                    UPDATE employees
                    SET 
                        firstname = %s,
                        lastname = %s,
                        email = %s,
                        phonenumber = %s,
                        department = %s,
                        role = %s,
                        shift = %s,
                        workline = %s,
                        workarea = %s,
                        supervisor = %s,
                        manager = %s,
                        user_id = %s,
                        supervisor_id = %s,
                        manager_id = %s,
                        date_of_employment = %s,
                        allocated_vacation_hours = %s,
                        max_accumulated_hours = %s,
                        vacation_schedule_years = %s,
                        vacation_schedule_hours = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING updated_at
                """, (
                    firstname,
                    lastname,
                    data.get('email') or None,
                    data.get('phonenumber') or data.get('phone') or None,
                    data.get('department') or None,
                    data.get('role') or None,
                    data.get('shift') or None,
                    data.get('workline') or None,
                    data.get('workarea') or None,
                    supervisor_name,  # Text field for display
                    manager_name,     # Text field for display
                    user_id,
                    supervisor_id,    # UUID looked up from users table
                    manager_id,       # UUID looked up from users table
                    manager_id,     # UUID for filtering
                    data.get('date_of_employment') or data.get('dateOfEmployment') or None,
                    data.get('allocated_vacation_hours') or data.get('vacation_hours') or None,
                    data.get('max_accumulated_hours') or data.get('maxAccumulatedHours') or None,
                    data.get('vacation_schedule_years', []),
                    data.get('vacation_schedule_hours', []),
                    employee_id
                ))
                
                updated_at = cur.fetchone()[0]
                conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Employee updated successfully',
            'updatedAt': updated_at.isoformat() if updated_at else None
        })
        
    except Exception as e:
        logger.error(f"Update employee error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/employees/<int:employee_id>', methods=['DELETE'])
@login_required
def delete_employee(employee_id):
    """Delete an employee"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if employee exists
                cur.execute("SELECT id FROM employees WHERE id = %s", (employee_id,))
                if not cur.fetchone():
                    return jsonify({
                        'success': False,
                        'error': 'Employee not found'
                    }), 404
                
                # Check if employee has vacation records
                cur.execute("SELECT COUNT(*) FROM vacation WHERE employee_id = %s", (employee_id,))
                vacation_count = cur.fetchone()[0]
                
                if vacation_count > 0:
                    return jsonify({
                        'success': False,
                        'error': f'Cannot delete employee with {vacation_count} vacation record(s). Please delete vacation records first.'
                    }), 400
                
                cur.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
                conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Employee deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Delete employee error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/users', methods=['GET'])
@login_required
def get_users_for_dropdown():
    """Get all users for dropdown selection"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, email, first_name, last_name
                    FROM users
                    WHERE is_active = TRUE
                    ORDER BY email
                """)
                
                users = []
                for row in cur.fetchall():
                    users.append({
                        'id': str(row[0]),
                        'email': row[1],
                        'first_name': row[2] or '',
                        'last_name': row[3] or ''
                    })
        
        return jsonify({
            'success': True,
            'users': users
        })
        
    except Exception as e:
        logger.error(f"Get users error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== VACATION MANAGEMENT API ====================

@app.route('/api/vacation', methods=['POST'])
@login_required
def create_vacation_request():
    """Create a new vacation request"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['employee_id', 'leave_type', 'start_date', 'end_date', 'reason']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        employee_id = data['employee_id']
        leave_type = data['leave_type'].lower()
        start_date = data['start_date']
        end_date = data['end_date']
        reason = data['reason']
        coverage_plan = data.get('coverage_plan', None)
        emergency_phone = data.get('emergency_phone', None)
        emergency_email = data.get('emergency_email', None)
        auto_approve = data.get('auto_approve', False)
        
        # Get current user
        current_user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Verify employee exists and get snapshot data
                cur.execute("""
                    SELECT id, department, role, shift, workline, workarea
                    FROM employees
                    WHERE id = %s
                """, (employee_id,))
                
                employee = cur.fetchone()
                if not employee:
                    return jsonify({
                        'success': False,
                        'message': 'Employee not found'
                    }), 404
                
                # Validate leave type
                valid_leave_types = ['vacation', 'bereavement', 'sick', 'emergency', 'unpaid', 'personal']
                if leave_type not in valid_leave_types:
                    return jsonify({
                        'success': False,
                        'message': f'Invalid leave type. Must be one of: {", ".join(valid_leave_types)}'
                    }), 400
                
                # Create initial status history
                status_history = [{
                    'status': 'pending',
                    'timestamp': datetime.now().isoformat(),
                    'changed_by': str(current_user_id) if current_user_id else None,
                    'reason': 'Request created'
                }]
                
                # Insert vacation request
                cur.execute("""
                    INSERT INTO vacation (
                        employee_id,
                        requested_by_user_id,
                        leave_type,
                        start_date,
                        end_date,
                        reason,
                        coverage_plan,
                        emergency_phone,
                        emergency_email,
                        auto_approve,
                        status,
                        department_snapshot,
                        role_snapshot,
                        shift_snapshot,
                        workline_snapshot,
                        workarea_snapshot,
                        status_history,
                        created_at,
                        updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    ) RETURNING id, created_at
                """, (
                    employee_id,
                    current_user_id,
                    leave_type,
                    start_date,
                    end_date,
                    reason,
                    coverage_plan,
                    emergency_phone,
                    emergency_email,
                    auto_approve,
                    'pending',
                    employee['department'],
                    employee['role'],
                    employee['shift'],
                    employee['workline'],
                    employee['workarea'],
                    json.dumps(status_history)
                ))
                
                result = cur.fetchone()
                vacation_id = result['id']
                created_at = result['created_at']
                
                conn.commit()
        
        # Create notification for the employee
        # Parse dates for the notification message (they come as strings from JSON)
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if isinstance(start_date, str) else start_date
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if isinstance(end_date, str) else end_date
        
        notification_title = "Vacation Request Submitted"
        notification_message = f"Your vacation request for {start_date_obj.strftime('%b %d')} - {end_date_obj.strftime('%b %d, %Y')} has been submitted and is pending approval."
        
        create_notification(
            employee_id=employee_id,
            notification_type='vacation_submitted',
            title=notification_title,
            message=notification_message,
            related_vacation_id=vacation_id
        )
        
        logger.info(f"Vacation request created: ID={vacation_id}, Employee={employee_id}, Type={leave_type}")
        
        return jsonify({
            'success': True,
            'message': 'Vacation request created successfully',
            'vacation_id': vacation_id,
            'created_at': created_at.isoformat() if created_at else None
        })
        
    except Exception as e:
        logger.error(f"Create vacation request error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/stats', methods=['GET'])
@login_required
def get_vacation_stats():
    """Get vacation dashboard statistics"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get overall stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_requests,
                        COUNT(*) FILTER (WHERE status = 'pending') as pending,
                        COUNT(*) FILTER (WHERE status = 'approved') as approved,
                        COUNT(*) FILTER (WHERE status = 'denied') as denied,
                        COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                        COUNT(*) FILTER (WHERE status = 'approved' 
                                          AND EXTRACT(MONTH FROM decided_at) = EXTRACT(MONTH FROM CURRENT_DATE)
                                          AND EXTRACT(YEAR FROM decided_at) = EXTRACT(YEAR FROM CURRENT_DATE)) as approved_this_month,
                        COALESCE(SUM(duration_days) FILTER (WHERE status = 'approved' 
                                          AND EXTRACT(YEAR FROM start_date) = EXTRACT(YEAR FROM CURRENT_DATE)), 0) as days_used_ytd
                    FROM vacation
                """)
                
                stats = cur.fetchone()
                
                # Get total employees count
                cur.execute("SELECT COUNT(*) as total_employees FROM employees")
                emp_count = cur.fetchone()
                
                result = dict(stats) if stats else {}
                result['total_employees'] = emp_count['total_employees'] if emp_count else 0
                
                return jsonify({
                    'success': True,
                    'stats': result
                })
                
    except Exception as e:
        logger.error(f"Get vacation stats error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/upcoming', methods=['GET'])
@login_required
def get_upcoming_vacations():
    """Get approved vacations in the next 30 days"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        v.id,
                        v.employee_id,
                        e.firstname,
                        e.lastname,
                        v.department_snapshot as department,
                        v.role_snapshot as role,
                        v.start_date,
                        v.end_date,
                        v.leave_type,
                        v.status,
                        v.duration_days,
                        v.reason
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    WHERE v.status = 'approved'
                        AND v.start_date >= CURRENT_DATE
                        AND v.start_date <= CURRENT_DATE + INTERVAL '30 days'
                    ORDER BY v.start_date ASC
                """)
                
                vacations = cur.fetchall()
                
                # Convert to list of dicts
                result = []
                for vac in vacations:
                    vac_dict = dict(vac)
                    # Format dates as strings
                    if vac_dict['start_date']:
                        vac_dict['start_date'] = vac_dict['start_date'].strftime('%Y-%m-%d')
                    if vac_dict['end_date']:
                        vac_dict['end_date'] = vac_dict['end_date'].strftime('%Y-%m-%d')
                    result.append(vac_dict)
                
                return jsonify({
                    'success': True,
                    'vacations': result
                })
                
    except Exception as e:
        logger.error(f"Get upcoming vacations error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/pending', methods=['GET'])
@login_required
def get_pending_vacations():
    """Get vacation requests pending approval"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        v.id,
                        v.employee_id,
                        e.firstname,
                        e.lastname,
                        v.department_snapshot as department,
                        v.role_snapshot as role,
                        v.start_date,
                        v.end_date,
                        v.leave_type,
                        v.status,
                        v.duration_days,
                        v.reason,
                        v.coverage_plan,
                        v.emergency_phone,
                        v.emergency_email,
                        v.created_at,
                        e.allocated_vacation_hours as vacation_balance
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    WHERE v.status = 'pending'
                    ORDER BY v.created_at DESC
                """)
                
                vacations = cur.fetchall()
                
                # Convert to list of dicts
                result = []
                for vac in vacations:
                    vac_dict = dict(vac)
                    # Format dates as strings
                    if vac_dict['start_date']:
                        vac_dict['start_date'] = vac_dict['start_date'].strftime('%Y-%m-%d')
                    if vac_dict['end_date']:
                        vac_dict['end_date'] = vac_dict['end_date'].strftime('%Y-%m-%d')
                    if vac_dict['created_at']:
                        vac_dict['created_at'] = vac_dict['created_at'].isoformat()
                    result.append(vac_dict)
                
                return jsonify({
                    'success': True,
                    'vacations': result
                })
                
    except Exception as e:
        logger.error(f"Get pending vacations error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/recent', methods=['GET'])
@login_required
def get_recent_vacations():
    """Get recently decided vacation requests (last 30 days)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        v.id,
                        v.employee_id,
                        e.firstname,
                        e.lastname,
                        v.department_snapshot as department,
                        v.role_snapshot as role,
                        v.start_date,
                        v.end_date,
                        v.leave_type,
                        v.status,
                        v.duration_days,
                        v.reason,
                        v.decided_at,
                        v.decision_reason,
                        u.first_name as approver_first_name,
                        u.last_name as approver_last_name
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    LEFT JOIN users u ON v.approved_by_user_id = u.id
                    WHERE v.status IN ('approved', 'denied')
                        AND v.decided_at >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY v.decided_at DESC
                    LIMIT 20
                """)
                
                vacations = cur.fetchall()
                
                # Convert to list of dicts
                result = []
                for vac in vacations:
                    vac_dict = dict(vac)
                    # Format dates as strings
                    if vac_dict['start_date']:
                        vac_dict['start_date'] = vac_dict['start_date'].strftime('%Y-%m-%d')
                    if vac_dict['end_date']:
                        vac_dict['end_date'] = vac_dict['end_date'].strftime('%Y-%m-%d')
                    if vac_dict['decided_at']:
                        vac_dict['decided_at'] = vac_dict['decided_at'].isoformat()
                    result.append(vac_dict)
                
                return jsonify({
                    'success': True,
                    'vacations': result
                })
                
    except Exception as e:
        logger.error(f"Get recent vacations error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/<int:vacation_id>/approve', methods=['POST'])
@login_required
def approve_vacation(vacation_id):
    """Approve a vacation request"""
    try:
        current_user_id = session.get('user_id')
        data = request.get_json() or {}
        decision_reason = data.get('reason', '')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get current vacation request with employee info
                cur.execute("""
                    SELECT v.*, e.firstname || ' ' || e.lastname as employee_name
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    WHERE v.id = %s
                """, (vacation_id,))
                vacation = cur.fetchone()
                
                if not vacation:
                    return jsonify({'success': False, 'message': 'Vacation request not found'}), 404
                
                if vacation['status'] != 'pending':
                    return jsonify({'success': False, 'message': 'Only pending requests can be approved'}), 400
                
                # Update status
                cur.execute("""
                    UPDATE vacation
                    SET status = 'approved',
                        approved_by_user_id = %s,
                        decided_at = NOW(),
                        decision_reason = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (current_user_id, decision_reason, vacation_id))
                
                conn.commit()
                
                # Create notification for the employee
                notification_title = "Vacation Request Approved"
                notification_message = f"Your vacation request for {vacation['start_date'].strftime('%b %d')} - {vacation['end_date'].strftime('%b %d, %Y')} has been approved."
                if decision_reason:
                    notification_message += f" Note: {decision_reason}"
                
                create_notification(
                    employee_id=vacation['employee_id'],
                    notification_type='vacation_approved',
                    title=notification_title,
                    message=notification_message,
                    related_vacation_id=vacation_id
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Vacation request approved successfully'
                })
                
    except Exception as e:
        logger.error(f"Approve vacation error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/<int:vacation_id>/deny', methods=['POST'])
@login_required
def deny_vacation(vacation_id):
    """Deny a vacation request"""
    try:
        current_user_id = session.get('user_id')
        data = request.get_json() or {}
        decision_reason = data.get('reason', '')
        
        if not decision_reason:
            return jsonify({'success': False, 'message': 'Denial reason is required'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get current vacation request with employee info
                cur.execute("""
                    SELECT v.*, e.firstname || ' ' || e.lastname as employee_name
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    WHERE v.id = %s
                """, (vacation_id,))
                vacation = cur.fetchone()
                
                if not vacation:
                    return jsonify({'success': False, 'message': 'Vacation request not found'}), 404
                
                if vacation['status'] != 'pending':
                    return jsonify({'success': False, 'message': 'Only pending requests can be denied'}), 400
                
                # Update status
                cur.execute("""
                    UPDATE vacation
                    SET status = 'denied',
                        approved_by_user_id = %s,
                        decided_at = NOW(),
                        decision_reason = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (current_user_id, decision_reason, vacation_id))
                
                conn.commit()
                
                # Create notification for the employee
                notification_title = "Vacation Request Denied"
                notification_message = f"Your vacation request for {vacation['start_date'].strftime('%b %d')} - {vacation['end_date'].strftime('%b %d, %Y')} was not approved. Reason: {decision_reason}"
                
                create_notification(
                    employee_id=vacation['employee_id'],
                    notification_type='vacation_denied',
                    title=notification_title,
                    message=notification_message,
                    related_vacation_id=vacation_id
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Vacation request denied successfully'
                })
                
    except Exception as e:
        logger.error(f"Deny vacation error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/<int:vacation_id>', methods=['GET'])
@login_required
def get_vacation_details(vacation_id):
    """Get detailed information for a specific vacation request"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        v.id,
                        v.employee_id,
                        e.firstname,
                        e.lastname,
                        e.email,
                        v.department_snapshot as department,
                        v.role_snapshot as role,
                        v.start_date,
                        v.end_date,
                        v.leave_type,
                        v.status,
                        v.duration_days,
                        v.reason,
                        v.created_at,
                        v.updated_at,
                        v.decided_at,
                        v.decision_reason,
                        v.approved_by_user_id,
                        approver.first_name as approved_by_first_name,
                        approver.last_name as approved_by_last_name
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    LEFT JOIN users approver ON v.approved_by_user_id = approver.id
                    WHERE v.id = %s
                """, (vacation_id,))
                
                vacation = cur.fetchone()
                
                if not vacation:
                    return jsonify({
                        'success': False,
                        'message': 'Vacation request not found'
                    }), 404
                
                # Convert to dict and format dates
                vac_dict = dict(vacation)
                
                # Combine approver name
                if vac_dict.get('approved_by_first_name') and vac_dict.get('approved_by_last_name'):
                    vac_dict['approved_by_username'] = f"{vac_dict['approved_by_first_name']} {vac_dict['approved_by_last_name']}"
                else:
                    vac_dict['approved_by_username'] = None
                
                # Remove individual name fields
                vac_dict.pop('approved_by_first_name', None)
                vac_dict.pop('approved_by_last_name', None)
                
                if vac_dict['start_date']:
                    vac_dict['start_date'] = vac_dict['start_date'].strftime('%Y-%m-%d')
                if vac_dict['end_date']:
                    vac_dict['end_date'] = vac_dict['end_date'].strftime('%Y-%m-%d')
                if vac_dict['created_at']:
                    vac_dict['created_at'] = vac_dict['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if vac_dict['updated_at']:
                    vac_dict['updated_at'] = vac_dict['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
                if vac_dict['decided_at']:
                    vac_dict['decided_at'] = vac_dict['decided_at'].strftime('%Y-%m-%d %H:%M:%S')
                
                return jsonify({
                    'success': True,
                    'vacation': vac_dict
                })
                
    except Exception as e:
        logger.error(f"Get vacation details error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/activity', methods=['GET'])
@login_required
def get_vacation_activity_log():
    """Get vacation activity log with filtering and pagination"""
    try:
        # Get query parameters
        activity_type = request.args.get('type', 'all')  # all, approvals, denials, modifications, new_requests
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Base query with all necessary joins
                query = """
                    SELECT 
                        v.id,
                        v.employee_id,
                        e.firstname,
                        e.lastname,
                        v.department_snapshot as department,
                        v.role_snapshot as role,
                        v.start_date,
                        v.end_date,
                        v.leave_type,
                        v.status,
                        v.duration_days,
                        v.reason,
                        v.created_at,
                        v.updated_at,
                        v.decided_at,
                        v.decision_reason,
                        v.approved_by_user_id,
                        approver.first_name as approved_by_first_name,
                        approver.last_name as approved_by_last_name,
                        requester.first_name as requested_by_first_name,
                        requester.last_name as requested_by_last_name
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    LEFT JOIN users approver ON v.approved_by_user_id = approver.id
                    LEFT JOIN users requester ON v.requested_by_user_id = requester.id
                """
                
                # Add filters based on activity type
                where_clauses = []
                if activity_type == 'approvals':
                    where_clauses.append("v.status = 'approved'")
                elif activity_type == 'denials':
                    where_clauses.append("v.status = 'denied'")
                elif activity_type == 'new_requests':
                    where_clauses.append("v.status = 'pending'")
                elif activity_type == 'modifications':
                    where_clauses.append("v.updated_at > v.created_at + INTERVAL '1 minute'")
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                # Order by most recent activity first
                query += " ORDER BY GREATEST(v.created_at, COALESCE(v.updated_at, v.created_at), COALESCE(v.decided_at, v.created_at)) DESC"
                query += " LIMIT %s OFFSET %s"
                
                cur.execute(query, (limit, offset))
                activities = cur.fetchall()
                
                # Process activities to determine activity type and format data
                result = []
                for activity in activities:
                    act_dict = dict(activity)
                    
                    # Combine approver and requester names
                    if act_dict.get('approved_by_first_name') and act_dict.get('approved_by_last_name'):
                        act_dict['approved_by_username'] = f"{act_dict['approved_by_first_name']} {act_dict['approved_by_last_name']}"
                    else:
                        act_dict['approved_by_username'] = None
                    
                    if act_dict.get('requested_by_first_name') and act_dict.get('requested_by_last_name'):
                        act_dict['requested_by_username'] = f"{act_dict['requested_by_first_name']} {act_dict['requested_by_last_name']}"
                    else:
                        act_dict['requested_by_username'] = None
                    
                    # Remove individual name fields to keep response clean
                    act_dict.pop('approved_by_first_name', None)
                    act_dict.pop('approved_by_last_name', None)
                    act_dict.pop('requested_by_first_name', None)
                    act_dict.pop('requested_by_last_name', None)
                    
                    # Determine activity type based on status and timestamps
                    if act_dict['status'] == 'pending' and act_dict['decided_at'] is None:
                        act_dict['activity_type'] = 'new_request'
                        act_dict['activity_timestamp'] = act_dict['created_at']
                    elif act_dict['status'] == 'approved':
                        act_dict['activity_type'] = 'approved'
                        act_dict['activity_timestamp'] = act_dict['decided_at'] or act_dict['updated_at']
                    elif act_dict['status'] == 'denied':
                        act_dict['activity_type'] = 'denied'
                        act_dict['activity_timestamp'] = act_dict['decided_at'] or act_dict['updated_at']
                    elif act_dict['updated_at'] and act_dict['created_at'] and \
                         (act_dict['updated_at'] - act_dict['created_at']).total_seconds() > 60:
                        act_dict['activity_type'] = 'modified'
                        act_dict['activity_timestamp'] = act_dict['updated_at']
                    else:
                        act_dict['activity_type'] = 'new_request'
                        act_dict['activity_timestamp'] = act_dict['created_at']
                    
                    # Format dates as strings
                    if act_dict['start_date']:
                        act_dict['start_date'] = act_dict['start_date'].strftime('%Y-%m-%d')
                    if act_dict['end_date']:
                        act_dict['end_date'] = act_dict['end_date'].strftime('%Y-%m-%d')
                    if act_dict['created_at']:
                        act_dict['created_at'] = act_dict['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if act_dict['updated_at']:
                        act_dict['updated_at'] = act_dict['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if act_dict['decided_at']:
                        act_dict['decided_at'] = act_dict['decided_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if act_dict['activity_timestamp']:
                        act_dict['activity_timestamp'] = act_dict['activity_timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    result.append(act_dict)
                
                return jsonify({
                    'success': True,
                    'activities': result,
                    'count': len(result),
                    'limit': limit,
                    'offset': offset
                })
                
    except Exception as e:
        logger.error(f"Get vacation activity log error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== VACATION SETTINGS & CONSTRAINTS API ====================

@app.route('/api/vacation/settings', methods=['GET'])
@login_required
def get_vacation_settings():
    """Get vacation rules and limits settings"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        standard_allocation_days,
                        minimum_notice_days,
                        max_consecutive_days,
                        min_team_coverage_percent,
                        max_simultaneous_absences,
                        critical_role_coverage_required,
                        updated_at
                    FROM vacation_settings
                    WHERE id = 1
                """)
                
                settings = cur.fetchone()
                
                if settings:
                    settings_dict = dict(settings)
                    if settings_dict['updated_at']:
                        settings_dict['updated_at'] = settings_dict['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    return jsonify({
                        'success': True,
                        'settings': settings_dict
                    })
                else:
                    # Return defaults if no settings exist
                    return jsonify({
                        'success': True,
                        'settings': {
                            'standard_allocation_days': 25,
                            'minimum_notice_days': 14,
                            'max_consecutive_days': 15,
                            'min_team_coverage_percent': 60,
                            'max_simultaneous_absences': 3,
                            'critical_role_coverage_required': True
                        }
                    })
                
    except Exception as e:
        logger.error(f"Get vacation settings error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/blackout-periods', methods=['GET'])
@login_required
def get_blackout_periods():
    """Get active vacation blackout periods"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        name,
                        start_date,
                        end_date,
                        description,
                        is_active,
                        created_at
                    FROM vacation_blackout_periods
                    WHERE is_active = TRUE
                    ORDER BY start_date ASC
                """)
                
                periods = cur.fetchall()
                
                # Format dates
                result = []
                for period in periods:
                    period_dict = dict(period)
                    if period_dict['start_date']:
                        period_dict['start_date'] = period_dict['start_date'].strftime('%Y-%m-%d')
                    if period_dict['end_date']:
                        period_dict['end_date'] = period_dict['end_date'].strftime('%Y-%m-%d')
                    if period_dict['created_at']:
                        period_dict['created_at'] = period_dict['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    result.append(period_dict)
                
                return jsonify({
                    'success': True,
                    'periods': result
                })
                
    except Exception as e:
        logger.error(f"Get blackout periods error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/blackout-periods', methods=['POST'])
@login_required
def create_blackout_period():
    """Create a new blackout period"""
    try:
        data = request.get_json()
        
        # Get current user ID from session
        user_id = session.get('user_id', 1)  # Default to 1 if not in session
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO vacation_blackout_periods 
                    (name, start_date, end_date, description, is_active, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data.get('name'),
                    data.get('start_date'),
                    data.get('end_date'),
                    data.get('description'),
                    data.get('is_active', True),
                    user_id
                ))
                
                new_id = cur.fetchone()['id']
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Blackout period created successfully',
                    'id': new_id
                })
                
    except Exception as e:
        logger.error(f"Create blackout period error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/blackout-periods/<int:period_id>', methods=['PUT'])
@login_required
def update_blackout_period(period_id):
    """Update a blackout period"""
    try:
        data = request.get_json()
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if period exists
                cur.execute("SELECT id FROM vacation_blackout_periods WHERE id = %s", (period_id,))
                period = cur.fetchone()
                
                if not period:
                    return jsonify({
                        'success': False,
                        'message': 'Blackout period not found'
                    }), 404
                
                # Update the period
                cur.execute("""
                    UPDATE vacation_blackout_periods
                    SET 
                        name = %s,
                        start_date = %s,
                        end_date = %s,
                        description = %s,
                        is_active = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    data.get('name'),
                    data.get('start_date'),
                    data.get('end_date'),
                    data.get('description'),
                    data.get('is_active', True),
                    period_id
                ))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Blackout period updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Update blackout period error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/blackout-periods/<int:period_id>', methods=['DELETE'])
@login_required
def delete_blackout_period(period_id):
    """Delete a blackout period"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if period exists
                cur.execute("SELECT id, name FROM vacation_blackout_periods WHERE id = %s", (period_id,))
                period = cur.fetchone()
                
                if not period:
                    return jsonify({
                        'success': False,
                        'message': 'Blackout period not found'
                    }), 404
                
                # Delete the period
                cur.execute("DELETE FROM vacation_blackout_periods WHERE id = %s", (period_id,))
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': f"Blackout period '{period['name']}' deleted successfully"
                })
                
    except Exception as e:
        logger.error(f"Delete blackout period error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/settings', methods=['PUT'])
@login_required
def update_vacation_settings():
    """Update vacation settings"""
    try:
        data = request.get_json()
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Only update the fields that are still relevant
                # standard_allocation_days and max_simultaneous_absences are no longer used
                cur.execute("""
                    UPDATE vacation_settings
                    SET 
                        minimum_notice_days = %s,
                        max_consecutive_days = %s,
                        min_team_coverage_percent = %s,
                        critical_role_coverage_required = %s,
                        updated_at = NOW()
                    WHERE id = 1
                """, (
                    data.get('minimum_notice_days'),
                    data.get('max_consecutive_days'),
                    data.get('min_team_coverage_percent'),
                    data.get('critical_role_coverage_required')
                ))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Vacation settings updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Update vacation settings error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/vacation/requests', methods=['GET'])
@login_required
def get_vacation_requests():
    """Get all vacation requests with employee information"""
    try:
        # Get optional status filter
        status_filter = request.args.get('status', 'all')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build query with optional status filter
                query = """
                    SELECT 
                        v.id,
                        v.employee_id,
                        v.start_date,
                        v.end_date,
                        v.duration_days,
                        v.leave_type,
                        v.status,
                        v.created_at,
                        v.approved_by_user_id,
                        v.decided_at,
                        v.decision_reason,
                        e.firstname,
                        e.lastname,
                        e.role as department,
                        u.first_name as approver_first_name,
                        u.last_name as approver_last_name
                    FROM vacation v
                    LEFT JOIN employees e ON v.employee_id = e.id
                    LEFT JOIN users u ON v.approved_by_user_id = u.id
                """
                
                params = []
                if status_filter != 'all':
                    query += " WHERE v.status = %s"
                    params.append(status_filter)
                
                query += " ORDER BY v.created_at DESC"
                
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                
                requests = cur.fetchall()
                
                # Format the results
                result = []
                for req in requests:
                    req_dict = dict(req)
                    
                    # Format dates
                    if req_dict['start_date']:
                        req_dict['start_date'] = req_dict['start_date'].strftime('%Y-%m-%d')
                    if req_dict['end_date']:
                        req_dict['end_date'] = req_dict['end_date'].strftime('%Y-%m-%d')
                    if req_dict['created_at']:
                        req_dict['created_at'] = req_dict['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if req_dict['decided_at']:
                        req_dict['decided_at'] = req_dict['decided_at'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Create full employee name
                    req_dict['employee_name'] = f"{req_dict['firstname']} {req_dict['lastname']}"
                    
                    # Create employee initials for avatar
                    req_dict['initials'] = f"{req_dict['firstname'][0]}{req_dict['lastname'][0]}".upper()
                    
                    # Create approver name if available
                    if req_dict['approver_first_name'] and req_dict['approver_last_name']:
                        req_dict['approver_name'] = f"{req_dict['approver_first_name']} {req_dict['approver_last_name']}"
                    else:
                        req_dict['approver_name'] = None
                    
                    result.append(req_dict)
                
                return jsonify({
                    'success': True,
                    'requests': result,
                    'count': len(result)
                })
                
    except Exception as e:
        logger.error(f"Get vacation requests error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/employees/directory', methods=['GET'])
@login_required
def get_employees_directory():
    """
    Get employee directory with vacation information
    Supports filtering by department (role) and status
    """
    try:
        department_filter = request.args.get('department', 'all')
        status_filter = request.args.get('status', 'all')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Build the base query - get all employees with their vacation stats
                query = """
                WITH employee_vacation_stats AS (
                    SELECT 
                        e.id,
                        e.firstname,
                        e.lastname,
                        e.role,
                        e.workarea,
                        COALESCE(e.annual_allocation, 25) as vacation_balance_days,
                        -- Calculate total vacation days used (approved vacations only)
                        COALESCE(SUM(
                            CASE 
                                WHEN v.status = 'approved' 
                                THEN (v.end_date - v.start_date + 1)
                                ELSE 0
                            END
                        ), 0) as vacation_days_used,
                        -- Current vacation info (if on vacation right now)
                        MAX(CASE 
                            WHEN v.status = 'approved' 
                            AND CURRENT_DATE BETWEEN v.start_date AND v.end_date 
                            THEN v.id 
                            ELSE NULL 
                        END) as current_vacation_id,
                        MAX(CASE 
                            WHEN v.status = 'approved' 
                            AND CURRENT_DATE BETWEEN v.start_date AND v.end_date 
                            THEN v.end_date 
                            ELSE NULL 
                        END) as current_vacation_end,
                        -- Upcoming vacation info (next approved or pending vacation)
                        MAX(CASE 
                            WHEN (v.status = 'approved' OR v.status = 'pending')
                            AND v.start_date > CURRENT_DATE
                            THEN v.id 
                            ELSE NULL 
                        END) as upcoming_vacation_id
                    FROM employees e
                    LEFT JOIN vacation v ON e.id = v.employee_id
                    GROUP BY e.id, e.firstname, e.lastname, e.role, e.workarea, e.annual_allocation
                ),
                upcoming_vacation_details AS (
                    SELECT 
                        v.id,
                        v.employee_id,
                        v.start_date,
                        v.end_date,
                        v.status,
                        ROW_NUMBER() OVER (PARTITION BY v.employee_id ORDER BY v.start_date ASC) as rn
                    FROM vacation v
                    WHERE (v.status = 'approved' OR v.status = 'pending')
                    AND v.start_date > CURRENT_DATE
                )
                SELECT 
                    evs.*,
                    uvd.start_date as upcoming_start,
                    uvd.end_date as upcoming_end,
                    uvd.status as upcoming_status
                FROM employee_vacation_stats evs
                LEFT JOIN upcoming_vacation_details uvd 
                    ON evs.upcoming_vacation_id = uvd.id 
                    AND uvd.rn = 1
                """
                
                # Add filters
                where_conditions = []
                params = []
                
                if department_filter and department_filter != 'all':
                    where_conditions.append("evs.role = %s")
                    params.append(department_filter)
                
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)
                
                query += " ORDER BY evs.firstname, evs.lastname"
                
                cursor.execute(query, params)
                employees = cursor.fetchall()
                
                result = []
                for emp in employees:
                    emp_dict = dict(emp)
                    
                    # Determine current status
                    if emp_dict['current_vacation_id']:
                        emp_dict['current_status'] = 'on_vacation'
                        emp_dict['return_date'] = emp_dict['current_vacation_end'].strftime('%Y-%m-%d') if emp_dict['current_vacation_end'] else None
                    else:
                        emp_dict['current_status'] = 'available'
                        emp_dict['return_date'] = None
                    
                    # Format upcoming vacation
                    emp_dict['upcoming_vacation'] = bool(emp_dict['upcoming_vacation_id'])
                    if emp_dict['upcoming_start']:
                        emp_dict['upcoming_start'] = emp_dict['upcoming_start'].strftime('%Y-%m-%d')
                    if emp_dict['upcoming_end']:
                        emp_dict['upcoming_end'] = emp_dict['upcoming_end'].strftime('%Y-%m-%d')
                    
                    # Apply status filter
                    if status_filter and status_filter != 'all':
                        if status_filter == 'on-vacation' and emp_dict['current_status'] != 'on_vacation':
                            continue
                        elif status_filter == 'available' and emp_dict['current_status'] != 'available':
                            continue
                        elif status_filter == 'upcoming' and not emp_dict['upcoming_vacation']:
                            continue
                    
                    # Clean up temporary fields
                    del emp_dict['current_vacation_id']
                    del emp_dict['current_vacation_end']
                    del emp_dict['upcoming_vacation_id']
                    
                    result.append(emp_dict)
                
                return jsonify({
                    'success': True,
                    'employees': result,
                    'count': len(result)
                })
                
    except Exception as e:
        logger.error(f"Get employees directory error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/employees/departments', methods=['GET'])
@login_required
def get_employee_departments():
    """
    Get distinct departments (roles) from employees table
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT DISTINCT role 
                    FROM employees 
                    WHERE role IS NOT NULL AND role != ''
                    ORDER BY role
                """)
                departments = cursor.fetchall()
                
                result = [dept['role'] for dept in departments if dept['role']]
                
                return jsonify({
                    'success': True,
                    'departments': result
                })
                
    except Exception as e:
        logger.error(f"Get employee departments error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/vacation/conflicts', methods=['GET'])
@login_required
def get_vacation_conflicts():
    """
    Detect and return vacation scheduling conflicts and warnings
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                conflicts = []
                
                # Get vacation settings for thresholds
                cursor.execute("SELECT * FROM vacation_settings LIMIT 1")
                settings = cursor.fetchone()
                
                if not settings:
                    settings = {
                        'min_team_coverage_percent': 70,
                        'max_simultaneous_absences': 3
                    }
                
                max_simultaneous = settings.get('max_simultaneous_absences', 3)
                
                logger.info(f"Checking for conflicts with max_simultaneous_absences: {max_simultaneous}")
                
                # Check for overlapping vacations across the company
                # Find all dates where more people are on vacation than allowed
                cursor.execute("""
                    WITH date_series AS (
                        SELECT generate_series(
                            CURRENT_DATE - INTERVAL '30 days',
                            CURRENT_DATE + INTERVAL '90 days',
                            '1 day'::interval
                        )::date as check_date
                    ),
                    vacations_per_day AS (
                        SELECT 
                            ds.check_date,
                            COUNT(DISTINCT v.id) as vacation_count,
                            array_agg(
                                DISTINCT jsonb_build_object(
                                    'employee_name', e.firstname || ' ' || e.lastname,
                                    'start_date', v.start_date,
                                    'end_date', v.end_date,
                                    'status', v.status,
                                    'role', e.role
                                )
                            ) FILTER (WHERE v.id IS NOT NULL) as employees_off
                        FROM date_series ds
                        LEFT JOIN vacation v ON ds.check_date BETWEEN v.start_date AND v.end_date
                            AND (v.status = 'approved' OR v.status = 'pending')
                        LEFT JOIN employees e ON v.employee_id = e.id
                        GROUP BY ds.check_date
                        HAVING COUNT(DISTINCT v.id) > %s
                        ORDER BY ds.check_date
                        LIMIT 10
                    )
                    SELECT 
                        check_date,
                        vacation_count,
                        employees_off
                    FROM vacations_per_day
                """, (max_simultaneous,))
                
                conflicts_by_date = cursor.fetchall()
                
                logger.info(f"Found {len(conflicts_by_date)} conflict dates")
                
                # Group consecutive dates into conflict periods
                conflict_periods = []
                if conflicts_by_date:
                    current_period = {
                        'start_date': conflicts_by_date[0]['check_date'],
                        'end_date': conflicts_by_date[0]['check_date'],
                        'max_count': conflicts_by_date[0]['vacation_count'],
                        'all_employees': conflicts_by_date[0]['employees_off']
                    }
                    
                    for row in conflicts_by_date[1:]:
                        # If consecutive day, extend period
                        if (row['check_date'] - current_period['end_date']).days == 1:
                            current_period['end_date'] = row['check_date']
                            current_period['max_count'] = max(current_period['max_count'], row['vacation_count'])
                            # Merge employee lists
                            for emp in row['employees_off']:
                                if emp not in current_period['all_employees']:
                                    current_period['all_employees'].append(emp)
                        else:
                            # Save current period and start new one
                            conflict_periods.append(current_period)
                            current_period = {
                                'start_date': row['check_date'],
                                'end_date': row['check_date'],
                                'max_count': row['vacation_count'],
                                'all_employees': row['employees_off']
                            }
                    
                    # Don't forget the last period
                    conflict_periods.append(current_period)
                
                # Create conflict cards from periods
                for period in conflict_periods:
                    # Get unique employees in this period
                    unique_employees = {}
                    for emp_obj in period['all_employees']:
                        key = emp_obj['employee_name']
                        if key not in unique_employees:
                            unique_employees[key] = emp_obj
                    
                    conflicting_requests = list(unique_employees.values())
                    
                    conflicts.append({
                        'severity': 'critical' if period['max_count'] > max_simultaneous + 1 else 'warning',
                        'title': f'Too Many Simultaneous Absences',
                        'description': f'{period["max_count"]} employees requesting time off simultaneously (maximum allowed: {max_simultaneous})',
                        'conflicting_requests': conflicting_requests[:10],  # Limit to 10 for display
                        'period': {
                            'start': period['start_date'].strftime('%b %d, %Y'),
                            'end': period['end_date'].strftime('%b %d, %Y')
                        }
                    })
                
                # Also check for overlapping vacations by role/department
                cursor.execute("""
                    WITH overlapping_vacations AS (
                        SELECT 
                            v1.id as vacation1_id,
                            v1.employee_id as employee1_id,
                            e1.firstname || ' ' || e1.lastname as employee1_name,
                            e1.role as role,
                            v1.start_date as start1,
                            v1.end_date as end1,
                            v2.id as vacation2_id,
                            v2.employee_id as employee2_id,
                            e2.firstname || ' ' || e2.lastname as employee2_name,
                            v2.start_date as start2,
                            v2.end_date as end2
                        FROM vacation v1
                        JOIN employees e1 ON v1.employee_id = e1.id
                        JOIN vacation v2 ON v1.id < v2.id 
                        JOIN employees e2 ON v2.employee_id = e2.id
                        WHERE 
                            e1.role = e2.role
                            AND e1.role IS NOT NULL
                            AND (v1.status = 'approved' OR v1.status = 'pending')
                            AND (v2.status = 'approved' OR v2.status = 'pending')
                            AND (
                                (v1.start_date <= v2.end_date AND v1.end_date >= v2.start_date)
                            )
                            AND v1.start_date >= CURRENT_DATE - INTERVAL '7 days'
                    )
                    SELECT 
                        role,
                        COUNT(*) as overlap_count,
                        array_agg(
                            json_build_object(
                                'employee_name', employee1_name,
                                'start_date', start1,
                                'end_date', end1
                            )
                        ) || array_agg(
                            json_build_object(
                                'employee_name', employee2_name,
                                'start_date', start2,
                                'end_date', end2
                            )
                        ) as conflicting_requests
                    FROM overlapping_vacations
                    GROUP BY role
                    HAVING COUNT(*) >= 1
                """)
                
                overlaps = cursor.fetchall()
                
                for overlap in overlaps:
                    # Remove duplicates from conflicting_requests
                    seen = set()
                    unique_requests = []
                    for req in overlap['conflicting_requests']:
                        key = (req['employee_name'], str(req['start_date']), str(req['end_date']))
                        if key not in seen:
                            seen.add(key)
                            unique_requests.append(req)
                    
                    conflicts.append({
                        'severity': 'warning',
                        'title': f'Team Coverage Warning - {overlap["role"]}',
                        'description': 'Multiple team members requesting overlapping vacation dates',
                        'conflicting_requests': unique_requests[:5]  # Limit to 5 for display
                    })
                
                # Check for blackout period violations
                cursor.execute("""
                    SELECT 
                        v.id,
                        e.firstname || ' ' || e.lastname as employee_name,
                        v.start_date,
                        v.end_date,
                        bp.name as blackout_name,
                        bp.start_date as blackout_start,
                        bp.end_date as blackout_end
                    FROM vacation v
                    JOIN employees e ON v.employee_id = e.id
                    JOIN vacation_blackout_periods bp ON bp.is_active = true
                    WHERE 
                        (v.status = 'pending')
                        AND (
                            (v.start_date <= bp.end_date AND v.end_date >= bp.start_date)
                        )
                    ORDER BY v.start_date
                    LIMIT 5
                """)
                
                blackout_violations = cursor.fetchall()
                
                for violation in blackout_violations:
                    conflicts.append({
                        'severity': 'critical',
                        'title': f'Blackout Period Violation',
                        'description': f'Vacation request during restricted period: {violation["blackout_name"]}',
                        'details': {
                            'Employee': violation['employee_name'],
                            'Requested Dates': f"{violation['start_date'].strftime('%b %d')} - {violation['end_date'].strftime('%b %d, %Y')}",
                            'Blackout Period': violation['blackout_name']
                        }
                    })
                
                logger.info(f"Total conflicts found: {len(conflicts)}")
                
                return jsonify({
                    'success': True,
                    'conflicts': conflicts,
                    'count': len(conflicts)
                })
                
    except Exception as e:
        logger.error(f"Get vacation conflicts error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== NOTIFICATION HELPER FUNCTIONS ====================

def create_notification(employee_id, notification_type, title, message, related_vacation_id=None):
    """
    Create a notification for an employee
    
    Args:
        employee_id: ID of the employee to notify (references employees.id)
        notification_type: Type of notification ('vacation_approved', 'vacation_denied', 'vacation_submitted', etc.)
        title: Notification title
        message: Notification message
        related_vacation_id: Optional ID of related vacation request
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # The notifications table uses 'user_id' column that actually references employees(id)
                cursor.execute("""
                    INSERT INTO notifications 
                    (user_id, notification_type, title, message, related_vacation_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (employee_id, notification_type, title, message, related_vacation_id))
                
                notification_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Created notification {notification_id} for employee {employee_id}: {notification_type}")
                return notification_id
                
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        return None


# ==================== NOTIFICATION API ENDPOINTS ====================

@app.route('/api/vacation/notifications', methods=['GET'])
@login_required
def get_vacation_notifications():
    """Get vacation notifications for the current user (or all for admin/supervisor)"""
    try:
        user_uuid = session.get('user_id')  # This is a UUID string
        user_role = session.get('user_role', '').lower()
        limit = request.args.get('limit', 20, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        logger.info(f"Getting notifications for user_uuid: {user_uuid}, role: {user_role}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if notifications table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'notifications'
                    )
                """)
                table_exists = cursor.fetchone()['exists']
                
                if not table_exists:
                    logger.warning("Notifications table does not exist yet")
                    return jsonify({
                        'success': True,
                        'notifications': [],
                        'unreadCount': 0
                    })
                
                # Get employee ID from UUID (needed for regular employees to see their own notifications)
                employee_id = None
                if user_role not in ['admin', 'supervisor']:
                    cursor.execute("""
                        SELECT id FROM employees WHERE user_id = %s
                    """, (user_uuid,))
                    employee = cursor.fetchone()
                    
                    if not employee:
                        logger.warning(f"No employee found for user_id: {user_uuid}")
                        # Try to show what employees exist
                        cursor.execute("SELECT id, user_id FROM employees LIMIT 5")
                        sample_employees = cursor.fetchall()
                        logger.info(f"Sample employees in database: {sample_employees}")
                        return jsonify({
                            'success': True,
                            'notifications': [],
                            'unreadCount': 0
                        })
                    
                    employee_id = employee['id']
                    logger.info(f"Found employee_id: {employee_id} for user_uuid: {user_uuid}")
                
                # Build query based on role
                query = """
                    SELECT 
                        n.id,
                        n.notification_type,
                        n.title,
                        n.message,
                        n.related_vacation_id,
                        n.is_read,
                        n.created_at,
                        n.read_at,
                        n.user_id,
                        e.firstname,
                        e.lastname,
                        v.start_date as vacation_start_date,
                        v.end_date as vacation_end_date,
                        v.status as vacation_status
                    FROM notifications n
                    LEFT JOIN vacation v ON n.related_vacation_id = v.id
                    LEFT JOIN employees e ON n.user_id = e.id
                """
                
                params = []
                
                if user_role == 'admin':
                    # Admin sees ALL notifications from all employees
                    query += " WHERE 1=1"
                    logger.info("Admin viewing all notifications from all employees")
                elif user_role == 'supervisor':
                    # Supervisor sees notifications only from employees assigned to them
                    query += " WHERE e.supervisor_id = %s"
                    params.append(user_uuid)
                    logger.info(f"Supervisor viewing notifications from their assigned employees (supervisor_id = {user_uuid})")
                else:
                    # Regular employee sees only their own notifications
                    query += " WHERE n.user_id = %s"
                    params.append(employee_id)
                    logger.info(f"Employee viewing their own notifications (employee_id = {employee_id})")
                
                if unread_only:
                    query += " AND n.is_read = FALSE"
                
                query += " ORDER BY n.created_at DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(query, params)
                notifications = cursor.fetchall()
                
                # Get unread count based on role
                if user_role == 'admin':
                    # Admin sees unread count from all employees
                    cursor.execute("""
                        SELECT COUNT(*) as unread_count
                        FROM notifications
                        WHERE is_read = FALSE
                    """)
                elif user_role == 'supervisor':
                    # Supervisor sees unread count from their assigned employees only
                    cursor.execute("""
                        SELECT COUNT(*) as unread_count
                        FROM notifications n
                        JOIN employees e ON n.user_id = e.id
                        WHERE e.supervisor_id = %s AND n.is_read = FALSE
                    """, (user_uuid,))
                else:
                    # Regular employee sees their own unread count
                    cursor.execute("""
                        SELECT COUNT(*) as unread_count
                        FROM notifications
                        WHERE user_id = %s AND is_read = FALSE
                    """, (employee_id,))
                
                unread_count = cursor.fetchone()['unread_count']
                
                # Format notifications
                formatted_notifications = []
                for notif in notifications:
                    notification_data = {
                        'id': notif['id'],
                        'type': notif['notification_type'],
                        'title': notif['title'],
                        'message': notif['message'],
                        'isRead': notif['is_read'],
                        'createdAt': notif['created_at'].isoformat() if notif['created_at'] else None,
                        'readAt': notif['read_at'].isoformat() if notif['read_at'] else None,
                        'relatedVacationId': notif['related_vacation_id'],
                        'vacationInfo': {
                            'startDate': notif['vacation_start_date'].isoformat() if notif.get('vacation_start_date') else None,
                            'endDate': notif['vacation_end_date'].isoformat() if notif.get('vacation_end_date') else None,
                            'status': notif.get('vacation_status')
                        } if notif.get('vacation_start_date') else None
                    }
                    
                    # Add employee name for admin/supervisor view (they see others' notifications)
                    if user_role in ['admin', 'supervisor'] and notif.get('first_name'):
                        employee_name = f"{notif['first_name']} {notif.get('last_name', '')}".strip()
                        notification_data['employeeName'] = employee_name
                    
                    formatted_notifications.append(notification_data)
                
                return jsonify({
                    'success': True,
                    'notifications': formatted_notifications,
                    'unreadCount': unread_count
                })
                
    except Exception as e:
        logger.error(f"Get vacation notifications error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_vacation_notification_read(notification_id):
    """Mark a vacation notification as read"""
    try:
        user_uuid = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee ID from UUID
                cursor.execute("SELECT id FROM employees WHERE user_id = %s", (user_uuid,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({'success': False, 'message': 'Employee not found'}), 404
                
                employee_id = employee['id']
                
                cursor.execute("""
                    UPDATE notifications
                    SET is_read = TRUE, read_at = NOW()
                    WHERE id = %s AND user_id = %s
                """, (notification_id, employee_id))
                
                conn.commit()
                
                return jsonify({'success': True, 'message': 'Notification marked as read'})
                
    except Exception as e:
        logger.error(f"Mark vacation notification read error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_vacation_notifications_read():
    """Mark all vacation notifications as read for the current user"""
    try:
        user_uuid = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee ID from UUID
                cursor.execute("SELECT id FROM employees WHERE user_id = %s", (user_uuid,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({'success': False, 'message': 'Employee not found'}), 404
                
                employee_id = employee['id']
                
                cursor.execute("""
                    UPDATE notifications
                    SET is_read = TRUE, read_at = NOW()
                    WHERE user_id = %s AND is_read = FALSE
                """, (employee_id,))
                
                conn.commit()
                
                return jsonify({'success': True, 'message': 'All notifications marked as read'})
                
    except Exception as e:
        logger.error(f"Mark all vacation notifications read error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_vacation_notification(notification_id):
    """Delete a vacation notification"""
    try:
        user_uuid = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee ID from UUID
                cursor.execute("SELECT id FROM employees WHERE user_id = %s", (user_uuid,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({'success': False, 'message': 'Employee not found'}), 404
                
                employee_id = employee['id']
                
                cursor.execute("""
                    DELETE FROM notifications
                    WHERE id = %s AND user_id = %s
                """, (notification_id, employee_id))
                
                conn.commit()
                
                return jsonify({'success': True, 'message': 'Notification deleted'})
                
    except Exception as e:
        logger.error(f"Delete vacation notification error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== EMPLOYEE VACATION API ====================

@app.route('/api/vacation/my-stats', methods=['GET'])
@login_required
def get_my_vacation_stats():
    """Get vacation statistics for the logged-in employee"""
    try:
        user_uuid = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee ID and vacation balance (using actual column name)
                cursor.execute("""
                    SELECT id, allocated_vacation_hours, annual_allocation 
                    FROM employees 
                    WHERE user_id = %s
                """, (user_uuid,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({'success': False, 'message': 'Employee not found'}), 404
                
                employee_id = employee['id']
                
                # Get total vacation hours (use allocated_vacation_hours or annual_allocation)
                vacation_hours = employee.get('allocated_vacation_hours') or employee.get('annual_allocation') or 200
                # Convert to float to avoid Decimal type issues
                total_days = float(vacation_hours) / 8.0  # Convert hours to days
                
                # Get days used (approved vacations this year)
                cursor.execute("""
                    SELECT COALESCE(SUM(duration_days), 0) as days_used
                    FROM vacation
                    WHERE employee_id = %s
                    AND status = 'approved'
                    AND EXTRACT(YEAR FROM start_date) = EXTRACT(YEAR FROM CURRENT_DATE)
                """, (employee_id,))
                result = cursor.fetchone()
                days_used = float(result['days_used']) if result and result['days_used'] else 0.0
                
                # Get approved count (this year)
                cursor.execute("""
                    SELECT COUNT(*) as approved_count
                    FROM vacation
                    WHERE employee_id = %s
                    AND status = 'approved'
                    AND EXTRACT(YEAR FROM start_date) = EXTRACT(YEAR FROM CURRENT_DATE)
                """, (employee_id,))
                result = cursor.fetchone()
                approved_count = int(result['approved_count']) if result else 0
                
                # Debug: Get all approved vacations to see what's happening
                cursor.execute("""
                    SELECT id, start_date, end_date, status, duration_days,
                           EXTRACT(YEAR FROM start_date) as vacation_year,
                           EXTRACT(YEAR FROM CURRENT_DATE) as current_year
                    FROM vacation
                    WHERE employee_id = %s
                    AND status = 'approved'
                """, (employee_id,))
                debug_vacations = cursor.fetchall()
                logger.info(f"Employee {employee_id} approved vacations: {debug_vacations}")
                
                # Get pending count
                cursor.execute("""
                    SELECT COUNT(*) as pending_count
                    FROM vacation
                    WHERE employee_id = %s
                    AND status = 'pending'
                """, (employee_id,))
                result = cursor.fetchone()
                pending = int(result['pending_count']) if result else 0
                
                days_remaining = float(total_days) - float(days_used)
                
                logger.info(f"Employee {employee_id} stats - Total: {total_days}, Used: {days_used}, Remaining: {days_remaining}, Pending: {pending}, Approved: {approved_count}")
                
                return jsonify({
                    'success': True,
                    'stats': {
                        'total_days': int(total_days),
                        'days_used': int(days_used),
                        'days_remaining': int(days_remaining),
                        'pending': pending,
                        'approved_count': approved_count
                    }
                })
                
    except Exception as e:
        logger.error(f"Get my vacation stats error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/my-history', methods=['GET'])
@login_required
def get_my_vacation_history():
    """Get vacation history for the logged-in employee"""
    try:
        user_uuid = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee ID from UUID
                cursor.execute("SELECT id FROM employees WHERE user_id = %s", (user_uuid,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({'success': False, 'message': 'Employee not found'}), 404
                
                employee_id = employee['id']
                
                # Get all vacation requests for this employee
                cursor.execute("""
                    SELECT 
                        v.id,
                        v.start_date,
                        v.end_date,
                        v.duration_days,
                        v.leave_type,
                        v.reason,
                        v.status,
                        v.created_at,
                        v.decided_at,
                        v.decision_reason
                    FROM vacation v
                    WHERE v.employee_id = %s
                    ORDER BY v.created_at DESC
                    LIMIT 50
                """, (employee_id,))
                
                vacations = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'vacations': vacations
                })
                
    except Exception as e:
        logger.error(f"Get my vacation history error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/my-activity', methods=['GET'])
@login_required
def get_my_vacation_activity():
    """Get activity log for the logged-in employee's vacation requests"""
    try:
        user_uuid = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee ID from UUID
                cursor.execute("SELECT id FROM employees WHERE user_id = %s", (user_uuid,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({'success': False, 'message': 'Employee not found'}), 404
                
                employee_id = employee['id']
                
                # Get activity log (recent changes to their vacation requests)
                cursor.execute("""
                    SELECT 
                        v.id,
                        v.start_date,
                        v.end_date,
                        v.duration_days,
                        v.leave_type,
                        v.status,
                        v.decision_reason,
                        CASE 
                            WHEN v.status = 'approved' AND v.decided_at IS NOT NULL THEN 'approved'
                            WHEN v.status = 'denied' AND v.decided_at IS NOT NULL THEN 'denied'
                            WHEN v.updated_at > v.created_at THEN 'modified'
                            ELSE 'new_request'
                        END as activity_type,
                        COALESCE(v.decided_at, v.updated_at, v.created_at) as activity_timestamp
                    FROM vacation v
                    WHERE v.employee_id = %s
                    ORDER BY activity_timestamp DESC
                    LIMIT 20
                """, (employee_id,))
                
                activities = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'activities': activities
                })
                
    except Exception as e:
        logger.error(f"Get my vacation activity error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/my-upcoming', methods=['GET'])
@login_required
def get_my_upcoming_vacations():
    """Get employee's approved upcoming vacations (next 30 days)"""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee_id from user_id
                cursor.execute("""
                    SELECT id FROM employees WHERE user_id = %s
                """, (user_id,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({
                        'success': False,
                        'message': 'Employee record not found'
                    }), 404
                
                employee_id = employee['id']
                
                cursor.execute("""
                    SELECT 
                        id,
                        start_date,
                        end_date,
                        duration_days,
                        leave_type,
                        status,
                        reason,
                        created_at
                    FROM vacation
                    WHERE employee_id = %s
                    AND status = 'approved'
                    AND start_date >= CURRENT_DATE
                    AND start_date <= CURRENT_DATE + INTERVAL '30 days'
                    ORDER BY start_date ASC
                """, (employee_id,))
                
                vacations = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'vacations': vacations
                })
                
    except Exception as e:
        logger.error(f"Get my upcoming vacations error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/my-pending', methods=['GET'])
@login_required
def get_my_pending_requests():
    """Get employee's pending vacation requests"""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee_id from user_id
                cursor.execute("""
                    SELECT id FROM employees WHERE user_id = %s
                """, (user_id,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({
                        'success': False,
                        'message': 'Employee record not found'
                    }), 404
                
                employee_id = employee['id']
                
                cursor.execute("""
                    SELECT 
                        id,
                        start_date,
                        end_date,
                        duration_days,
                        leave_type,
                        status,
                        reason,
                        created_at
                    FROM vacation
                    WHERE employee_id = %s
                    AND status = 'pending'
                    ORDER BY created_at DESC
                """, (employee_id,))
                
                vacations = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'vacations': vacations
                })
                
    except Exception as e:
        logger.error(f"Get my pending requests error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/my-recent', methods=['GET'])
@login_required
def get_my_recent_activity():
    """Get employee's recent vacation decisions (approved/denied in last 30 days)"""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee_id from user_id
                cursor.execute("""
                    SELECT id FROM employees WHERE user_id = %s
                """, (user_id,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({
                        'success': False,
                        'message': 'Employee record not found'
                    }), 404
                
                employee_id = employee['id']
                
                cursor.execute("""
                    SELECT 
                        id,
                        start_date,
                        end_date,
                        duration_days,
                        leave_type,
                        status,
                        reason,
                        decision_reason,
                        decided_at,
                        created_at
                    FROM vacation
                    WHERE employee_id = %s
                    AND status IN ('approved', 'denied')
                    AND decided_at IS NOT NULL
                    AND decided_at >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY decided_at DESC
                """, (employee_id,))
                
                vacations = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'vacations': vacations
                })
                
    except Exception as e:
        logger.error(f"Get my recent activity error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/vacation/my-conflicts', methods=['GET'])
@login_required
def get_my_vacation_conflicts():
    """Get conflicts related to current employee's vacation requests"""
    try:
        user_id = session.get('user_id')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get employee_id from user_id
                cursor.execute("""
                    SELECT id FROM employees WHERE user_id = %s
                """, (user_id,))
                employee = cursor.fetchone()
                
                if not employee:
                    return jsonify({
                        'success': False,
                        'message': 'Employee record not found'
                    }), 404
                
                employee_id = employee['id']
                
                conflicts = []
                
                # Get vacation settings for thresholds
                cursor.execute("SELECT * FROM vacation_settings LIMIT 1")
                settings = cursor.fetchone()
                
                if not settings:
                    settings = {
                        'max_simultaneous_absences': 3
                    }
                
                max_simultaneous = settings.get('max_simultaneous_absences', 3)
                
                # Get employee's approved and pending vacation requests
                cursor.execute("""
                    SELECT 
                        id,
                        start_date,
                        end_date,
                        status,
                        leave_type,
                        duration_days
                    FROM vacation
                    WHERE employee_id = %s
                    AND status IN ('approved', 'pending')
                    AND end_date >= CURRENT_DATE
                    ORDER BY start_date
                """, (employee_id,))
                
                my_vacations = cursor.fetchall()
                
                # For each vacation, check for conflicts
                for vac in my_vacations:
                    # Check how many other people are off during this period
                    cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT v.id) as overlapping_count,
                            array_agg(
                                DISTINCT jsonb_build_object(
                                    'employee_name', e.firstname || ' ' || e.lastname,
                                    'start_date', v.start_date,
                                    'end_date', v.end_date,
                                    'status', v.status
                                )
                            ) FILTER (WHERE v.id IS NOT NULL AND v.id != %s) as other_employees
                        FROM vacation v
                        JOIN employees e ON v.employee_id = e.id
                        WHERE (v.status = 'approved' OR v.status = 'pending')
                        AND v.employee_id != %s
                        AND (
                            (v.start_date BETWEEN %s AND %s)
                            OR (v.end_date BETWEEN %s AND %s)
                            OR (v.start_date <= %s AND v.end_date >= %s)
                        )
                    """, (
                        vac['id'], 
                        employee_id,
                        vac['start_date'], vac['end_date'],
                        vac['start_date'], vac['end_date'],
                        vac['start_date'], vac['end_date']
                    ))
                    
                    overlap_data = cursor.fetchone()
                    total_off = overlap_data['overlapping_count'] + 1  # +1 for current employee
                    
                    if total_off > max_simultaneous:
                        # Create conflict entry
                        start_str = vac['start_date'].strftime('%b %d')
                        end_str = vac['end_date'].strftime('%b %d, %Y')
                        
                        conflicts.append({
                            'severity': 'critical' if total_off > max_simultaneous + 1 else 'warning',
                            'title': f'Scheduling Conflict: {start_str} - {end_str}',
                            'description': f'{total_off} employees requesting time off (maximum allowed: {max_simultaneous}). Your request may be affected.',
                            'conflicting_requests': overlap_data['other_employees'][:10] if overlap_data['other_employees'] else [],
                            'details': {
                                'Your Request': f"{vac['status'].capitalize()} - {vac['duration_days']} days",
                                'Total Employees Off': str(total_off),
                                'Maximum Allowed': str(max_simultaneous)
                            }
                        })
                
                return jsonify({
                    'success': True,
                    'conflicts': conflicts
                })
                
    except Exception as e:
        logger.error(f"Get my vacation conflicts error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== WORK AREA SETTINGS API ====================

@app.route('/api/assets/work-lines-areas', methods=['GET'])
@login_required
def get_work_lines_and_areas():
    """Get work lines and work areas from assets table"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        work_lines,
                        work_areas
                    FROM assets
                    WHERE is_active = true
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                
                if result:
                    return jsonify({
                        'success': True,
                        'work_lines': result['work_lines'] or [],
                        'work_areas': result['work_areas'] or []
                    })
                else:
                    # Return empty arrays if no data found
                    return jsonify({
                        'success': True,
                        'work_lines': [],
                        'work_areas': []
                    })
                
    except Exception as e:
        logger.error(f"Get work lines and areas error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/work-area-settings', methods=['GET'])
@login_required
def get_work_area_settings():
    """Get all work area settings"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        id,
                        work_area,
                        work_line,
                        work_area_name,
                        max_simultaneous_absences,
                        description,
                        is_active
                    FROM work_area_settings
                    ORDER BY work_line, work_area_name
                """)
                
                settings = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'settings': settings
                })
                
    except Exception as e:
        logger.error(f"Get work area settings error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/work-area-settings', methods=['POST'])
@login_required
def create_work_area_setting():
    """Create a new work area setting"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('work_line'):
            return jsonify({
                'success': False,
                'message': 'Work line is required'
            }), 400
            
        if not data.get('work_area_name'):
            return jsonify({
                'success': False,
                'message': 'Work area is required'
            }), 400
            
        if not data.get('max_simultaneous_absences'):
            return jsonify({
                'success': False,
                'message': 'Max simultaneous absences is required'
            }), 400
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if this work line + area combination already exists
                cursor.execute("""
                    SELECT id FROM work_area_settings
                    WHERE work_line = %s AND work_area_name = %s
                """, (data['work_line'], data['work_area_name']))
                
                if cursor.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'A setting for this work line and area combination already exists'
                    }), 400
                
                # Create combined display name for backward compatibility
                combined_name = f"{data['work_line']} - {data['work_area_name']}"
                
                # Insert new setting
                cursor.execute("""
                    INSERT INTO work_area_settings (
                        work_line,
                        work_area_name,
                        work_area,
                        max_simultaneous_absences,
                        description,
                        is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data['work_line'],
                    data['work_area_name'],
                    combined_name,
                    data['max_simultaneous_absences'],
                    data.get('description', ''),
                    data.get('is_active', True)
                ))
                
                new_id = cursor.fetchone()['id']
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Work area setting created successfully',
                    'id': new_id
                })
                
    except Exception as e:
        logger.error(f"Create work area setting error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/work-area-settings/<int:setting_id>', methods=['PUT'])
@login_required
def update_work_area_setting(setting_id):
    """Update an existing work area setting"""
    try:
        data = request.json
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if setting exists
                cursor.execute("""
                    SELECT id FROM work_area_settings WHERE id = %s
                """, (setting_id,))
                
                if not cursor.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Work area setting not found'
                    }), 404
                
                # Check if work line/area combination is being changed and if it conflicts
                if data.get('work_line') and data.get('work_area_name'):
                    cursor.execute("""
                        SELECT id FROM work_area_settings
                        WHERE work_line = %s AND work_area_name = %s AND id != %s
                    """, (data['work_line'], data['work_area_name'], setting_id))
                    
                    if cursor.fetchone():
                        return jsonify({
                            'success': False,
                            'message': 'Another setting with this work line and area combination already exists'
                        }), 400
                
                # Create combined display name if both fields are provided
                combined_name = None
                if data.get('work_line') and data.get('work_area_name'):
                    combined_name = f"{data['work_line']} - {data['work_area_name']}"
                
                # Update the setting
                cursor.execute("""
                    UPDATE work_area_settings
                    SET 
                        work_line = COALESCE(%s, work_line),
                        work_area_name = COALESCE(%s, work_area_name),
                        work_area = COALESCE(%s, work_area),
                        max_simultaneous_absences = COALESCE(%s, max_simultaneous_absences),
                        description = COALESCE(%s, description),
                        is_active = COALESCE(%s, is_active)
                    WHERE id = %s
                """, (
                    data.get('work_line'),
                    data.get('work_area_name'),
                    combined_name,
                    data.get('max_simultaneous_absences'),
                    data.get('description'),
                    data.get('is_active'),
                    setting_id
                ))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Work area setting updated successfully'
                })
                
    except Exception as e:
        logger.error(f"Update work area setting error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/work-area-settings/<int:setting_id>', methods=['DELETE'])
@login_required
def delete_work_area_setting(setting_id):
    """Delete a work area setting"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if setting exists
                cursor.execute("""
                    SELECT id FROM work_area_settings WHERE id = %s
                """, (setting_id,))
                
                if not cursor.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Work area setting not found'
                    }), 404
                
                # Delete the setting
                cursor.execute("""
                    DELETE FROM work_area_settings WHERE id = %s
                """, (setting_id,))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Work area setting deleted successfully'
                })
                
    except Exception as e:
        logger.error(f"Delete work area setting error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== ASSETS MANAGEMENT API ====================

@app.route('/api/assets', methods=['GET'])
@login_required
def get_assets():
    """Get current active assets configuration"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        work_roles,
                        work_lines,
                        work_areas,
                        departments,
                        shifts_names,
                        version,
                        created_at,
                        updated_at
                    FROM assets
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                result = cur.fetchone()
                
                if result:
                    return jsonify({
                        'success': True,
                        'assets': {
                            'workRoles': result[0] or [],
                            'workLines': result[1] or [],
                            'workAreas': result[2] or [],
                            'departments': result[3] or [],
                            'shiftsNames': result[4] or [],
                            'version': result[5],
                            'createdAt': result[6].isoformat() if result[6] else None,
                            'updatedAt': result[7].isoformat() if result[7] else None
                        }
                    })
                
                return jsonify({
                    'success': False,
                    'error': 'No active configuration found'
                }), 404
        
    except Exception as e:
        logger.error(f"Get assets error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/assets', methods=['PUT'])
@login_required
def update_assets():
    """Update assets configuration (creates new version)"""
    try:
        data = request.get_json()
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get current version
                cur.execute("""
                    SELECT version
                    FROM assets
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                current_version = cur.fetchone()
                next_version = (current_version[0] + 1) if current_version else 1
                
                # Archive current version
                cur.execute("UPDATE assets SET is_active = FALSE WHERE is_active = TRUE")
                
                # Insert new version
                cur.execute("""
                    INSERT INTO assets (
                        work_roles,
                        work_lines,
                        work_areas,
                        departments,
                        shifts_names,
                        version,
                        notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, version, created_at
                """, (
                    data.get('workRoles', []),
                    data.get('workLines', []),
                    data.get('workAreas', []),
                    data.get('departments', []),
                    data.get('shiftsNames', []),
                    next_version,
                    data.get('notes')
                ))
                
                result = cur.fetchone()
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Assets configuration updated',
                    'id': result[0],
                    'version': result[1],
                    'createdAt': result[2].isoformat() if result[2] else None
                })
        
    except Exception as e:
        logger.error(f"Update assets error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/assets/history', methods=['GET'])
@login_required
def get_assets_history():
    """Get all assets configurations (version history)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id,
                        version,
                        is_active,
                        created_at,
                        updated_at,
                        notes,
                        array_length(work_roles, 1) as roles_count,
                        array_length(work_lines, 1) as lines_count,
                        array_length(work_areas, 1) as areas_count,
                        array_length(departments, 1) as departments_count,
                        array_length(shifts_names, 1) as shifts_count
                    FROM assets
                    ORDER BY created_at DESC
                """)
                
                history = []
                for row in cur.fetchall():
                    history.append({
                        'id': row[0],
                        'version': row[1],
                        'isActive': row[2],
                        'createdAt': row[3].isoformat() if row[3] else None,
                        'updatedAt': row[4].isoformat() if row[4] else None,
                        'notes': row[5],
                        'counts': {
                            'workRoles': row[6] or 0,
                            'workLines': row[7] or 0,
                            'workAreas': row[8] or 0,
                            'departments': row[9] or 0,
                            'shiftsNames': row[10] or 0
                        }
                    })
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        logger.error(f"Get assets history error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/assets/<int:asset_id>', methods=['GET'])
@login_required
def get_asset_by_id(asset_id):
    """Get specific assets configuration by ID"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id,
                        work_roles,
                        work_lines,
                        work_areas,
                        departments,
                        shifts_names,
                        version,
                        is_active,
                        created_at,
                        updated_at,
                        notes
                    FROM assets
                    WHERE id = %s
                """, (asset_id,))
                
                result = cur.fetchone()
                
                if not result:
                    return jsonify({
                        'success': False,
                        'error': 'Asset configuration not found'
                    }), 404
                
                return jsonify({
                    'success': True,
                    'asset': {
                        'id': result[0],
                        'workRoles': result[1] or [],
                        'workLines': result[2] or [],
                        'workAreas': result[3] or [],
                        'departments': result[4] or [],
                        'shiftsNames': result[5] or [],
                        'version': result[6],
                        'isActive': result[7],
                        'createdAt': result[8].isoformat() if result[8] else None,
                        'updatedAt': result[9].isoformat() if result[9] else None,
                        'notes': result[10]
                    }
                })
        
    except Exception as e:
        logger.error(f"Get asset by ID error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5005))
    app.run(host='0.0.0.0', port=port, debug=False)

