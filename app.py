from flask import Flask, render_template, request, redirect, url_for, session, flash
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from flask import jsonify
from datetime import datetime


day_column_map = {
    "Monday": "D",
    "Tuesday": "E",
    "Wednesday": "F",
    "Thursday": "G",
    "Friday": "H"
}

shift_rows = {
    "First Shift": {
        "oee1": 6, "oee2": 7, "oeeTotal": 8,
        "pounds1": 9, "pounds2": 10, "poundsTotal": 11,
        "waste1": 12, "waste2": 13
    },
    "Second Shift": {
        "oee1": 20, "oee2": 21, "oeeTotal": 22,
        "pounds1": 23, "pounds2": 24, "poundsTotal": 25,
        "waste1": 26, "waste2": 27
    },
    "Both Shift": {
        "oee1": 34, "oee2": 35, "oeeTotal": 36,
        "pounds1": 37, "pounds2": 38, "poundsTotal": 39,
        "waste1": 40, "waste2": 41, "wasteTotal": 42
    }
}




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
#creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
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

@app.route('/report')
def report():
    if not session.get('verified'):
        return redirect(url_for('home'))

    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    week_names = []

    for ws in spreadsheet.worksheets():
        title = ws.title
        if "_" in title and len(title.split("_")) == 2:
            week_names.append(title)

    def extract_week_start(week_name):
        try:
            start_str = week_name.split("_")[0]
            return datetime.strptime(start_str, "%m-%d-%Y")
        except Exception:
            return datetime.min  # fallback for unexpected titles

    week_names.sort(key=extract_week_start, reverse=True)


    default_week = week_names[0] if week_names else ""
    return render_template('report.html', week_names=week_names, default_week=default_week)


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



def get_week_average_column(sheet, shift):
    """
    Pulls values from Column I based on the shift:
    First Shift: I6:I14
    Second Shift: I20:I28
    Both Shift: I34:I42
    Returns a dictionary of values keyed by line id
    """
    shift_ranges = {
        "First Shift": (6, 14),
        "Second Shift": (20, 28),
        "Both Shift": (34, 42)
    }

    start, end = shift_ranges[shift]
    values = []
    for row in range(start, end + 1):
        try:
            val = sheet.acell(f"I{row}").value
            values.append(float(val) if val and val.strip() else "-")
        except:
            values.append("-")

    # Map to corresponding report rows
    return {
        "oee1Avg": values[0],
        "oee2Avg": values[1],
        "oeeTotalAvg": values[2],
        "pounds1Avg": values[3],
        "pounds2Avg": values[4],
        "poundsTotalAvg": values[5],
        "waste1Avg": values[6],
        "waste2Avg": values[7],
        "wasteTotalAvg": values[8]
    }





@app.route('/api/report')
def api_report():
    if not session.get('verified'):
        return jsonify({"error": "unauthorized"}), 401

    week = request.args.get('week')
    day = request.args.get('day')
    shift = request.args.get('shift')

    if not week or day not in day_column_map or shift not in shift_rows:
        return jsonify({"error": "invalid parameters"}), 400

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(week)
        col = day_column_map[day]
        rows = shift_rows[shift]

        def val(cell):
            try:
                return float(sheet.acell(cell).value)
            except:
                return 0

        def get(key): return val(f"{col}{rows[key]}")

        oee1 = get("oee1")
        oee2 = get("oee2")
        oeeTotal = get("oeeTotal")

        pounds1 = get("pounds1")
        pounds2 = get("pounds2")
        poundsTotal = get("poundsTotal")

        waste1_lb = get("waste1")
        waste2_lb = get("waste2")

        if shift == "Both Shift":
            wasteTotal = get("wasteTotal")
        else:
            w1 = (waste1_lb / pounds1 * 100) if pounds1 else 0
            w2 = (waste2_lb / pounds2 * 100) if pounds2 else 0
            wasteTotal = round((w1 + w2) / 2, 2)
        
        waste1 = round((waste1_lb / pounds1 * 100), 2) if pounds1 > 0 else 0
        waste2 = round((waste2_lb / pounds2 * 100), 2) if pounds2 > 0 else 0

        week_avg = get_week_average_column(sheet, shift)


        return jsonify({
            "oee1": oee1, "oee2": oee2, "oeeTotal": oeeTotal,
            "pounds1": pounds1, "pounds2": pounds2, "poundsTotal": poundsTotal,
            "waste1": waste1, "waste2": waste2, "wasteTotal": wasteTotal,
            **week_avg  # include WEEK AVERAGE values dynamically
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)



