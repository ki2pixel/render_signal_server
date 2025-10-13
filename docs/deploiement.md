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
