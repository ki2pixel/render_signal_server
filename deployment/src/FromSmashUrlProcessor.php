<?php
/**
 * FromSmash URL Processor
 * Extracts and returns FromSmash share URLs from email content.
 */

class FromSmashUrlProcessor
{
    /**
     * Regex pattern to match FromSmash URLs
     * Examples: https://fromsmash.com/OPhYnnPgFM-ct
     */
    private static $fromSmashPattern = '/(https?:\/\/(?:www\.)?fromsmash\.com\/[A-Za-z0-9_-]+)/i';

    /**
     * Extract FromSmash URLs from email content
     *
     * @param string $content Email content (HTML or text)
     * @return array Array of found FromSmash URLs
     */
    public static function extractFromSmashUrls($content)
    {
        if (empty($content)) {
            return [];
        }

        $matches = [];
        preg_match_all(self::$fromSmashPattern, $content, $matches);

        return isset($matches[1]) ? array_values(array_unique($matches[1])) : [];
    }

    /**
     * Process a single FromSmash URL
     * For FromSmash, no transformation is required; return as-is.
     *
     * @param string $url Raw FromSmash URL
     * @return string|null Processed URL or null if invalid
     */
    public static function processFromSmashUrl($url)
    {
        if (empty($url)) {
            return null;
        }
        return $url;
    }

    /**
     * Process all FromSmash URLs found in content
     *
     * @param string $content Email content
     * @return array Array of processed URLs
     */
    public static function processAllFromSmashUrls($content)
    {
        $urls = self::extractFromSmashUrls($content);
        $processed = [];
        foreach ($urls as $url) {
            $p = self::processFromSmashUrl($url);
            if ($p !== null) {
                $processed[] = $p;
            }
        }
        return $processed;
    }
}
