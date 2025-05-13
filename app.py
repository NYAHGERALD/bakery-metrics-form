from flask import Flask, render_template, request, redirect, url_for, session, flash
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = 'v@^i4N9r#2LjkU7!XzYp0aE&$RmW'
app.permanent_session_lifetime = timedelta(minutes=15)

@app.before_request
def make_session_permanent():
    session.permanent = True

# Google Sheets setup
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/credentials.json', scope)
client = gspread.authorize(creds)
SPREADSHEET_ID = '15YC7uMlrecjNDuwyT1fzRhipxmtjjzhfibxnLxoYkoQ'

# Helper to get latest week sheet name
def get_latest_week_sheet():
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet_names = spreadsheet.worksheets()
    import re
    pattern = re.compile(r"(\d{2}-\d{2}-\d{4})_\d{2}-\d{2}-\d{4}")

    def extract_date(sheet):
        match = pattern.match(sheet.title)
        if match:
            return datetime.strptime(match.group(1), "%m-%d-%Y")
        return datetime.min

    sorted_sheets = sorted(sheet_names, key=extract_date, reverse=True)
    return sorted_sheets[0].title if sorted_sheets else ""

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/verify-email', methods=['POST'])
def verify_email():
    email = request.form.get('email')
    if not email:
        flash("Email is required.", "error")
        return redirect(url_for('home'))
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        email_list = sheet.col_values(1)[1:]  # Skip header
        if email.lower() in [e.lower() for e in email_list]:
            session['verified'] = True
            session['user_email'] = email
            return redirect(url_for('form'))
        else:
            flash("Sorry, this email has no permission for submitting Bakery metrics. Please contact your application administrator for assistance.", "danger")
            return redirect(url_for('home'))
    except Exception as e:
        flash(f"Something went wrong: {e}", "error")
        return redirect(url_for('home'))

@app.route('/form')
def form():
    if not session.get('verified'):
        return redirect(url_for('home'))
    latest_week = get_latest_week_sheet()
    return render_template('form.html', latest_week=latest_week)

@app.route('/submit', methods=['POST'])
def submit():
    if not session.get('verified'):
        return redirect(url_for('home'))

    week = request.form.get('week')
    day = request.form.get('day')
    submitted_by = request.form.get('submitted_by')
    local_timestamp = request.form.get('local_timestamp')

    column_map = {
        "Monday": "D",
        "Tuesday": "E",
        "Wednesday": "F",
        "Thursday": "G",
        "Friday": "H"
    }

    if not week or not day or day not in column_map:
        return "❌ Invalid week or day provided.", 400

    col = column_map[day]
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(week)
    except Exception as e:
        return f"❌ Sheet/tab not found: {week}. Error: {e}", 404

    metric_map = {
        "oee_–_die_cut_1_(1st_shift)": 6,
        "oee_–_die_cut_2_(1st_shift)": 7,
        "pounds_–_die_cut_1_(1st_shift)": 9,
        "pounds_–_die_cut_2_(1st_shift)": 10,
        "waste_–_die_cut_1_(1st_shift)": 12,
        "waste_–_die_cut_2_(1st_shift)": 13,
        "oee_–_die_cut_1_(2nd_shift)": 20,
        "oee_–_die_cut_2_(2nd_shift)": 21,
        "pounds_–_die_cut_1_(2nd_shift)": 23,
        "pounds_–_die_cut_2_(2nd_shift)": 24,
        "waste_–_die_cut_1_(2nd_shift)": 26,
        "waste_–_die_cut_2_(2nd_shift)": 27
    }

    updated = False
    for field_name, row in metric_map.items():
        value = request.form.get(field_name)
        if value and value.strip():
            current_value = sheet.acell(f"{col}{row}").value
            if not current_value or current_value.strip() == "0":
                sheet.update_acell(f"{col}{row}", value)
                updated = True

    return render_template('confirmation.html', success=updated, name=submitted_by, timestamp=local_timestamp)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)



