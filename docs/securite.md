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

### Anonymisation des journaux (Lot 1)
- Tous les points de log du poller IMAP et des webhooks passent par `utils.text_helpers.mask_sensitive_data()` :
  - `type="email"` tronque l'adresse (`s***@domaine`).
  - `type="subject"` conserve les trois premiers mots + hash court (`prefix... [abc123]`).
  - `type="content"` journalise uniquement la longueur.
- Le masquage est appliqué dans `email_processing/orchestrator.py` (lecture IMAP, allowlist, décisions) et `email_processing/webhook_sender.py` (logs Make.com/dashboard). Vérifiez que vos ajouts de logs sensibles utilisent la même fonction pour éviter toute fuite de PII.

## Magic Links

### Génération sécurisée
- Les tokens sont signés avec HMAC-SHA256 en utilisant `FLASK_SECRET_KEY`
- Chaque token contient un identifiant unique, une date d'expiration et une signature
- Les tokens sont générés de manière aléatoire avec `secrets.token_urlsafe()`

### Validation robuste
- Vérification de la signature à chaque utilisation
- Vérification de la date d'expiration (sauf pour les liens permanents)
- Protection contre les attaques par timing avec `hmac.compare_digest()`

### Gestion du cycle de vie
- Les liens à usage unique sont immédiatement invalidés après utilisation
- Les liens expirés sont automatiquement nettoyés du stockage
- Les liens permanents doivent être révoqués manuellement si compromis

### Bonnes pratiques
1. **Durée de vie limitée** :
   - Les liens standards expirent après 15 minutes (configurable via `MAGIC_LINK_TTL_SECONDS`)
   - Privilégier les liens à usage unique pour un accès temporaire

2. **Stockage sécurisé** :
   - Les tokens sont stockés dans un fichier JSON protégé (`magic_link_tokens.json`)
   - Accès exclusif avec verrouillage pour éviter les conditions de course

3. **Journalisation** :
   - Toutes les tentatives d'utilisation de magic links sont journalisées
   - Les échecs de validation sont enregistrés avec le motif d'échec

4. **Configuration recommandée** :
   ```env
   # Durée de vie des liens en secondes (900 = 15 minutes)
   MAGIC_LINK_TTL_SECONDS=900
   
   # Fichier de stockage des tokens
   MAGIC_LINK_TOKENS_FILE=./magic_link_tokens.json
   ```

5. **Réponse aux incidents** :
   - En cas de fuite d'un lien, le révoquer immédiatement
   - Pour les liens permanents, régénérer `FLASK_SECRET_KEY` pour invalider tous les tokens existants

## Redis
- Utiliser `REDIS_URL` avec mot de passe et TLS si possible.
- Éviter l'exposition publique de Redis.

## Cloudflare R2 (Offload fichiers)

### Configuration sécurisée
- Les clés Cloudflare R2 ne doivent jamais être commitées dans le code
- Utiliser uniquement les variables d'environnement Render pour les secrets
- `R2_FETCH_ENDPOINT` doit pointer vers un Worker Cloudflare sécurisé
- `R2_PUBLIC_BASE_URL` doit être un domaine HTTPS validé

### Validation des URLs sources
- Le Worker et la couche Python valident les domaines sources autorisés pour éviter les abus :
  - `dropbox.com`, `fromsmash.com`, `swisstransfer.com`, `wetransfer.com`
- Seules les URLs provenant de ces domaines sont acceptées (anti-SSRF côté service R2 + allowlist côté Worker)
- Logs détaillés en cas de rejet de domaine non autorisé

### Sécurité du Worker Cloudflare
- Rate limiting configuré via `wrangler.toml` pour éviter les abus
- Validation stricte des payloads JSON entrants
- Timeout de 120 secondes maximum pour les transferts
- Logs sécurisés (pas de secrets exposés côté client)

### Gestion des erreurs et fallback
- En cas d'échec R2, le système revient aux URLs sources originales
- Aucun blocage du flux principal si R2 est indisponible
- Logs détaillés pour le debugging sans exposition de secrets

### Bonnes pratiques R2
1. **Rotation des secrets** : Régénérer périodiquement les clés Cloudflare R2
2. **Monitoring** : Surveiller les logs Worker pour détecter les abus potentiels  
3. **Domaines autorisés** : Maintenir la liste des domaines sources à jour
4. **Rate limiting** : Ajuster le rate limiting selon le volume d'usage

Variables d'environnement sensibles :
```env
# NE PAS COMMITER - seulement dans Render
R2_ACCESS_KEY_ID=votre_access_key_cloudflare
R2_SECRET_ACCESS_KEY=votre_secret_key_cloudflare  
R2_ACCOUNT_ID=votre_account_id_cloudflare
```
