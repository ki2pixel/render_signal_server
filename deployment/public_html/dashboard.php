<?php
/**
 * Dashboard
 * Monitoring and statistics interface
 */

// Error reporting
error_reporting(E_ALL);
ini_set('display_errors', 1);
ini_set('log_errors', 1);
ini_set('error_log', dirname(__DIR__) . '/logs/error.log');

require_once dirname(__DIR__) . '/src/WebhookHandler.php';

// Get statistics (with safe error handling)
try {
    $handler = new WebhookHandler();
    $stats = $handler->getStatistics();
} catch (Exception $e) {
    // Do not expose sensitive details. Guide the operator to server logs.
    $stats = [
        'recent_logs' => [],
        'authorized_senders' => [],
        'error' => 'Erreur de connexion au service de base de données. Consultez le fichier de logs côté serveur (logs/error.log) pour plus de détails et vérifiez la configuration database.php.'
    ];
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Dropbox URL Processor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px; }
        .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #dee2e6; }
        .stat-number { font-size: 2em; font-weight: bold; color: #007cba; }
        .stat-label { color: #6c757d; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; font-weight: bold; }
        .url-cell { max-width: 300px; word-break: break-all; }
        .timestamp { color: #6c757d; font-size: 0.9em; }
        .back-link { color: #007cba; text-decoration: none; margin-bottom: 20px; display: inline-block; }
        .back-link:hover { text-decoration: underline; }
        .refresh-btn { background: #28a745; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; float: right; }
        .refresh-btn:hover { background: #218838; }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; border: 1px solid #f5c6cb; }
        .empty-state { text-align: center; color: #6c757d; padding: 40px; }
    </style>
</head>
<body>
    <div class="container">
        <a href="index.php" class="back-link">← Back to Main</a>
        
        <h1>📊 Processing Dashboard</h1>
        
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        
        <?php if (isset($stats['error'])): ?>
            <div class="error">
                <strong>Error:</strong> <?php echo htmlspecialchars($stats['error']); ?>
            </div>
        <?php endif; ?>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number"><?php echo count($stats['recent_logs']); ?></div>
                <div class="stat-label">Recent Logs</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-number"><?php echo count($stats['authorized_senders']); ?></div>
                <div class="stat-label">Authorized Senders</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-number"><?php echo date('Y-m-d H:i:s'); ?></div>
                <div class="stat-label">Last Updated</div>
            </div>
        </div>

        <div class="section">
            <h2>📋 Recent Dropbox URL Logs</h2>
            
            <?php if (empty($stats['recent_logs'])): ?>
                <div class="empty-state">
                    <p>No Dropbox URLs have been processed yet.</p>
                    <p>Send a webhook request or use the manual testing feature to see logs here.</p>
                </div>
            <?php else: ?>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Dropbox URL</th>
                            <th>Timestamp</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($stats['recent_logs'] as $log): ?>
                            <tr>
                                <td><?php echo htmlspecialchars($log['id']); ?></td>
                                <td class="url-cell">
                                    <a href="<?php echo htmlspecialchars($log['url_dropbox']); ?>" 
                                       target="_blank" 
                                       style="color: #007cba; text-decoration: none;">
                                        <?php echo htmlspecialchars($log['url_dropbox']); ?>
                                    </a>
                                </td>
                                <td class="timestamp"><?php echo htmlspecialchars($log['timestamp']); ?></td>
                                <td class="timestamp"><?php echo htmlspecialchars($log['created_at']); ?></td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>

        <div class="section">
            <h2>✅ Authorized Email Addresses</h2>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                <ul style="margin: 0; padding-left: 20px;">
                    <?php foreach ($stats['authorized_senders'] as $email): ?>
                        <li><?php echo htmlspecialchars($email); ?></li>
                    <?php endforeach; ?>
                </ul>
            </div>
        </div>

        <div class="section">
            <h2>🔧 System Status</h2>
            <table>
                <tr>
                    <td><strong>PHP Version</strong></td>
                    <td><?php echo PHP_VERSION; ?></td>
                </tr>
                <tr>
                    <td><strong>IMAP Extension</strong></td>
                    <td><?php echo extension_loaded('imap') ? '✅ Available' : '❌ Not Available'; ?></td>
                </tr>
                <tr>
                    <td><strong>PDO MySQL Extension</strong></td>
                    <td><?php echo extension_loaded('pdo_mysql') ? '✅ Available' : '❌ Not Available'; ?></td>
                </tr>
                <tr>
                    <td><strong>Error Log</strong></td>
                    <td><?php echo file_exists(__DIR__ . '/../logs/error.log') ? '✅ Available' : '❌ Not Found'; ?></td>
                </tr>
                <tr>
                    <td><strong>Database Connection</strong></td>
                    <td>
                        <?php
                        try {
                            $testLogger = new DatabaseLogger();
                            echo '✅ Connected';
                        } catch (Exception $e) {
                            echo '❌ Failed: ' . htmlspecialchars($e->getMessage());
                        }
                        ?>
                    </td>
                </tr>
            </table>
        </div>

        <div class="section">
            <h2>📝 Recent Error Logs</h2>
            <?php
            $errorLogPath = dirname(__DIR__) . '/logs/error.log';
            if (file_exists($errorLogPath)) {
                $errorLines = array_slice(file($errorLogPath), -10);
                if (!empty($errorLines)) {
                    echo '<pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; max-height: 200px; overflow-y: auto;">';
                    foreach (array_reverse($errorLines) as $line) {
                        echo htmlspecialchars($line);
                    }
                    echo '</pre>';
                } else {
                    echo '<p style="color: #6c757d;">No recent errors logged.</p>';
                }
            } else {
                echo '<p style="color: #6c757d;">Error log file not found.</p>';
            }
            ?>
        </div>
    </div>

    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
