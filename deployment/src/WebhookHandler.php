<?php
/**
 * Webhook Handler
 * Main class that processes webhook requests and orchestrates the entire workflow
 */

require_once __DIR__ . '/AuthorizedSenders.php';
require_once __DIR__ . '/EmailProcessor.php';
require_once __DIR__ . '/DropboxUrlProcessor.php';
require_once __DIR__ . '/FromSmashUrlProcessor.php';
require_once __DIR__ . '/SwissTransferUrlProcessor.php';
require_once __DIR__ . '/DatabaseLogger.php';
require_once __DIR__ . '/GmailMailer.php';

class WebhookHandler
{
    private $emailProcessor;
    private $databaseLogger;

    /**
     * Constructor
     */
    public function __construct()
    {
        $this->emailProcessor = new EmailProcessor();
        $this->databaseLogger = new DatabaseLogger();
        
        // Ensure database table exists
        $this->databaseLogger->ensureTableExists();
    }

    /**
     * Process webhook request
     * 
     * @param array $webhookData Webhook payload data
     * @return array Processing result
     */
    public function processWebhook($webhookData)
    {
        $result = [
            'success' => false,
            'message' => '',
            'processed_urls' => [],
            'errors' => []
        ];

        try {
            // Validate webhook data
            if (!$this->validateWebhookData($webhookData)) {
                $result['message'] = 'Invalid webhook data';
                return $result;
            }

            // Extract sender email from webhook data (support sender_address or sender_email)
            $senderField = isset($webhookData['sender_address']) ? $webhookData['sender_address'] : (isset($webhookData['sender_email']) ? $webhookData['sender_email'] : '');
            $senderEmail = $this->emailProcessor->extractSenderEmail($senderField);
            
            if (!$senderEmail) {
                $result['message'] = 'Could not extract sender email';
                return $result;
            }

            // Check if sender is authorized
            if (!AuthorizedSenders::isAuthorized($senderEmail)) {
                $result['message'] = "Sender not authorized: {$senderEmail}";
                error_log("Unauthorized sender: {$senderEmail}");
                return $result;
            }

            // If detector indicates AUTOREPONDEUR flow, send an email via Gmail OAuth and return.
            // This mirrors the Make.com scenario defined in make/AUTOREPONDEUR_MAKE_WEBHOOK_URL.blueprint.json
            $detector = isset($webhookData['detector']) ? $webhookData['detector'] : null;
            if ($detector === 'desabonnement_journee_tarifs') {
                $to = 'technique@media-solution.fr'; // Temporaire pour les tests
                error_log("AUTOREPONDEUR: Envoi à $to");
                if (empty($to)) {
                    $result['message'] = 'AUTOREPONDEUR_TO not configured';
                    $result['errors'][] = 'Missing env AUTOREPONDEUR_TO';
                    return $result;
                }

                $emailContent = '';
                if (isset($webhookData['email_content'])) {
                    $emailContent = (string)$webhookData['email_content'];
                } elseif (isset($webhookData['Text'])) {
                    $emailContent = (string)$webhookData['Text'];
                }

                $incomingSubject = isset($webhookData['Subject']) ? (string)$webhookData['Subject'] : ((isset($webhookData['subject']) ? (string)$webhookData['subject'] : ''));
                $start = isset($webhookData['webhooks_time_start']) ? (string)$webhookData['webhooks_time_start'] : 'maintenant';
                $end = isset($webhookData['webhooks_time_end']) ? (string)$webhookData['webhooks_time_end'] : '';

                $isUrgent = stripos($emailContent, 'urgent') !== false;
                if ($isUrgent) {
                    $subjectOut = 'Acceptation lot urgent : ' . $incomingSubject;
                    $html = "Hello !<br><br>\nJe peux prendre en charge ce lot urgent dès maintenant.<br><br>\nCamille";
                } else {
                    $subjectOut = 'Acception : ' . $incomingSubject;
                    $timeWindow = htmlspecialchars($start, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
                    $timeEnd = htmlspecialchars($end, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
                    $html = "Hello !<br><br>\nJe peux prendre en charge les vidéos aujourd'hui de {$timeWindow} jusqu'à {$timeEnd}.<br><br>\nCamille";
                }

                $mailer = new GmailMailer();
                error_log("GmailMailer configuré: " . ($mailer->isConfigured() ? 'oui' : 'non'));
                if (!$mailer->isConfigured()) {
                    $result['message'] = 'Gmail OAuth not configured';
                    $result['errors'][] = 'Missing GMAIL_CLIENT_* or GMAIL_FROM_* env variables';
                    return $result;
                }

                error_log("Envoi email: $subjectOut à $to");
                $sendRes = $mailer->send($to, $subjectOut, $html);
                error_log("Résultat envoi: " . json_encode($sendRes));
                if ($sendRes['success']) {
                    $result['success'] = true;
                    $result['message'] = 'AUTOREPONDEUR email sent successfully';
                    return $result;
                } else {
                    $result['message'] = 'Failed to send AUTOREPONDEUR email';
                    $result['errors'][] = $sendRes['error'] ?? ('status=' . ($sendRes['status'] ?? 'unknown'));
                    return $result;
                }
            } elseif ($detector === 'recadrage') {
                // Confirmation mission recadrage (Make blueprint: RECADRAGE_MAKE_WEBHOOK_URL)
                $to = 'camille.moine.pro@gmail.com'; // Temporaire pour les tests (configurable via ENV à terme)
                error_log("RECADRAGE: Envoi à $to");
                if (empty($to)) {
                    $result['message'] = 'RECADRAGE_TO not configured';
                    $result['errors'][] = 'Missing env RECADRAGE_TO';
                    return $result;
                }

                // Inputs from webhook (per Make blueprint interface): subject, delivery_time, sender_email
                $incomingSubject = isset($webhookData['Subject']) ? (string)$webhookData['Subject'] : ((isset($webhookData['subject']) ? (string)$webhookData['subject'] : ''));
                $deliveryTime = isset($webhookData['delivery_time']) ? (string)$webhookData['delivery_time'] : '';

                // Urgency detection is based on SUBJECT containing 'urgence' (case-insensitive)
                $isUrgent = stripos($incomingSubject, 'urgence') !== false;

                // Compose email mirroring the Make.com modules
                $safeSubject = $incomingSubject; // kept raw in subject line as in Make; can be sanitized by Gmail API
                if ($isUrgent) {
                    $subjectOut = 'Confirmation : ' . $safeSubject;
                    $html = "OK merci, je m'en occupe.";
                } else {
                    $subjectOut = 'Confirmation : ' . $safeSubject;
                    $safeDelivery = htmlspecialchars($deliveryTime, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
                    $html = "OK merci, je m'en occupe pour {$safeDelivery}.";
                }

                $mailer = new GmailMailer();
                error_log("GmailMailer configuré (recadrage): " . ($mailer->isConfigured() ? 'oui' : 'non'));
                if (!$mailer->isConfigured()) {
                    $result['message'] = 'Gmail OAuth not configured';
                    $result['errors'][] = 'Missing GMAIL_CLIENT_* or GMAIL_FROM_* env variables';
                    return $result;
                }

                error_log("Envoi email (recadrage): $subjectOut à $to");
                $sendRes = $mailer->send($to, $subjectOut, $html);
                error_log("Résultat envoi (recadrage): " . json_encode($sendRes));
                if ($sendRes['success']) {
                    $result['success'] = true;
                    $result['message'] = 'RECADRAGE email sent successfully';
                    return $result;
                } else {
                    $result['message'] = 'Failed to send RECADRAGE email';
                    $result['errors'][] = $sendRes['error'] ?? ('status=' . ($sendRes['status'] ?? 'unknown'));
                    return $result;
                }
            }

            // If delivery_links are provided (Make webhook), use them directly
            $processedUrls = [];
            if (isset($webhookData['delivery_links']) && is_array($webhookData['delivery_links']) && count($webhookData['delivery_links']) > 0) {
                foreach ($webhookData['delivery_links'] as $item) {
                    // Accept either dict { provider, raw_url } or raw string
                    if (is_array($item) && isset($item['raw_url'])) {
                        $processedUrls[] = $item['raw_url'];
                    } elseif (is_string($item)) {
                        $processedUrls[] = $item;
                    }
                }
                // Deduplicate
                $processedUrls = array_values(array_unique(array_filter($processedUrls)));
            } else {
                // Fallback: use provided email_content or search IMAP, then extract links server-side
                if (isset($webhookData['email_content']) && !empty($webhookData['email_content'])) {
                    // Use email content from webhook payload
                    $emailData = [
                        'text' => $webhookData['email_content'],
                        'html' => $webhookData['email_content'],
                        'subject' => $webhookData['subject'],
                        'from' => $senderField
                    ];
                } else {
                    // Fallback: Search for the email using IMAP
                    $emailData = $this->searchEmailFromWebhook($webhookData);

                    if (!$emailData) {
                        $result['message'] = 'Email not found in IMAP and no email content provided in webhook';
                        return $result;
                    }
                }

                // Process email content for URLs from supported providers
                $processedUrls = $this->processEmailForDropboxUrls($emailData);
            }

            if (empty($processedUrls)) {
                $result['message'] = 'No delivery links found';
                return $result;
            }

            // Log URLs to database
            $loggedCount = $this->databaseLogger->logMultipleDropboxUrls($processedUrls);

            $result['success'] = true;
            $result['message'] = "Successfully processed {$loggedCount} delivery link(s)";
            $result['processed_urls'] = $processedUrls;
            
            error_log("Webhook processed successfully: {$loggedCount} URLs logged");
            
        } catch (Exception $e) {
            $result['errors'][] = $e->getMessage();
            error_log("Webhook processing error: " . $e->getMessage());
        }

        return $result;
    }

    /**
     * Validate webhook data structure
     * 
     * @param array $data Webhook data
     * @return bool True if valid
     */
    private function validateWebhookData($data)
    {
        // Allow several shapes:
        // A) Legacy/custom webhook: requires sender_address, subject, receivedDateTime
        // B) Make webhook (Media Solution): may provide sender_email and delivery_links (and may omit receivedDateTime)
        // C) Detector webhook (e.g., recadrage, desabonnement_journee_tarifs): requires detector, subject, sender_email

        $hasSubject = isset($data['subject']) && !empty($data['subject']);
        $hasSender = (isset($data['sender_address']) && !empty($data['sender_address'])) || (isset($data['sender_email']) && !empty($data['sender_email']));
        $hasReceived = isset($data['receivedDateTime']) && !empty($data['receivedDateTime']);
        $hasDeliveryLinks = isset($data['delivery_links']) && is_array($data['delivery_links']) && count($data['delivery_links']) > 0;
        $hasValidDetector = isset($data['detector']) && in_array($data['detector'], ['recadrage', 'desabonnement_journee_tarifs']);

        // Accept if legacy required fields present
        if ($hasSubject && $hasSender && $hasReceived) {
            return true;
        }

        // Accept Make-style payload if it has at least subject, sender (any form), and delivery_links
        if ($hasSubject && $hasSender && $hasDeliveryLinks) {
            return true;
        }

        // As a fallback, accept if subject + sender present and email_content provided
        if ($hasSubject && $hasSender && isset($data['email_content']) && !empty($data['email_content'])) {
            return true;
        }

        // Accept detector-based webhook (e.g., recadrage, desabonnement_journee_tarifs)
        if ($hasValidDetector && $hasSubject && $hasSender) {
            return true;
        }

        // Otherwise, invalid
        error_log("Invalid webhook payload: missing required fields (subject/sender and either receivedDateTime, delivery_links, email_content, or valid detector)");
        return false;
    }

    /**
     * Search for email using webhook data
     * 
     * @param array $webhookData Webhook data
     * @return array|null Email data or null if not found
     */
    private function searchEmailFromWebhook($webhookData)
    {
        // Extract sender email
        $senderEmail = $this->emailProcessor->extractSenderEmail($webhookData['sender_address']);
        
        // Format date for search
        $searchDate = $this->emailProcessor->formatDateForSearch($webhookData['receivedDateTime']);
        
        // Build search criteria (replicating Make.com logic)
        $searchCriteria = [
            'from' => $senderEmail,
            'subject' => $webhookData['subject'],
            'since' => $searchDate
        ];
        
        return $this->emailProcessor->searchEmail($searchCriteria);
    }

    /**
     * Process email content for Dropbox URLs
     * 
     * @param array $emailData Email data
     * @return array Array of processed Dropbox URLs
     */
    private function processEmailForDropboxUrls($emailData)
    {
        // Get email content (prefer HTML, fallback to text)
        $content = !empty($emailData['html']) ? $emailData['html'] : $emailData['text'];
        
        if (empty($content)) {
            return [];
        }

        // Aggregate URLs from all supported providers (minimal change, keep DB schema/logging intact)
        $urlsDropbox = DropboxUrlProcessor::processAllDropboxUrls($content);
        $urlsSmash = FromSmashUrlProcessor::processAllFromSmashUrls($content);
        $urlsSwiss = SwissTransferUrlProcessor::processAllSwissTransferUrls($content);

        // Merge and deduplicate
        $allUrls = array_unique(array_merge($urlsDropbox, $urlsSmash, $urlsSwiss));

        return $allUrls;
    }

    /**
     * Manual processing method for testing
     * 
     * @param string $senderEmail Sender email
     * @param string $subject Email subject
     * @param string $date Email date
     * @return array Processing result
     */
    public function manualProcess($senderEmail, $subject, $date)
    {
        $webhookData = [
            'sender_address' => "<{$senderEmail}>",
            'subject' => $subject,
            'receivedDateTime' => $date,
            'microsoft_graph_email_id' => 'manual-' . time(),
            'bodyPreview' => 'Manual processing'
        ];
        
        return $this->processWebhook($webhookData);
    }

    /**
     * Get processing statistics
     * 
     * @return array Statistics data
     */
    public function getStatistics()
    {
        try {
            $recentLogs = $this->databaseLogger->getRecentLogs(10);
            
            return [
                'recent_logs' => $recentLogs,
                'total_processed' => count($recentLogs),
                'authorized_senders' => AuthorizedSenders::getAuthorizedEmails()
            ];
        } catch (Exception $e) {
            error_log("Failed to get statistics: " . $e->getMessage());
            return [
                'recent_logs' => [],
                'total_processed' => 0,
                'authorized_senders' => AuthorizedSenders::getAuthorizedEmails(),
                'error' => $e->getMessage()
            ];
        }
    }

    /**
     * Test direct d'extraction d'URLs sans IMAP (uniquement pour les tests)
     * @param string $emailContent Contenu de l'email à analyser
     * @param string $subject Sujet de l'email (optionnel, par défaut un sujet valide)
     * @return array Résultat du traitement
     */
    public function testEmailProcessing($emailContent, $subject = 'Média Solution - Missions Recadrage - Lot 180') {

        // Vérifier que le contenu n'est pas vide
        if (empty(trim($emailContent))) {
            throw new Exception('Le contenu de l\'email ne peut pas être vide');
        }

        // Extraire les URLs de tous les fournisseurs
        $dropboxUrls = DropboxUrlProcessor::processAllDropboxUrls($emailContent);
        $fromSmashUrls = FromSmashUrlProcessor::processAllFromSmashUrls($emailContent);
        $swissTransferUrls = SwissTransferUrlProcessor::processAllSwissTransferUrls($emailContent);

        // Combiner et dédupliquer les URLs
        $allUrls = array_unique(array_merge($dropboxUrls, $fromSmashUrls, $swissTransferUrls));

        // Simuler la structure de retour complète
        $result = [
            'success' => !empty($allUrls),
            'message' => !empty($allUrls) ? 'URLs extraites avec succès' : 'Aucune URL valide trouvée',
            'processed_urls' => $allUrls,
            'provider_counts' => [
                'dropbox' => count($dropboxUrls),
                'fromsmash' => count($fromSmashUrls),
                'swisstransfer' => count($swissTransferUrls)
            ]
        ];

        // Si on a des URLs, on les enregistre en base
        if (!empty($allUrls)) {
            try {
                // On utilise le logger existant de la classe
                $this->databaseLogger->logMultipleDropboxUrls($allUrls);
                $result['logged_count'] = count($allUrls);
            } catch (Exception $e) {
                // On ne bloque pas le test en cas d'erreur de log
                $result['log_error'] = $e->getMessage();
            }
        }

        return $result;
    }
}