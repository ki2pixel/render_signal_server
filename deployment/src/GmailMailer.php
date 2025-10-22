<?php
/**
 * GmailMailer
 * Sends emails via Gmail API using OAuth2 (client_id + client_secret + refresh_token).
 * No external library required (uses cURL). Secrets are read from environment variables.
 *
 * Required env vars:
 * - GMAIL_CLIENT_ID
 * - GMAIL_CLIENT_SECRET
 * - GMAIL_REFRESH_TOKEN
 * - GMAIL_FROM_EMAIL
 * - GMAIL_FROM_NAME (optional)
 * - AUTOREPONDEUR_TO (recipient for autorepondeur notifications)
 */

class GmailMailer
{
    private $clientId;
    private $clientSecret;
    private $refreshToken;
    private $fromEmail;
    private $fromName;

    public function __construct()
    {
        // Load sensitive values from environment variables (injected via Apache SetEnv or hosting panel)
        // Never hardcode secrets in source control.
        $this->clientId = getenv('GMAIL_CLIENT_ID') ?: ($_SERVER['GMAIL_CLIENT_ID'] ?? null);
        $this->clientSecret = getenv('GMAIL_CLIENT_SECRET') ?: ($_SERVER['GMAIL_CLIENT_SECRET'] ?? null);
        $this->refreshToken = getenv('GMAIL_REFRESH_TOKEN') ?: ($_SERVER['GMAIL_REFRESH_TOKEN'] ?? null);
        $this->fromEmail = getenv('GMAIL_FROM_EMAIL') ?: ($_SERVER['GMAIL_FROM_EMAIL'] ?? null);
        $this->fromName = getenv('GMAIL_FROM_NAME') ?: ($_SERVER['GMAIL_FROM_NAME'] ?? null);
    }

    public function isConfigured(): bool
    {
        return $this->clientId && $this->clientSecret && $this->refreshToken && $this->fromEmail;
    }

    /**
     * Send an HTML email using Gmail API.
     * @param string $to Recipient email
     * @param string $subject Email subject
     * @param string $html HTML body
     * @return array [success => bool, status => int|null, error => string|null]
     */
    public function send(string $to, string $subject, string $html): array
    {
        if (!$this->isConfigured()) {
            error_log('GmailMailer: Configuration manquante - ' . json_encode([
                'clientId' => $this->clientId ? 'set' : 'missing',
                'clientSecret' => $this->clientSecret ? 'set' : 'missing',
                'refreshToken' => $this->refreshToken ? 'set' : 'missing',
                'fromEmail' => $this->fromEmail ?: 'missing'
            ]));
            return ['success' => false, 'status' => null, 'error' => 'Gmail OAuth not configured'];
        }

        error_log('GmailMailer: Tentative d\'obtention du token d\'accès');
        $tokenResult = $this->getAccessToken();
        if (!$tokenResult['success']) {
            // Retourner les détails de l'erreur pour le débogage
            return [
                'success' => false,
                'status' => null,
                'error' => 'Erreur d\'authentification Gmail: ' . ($tokenResult['error'] ?? 'Inconnue'),
                'details' => $tokenResult['details'] ?? null
            ];
        }
        $accessToken = $tokenResult['access_token'];

        // Build RFC 2822 raw message
        $fromName = $this->fromName ?: $this->fromEmail;
        $boundary = '=_mime_boundary_' . bin2hex(random_bytes(8));

        $headers = [];
        $headers[] = 'From: ' . $this->encodeDisplayName($fromName) . ' <' . $this->fromEmail . '>';
        $headers[] = 'To: ' . $to;
        $headers[] = 'Subject: ' . $this->encodeHeader($subject);
        $headers[] = 'MIME-Version: 1.0';
        $headers[] = 'Content-Type: multipart/alternative; boundary="' . $boundary . '"';

        $bodyParts = [];
        // Plain text fallback (strip tags)
        $text = trim(html_entity_decode(strip_tags($html)));
        $bodyParts[] = '--' . $boundary;
        $bodyParts[] = 'Content-Type: text/plain; charset=UTF-8';
        $bodyParts[] = 'Content-Transfer-Encoding: 7bit';
        $bodyParts[] = '';
        $bodyParts[] = $text;

        // HTML part
        $bodyParts[] = '--' . $boundary;
        $bodyParts[] = 'Content-Type: text/html; charset=UTF-8';
        $bodyParts[] = 'Content-Transfer-Encoding: 7bit';
        $bodyParts[] = '';
        $bodyParts[] = $html;
        $bodyParts[] = '--' . $boundary . '--';

        $raw = implode("\r\n", array_merge($headers, [''], $bodyParts));
        $rawBase64Url = rtrim(strtr(base64_encode($raw), '+/', '-_'), '=');

        // Send via Gmail API
        $url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send';
        $postData = json_encode(['raw' => $rawBase64Url]);

        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Authorization: Bearer ' . $accessToken,
            'Content-Type: application/json',
        ]);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        if ($response === false) {
            $err = curl_error($ch);
            curl_close($ch);
            error_log('GmailMailer cURL error: ' . $err);
            return ['success' => false, 'status' => null, 'error' => $err];
        }
        curl_close($ch);

        $ok = ($httpCode >= 200 && $httpCode < 300);
        if (!$ok) {
            error_log('GmailMailer send failed: HTTP ' . $httpCode . ' resp=' . substr($response, 0, 300));
        }
        return ['success' => $ok, 'status' => $httpCode, 'error' => $ok ? null : $response];
    }

    /**
     * Obtain an access token using the refresh token.
     */
    private function getAccessToken()
    {
        $url = 'https://oauth2.googleapis.com/token';
        $data = [
            'client_id' => $this->clientId,
            'client_secret' => $this->clientSecret,
            'refresh_token' => $this->refreshToken,
            'grant_type' => 'refresh_token',
        ];

        // Log des données d'authentification (sans le refresh token complet pour des raisons de sécurité)
        $logData = $data;
        $logData['refresh_token'] = substr($data['refresh_token'], 0, 10) . '...';
        error_log('Données de la requête OAuth: ' . print_r($logData, true));

        $postData = http_build_query($data);

        $ch = curl_init($url);
        $headers = [
            'Content-Type: application/x-www-form-urlencoded',
            'Accept: application/json'
        ];

        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST => true,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_POSTFIELDS => $postData,
            CURLOPT_VERBOSE => true,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_USERAGENT => 'PHP-Gmail-OAuth/1.0',
            CURLOPT_HEADER => true
        ]);

        // Activation du mode verbeux et capture de la sortie
        curl_setopt($ch, CURLOPT_VERBOSE, true);
        $verbose = fopen('php://temp', 'w+');
        curl_setopt($ch, CURLOPT_STDERR, $verbose);
        curl_setopt($ch, CURLOPT_TIMEOUT, 15);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
        $headers = substr($response, 0, $headerSize);
        $resp = substr($response, $headerSize);
        $curlError = curl_error($ch);
        $curlErrno = curl_errno($ch);

        // Récupérer les infos de débogage
        rewind($verbose);
        $verboseLog = stream_get_contents($verbose);
        fclose($verbose);

        $errorDetails = [
            'http_code' => $httpCode,
            'curl_errno' => $curlErrno,
            'curl_error' => $curlError,
            'response_headers' => $headers,
            'response_body' => $resp,
            'verbose_log' => $verboseLog,
            'request_url' => $url,
            'request_headers' => $headers,
            'request_body' => $postData
        ];

        // Journalisation des erreurs
        if ($curlErrno) {
            error_log(sprintf('cURL error %s: %s', $curlErrno, $curlError));
        }

        error_log('Réponse complète de Google OAuth: ' . print_r($errorDetails, true));

        curl_close($ch);

        if ($resp === false) {
            return [
                'success' => false,
                'error' => 'Erreur cURL: ' . $curlError,
                'details' => $errorDetails
            ];
        }

        if ($httpCode !== 200) {
            return [
                'success' => false,
                'error' => 'Erreur HTTP ' . $httpCode,
                'details' => $errorDetails
            ];
        }

        $json = json_decode($resp, true);
        if (!isset($json['access_token'])) {
            return [
                'success' => false,
                'error' => 'Token d\'accès non reçu dans la réponse',
                'details' => $errorDetails
            ];
        }

        return [
            'success' => true,
            'access_token' => $json['access_token']
        ];
    }

    private function encodeHeader(string $str): string
    {
        // Encode non-ASCII per RFC 2047
        if (preg_match('/[\x80-\xFF]/', $str)) {
            return '=?UTF-8?B?' . base64_encode($str) . '?=';
        }
        return $str;
    }

    private function encodeDisplayName(string $name): string
    {
        // Quote if contains special chars
        if (preg_match('/[",<>]/', $name)) {
            return '"' . addcslashes($name, '"') . '"';
        }
        return $this->encodeHeader($name);
    }
}
