# Guide d'Utilisation des Services

**Date:** 2025-11-17  
**Architecture:** Services Orientés Objets  

Ce document fournit des exemples concrets d'utilisation des services nouvellement créés.

---

## Table des Matières

1. [ConfigService](#configservice)
2. [RuntimeFlagsService](#runtimeflagsservice)
3. [WebhookConfigService](#webhookconfigservice)
4. [AuthService](#authservice)
5. [DeduplicationService](#deduplicationservice)
6. [Intégration dans app_render.py](#intégration-complète)

---

## ConfigService

Service centralisé pour accéder à toute la configuration applicative.

### Utilisation Basique

```python
from services import ConfigService

# Créer une instance
config = ConfigService()

# Configuration Email
if config.is_email_config_valid():
    email_cfg = config.get_email_config()
    print(f"Email: {email_cfg['address']}")
    print(f"Server: {email_cfg['server']}:{email_cfg['port']}")

# Configuration Webhooks
if config.has_webhook_url():
    webhook_url = config.get_webhook_url()
    ssl_verify = config.get_webhook_ssl_verify()
    print(f"Webhook: {webhook_url} (SSL: {ssl_verify})")

# Authentification API
api_token = config.get_api_token()
if config.verify_api_token("some-token"):
    print("Token valide")

# Configuration Déduplication
dedup_config = config.get_dedup_redis_keys()
email_dedup_disabled = config.is_email_id_dedup_disabled()
subject_dedup_enabled = config.is_subject_group_dedup_enabled()
```

### Injection dans d'Autres Services

```python
from services import ConfigService, AuthService

config = ConfigService()
auth = AuthService(config)  # Inject config dans auth
```

---

## RuntimeFlagsService

Service pour gérer les flags runtime avec cache intelligent (Singleton).

### Initialisation (Une fois au démarrage)

```python
from services import RuntimeFlagsService
from pathlib import Path

# Première initialisation - créer l'instance
service = RuntimeFlagsService.get_instance(
    file_path=Path("debug/runtime_flags.json"),
    defaults={
        "disable_email_id_dedup": False,
        "allow_custom_webhook_without_links": False,
    }
)
```

### Utilisation

```python
from services import RuntimeFlagsService

# Récupérer l'instance (déjà initialisée)
service = RuntimeFlagsService.get_instance()

# Lire un flag
if service.get_flag("disable_email_id_dedup"):
    print("Email ID dedup is disabled")

# Modifier un flag (persiste immédiatement)
service.set_flag("disable_email_id_dedup", True)

# Lire tous les flags
all_flags = service.get_all_flags()
print(all_flags)

# Mettre à jour plusieurs flags atomiquement
service.update_flags({
    "disable_email_id_dedup": False,
    "allow_custom_webhook_without_links": True,
})

# Forcer rechargement depuis disque
service.reload()
```

### Configuration du Cache

```python
service = RuntimeFlagsService.get_instance()

# Voir TTL actuel
print(f"Cache TTL: {service.get_cache_ttl()}s")

# Modifier TTL
service.set_cache_ttl(120)  # 2 minutes

# Vérifier état du cache
if service.is_cache_valid():
    print("Cache is valid")
```

---

## WebhookConfigService

Service pour gérer la configuration webhooks avec validation (Singleton).

### Initialisation

```python
from services import WebhookConfigService
from pathlib import Path

service = WebhookConfigService.get_instance(
    file_path=Path("../../debug/webhook_config.json"),
    external_store=None  # Optionnel: app_config_store
)
```

### Gestion des URLs

```python
from services import WebhookConfigService

service = WebhookConfigService.get_instance()

# Définir une URL avec validation
ok, msg = service.set_webhook_url("https://hook.eu2.make.com/abc123")
if ok:
    print("URL mise à jour")
else:
    print(f"Erreur: {msg}")

# URLs au format Make.com (auto-normalisées)
ok, msg = service.set_webhook_url("abc123@hook.eu2.make.com")
# Sera converti en: https://hook.eu2.make.com/abc123

# Lire l'URL actuelle
url = service.get_webhook_url()
print(f"Current webhook URL: {url}")
```

### Configuration Présence

```python
service = WebhookConfigService.get_instance()

# Lire config présence
presence = service.get_presence_config()
print(f"Flag: {presence['flag']}")
print(f"True URL: {presence['true_url']}")
print(f"False URL: {presence['false_url']}")

# Mettre à jour
ok, msg = service.update_presence_config({
    "presence_flag": True,
    "presence_true_url": "https://hook.eu2.make.com/presence_true",
    "presence_false_url": "https://hook.eu2.make.com/presence_false",
})
```

### SSL et Envoi Activé

```python
service = WebhookConfigService.get_instance()

# Vérifier si SSL activé
if service.get_ssl_verify():
    print("SSL verification enabled")

# Désactiver SSL (développement uniquement!)
service.set_ssl_verify(False)

# Vérifier si envoi activé
if service.is_webhook_sending_enabled():
    print("Webhook sending is enabled")

# Désactiver temporairement l'envoi
service.set_webhook_sending_enabled(False)
```

---

## AuthService

Service centralisé pour l'authentification (dashboard + API).

### Initialisation avec Flask

```python
from flask import Flask
from services import ConfigService, AuthService

app = Flask(__name__)
config = ConfigService()
auth = AuthService(config)

# Initialiser Flask-Login
auth.init_flask_login(app, login_view='dashboard.login')
```

### Authentification Dashboard

```python
from flask import request
from flask_login import login_user
from services import AuthService, ConfigService

config = ConfigService()
auth = AuthService(config)

# Dans une route de login
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Vérifier credentials
    if auth.verify_dashboard_credentials(username, password):
        user = auth.create_user(username)
        login_user(user)
        return {"status": "success"}
    
    return {"status": "error", "message": "Invalid credentials"}, 401
```

### Authentification API

```python
from services import AuthService

# Vérifier token depuis request
@app.route('/api/protected')
def protected():
    if not auth.verify_api_key_from_request(request):
        return {"error": "Unauthorized"}, 401
    return {"data": "secret"}
```

### Utilisation des Décorateurs

```python
# Décorateur pour API token
@app.route('/api/process')
@auth.api_key_required
def process_endpoint():
    return {"status": "processing"}

# Décorateur pour test API key
@app.route('/api/test/validate')
@auth.test_api_key_required
def test_endpoint():
    return {"status": "test ok"}
```

---

## DeduplicationService

Service pour déduplication emails et subject groups.

### Initialisation

```python
from services import DeduplicationService, ConfigService
from config.polling_config import PollingConfigService

config = ConfigService()
polling_config = PollingConfigService()

dedup = DeduplicationService(
    redis_client=redis_client,  # Optionnel (None = fallback mémoire)
    logger=app.logger,
    config_service=config,
    polling_config_service=polling_config
)
```

### Déduplication Email ID

```python
# Vérifier si déjà traité
email_id = "abc123xyz"
if dedup.is_email_processed(email_id):
    print("Email déjà traité - skip")
else:
    # Traiter l'email
    process_email(email_id)
    
    # Marquer comme traité
    dedup.mark_email_processed(email_id)
```

### Déduplication Subject Group

```python
# Vérifier un sujet
subject = "Média Solution - Missions Recadrage - Lot 42"

if dedup.is_subject_group_processed(subject):
    print("Ce lot a déjà été traité ce mois-ci")
else:
    # Traiter le sujet
    process_subject(subject)
    
    # Marquer le groupe comme traité
    dedup.mark_subject_group_processed(subject)
```

### Génération Subject Group ID

```python
# Générer ID de groupe
subject1 = "Média Solution - Missions Recadrage - Lot 42"
group_id1 = dedup.generate_subject_group_id(subject1)
# Résultat: "media_solution_missions_recadrage_lot_42"

subject2 = "Re: Fwd: Média Solution - Lot 42"
group_id2 = dedup.generate_subject_group_id(subject2)
# Résultat: "media_solution_missions_recadrage_lot_42" (même groupe!)

subject3 = "Autre sujet quelconque"
group_id3 = dedup.generate_subject_group_id(subject3)
# Résultat: "subject_hash_<md5>" (fallback)
```

### Statistiques et Diagnostic

```python
# Voir les stats du fallback mémoire
stats = dedup.get_memory_stats()
print(f"Email IDs in memory: {stats['email_ids_count']}")
print(f"Subject groups in memory: {stats['subject_groups_count']}")
print(f"Using Redis: {stats['using_redis']}")

# Vider le cache mémoire (tests/débogage uniquement)
dedup.clear_memory_cache()
```

---

## Intégration Complète

Exemple d'intégration dans `app_render.py`:

```python
from flask import Flask
from services import (
    ConfigService,
    RuntimeFlagsService,
    WebhookConfigService,
    AuthService,
    DeduplicationService,
)
from config.polling_config import PollingConfigService

app = Flask(__name__)

# === Initialisation des Services ===

# 1. Configuration
_config_service = ConfigService()

# 2. Runtime Flags (Singleton)
_runtime_flags_service = RuntimeFlagsService.get_instance(
    file_path=Path("debug/runtime_flags.json"),
    defaults={
        "disable_email_id_dedup": False,
        "allow_custom_webhook_without_links": False,
    }
)

# 3. Webhook Config (Singleton)
_webhook_service = WebhookConfigService.get_instance(
    file_path=Path("debug/webhook_config.json"),
    external_store=None  # ou app_config_store
)

# 4. Auth
_auth_service = AuthService(_config_service)
_auth_service.init_flask_login(app)

# 5. Polling (déjà refactoré)
_polling_service = PollingConfigService(settings)

# 6. Deduplication
_dedup_service = DeduplicationService(
    redis_client=redis_client,
    logger=app.logger,
    config_service=_config_service,
    polling_config_service=_polling_service,
)

# === Utilisation dans le Code ===

# Vérifier config email
if _config_service.is_email_config_valid():
    # Démarrer polling...
    pass

# Vérifier flags runtime
if not _runtime_flags_service.get_flag("disable_email_id_dedup"):
    if not _dedup_service.is_email_processed(email_id):
        # Traiter email
        _dedup_service.mark_email_processed(email_id)

# Envoyer webhook
if _webhook_service.is_webhook_sending_enabled():
    webhook_url = _webhook_service.get_webhook_url()
    # Envoyer...

# Route protégée
@app.route('/api/admin/deploy')
@_auth_service.api_key_required
def deploy():
    return {"status": "deploying"}
```

---

## Avantages de cette Architecture

### ✅ Testabilité
```python
# Mock facile pour les tests
mock_config = MockConfigService()
auth = AuthService(mock_config)
```

### ✅ Centralisation
```python
# Un seul point pour accéder à la config
url = _config_service.get_webhook_url()  # Au lieu de settings.WEBHOOK_URL
```

### ✅ Validation
```python
# Validation automatique
ok, msg = _webhook_service.set_webhook_url("invalid-url")
# ok = False, msg = "L'URL doit commencer par https://"
```

### ✅ Cache Intelligent
```python
# Cache avec TTL automatique
flag = _runtime_flags_service.get_flag("my_flag")  # Depuis cache si valide
```

### ✅ Fallbacks Robustes
```python
# Redis indisponible ? Fallback mémoire automatique
_dedup_service.mark_email_processed(email_id)  # Fonctionne toujours
```

---

## Migration Progressive

Les services peuvent être adoptés progressivement sans tout casser:

```python
# Ancien code (fonctionne toujours)
from config import settings
webhook_url = settings.WEBHOOK_URL

# Nouveau code (préféré)
from services import ConfigService
config = ConfigService()
webhook_url = config.get_webhook_url()

# Les deux peuvent coexister pendant la migration
```

---

**Prochaine étape:** Voir `REFACTORING_ARCHITECTURE_PLAN.md` pour le plan complet de migration.
