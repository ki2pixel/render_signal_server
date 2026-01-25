# Moteur de Règles de Routage Dynamique

## Vue d'ensemble

Le moteur de routage dynamique permet de configurer le traitement des emails via l'interface utilisateur plutôt que par code dur. Il remplace la logique "hardcodée" historique (DESABO vs RECADRAGE vs CUSTOM) par un système flexible de règles conditionnelles.

## Architecture

### Backend Service

**`RoutingRulesService`** (`services/routing_rules_service.py`)
- **Pattern** : Singleton avec cache TTL de 30s
- **Stockage** : Redis-first avec fallback fichier JSON (`debug/routing_rules.json`)
- **Validation** : Stricte avec normalisation des URLs et vérification des champs
- **Cache** : Mémoire avec invalidation automatique lors des mises à jour

```python
# Structure d'une règle
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

### API REST

**Endpoints** (`routes/api_routing_rules.py`)
- `GET /api/routing_rules` : Récupère la configuration complète
- `POST /api/routing_rules` : Met à jour les règles (validation + persistance)

**Sécurité**
- Authentification requise (`@login_required`)
- Validation stricte des payloads
- Messages d'erreur explicites pour le débogage

### Intégration Orchestrateur

**Évaluation des règles** (`email_processing/orchestrator.py`)
1. **Chargement dynamique** : `_get_routing_rules_payload()` lit depuis Redis/fichier
2. **Matching** : `_find_matching_routing_rule()` évalue les règles dans l'ordre
3. **Conditions** : `_match_routing_condition()` supporte `contains`, `equals`, `regex`
4. **Action** : Si une règle correspond, utilise son webhook et respecte `stop_processing`

**Ordre de priorité**
1. Règles de routage dynamique (si match)
2. Logique historique DESABO/Media Solution (fallback)
3. Webhook par défaut (settings)

### Règles de secours générées côté backend

Lorsque aucun jeu de règles personnalisé n'est encore configuré, l'API `/api/routing_rules` expose automatiquement trois règles "backend-*" générées par `_build_backend_fallback_rules()` pour reproduire les comportements historiques :

1. **Confirmation Mission Recadrage** : chaîne de conditions (subject regex + body regex) qui ciblent les emails "Média Solution". Le webhook utilisé est déduit de `webhook_config` (store Redis) et un filtre expéditeur optionnel est construit à partir de la allowlist provenant de `PollingConfigService` (`sender_of_interest_for_polling`).
2. **Confirmation Disponibilité Mission Recadrage (sujet/corps)** : deux variantes DESABO qui vérifient respectivement le sujet et le contenu du corps pour les mots-clés `désabonn`/`journee`/`tarifs habituels`. Chaque règle réutilise la même URL webhook et reste en `priority="normal"` sans `stop_processing` pour laisser passer les règles utilisateur plus spécifiques.

Ces règles apparaissent dans le payload retourné par `GET /api/routing_rules` tant que le store persistant ne contient pas d'entrées utilisateur, garantissant que la migration vers le moteur dynamique ne casse pas les flux Recadrage/DÉSABO existants. Elles sont construites dans `routes/api_routing_rules.py` à partir du webhook actif et des patterns calculés dynamiquement.@routes/api_routing_rules.py#32-195

## Frontend Interface

### Panneau Routage Dynamique

**Service ES6** (`static/services/RoutingRulesService.js`)
- **638 lignes** de code modulaire
- **Builder visuel** avec drag-and-drop
- **Auto-sauvegarde** intelligente (debounce 2-3s)
- **Validation temps réel** des URLs et formats

**Fonctionnalités**
- **Conditions multiples** : Expéditeur, sujet, corps
- **Opérateurs** : Contient, Égal, Regex
- **Actions** : Webhook cible, priorité, stop_processing
- **Réorganisation** : Glisser-déposer pour modifier l'ordre d'évaluation
- **Feedback visuel** : Indicateurs de statut et erreurs

### Validation

**Côté client**
- URLs HTTPS obligatoires ou tokens Make.com
- Champs obligatoires : nom, au moins une condition, webhook
- Formatage automatique des valeurs

**Côté serveur**
- Normalisation des URLs Make.com
- Validation des opérateurs et champs
- Protection contre les injections regex

## Configuration

### Variables d'environnement

Aucune variable spécifique requise. Le service utilise :
- `REDIS_URL` si disponible (mode Redis-first)
- `FLASK_SECRET_KEY` pour la sécurité (indirectement via app_config_store)

### Stockage

**Redis (recommandé)**
- Clé : `routing_rules`
- Format : JSON avec les règles et timestamp `_updated_at`
- Avantages : Multi-conteneurs, persistance redeploys

**Fichier fallback**
- Chemin : `debug/routing_rules.json`
- Création automatique si Redis indisponible
- Usage : Développement et environnements mono-conteneur

## Tests

### Couverture

**Service** (`tests/test_routing_rules_service.py`)
- 3 tests : succès, validation, rechargement

**API** (`tests/routes/test_api_routing_rules.py`)
- 3 tests : GET succès, POST succès, POST validation error

**Orchestrateur** (`tests/email_processing/test_routing_rules_orchestrator.py`)
- 6 tests : helpers + 2 E2E avec routing conditionnel

**Total** : 12 tests couvrant tous les scénarios critiques

### Exécution

```bash
# Tests spécifiques au routing
pytest -k "routing" -v

# Avec environnement partagé
/mnt/venv_ext4/venv_render_signal_server/bin/pytest -k "routing" -v
```

## Cas d'usage

### Exemple 1 : Factures clients

**Règle** : Router les factures vers un webhook dédié
```json
{
    "name": "Factures Client X",
    "conditions": [
        {"field": "sender", "operator": "contains", "value": "@clientx.com"},
        {"field": "subject", "operator": "contains", "value": "facture"}
    ],
    "actions": {
        "webhook_url": "https://hook.eu2.make.com/factures",
        "priority": "high",
        "stop_processing": true
    }
}
```

### Exemple 2 : Support urgent

**Règle** : Prioriser les emails de support urgent
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

## Limites et Bonnes Pratiques

### Limites actuelles
- **Performance** : Évaluation séquentielle (max ~50 règles recommandées)
- **Regex** : Validation basique, expressions complexes non recommandées
- **Debug** : Logs limités pour éviter l'exposition de données sensibles

### Bonnes pratiques
- **Ordre des règles** : Plus spécifique en premier
- **Noms explicites** : Facilitent la maintenance
- **Test progressif** : Valider avec emails de test
- **Backup** : Exporter la configuration régulièrement

## Évolutions futures

### Roadmap Q2 2026
- **Performance** : Indexation des règles pour grands volumes
- **Avancé** : Conditions temporelles (heures/jours)
- **UI** : Templates de règles prédéfinies
- **Debug** : Mode "dry-run" avec logs détaillés

### Améliorations continues
- **Import/Export** : Configuration entre environnements
- **Versioning** : Historique des changements de règles
- **Analytics** : Statistiques d'utilisation par règle

---

*Ce document décrit l'implémentation complète du moteur de routage dynamique. Pour les détails d'API, voir `docs/api.md`. Pour l'architecture générale, voir `docs/architecture/overview.md`.*
