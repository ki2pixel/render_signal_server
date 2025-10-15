<?php
/**
 * Main Entry Point
 * Handles webhook requests and provides basic web interface
 */

// Error reporting for development
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Configuration des logs
$logDir = dirname(__DIR__) . '/logs';
$logFile = $logDir . '/error.log';

// Créer le répertoire de logs s'il n'existe pas
if (!is_dir($logDir)) {
    mkdir($logDir, 0755, true);
}

// Vérifier les permissions du répertoire
if (!is_writable($logDir)) {
    error_log("ERREUR: Le répertoire de logs n'est pas accessible en écriture: " . $logDir);
} else {
    // Configurer la journalisation des erreurs
    ini_set('log_errors', 1);
    ini_set('error_log', $logFile);
    
    // Vérifier que le fichier de log est accessible
    if (!file_exists($logFile)) {
        touch($logFile);
        chmod($logFile, 0666); // Permissions plus larges pour le fichier
    }
    
    if (!is_writable($logFile)) {
        error_log("ERREUR: Impossible d'écrire dans le fichier de log: " . $logFile);
    }
}

// Activer l'affichage des erreurs en développement
if (getenv('APP_ENV') === 'development' || ($_SERVER['SERVER_NAME'] ?? '') === 'localhost') {
    ini_set('display_errors', 1);
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', 0);
    error_reporting(E_ERROR | E_WARNING | E_PARSE);
}
if (!is_writable($logDir)) {
    error_log("ERREUR: Le répertoire de logs n'est pas accessible en écriture: " . $logDir);
} else {
    // Configurer la journalisation des erreurs
    ini_set('log_errors', 1);
    ini_set('error_log', $logFile);
    
    // Vérifier que le fichier de log est accessible
    if (!file_exists($logFile)) {
        touch($logFile);
        chmod($logFile, 0666); // Permissions plus larges pour le fichier
    }
    
    if (!is_writable($logFile)) {
        error_log("ERREUR: Impossible d'écrire dans le fichier de log: " . $logFile);
    }
}

// Activer l'affichage des erreurs en développement
if (getenv('APP_ENV') === 'development' || ($_SERVER['SERVER_NAME'] ?? '') === 'localhost') {
    ini_set('display_errors', 1);
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', 0);
    error_reporting(E_ERROR | E_WARNING | E_PARSE);
}

require_once dirname(__DIR__) . '/src/WebhookHandler.php';

// Handle different request methods
$method = $_SERVER['REQUEST_METHOD'];

// Vérifier si c'est une requête de test d'e-mail
if (isset($_GET['test-email']) && $method === 'POST') {
    testGmailSending();
} 
// Gérer les webhooks normaux
else if ($method === 'POST') {
    handleWebhookRequest();
} 
// Afficher l'interface web ou la page de test
else {
    if (isset($_GET['test-email'])) {
        showTestEmailForm();
    } else {
        showWebInterface();
    }
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
        // Debug: request metadata
        $method = $_SERVER['REQUEST_METHOD'] ?? 'UNKNOWN';
        $uri = $_SERVER['REQUEST_URI'] ?? '';
        $ip = $_SERVER['REMOTE_ADDR'] ?? '';
        $len = isset($_SERVER['CONTENT_LENGTH']) ? intval($_SERVER['CONTENT_LENGTH']) : strlen((string)$input);
        $headers = function_exists('apache_request_headers') ? @apache_request_headers() : [];
        error_log(sprintf("Webhook request meta: method=%s uri=%s ip=%s content_length=%d", $method, $uri, $ip, $len));
        if (!empty($headers)) {
            // Avoid logging sensitive headers; log keys only
            error_log("Webhook request headers: " . implode(',', array_keys($headers)));
        }
        if ($len === 0 || $input === false || $input === '') {
            error_log("Webhook received empty body");
        }
        $webhookData = json_decode($input, true);
        
        if (json_last_error() !== JSON_ERROR_NONE) {
            http_response_code(400);
            echo json_encode(['error' => 'Invalid JSON data']);
            return;
        }
        
        // Log incoming webhook
        error_log("Webhook received (json ok). Keys: " . implode(',', array_keys((array)$webhookData)));
        if (isset($webhookData['delivery_links'])) {
            $dlCount = is_array($webhookData['delivery_links']) ? count($webhookData['delivery_links']) : 0;
            error_log("Webhook payload contains delivery_links count=" . $dlCount);
        }
        
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
    // Votre code existant...
    // ...
}

/**
 * Affiche un formulaire de test d'envoi d'e-mail
 */
function showTestEmailForm()
{
    header('Content-Type: text/html; charset=utf-8');
    
    // Vérifier la configuration Gmail
    $gmailConfigured = false;
    $missingConfigs = [];
    
    if (!empty(getenv('GMAIL_CLIENT_ID')) || !empty($_SERVER['GMAIL_CLIENT_ID'])) {
        if (!empty(getenv('GMAIL_CLIENT_SECRET')) || !empty($_SERVER['GMAIL_CLIENT_SECRET'])) {
            if (!empty(getenv('GMAIL_REFRESH_TOKEN')) || !empty($_SERVER['GMAIL_REFRESH_TOKEN'])) {
                if (!empty(getenv('GMAIL_FROM_EMAIL')) || !empty($_SERVER['GMAIL_FROM_EMAIL'])) {
                    $gmailConfigured = true;
                } else {
                    $missingConfigs[] = 'GMAIL_FROM_EMAIL';
                }
            } else {
                $missingConfigs[] = 'GMAIL_REFRESH_TOKEN';
            }
        } else {
            $missingConfigs[] = 'GMAIL_CLIENT_SECRET';
        }
    } else {
        $missingConfigs[] = 'GMAIL_CLIENT_ID';
    }
    
    ?>
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Test d'envoi Gmail</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                max-width: 800px; 
                margin: 0 auto; 
                padding: 20px; 
                line-height: 1.6;
                color: #333;
            }
            .container { 
                max-width: 800px; 
                margin: 0 auto; 
                background: white; 
                padding: 30px; 
                border-radius: 8px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            }
            h1 { 
                color: #333; 
                border-bottom: 2px solid #007cba; 
                padding-bottom: 10px; 
                margin-top: 0;
            }
            .form-group { 
                margin-bottom: 20px; 
            }
            label { 
                display: block; 
                margin-bottom: 8px; 
                font-weight: bold;
            }
            input[type="email"], 
            input[type="text"], 
            textarea {
                width: 100%;
                padding: 10px;
                margin-bottom: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 16px;
            }
            textarea {
                min-height: 150px;
                resize: vertical;
            }
            button {
                background-color: #007cba;
                color: white;
                padding: 12px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                transition: background-color 0.3s;
            }
            button:hover { 
                background-color: #005a87; 
            }
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            #result { 
                margin-top: 20px; 
                padding: 15px; 
                border-radius: 4px; 
                display: none;
            }
            .success { 
                background-color: #dff0d8; 
                color: #3c763d; 
                border: 1px solid #d6e9c6;
            }
            .error { 
                background-color: #f2dede; 
                color: #a94442; 
                border: 1px solid #ebccd1;
            }
            .warning {
                background-color: #fcf8e3;
                color: #8a6d3b;
                border: 1px solid #faebcc;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 4px;
            }
            .config-status {
                padding: 10px 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                font-weight: bold;
            }
            .config-ok {
                background-color: #dff0d8;
                color: #3c763d;
                border: 1px solid #d6e9c6;
            }
            .config-error {
                background-color: #f2dede;
                color: #a94442;
                border: 1px solid #ebccd1;
            }
            pre {
                background: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                overflow-x: auto;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Test d'envoi Gmail</h1>
            
            <?php if (!$gmailConfigured): ?>
                <div class="config-status config-error">
                    ⚠️ Configuration Gmail incomplète. Variables manquantes : <?php echo implode(', ', $missingConfigs); ?>
                </div>
                <div class="warning">
                    <p>Pour configurer l'envoi d'e-mails, assurez-vous que les variables d'environnement suivantes sont définies dans votre fichier <code>.htaccess</code> :</p>
                    <pre># Exemple de configuration dans .htaccess
SetEnv GMAIL_CLIENT_ID "votre-client-id"
SetEnv GMAIL_CLIENT_SECRET "votre-client-secret"
SetEnv GMAIL_REFRESH_TOKEN "votre-refresh-token"
SetEnv GMAIL_FROM_EMAIL "votre-email@exemple.com"
SetEnv GMAIL_FROM_NAME "Votre Nom"</pre>
                </div>
            <?php else: ?>
                <div class="config-status config-ok">
                    ✅ Configuration Gmail détectée
                </div>
            <?php endif; ?>
            
            <form id="testEmailForm" class="test-form">
                <div class="form-group">
                    <label for="to">Adresse e-mail du destinataire :</label>
                    <input type="email" id="to" name="to" required 
                           placeholder="destinataire@exemple.com">
                </div>
                
                <div class="form-group">
                    <label for="subject">Sujet :</label>
                    <input type="text" id="subject" name="subject" required
                           value="Test d'envoi Gmail">
                </div>
                
                <div class="form-group">
                    <label for="message">Message :</label>
                    <textarea id="message" name="message" required>Bonjour,

Ceci est un test d'envoi d'e-mail via l'API Gmail.

Cordialement,</textarea>
                </div>
                
                <button type="submit" id="sendButton" <?php echo !$gmailConfigured ? 'disabled' : ''; ?>>
                    Envoyer l'e-mail de test
                </button>
            </form>
            
            <div id="result"></div>
            
            <div class="section" id="debug-logs" style="display: none; margin-top: 30px;">
                <h3>📜 Logs de débogage</h3>
                <pre id="log-output" style="background: #f5f5f5; padding: 15px; border-radius: 5px; max-height: 300px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;"></pre>
            </div>
        </div>
        
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const form = document.getElementById('testEmailForm');
                if (!form) return;
                
                const resultDiv = document.getElementById('result');
                const sendButton = document.getElementById('sendButton');
                
                form.addEventListener('submit', async function(e) {
                    e.preventDefault();
                    
                    if (!sendButton) return;
                    
                    // Désactiver le bouton pendant l'envoi
                    sendButton.disabled = true;
                    sendButton.textContent = 'Envoi en cours...';
                    
                    // Réinitialiser le message de résultat
                    if (resultDiv) {
                        resultDiv.style.display = 'none';
                        resultDiv.className = '';
                        resultDiv.textContent = '';
                    }
                    
                    try {
                        const formData = new FormData(form);
                        const response = await fetch(window.location.pathname + '?test-email', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                            },
                            body: new URLSearchParams(formData).toString()
                        });
                        
                        if (!response.ok) {
                            throw new Error(`Erreur HTTP: ${response.status}`);
                        }
                        
                        const data = await response.json();
                        
                        // Afficher le résultat
                        if (resultDiv) {
                            resultDiv.style.display = 'block';
                            
                            // Afficher le résultat principal
                            if (data.success) {
                                resultDiv.className = 'success';
                                resultDiv.innerHTML = '✅ <strong>Succès !</strong> ' + data.message;
                            } else {
                                resultDiv.className = 'error';
                                let errorMessage = '❌ <strong>Erreur :</strong> ' + (data.message || 'Une erreur est survenue');
                                
                                if (data.details) {
                                    errorMessage += '<div style="margin-top: 10px; font-family: monospace; font-size: 12px; white-space: pre-wrap;">' + 
                                        JSON.stringify(data.details, null, 2) + '</div>';
                                }
                                
                                resultDiv.innerHTML = errorMessage;
                            }
                        }
                        
                        // Afficher les logs si disponibles
                        if (data.logs && data.logs.length > 0) {
                            const logOutput = document.getElementById('log-output');
                            const debugSection = document.getElementById('debug-logs');
                            
                            if (logOutput && debugSection) {
                                // Formater et afficher les logs
                                logOutput.textContent = data.logs.join('\n');
                                debugSection.style.display = 'block';
                                
                                // Faire défiler jusqu'aux logs
                                debugSection.scrollIntoView({ behavior: 'smooth' });
                            }
                        }
                    } catch (error) {
                        console.error('Erreur lors de l\'envoi du formulaire:', error);
                        if (resultDiv) {
                            resultDiv.style.display = 'block';
                            resultDiv.className = 'error';
                            resultDiv.innerHTML = '❌ <strong>Erreur :</strong> ' + (error.message || 'Une erreur est survenue');
                        }
                    } finally {
                        // Réactiver le bouton
                        if (sendButton) {
                            sendButton.disabled = false;
                            sendButton.textContent = 'Envoyer l\'e-mail de test';
                        }
                        
                        // Faire défiler jusqu'au résultat
                        if (resultDiv && resultDiv.style.display === 'block') {
                            resultDiv.scrollIntoView({ behavior: 'smooth' });
                        }
                    }
                });
            });
        </script>
    </div>
</body>
</html>
    <?php
}

/**
 * Teste l'envoi d'un e-mail via Gmail
 */
function testGmailSending()
{
    header('Content-Type: application/json');
    
    // Démarrer la capture des logs
    $logBuffer = [];
    
    // Redéfinir la fonction error_log pour capturer les logs
    $originalErrorLog = function($message, $messageType = 0, $destination = null, $extraHeaders = null) use (&$logBuffer) {
        $logBuffer[] = $message;
        return error_log($message, $messageType, $destination, $extraHeaders);
    };
    
    // Initialiser le tableau de réponse
    $response = [
        'success' => false,
        'message' => '',
        'details' => [],
        'logs' => []
    ];
    
    // Fonction pour logger les erreurs
    $logError = function($message, $data = []) use (&$logBuffer) {
        $logMessage = date('[Y-m-d H:i:s] ') . $message;
        if (!empty($data)) {
            $logMessage .= ' - ' . json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
        }
        $logBuffer[] = $logMessage;
        error_log($logMessage);
    };
    
    try {
        // Récupérer les données du formulaire
        $to = filter_input(INPUT_POST, 'to', FILTER_VALIDATE_EMAIL);
        $subject = filter_input(INPUT_POST, 'subject', FILTER_SANITIZE_STRING) ?: 'Test d\'envoi Gmail';
        $message = filter_input(INPUT_POST, 'message', FILTER_SANITIZE_STRING) ?: 'Ceci est un test d\'envoi via Gmail';
        
        // Journaliser la tentative d'envoi
        $logError("Tentative d'envoi d'email", [
            'to' => $to,
            'subject' => $subject,
            'message_length' => strlen($message),
            'remote_addr' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
            'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown'
        ]);
        
        if (!$to) {
            throw new Exception('Adresse e-mail du destinataire invalide');
        }
        
        // Initialiser GmailMailer
        require_once dirname(__DIR__) . '/src/GmailMailer.php';
        $mailer = new GmailMailer();
        
        // Vérifier la configuration Gmail
        if (!$mailer->isConfigured()) {
            $missing = [];
            $envVars = [
                'GMAIL_CLIENT_ID' => getenv('GMAIL_CLIENT_ID') ?: ($_SERVER['GMAIL_CLIENT_ID'] ?? null),
                'GMAIL_CLIENT_SECRET' => getenv('GMAIL_CLIENT_SECRET') ?: ($_SERVER['GMAIL_CLIENT_SECRET'] ?? null),
                'GMAIL_REFRESH_TOKEN' => getenv('GMAIL_REFRESH_TOKEN') ?: ($_SERVER['GMAIL_REFRESH_TOKEN'] ?? null),
                'GMAIL_FROM_EMAIL' => getenv('GMAIL_FROM_EMAIL') ?: ($_SERVER['GMAIL_FROM_EMAIL'] ?? null)
            ];
            
            foreach ($envVars as $var => $value) {
                if (empty($value)) {
                    $missing[] = $var;
                }
            }
            
            $errorMsg = 'Configuration Gmail manquante. Variables manquantes : ' . implode(', ', $missing);
            $logError($errorMsg, ['env_vars' => $envVars]);
            throw new Exception($errorMsg);
        }
        
        $logError("Configuration Gmail chargée avec succès");
        
        // Construire le contenu HTML de l'e-mail
        $htmlMessage = nl2br(htmlspecialchars($message));
        $html = "
            <div style='font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;'>
                <h2>Test d'envoi Gmail</h2>
                <p>" . $htmlMessage . "</p>
                <hr>
                <p style='color: #666; font-size: 0.9em;'>
                    Cet e-mail a été envoyé depuis l'outil de test Gmail.
                </p>
            </div>
        ";
        
        // Journaliser les détails de l'e-mail avant envoi
        $logError("Préparation de l'envoi d'e-mail", [
            'to' => $to,
            'subject' => $subject,
            'message_length' => strlen($html)
        ]);
        
        // Envoyer l'e-mail
        $result = $mailer->send($to, $subject, $html);
        
        // Journaliser le résultat
        $logError("Résultat de l'envoi d'e-mail", [
            'success' => $result['success'] ?? false,
            'status' => $result['status'] ?? null,
            'error' => $result['error'] ?? null,
            'details' => $result['details'] ?? null
        ]);
        
        if (!empty($result['success'])) {
            $response = [
                'success' => true,
                'message' => 'E-mail envoyé avec succès à ' . $to,
                'details' => [
                    'status' => $result['status'] ?? 'unknown',
                    'to' => $to,
                    'subject' => $subject
                ],
                'logs' => $logBuffer
            ];
            echo json_encode($response, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
        } else {
            $errorMsg = $result['error'] ?? 'Échec de l\'envoi de l\'e-mail';
            $logError("Erreur lors de l'envoi de l'e-mail", [
                'error' => $errorMsg,
                'result' => $result
            ]);
            throw new Exception($errorMsg);
        }
        
    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode([
            'success' => false,
            'message' => $e->getMessage(),
            'details' => [
                'file' => $e->getFile(),
                'line' => $e->getLine(),
                'trace' => $e->getTraceAsString()
            ]
        ]);
    }
    
    exit;
}
?>
