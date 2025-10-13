<?php
/**
 * Dropbox URL Processor
 * Handles extraction and transformation of Dropbox URLs from email content
 */

class DropboxUrlProcessor
{
    /**
     * Regex pattern to match Dropbox URLs (from Make.com blueprint)
     */
    private static $dropboxPattern = '/(https:\/\/www\.dropbox\.com\/\S+)/';

    /**
     * Extract Dropbox URLs from email content
     * 
     * @param string $content Email content (HTML or text)
     * @return array Array of found Dropbox URLs
     */
    public static function extractDropboxUrls($content)
    {
        if (empty($content)) {
            return [];
        }

        $matches = [];
        preg_match_all(self::$dropboxPattern, $content, $matches);
        
        return isset($matches[1]) ? $matches[1] : [];
    }

    /**
     * Process a single Dropbox URL according to Make.com blueprint logic
     * 
     * @param string $url Raw Dropbox URL
     * @return string|null Processed URL or null if invalid
     */
    public static function processDropboxUrl($url)
    {
        if (empty($url)) {
            return null;
        }

        // Step 1: Replace HTML entities (&amp; → &)
        $cleanUrl = str_replace('&amp;', '&', $url);

        // Step 2: Replace ?dl=0 with ?dl=1
        $urlWithDl1 = str_replace('?dl=0', '?dl=1', $cleanUrl);

        // Step 3: Replace &dl=0 with &dl=1 if ?dl=0 replacement didn't occur
        if ($urlWithDl1 === $cleanUrl) {
            $urlWithDl1 = str_replace('&dl=0', '&dl=1', $cleanUrl);
        }

        // Step 4: Ensure URL has dl=1 parameter
        $finalUrl = self::ensureDirectDownload($urlWithDl1);

        return $finalUrl;
    }

    /**
     * Ensure URL has dl=1 parameter for direct download
     * 
     * @param string $url URL to process
     * @return string URL with dl=1 parameter
     */
    private static function ensureDirectDownload($url)
    {
        // If URL already contains dl=1, return as is
        if (strpos($url, 'dl=1') !== false) {
            return $url;
        }

        // If URL contains ?, add &dl=1
        if (strpos($url, '?') !== false) {
            return $url . '&dl=1';
        }

        // If URL doesn't contain ?, add ?dl=1
        return $url . '?dl=1';
    }

    /**
     * Process all Dropbox URLs found in content
     * 
     * @param string $content Email content
     * @return array Array of processed URLs
     */
    public static function processAllDropboxUrls($content)
    {
        $urls = self::extractDropboxUrls($content);
        $processedUrls = [];

        foreach ($urls as $url) {
            $processed = self::processDropboxUrl($url);
            if ($processed !== null) {
                $processedUrls[] = $processed;
            }
        }

        return $processedUrls;
    }

    /**
     * Validate if a URL is a valid Dropbox URL
     * 
     * @param string $url URL to validate
     * @return bool True if valid Dropbox URL
     */
    public static function isValidDropboxUrl($url)
    {
        return preg_match(self::$dropboxPattern, $url) === 1;
    }
}
