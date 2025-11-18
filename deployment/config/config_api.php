<?php
/**
 * deployment/config/config_api.php
 *
 * Configuration du mini-API de persistance JSON.
 * IMPORTANT: Ne committez jamais un vrai token ici en production.
 * Remplacez la valeur par un token fort au moment du déploiement (ou via un include non versionné).
 */

// Token d'accès API (à changer impérativement en prod)
if (!defined('CONFIG_API_TOKEN')) {
    define('CONFIG_API_TOKEN', '11tM9kTIhw0dPW0eF3oUjioVRmkADVoYPEDBDXG3satW0pAYphhMCKBWeM3iDol1');
}

// Répertoire de stockage des fichiers JSON (en dehors de public_html si possible)
if (!defined('CONFIG_API_STORAGE_DIR')) {
    // Stocke dans deployment/public_html/../data/app_config/
    $base = realpath(__DIR__ . '/../');
    $dir = $base . '/data/app_config';
    define('CONFIG_API_STORAGE_DIR', $dir);
}
