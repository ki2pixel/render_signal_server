# Rapport d'Audit Backend — Render Signal Server

**Date :** 2026-07-17
**Cible :** Flask 3.1.2, Gunicorn, Redis, architecture services

---

## 🔴 CRITIQUE (3)

### 1. Fichier `.env` exposé avec secrets de production
**Fichier :** `.env` à la racine du projet
Tous les secrets en clair : `FLASK_SECRET_KEY`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `REDIS_URL` (mot de passe embarqué), `RENDER_API_KEY`, `RENDER_DEPLOY_HOOK_URL`, `GROQ_API_KEY`, `R2_FETCH_TOKEN`, `CONFIG_API_TOKEN`, `PROCESS_API_TOKEN`, `TEST_API_KEY`, `TRIGGER_PAGE_PASSWORD`.

→ **Rotation immédiate de tous les secrets**, surtout Gmail et Render.

### 2. Injection de commande via `RESTART_CMD` / `DEPLOY_CMD`
**Fichier :** `routes/api_admin.py:60-72, 307-319`
```python
subprocess.Popen(["/bin/bash", "-lc", f"sleep 1; {restart_cmd}"], ...)
subprocess.Popen(["/bin/bash", "-lc", f"sleep 1; {deploy_cmd}"], ...)
```
Les variables d'env sont passées à `/bin/bash -lc`. Si jamais contrôlables par un attaquant, RCE directe. Le endpoint est protégé par `@login_required`, mais le blast radius est maximal.

→ Remplacer par `subprocess.Popen(cmd.split())` sans shell, ou nettoyer les entrées.

### 3. Aucune protection anti brute-force sur `/login`
**Fichier :** `routes/dashboard.py`
Pas de rate limiting, pas de account lockout, pas de délai progressif. Le mot de passe est stocké en clair (variable d'env).

→ Ajouter `Flask-Limiter` ou un middleware de rate limiting. Hasher le mot de passe.

---

## 🟠 HAUTE (3)

### 4. Regex utilisateur stockée et exécutée (ReDoS/Injection)
**Fichier :** `services/routing_rules_service.py:287`
Un admin authentifié peut injecter une regex arbitraire qui sera compilée avec `re.compile()` et exécutée contre le contenu des emails. Une regex malveillante peut causer un ReDoS (blocage CPU).

→ Ajouter un timeout de compilation regex (`re.compile(..., timeout=1)`) ou limiter la complexité.

### 5. Transfert R2 synchrone bloque la réponse Gmail Push
**Fichier :** `services/ingress_service.py:133`
```python
r2_url, original_filename = r2_service.request_remote_fetch(
    source_url=normalized_source_url, provider=provider,
    email_id=email_id, timeout=remote_fetch_timeout  # jusqu'à 120s !
)
```
Gmail Push attend une réponse en ~5 secondes. Un transfert R2 de 120s bloque toute la requête et peut causer des timeouts Gmail + retries en cascade.

→ Rendre le transfert R2 asynchrone (fire-and-forget, Celery, ou thread pool).

### 6. CI désactivée — aucun test exécuté avant merge
**Fichier :** `.github/workflows/python-ci.yml.disabled`
Le suffixe `.disabled` empêche l'exécution. Aucun test, linting, ou type checking ne tourne en CI. Le code peut merger sur `main` sans validation.

→ Renommer en `python-ci.yml`, ajouter `black --check`, `ruff`, `mypy`, et `pytest --cov-fail-under=70`.

---

## 🟡 MOYENNE (7)

### 7. Rate limiter local au processus, pas global
**Fichier :** `services/rate_limit_service.py:21`
```python
self._webhook_send_times: deque[float] = deque()
```
Avec plusieurs workers Gunicorn, chaque worker a son propre compteur. Le rate limiting n'est **pas effectif globalement**.

→ Migrer vers un rate limiter Redis (`INCR` + `EXPIRE` ou sorted set).

### 8. Déduplication locale en fallback — risques de doublons
**Fichier :** `services/deduplication_service.py:90-91`
```python
self._processed_email_ids: Set[str] = set()
```
Quand Redis est indisponible, la déduplication tombe en mémoire locale par worker → doublons possibles entre workers.

### 9. `except Exception` généralisé — 182 occurrences
Top 3 fichiers :
- `email_processing/orchestrator.py` : 36 instances
- `services/ingress_service.py` : 19 instances  
- `services/magic_link_service.py` : 14 instances

Seulement 4% des clauses `except` utilisent un type d'exception spécifique. Plusieurs `except Exception: pass` silencieux sans log.

→ Remplacer par des types spécifiques. Ajouter `logger.warning(..., exc_info=True)` au minimum.

### 10. Aucun gestionnaire d'erreur Flask global
Zéro `@app.errorhandler` dans toute l'application. Les exceptions non gérées remontent aux pages d'erreur Flask par défaut, potentiellement avec stack traces.

→ Ajouter `@app.errorhandler(500)` et `@app.errorhandler(Exception)`.

### 11. Duplication de code majeure orchestrator ↔ ingress_service
`ingress_service.py` duplique ~40% de la logique de `orchestrator.py` :
- `_get_detector_and_time()` ≈ `_infer_detectors()`
- `_evaluate_time_window()` ≈ `_load_webhook_global_time_window()`
- `_maybe_enrich_delivery_links_with_r2()` ≈ `_handle_r2_enrichment()`

→ Extraire la logique partagée dans un module commun.

### 12. Pas de session timeout
Les sessions Flask sont permanentes par défaut (31 jours). Aucun timeout d'inactivité configuré.

→ `app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)`.

### 13. Pas de `docker-compose.yml`
Le développement local nécessite Redis configuré manuellement. Pas d'orchestration pour Redis + app.

---

## 🟢 BASSE (6)

### 14. Username par défaut `"admin"` — devinable
`config/settings.py:9`

### 15. 4 connexions Redis indépendantes, pas de pool partagé
`app_render.py`, `background/lock.py`, `config/app_config_store.py`, `services/magic_link_service.py` créent chacun leur propre client Redis.

→ Injecter un client Redis unique via l'app factory.

### 16. `handle_presence_route()` — fonction stub qui retourne toujours `False`
`email_processing/orchestrator.py:956` — 17 paramètres pour rien.

### 17. `background/polling_thread.py` et `background/lock.py` — code mort (0% coverage)
### 18. `GUNICORN_CMD_ARGS` dans `.env` ignoré par le Dockerfile
### 19. `COPY . .` dans le Dockerfile embarqué tests, docs, htmlcov en production

---

## 📊 MÉTRIQUES

| Métrique | Valeur |
|----------|--------|
| Couverture de tests | ~70% (objectif 100% non atteint) |
| `except Exception` | 182 occurrences / ~195 total |
| Fichiers avec 0% coverage | 2 (`background/lock.py`, `background/polling_thread.py`) |
| Services sous 50% coverage | `deduplication_service.py` (39.6%), `auth_service.py` (28.6%), `config_service.py` (50%) |
| Complexité max | `orchestrator.py:check_new_emails_and_trigger_webhook()` (~180 lignes, 6+ niveaux d'imbrication) |
| Routes publiques non protégées | `/health`, `/api/ping`, `/login`, `/login/magic/<token>` |
| Secrets en clair | 13 variables dans `.env` |
| Workers Gunicorn | 1 (single point of failure) |

---

## ✅ POINTS POSITIFS

- `hmac.compare_digest()` pour toutes les comparaisons de tokens/mots de passe → timing-attack safe
- CSRFProtect activé globalement avec exemptions ciblées appropriées
- Jinja2 auto-escape protège contre XSS — aucun `| safe` sur données utilisateur
- `@login_required` sur toutes les routes dashboard/admin sensibles
- Protection open redirect sur le paramètre `next` du login
- Magic links : HMAC-SHA256 signés, TTL configurable, single-use, atomiques
- Utilisateur non-root dans le container Docker
- Architecture services bien structurée (12 services, pattern singleton cohérent)
- Tests bien organisés (39 fichiers, fixtures partagées, markers pytest)
- Fallback Redis → fichier → mémoire bien conçu

---

## 🎯 RECOMMANDATIONS PRIORISÉES

1. **Rotation immédiate** de tous les secrets exposés dans `.env`
2. **Réactiver la CI** (`python-ci.yml.disabled` → `python-ci.yml`) avec lint + tests + coverage gate
3. **Remplacer `subprocess.Popen` avec shell** par un appel sans shell dans `api_admin.py`
4. **Rendre le transfert R2 asynchrone** — ne pas bloquer la réponse Gmail Push
5. **Ajouter rate limiting sur `/login`** et les autres endpoints publics
6. **Migrer le rate limiter vers Redis** pour la cohérence multi-workers
7. **Ajouter `@app.errorhandler(Exception)`** global
8. **Réduire les `except Exception`** → types spécifiques + logging
9. **Extraire la logique dupliquée** entre `orchestrator.py` et `ingress_service.py`
10. **Ajouter `docker-compose.yml`** avec Redis pour le dev local