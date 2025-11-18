# Configuration de l'authentification Gmail OAuth

Ce guide explique comment configurer l'authentification OAuth 2.0 pour envoyer des e-mails via l'API Gmail.

## Prérequis

1. Un compte Google (Gmail)
2. Accès à [Google Cloud Console](https://console.cloud.google.com/)
3. Accès à [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)

## Étape 1 : Configurer un projet dans Google Cloud Console

1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un nouveau projet ou sélectionnez-en un existant
3. Activez l'API Gmail :
   - Allez dans "APIs et services" > "Bibliothèque"
   - Recherchez "Gmail API"
   - Cliquez sur "Activer"

## Étape 2 : Configurer l'écran de consentement OAuth

1. Dans la console, allez dans "APIs et services" > "Écran de consentement OAuth"
2. Sélectionnez le type d'utilisateur (Externe ou Interne)
3. Remplissez les informations requises :
   - Nom de l'application
   - E-mail de support
   - E-mail du contact de la protection des données
4. Cliquez sur "Enregistrer et continuer"
5. Pour les champs de portée, vous pouvez ignorer pour l'instant
6. Ajoutez-vous comme utilisateur de test

## Étape 3 : Générer les identifiants OAuth 2.0

1. Allez dans "Identifiants" > "Créer des identifiants" > "ID client OAuth"
2. Sélectionnez "Application de bureau"
4. Notez l'**ID client** et le **secret client** générés

## Étape 4 : Obtenir un refresh token via OAuth Playground

1. Allez sur [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Cliquez sur## Validation de l'OAuth Gmail

### Outils de Validation

#### Script CLI (`deployment/scripts/gmail_oauth_connection_test.php`)
- Valide la configuration OAuth et envoie un e-mail de test
- Mode `--dry-run` pour validation sans envoi
- Envoi réel pour test complet
- Historisation des runs dans `deployment/data/gmail_oauth_check_history.jsonl`

#### Page Web (`deployment/public_html/GmailOAuthTest.php`)
- Test depuis un navigateur (dry-run + send)
- Endpoint `action=auto-check` pour vérification périodique
- Protégé par clé `GMAIL_OAUTH_CHECK_KEY`
- Intervalle configurable via `GMAIL_OAUTH_CHECK_INTERVAL_DAYS` (défaut 7j)
- Persistance de l'état dans `deployment/data/gmail_oauth_last_check.json`

### Configuration Requise
- `GMAIL_CLIENT_ID` : ID client OAuth
- `GMAIL_CLIENT_SECRET` : Secret client OAuth
- `GMAIL_REFRESH_TOKEN` : Refresh token OAuth
- `GMAIL_FROM_EMAIL` : Adresse e-mail expéditrice
- `GMAIL_OAUTH_CHECK_KEY` : Clé pour l'auto-check (optionnel)
- `GMAIL_OAUTH_CHECK_INTERVAL_DAYS` : Intervalle d'auto-check (défaut 7)
- `GMAIL_OAUTH_TEST_TO` :Destinataire des tests (optionnel)

### Déploiement DirectAdmin
- Inclusion de `bootstrap_env.php` via `__DIR__` dans les scripts PHP
- Auto-prepend dans `.htaccess` : `php_value auto_prepend_file bootstrap_env.php`
- Chemins résolus : `public_html/` pour web, `data/` pour stockage
- Persistance OAuth dans `domains/webhook.kidpixel.fr/data/env.local.php`) avec le contenu suivant :

```php
<?php
return [
    // Identifiants Google Cloud
    'GMAIL_CLIENT_ID' => 'votre_id_client',
    'GMAIL_CLIENT_SECRET' => 'votre_secret_client',
    'GMAIL_REFRESH_TOKEN' => 'votre_refresh_token',
    
    // Configuration de l'application
    'GMAIL_REDIRECT_URI' => 'https://webhook.kidpixel.fr/oauth_callback.php',
    'GMAIL_FROM_EMAIL' => 'votre@email.com',
    'AUTOREPONDEUR_TO' => 'destinataire@example.com',
    
    // Sécurité
    'GMAIL_OAUTH_CHECK_KEY' => 'change_me_strong_key',
    'GMAIL_OAUTH_TEST_TO' => 'camille.moine.pro@gmail.com',
    'GMAIL_OAUTH_CHECK_INTERVAL_DAYS' => '7'
];
```

> **Important** : 
> - Assurez-vous que le fichier est protégé (chmod 600 recommandé) et n'est pas accessible depuis le web.
> - Le fichier doit être placé en dehors du répertoire `public_html`.
> - Les chemins sont configurés pour l'environnement DirectAdmin standard.

### Initialisation via `bootstrap_env.php`

Pour garantir que toutes les pages PHP chargent automatiquement les secrets (`env.local.php`), activez l'auto-prepend dans `.htaccess` (ou la configuration vhost) au sein de `deployment/public_html/` :

```apache
php_value auto_prepend_file "/home/kidp0/domains/webhook.kidpixel.fr/public_html/bootstrap_env.php"
```

Le helper `env_bootstrap_path()` différencie désormais les chemins sous `public_html/` et ceux du dossier `data/` :

- Les fichiers web (`*.php`, assets) restent sous `/home/kidp0/domains/webhook.kidpixel.fr/public_html/…`
- Les secrets et persistances (`data/env.local.php`, historiques) résident sous `/home/kidp0/domains/webhook.kidpixel.fr/data/`

> **Sécurité** : le dossier `deployment/data/` doit rester hors webroot. Vérifiez les permissions (ex: `chmod 600 deployment/data/env.local.php`) et limitez l'accès FTP/SFTP aux comptes autorisés.

## Validation de la connexion

Un script CLI est fourni pour vérifier la validité OAuth et, si souhaité, envoyer un e‑mail de test : `deployment/scripts/gmail_oauth_connection_test.php`.

### 1) Dry-run (obtention du token uniquement)

Vérifie l'authentification sans envoyer d'e‑mail.

```bash
php deployment/scripts/gmail_oauth_connection_test.php --dry-run
```
Sortie attendue (exemple) :
```json
{
  "success": true,
  "message": "Connexion OAuth valide (dry-run)",
  "details": {
    "http_status": 200,
    "token_type": "Bearer",
    "expires_in": 3599
  }
}

## Auto-check (cron)
```
Notes :

- Si `--to` est omis, le script utilise `AUTOREPONDEUR_TO` puis `GMAIL_FROM_EMAIL`.
- Sortie JSON : `success`, `message`, `details` (statut HTTP, erreur éventuelle). Les secrets sont masqués.
- Codes de sortie : `0` = succès, `1` = échec.

### 2) Test via l'interface web `GmailOAuthTest.php`

La page `deployment/public_html/GmailOAuthTest.php` expose trois actions :

- `POST ?action=dry-run` → vérifie l'obtention du token. Réponse JSON (ou HTML si chargé directement).
- `POST ?action=send` → envoie un e‑mail HTML de test via `deployment/src/GmailMailer.php`, retourne les IDs Gmail (`gmail_message_id`, `gmail_thread_id`).
- `POST/GET ?action=auto-check` → mode cron/monitoring. Respecte `GMAIL_OAUTH_CHECK_INTERVAL_DAYS`, supporte `force=1` pour ignorer l'intervalle.

Toutes les réponses asynchrones renvoient du JSON valide (token partiellement masqué), évitant l'ancien message « Unexpected token '<' » côté front. Les erreurs HTTP (400/422/502) retournent un message explicite (`message`, `details`).

Les exécutions auto-check journalisent l'état dans :

- `deployment/data/gmail_oauth_last_check.json` (dernier statut)
- `deployment/data/gmail_oauth_check_history.jsonl` (historique append-only)

> **Bonnes pratiques** : protégez `GmailOAuthTest.php` (HTTP auth, IP allowlist) et définissez `GMAIL_OAUTH_CHECK_KEY`. L'auto-check crée aussi un log d'erreurs `deployment/public_html/gmail_oauth_errors.log` pour diagnostiquer les problèmes serveur.

### 3) Auto-check (cron) et forçage

L’endpoint web `deployment/public_html/GmailOAuthTest.php` expose une action `auto-check` pour valider périodiquement la connexion (et envoyer un e‑mail de test au besoin). Configurez ces variables d’environnement :

```
GMAIL_OAUTH_TEST_TO="camille.moine.pro@gmail.com"   # destinataire test
GMAIL_OAUTH_CHECK_INTERVAL_DAYS="7"                 # intervalle minimal entre 2 checks
GMAIL_OAUTH_CHECK_KEY="change_me_strong_key"       # clé requise pour l’endpoint
```

- Exemple cron (POST, recommandé) : exécution quotidienne, le script applique l’intervalle côté serveur.
```bash
/usr/bin/curl -fsS --retry 3 -X POST \
  -d "action=auto-check" \
  -d "key=change_me_strong_key" \
  "https://votre-domaine.tld/GmailOAuthTest.php" >/dev/null 2>&1
```

- Variante GET (moins privé car la clé apparaît dans l’URL) :
```bash
/usr/bin/curl -fsS "https://votre-domaine.tld/GmailOAuthTest.php?action=auto-check&key=change_me_strong_key" >/dev/null 2>&1
```

- Forcer un run immédiat (ignorer l’intervalle) :
```bash
curl -sS "https://votre-domaine.tld/GmailOAuthTest.php?action=auto-check&key=change_me_strong_key&force=1"
```

Notes :
- Les résultats sont persistés dans `deployment/data/gmail_oauth_last_check.json` et l’historique dans `deployment/data/gmail_oauth_check_history.jsonl`.
- La réponse JSON inclut `gmail_message_id`/`gmail_thread_id` pour la traçabilité.
- Sécurité : protégez la page par clé (`GMAIL_OAUTH_CHECK_KEY`) et idéalement par Auth HTTP/IP allowlist si public.

## Dépannage

- **Erreur "invalid_grant"** : Le refresh token a expiré. Générez-en un nouveau.
- **Erreur d'autorisation** : Vérifiez que le scope accordé est `gmail.send`.
- **E‑mails non reçus** : Vérifiez le dossier spam et les journaux d'erreurs.

## Sécurité

- Ne partagez jamais votre `client_secret` ou `refresh_token`.
- Régénérez vos jetons régulièrement.
- Utilisez des variables d'environnement pour stocker les identifiants.

## Références

- [Documentation de l'API Gmail](https://developers.google.com/gmail/api/guides)
- [Guide OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
