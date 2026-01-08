<?php
/**
 * Manual Testing Interface
 * Allows manual testing of the email processing workflow
 */

// Error reporting
error_reporting(E_ALL);
ini_set('display_errors', 1);
ini_set('log_errors', 1);
ini_set('error_log', dirname(__DIR__) . '/logs/error.log');

require_once dirname(__DIR__) . '/src/WebhookHandler.php';
// Explicitly include provider processors for the standalone provider test below
require_once dirname(__DIR__) . '/src/DropboxUrlProcessor.php';
require_once dirname(__DIR__) . '/src/FromSmashUrlProcessor.php';
require_once dirname(__DIR__) . '/src/SwissTransferUrlProcessor.php';
require_once dirname(__DIR__) . '/src/WebhookTestUtils.php';

$result = null;
$error = null;
// For provider-only test (no DB writes, no IMAP)
$provResult = null; // array with keys: dropbox, fromsmash, swisstransfer, all
$provError = null;
$linksDiagnostics = null;

// Handle form submissions
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? null;

    if ($action === 'provider_only') {
        try {
            $content = filter_input(INPUT_POST, 'email_content', FILTER_UNSAFE_RAW) ?? '';
            if (trim($content) === '') {
                throw new Exception('The email content field is required');
            }

            $urlsDropbox = DropboxUrlProcessor::processAllDropboxUrls($content);
            $urlsSmash = FromSmashUrlProcessor::processAllFromSmashUrls($content);
            $urlsSwiss = SwissTransferUrlProcessor::processAllSwissTransferUrls($content);

            $all = array_values(array_unique(array_merge($urlsDropbox, $urlsSmash, $urlsSwiss)));

            $provResult = [
                'dropbox' => $urlsDropbox,
                'fromsmash' => $urlsSmash,
                'swisstransfer' => $urlsSwiss,
                'all' => $all,
            ];
        } catch (Exception $e) {
            $provError = $e->getMessage();
        }
    } elseif ($action === 'manual_imap') {
        try {
            $sender = $_POST['sender'] ?? '';
            $subject = $_POST['subject'] ?? '';
            $date = $_POST['date'] ?? '';

            if (empty($sender) || empty($subject) || empty($date)) {
                throw new Exception('All fields are required');
            }

            $handler = new WebhookHandler();
            $result = $handler->manualProcess($sender, $subject, $date);
        } catch (Exception $e) {
            $error = $e->getMessage();
        }
    }
}

$linksDiagnostics = loadWebhookLinksDiagnostics();
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manual Testing - Multi-Provider URL Processor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px; }
        .back-link { color: #007cba; text-decoration: none; margin-bottom: 20px; display: inline-block; }
        .back-link:hover { text-decoration: underline; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        button { background: #007cba; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #005a87; }
        .result { margin: 20px 0; padding: 15px; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .warning { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
        .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        .url-list { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .url-item { margin: 5px 0; word-break: break-all; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
        .diag-header { display: flex; align-items: center; gap: 10px; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: bold; text-transform: uppercase; }
        .badge-ok { background: #d4edda; color: #155724; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .badge-error { background: #f8d7da; color: #721c24; }
        details summary { cursor: pointer; font-weight: bold; }
        .example-data { background: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #ffeaa7; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <a href="index.php" class="back-link">← Back to Main</a>
        
        <h1>🧪 Manual Testing</h1>
        
        <div class="example-data">
            <h3>💡 Example Test Data</h3>
            <p><strong>Sender:</strong> achats@media-solution.fr</p>
            <p><strong>Subject:</strong> Test Dropbox Link</p>
            <p><strong>Date:</strong> <?php echo date('D, d M Y H:i:s O'); ?></p>
            <p><em>Note: Make sure the email actually exists in your IMAP inbox for testing.</em></p>
        </div>

        <form method="post">
            <input type="hidden" name="action" value="manual_imap">
            <div class="form-group">
                <label for="sender">Sender Email Address:</label>
                <input type="email" 
                       id="sender" 
                       name="sender" 
                       value="<?php echo htmlspecialchars($_POST['sender'] ?? 'achats@media-solution.fr'); ?>" 
                       placeholder="Enter sender email address"
                       required>
                <small style="color: #6c757d;">Must be from authorized senders list</small>
            </div>

            <div class="form-group">
                <label for="subject">Email Subject:</label>
                <input type="text" 
                       id="subject" 
                       name="subject" 
                       value="<?php echo htmlspecialchars($_POST['subject'] ?? 'Test Dropbox Link'); ?>" 
                       placeholder="Enter email subject"
                       required>
            </div>

            <div class="form-group">
                <label for="date">Received Date:</label>
                <input type="text" 
                       id="date" 
                       name="date" 
                       value="<?php echo htmlspecialchars($_POST['date'] ?? date('D, d M Y H:i:s O')); ?>" 
                       placeholder="Mon, 01 Jan 2024 12:00:00 +0000"
                       required>
                <small style="color: #6c757d;">Format: Day, DD Mon YYYY HH:MM:SS +ZZZZ</small>
            </div>

            <button type="submit">🔍 Test Email Processing (IMAP + DB)</button>
        </form>

        <hr style="margin: 30px 0;">

        <h2>🧪 Provider-only Extraction (No DB, No IMAP)</h2>
        <p class="info" style="padding: 10px; border-radius: 5px;">Paste any email body below. This test runs local extraction only and does not write to the database.</p>
        <form method="post">
            <input type="hidden" name="action" value="provider_only">
            <div class="form-group">
                <label for="email_content">Email Content (raw):</label>
                <textarea id="email_content" name="email_content" rows="8" placeholder="Paste email content containing provider links here (Dropbox, FromSmash, SwissTransfer)"><?php echo isset($_POST['email_content']) ? htmlspecialchars($_POST['email_content']) : '' ; ?></textarea>
            </div>
            <button type="submit">🔎 Extract URLs (No DB)</button>
        </form>

        <?php if ($error): ?>
            <div class="result error">
                <h3>❌ Error</h3>
                <p><?php echo htmlspecialchars($error); ?></p>
            </div>
        <?php endif; ?>

        <?php if ($result): ?>
            <div class="result <?php echo $result['success'] ? 'success' : 'error'; ?>">
                <h3><?php echo $result['success'] ? '✅ Success' : '❌ Failed'; ?></h3>
                <p><strong>Message:</strong> <?php echo htmlspecialchars($result['message']); ?></p>
                
                <?php if (!empty($result['processed_urls'])): ?>
                    <h4>📎 Processed URLs (All Providers):</h4>
                    <div class="url-list">
                        <?php foreach ($result['processed_urls'] as $url): ?>
                            <div class="url-item">
                                <a href="<?php echo htmlspecialchars($url); ?>" target="_blank" style="color: #007cba;">
                                    <?php echo htmlspecialchars($url); ?>
                                </a>
                            </div>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>
                
                <?php if (!empty($result['errors'])): ?>
                    <h4>⚠️ Errors:</h4>
                    <ul>
                        <?php foreach ($result['errors'] as $err): ?>
                            <li><?php echo htmlspecialchars($err); ?></li>
                        <?php endforeach; ?>
                    </ul>
                <?php endif; ?>
                
                <h4>🔍 Full Response:</h4>
                <pre><?php echo htmlspecialchars(json_encode($result, JSON_PRETTY_PRINT)); ?></pre>
            </div>
        <?php endif; ?>

        <?php if ($provError): ?>
            <div class="result error" style="margin-top: 20px;">
                <h3>❌ Provider-only Extraction Error</h3>
                <p><?php echo htmlspecialchars($provError); ?></p>
            </div>
        <?php endif; ?>

        <?php if ($provResult): ?>
            <div class="result success" style="margin-top: 20px;">
                <h3>✅ Provider-only Extraction Results</h3>
                <h4>Dropbox</h4>
                <div class="url-list">
                    <?php if (!empty($provResult['dropbox'])): foreach ($provResult['dropbox'] as $url): ?>
                        <div class="url-item"><a href="<?php echo htmlspecialchars($url); ?>" target="_blank" style="color: #007cba;"><?php echo htmlspecialchars($url); ?></a></div>
                    <?php endforeach; else: ?>
                        <p style="color:#6c757d;">No Dropbox URLs.</p>
                    <?php endif; ?>
                </div>
                <h4>FromSmash</h4>
                <div class="url-list">
                    <?php if (!empty($provResult['fromsmash'])): foreach ($provResult['fromsmash'] as $url): ?>
                        <div class="url-item"><a href="<?php echo htmlspecialchars($url); ?>" target="_blank" style="color: #007cba;"><?php echo htmlspecialchars($url); ?></a></div>
                    <?php endforeach; else: ?>
                        <p style="color:#6c757d;">No FromSmash URLs.</p>
                    <?php endif; ?>
                </div>
                <h4>SwissTransfer</h4>
                <div class="url-list">
                    <?php if (!empty($provResult['swisstransfer'])): foreach ($provResult['swisstransfer'] as $url): ?>
                        <div class="url-item"><a href="<?php echo htmlspecialchars($url); ?>" target="_blank" style="color: #007cba;"><?php echo htmlspecialchars($url); ?></a></div>
                    <?php endforeach; else: ?>
                        <p style="color:#6c757d;">No SwissTransfer URLs.</p>
                    <?php endif; ?>
                </div>
                <h4>Combined (deduplicated)</h4>
                <div class="url-list">
                    <?php if (!empty($provResult['all'])): foreach ($provResult['all'] as $url): ?>
                        <div class="url-item"><a href="<?php echo htmlspecialchars($url); ?>" target="_blank" style="color: #007cba;"><?php echo htmlspecialchars($url); ?></a></div>
                    <?php endforeach; else: ?>
                        <p style="color:#6c757d;">No URLs detected.</p>
                    <?php endif; ?>
                </div>
            </div>
        <?php endif; ?>

        <?php if ($linksDiagnostics): ?>
            <?php
                $diagStatus = $linksDiagnostics['status'] ?? 'error';
                $badgeClass = [
                    'ok' => 'badge-ok',
                    'warning' => 'badge-warning',
                    'error' => 'badge-error',
                ][$diagStatus] ?? 'badge-warning';
            ?>
            <div class="result info">
                <div class="diag-header">
                    <h3 style="margin: 0;">📁 Diagnostic webhook_links.json</h3>
                    <span class="badge <?php echo $badgeClass; ?>">
                        <?php echo htmlspecialchars(strtoupper($diagStatus)); ?>
                    </span>
                </div>
                <p style="margin-top: 10px;"><?php echo htmlspecialchars($linksDiagnostics['message']); ?></p>
                <p style="margin: 5px 0;"><strong>Chemin :</strong> <code><?php echo htmlspecialchars($linksDiagnostics['file']); ?></code></p>
                <?php if (!empty($linksDiagnostics['provider_counts'])): ?>
                    <p><strong>Comptage par provider :</strong></p>
                    <ul>
                        <?php foreach ($linksDiagnostics['provider_counts'] as $provider => $count): ?>
                            <li><?php echo htmlspecialchars($provider); ?> : <?php echo (int)$count; ?></li>
                        <?php endforeach; ?>
                    </ul>
                <?php endif; ?>

                <?php if ($linksDiagnostics['has_legacy_entries']): ?>
                    <div class="result warning" style="margin-top: 10px;">
                        <strong>Legacy détecté :</strong> certaines entrées utilisent encore l'ancien champ <code>url</code>.
                        Supprimez-les ou laissez le backend Python les remplacer avant de valider un offload R2.
                    </div>
                <?php endif; ?>

                <?php if (!empty($linksDiagnostics['schema_issues'])): ?>
                    <div class="result warning" style="margin-top: 10px;">
                        <strong>Incohérences de schéma détectées :</strong>
                        <ul>
                            <?php foreach ($linksDiagnostics['schema_issues'] as $issue): ?>
                                <li><?php echo htmlspecialchars($issue); ?></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>
                <?php endif; ?>

                <details style="margin-top: 10px;">
                    <summary>Voir les 5 dernières entrées</summary>
                    <?php if (!empty($linksDiagnostics['last_entries'])): ?>
                        <pre><?php echo htmlspecialchars(json_encode($linksDiagnostics['last_entries'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)); ?></pre>
                    <?php else: ?>
                        <p style="margin-top: 10px;">Aucune entrée enregistrée.</p>
                    <?php endif; ?>
                </details>

                <details style="margin-top: 10px;">
                    <summary>Contenu JSON complet</summary>
                    <pre><?php echo htmlspecialchars($linksDiagnostics['raw_json'] ?? ''); ?></pre>
                </details>

                <p style="margin-top: 15px; font-size: 14px;">
                    <strong>Checklist test R2 :</strong>
                    <ol style="margin: 10px 0 0 20px;">
                        <li>Utiliser le formulaire ci-dessus pour confirmer que le lien est détecté et loggé côté PHP.</li>
                        <li>Déposer le même email dans la messagerie pour que le poller Flask lance l'offload R2.</li>
                        <li>Actualiser cette page pour vérifier l'apparition de <code>source_url</code>/<code>r2_url</code> dans le JSON.</li>
                        <li>Contrôler les logs Render (<code>R2_TRANSFER</code>) et Cloudflare Worker pour confirmer l'upload/cleanup.</li>
                    </ol>
                </p>
            </div>
        <?php endif; ?>

        <div class="info" style="margin-top: 30px;">
            <h3>ℹ️ Testing Notes</h3>
            <ul>
                <li>The email must actually exist in your IMAP inbox (kidpixel@inbox.lt)</li>
                <li>The sender must be in the authorized senders list</li>
                <li>The email content may contain Dropbox, FromSmash or SwissTransfer URLs</li>
                <li>Check the <a href="dashboard.php" style="color: #0c5460;">dashboard</a> to see logged results</li>
                <li>View error logs if processing fails</li>
            </ul>
        </div>
    </div>
</body>
</html>
