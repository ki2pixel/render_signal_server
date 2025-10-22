<?php
/**
 * deployment/public_html/config_api.php
 *
 * Mini-API de persistance de configurations JSON par clé.
 * Sécurité via jeton Bearer.
 *
 * GET  /config_api.php?key=<config_key>
 *   Headers: Authorization: Bearer <TOKEN>
 *   -> { success: true, config: { ... } }
 *
 * POST /config_api.php
 *   Headers: Authorization: Bearer <TOKEN>, Content-Type: application/json
 *   Body: { "key": "webhook_config", "config": { ... } }
 *   -> { success: true }
 */

// Forcer JSON
header('Content-Type: application/json; charset=utf-8');

// Charger la configuration
$cfgPath = __DIR__ . '/../config/config_api.php';
if (!file_exists($cfgPath)) {
    http_response_code(500);
    echo json_encode([ 'success' => false, 'message' => 'Config file missing.' ]);
    exit;
}
require_once $cfgPath;

// Vérifier le token Bearer
function get_bearer_token(): ?string {
    $hdr = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
    if (!$hdr && function_exists('apache_request_headers')) {
        $headers = apache_request_headers();
        if (isset($headers['Authorization'])) $hdr = $headers['Authorization'];
    }
    if (!$hdr) return null;
    if (stripos($hdr, 'Bearer ') === 0) {
        return trim(substr($hdr, 7));
    }
    return null;
}

$token = get_bearer_token();
if (!$token || !defined('CONFIG_API_TOKEN') || $token !== CONFIG_API_TOKEN) {
    http_response_code(401);
    echo json_encode([ 'success' => false, 'message' => 'Unauthorized' ]);
    exit;
}

// Sanitize key (lowercase alphanum, dash, underscore)
function sanitize_key($k) {
    $k = trim(strtolower((string)$k));
    if (!preg_match('/^[a-z0-9_\-]{1,128}$/', $k)) return null;
    return $k;
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

// S'assurer que le répertoire de stockage existe
$storageDir = CONFIG_API_STORAGE_DIR;
if (!is_dir($storageDir)) {
    if (!@mkdir($storageDir, 0775, true) && !is_dir($storageDir)) {
        http_response_code(500);
        echo json_encode([ 'success' => false, 'message' => 'Storage directory not writable.' ]);
        exit;
    }
}

function path_for_key($dir, $key) {
    return rtrim($dir, '/').'/'.$key.'.json';
}

try {
    if ($method === 'GET') {
        $key = $_GET['key'] ?? '';
        $key = sanitize_key($key);
        if (!$key) {
            http_response_code(400);
            echo json_encode([ 'success' => false, 'message' => 'Invalid key' ]);
            exit;
        }
        $path = path_for_key($storageDir, $key);
        if (!file_exists($path)) {
            echo json_encode([ 'success' => true, 'config' => new stdClass() ]);
            exit;
        }
        $raw = @file_get_contents($path);
        if ($raw === false) {
            http_response_code(500);
            echo json_encode([ 'success' => false, 'message' => 'Read error' ]);
            exit;
        }
        $json = json_decode($raw, true);
        if (!is_array($json)) $json = [];
        echo json_encode([ 'success' => true, 'config' => $json ]);
        exit;
    }

    if ($method === 'POST') {
        $payload = json_decode(file_get_contents('php://input'), true);
        $key = $payload['key'] ?? '';
        $cfg = $payload['config'] ?? null;
        $key = sanitize_key($key);
        if (!$key || !is_array($cfg)) {
            http_response_code(400);
            echo json_encode([ 'success' => false, 'message' => 'Invalid payload' ]);
            exit;
        }
        // Ajoute un champ metadata minimal
        $cfg['_updated_at'] = gmdate('c');
        $path = path_for_key($storageDir, $key);
        $ok = @file_put_contents($path, json_encode($cfg, JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));
        if ($ok === false) {
            http_response_code(500);
            echo json_encode([ 'success' => false, 'message' => 'Write error' ]);
            exit;
        }
        echo json_encode([ 'success' => true ]);
        exit;
    }

    http_response_code(405);
    echo json_encode([ 'success' => false, 'message' => 'Method not allowed' ]);
} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode([ 'success' => false, 'message' => 'Server error' ]);
}
