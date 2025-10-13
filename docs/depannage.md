# Dépannage (Troubleshooting)

## Problèmes courants

- Connexion IMAP échoue
  - Vérifier `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`, `IMAP_PORT`, `IMAP_USE_SSL`.
  - Pare-feu sortant et extensions SSL.

- `POST /api/check_emails_and_download` retourne 503
  - Variables d'environnement manquantes: email, `SENDER_OF_INTEREST_FOR_POLLING`, `WEBHOOK_URL`.

- Pas d'envoi webhook
  - `WEBHOOK_URL` non défini ou non joignable.
  - Erreurs réseau côté serveur cible.

### Erreurs SSL lors des appels webhook

- Symptômes
  - Logs `POLLER`: `SSLError: certificate verify failed: Hostname mismatch, certificate is not valid for '<host>'`.
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
- Déclenchement manuel: `POST /api/check_emails_and_download` (observables dans les logs).
- Simulation IMAP: placer un e-mail test avec expéditeur autorisé, sujet conforme, URL Dropbox.
- Simulation sans réseau: utilisez `debug/simulate_webhooks.py` pour générer et inspecter les payloads sans IMAP ni appels HTTP réels.
  - Commande: `DISABLE_BACKGROUND_TASKS=true python debug/simulate_webhooks.py`
  - Scénarios: Dropbox, non-Dropbox (FromSmash/SwissTransfer), Présence/Désabonnement (Make). Les POST sont mockés et imprimés.
