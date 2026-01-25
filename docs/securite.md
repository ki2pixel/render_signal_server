# Sécurité

---

## 📅 Dernière mise à jour / Engagements Lot 2

**Date de refonte** : 2026-01-25 (protocol code-doc)

### Terminologie unifiée
- **`DASHBOARD_*`** : Variables d'environnement (anciennement `TRIGGER_PAGE_*`)
- **`MagicLinkService`** : Service singleton pour authentification sans mot de passe
- **`R2TransferService`** : Service singleton pour offload Cloudflare R2
- **"Absence Globale"** : Fonctionnalité de blocage configurable par jour de semaine

### Engagements Lot 2 (Résilience & Architecture)
- ✅ **Verrou distribué Redis** : Implémenté avec clé `render_signal:poller_lock`, TTL 5 min
- ✅ **Fallback R2 garanti** : Conservation URLs sources si Worker R2 indisponible
- ✅ **Watchdog IMAP** : Timeout 30s pour éviter processus zombies
- ✅ **Tests résilience** : `test_lock_redis.py`, `test_r2_resilience.py` avec marqueurs `@pytest.mark.redis`/`@pytest.mark.r2`
- ✅ **Store-as-Source-of-Truth** : Configuration dynamique depuis Redis/fichier, pas d'écriture runtime dans les globals

### Métriques de documentation
- **Volume** : 7 388 lignes de contenu réparties dans 25 fichiers actifs
- **Densité** : Justifie le découpage modulaire pour maintenir la lisibilité
- **Exclusions** : `archive/` et `audits/` maintenus séparément pour éviter le bruit

## Secrets et identifiants
- Ne jamais utiliser les valeurs de référence présentes dans le code (`REF_*`) en production.
- Fournir tous les secrets via variables d'environnement et gérer leur rotation.
- **Variables obligatoires** : 8 variables ENV requises avec enforcement au démarrage (`FLASK_SECRET_KEY`, `TRIGGER_PAGE_PASSWORD`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`, `PROCESS_API_TOKEN`, `WEBHOOK_URL`, `MAKECOM_API_KEY`).

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

### Variables d'environnement obligatoires (enforcement au démarrage)
- **Mécanisme** : `_get_required_env()` dans `config/settings.py` lève `ValueError` si une variable obligatoire est manquante
- **Liste complète** : `FLASK_SECRET_KEY`, `TRIGGER_PAGE_PASSWORD`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`, `PROCESS_API_TOKEN`, `WEBHOOK_URL`, `MAKECOM_API_KEY`
- **Message d'erreur** explicite au démarrage pour éviter les déploiements incomplets
- **Tests dédiés** : `tests/test_settings_required_env.py` avec scénarios Given/When/Then

### Anonymisation des journaux (Lot 1)
- Tous les points de log du poller IMAP et des webhooks passent par `utils.text_helpers.mask_sensitive_data()` :
  - `type="email"` tronque l'adresse (`s***@domaine`).
  - `type="subject"` conserve les trois premiers mots + hash court (`prefix... [abc123]`).
  - `type="content"` journalise uniquement la longueur.
- Le masquage est appliqué dans `email_processing/orchestrator.py` (lecture IMAP, allowlist, décisions) et `email_processing/webhook_sender.py` (logs Make.com/dashboard). Vérifiez que vos ajouts de logs sensibles utilisent la même fonction pour éviter toute fuite de PII.

### Écriture Atomique Configuration (Lot 1)
- **Services impactés** : `RuntimeFlagsService` et `WebhookConfigService` utilisent `RLock` + écriture atomique
- **Mécanisme** : Écriture via fichier temporaire + `os.replace()` pour garantir l'atomicité
- **Protection** : Prévention de la corruption des fichiers JSON lors écritures concurrentes
- **Fallback** : Fichier verrouillé avec `fcntl` pour éviter les conditions de course

### Validation Domaines R2 (Lot 1)
- **Service** : `R2TransferService` avec allowlist stricte des domaines sources
- **Protection** : Prévention SSRF (Server-Side Request Forgery) côté Python
- **Domaines autorisés** : `dropbox.com`, `fromsmash.com`, `swisstransfer.com`, `wetransfer.com`
- **Configuration** : `R2_ALLOWED_DOMAINS` (optionnel) pour surcharge personnalisée
- **Logging** : Rejets journalisés avec `WARNING` pour auditabilité
- **Fallback gracieux** : Conservation `raw_url` si R2 échoue, aucun blocage du flux principal

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
