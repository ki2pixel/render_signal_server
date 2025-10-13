<?php
/**
 * SwissTransfer URL Processor
 * Extracts and returns SwissTransfer download URLs from email content.
 */

class SwissTransferUrlProcessor
{
    /**
     * Regex pattern to match SwissTransfer URLs
     * Examples: https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12
     */
    private static $swissPattern = '/(https?:\/\/(?:www\.)?swisstransfer\.com\/d\/[A-Za-z0-9-]+)/i';

    /**
     * Extract SwissTransfer URLs from email content
     *
     * @param string $content Email content (HTML or text)
     * @return array Array of found SwissTransfer URLs
     */
    public static function extractSwissTransferUrls($content)
    {
        if (empty($content)) {
            return [];
        }

        $matches = [];
        preg_match_all(self::$swissPattern, $content, $matches);

        return isset($matches[1]) ? array_values(array_unique($matches[1])) : [];
    }

    /**
     * Process a single SwissTransfer URL
     * For SwissTransfer, no transformation is required; return as-is.
     *
     * @param string $url Raw SwissTransfer URL
     * @return string|null Processed URL or null if invalid
     */
    public static function processSwissTransferUrl($url)
    {
        if (empty($url)) {
            return null;
        }
        return $url;
    }

    /**
     * Process all SwissTransfer URLs found in content
     *
     * @param string $content Email content
     * @return array Array of processed URLs
     */
    public static function processAllSwissTransferUrls($content)
    {
        $urls = self::extractSwissTransferUrls($content);
        $processed = [];
        foreach ($urls as $url) {
            $p = self::processSwissTransferUrl($url);
            if ($p !== null) {
                $processed[] = $p;
            }
        }
        return $processed;
    }
}
