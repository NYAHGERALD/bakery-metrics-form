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
        email_list = sheet.col_values(1)[1:]
        if email.lower() in [e.lower() for e in email_list]:
            index = [e.lower() for e in email_list].index(email.lower()) + 2  # row index, A2 = index 2
            first_name = sheet.cell(index, 2).value  # Column B
            last_name = sheet.cell(index, 3).value   # Column C
            full_name = f"{first_name} {last_name}"
            
            session['verified'] = True
            session['user_email'] = email
            session['user_full_name'] = full_name
            return redirect(url_for('form'))
        else:
            flash("Sorry, this email has no permission for submitting Bakery metrics.", "danger")
            return redirect(url_for('home'))
    except Exception as e:
        flash(f"Something went wrong: {e}", "error")
        return redirect(url_for('home'))

@app.route('/form')
def form():
    if not session.get('verified'):
        return redirect(url_for('home'))
    latest_week = get_latest_week_sheet()
    return render_template(
        'form.html',
        latest_week=latest_week,
        user_full_name=session.get('user_full_name', 'User')
    )


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
    return render_template(
        'report.html',
        week_names=week_names,
        default_week=default_week,
        user_full_name=session.get('user_full_name', 'User')
    )


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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)



