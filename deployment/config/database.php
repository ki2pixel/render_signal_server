<?php
/**
 * Database Configuration
 * Configuration for MySQL connection to kidpixel.fr
 */

return [
    'host' => 'kidpixel.fr',
    'database' => 'kidp0_make',
    'username' => 'kidp0_make',
    'password' => 'M8BJzAwusfMSZAqg8jwy',
    'charset' => 'utf8mb4',
    'options' => [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]
];
