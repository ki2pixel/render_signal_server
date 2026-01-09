<?php
/**
 * Json Logger
 * Simple file-based logger to persist delivery links into a JSON array
 *
 * Storage file: deployment/data/webhook_links.json
 * Each entry shape:
 *   {
 *     "url": "https://...",
 *     "timestamp": "2025-10-17T10:30:00+02:00",
 *     "source": "webhook"
 *   }
 */

class JsonLogger
{
    private $dataDir;
    private $dataFile;

    public function __construct()
    {
        $this->dataDir = dirname(__DIR__) . '/data';
        $this->dataFile = $this->dataDir . '/webhook_links.json';
    }

    /**
     * Ensure data directory and file exist with correct permissions
     */
    public function ensureFileExists()
    {
        if (!is_dir($this->dataDir)) {
            @mkdir($this->dataDir, 0755, true);
        }
        if (!file_exists($this->dataFile)) {
            // Initialize as empty JSON array
            @file_put_contents($this->dataFile, "[]\n", LOCK_EX);
            @chmod($this->dataFile, 0644);
        }
        return is_writable($this->dataFile);
    }

    /**
     * Validate and normalize a URL
     */
    private function sanitizeUrl($url)
    {
        $url = is_string($url) ? trim($url) : '';
        if ($url === '') {
            return null;
        }
        // Basic validation
        if (filter_var($url, FILTER_VALIDATE_URL) === false) {
            return null;
        }
        return $url;
    }

    private function sanitizeOriginalFilename($value)
    {
        $value = is_string($value) ? trim($value) : '';
        if ($value === '') {
            return null;
        }

        $value = preg_replace('/[\x00-\x1F\x7F]/u', '', $value);
        $value = trim($value);
        if ($value === '') {
            return null;
        }

        if (strlen($value) > 255) {
            $value = substr($value, 0, 255);
        }

        return $value;
    }

    /**
     * Append a single URL entry to the JSON file
     * @param string $url
     * @param string $source optional source label
     * @return bool
     */
    public function logDropboxUrl($url, $source = 'webhook')
    {
        $clean = $this->sanitizeUrl($url);
        if ($clean === null) {
            return false;
        }
        if (!$this->ensureFileExists()) {
            error_log('JsonLogger: data file not writable');
            return false;
        }

        $entry = [
            'url' => $clean,
            'timestamp' => date('c'), // ISO 8601
            'source' => $source,
        ];

        return $this->appendEntry($entry);
    }

    /**
     * Log multiple URLs
     * @param array $urls
     * @return int number of successfully logged URLs
     */
    public function logMultipleDropboxUrls($urls, $source = 'webhook')
    {
        $count = 0;
        foreach ((array)$urls as $url) {
            if ($this->logDropboxUrl($url, $source)) {
                $count++;
            }
        }
        return $count;
    }

    public function logR2LinkPair($sourceUrl, $r2Url, $provider, $originalFilename = null)
    {
        $cleanSourceUrl = $this->sanitizeUrl($sourceUrl);
        $cleanR2Url = $this->sanitizeUrl($r2Url);
        if ($cleanSourceUrl === null || $cleanR2Url === null) {
            return false;
        }

        if (!$this->ensureFileExists()) {
            error_log('JsonLogger: data file not writable');
            return false;
        }

        $providerStr = is_string($provider) ? trim($provider) : '';
        if ($providerStr === '' || preg_match('/^[a-z0-9_-]{1,32}$/i', $providerStr) !== 1) {
            $providerStr = 'unknown';
        }

        $entry = [
            'source_url' => $cleanSourceUrl,
            'r2_url' => $cleanR2Url,
            'provider' => $providerStr,
            'created_at' => gmdate('c'),
        ];

        $cleanOriginalFilename = $this->sanitizeOriginalFilename($originalFilename);
        if ($cleanOriginalFilename !== null) {
            $entry['original_filename'] = $cleanOriginalFilename;
        }

        return $this->appendEntryDedup($entry, ['source_url', 'r2_url', 'provider']);
    }

    public function hasR2PairsInDeliveryLinks($deliveryLinks)
    {
        foreach ((array)$deliveryLinks as $item) {
            if (!is_array($item)) {
                continue;
            }
            $r2Url = isset($item['r2_url']) ? $item['r2_url'] : null;
            if (is_string($r2Url) && trim($r2Url) !== '') {
                return true;
            }
        }
        return false;
    }

    public function logDeliveryLinkPairs($deliveryLinks)
    {
        $count = 0;

        foreach ((array)$deliveryLinks as $item) {
            if (!is_array($item)) {
                continue;
            }

            $r2Url = isset($item['r2_url']) ? $item['r2_url'] : null;
            if (!is_string($r2Url) || trim($r2Url) === '') {
                continue;
            }

            $provider = isset($item['provider']) ? $item['provider'] : 'unknown';

            $sourceUrl = null;
            if (isset($item['direct_url']) && is_string($item['direct_url']) && trim($item['direct_url']) !== '') {
                $sourceUrl = $item['direct_url'];
            } elseif (isset($item['raw_url']) && is_string($item['raw_url']) && trim($item['raw_url']) !== '') {
                $sourceUrl = $item['raw_url'];
            }

            if ($sourceUrl === null) {
                continue;
            }

            $originalFilename = isset($item['original_filename']) ? $item['original_filename'] : null;

            if ($this->logR2LinkPair($sourceUrl, $r2Url, $provider, $originalFilename)) {
                $count++;
            }
        }

        return $count;
    }

    /**
     * Get recent logs (most recent first)
     * @param int $limit
     * @return array
     */
    public function getRecentLogs($limit = 50)
    {
        if (!$this->ensureFileExists()) {
            return [];
        }
        $data = $this->readAll();
        if (!is_array($data)) {
            return [];
        }
        // Sort DESC by timestamp
        usort($data, function ($a, $b) {
            $ta = isset($a['timestamp']) ? strtotime($a['timestamp']) : 0;
            $tb = isset($b['timestamp']) ? strtotime($b['timestamp']) : 0;
            return $tb <=> $ta;
        });
        return array_slice($data, 0, max(0, (int)$limit));
    }

    /**
     * Append an entry to JSON with file locking
     */
    private function appendEntry(array $entry)
    {
        $fp = @fopen($this->dataFile, 'c+');
        if (!$fp) {
            error_log('JsonLogger: cannot open data file for append');
            return false;
        }
        try {
            if (!flock($fp, LOCK_EX)) {
                error_log('JsonLogger: cannot lock data file');
                fclose($fp);
                return false;
            }
            // Read existing
            $size = filesize($this->dataFile);
            $json = '';
            if ($size > 0) {
                $json = fread($fp, $size);
            }
            $arr = json_decode($json, true);
            if (!is_array($arr)) {
                $arr = [];
            }
            $arr[] = $entry;

            // If rotation thresholds exceeded, rotate file and write only the new entry to a fresh file
            $maxEntries = $this->getMaxEntries();
            $maxBytes = $this->getMaxBytes();
            $needRotate = false;
            if ($maxEntries > 0 && count($arr) > $maxEntries) {
                $needRotate = true;
            }
            // Estimate bytes after write
            $serialized = json_encode($arr, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
            if ($maxBytes > 0 && strlen($serialized) > $maxBytes) {
                $needRotate = true;
            }

            if ($needRotate) {
                // Rotate current file to a timestamped backup
                $backup = $this->dataDir . '/webhook_links-' . date('Ymd-His') . '.json';
                // Ensure file pointer is closed before rename
                fflush($fp);
                flock($fp, LOCK_UN);
                fclose($fp);
                // Rename current file
                @rename($this->dataFile, $backup);
                // Start fresh file with only the last entry
                $fresh = [$entry];
                return @file_put_contents($this->dataFile, json_encode($fresh, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n", LOCK_EX) !== false;
            } else {
                // Truncate and write updated array
                ftruncate($fp, 0);
                rewind($fp);
                $ok = fwrite($fp, $serialized) !== false;
                fflush($fp);
                flock($fp, LOCK_UN);
                fclose($fp);
                return (bool)$ok;
            }
        } catch (Throwable $e) {
            try { flock($fp, LOCK_UN); fclose($fp); } catch (Throwable $e2) {}
            error_log('JsonLogger append error: ' . $e->getMessage());
            return false;
        }
    }

    private function appendEntryDedup(array $entry, array $dedupKeys)
    {
        $fp = @fopen($this->dataFile, 'c+');
        if (!$fp) {
            error_log('JsonLogger: cannot open data file for append');
            return false;
        }

        try {
            if (!flock($fp, LOCK_EX)) {
                error_log('JsonLogger: cannot lock data file');
                fclose($fp);
                return false;
            }

            $size = filesize($this->dataFile);
            $json = '';
            if ($size > 0) {
                $json = fread($fp, $size);
            }

            $arr = json_decode($json, true);
            if (!is_array($arr)) {
                $arr = [];
            }

            $matches = true;
            foreach (array_reverse($arr) as $existing) {
                if (!is_array($existing)) {
                    continue;
                }
                $matches = true;
                foreach ($dedupKeys as $key) {
                    if (!array_key_exists($key, $existing) || !array_key_exists($key, $entry)) {
                        $matches = false;
                        break;
                    }
                    if ((string)$existing[$key] !== (string)$entry[$key]) {
                        $matches = false;
                        break;
                    }
                }
                if ($matches) {
                    flock($fp, LOCK_UN);
                    fclose($fp);
                    return true;
                }
            }

            $arr[] = $entry;

            $maxEntries = $this->getMaxEntries();
            $maxBytes = $this->getMaxBytes();
            $needRotate = false;
            if ($maxEntries > 0 && count($arr) > $maxEntries) {
                $needRotate = true;
            }

            $serialized = json_encode($arr, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
            if ($maxBytes > 0 && strlen($serialized) > $maxBytes) {
                $needRotate = true;
            }

            if ($needRotate) {
                $backup = $this->dataDir . '/webhook_links-' . date('Ymd-His') . '.json';
                fflush($fp);
                flock($fp, LOCK_UN);
                fclose($fp);
                @rename($this->dataFile, $backup);
                $fresh = [$entry];
                return @file_put_contents(
                    $this->dataFile,
                    json_encode($fresh, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n",
                    LOCK_EX
                ) !== false;
            }

            ftruncate($fp, 0);
            rewind($fp);
            $ok = fwrite($fp, $serialized) !== false;
            fflush($fp);
            flock($fp, LOCK_UN);
            fclose($fp);
            return (bool)$ok;
        } catch (Throwable $e) {
            try {
                flock($fp, LOCK_UN);
                fclose($fp);
            } catch (Throwable $e2) {
            }
            error_log('JsonLogger append dedup error: ' . $e->getMessage());
            return false;
        }
    }

    /**
     * Read the full JSON array safely
     */
    private function readAll()
    {
        $fp = @fopen($this->dataFile, 'r');
        if (!$fp) {
            return [];
        }
        try {
            if (!flock($fp, LOCK_SH)) {
                fclose($fp);
                return [];
            }
            $json = stream_get_contents($fp);
            flock($fp, LOCK_UN);
            fclose($fp);
            $data = json_decode($json, true);
            return is_array($data) ? $data : [];
        } catch (Throwable $e) {
            try { flock($fp, LOCK_UN); fclose($fp); } catch (Throwable $e2) {}
            return [];
        }
    }

    /**
     * Rotation limits via environment
     */
    private function getMaxEntries()
    {
        $val = getenv('JSON_LOG_MAX_ENTRIES');
        if ($val === false || $val === null || trim((string)$val) === '') {
            return 5000; // default
        }
        $n = (int)$val;
        return $n < 0 ? 0 : $n;
    }

    private function getMaxBytes()
    {
        $val = getenv('JSON_LOG_MAX_BYTES');
        if ($val === false || $val === null || trim((string)$val) === '') {
            // default 5 MB
            return 5 * 1024 * 1024;
        }
        $n = (int)$val;
        return $n < 0 ? 0 : $n;
    }
}
