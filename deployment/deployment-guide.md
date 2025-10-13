# Deployment Guide for webhook.kidpixel.fr

## 🚀 Secure Deployment Instructions

### Step 1: Create Directory Structure
```bash
# On your server, create the main project directory
mkdir -p /home/kidpixel/webhook.kidpixel.fr
cd /home/kidpixel/webhook.kidpixel.fr

# Create secure directories (outside web root)
mkdir -p config src logs database

# The public_html directory should already exist as your document root
# If not, create it:
mkdir -p public_html
```

### Step 2: Upload Files to Correct Locations

**Upload to `/home/kidpixel/webhook.kidpixel.fr/public_html/`:**
- `public/index.php` → `public_html/index.php`
- `public/dashboard.php` → `public_html/dashboard.php`
- `public/test.php` → `public_html/test.php`

**Upload to `/home/kidpixel/webhook.kidpixel.fr/config/`:**
- `config/database.php`
- `config/email.php`

**Upload to `/home/kidpixel/webhook.kidpixel.fr/src/`:**
- `src/WebhookHandler.php`
- `src/EmailProcessor.php`
- `src/DropboxUrlProcessor.php`
- `src/DatabaseLogger.php`
- `src/AuthorizedSenders.php`

**Upload to `/home/kidpixel/webhook.kidpixel.fr/`:**
- `install.php`
- `verify-compatibility.php`
- `README.md`
- `database/schema.sql` → `database/schema.sql`
- `database/enhanced-schema.sql` → `database/enhanced-schema.sql`

### Step 3: Set File Permissions
```bash
# Set directory permissions
chmod 755 /home/kidpixel/webhook.kidpixel.fr
chmod 755 /home/kidpixel/webhook.kidpixel.fr/public_html
chmod 755 /home/kidpixel/webhook.kidpixel.fr/config
chmod 755 /home/kidpixel/webhook.kidpixel.fr/src
chmod 755 /home/kidpixel/webhook.kidpixel.fr/database
chmod 755 /home/kidpixel/webhook.kidpixel.fr/logs

# Set file permissions
chmod 644 /home/kidpixel/webhook.kidpixel.fr/public_html/*.php
chmod 644 /home/kidpixel/webhook.kidpixel.fr/config/*.php
chmod 644 /home/kidpixel/webhook.kidpixel.fr/src/*.php
chmod 644 /home/kidpixel/webhook.kidpixel.fr/database/*.sql

# Make logs directory writable
chmod 755 /home/kidpixel/webhook.kidpixel.fr/logs
```

### Step 4: Final Webhook URL
**Your webhook endpoint will be:**
```
https://webhook.kidpixel.fr/index.php
```

**Dashboard URL:**
```
https://webhook.kidpixel.fr/dashboard.php
```

**Testing URL:**
```
https://webhook.kidpixel.fr/test.php
```

### Step 5: Verification
1. Visit: `https://webhook.kidpixel.fr/install.php` (upload install.php to public_html temporarily)
2. Run compatibility check
3. Remove install.php from public_html after verification
