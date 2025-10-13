<?php
/**
 * Email Configuration
 * Configuration for IMAP connection to inbox.lt
 */

return [
    'imap' => [
        'host' => 'mail.inbox.lt',
        'port' => 993,
        'encryption' => 'ssl',
        'username' => 'kidpixel@inbox.lt',
        'password' => 'YvP3Zw66Xx',  // Special IMAP/SMTP password for inbox.lt
        'folder' => 'INBOX'
    ],
    'smtp' => [
        'host' => 'mail.inbox.lt',
        'port' => 587,
        'encryption' => 'tls',
        'username' => 'kidpixel@inbox.lt',
        'password' => 'YvP3Zw66Xx'  // Special IMAP/SMTP password for inbox.lt
    ]
];
