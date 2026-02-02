<?php
/**
 * Email Configuration
 * Configuration for IMAP connection to mail.kidpixel.fr
 */

return [
    'imap' => [
        'host' => 'mail.kidpixel.fr',
        'port' => 993,
        'encryption' => 'ssl',
        'username' => 'webhook@kidpixel.fr',
        'password' => 'z5NjmmWzJg5UBSmvBpZE',  // IMAP/SMTP password for kidpixel.fr
        'folder' => 'INBOX'
    ],
    'smtp' => [
        'host' => 'mail.kidpixel.fr',
        'port' => 587,
        'encryption' => 'tls',
        'username' => 'webhook@kidpixel.fr',
        'password' => 'z5NjmmWzJg5UBSmvBpZE'  // IMAP/SMTP password for kidpixel.fr
    ]
];
