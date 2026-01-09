<?php
/**
 * deployment/config/config_api.php
 *
 * Configuration du mini-API de persistance JSON.
 * IMPORTANT: les secrets doivent être injectés via env.local.php ou variables d'environnement.
 */

if (!function_exists('config_api_load_value')) {
    /**
     * Récupère une valeur depuis l'environnement ou, à défaut, depuis deployment/data/env.local.php.
     */
    function config_api_load_value(string $key, ?string $default = null): ?string
    {
        $envValue = getenv($key);
        if ($envValue !== false && $envValue !== '') {
            return $envValue;
        }

        static $localEnv = null;
        if ($localEnv === null) {
            $localFile = realpath(__DIR__ . '/../data/env.local.php');
            if ($localFile && is_readable($localFile)) {
                $loaded = include $localFile;
                $localEnv = is_array($loaded) ? $loaded : [];
            } else {
                $localEnv = [];
            }
        }

        if (array_key_exists($key, $localEnv) && $localEnv[$key] !== '') {
            $value = $localEnv[$key];
            return is_scalar($value) ? (string) $value : json_encode($value, JSON_UNESCAPED_UNICODE);
        }

        return $default;
    }
}

// Token d'accès API (à définir via env)
if (!defined('CONFIG_API_TOKEN')) {
    $token = config_api_load_value('CONFIG_API_TOKEN');
    if (!$token) {
        $token = 'changeme-config-api-token';
    }
    define('CONFIG_API_TOKEN', $token);
}

// Répertoire de stockage des fichiers JSON (fallback vers data/app_config)
if (!defined('CONFIG_API_STORAGE_DIR')) {
    $dir = config_api_load_value('CONFIG_API_STORAGE_DIR');
    if (!$dir) {
        $base = realpath(__DIR__ . '/../');
        $dir = $base . '/data/app_config';
    }
    define('CONFIG_API_STORAGE_DIR', $dir);
}
