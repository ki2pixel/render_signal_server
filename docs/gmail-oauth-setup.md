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
3. Donnez un nom à votre application
4. Notez l'**ID client** et le **secret client** générés

## Étape 4 : Obtenir un refresh token via OAuth Playground

1. Allez sur [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Cliquez sur l'icône d'engrenage (⚙️) en haut à droite
3. Cochez "Utiliser vos propres identifiants OAuth"
4. Dans la section "Scopes", entrez l'un des scopes suivants :
   - `https://mail.google.com/` (accès complet à l'API Gmail) - recommandé
   - `https://www.googleapis.com/auth/gmail.send` (uniquement pour l'envoi d'emails)
5. Cliquez sur "Authorize APIs" pour obtenir votre code d'autorisation
6. Échangez le code d'autorisation contre un refresh token
```
GMAIL_CLIENT_ID=votre_id_client
GMAIL_CLIENT_SECRET=votre_secret_client
GMAIL_REFRESH_TOKEN=le_refresh_token_obtenu
GMAIL_FROM_EMAIL=votre_email@gmail.com
AUTOREPONDEUR_TO=destinataire@example.com
```
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
