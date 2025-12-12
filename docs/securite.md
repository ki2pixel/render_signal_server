# Sécurité

## Secrets et identifiants
- Ne jamais utiliser les valeurs de référence présentes dans le code (`REF_*`) en production.
- Fournir tous les secrets via variables d'environnement et gérer leur rotation.
- `FLASK_SECRET_KEY` obligatoire et robuste (sessions/auth).

## Authentification UI
- `Flask-Login` protège `/` et les routes sensibles.
- Utiliser HTTPS en production, cookies `Secure`, `HttpOnly`, `SameSite` (via config Flask/Reverse proxy).

## Webhooks
- Les appels sortants désactivent la vérification SSL dans le code (pour compatibilité). En production, activez la validation SSL avec des certificats valides.
- Si vous exposez des endpoints webhook entrants (non prévu ici), sécurisez par tokens/HMAC/IP allowlist.

## Surface d'attaque
- Ralentir/limiter les tentatives de login (rate limiting / fail2ban au niveau proxy).
- Journaliser les accès et échecs d'authentification.

## Données utilisateur
- Sanitize systématique des entrées si vous ajoutez de nouvelles routes.
- Ne logguez pas les mots de passe ; masquez les secrets dans les logs.

## Redis
- Utiliser `REDIS_URL` avec mot de passe et TLS si possible.
- Éviter l'exposition publique de Redis.
