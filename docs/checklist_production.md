# Check-list de mise en production

## Secrets et configuration
- FLASK_SECRET_KEY défini (valeur forte, non commitée)
- TRIGGER_PAGE_USER / TRIGGER_PAGE_PASSWORD définis (mots de passe forts)
- Variables IMAP (EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER, IMAP_PORT, IMAP_USE_SSL) configurées
- WEBHOOK_URL (et, si utilisés, `RECADRAGE_MAKE_WEBHOOK_URL` / `AUTOREPONDEUR_MAKE_WEBHOOK_URL` pour les flux Make.com) configurés et joignables en HTTPS
- PROCESS_API_TOKEN / MAKECOM_API_KEY (si requis) définis via variables d’environnement
- SENDER_OF_INTEREST_FOR_POLLING définie (liste d’expéditeurs autorisés)
- RENDER_DISC_PATH défini si emplacement personnalisé
- Flags runtime vérifiés (`DISABLE_EMAIL_ID_DEDUP=false`, `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS=false` par défaut) et `debug/runtime_flags.json` accessible en écriture

## Réseau et sécurité
- Accès HTTPS activé (certificats valides)
- Reverse proxy configuré (timeouts, headers X-Forwarded-*)
- Cookies de session sécurisés (Secure, HttpOnly, SameSite)
- Limitation des tentatives de login (niveau proxy: rate limiting / fail2ban)
- Pare-feu limite l’accès au port interne de Gunicorn
- TLS côté client activé pour webhooks sortants (éviter disable verify)

## Déploiement applicatif
- Exécution via Gunicorn (workers adéquats) derrière Nginx/Apache
- Service systemd (restart=always, user/groupe dédiés, WorkingDirectory correct)
- Permissions sudo pour redémarrage serveur via UI : règle sudoers `<utilisateur_service> ALL=NOPASSWD: /bin/systemctl restart render-signal-server` (adapter utilisateur service)
- Logs applicatifs redirigés vers journald/rotation mise en place
- `pip freeze` conforme à `requirements.txt` (environnement virtuel isolé)

### Tâches de fond (poller IMAP)
- `ENABLE_BACKGROUND_TASKS=true` activé sur un seul worker/process (les autres à `false`).
- `BG_POLLER_LOCK_FILE` défini si besoin (sinon défaut `/tmp/render_signal_server_email_poller.lock`).
- Logs au démarrage confirment « singleton lock acquis ».

## Observabilité et logs
- `FLASK_LOG_LEVEL` approprié (INFO/WARNING en prod)
- Journaux: AUTH, BG_POLLER, IMAP_DEBUG visibles et surveillés
- Alerting basique (échec récurrent IMAP/webhooks)

## Données et persistance
- Redis accessible et sécurisé (si utilisé): REDIS_URL avec auth/TLS
- Politique de rétention des fichiers éphémères dans `RENDER_DISC_PATH`

## Tests post-déploiement
- `GET /api/ping` renvoie 200 et un `timestamp_utc`
- Connexion/déconnexion via `/login` fonctionne
- Accès à `/` (UI télécommande) protégé
- `POST /api/check_emails_and_download` renvoie 202 avec config complète
- Polling en tâche de fond démarre (logs BACKGROUND_TASKS / BG_POLLER)
- Simulation d’un e-mail conforme → webhook envoyé (vérifier côté récepteur)

### UI Webhooks – Fenêtre horaire
- (Recommandé: utiliser `GET/POST /api/webhooks/time-window`; les endpoints listés ci-dessous restent pris en charge pour compatibilité.)
- `GET /api/get_webhook_time_window` renvoie la configuration attendue (timezone incluse).
- `POST /api/set_webhook_time_window` accepte les formats `HHhMM`/`HH:MM`; vide+vide désactive.
- Les payloads webhook incluent `webhooks_time_start` / `webhooks_time_end` si configurés.

## Documentation et runbook
- Docs mises à jour: `docs/`
- Procédures d’urgence: rotation des secrets, redémarrage service, diagnostic IMAP/Redis
- Contacts/ownership définis
