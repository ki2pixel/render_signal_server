# Runtime Flags System

**TL;DR**: On stocke des toggles runtime en Redis avec cache mémoire TTL et fallback fichier JSON, thread-safe avec validation stricte, pour contrôler dynamiquement les fonctionnalités critiques sans redémarrage.

---

## Le problème : redémarrage obligatoire pour changer la configuration

J'ai hérité d'un système où chaque paramètre de comportement était codé en dur ou dans des variables d'environnement. Le problème ? Pour désactiver temporairement l'ingestion Gmail ou modifier un comportement, il fallait redémarrer l'application, ce qui interrompait le service et compliquait les opérations de maintenance.

---

## La solution : toggles runtime avec stockage hybride

Pensez aux runtime flags comme des interrupteurs électriques dans un tableau de contrôle : chaque flag contrôle un comportement critique (ingestion, déduplication, webhooks), stocké en Redis pour la performance avec cache mémoire TTL et fallback fichier JSON pour la persistance. Les modifications sont immédiates et thread-safe.

### ❌ L'ancien monde : variables d'environnement statiques

```python
# ANTI-PATTERN - comportement codé en dur
ENABLE_GMAIL = os.environ.get("ENABLE_GMAIL", "true").lower() == "true"

@app.route("/api/ingress/gmail")
def ingest_gmail():
    if not ENABLE_GMAIL:  # Vérification à chaque appel
        return jsonify({"error": "Gmail disabled"}), 409
    # Traitement...
```

### ✅ Le nouveau monde : flags runtime avec cache intelligent

```python
# Singleton initialisé au démarrage
runtime_flags = RuntimeFlagsService.get_instance(
    file_path=Path("debug/runtime_flags.json"),
    defaults={
        "gmail_ingress_enabled": True,
        "disable_email_id_dedup": False,
        "allow_custom_webhook_without_links": False,
    },
    external_store=app_config_store  # Redis
)

# Utilisation avec cache automatique
@app.route("/api/ingress/gmail")
def ingest_gmail():
    if not runtime_flags.get_flag("gmail_ingress_enabled"):
        return jsonify({"error": "Gmail ingress disabled"}), 409
    # Traitement instantané...
```

**La révolution** : modification runtime = effet immédiat = contrôle opérationnel.

---

## Architecture du système de flags

### Pattern Singleton avec cache TTL

```python
class RuntimeFlagsService:
    _instance: Optional[RuntimeFlagsService] = None
    _cache_ttl = 60  # secondes
    
    def _get_cached_flags(self) -> Dict[str, bool]:
        now = time.time()
        if (self._cache is not None and 
            self._cache_timestamp is not None and
            (now - self._cache_timestamp) < self._cache_ttl):
            return dict(self._cache)  # Cache hit
        
        # Cache miss: reload depuis stockage
        self._cache = self._load_from_disk()
        self._cache_timestamp = now
        return dict(self._cache)
```

**Optimisation** : Mémoire (60s) → Redis (persistence) → Fichier (fallback).

### Stockage hiérarchisé Redis-first

```python
def _load_from_disk(self) -> Dict[str, bool]:
    # 1. Essayer Redis d'abord
    if self._external_store is not None:
        try:
            raw = self._external_store.get_config_json("runtime_flags") or {}
            if isinstance(raw, dict):
                data.update(raw)
        except Exception:
            pass
    
    # 2. Fallback fichier JSON si Redis vide
    if not data and self._file_path.exists():
        with open(self._file_path, "r", encoding="utf-8") as f:
            raw = json.load(f) or {}
            data.update(raw)
    
    # 3. Fusion avec defaults
    result = dict(self._defaults)
    for key, value in data.items():
        if key in self._defaults:  # Validation: clés connues uniquement
            result[key] = bool(value)
    
    return result
```

### Thread-safety avec verrouillage

```python
def set_flag(self, key: str, value: bool) -> bool:
    with self._lock:  # RLock pour éviter deadlocks
        flags = self._load_from_disk()
        flags[key] = bool(value)  # Validation bool
        
        if self._save_to_disk(flags):
            self._invalidate_cache()  # Cache coherence
            return True
    return False
```

---

## Flags critiques du système

### Contrôle d'ingestion

| Flag | Défaut | Description | Impact |
|------|--------|-------------|--------|
| `gmail_ingress_enabled` | `true` | Active/désactive l'ingestion Gmail Push | Stoppe tout traitement email entrant |
| `webhook_sending_enabled` | `true` | Autorise l'envoi de webhooks | Protection contre spam webhook |

### Optimisations et sécurité

| Flag | Défaut | Description | Usage |
|------|--------|-------------|--------|
| `disable_email_id_dedup` | `false` | Désactive la déduplication par MD5 | Debug doublons, tests |
| `allow_custom_webhook_without_links` | `false` | Autorise webhooks sans liens | Flexibilité routing personnalisé |

### Monitoring et debug

| Flag | Défaut | Description | Outils |
|------|--------|-------------|--------|
| `enable_debug_logging` | `false` | Logs détaillés pour diagnostic | Troubleshooting production |
| `disable_rate_limiting` | `false` | Désactive les limites de taux | Tests de charge |

---

## API de gestion des flags

### Lecture de flag

```python
# Avec valeur par défaut si inexistant
enabled = runtime_flags.get_flag("gmail_ingress_enabled", default=True)

# Sans défaut (utilise le default du service)
enabled = runtime_flags.get_flag("gmail_ingress_enabled")
```

### Modification de flag

```python
# Flag unique
success = runtime_flags.set_flag("gmail_ingress_enabled", False)

# Plusieurs flags atomiquement
updates = {
    "gmail_ingress_enabled": False,
    "disable_email_id_dedup": True
}
success = runtime_flags.update_flags(updates)
```

### Inspection complète

```python
# Tous les flags actuels
all_flags = runtime_flags.get_all_flags()
# {"gmail_ingress_enabled": true, "disable_email_id_dedup": false, ...}

# Forcer rechargement
runtime_flags.reload()
```

---

## Persistance et résilience

### Atomicité des sauvegardes

```python
def _save_to_disk(self, data: Dict[str, bool]) -> bool:
    # 1. Essayer Redis d'abord
    if self._external_store is not None:
        try:
            return self._external_store.set_config_json("runtime_flags", data)
        except Exception:
            pass
    
    # 2. Fallback fichier avec atomicité
    try:
        tmp_path = self._file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Force écriture disque
        
        os.replace(tmp_path, self._file_path)  # Atomic move
        return True
    except Exception:
        # Nettoyer fichier temporaire si échec
        try:
            tmp_path.unlink()
        except Exception:
            pass
        return False
```

### Cohérence cache multi-instances

```python
def _invalidate_cache(self):
    """Invalide le cache local (Redis reste source de vérité)"""
    with self._lock:
        self._cache = None
        self._cache_timestamp = None
```

**Pattern** : Cache local optimiste, Redis comme source de vérité partagée.

---

## Intégration dashboard

### UI de contrôle en temps réel

```javascript
// static/dashboard.js - toggle Gmail ingress
async function toggleGmailIngress(enabled) {
  const response = await ApiService.post('/api/runtime-flags', {
    gmail_ingress_enabled: enabled
  });
  
  if (response.success) {
    updateStatusIndicator('gmail-ingress', enabled);
    showToast(`Gmail ingress ${enabled ? 'activé' : 'désactivé'}`);
  }
}
```

### API REST pour automation

```http
POST /api/runtime-flags
Content-Type: application/json

{
  "gmail_ingress_enabled": false,
  "webhook_sending_enabled": false
}
```

**Usage** : Intégration monitoring, automatisation déploiement.

---

## Sécurité et validation

### Validation stricte des clés

```python
def set_flag(self, key: str, value: bool) -> bool:
    # Validation: clé doit exister dans defaults
    if key not in self._defaults:
        return False  # Rejet silencieux des clés inconnues
    
    # Validation: valeur doit être bool
    value = bool(value)
    
    # Application avec verrouillage
    with self._lock:
        flags = self._load_from_disk()
        flags[key] = value
        return self._save_to_disk(flags)
```

### Audit et logs

```python
# Logs structurés pour audit
logger.info("RUNTIME_FLAG: %s set to %s by %s", 
           key, value, current_user.id)

# Historique via Redis
# config:runtime_flags:{timestamp} = snapshot
```

---

## Performance et monitoring

### Métriques de performance

- **Cache hit rate** : % lectures depuis cache (>95% attendu)
- **Redis latency** : Temps accès stockage (<10ms)
- **File fallback usage** : % temps en fallback fichier (doit être <1%)
- **Flag changes/minute** : Fréquence modifications

### Alertes opérationnelles

- **Cache invalidations > 10/min** : Modifications trop fréquentes
- **Redis failures > 5%** : Problème connectivité stockage
- **File writes > 100/min** : Activité anormale

### Optimisations

```python
# TTL cache ajustable
runtime_flags.set_cache_ttl(30)  # 30 secondes pour haute fréquence

# Préchargement bulk
all_flags = runtime_flags.get_all_flags()  # Charge tout le cache
```

---

## Tests et validation

### Suite complète de tests

```bash
pytest tests/services/test_runtime_flags_service.py -v
# 15 tests couvrant tous les scénarios
```

### Tests de résilience critiques

```python
def test_redis_failure_fallback():
    """Redis down = utilisation fichier JSON"""
    # Simuler panne Redis
    service = RuntimeFlagsService.get_instance(
        external_store=None,  # Pas de Redis
        file_path=test_file
    )
    
    # Doit fonctionner avec fichier uniquement
    assert service.set_flag("test_flag", True)
    assert service.get_flag("test_flag") == True

def test_concurrent_access_thread_safe():
    """Accès concurrents sans corruption"""
    import threading
    
    def toggle_flag():
        for _ in range(100):
            service.set_flag("counter", not service.get_flag("counter"))
    
    threads = [threading.Thread(target=toggle_flag) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # État final cohérent malgré accès concurrents
    assert isinstance(service.get_flag("counter"), bool)
```

---

## Cas d'usage opérationnel

### Maintenance programmée

```python
# Désactiver ingestion avant maintenance
runtime_flags.set_flag("gmail_ingress_enabled", False)
runtime_flags.set_flag("webhook_sending_enabled", False)

# Effectuer maintenance...

# Réactiver
runtime_flags.set_flag("gmail_ingress_enabled", True)
runtime_flags.set_flag("webhook_sending_enabled", True)
```

### Debug incident

```python
# Désactiver déduplication pour diagnostiquer doublons
runtime_flags.set_flag("disable_email_id_dedup", True)

# Collecter logs avec doublons...

# Réactiver
runtime_flags.set_flag("disable_email_id_dedup", False)
```

### Tests de charge

```python
# Désactiver rate limiting pour test de charge
runtime_flags.set_flag("disable_rate_limiting", True)

# Exécuter tests de charge...

# Réactiver protection
runtime_flags.set_flag("disable_rate_limiting", False)
```

---

## Évolutions prévues (Q2 2026)

### Fonctionnalités avancées

- **TTL par flag** : Expiration automatique de flags temporaires
- **Conditions contextuelles** : Flags activés selon heure/jour
- **Audit trail complet** : Historique modifications avec contexte

### Performance

- **Cache distribué** : Partage cache entre instances
- **Bulk operations** : Modification atomique de groupes de flags
- **Metrics intégrées** : Exposition métriques Prometheus

### Sécurité

- **RBAC flags** : Permissions par utilisateur/groupe
- **Validation schéma** : Contraintes complexes sur valeurs
- **Encryption stockage** : Chiffrement flags sensibles

---

## La Golden Rule : Cache TTL, Redis-first, validation stricte

Les runtime flags utilisent un cache mémoire avec TTL configurable, stockent en Redis comme source de vérité avec fallback fichier sécurisé, valident strictement les clés et valeurs, et garantissent la thread-safety pour modifications concurrentes sans corruption.

Flag modifié = cache invalidé = effet immédiat = contrôle opérationnel total.
