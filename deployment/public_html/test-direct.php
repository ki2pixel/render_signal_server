<?php
/**
 * Test direct d'extraction d'URLs sans IMAP
 * Accès: https://webhook.kidpixel.fr/test-direct.php
 */

// Error reporting
error_reporting(E_ALL);
ini_set('display_errors', 1);
ini_set('log_errors', 1);
ini_set('error_log', dirname(__DIR__) . '/logs/error.log');

require_once dirname(__DIR__) . '/src/WebhookHandler.php';
require_once dirname(__DIR__) . '/src/DropboxUrlProcessor.php';
require_once dirname(__DIR__) . '/src/FromSmashUrlProcessor.php';
require_once dirname(__DIR__) . '/src/SwissTransferUrlProcessor.php';

$result = null;
$error = null;

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        $emailContent = $_POST['email_content'] ?? '';
        $subject = $_POST['subject'] ?? 'Média Solution - Missions Recadrage - Lot 180';

        if (empty(trim($emailContent))) {
            throw new Exception('Le contenu de l\'email ne peut pas être vide');
        }

        $handler = new WebhookHandler();
        $result = $handler->testEmailProcessing($emailContent, $subject);

    } catch (Exception $e) {
        $error = $e->getMessage();
    }
}
?>
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Direct - Multi-Provider URL Processor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        textarea, input[type="text"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        button { background: #007cba; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #005a87; }
        .result { margin: 20px 0; padding: 15px; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .url-list { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .url-item { margin: 5px 0; word-break: break-all; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Test Direct d'Extraction d'URLs</h1>
        <p>Testez l'extraction d'URLs sans accès IMAP. Les URLs valides seront enregistrées en base.</p>

        <form method="post">
            <div class="form-group">
                <label for="subject">Sujet de l'email:</label>
                <input type="text"
                       id="subject"
                       name="subject"
                       value="<?php echo htmlspecialchars($_POST['subject'] ?? 'Média Solution - Missions Recadrage - Lot 180'); ?>"
                       placeholder="Sujet de l'email">
                <small>Doit contenir "Média Solution - Missions Recadrage - Lot" pour être traité</small>
            </div>

            <div class="form-group">
                <label for="email_content">Contenu de l'email:</label>
                <textarea id="email_content" name="email_content" rows="10" placeholder="Collez ici le contenu de l'email contenant des liens"><?php echo htmlspecialchars($_POST['email_content'] ?? ''); ?></textarea>
            </div>

            <button type="submit">🔍 Tester l'extraction</button>
        </form>

        <?php if ($error): ?>
            <div class="result error">
                <h3>❌ Erreur</h3>
                <p><?php echo htmlspecialchars($error); ?></p>
            </div>
        <?php endif; ?>

        <?php if ($result): ?>
            <div class="result <?php echo $result['success'] ? 'success' : 'error'; ?>">
                <h3><?php echo $result['success'] ? '✅ Succès' : '❌ Aucune URL trouvée'; ?></h3>
                <p><strong>Message:</strong> <?php echo htmlspecialchars($result['message']); ?></p>

                <?php if (!empty($result['processed_urls'])): ?>
                    <h4>📎 URLs traitées (<?php echo count($result['processed_urls']); ?>):</h4>
                    <div class="url-list">
                        <?php foreach ($result['processed_urls'] as $url): ?>
                            <div class="url-item">
                                <a href="<?php echo htmlspecialchars($url); ?>" target="_blank" style="color: #007cba;">
                                    <?php echo htmlspecialchars($url); ?>
                                </a>
                            </div>
                        <?php endforeach; ?>
                    </div>

                    <?php if (isset($result['logged_count'])): ?>
                        <p><strong>✅ <?php echo $result['logged_count']; ?> URLs enregistrées en base</strong></p>
                    <?php endif; ?>

                    <?php if (isset($result['log_error'])): ?>
                        <div class="error" style="margin-top: 10px; padding: 10px;">
                            <strong>⚠️ Erreur d'enregistrement en base:</strong><br>
                            <?php echo htmlspecialchars($result['log_error']); ?>
                        </div>
                    <?php endif; ?>
                <?php endif; ?>

                <h4>🔍 Détails par fournisseur:</h4>
                <ul>
                    <li>Dropbox: <?php echo $result['provider_counts']['dropbox']; ?> URLs</li>
                    <li>FromSmash: <?php echo $result['provider_counts']['fromsmash']; ?> URLs</li>
                    <li>SwissTransfer: <?php echo $result['provider_counts']['swisstransfer']; ?> URLs</li>
                </ul>

                <h4>📊 Réponse complète:</h4>
                <pre><?php echo htmlspecialchars(json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)); ?></pre>
            </div>
        <?php endif; ?>

        <div style="margin-top: 30px; padding: 15px; background: #e2f0fd; border-radius: 5px;">
            <h3>💡 Exemple de test</h3>
            <p>Collez ceci dans le champ "Contenu de l'email" :</p>
            <pre style="background: white; padding: 10px; border: 1px solid #ccc; border-radius: 4px; overflow-x: auto;">
Voici les missions pour le lot 180.

Recadrage 9:16 standard à faire pour 17h26 (aujourd\'hui 22/09) :
- Vidéo 1.mp4 (Logos requis: les marseillais.png)
- Vidéo 2.mp4 (Logos requis: les marseillais.png)

Lien : https://fromsmash.com/OPhYnnPgFM-ct

Merci !</pre>
        </div>
    </div>
</body>
</html>