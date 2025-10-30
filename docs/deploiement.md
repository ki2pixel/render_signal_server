# Déploiement

## Gunicorn + Reverse Proxy

1. Installer les dépendances
```
pip install -r requirements.txt
pip install gunicorn
```

2. Lancer via systemd (exemple)
```
[Unit]
Description=render-signal-server
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/render_signal_server
Environment="FLASK_SECRET_KEY=..."
Environment="TRIGGER_PAGE_USER=..."
Environment="TRIGGER_PAGE_PASSWORD=..."
# ... autres ENV (voir configuration.md)
ExecStart=/opt/render_signal_server/.venv/bin/gunicorn -w 2 -b 127.0.0.1:10000 app_render:app
Restart=always

[Install]
WantedBy=multi-user.target
```

3. Reverse proxy (Nginx – extrait)
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

## Vérifications post-déploiement
- Accès HTTPS au domaine et au login `/login`.
- `GET /api/ping` renvoie `200`.
- Les tâches de fond démarrent (logs `BACKGROUND_TASKS`).
- Les variables d'environnement sensibles sont présentes.

### Notes opérationnelles (poller IMAP singleton)

- Activer `ENABLE_BACKGROUND_TASKS=true` uniquement sur un seul worker/process.
- Vérifier les logs au démarrage: message indiquant « singleton lock acquis ».
- Si nécessaire, définir `BG_POLLER_LOCK_FILE` pour contrôler l'emplacement du verrou.

### Notes UI (fenêtre horaire des webhooks)

- Tester `GET /api/get_webhook_time_window` puis `POST /api/set_webhook_time_window` depuis l'UI `trigger_page.html`.
- Vérifier que les payloads webhook incluent `webhooks_time_start` / `webhooks_time_end` lorsque configurés.
