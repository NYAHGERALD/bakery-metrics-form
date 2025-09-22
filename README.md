# Bakery Metrics Dashboard

A comprehensive Flask web application for managing bakery operations, tracking daily metrics, inventory management, and analytics.

## Features

- **Daily Metrics Tracking**: Submit and monitor bakery production metrics
- **User Management**: Multi-role user system (Admin, Supervisor, User)
- **Inventory Management**: Track ingredients and supplies
- **Global Announcements**: System-wide notifications and announcements
- **PDF Reports**: Generate detailed reports and summaries
- **Email Notifications**: Automated email system for metrics updates
- **Dashboard Analytics**: Visual charts and performance tracking

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS (Tailwind), JavaScript
- **Database**: PostgreSQL
- **Deployment**: Render.com
- **Authentication**: Session-based with bcrypt password hashing

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Node.js (for CSS compilation)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd bakery-metrics-form
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install Node.js dependencies:
```bash
npm install
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database and email configuration
```

5. Set up your virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

6. Install Google API packages (if using Google Sheets integration):
```bash
pip install google-api-python-client google-auth
```

7. Run database migrations (if applicable):
```bash
./migrate_database.sh
```

8. Start the application:
```bash
python app.py
```

The application will be available at `http://localhost:5001`

## Environment Variables

Create a `.env` file with the following variables:

```
SECRET_KEY=your-secret-key
DB_HOST=your-database-host
DB_NAME=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_PORT=5432
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-email-password
MAIL_USE_TLS=True
```

## Deployment

This application is configured for deployment on Render.com using the included `render.yaml` configuration.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
