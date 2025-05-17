from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import re

# --- Setup ---
day_column_map = {
    "Monday": "D", "Tuesday": "E", "Wednesday": "F", "Thursday": "G", "Friday": "H"
}

shift_data_ranges = {
    "First Shift": {"metric_range": "D6:D14", "average_range": "I6:I14"},
    "Second Shift": {"metric_range": "D20:D28", "average_range": "I20:I28"},
    "Both Shift": {"metric_range": "D34:D42", "average_range": "I34:I42"}
}

# --- Flask App Config ---
load_dotenv()
app = Flask(__name__)
app.secret_key = 'v@^i4N9r#2LjkU7!XzYp0aE&$RmW'
app.permanent_session_lifetime = timedelta(minutes=15)

@app.before_request
def make_session_permanent():
    session.permanent = True

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
#creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/credentials.json', scope)
client = gspread.authorize(creds)
SPREADSHEET_ID = '15YC7uMlrecjNDuwyT1fzRhipxmtjjzhfibxnLxoYkoQ'

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

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/verify-email', methods=['POST'])
def verify_email():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    if not email or not password:
        flash("Email and password are required.", "danger")
        return redirect(url_for('home'))

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        email_list = sheet.col_values(1)[1:]

        if email not in [e.lower() for e in email_list]:
            flash("Email not found or unauthorized.", "danger")
            return redirect(url_for('home'))

        index = [e.lower() for e in email_list].index(email) + 2
        row = sheet.row_values(index)
        first_name = row[1] if len(row) > 1 else ''
        last_name = row[2] if len(row) > 2 else ''
        full_name = f"{first_name} {last_name}"
        stored_password = row[3] if len(row) > 3 else ''

        session['user_email'] = email
        session['user_full_name'] = full_name

        if stored_password == "tortilla#" and password == "tortilla#":
            return redirect(url_for('set_password'))

        if stored_password == password:
            session['verified'] = True
            return redirect(url_for('form'))

        flash("Incorrect password.", "danger")
        return redirect(url_for('home'))

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('home'))

# ✅ Place this inside your Flask app file (e.g. app.py), preferably below your existing routes
# or wherever your other @app.route definitions are located

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template('admin_login.html')

    try:
        admin_sheet = client.open_by_key(SPREADSHEET_ID).worksheet("admin_accounts")
        data = admin_sheet.get_all_values()

        for row in data[1:]:  # Skip header
            row_email = row[0].strip().lower() if len(row) > 0 else ''
            row_password = row[3] if len(row) > 3 else ''
            if email == row_email and password == row_password:
                session['admin_verified'] = True
                session['admin_email'] = email
                return redirect(url_for('administration'))

        flash("Please check your password or email and enter again.", "danger")
        return render_template('admin_login.html')

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return render_template('admin_login.html')

@app.route('/administration')
def administration():
    if not session.get('admin_verified'):
        flash("Please log in as an admin to continue.", "danger")
        return redirect(url_for('admin_login'))

    return render_template('administration.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    # POST: Handle form submission
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    access_key = request.form.get('access_key', '').strip()

    # Validation
    if not all([first_name, last_name, email, password, confirm_password, access_key]):
        flash("All fields are required, including Access Key.", "danger")
        return render_template('register.html')

    if password != confirm_password:
        flash("Passwords do not match.", "danger")
        return render_template('register.html')

    if len(password) < 6 or not re.search(r"[@#$%&]", password):
        flash("Password must be at least 6 characters and include a special character.", "danger")
        return render_template('register.html')

    if len(access_key) < 13:
        flash("Access key must be at least 13 characters long.", "danger")
        return render_template('register.html')

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        data = sheet.get_all_values()
        access_keys = [row[5].strip() if len(row) > 5 else '' for row in data]

        if email in [e[0].strip().lower() for e in data if len(e) > 0]:
            flash("This email is already registered.", "warning")
            return render_template('register.html')

        # Check if access key exists and get row number
        if access_key not in access_keys:
            flash("Access key not valid. Please contact your manager.", "danger")
            return render_template('register.html')

        row_number = access_keys.index(access_key) + 1  # 1-based row
        sheet.update(f"A{row_number}:E{row_number}", [[email, first_name, last_name, password, access_key]])

        return render_template('confirmation.html', success=True, name=first_name)

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return render_template('register.html')



@app.route('/set-password', methods=['GET', 'POST'])
def set_password():
    if request.method == 'GET':
        return render_template('set_password.html')

    email = session.get('user_email') or request.form.get('email', '')
    email = email.strip().lower()
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Validation Checks
    if not email:
        flash("Session expired. Please log in again.", "danger")
        return render_template('password_confirmation.html', user_name=session.get('user_full_name', 'User'))

    if not old_password or not new_password or not confirm_password:
        flash("All fields are required.", "danger")
        return render_template('set_password.html')

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return render_template('set_password.html')

    if len(new_password) < 6 or not re.search(r"[@#$%&]", new_password):
        flash("Password must be at least 6 characters and include a special character (@, #, $, %, &).", "danger")
        return render_template('set_password.html')

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        data = sheet.get_all_values()

        for i, row in enumerate(data[1:], start=2):  # Skip header
            row_email = row[0].strip().lower() if len(row) > 0 else ''
            row_password = row[3] if len(row) > 3 else ''

            if row_email == email:
                if row_password == old_password:
                    sheet.update_cell(i, 4, new_password)
                    session['verified'] = True
                    flash("Password updated successfully.", "success")
                    return render_template('password_confirmation.html')

                else:
                    flash("Old password is incorrect.", "danger")
                    return render_template('set_password.html')

        flash("Email not found in our records.", "danger")
        return render_template('set_password.html')

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return render_template('set_password.html')


# --- ADMIN API ROUTES ---
@app.route('/api/register-key', methods=['POST'])
def api_register_key():
    data = request.get_json()
    key = data.get("key", "").strip()
    if len(key) < 13:
        return jsonify({"message": "Access key must be at least 13 characters.", "status": "danger"})

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        all_rows = sheet.get_all_values()

        key_exists = any(row[5] == key for row in all_rows if len(row) > 5)
        if key_exists:
            return jsonify({"message": "This key is already registered.", "status": "warning"})

        for idx, row in enumerate(all_rows, start=1):
            if len(row) < 6 or not row[5]:
                sheet.update_cell(idx, 6, key)
                return jsonify({"message": "Key successfully registered.", "status": "success"})

        next_row = len(all_rows) + 1
        sheet.update_cell(next_row, 6, key)
        return jsonify({"message": "Key successfully registered.", "status": "success"})

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}", "status": "danger"})

@app.route('/api/users')
def api_get_users():
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        data = sheet.get_all_values()[1:]

        users = []
        dropdown = []

        for row in data:
            email = row[0] if len(row) > 0 else ""
            first = row[1] if len(row) > 1 else ""
            last = row[2] if len(row) > 2 else ""
            key = row[5] if len(row) > 5 else ""

            if key:
                users.append({"email": email, "first": first, "last": last, "key": key})
                dropdown.append(f"{key}_{last}")

        return jsonify({"users": users, "dropdown": dropdown})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/remove-user', methods=['POST'])
def api_remove_user():
    data = request.get_json()
    key = data.get("key")

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        all_rows = sheet.get_all_values()

        for idx, row in enumerate(all_rows, start=1):
            if len(row) > 5 and row[5] == key:
                sheet.update(f"A{idx}:F{idx}", [["" for _ in range(6)]])
                return jsonify({"message": "This user has been removed. Thank you!", "status": "success"})

        return jsonify({"message": "Key not found.", "status": "danger"})

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}", "status": "danger"})

@app.route('/admin/report')
def admin_to_report():
    return redirect(url_for('report'))

#End of ADMIN API



@app.route('/form')
def form():
    if not session.get('verified'):
        return redirect(url_for('home'))
    latest_week = get_latest_week_sheet()
    return render_template('form.html', latest_week=latest_week, user_full_name=session.get('user_full_name', 'User'))

@app.route('/submit', methods=['POST'])
def submit():
    if not session.get('verified'):
        return redirect(url_for('home'))

    week = request.form.get('week')
    day = request.form.get('day')
    submitted_by = request.form.get('submitted_by')
    local_timestamp = request.form.get('local_timestamp')

    column_map = day_column_map

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

@app.route('/report')
def report():
    if not session.get('verified'):
        return redirect(url_for('home'))

    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    week_names = [ws.title for ws in spreadsheet.worksheets() if "_" in ws.title and len(ws.title.split("_")) == 2]

    def extract_week_start(week_name):
        try:
            start_str = week_name.split("_")[0]
            return datetime.strptime(start_str, "%m-%d-%Y")
        except:
            return datetime.min

    week_names.sort(key=extract_week_start, reverse=True)
    default_week = week_names[0] if week_names else ""
    return render_template('report.html', week_names=week_names, default_week=default_week, user_full_name=session.get('user_full_name', 'User'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/api/report')
def api_report():
    if not session.get('verified'):
        return jsonify({"error": "unauthorized"}), 401

    week = request.args.get('week')
    day = request.args.get('day')
    shift = request.args.get('shift')

    if not week or day not in day_column_map or shift not in shift_data_ranges:
        return jsonify({"error": "invalid parameters"}), 400

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(week)
        col = day_column_map[day]

        metric_range = shift_data_ranges[shift]["metric_range"].replace("D", col)
        average_range = shift_data_ranges[shift]["average_range"]

        ranges = [metric_range, average_range]
        metric_data, avg_data = sheet.batch_get(ranges)

        flat_metric = [row[0] if row else "-" for row in metric_data]
        flat_avg = [row[0] if row else "-" for row in avg_data]

        response = {
            "oee1": flat_metric[0], "oee2": flat_metric[1], "oeeTotal": flat_metric[2],
            "pounds1": flat_metric[3], "pounds2": flat_metric[4], "poundsTotal": flat_metric[5],
            "waste1": flat_metric[6], "waste2": flat_metric[7], "wasteTotal": flat_metric[8],
            "oee1Avg": flat_avg[0], "oee2Avg": flat_avg[1], "oeeTotalAvg": flat_avg[2],
            "pounds1Avg": flat_avg[3], "pounds2Avg": flat_avg[4], "poundsTotalAvg": flat_avg[5],
            "waste1Avg": flat_avg[6], "waste2Avg": flat_avg[7], "wasteTotalAvg": flat_avg[8]
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
