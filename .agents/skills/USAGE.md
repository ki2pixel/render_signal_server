# Guide d'Utilisation des Skills Kimi Code CLI

Ce guide explique comment utiliser les skills Kimi Code CLI dans le projet Render Signal Server.

## Utilisation des Skills

Dans Kimi Code CLI, vous pouvez utiliser les skills avec la syntaxe suivante :

### Format Général
```
/skill:[nom-du-skill] [arguments ou contexte]
```

### Exemples Concrets

#### 1. Terminer une session (`/skill:end`)
```bash
/skill:end
# Termine la session courante et synchronise la Memory Bank
```

#### 2. Améliorer un prompt (`/skill:enhance`)
```bash
/skill:enhance "Ajouter une nouvelle route pour les webhooks Gmail"
# Transforme la demande en spécification technique structurée
```

#### 3. Mettre à jour la documentation (`/skill:docs-updater`)
```bash
/skill:docs-updater "Documenter le nouveau système de routing des webhooks"
# Met à jour la documentation avec les standards techniques
```

#### 4. Planifier une tâche complexe (`/skill:enhance-complex`)
```bash
/skill:enhance-complex "Refactoriser le système d'authentification pour supporter OAuth2"
# Utilise Shrimp Task Manager pour planifier et orchestrer la tâche
```

#### 5. Committer et pusher (`/skill:commit-push`)
```bash
/skill:commit-push "feat: Ajout du support OAuth2 pour l'authentification"
# Exécute git add, commit avec message formaté, et push
```

#### 6. Standards de documentation (`/skill:documentation`)
```bash
/skill:documentation "Rédiger un guide d'architecture pour le nouveau module"
# Applique les standards de rédaction technique et structure les articles
```

## Scénarios d'Utilisation Typiques

### Développement d'une Nouvelle Fonctionnalité
1. Commencer avec `/skill:enhance` pour structurer la demande
2. Utiliser `/skill:enhance-complex` pour planifier l'implémentation
3. Développer le code
4. Utiliser `/skill:docs-updater` pour documenter la fonctionnalité
5. Terminer avec `/skill:commit-push` pour sauvegarder le travail
6. Clôturer avec `/skill:end` pour synchroniser la Memory Bank

### Maintenance et Refactoring
1. `/skill:enhance` pour comprendre la portée du refactoring
2. `/skill:enhance-complex` pour planifier les étapes
3. `/skill:commit-push` pour committer les changements par lots

### Mise à Jour de la Documentation
1. `/skill:docs-updater` pour évaluer l'état actuel
2. `/skill:documentation` pour appliquer les standards de rédaction
3. `/skill:commit-push` pour versionner les changements

## Intégration avec les Outils MCP

Les skills utilisent les serveurs MCP disponibles dans Kimi Code CLI :

### Fast Filesystem
- `fast_read_file` : Lecture de fichiers avec chemins absolus
- `fast_write_file` : Écriture de fichiers
- `fast_list_directory` : Listing de répertoires
- Utilisé pour accéder aux fichiers du projet et de la Memory Bank

### Shrimp Task Manager
- `plan_task` : Planification de tâches complexes
- `analyze_task` : Analyse technique approfondie
- `split_tasks` : Décomposition en sous-tâches
- `execute_task` : Exécution guidée de tâches
- Utilisé par `/skill:enhance-complex`

### Sequential Thinking
- `sequentialthinking_tools` : Raisonnement structuré
- Utilisé pour les analyses complexes

### JSON Query
- `json_query_jsonpath` : Requêtes JSON avancées
- Utilisé pour analyser les configurations

## Conventions et Bonnes Pratiques

### 1. Chemins Absolus
Toujours utiliser les chemins absolus pour référencer les fichiers :
```javascript
const context = await fast_read_file('/home/kidpixel/render_signal_server-main/memory-bank/activeContext.md');
```

### 2. Références aux Règles Locales
Chaque skill doit référencer les fichiers de règles du projet :
- `.clinerules/v5.md` (section 2 critique)
- `.clinerules/codingstandards.md`
- `.clinerules/memorybankprotocol.md`
- `AGENTS.md`

### 3. Respect du Protocole Memory Bank
- Lire d'abord avant d'écrire
- Minimiser les modifications
- Documenter les décisions avec contexte complet
- Synchroniser tous les fichiers pertinents

### 4. Format des Messages de Commit
Suivre strictement `.windsurf/rules/commit-message-format.md` :
```
feat: Ajouter support OAuth2
fix: Corriger bug d'authentification
refactor: Simplifier architecture des routes
docs: Documenter nouveau workflow
```

## Dépannage

### Skill Non Détecté
Vérifier que :
1. Le répertoire `.agents/skills/[nom]/` existe
2. Le fichier `SKILL.md` contient un frontmatter YAML valide
3. Le skill n'a pas d'erreurs de syntaxe

### Erreurs d'Exécution
1. Vérifier les références aux outils MCP
2. S'assurer que les chemins absolus sont corrects
3. Vérifier les permissions des fichiers

### Problèmes de Compatibilité
Les skills sont spécifiquement adaptés pour Kimi Code CLI et ne fonctionnent pas avec Windsurf.

## Migration Continue

Pour ajouter de nouveaux skills ou mettre à jour des skills existants :

1. Créer/modifier le répertoire dans `.agents/skills/[nom]/`
2. Ajouter un frontmatter YAML avec `name` et `description`
3. Référencer les outils MCP Kimi Code CLI
4. Tester le skill avec Kimi Code CLI
5. Mettre à jour `README.md` et `USAGE.md`

## Support

Pour toute question sur l'utilisation des skills, consulter :
1. La documentation Kimi Code CLI
2. Les règles locales du projet dans `.clinerules/`
3. Le fichier `AGENTS.md` pour le contexte du projet