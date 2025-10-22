<?php
/**
 * LogMaintenance
 * Simple daily truncation for PHP error log file.
 *
 * Behavior:
 * - On first request after midnight (server timezone), truncate the error log file.
 * - Uses a marker file alongside the log to store last truncation date (YYYY-MM-DD).
 * - Safe no-op if files are missing or not writable.
 */
class LogMaintenance
{
    /**
     * Truncate the given log file once per calendar day.
     *
     * @param string $logFile Absolute path to the log file.
     * @param string|null $tz Optional timezone identifier (e.g., 'Europe/Luxembourg').
     * @return void
     */
    public static function truncateDaily(string $logFile, ?string $tz = null): void
    {
        try {
            if (!is_string($logFile) || $logFile === '') {
                return;
            }

            $logDir = dirname($logFile);
            if (!is_dir($logDir)) {
                return;
            }

            // Determine current date string in configured timezone (default: PHP/Server timezone)
            if ($tz) {
                $prevTz = date_default_timezone_get();
                @date_default_timezone_set($tz);
            }
            $today = date('Y-m-d');
            if ($tz) {
                @date_default_timezone_set($prevTz ?: 'UTC');
            }

            $marker = $logDir . '/.' . basename($logFile) . '.last_truncate';

            $last = null;
            if (is_file($marker)) {
                $last = trim((string)@file_get_contents($marker));
            }

            if ($last === $today) {
                // Already truncated today
                return;
            }

            // If the log file doesn't exist yet, just update marker
            if (!file_exists($logFile)) {
                @file_put_contents($marker, $today . "\n");
                return;
            }

            // Truncate file safely
            $fp = @fopen($logFile, 'c+');
            if ($fp === false) {
                // Cannot open log; bail without error
                return;
            }
            try {
                @flock($fp, LOCK_EX);
                @ftruncate($fp, 0);
                @fflush($fp);
                @flock($fp, LOCK_UN);
            } finally {
                @fclose($fp);
            }

            // Update marker
            @file_put_contents($marker, $today . "\n");

            // Optional: write a small header line to indicate reset
            @file_put_contents($logFile, '[' . date('d-M-Y H:i:s T') . "] Log reset (daily truncate)\n", FILE_APPEND | LOCK_EX);
        } catch (\Throwable $e) {
            // Silent failure; do not break request handling
        }
    }
}
