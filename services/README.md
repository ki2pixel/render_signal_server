# Services - Architecture Orientée Services

**Date de création:** 2025-11-17  
**Version:** 1.0  
**Status:** ✅ Production Ready

---

## 📋 Vue d'Ensemble

Le dossier `services/` contient 12 services qui encapsulent la logique métier de l'application. Ces services fournissent des interfaces cohérentes et testables pour accéder aux fonctionnalités clés.

### Philosophie

- **Separation of Concerns** - Un service = Une responsabilité
- **Dependency Injection** - Services configurables via injection
- **Testabilité** - Mocks faciles, tests isolés
- **Robustesse** - Gestion d'erreurs, fallbacks automatiques
- **Performance** - Cache intelligent, Singletons

---

## 🗂️ Structure

```
services/
├── __init__.py                    # Module principal - exports
├── config_service.py              # Configuration centralisée
├── auth_service.py                # Authentification unifiée
├── ingress_service.py             # Ingestion Gmail Push (Singleton)
├── runtime_flags_service.py       # Flags runtime avec cache (Singleton)
├── webhook_config_service.py      # Webhooks + validation (Singleton)
├── routing_rules_service.py       # Règles de routage dynamiques (Singleton)
├── deduplication_service.py       # Déduplication emails/subject groups (Singleton)
├── magic_link_service.py          # Magic links authentification (Singleton)
├── r2_transfer_service.py         # Offload Cloudflare R2 (Singleton)
├── rate_limit_service.py          # Limitation du débit webhook (Singleton)
├── runtime_metrics_service.py     # Métriques runtime (Singleton)
├── webhook_logger_service.py      # Journal des webhooks (Singleton)
└── README.md                      # Ce fichier
```

---

## 📦 Services Disponibles

### 1. ConfigService

**Fichier:** `config_service.py`  
**Pattern:** Standard (instance par appel)  
**Responsabilité:** Accès centralisé à toute la configuration applicative

**Fonctionnalités:**
- Configuration Email/IMAP
- Configuration Webhooks
- Tokens API
- Configuration Render (déploiement)
- Authentification Dashboard
- Clés Redis Déduplication

**Usage:**
```python
from services import ConfigService

config = ConfigService()

# Email config
if config.is_email_config_valid():
    email_cfg = config.get_email_config()
    print(f"Email: {email_cfg['address']}")

# Webhook config
if config.has_webhook_url():
    url = config.get_webhook_url()

# API token
if config.verify_api_token(token):
    # Token valide
    pass
```

---

### 2. RuntimeFlagsService

**Fichier:** `runtime_flags_service.py`  
**Pattern:** Singleton  
**Responsabilité:** Gestion flags runtime avec cache intelligent

**Fonctionnalités:**
- Cache mémoire avec TTL (60s par défaut)
- Persistence JSON automatique
- Invalidation cache intelligente
- Lecture/écriture atomique

**Usage:**
```python
from services import RuntimeFlagsService
from pathlib import Path

# Initialisation (une fois au démarrage)
service = RuntimeFlagsService.get_instance(
    file_path=Path("debug/runtime_flags.json"),
    defaults={
        "disable_dedup": False,
        "enable_feature": True,
    }
)

# Utilisation
if service.get_flag("disable_dedup"):
    # Bypass dedup
    pass

# Modifier un flag (persiste immédiatement)
service.set_flag("disable_dedup", True)

# Mise à jour multiple atomique
service.update_flags({
    "disable_dedup": False,
    "enable_feature": True,
})
```

---

### 3. WebhookConfigService

**Fichier:** `webhook_config_service.py`  
**Pattern:** Singleton  
**Responsabilité:** Configuration webhooks avec validation stricte

**Fonctionnalités:**
- Validation stricte URLs (HTTPS requis)
- Normalisation URLs Make.com
- Configuration Absence Globale
- SSL verify toggle
- Cache avec invalidation

**Usage:**
```python
from services import WebhookConfigService
from pathlib import Path

# Initialisation
service = WebhookConfigService.get_instance(
    file_path=Path("debug/webhook_config.json")
)

# Définir URL avec validation
ok, msg = service.set_webhook_url("https://hook.eu2.make.com/abc123")
if ok:
    print("URL valide et enregistrée")
else:
    print(f"Erreur: {msg}")

# Format Make.com auto-normalisé
ok, msg = service.set_webhook_url("abc123@hook.eu2.make.com")
# Converti en: https://hook.eu2.make.com/abc123

# Configuration Absence Globale
absence = service.get_absence_config()
service.update_absence_config({
    "absence_pause_enabled": True,
    "absence_pause_days": ["saturday", "sunday"],
})
```

---

### 4. AuthService

**Fichier:** `auth_service.py`  
**Pattern:** Standard (inject ConfigService)  
**Responsabilité:** Authentification unifiée (dashboard + API)

**Fonctionnalités:**
- Authentification dashboard (Flask-Login)
- Authentification API (Bearer token)
- Authentification endpoints test (X-API-Key)
- Gestion LoginManager
- Décorateurs réutilisables

**Usage:**
```python
from services import ConfigService, AuthService
from flask import Flask, request

app = Flask(__name__)
config = ConfigService()
auth = AuthService(config)

# Initialiser Flask-Login
auth.init_flask_login(app)

# Dashboard login
username = request.form.get('username')
password = request.form.get('password')
if auth.verify_dashboard_credentials(username, password):
    user = auth.create_user(username)
    login_user(user)

# Décorateur API
@app.route('/api/protected')
@auth.api_key_required
def protected():
    return {"data": "secret"}

# Décorateur test API
@app.route('/api/test/validate')
@auth.test_api_key_required
def test_endpoint():
    return {"status": "ok"}
```

---

### 5. DeduplicationService

**Fichier:** `deduplication_service.py`  
**Pattern:** Standard (inject services)  
**Responsabilité:** Déduplication emails et subject groups

**Fonctionnalités:**
- Dédup par email ID
- Dédup par subject group
- Fallback mémoire si Redis down
- Scoping mensuel automatique
- Génération subject group ID intelligente

**Usage:**
```python
from services import DeduplicationService, ConfigService

config = ConfigService()

dedup = DeduplicationService.get_instance(
    redis_client=redis_client,  # None = fallback mémoire
    logger=app.logger,
    config_service=config,
)

# Email ID dedup
email_id = "unique-email-id-123"
if not dedup.is_email_processed(email_id):
    # Traiter l'email
    process_email(email_id)
    dedup.mark_email_processed(email_id)

# Subject group dedup
subject = "Média Solution - Missions Recadrage - Lot 42"
if not dedup.is_subject_group_processed(subject):
    # Traiter
    process_subject(subject)
    dedup.mark_subject_group_processed(subject)

# Générer ID de groupe
group_id = dedup.generate_subject_group_id(subject)
# → "media_solution_missions_recadrage_lot_42"

# Stats
stats = dedup.get_memory_stats()
print(f"Email IDs in memory: {stats['email_ids_count']}")
print(f"Using Redis: {stats['using_redis']}")
```

---

## 🚀 Quick Start

### Utilisation dans app_render.py

Les services sont **déjà initialisés** dans `app_render.py` :

```python
# Services disponibles globalement dans app_render.py
_config_service = ConfigService()
_runtime_flags_service = RuntimeFlagsService.get_instance(...)
_webhook_service = WebhookConfigService.get_instance(...)
_auth_service = AuthService(_config_service)
_ingress_service = IngressService.get_instance(_config_service)
_dedup_service = DeduplicationService.get_instance(...)
_magic_link_service = MagicLinkService.get_instance(...)
_r2_transfer_service = R2TransferService.get_instance(...)
```

**Utiliser directement:**
```python
# Dans une fonction de app_render.py
def my_function():
    if _config_service.is_email_config_valid():
        # Faire quelque chose
        pass
```

---

### 6. MagicLinkService

**Fichier:** `magic_link_service.py`  
**Pattern:** Singleton  
**Responsabilité:** Génération et validation des magic links pour authentification sans mot de passe

**Fonctionnalités:**
- Génération de tokens HMAC SHA-256 signés (`<id>.<expires>.<signature>`)
- Support one-shot (TTL configurable) et permanent (`expires = permanent`)
- Stockage fichier JSON verrouillé, miroir optionnel Redis ou API PHP
- Marquage des tokens consommés et révocation ciblée
- Nettoyage des tokens expirés

**Usage:**
```python
from services import MagicLinkService

service = MagicLinkService.get_instance()

# Générer un token one-shot : (token, expires_at)
token, expires_at = service.generate_token(unlimited=False)

# Générer un token permanent : expires_at vaut None
permanent_token, _ = service.generate_token(unlimited=True)

# Consommer un token : (success, username ou message d'erreur)
ok, message = service.consume_token(token)
if ok:
    print(f"Connecté en tant que {message}")

# Révoquer un token précis ou tous les tokens
token_id = token.split(".")[0]
service.revoke_token(token_id)
service.revoke_all_tokens()
```

---

### 7. R2TransferService

**Fichier:** `r2_transfer_service.py`  
**Pattern:** Singleton  
**Responsabilité:** Offload Cloudflare R2 pour économiser la bande passante

**Fonctionnalités:**
- Normalisation URLs Dropbox (y compris `/scl/fo/`)
- Fetch distant via Worker Cloudflare sécurisé (token X-R2-FETCH-TOKEN)
- Persistance paires `source_url`/`r2_url` + `original_filename`
- Fallback gracieux si Worker indisponible
- Timeout spécifique pour dossiers Dropbox (120s)
- Validation ZIP et métadonnées

**Usage:**
```python
from services import R2TransferService

# Initialisation (automatique via get_instance)
service = R2TransferService.get_instance()

# Vérifier si le service est activé
if service.is_enabled():
    print("Service R2 activé")
    print(f"Endpoint: {service.get_fetch_endpoint()}")
    print(f"Bucket: {service.get_bucket_name()}")

# Demander un offload distant
try:
    result = service.request_remote_fetch(
        source_url="https://www.dropbox.com/scl/fi/...",
        provider="dropbox",
        original_filename="document.pdf"
    )
    if result and result.get('r2_url'):
        print(f"Offload réussi: {result['r2_url']}")
        print(f"Nom original: {result.get('original_filename')}")
    else:
        print("Offload échoué, utilisation URL source")
except Exception as e:
    print(f"Erreur R2: {e}")

# Persister manuellement une paire source/R2
service.persist_link_pair(
    source_url="https://example.com/file.pdf",
    r2_url="https://cdn.example.com/file.pdf",
    original_filename="file.pdf"
)

# Lister les liens récents
recent_links = service.get_recent_links(limit=10)
for link in recent_links:
    print(f"{link['provider']}: {link['original_filename']}")
```

---

### 8. IngressService

**Fichier:** `ingress_service.py`
**Pattern:** Singleton (`get_instance(config_service)`)
**Responsabilité:** Point d'entrée unique du flux Gmail Push

`process_gmail_push(payload)` retourne `(réponse, code_http)` et délègue la validation, la déduplication, la résolution des créneaux, l'enrichissement R2 et l'envoi webhook. L'exécuteur est borné ; `shutdown_executor()` et `reset_instance()` servent aux tests et à l'arrêt propre.

```python
from services import IngressService

result, status_code = IngressService.get_instance(config_service).process_gmail_push(payload)
```

### 9. RoutingRulesService

**Fichier:** `routing_rules_service.py`
**Pattern:** Singleton
**Responsabilité:** Règles de routage dynamiques (Redis-first, cache TTL)

```python
service = RoutingRulesService.get_instance(app_config_store=store)
rules = service.get_rules()
ok, message, payload = service.update_rules(new_rules)
```

Les conditions sont validées avant écriture ; `reload()` invalide le cache après une modification externe.

### 10. RateLimitService, RuntimeMetricsService, WebhookLoggerService

| Service | Interface principale | Rôle |
| --- | --- | --- |
| `RateLimitService` | `allow_send(limit_per_hour)`, `record_event()` | Compteur de débit partagé (Redis) |
| `RuntimeMetricsService` | `get_process_start_time()`, `get_last_poll_cycle_ts()` | Métriques exposées par `/api/utility` |
| `WebhookLoggerService` | `append_log(entry)` | Journal webhook Redis-first avec fallback JSON |

Ces trois services suivent le même contrat de singleton : `get_instance()` pour l'usage courant, `reset_instance()` réservé aux tests.

### Utilisation dans les Routes (Blueprints)

**Option 1: Importer depuis app_render**
```python
# Dans routes/api_webhooks.py par exemple
from app_render import _config_service, _webhook_service

@bp.route('/webhook/config')
def get_config():
    return {
        "url": _webhook_service.get_webhook_url(),
        "ssl_verify": _config_service.get_webhook_ssl_verify(),
    }
```

**Option 2: Créer vos propres instances**
```python
from services import ConfigService

def my_route():
    config = ConfigService()
    # Utiliser config
```

---

## ✅ Tests

Tous les services ont des tests unitaires dédiés :

```bash
pytest tests/test_services.py -v
pytest tests/test_r2_transfer_service.py tests/test_routing_rules_service.py -v
```

Les taux de couverture évoluent à chaque run ; se référer au rapport `pytest-cov` (`.coveragerc`) plutôt qu'à des chiffres figés ici.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `docs/core/architecture.md` | Rôle des services dans l'architecture |
| `docs/core/configuration-reference.md` | Variables et stockage de configuration |
| `tests/test_services.py` | Tests = documentation vivante |

---

## 🔧 Dépannage

### Le service retourne None

**Cause:** Échec d'initialisation  
**Solution:** Vérifier les logs au démarrage (préfixe `SVC:`)

```
INFO - SVC: RuntimeFlagsService initialized (cache_ttl=60s)
ERROR - SVC: Failed to initialize WebhookConfigService: ...
```

### Cache pas mis à jour

**Service:** RuntimeFlagsService, WebhookConfigService  
**Solution:** Forcer rechargement

```python
service.reload()  # Invalide cache, force reload depuis disque
```

### Redis indisponible

**Service:** DeduplicationService  
**Comportement:** Fallback automatique en mémoire (process-local)  
**Vérification:**

```python
stats = dedup.get_memory_stats()
print(stats['using_redis'])  # False = fallback mémoire
```

---

## 🎯 Bonnes Pratiques

### 1. Injecter les Dépendances

```python
# ✅ BON
def my_function(config_service: ConfigService):
    return config_service.get_webhook_url()

# ❌ ÉVITER
def my_function():
    config = ConfigService()  # Nouvelle instance à chaque appel
    return config.get_webhook_url()
```

### 2. Utiliser les Singletons Correctement

```python
# ✅ BON - Initialisation une fois
service = RuntimeFlagsService.get_instance(path, defaults)

# ✅ BON - Récupération ensuite
service = RuntimeFlagsService.get_instance()

# ❌ ÉVITER - Re-initialisation inutile
service = RuntimeFlagsService.get_instance(path, defaults)  # À chaque fois
```

### 3. Gérer les Erreurs

```python
# ✅ BON
try:
    ok, msg = webhook_service.set_webhook_url(url)
    if not ok:
        logger.error(f"Invalid webhook: {msg}")
except Exception as e:
    logger.error(f"Failed to set webhook: {e}")

# ❌ ÉVITER - Pas de gestion d'erreur
webhook_service.set_webhook_url(url)  # Peut lever exception
```

---

## 💡 Contribuer

### Ajouter un Nouveau Service

1. Créer `services/my_service.py`
2. Implémenter la classe avec docstrings
3. Ajouter au `services/__init__.py`
4. Créer tests dans `tests/test_services.py`
5. Documenter dans ce README

### Standards de Code

- ✅ Annotations de types complètes
- ✅ Docstrings Google style
- ✅ Gestion d'erreurs robuste
- ✅ Tests unitaires (>70% couverture)
- ✅ Logs avec préfixe `SVC:`

---

## 📞 Support

**Questions ?**  
Voir les exemples dans `docs/core/architecture.md`

**Bugs ?**  
Vérifier les logs (préfixe `SVC:`) et les tests

**Améliora tions ?**  
Suivre les décisions dans `memory-bank/decisionLog.md`

---

**Version:** 1.1  
**Status:** ✅ Production Ready  
**Last Update:** 2026-11-25
