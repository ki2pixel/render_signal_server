# Audit Backend Complet — `render_signal_server`

Application Flask d'ingestion d'emails Gmail (IMAP polling + Gmail Push), routage par règles, envoi de webhooks, offload Cloudflare R2, et dashboard d'administration.

---

## 1. Authentification & Sessions

### Vulnérabilités

**[Élevée] Absence de rate limiting sur le login dashboard**
`routes/dashboard.py:5832-5847` — Le formulaire `POST /login` accepte username/password sans aucune limitation de tentatives. `ConfigService.verify_dashboard_credentials` (`services/config_service.py:6599-6615`) utilise `hmac.compare_digest` (correct pour le timing) mais aucune protection contre le brute-force n'est en place.
**Recommandation :** Ajouter un rate-limit par IP + par username (ex. `flask-limiter`, 5 tentatives / 5 min).

**[Moyenne] Configuration session non visible**
Aucune configuration explicite de `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE` dans le code lu. Si l'app tourne derrière HTTPS (Render), les cookies de session Flask-Login ne sont pas forcés en `Secure`.
**Recommandation :** Forcer `app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')`.

**[Faible] Magic link — dérive HMAC sans rotation de clé**
`services/magic_link_service.py:7882-7884` — La signature HMAC dérive de `FLASK_SECRET_KEY`. Si cette clé fuit, tous les tokens peuvent être forgés. Pas de rotation de clé prévue.
**Recommandation :** Permettre la rotation via un versioning (`secret_v1`, `secret_v2`).

### Points positifs
- Magic links : tokens signés HMAC-SHA256, TTL configurable, usage unique, nettoyage automatique (`_cleanup_expired_tokens`), vérification à la consommation (`_process_token_consumption:7820-7846`).
- Protection open-redirect dans `_complete_login` (`routes/dashboard.py:5807-5812`) — vérifie le netloc.
- `compare_digest` utilisé partout pour les comparaisons de secrets.

---

## 2. Validation des entrées & Injection

**[Critique] ReDoS via regex utilisateur dans les règles de routage**
`email_processing/orchestrator.py:2282-2284` — L'opérateur `regex` des routing rules exécute `re.search(value, target)` avec un pattern fouri par l'utilisateur (admin). Aucune limite de complexité ni timeout. Un pattern malveillant ou mal écrit (ex. `(a+)+$`) peut causer un déni de service.
**Recommandation :** Utiliser `re.search` avec un timeout Python 3.11+ (`re.compile(pattern).search(target, timeout=1.0)`) ou valider la complexité du pattern. Alternative : restreindre à des patterns simples.

**[Élevée] Injection de commandes via `subprocess.Popen` avec `shell=True`**
`routes/api_admin.py:4163-4168` (`restart_server`) et `routes/api_admin.py:4409-4414` (`_deploy_via_fallback`) — `subprocess.Popen(["/bin/bash", "-lc", f"sleep 1; {restart_cmd}"], ...)` avec `restart_cmd` issu de `os.environ.get("RESTART_CMD")`. Bien que l'env soit contrôlé, si un attaquant peut modifier l'env (ex. via une autre vuln), il obtient RCE.
**Recommandation :** Éviter `shell=True`. Passer une liste d'arguments. Valider le format de la commande.

**[Moyenne] SSRF via URL webhook configurable**
`routes/api_webhooks.py:5647-5651` — L'admin peut configurer n'importe quelle URL HTTPS comme `webhook_url`. `send_custom_webhook_flow` (`orchestrator.py:3337`) fait `requests.post(webhook_url, ...)` sans restriction de destination. Un admin compromis ou un bug pourrait cibler des endpoints internes (169.254.169.254, localhost).
**Recommandation :** Valider que l'URL ne pointe pas vers des ranges privés/localhost (blocage SSRF) au moment de la sauvegarde.

**[Moyenne] Absence de vérification de signature sur l'ingress Gmail**
`routes/api_ingress.py:4688-4703` — L'endpoint `/api/ingress/gmail` vérifie seulement un Bearer token (`verify_api_key_from_request`). Aucune vérification de signature HMAC ni de l'origine (IP Google Apps Script). Le token est statique et partagé.
**Recommandation :** Ajouter une vérification de signature HMAC du payload ou restreindre par IP/source.

**[Faible] Validation URL webhook trop permissive**
`services/webhook_config_service.py:10260-10278` — `validate_webhook_url` vérifie seulement `startswith("https://")` et `len >= 10` et `"." in url`. Des URLs comme `https://x` passent.
**Recommandation :** Utiliser `urllib.parse.urlparse` et valider scheme + netloc + TLD.

---

## 3. Gestion des secrets & configuration

**[Moyenne] URL webhook loggée en debug**
`email_processing/orchestrator.py:3509-3513` — Le debug log inclut l'URL webhook complète (`webhook_url` non masqué).
**Recommandation :** Masquer l'URL dans les logs debug aussi.

### Points positifs
- `mask_sensitive_data` utilisé systématiquement pour PII dans les logs (`orchestrator.py:2326-2327`, `ingress_service.py:7399-7404`).
- Deploy hook URL masquée dans les logs (`routes/api_admin.py:4347-4349`).
- Secrets via env vars, pas de hardcoding visible.
- Tokens API comparés avec `hmac.compare_digest`.

---

## 4. Données & PII

**[Moyenne] Contenu email complet envoyé au webhook externe**
`orchestrator.py:2827-2835` et `ingress_service.py:7510-7514` — Le payload webhook inclut `email_content` (corps complet plain+HTML) et `bodyPreview`. Ces données transitent vers un endpoint externe (Make.com / PHP).
**Recommandation :** Évaluer la nécessité d'envoyer le contenu complet. Considérer un hachage ou une troncation. Documenter le flux PII pour conformité RGPD.

**[Faible] Sujets d'emails dans les logs webhook**
`orchestrator.py:3293` — `subject[:100]` stocké dans les logs webhook (fichier JSON + Redis). Rétention non configurée explicitement.
**Recommandation :** Définir une politique de rétention explicite pour `webhook_logs.json`.

---

## 5. Réseau & Infrastructure

**[Élevée] Absence de headers de sécurité**
Aucun header CSP, HSTS, X-Frame-Options, X-Content-Type-Options visible dans le code. Le dashboard est rendu via `render_template` sans after_request handler ajoutant ces headers.
**Recommandation :** Ajouter `flask-talisman` ou un `after_request` :
```python
@app.after_request
def set_security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    resp.headers['Content-Security-Policy'] = "default-src 'self'"
    return resp
```

**[Élevée] Absence de protection CSRF**
Les routes `POST` (`/api/restart_server`, `/api/migrate_configs_to_redis`, `/api/webhooks/config`, etc.) sont protégées par `@login_required` mais sans token CSRF. Un attaquant peut forger une requête cross-site si l'utilisateur est authentifié.
**Recommandation :** Activer `flask-wtf` CSRFProtect ou `flask-seasurf`.

**[Moyenne] Rate limiting absent sur les endpoints API**
Seul le rate limiting d'envoi webhook existe (`RateLimitService`). Les endpoints `/api/ingress/gmail`, `/api/test/*`, `/api/auth/magic-link` n'ont aucun rate limiting.
**Recommandation :** Ajouter `flask-limiter` sur les endpoints sensibles.

---

## 6. Logique métier & fiabilité

**[Critique] Déduplication Redis : set sans TTL → croissance illimitée**
`services/deduplication_service.py:6819` — `self._redis.sadd(key, email_id)` ajoute au set `r:ss:processed_email_ids:v1` sans TTL. Le set grandit indéfiniment.
**Recommandation :** Utiliser des clés individuelles avec TTL (ex. `SETEX r:ss:email:{id} 2592000 1`) ou un ZSET avec score = timestamp et nettoyage périodique.

**[Élevée] Fail-open sur le lock inflight**
`services/deduplication_service.py:6847-6850` — `acquire_email_inflight_lock` retourne `True` si Redis échoue. Deux requêtes concurrentes peuvent traiter le même email.
**Recommandation :** En cas d'erreur Redis, logger et rejeter (fail-closed) ou utiliser le fallback mémoire avec un lock threading local.

**[Élevée] `release_email_inflight_lock` sans vérification de propriété**
`services/deduplication_service.py:6862-6863` — `self._redis.delete(lock_key)` supprime la clé sans vérifier qui la possède. Un processus B peut supprimer le lock d'un processus A encore en cours.
**Recommandation :** Stocker un token unique à l'acquisition et ne supprimer qu'avec un Lua script vérifiant le token.

**[Moyenne] Race condition check-then-act sur la déduplication**
`orchestrator.py:2936-2937` et `ingress_service.py:7568-7569` — `is_email_processed` puis `mark_email_processed` ne sont pas atomiques. Le lock inflight mitigé mais fail-open.
**Recommandation :** Rendre atomique via `SET NX` (déjà partiellement fait pour inflight) mais corriger le fail-open.

**[Moyenne] `except Exception: pass` silencieux omniprésents**
Exemples : `orchestrator.py:2998-3002`, `ingress_service.py:7350-7351`, `magic_link_service.py:7764-7765`, etc. Des erreurs sont avalées sans log.
**Recommandation :** Au minimum logger l'erreur au niveau debug. Supprimer les `pass` nus.

**[Faible] Dead code — `handle_presence_route`**
`orchestrator.py:3040-3057` — Fonction qui retourne toujours `False`. Commentaire "presence feature removed".
**Recommandation :** Supprimer la fonction et ses appelants.

---

## 7. Qualité du code & maintainabilité

- **Singletons excessifs** : 9 services en singleton. Rend le test et le raisonnement sur l'état global difficile.
- **Couverture de tests faible** : 41-66% sur les services critiques (DeduplicationService 41%, AuthService 49%). Les chemins d'erreur et edge cases ne sont pas couverts.
- **Docstrings exhaustifs** : bon point pour l'onboarding.
- **Architecture en couches** (routes → services → utils) : propre et lisible.
- **`__import__('requests')` et `__import__('time')`** (`orchestrator.py:2721-2722`) : anti-pattern. Importer normalement en haut du fichier.
- **`globals().get('pattern_matching')`** (`orchestrator.py:2774`) : import dynamique fragile. Préférer un import explicite.

---

## 8. Tests & coverage

- Tests frontend Vitest présents (`autosave.test.js`, `status_banner.test.js`).
- Tests backend mentionnés (25/25 sur `test_services.py`) mais couverture faible sur les chemins critiques (auth, ingress, dedup en erreur).
- **Manquent :** tests de sécurité (ReDoS, SSRF, brute-force), tests d'idempotence de l'ingress sous concurrence, tests de fail-open du lock Redis.

---

## Synthèse des priorités

| Sévérité | Finding | Localisation |
|----------|---------|--------------|
| Critique | ReDoS regex utilisateur | `orchestrator.py:2282` |
| Critique | Set Redis dédup sans TTL | `deduplication_service.py:6819` |
| Élevée | Pas de rate limiting login | `dashboard.py:5832` |
| Élevée | `subprocess` shell=True | `api_admin.py:4163, 4409` |
| Élevée | Pas de headers de sécurité | global |
| Élevée | Pas de CSRF | global |
| Élevée | Lock inflight fail-open | `deduplication_service.py:6847` |
| Élevée | Lock release sans vérif propriété | `deduplication_service.py:6862` |
| Moyenne | SSRF via webhook URL | `api_webhooks.py:5647` |
| Moyenne | Ingress sans signature | `api_ingress.py:4688` |
| Moyenne | PII email envoyée au webhook | `orchestrator.py:2827` |
| Moyenne | Rate limiting API absent | global |
| Faible | Validation URL trop permissive | `webhook_config_service.py:10260` |
| Faible | Dead code `handle_presence_route` | `orchestrator.py:3040` |