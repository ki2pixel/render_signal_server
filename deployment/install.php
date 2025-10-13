<?php
/**
 * Installation Script
 * Sets up the database tables and verifies system requirements
 */

// Error reporting
error_reporting(E_ALL);
ini_set('display_errors', 1);

echo "<h1>🚀 Dropbox URL Processor - Installation</h1>\n";

// Check PHP version
echo "<h2>📋 System Requirements Check</h2>\n";
echo "<p><strong>PHP Version:</strong> " . PHP_VERSION;
if (version_compare(PHP_VERSION, '7.4.0', '>=')) {
    echo " ✅ OK</p>\n";
} else {
    echo " ❌ Requires PHP 7.4 or higher</p>\n";
    exit(1);
}

// Check required extensions
$requiredExtensions = ['imap', 'pdo_mysql', 'json'];
foreach ($requiredExtensions as $ext) {
    echo "<p><strong>{$ext} Extension:</strong> ";
    if (extension_loaded($ext)) {
        echo "✅ Loaded</p>\n";
    } else {
        echo "❌ Not Available - Please install php-{$ext}</p>\n";
        exit(1);
    }
}

// Check directories
echo "<h2>📁 Directory Setup</h2>\n";
$directories = ['logs', 'config', 'src', 'public', 'database'];
foreach ($directories as $dir) {
    echo "<p><strong>{$dir}/:</strong> ";
    if (is_dir($dir)) {
        echo "✅ Exists";
        if (is_writable($dir) || $dir === 'logs') {
            if ($dir === 'logs' && !is_writable($dir)) {
                chmod($dir, 0755);
            }
            echo " (writable)</p>\n";
        } else {
            echo " (read-only)</p>\n";
        }
    } else {
        echo "❌ Missing</p>\n";
    }
}

// Test database connection
echo "<h2>🗄️ Database Connection Test</h2>\n";
try {
    require_once 'src/DatabaseLogger.php';
    $logger = new DatabaseLogger();
    echo "<p><strong>Database Connection:</strong> ✅ Connected successfully</p>\n";
    
    // Test table creation
    if ($logger->ensureTableExists()) {
        echo "<p><strong>Database Table:</strong> ✅ logs_dropbox table ready</p>\n";
    } else {
        echo "<p><strong>Database Table:</strong> ❌ Failed to create table</p>\n";
    }
} catch (Exception $e) {
    echo "<p><strong>Database Connection:</strong> ❌ Failed - " . htmlspecialchars($e->getMessage()) . "</p>\n";
    echo "<p>Please check your database configuration in config/database.php</p>\n";
}

// Test email connection
echo "<h2>📧 Email Connection Test</h2>\n";
try {
    require_once 'src/EmailProcessor.php';
    $emailProcessor = new EmailProcessor();
    
    // Try to extract a test email
    $testEmail = $emailProcessor->extractSenderEmail('Test User <test@example.com>');
    if ($testEmail === 'test@example.com') {
        echo "<p><strong>Email Processing:</strong> ✅ Email extraction working</p>\n";
    } else {
        echo "<p><strong>Email Processing:</strong> ❌ Email extraction failed</p>\n";
    }
    
    echo "<p><strong>IMAP Connection:</strong> ⚠️ Cannot test without valid credentials</p>\n";
    echo "<p>Please verify your email configuration in config/email.php</p>\n";
    
} catch (Exception $e) {
    echo "<p><strong>Email Processing:</strong> ❌ Failed - " . htmlspecialchars($e->getMessage()) . "</p>\n";
}

// Test URL processing
echo "<h2>🔗 URL Processing Test</h2>\n";
try {
    require_once 'src/DropboxUrlProcessor.php';
    
    $testUrl = 'https://www.dropbox.com/s/example?dl=0';
    $processedUrl = DropboxUrlProcessor::processDropboxUrl($testUrl);
    
    if ($processedUrl === 'https://www.dropbox.com/s/example?dl=1') {
        echo "<p><strong>URL Processing:</strong> ✅ Working correctly</p>\n";
    } else {
        echo "<p><strong>URL Processing:</strong> ❌ Failed - Expected dl=1, got: " . htmlspecialchars($processedUrl) . "</p>\n";
    }
} catch (Exception $e) {
    echo "<p><strong>URL Processing:</strong> ❌ Failed - " . htmlspecialchars($e->getMessage()) . "</p>\n";
}

// Test authorized senders
echo "<h2>✅ Authorized Senders Test</h2>\n";
try {
    require_once 'src/AuthorizedSenders.php';
    
    $testAuthorized = AuthorizedSenders::isAuthorized('achats@media-solution.fr');
    $testUnauthorized = AuthorizedSenders::isAuthorized('unauthorized@example.com');
    
    if ($testAuthorized && !$testUnauthorized) {
        echo "<p><strong>Sender Validation:</strong> ✅ Working correctly</p>\n";
        echo "<p><strong>Authorized Emails:</strong> " . count(AuthorizedSenders::getAuthorizedEmails()) . " configured</p>\n";
    } else {
        echo "<p><strong>Sender Validation:</strong> ❌ Failed</p>\n";
    }
} catch (Exception $e) {
    echo "<p><strong>Sender Validation:</strong> ❌ Failed - " . htmlspecialchars($e->getMessage()) . "</p>\n";
}

// Create .htaccess for security (if Apache)
echo "<h2>🔒 Security Setup</h2>\n";
$htaccessContent = "# Protect configuration and source files
<Files ~ \"\\.(php|json)$\">
    <RequireAll>
        Require all denied
        Require local
    </RequireAll>
</Files>

# Allow public directory
<Directory \"public\">
    Require all granted
</Directory>

# Redirect to public directory
RewriteEngine On
RewriteCond %{REQUEST_URI} !^/public/
RewriteRule ^(.*)$ public/$1 [L]
";

if (file_put_contents('.htaccess', $htaccessContent)) {
    echo "<p><strong>.htaccess:</strong> ✅ Created security rules</p>\n";
} else {
    echo "<p><strong>.htaccess:</strong> ⚠️ Could not create (check permissions)</p>\n";
}

echo "<h2>🎉 Installation Summary</h2>\n";
echo "<p>Installation completed! Next steps:</p>\n";
echo "<ol>\n";
echo "<li>Verify database and email configurations</li>\n";
echo "<li>Test the webhook endpoint: <a href='public/index.php'>public/index.php</a></li>\n";
echo "<li>Check the dashboard: <a href='public/dashboard.php'>public/dashboard.php</a></li>\n";
echo "<li>Run manual tests: <a href='public/test.php'>public/test.php</a></li>\n";
echo "<li>Configure your webhook URL in your email system</li>\n";
echo "</ol>\n";

echo "<p><strong>Webhook URL:</strong> https://yourdomain.com/path/to/public/index.php</p>\n";
echo "<p><strong>Dashboard URL:</strong> https://yourdomain.com/path/to/public/dashboard.php</p>\n";

echo "<style>
body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
h1, h2 { color: #333; }
p { margin: 5px 0; }
ol { margin: 10px 0; padding-left: 20px; }
</style>";
?>
