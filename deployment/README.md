# Multi-Provider URL Processor (Dropbox, FromSmash, SwissTransfer)

A standalone web application that replicates the functionality of a Make.com automation scenario for processing Dropbox URLs from emails.

## 📋 Overview

This application processes webhook requests containing email information, retrieves emails from an IMAP server, extracts delivery URLs from supported providers (Dropbox, FromSmash, SwissTransfer), applies provider-specific transformations (Dropbox direct download), and logs them to a MySQL database.

Note: For backward compatibility with existing external systems, ALL detected URLs (including FromSmash and SwissTransfer) are stored in the existing `logs_dropbox` table using the `url_dropbox` column.

### Original Make.com Workflow Replicated:
1. **Webhook Trigger** - Receives email metadata
2. **Email Retrieval** - Fetches email from IMAP server
3. **Sender Authorization** - Validates against authorized email list
4. **URL Extraction** - Finds Dropbox URLs using regex
5. **URL Transformation** - Converts URLs to direct download format
6. **Database Logging** - Stores processed URLs with timestamps

## 🚀 Features

- **Webhook Endpoint** - Accepts POST requests with email data
- **IMAP Integration** - Connects to inbox.lt email server
- **Authorized Senders** - Validates emails against whitelist
- **Multi-Provider URL Processing** - Extracts URLs from Dropbox, FromSmash, and SwissTransfer (Dropbox URLs are transformed for direct download)
- **MySQL Logging** - Stores processed URLs with timestamps
- **Web Dashboard** - Monitor processing activity and logs
- **Manual Testing** - Test functionality without webhooks
- **Error Logging** - Comprehensive error tracking and debugging

## 📁 Project Structure

```
├── config/
│   ├── database.php      # Database configuration
│   └── email.php         # Email/IMAP configuration
├── src/
│   ├── WebhookHandler.php      # Main webhook processing logic
│   ├── EmailProcessor.php      # IMAP email retrieval
│   ├── DropboxUrlProcessor.php # Dropbox URL extraction and transformation
│   ├── FromSmashUrlProcessor.php # FromSmash URL extraction (no transform)
│   ├── SwissTransferUrlProcessor.php # SwissTransfer URL extraction (no transform)
│   ├── DatabaseLogger.php      # Database operations
│   └── AuthorizedSenders.php   # Sender validation
├── public/
│   ├── index.php         # Main entry point and webhook endpoint
│   ├── dashboard.php     # Monitoring dashboard
│   └── test.php          # Manual testing interface
├── database/
│   └── schema.sql        # Database table definitions
├── logs/                 # Error and activity logs
└── README.md            # This file
```

## ⚙️ Configuration

### Database Configuration
Edit `config/database.php`:
```php
return [
    // WARNING: Do NOT commit real credentials. Use environment variables or secure config management.
    'host' => 'YOUR_DB_HOST',
    'database' => 'YOUR_DB_NAME',
    'username' => 'YOUR_DB_USER',
    'password' => 'YOUR_DB_PASSWORD',
    // ...
];
```

### Email Configuration
Edit `config/email.php`:
```php
return [
    'imap' => [
        // WARNING: Do NOT commit real credentials. Use environment variables or secure config management.
        'host' => 'YOUR_IMAP_HOST',
        'port' => 993,
        'encryption' => 'ssl',
        'username' => 'YOUR_IMAP_USERNAME',
        'password' => 'YOUR_IMAP_PASSWORD',
        // ...
    ]
];
```

## 🔧 Installation

1. **Upload Files** - Upload all files to your web server
2. **Set Permissions** - Ensure `logs/` directory is writable
3. **Database Setup** - Run the SQL commands from `database/schema.sql`
4. **PHP Extensions** - Ensure IMAP and PDO MySQL extensions are enabled
5. **Test Installation** - Visit the web interface to verify setup

### Required PHP Extensions:
- `imap` - For email retrieval
- `pdo_mysql` - For database operations
- `json` - For webhook data processing
- `curl` - For HTTP requests (optional)

## 📡 Webhook Usage

### Endpoint
```
POST https://yourdomain.com/path/to/public/index.php
```

### Expected JSON Payload
```json
{
    "microsoft_graph_email_id": "unique_email_id",
    "subject": "Email Subject Line",
    "receivedDateTime": "Mon, 01 Jan 2024 12:00:00 +0000",
    "sender_address": "Display Name <email@domain.com>",
    "bodyPreview": "Email preview text"
}
```

### Response Format
```json
{
    "success": true,
    "message": "Successfully processed 2 Dropbox URLs",
    "processed_urls": [
        "https://www.dropbox.com/s/example1?dl=1",
        "https://www.dropbox.com/s/example2?dl=1"
    ],
    "errors": []
}
```

## ✅ Authorized Senders

Only emails from these addresses will be processed:
- achats@media-solution.fr
- camille.moine.pro@gmail.com
- a.peault@media-solution.fr
- v.lorent@media-solution.fr
- technique@media-solution.fr
- t.deslus@media-solution.fr

## 🔄 URL Processing Logic

The application replicates the Make.com URL transformation logic for Dropbox and adds URL extraction for FromSmash and SwissTransfer:

1. **Extract URLs**
   - Dropbox: `(https://www\.dropbox\.com/\S+)`
   - FromSmash: `(https?://(?:www\.)?fromsmash\.com/[A-Za-z0-9_-]+)` (case-insensitive)
   - SwissTransfer: `(https?://(?:www\.)?swisstransfer\.com/d/[A-Za-z0-9-]+)` (case-insensitive)
2. **Clean HTML Entities (Dropbox)** - Replace `&amp;` with `&`
3. **Replace dl=0 (Dropbox)** - Change `?dl=0` to `?dl=1`
4. **Handle Ampersand (Dropbox)** - Change `&dl=0` to `&dl=1`
5. **Ensure Direct Download (Dropbox)** - Add `?dl=1` or `&dl=1` if not present
6. **Logging** - For compatibility, all provider URLs are inserted into `logs_dropbox.url_dropbox`

## 📊 Monitoring

### Web Dashboard
Visit `dashboard.php` to view:
- Recent processed URLs
- System status
- Error logs
- Processing statistics

#### Dashboard Hardening
The `dashboard.php` now wraps database connection in a try/catch and displays a generic non-sensitive error message in case of failure, while logging details to `logs/error.log`. This prevents leaking credentials or server details to end users.

### Manual Testing
Use `test.php` to manually test email processing without webhooks.

Use `test-direct.php` to directly submit email `subject`, `sender_address`, and `email_content` without going through IMAP. This calls `WebhookHandler::testEmailProcessing()` and inserts detected provider URLs (Dropbox, FromSmash, SwissTransfer) into the database for verification.

## 🐛 Troubleshooting

### Common Issues

1. **IMAP Connection Failed**
   - Check email credentials in `config/email.php`
   - Verify IMAP extension is installed
   - Ensure firewall allows IMAP connections

2. **Database Connection Failed**
   - Verify database credentials in `config/database.php`
   - Check if database and table exist
   - Ensure PDO MySQL extension is installed

3. **No Emails Found**
   - Verify email exists in IMAP inbox
   - Check sender is in authorized list
   - Verify date format and search criteria

4. **No Dropbox URLs Found**
   - Check email content contains valid Dropbox URLs
   - Verify regex pattern matches URLs
   - Check email HTML/text content

### Error Logs
Check `logs/error.log` for detailed error information.

## 🔒 Security Considerations

- **Authorized Senders** - Only whitelisted email addresses are processed
- **Input Validation** - All webhook data is validated before processing
- **Error Handling** - Comprehensive error handling prevents information disclosure
- **Database Security** - Uses prepared statements to prevent SQL injection

## 📈 Performance

- **Efficient Processing** - Processes one email per webhook request
- **Database Indexing** - Optimized database queries with proper indexes
- **Error Recovery** - Graceful handling of temporary failures
- **Resource Management** - Proper cleanup of IMAP connections

## 🔄 Maintenance

### Regular Tasks
- Monitor error logs for issues
- Check database storage usage
- Verify IMAP connectivity
- Review processed URL logs

### Backup Recommendations
- Regular database backups
- Configuration file backups
- Log file rotation

## 📞 Support

For issues or questions:
1. Check the dashboard for system status
2. Review error logs in `logs/error.log`
3. Test manually using the test interface
4. Verify configuration settings
