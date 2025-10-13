<?php
/**
 * Main Entry Point
 * Handles webhook requests and provides basic web interface
 */

// Error reporting for development
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Set up error logging
ini_set('log_errors', 1);
ini_set('error_log', dirname(__DIR__) . '/logs/error.log');

// Ensure logs directory exists
if (!is_dir(dirname(__DIR__) . '/logs')) {
    mkdir(dirname(__DIR__) . '/logs', 0755, true);
}

require_once dirname(__DIR__) . '/src/WebhookHandler.php';

// Handle different request methods
$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'POST') {
    handleWebhookRequest();
} else {
    showWebInterface();
}

/**
 * Handle incoming webhook POST requests
 */
function handleWebhookRequest()
{
    // Set JSON response header
    header('Content-Type: application/json');
    
    try {
        // Get POST data
        $input = file_get_contents('php://input');
        $webhookData = json_decode($input, true);
        
        if (json_last_error() !== JSON_ERROR_NONE) {
            http_response_code(400);
            echo json_encode(['error' => 'Invalid JSON data']);
            return;
        }
        
        // Log incoming webhook
        error_log("Webhook received: " . $input);
        
        // Process webhook
        $handler = new WebhookHandler();
        $result = $handler->processWebhook($webhookData);
        
        // Return result
        if ($result['success']) {
            http_response_code(200);
        } else {
            http_response_code(422); // Unprocessable Entity
        }
        
        echo json_encode($result);
        
    } catch (Exception $e) {
        error_log("Webhook error: " . $e->getMessage());
        http_response_code(500);
        echo json_encode(['error' => 'Internal server error']);
    }
}

/**
 * Show basic web interface
 */
function showWebInterface()
{
    ?>
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dropbox URL Processor</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
            .webhook-url { background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace; word-break: break-all; }
            .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
            .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
            button { background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #005a87; }
            input, textarea { width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 3px; }
            .authorized-emails { background: #f8f9fa; padding: 15px; border-radius: 5px; }
            .authorized-emails ul { margin: 0; padding-left: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔗 Dropbox URL Processor</h1>
            
            <div class="section">
                <h2>📡 Webhook Endpoint</h2>
                <p>Send POST requests to this endpoint with email data:</p>
                <div class="webhook-url">
                    <?php echo 'https://' . $_SERVER['HTTP_HOST'] . $_SERVER['REQUEST_URI']; ?>
                </div>
                
                <h3>Expected JSON Format:</h3>
                <pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto;">
{
    "microsoft_graph_email_id": "email_id",
    "subject": "Email Subject",
    "receivedDateTime": "Mon, 01 Jan 2024 12:00:00 +0000",
    "sender_address": "Name &lt;email@domain.com&gt;",
    "bodyPreview": "Email preview"
}</pre>
            </div>

            <div class="section">
                <h2>✅ Authorized Senders</h2>
                <div class="authorized-emails">
                    <p>Only emails from these addresses will be processed:</p>
                    <ul>
                        <?php
                        require_once dirname(__DIR__) . '/src/AuthorizedSenders.php';
                        foreach (AuthorizedSenders::getAuthorizedEmails() as $email) {
                            echo "<li>{$email}</li>";
                        }
                        ?>
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2>🔧 Manual Testing</h2>
                <form method="post" action="test.php" style="margin-top: 15px;">
                    <label>Sender Email:</label>
                    <input type="email" name="sender" placeholder="test@media-solution.fr" required>
                    
                    <label>Subject:</label>
                    <input type="text" name="subject" placeholder="Test Email Subject" required>
                    
                    <label>Date:</label>
                    <input type="text" name="date" placeholder="Mon, 01 Jan 2024 12:00:00 +0000" required>
                    
                    <button type="submit">🧪 Test Processing</button>
                </form>
            </div>

            <div class="section">
                <h2>📊 Dashboard</h2>
                <p><a href="dashboard.php" style="color: #007cba; text-decoration: none;">→ View Processing Dashboard</a></p>
            </div>

            <div class="section">
                <h2>ℹ️ System Information</h2>
                <div class="info">
                    <strong>Status:</strong> System Ready<br>
                    <strong>PHP Version:</strong> <?php echo PHP_VERSION; ?><br>
                    <strong>IMAP Extension:</strong> <?php echo extension_loaded('imap') ? '✅ Loaded' : '❌ Not Available'; ?><br>
                    <strong>PDO MySQL:</strong> <?php echo extension_loaded('pdo_mysql') ? '✅ Loaded' : '❌ Not Available'; ?>
                </div>
            </div>
        </div>
    </body>
    </html>
    <?php
}
?>
