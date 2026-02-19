---
description: Manage Render.com deployments and services using MCP tools for service creation, environment management, monitoring, and deployment orchestration.
globs:
  - "**/render-deployment-manager/**"
  - "**/Dockerfile"
  - "**/render-image.yml"
alwaysApply: false
---

# Render Deployment Manager

## Objectif
Orchestrer les déploiements et la gestion des services Render.com pour l'application render_signal_server, en utilisant les outils MCP Render pour des opérations directes et automatisées.

## Quand utiliser ce skill
- Création de nouveaux services Render (web services, cron jobs, Postgres, key-value stores)
- Gestion des déploiements et monitoring des métriques
- Mise à jour des variables d'environnement
- Gestion des statiques sites
- Diagnostic des problèmes de déploiement

## Pré-requis
- MCP `render-signal-mcp` configuré avec clé API valide
- Workspace Render sélectionné (`select_workspace`)
- Droits d'accès aux services Render appropriés
- Connaissance des spécifications de service (runtime, build commands, etc.)

## Workflow de déploiement
1. **Préparation du workspace**
   - `select_workspace` pour choisir le workspace approprié
   - `list_services` pour inventorier les services existants
2. **Création/Mise à jour de services**
   - `create_web_service` pour déployer l'application principale
   - `create_postgres` pour bases de données si nécessaire
   - `create_static_site` pour assets statiques
   - `update_web_service` pour modifications de configuration
3. **Configuration environnement**
   - `update_environment_variables` pour configurer les variables d'environnement
   - Validation des secrets et clés API
4. **Monitoring et diagnostic**
   - `get_metrics` pour surveiller CPU, mémoire, requêtes HTTP
   - `list_deploys` pour historique des déploiements
   - `get_service` pour statut détaillé des services
5. **Maintenance**
   - `get_deploy` pour détails spécifiques de déploiement
   - `list_logs` pour diagnostic des erreurs

## Outils MCP Render utilisés
- `select_workspace <id>` : Sélection du workspace de travail
- `create_web_service <config>` : Création service web (Python/Flask)
- `create_postgres <config>` : Création instance Postgres
- `create_static_site <config>` : Création site statique
- `update_environment_variables <service_id> <vars>` : Mise à jour ENV vars
- `get_metrics <service_id> <time_range>` : Métriques performance
- `list_deploys <service_id>` : Historique déploiements
- `get_service <service_id>` : Détails service
- `list_logs <filters>` : Logs filtrés par service/région

## Exemples d'usage courants
### Déploiement initial
```bash
# Sélection workspace
select_workspace "workspace_id"

# Création service web
create_web_service {
  "name": "render-signal-server",
  "repo": "https://github.com/user/render_signal_server",
  "branch": "main",
  "runtime": "python3",
  "buildCommand": "pip install -r requirements.txt",
  "startCommand": "python app_render.py"
}

# Configuration environnement
update_environment_variables "service_id" {
  "FLASK_SECRET_KEY": "secret",
  "REDIS_URL": "redis://...",
  "PROCESS_API_TOKEN": "token"
}
```

### Monitoring post-déploiement
```bash
# Vérification métriques
get_metrics "service_id" "1h"

# Vérification logs erreurs
list_logs {"service": "service_id", "status": "error"}
```

## Ressources
- Documentation Render.com pour spécifications détaillées
- Scripts de déploiement existants maintenus pour compatibilité

## Bonnes pratiques
- Toujours vérifier le workspace avant opérations
- Utiliser des noms de service descriptifs et cohérents
- Valider les variables d'environnement avant déploiement
- Monitorer les métriques après déploiement
- Garder l'historique des déploiements pour rollback si nécessaire
- Ne pas exposer les clés API ou secrets dans les logs
