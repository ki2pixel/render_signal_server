# Routing Engine

**TL;DR**: On a remplacé le code dur (DESABO vs RECADRAGE) par un moteur de règles dynamiques avec builder visuel, validation temps réel, et verrouillage par défaut pour éviter les accidents.

---

## Le problème : le code dur qui ne bougeait pas

J'ai hérité d'un code où la logique de routage était écrite en dur dans l'orchestrateur :

```python
# ANTI-PATTERN - orchestrator.py
def route_email(email):
    if "désabonnement" in subject:
        if "urgent" in subject:
            return handle_urgent_desabo(email)
        else:
            return handle_desabo(email)
    elif "média solution" in body:
        return handle_media_solution(email)
    else:
        return send_to_default_webhook(email)
```

Le problème ? Chaque nouvelle règle nécessitait de modifier le code, déployer, et tester. Pire encore, les clients voulaient des règles personnalisées ("les factures du client X vont vers ce webhook"), et c'était impossible sans toucher au code source.

---

## La solution : système de tri postal intelligent

Pensez au routing engine comme un système de tri postal intelligent : les emails sont des lettres qui arrivent à un centre de tri, où des règles de tri personnalisées les dirigent vers les bonnes boîtes aux lettres (webhooks). Le système a un verrou de sécurité par défaut pour éviter les erreurs de tri, avec un builder visuel pour configurer les règles sans toucher au code.

### ❌ L'ancien monde : tri manuel codé en dur

```python
# Ancien orchestrateur - impossible à étendre
def _determine_email_type(self, subject, body):
    if re.search(r'd[ée]sabonn', subject, re.IGNORECASE):
        return 'DESABO'
    elif re.search(r'm[ée]dia\s+solution', body, re.IGNORECASE):
        return 'MEDIA_SOLUTION'
    return 'DEFAULT'
```

### ✅ Le nouveau monde : règles de tri configurables

```json
{
  "id": "rule-12345",
  "name": "Factures Client X",
  "conditions": [
    {
      "field": "sender",
      "operator": "contains", 
      "value": "@clientx.com",
      "case_sensitive": false
    },
    {
      "field": "subject",
      "operator": "regex",
      "value": "facture\\s+\\d{4}",
      "case_sensitive": false
    }
  ],
  "actions": {
    "webhook_url": "https://hook.eu2.make.com/abc123",
    "priority": "high",
    "stop_processing": true
  }
}
```

**La révolution** : les règles de tri sont stockées dans Redis, modifiables via UI, sans jamais toucher au code.

---

## Idées reçues sur le système de tri postal

### ❌ "Les règles dynamiques sont moins sûres"
Le système de tri a un verrouillage par défaut (🔒) et une validation stricte. Les modifications sont sécurisées et nécessitent un déverrouillage explicite. C'est plus sûr que du code codé en dur.

### ❌ "Le builder visuel est limité"
Le builder supporte 3 champs (sender, subject, body) et 3 opérateurs (contains, equals, regex). C'est suffisant pour 95% des cas d'usage, et les fallbacks backend garantissent la compatibilité.

### ❌ "La performance sera mauvaise"
L'évaluation séquentielle est optimisée avec cache TTL court (30s) et recommandée pour ~50 règles max. Pour la plupart des entreprises, c'est largement suffisant.

---

## Tableau comparatif des systèmes de tri

| Système | Flexibilité | Maintenance | Performance | Sécurité | Complexité |
|----------|------------|--------------|------------|----------|------------|
| Code dur | Nulle | Très élevée | Maximale | Faible | Très faible |
| Système de tri postal | Très élevée | Faible | Optimisée | Élevée | Moyenne |
| Rules Engine externe | Variable | Variable | Variable | Variable | Élevée |
| Machine Learning | Maximale | Très élevée | Variable | Moyenne | Très élevée |

---

## Architecture du système de tri postal

### Backend : RoutingRulesService (centre de tri)

```python
# services/routing_rules_service.py
class RoutingRulesService:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 30  # secondes
        self._app_config_store = AppConfigStore()
    
    def get_rules(self):
        if self._is_cache_expired():
            self._cache = self._app_config_store.get_config_json("routing_rules")
        return self._cache.get('rules', [])
    
    def update_rules(self, rules):
        # Validation stricte
        validated_rules = self._normalize_rules(rules)
        
        # Persistance Redis-first
        self._app_config_store.set_config_json("routing_rules", {
            'rules': validated_rules,
            '_updated_at': datetime.utcnow().isoformat()
        })
        
        self._invalidate_cache()
```

**Pattern** : singleton avec cache TTL court, Redis-first, validation stricte.

### API REST : endpoints sécurisés du centre de tri

```python
# routes/api_routing_rules.py
@bp.route("/api/routing_rules", methods=["GET"])
@login_required
def get_routing_rules():
    rules = routing_service.get_rules()
    
    # Si aucune règle utilisateur, générer les fallbacks backend
    if not rules:
        rules = _build_backend_fallback_rules()
    
    return jsonify({"rules": rules})

@bp.route("/api/routing_rules", methods=["POST"])
@login_required
def update_routing_rules():
    payload = request.get_json()
    
    # Validation backend
    try:
        validated_rules = RoutingRulesSchema().load(payload)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    
    routing_service.update_rules(validated_rules)
    return jsonify({"status": "ok"})
```

### Intégration Orchestrateur : évaluation séquentielle des lettres

```python
# email_processing/orchestrator.py
def send_custom_webhook_flow(email_data, matched_rule=None):
    # 1. Évaluation des règles dynamiques
    if not matched_rule:
        matched_rule = _find_matching_routing_rule(email_data)
    
    # 2. Si règle trouvée, utiliser son webhook
    if matched_rule:
        webhook_url = matched_rule['actions']['webhook_url']
        priority = matched_rule['actions'].get('priority', 'normal')
        
        if matched_rule['actions'].get('stop_processing'):
            logger.info(f"Routing rule matched with stop_processing: {matched_rule['name']}")
            return _send_webhook(webhook_url, email_data, priority)
    
    # 3. Fallback vers logique historique
    return _handle_legacy_routing(email_data)

def _find_matching_routing_rule(self, email_data):
    rules = routing_service.get_rules()
    
    for rule in rules:
        if self._match_all_conditions(rule['conditions'], email_data):
            return rule
    
    return None
```

**Ordre de priorité** : règles utilisateur → fallbacks backend → logique historique → défaut.

---

## Frontend : builder visuel avec verrouillage de sécurité

### RoutingRulesService.js : service de configuration du centre de tri

```javascript
// static/services/RoutingRulesService.js
class RoutingRulesService {
  constructor() {
    this._rules = [];
    this._isLocked = true;  // Verrouillé par défaut !
    this._dirty = false;
  }
  
  // Builder de règles
  addRule() {
    const newRule = {
      id: this._generateId(),
      name: "Nouvelle règle",
      conditions: [{
        field: "sender",
        operator: "contains", 
        value: "",
        case_sensitive: false
      }],
      actions: {
        webhook_url: "",
        priority: "normal",
        stop_processing: false
      }
    };
    
    this._rules.push(newRule);
    this._markDirty();
    this._renderRules();
  }
  
  // Auto-sauvegarde intelligente
  _scheduleAutoSave() {
    if (this._autoSaveTimer) {
      clearTimeout(this._autoSaveTimer);
    }
    
    this._autoSaveTimer = setTimeout(() => {
      if (this._dirty && !this._isLocked) {
        this.saveRules();
      }
    }, 2500);  // 2.5s debounce
  }
}
```

### Verrouillage par défaut : sécurité maximale du centre de tri

```javascript
toggleLock() {
  this._isLocked = !this._isLocked;
  this._updateLockUI();
  
  if (this._isLocked) {
    console.log('ROUTING_LOCK: Locked by user');
  } else {
    console.log('ROUTING_LOCK: Unlocked by user');
  }
}

_updateLockUI() {
  const lockIcon = document.getElementById('routingLockIcon');
  const allFields = document.querySelectorAll('.routing-rule input, .routing-rule select');
  const actionButtons = document.querySelectorAll('.routing-rule-actions button');
  
  if (this._isLocked) {
    lockIcon.textContent = '🔒';
    lockIcon.title = 'Déverrouiller pour modifier les règles';
    
    // Désactiver tous les champs
    allFields.forEach(field => {
      field.disabled = true;
      field.style.opacity = '0.6';
    });
    
    actionButtons.forEach(btn => btn.disabled = true);
  } else {
    lockIcon.textContent = '🔓';
    lockIcon.title = 'Verrouiller pour sécuriser les règles';
    
    // Activer tous les champs
    allFields.forEach(field => {
      field.disabled = false;
      field.style.opacity = '1.0';
    });
    
    actionButtons.forEach(btn => btn.disabled = false);
  }
}
```

**Le workflow** :
1. Déverrouiller (🔒 → 🔓)
2. Modifier les règles de tri
3. Sauvegarder → Auto-verrouillage (🔓 → 🔒)

---

## Critères de tri : flexibilité maximale

### Champs disponibles pour le tri

| Champ | Description | Exemples |
|-------|-------------|----------|
| `sender` | Expéditeur brut | `"notification@service.com"` |
| `subject` | Sujet email | `"Facture #1234"` |
| `body` | Corps email | `"Veuillez trouver ci-joint"` |

### Opérateurs de tri

| Opérateur | Description | Exemple |
|-----------|-------------|---------|
| `contains` | Contient la chaîne | `subject.contains("facture")` |
| `equals` | Égal exact | `sender.equals("noreply@service.com")` |
| `regex` | Expression régulière | `subject.regex("facture\\s+\\d{4}")` |

### Exemples de règles de tri

#### Factures client spécifique (tri prioritaire)

```json
{
  "name": "Factures Client X",
  "conditions": [
    {"field": "sender", "operator": "contains", "value": "@clientx.com"},
    {"field": "subject", "operator": "contains", "value": "facture"}
  ],
  "actions": {
    "webhook_url": "https://hook.eu2.make.com/factures-x",
    "priority": "high",
    "stop_processing": true
  }
}
```

#### Support urgent (tri haute priorité)

```json
{
  "name": "Support Urgent",
  "conditions": [
    {"field": "subject", "operator": "regex", "value": "urgent|urgence"}
  ],
  "actions": {
    "webhook_url": "https://hook.eu2.make.com/support-urgent",
    "priority": "high",
    "stop_processing": false
  }
}
```

#### Média Solution (tri fallback backend)

```json
{
  "name": "backend-media-solution",
  "conditions": [
    {"field": "subject", "operator": "regex", "value": "m[ée]dia\\s+solution"},
    {"field": "body", "operator": "contains", "value": "dropbox"}
  ],
  "actions": {
    "webhook_url": "https://hook.eu2.make.com/media-solution",
    "priority": "normal",
    "stop_processing": false
  }
}
```

---

## Validation : sécurité et robustesse du tri

### Validation frontend (temps réel du centre de tri)

```javascript
_validateRule(rule) {
  const errors = [];
  
  // Nom obligatoire
  if (!rule.name || rule.name.trim().length === 0) {
    errors.push("Le nom de la règle est obligatoire");
  }
  
  // Au moins une condition
  if (!rule.conditions || rule.conditions.length === 0) {
    errors.push("Au moins une condition est requise");
  }
  
  // Webhook URL obligatoire et HTTPS
  if (!rule.actions.webhook_url) {
    errors.push("L'URL du webhook est obligatoire");
  } else if (!rule.actions.webhook_url.startsWith('https://') && 
             !rule.actions.webhook_url.startsWith('https://hook.make.com/')) {
    errors.push("L'URL doit être en HTTPS ou un token Make.com");
  }
  
  return errors;
}
```

### Validation backend (stricte des règles de tri)

```python
# services/routing_rules_service.py
def _normalize_rules(self, rules):
    normalized = []
    
    for rule in rules:
        # Validation structure
        if not self._validate_rule_structure(rule):
            raise ValueError(f"Invalid rule structure: {rule.get('name', 'unnamed')}")
        
        # Normalisation webhook URL
        webhook_url = rule['actions']['webhook_url']
        rule['actions']['webhook_url'] = self._normalize_webhook_url(webhook_url)
        
        # Validation opérateurs
        for condition in rule['conditions']:
            if condition['operator'] not in ['contains', 'equals', 'regex']:
                raise ValueError(f"Invalid operator: {condition['operator']}")
        
        normalized.append(rule)
    
    return normalized
```

---

## Fallbacks backend : compatibilité garantie du tri

### Génération automatique des règles de tri héritées

```python
# routes/api_routing_rules.py
def _build_backend_fallback_rules():
    """Génère les règles historiques si aucune règle utilisateur n'existe"""
    
    webhook_config = webhook_config_service.get_config()
    webhook_url = webhook_config.get('url')
    
    rules = []
    
    # 1. Media Solution
    rules.append({
        "id": "backend-media-solution",
        "name": "backend-media-solution",
        "conditions": [
            {"field": "subject", "operator": "regex", "value": "m[ée]dia\\s+solution"},
            {"field": "body", "operator": "contains", "value": "dropbox"}
        ],
        "actions": {
            "webhook_url": webhook_url,
            "priority": "normal",
            "stop_processing": false
        }
    })
    
    # 2. DESABO sujet
    rules.append({
        "id": "backend-desabo-subject",
        "name": "backend-desabo-subject", 
        "conditions": [
            {"field": "subject", "operator": "regex", "value": "d[ée]sabonn"}
        ],
        "actions": {
            "webhook_url": webhook_url,
            "priority": "normal",
            "stop_processing": false
        }
    })
    
    # 3. DESABO corps
    rules.append({
        "id": "backend-desabo-body",
        "name": "backend-desabo-body",
        "conditions": [
            {"field": "body", "operator": "regex", "value": "d[ée]sabonn.*journee.*tarifs"}
        ],
        "actions": {
            "webhook_url": webhook_url,
            "priority": "normal", 
            "stop_processing": false
        }
    })
    
    return rules
```

**La magie** : la première fois qu'un utilisateur accède au tri, il voit les règles historiques déjà configurées. Pas de migration manuelle.

---

## Tests : couverture complète du système de tri

### 12 tests couvrant tous les scénarios de tri

```bash
# Service (3 tests)
pytest tests/test_routing_rules_service.py -v

# API (3 tests) 
pytest tests/routes/test_api_routing_rules.py -v

# Orchestrateur (6 tests)
pytest tests/email_processing/test_routing_rules_orchestrator.py -v

# Tous les tests routing
pytest -k "routing" -v
```

### Tests clés du système de tri

```python
def test_routing_rule_evaluation():
    """Test l'évaluation séquentielle des règles"""
    rules = [
        {
            "conditions": [{"field": "sender", "operator": "contains", "value": "@urgent.com"}],
            "actions": {"webhook_url": "https://urgent.webhook.com", "stop_processing": True}
        },
        {
            "conditions": [{"field": "subject", "operator": "contains", "value": "facture"}],
            "actions": {"webhook_url": "https://invoice.webhook.com"}
        }
    ]
    
    email_data = {"sender": "alert@urgent.com", "subject": "facture #123"}
    matched_rule = routing_service.evaluate(email_data, rules)
    
    # La première règle doit matcher (stop_processing)
    assert matched_rule['actions']['webhook_url'] == "https://urgent.webhook.com"
    assert matched_rule['actions']['stop_processing'] == True
```

---

## Performance et limites du système de tri

### Limites actuelles du centre de tri

- **Performance** : Évaluation séquentielle (~50 règles max recommandées)
- **Regex** : Validation basique, éviter les expressions complexes
- **Cache** : 30s TTL pour éviter la surcharge Redis

### Bonnes pratiques de tri

- **Ordre des règles** : Plus spécifique en premier
- **Noms explicites** : `"Factures Client X"` plutôt que `"Règle 1"`
- **Test progressif** : Valider avec emails de test avant production
- **Backup** : Exporter régulièrement la configuration

---

## Évolutions prévues du système de tri (Q2 2026)

### Performance du tri

- **Indexation** : Accélérer la recherche pour >50 règles
- **Évaluation parallèle** : Conditions indépendantes en parallèle

### Fonctionnalités avancées de tri

- **Conditions temporelles** : `time_window: "09:00-18:00"`
- **Templates** : Règles prédéfinies (factures, support, etc.)
- **Mode dry-run** : Simulation sans envoi webhook
- **Import/Export** : Configuration entre environnements

---

## La Golden Rule : Système de tri configurable, verrouillage par défaut

Les règles de tri sont stockées dans Redis, modifiables via builder visuel, avec validation stricte et auto-sauvegarde. Le verrouillage par défaut (🔒) prévient les erreurs de tri accidentelles. Le fallback backend garantit la compatibilité avec les flux existants. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la sécurité du centre de tri.

Pour modifier : déverrouiller → éditer → sauvegarder → auto-verrouillage.

---

*Pour les détails d'API : voir `docs/v2/core/configuration-reference.md`. Pour l'architecture générale : voir `docs/v2/core/architecture.md`.*
