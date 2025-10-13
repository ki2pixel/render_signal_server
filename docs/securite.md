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

## Risques & limites de la résolution headless

La résolution headless (Playwright) peut aider à capturer des liens de téléchargement réellement utilisés par certaines plateformes (SPA, XHR). Elle présente toutefois des limites et risques à considérer :

- Anti‑bot / 403 : certains fournisseurs (ex. SwissTransfer) détectent les navigateurs headless et renvoient `403`. Basculer en `HEADLESS_MODE=false` pour diagnostiquer et gérer les consentements.
- Consentements / Cookies : des popups RGPD ou modales de consentement peuvent bloquer le téléchargement. Les sélecteurs sont gérés au mieux, mais peuvent changer côté fournisseur.
- Jetons / Session / Expiration : des liens signés peuvent expirer rapidement ou être liés à une session. La résolution n'est pas garantie.
- Budget temps / Ressources : configurez `HEADLESS_TOTAL_TIMEOUT_MS` et les tentatives. Les interactions headless consomment CPU/RAM.
- Conformité & ToS : respectez les conditions d'utilisation des plateformes. N'automatisez pas des interactions interdites.
- Journalisation : activez `HEADLESS_TRACE=true` pour diagnostiquer, en notant que seules les URLs (pas les contenus) sont tracées. Ne logguez jamais de secrets.
- Maintenance : les sélecteurs/heuristiques peuvent casser si l'UI des plateformes évolue. Prévoir une veille et des mises à jour.
