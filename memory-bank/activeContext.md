# Contexte Actif

## Tâche en cours
- Archive des emails « Missions Recadrage » : stockage hybride PHP + proxy public `email_proxy.php`.

## Décisions récentes
- Option B retenue : un fichier JSON par mission (`data/emails/recadrage_*.json`) + index léger plafonné (`data/emails_recadrage_index.json`).
- Corps, sujet et snippet bruts (contenu de la mission) ; seul `sender` est masqué ; ID Gmail hashé.
- Proxy public en lecture, avec `EMAIL_PROXY_TOKEN` optionnel.
- Détection d'urgence alignée sur `URGENT` et `URGENCE` (regex `/\b(urgent|urgence)\b/i`).

## Questions Ouvertes
- Rétention : conservation indéfinie des fichiers détail ; prévoir une purge si > 1 000 lots.
- Déploiement manuel des fichiers PHP (dossier `deployment/` ignoré par Git).

## Prochaine Étape
- Uploader `src/EmailStorageLogger.php`, `public_html/email_proxy.php` et `src/WebhookHandler.php` sur l'hôte.
- Vérifier le premier lot réel via `GET /email_proxy.php`.
