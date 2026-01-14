# Plan de Refactoring Profond - Architecture Services
**Date:** 2025-11-17  
**Objectif:** Restructurer les modules de configuration et authentification avec une architecture orientée services

## 🎯 Objectifs du Refactoring

### Objectifs Principaux
1. **Centralisation** - Point d'accès unique pour chaque domaine fonctionnel
2. **Testabilité** - Services facilement mockables et testables
3. **Maintenabilité** - Code organisé, responsabilités claires
4. **Évolutivité** - Architecture extensible pour futurs besoins
5. **Sécurité** - Encapsulation des données sensibles

### Patterns Utilisés
- **Service Pattern** - Encapsulation de logique métier
- **Singleton Pattern** - Instance unique pour services stateless
- **Dependency Injection** - Inversion de contrôle
- **Factory Pattern** - Création d'instances configurées

## 📋 Architecture Cible

```
render_signal_server/
├── services/                    # NOUVEAU
│   ├── __init__.py
│   ├── config_service.py        # Configuration centralisée
│   ├── runtime_flags_service.py # Runtime flags avec cache
│   ├── webhook_config_service.py# Webhooks avec validation
│   ├── auth_service.py          # Authentification unifiée
│   └── deduplication_service.py # Déduplication Redis/Memory
│
├── config/
│   ├── settings.py              # REFACTORÉ - Données brutes uniquement
│   ├── polling_config.py        # ✅ Déjà refactoré (PollingConfigService)
│   ├── runtime_flags.py         # DÉPRÉCIÉ → services/runtime_flags_service.py
│   └── webhook_config.py        # DÉPRÉCIÉ → services/webhook_config_service.py
│
├── auth/
│   ├── user.py                  # REFACTORÉ - Utilise AuthService
│   └── helpers.py               # REFACTORÉ - Utilise AuthService
│
└── deduplication/
    ├── redis_client.py          # DÉPRÉCIÉ → services/deduplication_service.py
    └── subject_group.py         # INTÉGRÉ dans DeduplicationService
```

## 🔧 Services à Créer

### 1. ConfigService (`services/config_service.py`)

**Responsabilité:** Accès centralisé à toute la configuration applicative

```python
class ConfigService:
    """Service centralisé pour accéder à la configuration applicative.
    
    Remplace l'accès direct aux variables de config.settings.
    Fournit validation, transformation et cache si nécessaire.
    """
    
    def __init__(self, settings_module=None):
        self._settings = settings_module or self._import_settings()
    
    # Configuration IMAP
    def get_email_config(self) -> dict:
        """Retourne la configuration email complète et validée."""
        
    def is_email_config_valid(self) -> bool:
        """Vérifie si la config email est complète."""
    
    # Configuration Webhooks
    def get_webhook_url(self) -> str:
        """Retourne l'URL webhook principale."""
        
    def get_webhook_ssl_verify(self) -> bool:
        """Retourne si la vérification SSL est activée."""
    
    # Configuration API
    def get_api_token(self) -> str:
        """Retourne le token API (sensible)."""
        
    def verify_api_token(self, token: str) -> bool:
        """Vérifie un token API."""
    
    # Configuration Render
    def get_render_config(self) -> dict:
        """Retourne la configuration Render (deploy)."""
    
    # Configuration Présence
    def get_presence_config(self) -> dict:
        """Retourne la configuration webhooks de présence."""
```

**Bénéfices:**
- ✅ Validation centralisée
- ✅ Transformation des valeurs (ex: normalisation URLs)
- ✅ Cache pour valeurs coûteuses
- ✅ Interface stable même si settings change

---

### 2. RuntimeFlagsService (`services/runtime_flags_service.py`)

**Responsabilité:** Gestion des flags runtime avec cache et persistence

```python
class RuntimeFlagsService:
    """Service pour gérer les flags runtime avec cache intelligent.
    
    Features:
    - Cache en mémoire avec invalidation
    - Persistence JSON
    - Thread-safe
    - Validation des valeurs
    """
    
    _instance = None  # Singleton
    
    def __init__(self, file_path: Path, defaults: dict):
        self._file_path = file_path
        self._defaults = defaults
        self._cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60  # seconds
    
    @classmethod
    def get_instance(cls, file_path: Path = None, defaults: dict = None):
        """Pattern Singleton avec lazy initialization."""
        if cls._instance is None:
            cls._instance = cls(file_path, defaults)
        return cls._instance
    
    def get_flag(self, key: str, default=None) -> bool:
        """Récupère un flag avec cache."""
        
    def set_flag(self, key: str, value: bool) -> bool:
        """Définit un flag et persiste."""
        
    def get_all_flags(self) -> dict:
        """Retourne tous les flags."""
        
    def update_flags(self, updates: dict) -> bool:
        """Met à jour plusieurs flags atomiquement."""
        
    def reload(self) -> None:
        """Force le rechargement depuis le disque."""
        
    def _load_from_disk(self) -> dict:
        """Charge depuis JSON avec gestion d'erreurs."""
        
    def _save_to_disk(self, data: dict) -> bool:
        """Sauvegarde avec gestion d'erreurs."""
```

**Bénéfices:**
- ✅ Cache intelligent (évite I/O répétitives)
- ✅ Thread-safe pour accès concurrent
- ✅ Pattern Singleton (instance unique)
- ✅ Invalidation automatique du cache

---

### 3. WebhookConfigService (`services/webhook_config_service.py`)

**Responsabilité:** Configuration webhooks avec validation stricte

```python
class WebhookConfigService:
    """Service pour gérer la configuration des webhooks.
    
    Features:
    - Validation des URLs (HTTPS requis)
    - Normalisation URLs Make.com
    - Cache avec invalidation
    - Persistence JSON
    - Intégration avec external store
    """
    
    _instance = None
    
    def __init__(self, file_path: Path, external_store=None):
        self._file_path = file_path
        self._external_store = external_store
        self._cache = None
    
    @classmethod
    def get_instance(cls, file_path: Path = None, external_store=None):
        """Singleton avec lazy init."""
        
    def get_webhook_url(self) -> str:
        """Retourne l'URL webhook principale."""
        
    def set_webhook_url(self, url: str) -> tuple[bool, str]:
        """Définit l'URL webhook avec validation."""
        
    def get_presence_config(self) -> dict:
        """Configuration présence (true/false URLs)."""
        
    def update_presence_config(self, config: dict) -> tuple[bool, str]:
        """Met à jour la config présence."""
        
    def get_ssl_verify(self) -> bool:
        """Retourne le flag SSL verify."""
        
    def get_time_window(self) -> dict:
        """Retourne la fenêtre horaire."""
        
    def is_webhook_enabled(self) -> bool:
        """Vérifie si l'envoi de webhooks est activé."""
        
    def validate_webhook_url(self, url: str) -> tuple[bool, str]:
        """Valide une URL webhook."""
        
    def _normalize_url(self, url: str) -> str:
        """Normalise les URLs Make.com."""
```

**Bénéfices:**
- ✅ Validation stricte des URLs
- ✅ Prévention d'erreurs de configuration
- ✅ Synchronisation avec external store
- ✅ Cache pour performance

---

### 4. AuthService (`services/auth_service.py`)

**Responsabilité:** Authentification unifiée (dashboard + API)

```python
class AuthService:
    """Service centralisé pour toute l'authentification.
    
    Combine:
    - Authentification dashboard (user/password)
    - Authentification API (X-API-Key)
    - Flask-Login management
    """
    
    def __init__(self, config_service: ConfigService):
        self._config = config_service
        self._login_manager = None
    
    # Dashboard Authentication
    def verify_dashboard_credentials(self, username: str, password: str) -> bool:
        """Vérifie les credentials du dashboard."""
        
    def create_user(self, username: str) -> User:
        """Crée une instance User pour Flask-Login."""
        
    def load_user(self, user_id: str) -> User | None:
        """User loader pour Flask-Login."""
    
    # API Authentication
    def verify_api_key(self, request) -> bool:
        """Vérifie la clé API dans les headers."""
        
    def verify_test_api_key(self, request) -> bool:
        """Vérifie la clé API pour endpoints de test."""
    
    # Flask-Login Integration
    def init_flask_login(self, app, login_view: str = 'dashboard.login'):
        """Initialise Flask-Login avec ce service."""
        
    def get_login_manager(self):
        """Retourne le LoginManager configuré."""
    
    # Decorators
    @staticmethod
    def api_key_required(func):
        """Décorateur pour protéger les endpoints API."""
        
    @staticmethod
    def test_api_key_required(func):
        """Décorateur pour endpoints de test."""
```

**Bénéfices:**
- ✅ Authentification centralisée
- ✅ Séparation dashboard/API claire
- ✅ Décorateurs réutilisables
- ✅ Facilite l'ajout de nouveaux mécanismes auth

---

### 5. DeduplicationService (`services/deduplication_service.py`)

**Responsabilité:** Déduplication emails et subject groups

```python
class DeduplicationService:
    """Service pour la déduplication avec Redis et fallback mémoire.
    
    Features:
    - Déduplication par email ID
    - Déduplication par subject group
    - Fallback mémoire si Redis indisponible
    - Scoping mensuel optionnel
    - Thread-safe
    """
    
    def __init__(
        self,
        redis_client=None,
        logger=None,
        config_service: ConfigService = None,
        polling_config_service = None
    ):
        self._redis = redis_client
        self._logger = logger
        self._config = config_service
        self._polling_config = polling_config_service
        
        # In-memory fallbacks
        self._processed_email_ids = set()
        self._processed_subject_groups = set()
    
    # Email ID Deduplication
    def is_email_processed(self, email_id: str) -> bool:
        """Vérifie si un email a déjà été traité."""
        
    def mark_email_processed(self, email_id: str) -> bool:
        """Marque un email comme traité."""
    
    # Subject Group Deduplication
    def is_subject_group_processed(self, subject: str) -> bool:
        """Vérifie si un subject group a été traité."""
        
    def mark_subject_group_processed(self, subject: str) -> bool:
        """Marque un subject group comme traité."""
        
    def generate_subject_group_id(self, subject: str) -> str:
        """Génère un ID de groupe stable pour un sujet."""
    
    # Configuration
    def is_email_dedup_enabled(self) -> bool:
        """Vérifie si la dédup email est activée."""
        
    def is_subject_dedup_enabled(self) -> bool:
        """Vérifie si la dédup subject est activée."""
    
    # Internal helpers
    def _get_scoped_group_id(self, group_id: str) -> str:
        """Applique le scoping mensuel si activé."""
        
    def _use_redis(self) -> bool:
        """Vérifie si Redis est disponible."""
```

**Bénéfices:**
- ✅ Logique dédup centralisée
- ✅ Fallback automatique si Redis down
- ✅ Configuration injectable
- ✅ Facilite les tests (mock Redis)

---

## 🔄 Migration des Modules Existants

### config/settings.py
**Changements:**
- ❌ Supprimer: Rien (reste source de vérité)
- ✅ Ajouter: Types annotations complets
- ✅ Ajouter: Validation des valeurs critiques
- ✅ Déprécier: Accès direct (utiliser ConfigService)

### config/runtime_flags.py
**Changements:**
- ⚠️ **DÉPRÉCIÉ** - Remplacé par RuntimeFlagsService
- 📝 Garder pour compatibilité temporaire
- 📝 Ajouter warnings de dépréciation

### config/webhook_config.py
**Changements:**
- ⚠️ **DÉPRÉCIÉ** - Remplacé par WebhookConfigService
- 📝 Garder pour compatibilité temporaire

### auth/user.py
**Changements:**
- ✅ Utiliser AuthService pour verify_credentials
- ✅ Garder classe User (nécessaire pour Flask-Login)
- ✅ Simplifier init_login_manager

### auth/helpers.py
**Changements:**
- ✅ Déplacer testapi_authorized vers AuthService
- ✅ Garder décorateurs comme wrappers vers AuthService

### deduplication/redis_client.py
**Changements:**
- ⚠️ **DÉPRÉCIÉ** - Logique migrée vers DeduplicationService
- 📝 Garder pour compatibilité

### deduplication/subject_group.py
**Changements:**
- ⚠️ **INTÉGRÉ** dans DeduplicationService.generate_subject_group_id()
- 📝 Garder wrapper pour compatibilité

---

## 📊 Impact sur app_render.py

### Avant
```python
# Multiples imports et initialisations
from config import settings
from config import runtime_flags
from config import webhook_config
from auth import user, helpers
import deduplication.redis_client as _dedup

# Variables globales dispersées
email_config_valid = bool(EMAIL_ADDRESS and ...)
WEBHOOK_URL = settings.WEBHOOK_URL
redis_client = None
```

### Après
```python
# Imports services
from services import (
    ConfigService,
    RuntimeFlagsService,
    WebhookConfigService,
    AuthService,
    DeduplicationService,
)
from config.polling_config import PollingConfigService

# Initialisation centralisée
_config_service = ConfigService()
_runtime_flags_service = RuntimeFlagsService.get_instance(
    RUNTIME_FLAGS_FILE, defaults={...}
)
_webhook_service = WebhookConfigService.get_instance(
    WEBHOOK_CONFIG_FILE, external_store=_store
)
_auth_service = AuthService(_config_service)
_dedup_service = DeduplicationService(
    redis_client, app.logger, _config_service, _polling_service
)

# Utilisation simplifiée
if _config_service.is_email_config_valid():
    ...
if _dedup_service.is_email_processed(email_id):
    ...
```

---

## ✅ Critères de Validation

### Tests Unitaires (À Créer)
- [ ] `tests/services/test_config_service.py`
- [ ] `tests/services/test_runtime_flags_service.py`
- [ ] `tests/services/test_webhook_config_service.py`
- [ ] `tests/services/test_auth_service.py`
- [ ] `tests/services/test_deduplication_service.py`

### Tests d'Intégration
- [ ] Tous les tests existants passent (58/58)
- [ ] Démarrage application sans erreur
- [ ] Endpoints API fonctionnels
- [ ] Authentification dashboard OK
- [ ] Déduplication fonctionnelle

### Documentation
- [ ] README des services
- [ ] Exemples d'utilisation
- [ ] Guide de migration
- [ ] Diagrammes d'architecture

---

## 📅 Planning d'Exécution

### Phase 1: Fondations (2h)
- Créer structure `services/`
- Implémenter ConfigService
- Implémenter RuntimeFlagsService
- Tests unitaires de base

### Phase 2: Configuration (1.5h)
- Implémenter WebhookConfigService
- Migration des usages dans routes/
- Tests d'intégration

### Phase 3: Authentification (1h)
- Implémenter AuthService
- Refactoriser auth/user.py et auth/helpers.py
- Tests

### Phase 4: Déduplication (1.5h)
- Implémenter DeduplicationService
- Migration depuis app_render.py
- Tests avec mock Redis

### Phase 5: Intégration (1h)
- Refactoriser app_render.py complet
- Validation tous tests
- Documentation

**Total estimé: 6-7 heures**

---

## 🎯 Résultats Attendus

### Métriques de Qualité
| Métrique | Avant | Après | Objectif |
|----------|-------|-------|----------|
| Lignes dans app_render.py | 782 | ~650 | -15% |
| Services réutilisables | 1 | 6 | +500% |
| Couverture tests services | 0% | 80% | Nouveau |
| Points d'accès config | Multiple | 1 (ConfigService) | Centralisé |
| Singletons thread-safe | 0 | 3 | Robustesse |

### Bénéfices Long Terme
✅ **Testabilité** - Services mockables facilement  
✅ **Évolutivité** - Ajout de fonctionnalités simplifié  
✅ **Maintenabilité** - Responsabilités claires  
✅ **Performance** - Cache intelligent  
✅ **Sécurité** - Validation centralisée  
✅ **Documentation** - Architecture claire  

---

**Status:** 📋 Plan validé - Prêt pour implémentation  
**Prochaine étape:** Création de `services/__init__.py` et `services/config_service.py`
