# Déploiement

## Gunicorn + Reverse Proxy

1. Préparer l’environnement Python (prioritaire)
```
source /mnt/venv_ext4/venv_render_signal_server/bin/activate
```

> Alternative locale : si le montage partagé n’est pas accessible (CI, poste externe), créez un virtualenv dédié (`python3 -m venv .venv && source .venv/bin/activate`) avant d’installer les dépendances.

2. Installer les dépendances dans l’environnement actif
```
pip install -r requirements.txt
pip install gunicorn
```

3. Lancer via systemd (exemple)
```
[Unit]
Description=render-signal-server
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/render_signal_server
Environment="FLASK_SECRET_KEY=..."
Environment="DASHBOARD_USER=..."
Environment="DASHBOARD_PASSWORD=..."
# ... autres ENV (voir configuration.md)
ExecStart=/mnt/venv_ext4/venv_render_signal_server/bin/gunicorn -w 2 -b 127.0.0.1:10000 app_render:app
Restart=always

[Install]
WantedBy=multi-user.target
```

4. Reverse proxy (Nginx – extrait)
```
location / {
    proxy_pass http://127.0.0.1:10000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Dossier `deployment/` (PHP)

Le répertoire `deployment/` contient une application PHP autonome reproduisant le scénario Make.com (IMAP, extraction d'URL Dropbox, logs MySQL, dashboard). Elle est indépendante du serveur Flask. Voir `deployment/README.md` et `deployment/deployment-guide.md` pour l'installer côté PHP si nécessaire.

### Pages de test (diagnostic R2)

Les pages suivantes servent de support de diagnostic pour valider end-to-end l'offload R2 et l'état de `deployment/data/webhook_links.json` :

- `deployment/public_html/test.php`
  - Test IMAP + DB (flux complet côté PHP)
  - Test « provider-only » (extraction locale Dropbox/FromSmash/SwissTransfer sans écriture DB)
  - **Test "Offload via Worker"** : permet d'obtenir un vrai `r2_url` depuis le Worker Cloudflare et de simuler un webhook Make-style
  - Affiche un diagnostic `webhook_links.json` : conformité schéma, entrées legacy vs R2, comptage par provider, dernières entrées, présence d'`original_filename`.

- `deployment/public_html/test-direct.php`
  - Test direct d'extraction d'URLs (sans IMAP)
  - **Test "Offload via Worker"** : similaire à test.php mais sans passer par IMAP
  - Affiche aussi le diagnostic `webhook_links.json` enrichi (paires R2, nom de fichier original, différenciation legacy/R2).

Pour éviter des conflits d'inclusion PHP, la logique de diagnostic est consolidée dans un seul helper :

- `deployment/src/WebhookTestUtils.php` (fonctions `loadWebhookLinksDiagnostics()`, `fetchR2UrlViaWorker()`)

#### Configuration requise pour les tests R2

Pour utiliser le mode "Offload via Worker" dans les pages PHP, configurez les variables d'environnement suivantes dans `deployment/data/env.local.php` :

```php
<?php
// Configuration R2 Worker pour tests PHP
putenv('R2_FETCH_ENDPOINT=https://r2-fetch.your-worker.workers.dev');
putenv('R2_FETCH_TOKEN=votre-secret-token-partage');
putenv('R2_BUCKET_NAME=render-signal-media');
putenv('R2_PUBLIC_BASE_URL=https://media.yourdomain.com');
?>
```

**Sécurité** : Le token `R2_FETCH_TOKEN` doit être identique à celui configuré dans le Worker Cloudflare et dans les variables d'environnement Render.

#### Fonctionnement des tests R2

1. **Extraction** : Les pages détectent les URLs Dropbox/FromSmash/SwissTransfer dans le contenu fourni
2. **Offload** : Pour chaque URL, `fetchR2UrlViaWorker()` appelle le Worker Cloudflare avec le token d'authentification
3. **Simulation** : Si l'offload réussit, les pages simulent l'envoi d'un webhook avec les `delivery_links` enrichies (`r2_url`, `original_filename`)
4. **Journalisation** : `deployment/src/JsonLogger.php` écrit chaque paire via `logR2LinkPair()` / `logDeliveryLinkPairs()` afin de conserver une trace alignée avec Render (sans champ `email_id`, déduplication stricte).
5. **Diagnostics** : Les résultats détaillés (succès/échec, payloads, réponses Worker, entrées `webhook_links.json`) sont affichés pour le débogage

Ces pages sont prévues pour un usage admin/diagnostic uniquement et nécessitent une configuration correcte du Worker R2.

### Configuration DirectAdmin (Gmail OAuth)

- **Auto-prepend** : activer dans `.htaccess` (ou via DirectAdmin) :

  ```apache
  php_value auto_prepend_file "/home/kidp0/domains/webhook.kidpixel.fr/public_html/bootstrap_env.php"
  ```

  Cela garantit que `deployment/public_html/bootstrap_env.php` charge `deployment/data/env.local.php` et injecte les variables d'environnement avant toute exécution.

- **Chemins absolus** : `env_bootstrap_path()` résout automatiquement les fichiers sous `public_html/` et `data/`. Les secrets (OAuth, historiques) doivent rester dans `/home/kidp0/domains/webhook.kidpixel.fr/data/` avec des permissions restrictives (`chmod 600` conseillé).

- **Journaux** : la page `GmailOAuthTest.php` écrit les erreurs PHP dans `deployment/public_html/gmail_oauth_errors.log`. Surveillez ce fichier lors des vérifications post-déploiement.

- **Vérifications recommandées** :
  - Accéder à `https://<domaine>/GmailOAuthTest.php?_format=json` pour vérifier la configuration (réponse JSON `status: success`).
  - Tester `POST action=dry-run` et `POST action=send` (via bouton ou `curl`) pour confirmer l'obtention du token et l'envoi Gmail.
  - Lancer `POST action=auto-check&force=1` pour créer/mettre à jour `deployment/data/gmail_oauth_last_check.json` et `.../gmail_oauth_check_history.jsonl`.
  - Protéger l'endpoint via `GMAIL_OAUTH_CHECK_KEY` (et idéalement Auth HTTP/IP allowlist).

## Configuration des Magic Links

### Variables d'environnement requises

- `FLASK_SECRET_KEY` (obligatoire) : Clé secrète utilisée pour signer les tokens. Doit être identique sur tous les workers.
  ```
  FLASK_SECRET_KEY=votre_cle_secrete_tres_longue_et_aleatoire
  ```

### Variables d'environnement optionnelles

- `MAGIC_LINK_TTL_SECONDS` (optionnel, défaut: 900 - 15 minutes) :
  Durée de validité des liens à usage unique en secondes.
  ```
  MAGIC_LINK_TTL_SECONDS=900
  ```

- `MAGIC_LINK_TOKENS_FILE` (optionnel, défaut: `./magic_link_tokens.json`) :
  Chemin vers le fichier de stockage des tokens. Doit être accessible en écriture par l'utilisateur du service.
  ```
  MAGIC_LINK_TOKENS_FILE=/var/lib/render_signal_server/magic_link_tokens.json
  ```

### Recommandations de sécurité

1. **Stockage sécurisé** :
   - Placez le fichier des tokens dans un répertoire protégé (ex: `/var/lib/render_signal_server/`)
   - Définissez des permissions restrictives :
     ```bash
     chown www-data:www-data /var/lib/render_signal_server/magic_link_tokens.json
     chmod 600 /var/lib/render_signal_server/magic_link_tokens.json
     ```

2. **Rotation des clés** :
   - Régénérez périodiquement `FLASK_SECRET_KEY` pour invalider les tokens existants
   - Planifiez une rotation tous les 3-6 mois ou selon votre politique de sécurité

3. **Surveillance** :
   - Surveillez la taille du fichier de tokens pour détecter les abus
   - Configurez des alertes pour les échecs d'authentification par magic link

### Stockage partagé via API PHP (optionnel mais recommandé sur Render)

Lorsque l'application tourne sur Render (filesystem éphémère, multi-workers), activez l'API PHP `config_api.php` comme backend de stockage :

- Variables supplémentaires à définir côté Render :
  ```bash
  EXTERNAL_CONFIG_BASE_URL=https://webhook.kidpixel.fr
  CONFIG_API_TOKEN=token-ultra-secret
  CONFIG_API_STORAGE_DIR=/home/kidp0/domains/.../data/app_config
  ```
- `MagicLinkService` écrit alors les tokens (one-shot + permanents) dans `deployment/data/app_config/magic_link_tokens.json` via l'API PHP. Le fichier local `MAGIC_LINK_TOKENS_FILE` ne sert plus que de fallback.
- Sur le serveur PHP:
  - `deployment/config/config_api.php` doit charger `CONFIG_API_TOKEN` + `CONFIG_API_STORAGE_DIR` via `env.local.php`.
  - Vérifiez que le répertoire `app_config/` est hors `public_html` et possède des permissions 750 / fichiers 640.
- En cas d'indisponibilité du backend PHP (maintenance, jeton invalide), `MagicLinkService` retombe automatiquement sur le fichier local avec verrou inter-processus, et logge un warning `MAGIC_LINK: external store unavailable`.

## Vérifications post-déploiement
- Accès HTTPS au domaine et au login `/login`.
- `GET /api/ping` renvoie `200`.
- Les tâches de fond démarrent (logs `BACKGROUND_TASKS`).
- Les variables d'environnement sensibles sont présentes.
- Vérifiez que le fichier de tokens est accessible et a les bonnes permissions.
- **R2** : déclencher une capture d’e-mail contenant un lien Dropbox et vérifier (logs + `deployment/public_html/test.php`) que `r2_url` et `original_filename` sont persistés dans `deployment/data/webhook_links.json`. En cas d’échec, confirmer que `R2_FETCH_TOKEN` côté Render/Worker est identique.

### Observabilité & Signaux

- Le processus journalise `PROCESS: SIGTERM received; ...` lors d'un redémarrage Render/OS (handler SIGTERM).
- Un heartbeat périodique loggue l'état des threads (`HEARTBEAT: alive (bg_poller=..., make_watcher=...)`).

### Paramètres Gunicorn recommandés (Render)

- `GUNICORN_CMD_ARGS="--timeout 120 --graceful-timeout 30 --keep-alive 75 --threads 2 --max-requests 15000 --max-requests-jitter 3000"`
- Objectif: redémarrages contrôlés quotidiens, stabilité des connexions et gestion mémoire.

### Notes opérationnelles (poller IMAP singleton)

- Activer `ENABLE_BACKGROUND_TASKS=true` uniquement sur un seul worker/process.
- Vérifier les logs au démarrage: message indiquant « singleton lock acquis ».
- Si nécessaire, définir `BG_POLLER_LOCK_FILE` pour contrôler l'emplacement du verrou.

### Notes UI (fenêtre horaire des webhooks)

- Tester `GET /api/get_webhook_time_window` puis `POST /api/set_webhook_time_window` depuis l'UI `dashboard.html`.
- Vérifier que les payloads webhook incluent `webhooks_time_start` / `webhooks_time_end` lorsque configurés.

## Déploiement Render via image Docker (GHCR → Render)

### Vue d'ensemble

- Le dépôt fournit désormais un `Dockerfile` racine qui construit l'application Flask/Gunicorn avec la configuration standard (`app_render.py`, services orientés métier, tâches de fond).
- Un workflow GitHub Actions (`.github/workflows/render-image.yml`) :
  1. Construit l'image Docker.
  2. La pousse sur GitHub Container Registry (GHCR) avec les tags `latest` et `<commit-sha>`.
  3. Déclenche un déploiement Render image-based via:
     - Le Deploy Hook (`RENDER_DEPLOY_HOOK_URL`) si disponible.
     - Sinon, l'API Render `/v1/services/{serviceId}/deploys` avec `imageUrl`.

### Pré-requis secrets (GitHub)

- `GHCR_TOKEN` (facultatif) : token PAT ou `GITHUB_TOKEN`. Utilisé pour `docker login`. À défaut, `GITHUB_TOKEN` suffit si authorisations packages activées.
- `GHCR_USERNAME` (facultatif) : nom d'utilisateur PAT. Par défaut `github.actor`.
- `RENDER_DEPLOY_HOOK_URL` : URL Render Deploy Hook (préfixe `https://api.render.com/deploy/`). Optionnel si API utilisée.
- `RENDER_API_KEY`, `RENDER_SERVICE_ID` : requis si l'on déclenche via API Render. Les valeurs sont les mêmes que celles exposées par `ConfigService.get_render_config()` / `config/settings.py`.
- `RENDER_DEPLOY_CLEAR_CACHE` (optionnel) : `clear` ou `do_not_clear`. Valeur par défaut `do_not_clear`.

| Secret GitHub | Usage | Note |
| --- | --- | --- |
| `GHCR_USERNAME` | Identité `docker login` | défaut : `github.actor` |
| `GHCR_TOKEN` | Authentifie le push GHCR | PAT perso ou `GITHUB_TOKEN` avec droits packages |
| `RENDER_DEPLOY_HOOK_URL` | Déploiement Render prioritaire | doit commencer par `https://api.render.com/deploy/` |
| `RENDER_API_KEY` | Authentification API Render | requis pour fallback API |
| `RENDER_SERVICE_ID` | Service cible Render | correspond à l'ID affiché dans le dashboard Render |
| `RENDER_DEPLOY_CLEAR_CACHE` | Paramètre `clearCache` | `clear` ou `do_not_clear` |

### Variables Render

- Côté Render, ne changez pas la commande de démarrage : le Dockerfile exécute déjà `gunicorn ... app_render:app` et respecte les valeurs `GUNICORN_*`.
- Conservez les variables applicatives historiques (`ENABLE_BACKGROUND_TASKS`, `WEBHOOK_URL`, etc.). Elles sont injectées par Render lors du déploiement de l'image.
- Les logs (stdout/stderr) continuent à exposer `BG_POLLER`, `HEARTBEAT`, `MAKE_WATCHER`, etc., conformément à `docs/operational-guide.md`.
- **Nouveau** : configurez systématiquement les variables d'offload R2 côté Render (`R2_FETCH_ENABLED`, `R2_FETCH_ENDPOINT`, `R2_FETCH_TOKEN`, `R2_PUBLIC_BASE_URL`, `R2_BUCKET_NAME`, `WEBHOOK_LINKS_FILE`). Sans token ou endpoint, l'intégration R2 reste désactivée et les webhooks ne contiendront pas `r2_url`.
- Vérifiez que `WEBHOOK_LINKS_FILE` pointe vers un volume persistant si vous souhaitez analyser l'historique des paires R2 après un redéploiement.

### Flux de déploiement

1. Push sur `main` (ou tag `v*`/`release-*`).
2. GitHub Actions construit et pousse l'image sur `ghcr.io/<owner>/<repo>:latest` et `...:<sha>`.
3. Si `RENDER_DEPLOY_HOOK_URL` est défini, Render déploie la nouvelle image.
4. Sinon, l'action utilise `RENDER_API_KEY` + `RENDER_SERVICE_ID` + `imageUrl` (tag `sha`).
5. En cas d'échec, l'étape finale notifie et vous pouvez utiliser `POST /api/deploy_application` pour relancer (voir section ci-dessous pour l'ordre Hook/API/fallback local).

### Vérifications

- Voir `Render Dashboard → Events/Logs` pour confirmer que le déploiement provient de `api` ou `deploy_hook`.
- S'assurer que l'image tirée (affichée dans Render) correspond à `ghcr.io/...:<sha>` attendu.
- Côté application, vérifier les logs de démarrage (Gunicorn + `Process: SIGTERM` + `HEARTBEAT`) pour confirmer la montée de version.

## Déploiement Render via API interne (fallback manuel)

- Endpoint: `POST /api/deploy_application` (protégé)
- Ordre de tentative:
  1) Deploy Hook (`RENDER_DEPLOY_HOOK_URL` commençant par `https://api.render.com/deploy/`)
  2) Render API (`RENDER_API_KEY`, `RENDER_SERVICE_ID`, payload `{ clearCache: RENDER_DEPLOY_CLEAR_CACHE }`)
  3) Fallback local (`DEPLOY_CMD`, défaut: reload-or-restart + reload Nginx)
- Variables d'environnement: voir `docs/configuration.md`.
- Les logs masquent la clé du Deploy Hook et tracent l'utilisateur authentifié ayant déclenché l'action.

### Détails de l'API Render `/v1/services/{serviceId}/deploys`

- Méthode: `POST https://api.render.com/v1/services/{serviceId}/deploys`
- Paramètre de chemin:
  - `serviceId` (string, requis) : identifiant du service Render ciblé.
- Corps JSON typique:
  - `clearCache` (`clear` | `do_not_clear`) – contrôle le vidage du cache de build (défaut : `do_not_clear`).
  - `commitId` (string, optionnel) – SHA Git spécifique à déployer (sinon dernier commit de la branche configurée).
  - `imageUrl` (string, optionnel) – URL de l’image à déployer pour les services basés sur une image.
- Codes de réponse usuels (côté Render):
  - `201 Created` / `202 Queued` – déploiement accepté ou mis en file d’attente.
  - `400/401/404/409/429/500/503` – erreurs de validation, d’authentification ou de plateforme.

Pour la référence complète, voir la documentation Render officielle :
https://render.com/docs/api#tag/Deploys/operation/createDeploy
