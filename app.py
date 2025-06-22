# type: ignore

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import re
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import uuid
from flask import request, jsonify



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
app.permanent_session_lifetime = timedelta(hours=1)

@app.before_request
def make_session_permanent():
    session.permanent = True

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
#creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/credentials.json', scope)
client = gspread.authorize(creds)
SPREADSHEET_ID = '15YC7uMlrecjNDuwyT1fzRhipxmtjjzhfibxnLxoYkoQ'
SHEET_NAME = "Foreign Material Reports"
GOOGLE_DRIVE_FOLDER_ID = "1O5-wG6PWFTXI-gldzZhqknp03gxyXRyv"  # create or reuse "FM-Images" folder
# Your Spreadsheet name
SPREADSHEET_NAME = 'BAKERY METRICS_2024-2025'

drive_service = build('drive', 'v3', credentials=creds)

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


def log_submission(name, email, timestamp, message, week=None, day=None):
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("submit_logs")
        row = [name, email, timestamp, message, week, day]
        sheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print("❌ Failed to log submission:", e)


def upload_image_to_drive(image_file):
    creds_drive = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    drive_service = build('drive', 'v3', credentials=creds_drive)

    file_metadata = {
        'name': image_file.filename,
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

    image_url = f"https://drive.google.com/uc?id={uploaded_file['id']}"
    return image_url



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
        session['email'] = email  # ✅ Add this line here
        session['user_full_name'] = full_name

        if stored_password == "tortilla#" and password == "tortilla#":
            return redirect(url_for('set_password'))

        if stored_password == password:
            session['verified'] = True
            return render_template('dashboard.html')


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


@app.route('/api/submission-logs')
def get_submission_logs():
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("submit_logs")
        values = sheet.get_all_values()

        if len(values) <= 1:
            return jsonify({"logs": []})  # Empty or only header

        logs = []
        for row in values[1:]:  # Skip the header row
            logs.append({
                "name": row[0] if len(row) > 0 else '',
                "email": row[1] if len(row) > 1 else '',
                "timestamp": row[2] if len(row) > 2 else '',
                "message": row[3] if len(row) > 3 else '',
                "week": row[4] if len(row) > 4 else '',
                "day": row[5] if len(row) > 5 else ''
            })

        return jsonify({"logs": logs})

    except Exception as e:
        print("⚠️ Error in /api/submission-logs:", e)
        return jsonify({"logs": [], "error": str(e)})




@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('home'))

    user_email = session['email']
    phone_number = ''
    message = None

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("user-emails")
        data = sheet.get_all_values()

        # Find the row for this user's email
        for idx, row in enumerate(data[1:], start=2):
            if row[0].strip().lower() == user_email.lower():
                phone_number = row[6] if len(row) > 6 else ""

                if request.method == 'POST':
                    submitted_phone = request.form.get('phone', '').strip()

                    if submitted_phone and submitted_phone != phone_number:
                        if not submitted_phone.startswith("+1") or len(submitted_phone) < 10:
                            message = "⚠️ Please enter a valid U.S. phone number starting with +1"
                        else:
                            sheet.update_cell(idx, 7, submitted_phone)
                            phone_number = submitted_phone
                            message = "✅ Phone number updated successfully."

                return render_template('profile.html', email=user_email, phone=phone_number, message=message)

        return "❌ User email not found.", 404

    except Exception as e:
        print("❌ Error in profile update:", e)
        return render_template('profile.html', email=user_email, phone=phone_number, message="An error occurred.")




@app.route('/chat')
def chat():
    return render_template('chat.html')




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


    message = "✅ Submission successful." if updated else "⚠️ No data was submitted (already exists)."
    
    # Log submission with extra info
    user_email = session.get('email', 'Unknown')
    log_submission(submitted_by, user_email, local_timestamp, message, week=week, day=day)


    return render_template('confirmation.html', success=updated, name=submitted_by, timestamp=local_timestamp)


@app.route('/foreign-material')
def foreign_material():
    return render_template('foreignMaterial.html')


@app.route('/dashboard')
def dashboard():
    if not session.get('verified'):
        return redirect(url_for('home'))  # Optional: protect dashboard for logged-in users only
    return render_template('dashboard.html', user_full_name=session.get('user_full_name', 'User'))



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


@app.route('/api/load-reports')
def load_reports():
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        values = sheet.get_all_values()
        header = values[0]
        report_name_col = header.index("Name your report")
        date_col = 0  # column A

        options = []
        for i, row in enumerate(values[1:], start=2):  # skip header
            name = row[report_name_col] if len(row) > report_name_col else ""
            date = row[date_col] if len(row) > date_col else ""
            if name:
                label = f"{name} - {date}"
                options.append({"label": label, "row": i})

        return jsonify({"reports": options})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/submit-foreign-material', methods=['POST'])
def submit_foreign_material():
    try:
        fields_raw = request.form.get("fields")
        if not fields_raw:
            return jsonify({"status": "error", "message": "No form data received."}), 400

        form_data = eval(fields_raw) if isinstance(fields_raw, str) else fields_raw

        # Validate it's a dictionary
        if not isinstance(form_data, dict):
            return jsonify({"status": "error", "message": "Invalid form structure."}), 400

        # Define field order
        FIELD_KEYS = [
            "reportDate", "time", "line", "department", "productName", "individualsInvolved",
            "productCode", "amount", "foreignMaterialDescription", "initials-foreignMaterialDescription", "Date-foreignMaterialDescription",
            "possibleSource", "initials-possibleSource", "date-possibleSource",
            "correctiveAction", "initials-correctiveAction", "date-correctiveAction",
            "correctiveActionImplemented", "initials-correctiveActionImplemented", "date-correctiveActionImplemented",
            "maintenanceWork", "initials-maintenanceWork",
            "ProductOnHold", "initials-ProductOnHold", "date-ProductOnHold",
            "screeningProcess", "initials-screeningProcess", "date-screeningProcess",
            "dispositionOfProduct", "initials-dispositionOfProduct", "date-dispositionOfProduct",
            "disposeDate", "initials-disposeDate",
            "re-occurring", "initials-re-occurring", "date-re-occurring",
            "corporateNotified", "date-corporateNotified",
            "reportName"
        ]

        # Create row in fixed order
        row_data = [form_data.get(key, "") for key in FIELD_KEYS]

        # Upload images and append URLs
        for file_key in request.files:
            image_file = request.files[file_key]
            if image_file:
                image_url = upload_image_to_drive(image_file)
                row_data.append(image_url)

        # ✅ ✅ THIS IS WHERE YOU PLACE IT:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        sheet.append_row(row_data, value_input_option="RAW")  # <- PLACE IT HERE

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ Error saving foreign material report:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/get-report-names', methods=['GET'])
def get_report_names():
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Foreign Material Reports")
        data = sheet.get_all_records()

        report_list = []
        for row in data:
            name = row.get("reportName", "").strip()
            date = row.get("reportDate", "").strip()
            if name and date:
                report_list.append(f"{name}-{date}")

        return jsonify({"status": "success", "reports": report_list})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/inventory")
def inventory():
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
        all_sheets = spreadsheet.worksheets()
        sheet_names = [ws.title for ws in all_sheets]

        # Filter for 3-digit or specific names
        valid_sheets = []
        for name in sheet_names:
            if (
                re.fullmatch(r"\d{3}", name) or
                name in ["150344", "Dough-Conditioner", "Beta-Tabs"]
            ):
                valid_sheets.append(name)

        return render_template("inventory.html", sheet_options=valid_sheets)
    except Exception as e:
        return f"❌ Error loading inventory sheets: {e}"




@app.route('/submit-inventory', methods=['POST'])
def submit_inventory():
    try:
        data = {
            "inventoryType": request.form.get("inventoryType", "received"),
            "item": request.form.get("item"),
            "shift": request.form.get("shift"),
            "lotNumber": request.form.get("lotNumber"),
            "numBoxes": request.form.get("numBoxes"),
            "numBags": request.form.get("numBags"),
            "doughQty": request.form.get("doughQty"),
            "betaQty": request.form.get("betaQty"),
            "weekday": datetime.now().strftime('%A'),
            "date": datetime.now().strftime('%m/%d/%Y'),
            "time": datetime.now().strftime('%I:%M:%S %p'),
            "user": session.get('email', 'unknown')
        }

        # Open the sheet by item name
        sheet = client.open(SPREADSHEET_NAME).worksheet(data['item'])

        # Get all existing rows
        all_rows = sheet.get_all_values()
        next_row = len(all_rows) + 1

        # Write to columns A–L
        row_data = [
            data["numBags"],       # A
            data["lotNumber"],     # B
            data["numBoxes"],      # C
            data["doughQty"],      # D
            data["betaQty"],       # E
            data["shift"],         # F
            data["weekday"],       # G
            data["date"],          # H
            data["time"],          # I
            data["user"],          # J
            data["inventoryType"], # K (received or returned)
            data["item"]           # L
        ]

        sheet.update(f"A{next_row}", [row_data])

        return render_template("confirmation.html", success=True, name=data["user"], timestamp=data["time"])

    except Exception as e:
        print("❌ Inventory submission error:", e)
        return render_template("confirmation.html", success=False, name="Unknown", timestamp=datetime.now())




@app.route('/get-report-data', methods=['GET'])
def get_report_data():
    try:
        report_key = request.args.get('report', '').strip()
        if not report_key:
            return jsonify({"status": "error", "message": "Missing report key."})

        report_name = report_key.split('-20')[0].strip()

        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Foreign Material Reports")
        records = sheet.get_all_records()

        for row in records:
            if row.get("reportName", "").strip() == report_name:
                # Gather all image links (assuming they are named like image0, image1, image2...)
                # Extract all image URLs from any column that includes 'image_url'
                images = []
                for key, value in row.items():
                    if 'image_url' in key.lower() and isinstance(value, str) and value.strip().startswith('http'):
                        images.append(value.strip())

                row['images'] = images
                return jsonify({"status": "success", "data": row})

        return jsonify({"status": "error", "message": "Report not found."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



@app.route('/api/weekly-metrics')
def get_weekly_metrics():
    week = request.args.get('week')

    # Handle "latest" week dynamically
    if not week or week == "latest":
        spreadsheet = client.open(SPREADSHEET_NAME)
        week_names = [ws.title for ws in spreadsheet.worksheets() if "_" in ws.title and len(ws.title.split("_")) == 2]

        def extract_week_start(week_name):
            try:
                start_str = week_name.split("_")[0]
                return datetime.strptime(start_str, "%m-%d-%Y")
            except:
                return datetime.min

        week_names.sort(key=extract_week_start, reverse=True)
        week = week_names[0] if week_names else None

        if not week:
            return jsonify({'error': 'No valid week found'}), 404

    try:
        sheet = client.open(SPREADSHEET_NAME).worksheet(week)

        # Fetch values for OEE (D36:H36)
        oee_range = sheet.get('D36:H36')[0]
        oee_data = [float(val) if val else 0 for val in oee_range]

        # Fetch values for Waste (D42:H42)
        waste_range = sheet.get('D42:H42')[0]
        waste_data = [float(val) if val else 0 for val in waste_range]

        # Fetch averages from cells I36 and I42
        oee_avg = sheet.acell('I36').value or "0"
        waste_avg = sheet.acell('I42').value or "0"

        # Fetch values for First Shift OEE (D8:H8)
        oee_first_shift_range = sheet.get('D8:H8')[0]
        oee_first_shift = [float(val) if val else 0 for val in oee_first_shift_range]

        # Fetch values for First Shift Waste (D14:H14)
        waste_first_shift_range = sheet.get('D14:H14')[0]
        waste_first_shift = [float(val) if val else 0 for val in waste_first_shift_range]

        # Fetch values for Second Shift OEE (D22:H22)
        oee_second_shift_range = sheet.get('D22:H22')[0]
        oee_second_shift = [float(val) if val else 0 for val in oee_second_shift_range]

        # Fetch values for Second Shift Waste (D28:H28)
        waste_second_shift_range = sheet.get('D28:H28')[0]
        waste_second_shift = [float(val) if val else 0 for val in waste_second_shift_range]


        return jsonify({
            'week': week,
            'oee': oee_data,
            'waste': waste_data,
            'oeeAvg': float(oee_avg),
            'wasteAvg': float(waste_avg),
            'oeeFirstShift': oee_first_shift,
            'wasteFirstShift': waste_first_shift,
            'oeeSecondShift': oee_second_shift,
            'wasteSecondShift': waste_second_shift
        })
    except Exception as e:
        print(f"❌ Error reading sheet for week '{week}':", str(e))
        return jsonify({'error': 'Unable to read sheet data'}), 500


@app.route('/inventory-overview')
def inventory_overview():
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
        all_sheets = spreadsheet.worksheets()

        # Only get relevant sheet names
        sheet_names = [ws.title for ws in all_sheets if re.fullmatch(r'\d{3}', ws.title) or ws.title in [
            "150344", "Dough-Conditioner", "Beta-Tabs"]]

        return render_template("inventory_overview.html", sheet_names=sheet_names)

    except Exception as e:
        print("❌ Error loading inventory overview page:", e)
        return "Internal Server Error", 500







@app.route('/api/inventory-sheets')
def get_inventory_sheet_names():
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
        all_sheets = spreadsheet.worksheets()

        valid_sheets = []
        for sheet in all_sheets:
            title = sheet.title.strip()
            if (
                re.fullmatch(r"\d{3}", title) or
                title in ["150344", "Dough-Conditioner", "Beta-Tabs"]
            ):
                valid_sheets.append(title)

        return jsonify({"sheets": valid_sheets})

    except Exception as e:
        print("❌ Error fetching sheet names:", e)
        return jsonify({"sheets": [], "error": str(e)})
    


@app.route('/api/inventory-overview-data')
def inventory_overview_data():
    from datetime import datetime

    sheet_param = request.args.get('sheet')
    day_filter = request.args.get('day')
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')

    rows = []

    if not sheet_param:
        return jsonify(rows=[])

    try:
        sheet = client.open(SPREADSHEET_NAME).worksheet(sheet_param)
        data = sheet.get_all_values()

        if not data or len(data) < 1:
            return jsonify(rows=[])

        def safe_float(value):
            try:
                return float(value)
            except:
                return 0

        multiplier_map = {
            "222": lambda r: safe_float(r[0]) * 6 + safe_float(r[2]) * 48,
            "221": lambda r: safe_float(r[0]) * 3.88 + safe_float(r[2]) * 46.56,
            "185": lambda r: safe_float(r[0]) * 2.85 + safe_float(r[2]) * 45.6,
            "168": lambda r: safe_float(r[0]) * 37.5,
            "171": lambda r: safe_float(r[0]) * 37.69,
            "186": lambda r: safe_float(r[0]) * 17.25,
            "203": lambda r: safe_float(r[0]) * 37.69,
            "150344": lambda r: safe_float(r[0]) * 50,
            "Dough-Conditioner": lambda r: safe_float(r[3]) * 500,
            "Beta-Tabs": lambda r: safe_float(r[4]) * 8.4
        }

        for row in data:
            if not any(cell.strip() for cell in row):
                continue
            if len(row) < 12:
                continue

            quantity = multiplier_map.get(sheet_param, lambda r: 0)(row)

            raw_date = row[7] if len(row) > 7 else ""
            try:
                parsed_date = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%Y-%m-%d")
            except:
                parsed_date = ""

            record = {
                "quantity": round(quantity, 2),
                "lot": row[1] if len(row) > 1 else "",
                "shift": row[5] if len(row) > 5 else "",
                "day": row[6] if len(row) > 6 else "",
                "date": parsed_date,
                "time": row[8] if len(row) > 8 else "",
                "user": row[9] if len(row) > 9 else "",
                "status": row[10] if len(row) > 10 else "",
                "item": row[11] if len(row) > 11 else ""
            }

            rows.append(record)

        # ✅ Apply filters **after** collecting all rows
        if day_filter:
            rows = [r for r in rows if r['day'].lower() == day_filter.lower()]
        if status_filter and status_filter != "all":
            if status_filter in ["received", "returned"]:
                rows = [r for r in rows if r['status'].lower() == status_filter]
            elif status_filter in ["first shift", "second shift"]:
                rows = [r for r in rows if r['shift'].lower() == status_filter]
        if date_filter:
            rows = [r for r in rows if r.get("date", "").strip() == date_filter]

        return jsonify(rows=rows)

    except Exception as e:
        print("❌ Error in inventory_overview_data:", e)
        return jsonify(rows=[], error=str(e)), 500








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
