<?php
/**
 * Email Processor
 * Handles IMAP email retrieval and processing
 */

class EmailProcessor
{
    private $config;
    private $connection;

    /**
     * Constructor - Initialize email configuration
     */
    public function __construct()
    {
        $this->config = require dirname(__DIR__) . '/config/email.php';
    }

    /**
     * Connect to IMAP server
     * 
     * @return bool True if connected successfully
     */
    private function connect()
    {
        if ($this->connection) {
            return true;
        }

        $imap = $this->config['imap'];
        $mailbox = "{{$imap['host']}:{$imap['port']}/imap/{$imap['encryption']}}";
        
        try {
            $this->connection = imap_open($mailbox, $imap['username'], $imap['password']);
            
            if (!$this->connection) {
                error_log("IMAP connection failed: " . imap_last_error());
                return false;
            }
            
            return true;
        } catch (Exception $e) {
            error_log("IMAP connection exception: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Disconnect from IMAP server
     */
    private function disconnect()
    {
        if ($this->connection) {
            imap_close($this->connection);
            $this->connection = null;
        }
    }

    /**
     * Extract sender email from webhook sender_address field
     * Replicates Make.com logic: get(split(get(split(1.sender_address; "<"); 2); ">"); 1)
     * 
     * @param string $senderAddress Raw sender address from webhook
     * @return string|null Extracted email address
     */
    public function extractSenderEmail($senderAddress)
    {
        if (empty($senderAddress)) {
            return null;
        }

        // Split by "<" and get second part
        $parts1 = explode('<', $senderAddress);
        if (count($parts1) < 2) {
            // No "<" found, assume it's just an email
            return trim($senderAddress);
        }

        // Split by ">" and get first part
        $parts2 = explode('>', $parts1[1]);
        if (count($parts2) < 1) {
            return null;
        }

        return trim($parts2[0]);
    }

    /**
     * Search for email by criteria (replicating Make.com search)
     * 
     * @param array $criteria Search criteria
     * @return array|null Email data or null if not found
     */
    public function searchEmail($criteria)
    {
        if (!$this->connect()) {
            return null;
        }

        try {
            // Build search criteria
            $searchCriteria = ['ALL'];
            
            if (!empty($criteria['from'])) {
                $searchCriteria[] = 'FROM "' . $criteria['from'] . '"';
            }
            
            if (!empty($criteria['subject'])) {
                $searchCriteria[] = 'SUBJECT "' . $criteria['subject'] . '"';
            }
            
            if (!empty($criteria['since'])) {
                $searchCriteria[] = 'SINCE "' . $criteria['since'] . '"';
            }

            // Search emails
            $searchString = implode(' ', $searchCriteria);
            $emails = imap_search($this->connection, $searchString);
            
            if (!$emails) {
                error_log("No emails found with criteria: " . $searchString);
                return null;
            }

            // Get the most recent email (last in array)
            $emailNumber = end($emails);
            
            // Get email details
            $header = imap_headerinfo($this->connection, $emailNumber);
            $body = $this->getEmailBody($emailNumber);
            
            $emailData = [
                'uid' => $emailNumber,
                'subject' => isset($header->subject) ? $header->subject : '',
                'from' => [
                    'address' => isset($header->from[0]) ? $header->from[0]->mailbox . '@' . $header->from[0]->host : '',
                    'name' => isset($header->from[0]->personal) ? $header->from[0]->personal : ''
                ],
                'date' => isset($header->date) ? $header->date : '',
                'text' => $body['text'],
                'html' => $body['html']
            ];
            
            return $emailData;
            
        } catch (Exception $e) {
            error_log("Email search failed: " . $e->getMessage());
            return null;
        } finally {
            $this->disconnect();
        }
    }

    /**
     * Get email body (both text and HTML)
     * 
     * @param int $emailNumber Email number
     * @return array Array with 'text' and 'html' keys
     */
    private function getEmailBody($emailNumber)
    {
        $body = ['text' => '', 'html' => ''];
        
        try {
            $structure = imap_fetchstructure($this->connection, $emailNumber);
            
            if (isset($structure->parts)) {
                // Multipart email
                foreach ($structure->parts as $partNumber => $part) {
                    $this->extractBodyPart($emailNumber, $partNumber + 1, $part, $body);
                }
            } else {
                // Single part email
                $this->extractBodyPart($emailNumber, 1, $structure, $body);
            }
            
        } catch (Exception $e) {
            error_log("Failed to get email body: " . $e->getMessage());
        }
        
        return $body;
    }

    /**
     * Extract body part from email structure
     * 
     * @param int $emailNumber Email number
     * @param int $partNumber Part number
     * @param object $part Part structure
     * @param array &$body Body array to populate
     */
    private function extractBodyPart($emailNumber, $partNumber, $part, &$body)
    {
        $data = imap_fetchbody($this->connection, $emailNumber, $partNumber);
        
        // Decode based on encoding
        if (isset($part->encoding)) {
            switch ($part->encoding) {
                case 1: // 8bit
                    $data = imap_8bit($data);
                    break;
                case 2: // binary
                    $data = imap_binary($data);
                    break;
                case 3: // base64
                    $data = base64_decode($data);
                    break;
                case 4: // quoted-printable
                    $data = quoted_printable_decode($data);
                    break;
            }
        }
        
        // Determine content type
        $contentType = '';
        if (isset($part->subtype)) {
            $contentType = strtolower($part->subtype);
        }
        
        if ($contentType === 'plain') {
            $body['text'] = $data;
        } elseif ($contentType === 'html') {
            $body['html'] = $data;
        }
    }

    /**
     * Format date for email search (YYYY-MM-DD format)
     * 
     * @param string $dateString Date string to format
     * @return string|null Formatted date or null if invalid
     */
    public function formatDateForSearch($dateString)
    {
        try {
            // Parse the date (expecting format from webhook: "ddd, DD MMM YYYY HH:mm:ss ZZ")
            $date = DateTime::createFromFormat('D, d M Y H:i:s O', $dateString);
            
            if (!$date) {
                // Try alternative formats
                $date = new DateTime($dateString);
            }
            
            return $date->format('Y-m-d');
        } catch (Exception $e) {
            error_log("Date formatting failed: " . $e->getMessage());
            return null;
        }
    }
}
