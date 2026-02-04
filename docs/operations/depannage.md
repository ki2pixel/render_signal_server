# Dépannage (Troubleshooting)

## Problèmes courants

- Gmail Push Ingress échoue
  - Vérifier `PROCESS_API_TOKEN` dans les variables d'environnement Render.
  - Confirmer que le Google Apps Script est correctement configuré.
  - Vérifier les logs pour `INGRESS: 401 Unauthorized` ou `INGRESS: 400 Invalid JSON payload`.

- `POST /api/ingress/gmail` retourne 401
  - Token `PROCESS_API_TOKEN` manquant ou incorrect.
  - Vérifier l'en-tête `Authorization: Bearer <token>`.

- `POST /api/ingress/gmail` retourne 400
  - Payload JSON invalide ou champs obligatoires manquants (`sender`, `body`).
  - Corriger le format du payload Apps Script.

- Pas d'envoi webhook
  - `WEBHOOK_URL` non défini ou non joignable.
  - Erreurs réseau côté serveur cible.
- Les modifications UI (fenêtre horaire, absence, runtime flags) ne prennent pas effet
  - Vérifier les logs `SVC: RuntimeFlagsService` / `SVC: WebhookConfigService` pour détecter une erreur d'écriture (doivent signaler l'utilisation d'un `RLock` + fichier `.tmp`).
  - Confirmer que `debug/runtime_flags.json` et `debug/webhook_config.json` sont accessibles en écriture (permissions) avant de relancer la requête API.
  - Si `EXTERNAL_CONFIG_BASE_URL`/`CONFIG_API_TOKEN` sont configurés, inspecter l'API PHP `config_api.php` (hébergement, droits disque) : le store externe est prioritaire, le fallback fichier n'est utilisé qu'en cas d'échec.
  - Ne pas éditer manuellement les fichiers JSON pendant que l'app tourne : utilisez toujours les services (`/api/config/*`, `/api/webhooks/*`) qui gèrent l'atomicité et invalident le cache.

### Erreurs SSL lors des appels webhook

- Symptômes
  - Logs `WEBHOOK_SENDER`: `SSLError: certificate verify failed: Hostname mismatch, certificate is not valid for '<host>'`.
  - `curl -I https://<host>/...` échoue avec `subjectAltName does not match <host>`.

- Diagnostic rapide
  - Vérifier le certificat présenté par le serveur et ses SAN (Subject Alternative Names):
    - `openssl s_client -connect <host>:443 -servername <host> -showcerts </dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName`
  - Tester la connexion HTTPS:
    - `curl -svI https://<host>/index.php --max-time 10`

- Causes probables
  - Le certificat ne couvre pas le FQDN utilisé dans `WEBHOOK_URL` (ex: CN/SAN = `kidpixel.fr` et `www.kidpixel.fr`, mais `WEBHOOK_URL` = `webhook.kidpixel.fr`).
  - Mauvaise config de vhost/SNI côté reverse proxy.

- Résolutions recommandées (sécurité by default)
  - Émettre un certificat qui inclut explicitement le hostname exact (SAN) utilisé par `WEBHOOK_URL`.
  - OU modifier `WEBHOOK_URL` pour cibler un hostname couvert par le certificat existant, si fonctionnellement équivalent.
  - Vérifier la configuration SNI/vhost pour servir le bon certificat selon le `servername` (SNI).

- Mesure temporaire (débogage uniquement)
  - Vous pouvez définir `WEBHOOK_SSL_VERIFY=false` pour bypass la vérification TLS pendant une phase de diagnostic. Non recommandé en production. Le code logge un avertissement clair si désactivé.

- Bonnes pratiques
  - Conserver `WEBHOOK_SSL_VERIFY=true` en production.
  - Surveiller l'expiration (`notAfter`) et renouveler avant échéance.
  - Tester après déploiement: `curl -svI https://<host>/index.php`.

- Interface affiche « Authentification requise »
  - Session expirée: reconnectez-vous sur `/login`.

- Télécommande ne met pas à jour le statut
  - Les endpoints worker local `/api/get_local_status` et `/api/trigger_local_workflow` ne sont pas fournis par ce backend.
  - Démarrer/configurer le worker local et autoriser CORS si origine différente.

## Tests recommandés
- Appel `GET /api/ping` doit répondre `200`.
- Connexion/déconnexion via `/login` et `/logout`.
- Test Gmail Push: `POST /api/ingress/gmail` avec payload de test (observables dans les logs).
- Simulation Gmail Push: utilisez `curl` pour tester l'endpoint sans Apps Script.
  ```bash
  curl -X POST https://votre-instance.onrender.com/api/ingress/gmail \
    -H "Authorization: Bearer PROCESS_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"sender":"test@example.com","body":"test","subject":"test"}'
  ```
- Simulation sans réseau: utilisez `debug/simulate_webhooks.py` pour générer et inspecter les payloads sans appels HTTP réels.
  - Commande: `python debug/simulate_webhooks.py`
  - Scénarios: Dropbox, non-Dropbox (FromSmash/SwissTransfer), e-mails Media Solution / Désabonnement (DESABO) et autres types personnalisés. Les POST sont mockés et imprimés.
