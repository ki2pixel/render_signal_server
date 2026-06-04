---
name: sequentialthinking-logic
description: Expert en raisonnement décomposé. Force l'usage de sequentialthinking_tools pour valider la logique Flask, les orchestrateurs et les flux asynchrones Redis/Celery.
---

# Sequential Thinking Logic

> **Expertise** : Raisonnement décomposé, validation logique, analyse étape par étape, pensée structurée pour architectures complexes backend.

## Quick Start

### Mental Model

Sequential Thinking Logic décompose les problèmes complexes en séquences logiques validées :
- Analyse des Routes Flask vs Background Tasks
- Validation des flux de données via Redis (Config Store / Cache)
- Identification des points de défaillance (IngressService, Webhook Orchestrator)
- Construction de chaînes de raisonnement robustes

### Workflow obligatoire

1. **Décomposition** : Identifier les composants logiques principaux (API, Ingress, Async Task)
2. **Validation** : Utiliser `sequentialthinking_tools` (en passant l'action en paramètre) pour chaque étape
3. **Chaînage** : Connecter les étapes en une séquence cohérente
4. **Test logique** : Valider les hypothèses et points de rupture

### Patterns d'utilisation

#### Pour architecture Flask / Background

```bash
# Décomposer l'architecture
sequentialthinking_tools decompose "Ingestion Email: API <-> IngressService <-> Redis Deduplication"

# Valider chaque composant
sequentialthinking_tools validate "Flask route payload validation"
sequentialthinking_tools validate "IngressService singleton logic"
sequentialthinking_tools validate "Redis TTL hash deduplication"

# Tester la séquence complète
sequentialthinking_tools test-sequence "POST /api/ingress -> IngressService -> DeduplicationService -> Webhook"
```

#### Pour logique métier (Orchestrator)

```bash
# Analyser le flux métier
sequentialthinking_tools decompose "Webhook delivery flow"

# Valider chaque étape
sequentialthinking_tools validate "Load processing_prefs"
sequentialthinking_tools validate "Pattern matching (DESABO / Media Solution)"
sequentialthinking_tools validate "RateLimit & R2 offload"
sequentialthinking_tools validate "Error handling / Fallbacks"

# Identifier les points de rupture
sequentialthinking_tools find-breakpoints "webhook_flow"
```

## Production-safe patterns

### Validation systématique

Pour chaque composant logique :

```bash
# 1. Décomposition
sequentialthinking_tools decompose "[composant]"

# 2. Validation logique
sequentialthinking_tools validate "[sous-composant_1]"
sequentialthinking_tools validate "[sous-composant_2]"

# 3. Test de séquence
sequentialthinking_tools test-sequence "[flux_complet]"
```

### Route Handler vs Async Background

Pattern spécifique pour l'architecture serveur :

```bash
# Flask Route Logic
sequentialthinking_tools validate-route "payload_sanitization"
sequentialthinking_tools validate-route "auth_verification"
sequentialthinking_tools validate-route "response_formatting"

# Background / Orchestrator Logic
sequentialthinking_tools validate-async "redis_lock_acquisition"
sequentialthinking_tools validate-async "r2_transfer_resilience"
sequentialthinking_tools validate-async "webhook_retries"

# Route to Async communication
sequentialthinking_tools test-communication "Flask API <-> Background Service"
```

### Gestion des erreurs logiques

```bash
# Identifier les points de défaillance
sequentialthinking_tools find-breakpoints "[flux]"

# Analyser les cas limites
sequentialthinking_tools edge-cases "[composant]"

# Valider la gestion d'erreurs
sequentialthinking_tools validate-error-handling "[flux]"
```

## Common gotchas

### Séquences incomplètes

- Toujours valider le début ET la fin de chaque séquence
- Les points de décision doivent avoir tous les cas couverts (ex: HTTP 200 vs 400/409/500)
- Les processus idempotents doivent bien vérifier l'état avant d'agir

### Dépendances circulaires / Locks

```bash
# Détecter les circularités
sequentialthinking_tools detect-cycles "[services_singletons]"

# Résoudre les deadlocks
sequentialthinking_tools detect-deadlocks "[redis_locks]"
```

### Route/Async contamination

- Éviter de bloquer le thread principal Flask avec des appels distants lents (utiliser l'asynchronisme ou des timeouts courts)
- Isoler les communications réseau dans des try/except robustes
- Valider les contextes d'exécution séparément

## API Reference

> **ATTENTION** : Le seul outil disponible est `sequentialthinking_tools`. Les actions (`decompose`, `validate`, etc.) doivent être passées en paramètres de l'outil et non invoquées comme des outils distincts.

### Outil principal

- `sequentialthinking_tools` : Accepte des paramètres comme `action` et `target`.

### Actions disponibles (à passer en paramètre)

- `decompose` : Décompose en composants logiques
- `validate` : Valide la logique d'un composant
- `test-sequence` : Teste une séquence complète
- `find-breakpoints` : Identifie les points de rupture
- `edge-cases` : Analyse les cas limites
- `validate-route` : Validation des handlers Flask
- `validate-async` : Validation des tâches asynchrones / services
- `test-communication` : Test communication inter-couches
- `detect-cycles` : Détection dépendances circulaires
- `detect-deadlocks` : Détection des problèmes de locks

### Options avancées (paramètres supplémentaires)

- `depth` : Profondeur d'analyse (1-5)
- `verbose` : Sortie détaillée du raisonnement
- `export_logic` : Exporte le modèle logique
- `test_cases` : Génère cas de test automatiquement

## Debugging checklist

- Confirmer que chaque étape a une entrée ET une sortie
- Vérifier que les points de décision sont complets
- Tester les cas limites et erreurs
- Valider la gestion des timeouts et locks (Redis)
- Contrôler l'absence de dépendances circulaires entre Singletons

## When to use this skill

- **Architecture Backend** : Flask Routes, Singletons, Webhook Orchestrators
- **Logique métier complexe** : Flux multi-étapes avec validations (Deduplication, Rate Limit)
- **Systèmes distribués** : Communication API -> Redis -> R2
- **Validation de design** : Revue logique d'architectures asynchrones
- **Debugging logique** : Analyse de raisonnement défaillant

## Integration patterns

### Avec Shrimp Task Manager

Utilise après `analyze_task` pour valider la décomposition logique des tâches.

### Avec Redis Config Guardian

Utilise pour valider le flux de mise à jour des configs en cache avant persistance.