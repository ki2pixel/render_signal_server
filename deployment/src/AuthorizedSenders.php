<?php
/**
 * Authorized Senders Management
 * Handles validation of email senders against authorized list
 */

class AuthorizedSenders
{
    /**
     * List of authorized email addresses (from Make.com blueprint)
     */
    private static $authorizedEmails = [
        'achats@media-solution.fr',
        'camille.moine.pro@gmail.com',
        'a.peault@media-solution.fr',
        'v.lorent@media-solution.fr',
        'technique@media-solution.fr',
        't.deslus@media-solution.fr'
    ];

    /**
     * Check if an email address is authorized
     * 
     * @param string $email Email address to check
     * @return bool True if authorized, false otherwise
     */
    public static function isAuthorized($email)
    {
        if (empty($email)) {
            return false;
        }

        // Case-insensitive comparison (as per Make.com blueprint)
        $email = strtolower(trim($email));
        
        foreach (self::$authorizedEmails as $authorizedEmail) {
            if (strtolower(trim($authorizedEmail)) === $email) {
                return true;
            }
        }

        return false;
    }

    /**
     * Get list of all authorized email addresses
     * 
     * @return array List of authorized emails
     */
    public static function getAuthorizedEmails()
    {
        return self::$authorizedEmails;
    }

    /**
     * Add a new authorized email address
     * 
     * @param string $email Email to add
     * @return bool True if added successfully
     */
    public static function addAuthorizedEmail($email)
    {
        if (empty($email) || self::isAuthorized($email)) {
            return false;
        }

        self::$authorizedEmails[] = trim($email);
        return true;
    }

    /**
     * Remove an authorized email address
     * 
     * @param string $email Email to remove
     * @return bool True if removed successfully
     */
    public static function removeAuthorizedEmail($email)
    {
        $email = strtolower(trim($email));
        $originalCount = count(self::$authorizedEmails);
        
        self::$authorizedEmails = array_filter(self::$authorizedEmails, function($authorizedEmail) use ($email) {
            return strtolower(trim($authorizedEmail)) !== $email;
        });

        return count(self::$authorizedEmails) < $originalCount;
    }
}
