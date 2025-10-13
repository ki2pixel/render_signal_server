# Upload Checklist for webhook.kidpixel.fr

## Files to Upload to public_html/
- [ ] index.php
- [ ] dashboard.php  
- [ ] test.php
- [ ] .htaccess

## Files to Upload to /home/kidpixel/webhook.kidpixel.fr/
- [ ] config/database.php
- [ ] config/email.php
- [ ] src/WebhookHandler.php
- [ ] src/EmailProcessor.php
- [ ] src/DropboxUrlProcessor.php
- [ ] src/DatabaseLogger.php
- [ ] src/AuthorizedSenders.php
 - [ ] src/FromSmashUrlProcessor.php
 - [ ] src/SwissTransferUrlProcessor.php
- [ ] database/schema.sql
- [ ] database/enhanced-schema.sql
- [ ] logs/ directory (empty)
- [ ] install.php (for testing)
- [ ] verify-compatibility.php (for testing)

## Post-Upload Tasks
- [ ] Set directory permissions (755 for directories, 644 for files)
- [ ] Make logs directory writable
- [ ] Test installation via install.php
- [ ] Verify webhook endpoint works
- [ ] Remove install.php from public_html
- [ ] Test webhook with real data

## Final URLs
- Webhook: https://webhook.kidpixel.fr/index.php
- Dashboard: https://webhook.kidpixel.fr/dashboard.php
- Testing: https://webhook.kidpixel.fr/test.php
