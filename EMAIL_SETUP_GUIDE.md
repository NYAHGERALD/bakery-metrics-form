# Email Notification System Setup Guide

## Overview
The bakery metrics application now includes an automated email notification system that sends professional email alerts to all active users whenever metrics forms are submitted.

## Email Configuration Setup

### 1. Gmail App Password Setup
To use Gmail SMTP, you need to create an App Password:

1. Go to your Google Account settings: https://myaccount.google.com/
2. Navigate to "Security" → "App passwords"
3. Select "Mail" as the app and your device
4. Google will generate a 16-character app password
5. Copy this password for use in the .env file

### 2. Environment Configuration
Update your `.env` file with the correct email password:

```
# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=nyah.gerard@gmail.com
MAIL_PASSWORD=YOUR_16_CHARACTER_APP_PASSWORD_HERE
MAIL_DEFAULT_SENDER=nyah.gerard@gmail.com
```

Replace `YOUR_16_CHARACTER_APP_PASSWORD_HERE` with the actual app password from Gmail.

## Features

### Automated Email Notifications
- **Trigger**: Sent automatically when metrics forms are successfully submitted
- **Recipients**: All active users in the system
- **Content**: Professional "Do Not Reply" email with OEE and Waste metrics data
- **Format**: HTML email with clean, professional styling

### Email Content Includes:
- Week and day information
- First Shift metrics (OEE percentages, production pounds, waste pounds)
- Second Shift metrics (OEE percentages, production pounds, waste pounds)
- Submitter information
- Professional styling with company branding

### Technical Features:
- **Asynchronous sending**: Emails are sent in background threads to prevent blocking the web interface
- **Error handling**: Email failures don't break form submission functionality
- **Logging**: All email activities are logged for troubleshooting
- **Professional formatting**: Clean HTML emails with consistent styling

## Testing

### Test Route (Development Only)
A test route is available at `/test-email` for development testing:
- Access while logged in to test email functionality
- Sends sample metrics data to all active users
- Returns JSON response indicating success/failure

**Note**: Remove the test route in production for security.

### Production Testing
1. Submit a real metrics form through the normal interface
2. Check that all active users receive the email notification
3. Verify email content and formatting

## Troubleshooting

### Common Issues:
1. **Email not sending**: Check app password configuration
2. **Authentication errors**: Verify Gmail app password is correct
3. **No recipients**: Ensure users have valid email addresses and are marked as active

### Logs:
Check application logs for email-related errors:
- Email configuration issues
- SMTP connection problems
- Recipient validation errors

## Security Notes
- Uses Gmail's secure SMTP with TLS encryption
- App passwords are more secure than regular passwords
- "Do Not Reply" sender to prevent email loops
- No sensitive data stored in email content beyond metrics

## Production Deployment
When deploying to production:
1. Set proper app password in environment variables
2. Remove or secure the test email route
3. Verify firewall settings allow SMTP connections
4. Test with a small group before full deployment
