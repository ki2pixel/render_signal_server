---
name: sequentialthinking-logic
description: Expert en raisonnement décomposé. Force l'usage de sequentialthinking_tools pour valider la logique Background/Content Script des extensions et architectures complexes.
---

# Sequential Thinking Logic

> **Expertise** : Raisonnement décomposé, validation logique, analyse étape par étape, pensée structurée pour architectures complexes.

## Quick Start

### Mental Model

Sequential Thinking Logic décompose les problèmes complexes en séquences logiques validées :
- Analyse Background Script vs Content Script
- Validation des flux de données
- Identification des points de défaillance
- Construction de chaînes de raisonnement robustes

### Workflow obligatoire

1. **Décomposition** : Identifier les composants logiques principaux
2. **Validation** : Utiliser `sequentialthinking_tools` (en passant l'action en paramètre) pour chaque étape
3. **Chaînage** : Connecter les étapes en une séquence cohérente
4. **Test logique** : Valider les hypothèses et points de rupture

### Patterns d'utilisation

#### Pour architecture d'extension

```bash
# Décomposer l'architecture
sequentialthinking_tools decompose "Extension Chrome: Background <-> Content <-> API"

# Valider chaque composant
sequentialthinking_tools validate "Background script logic"
sequentialthinking_tools validate "Content script injection"
sequentialthinking_tools validate "API communication flow"

# Tester la séquence complète
sequentialthinking_tools test-sequence "user_action -> background -> content -> api -> response"
```

#### Pour logique métier complexe

```bash
# Analyser le flux métier
sequentialthinking_tools decompose "User authentication flow"

# Valider chaque étape
sequentialthinking_tools validate "Input validation"
sequentialthinking_tools validate "Credential verification"
sequentialthinking_tools validate "Session management"
sequentialthinking_tools validate "Error handling"

# Identifier les points de rupture
sequentialthinking_tools find-breakpoints "auth_flow"
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

### Background vs Content Script

Pattern spécifique pour extensions web :

```bash
# Background Script Logic
sequentialthinking_tools validate-background "event_listeners"
sequentialthinking_tools validate-background "message_routing"
sequentialthinking_tools validate-background "storage_management"

# Content Script Logic
sequentialthinking_tools validate-content "dom_manipulation"
sequentialthinking_tools validate-content "user_interaction"
sequentialthinking_tools validate-content "message_communication"

# Cross-script communication
sequentialthinking_tools test-communication "background <-> content"
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
- Les points de décision doivent avoir tous les cas couverts
- Les boucles doivent avoir des conditions de sortie claires

### Dépendances circulaires

```bash
# Détecter les circularités
sequentialthinking_tools detect-cycles "[architecture]"

# Résoudre les dépendances
sequentialthinking_tools resolve-dependencies "[composants]"
```

### Background/Content contamination

- Éviter de mélanger logique UI et logique métier
- Isoler les communications entre scripts
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
- `validate-background` : Validation Background Script
- `validate-content` : Validation Content Script
- `test-communication` : Test communication inter-scripts
- `detect-cycles` : Détection dépendances circulaires
- `resolve-dependencies` : Résolution dépendances

### Options avancées (paramètres supplémentaires)

- `depth` : Profondeur d'analyse (1-5)
- `verbose` : Sortie détaillée du raisonnement
- `export_logic` : Exporte le modèle logique
- `test_cases` : Génère cas de test automatiquement

## Debugging checklist

- Confirmer que chaque étape a une entrée ET une sortie
- Vérifier que les points de décision sont complets
- Tester les cas limites et erreurs
- Valider les communications entre composants
- Contrôler l'absence de dépendances circulaires

## When to use this skill

- **Architecture d'extensions** : Chrome/Firefox Background/Content Scripts
- **Logique métier complexe** : Flux multi-étapes avec validations
- **Systèmes distribués** : Communication entre services
- **Algorithmes séquentiels** : Traitement par étapes
- **Validation de design** : Revue logique d'architectures
- **Debugging logique** : Analyse de raisonnement défaillant

## Integration patterns

### Avec Shrimp Task Manager

Utilise après `analyze_task` pour valider la décomposition logique des tâches.

### Avec Fast Filesystem

Utilise pour valider la logique avant les édition chirurgicales avec `edit_file`.

### Avec JSON Query

Utilise `json_query_query_json` pour extraire les structures logiques des fichiers de configuration avant validation.