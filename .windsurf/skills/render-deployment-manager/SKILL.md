---
name: render-deployment-manager
description: Manage Render.com deployments for this repository using the built-in admin endpoints, ConfigService, and the active Render environment variables.
---

# Render Deployment Manager

## Objectif
Orchestrer les déploiements Render de `render_signal_server` en s'appuyant d'abord sur les primitives réellement présentes dans ce dépôt : `routes/api_admin.py`, `ConfigService` et les variables `RENDER_*`.

## Quand utiliser ce skill
- Vérification de la configuration Render exposée par `ConfigService.get_render_config()`
- Déclenchement d'un déploiement via `POST /api/deploy_application`
- Redémarrage applicatif via `POST /api/restart_server`
- Diagnostic des problèmes de déploiement ou de hook Render
- Vérification des variables d'environnement `RENDER_*`

## Pré-requis
- Variables `RENDER_API_KEY` + `RENDER_SERVICE_ID` si vous passez par l'API Render
- ou `RENDER_DEPLOY_HOOK_URL` si vous passez par le Deploy Hook
- Connaissance des fallbacks locaux `DEPLOY_CMD` et `RESTART_CMD`
- Accès authentifié au dashboard admin si vous utilisez les endpoints Flask

## Workflow de déploiement
1. **Valider la configuration active**
   - Inspecter `ConfigService.get_render_config()` ou les variables `RENDER_API_KEY`, `RENDER_SERVICE_ID`, `RENDER_DEPLOY_HOOK_URL`, `RENDER_DEPLOY_CLEAR_CACHE`.
   - Vérifier si le déploiement doit passer par hook, API Render ou fallback local.
2. **Déclencher le déploiement applicatif**
   - Utiliser `POST /api/deploy_application` pour laisser `routes/api_admin.py` choisir automatiquement la meilleure stratégie (Deploy Hook, API Render, puis fallback local).
3. **Redémarrer si nécessaire**
   - Utiliser `POST /api/restart_server` pour forcer un redémarrage applicatif lorsque le besoin n'est pas un déploiement complet.
4. **Suivre l'état**
   - Contrôler le retour JSON des endpoints admin (`success`, `message`, `deploy_id`, `status`).
   - Vérifier ensuite `/health` et les logs Render / applicatifs.
5. **Diagnostiquer les erreurs**
   - Vérifier les valeurs `RENDER_*`, les hooks invalident, puis les commandes `DEPLOY_CMD` / `RESTART_CMD` si le fallback local est utilisé.

## Points d'entrée réels du dépôt
- `routes/api_admin.py` : endpoints `/api/deploy_application` et `/api/restart_server`
- `services/config_service.py` : `get_render_config()` et `has_render_config()`
- `config/settings.py` : variables `RENDER_API_KEY`, `RENDER_SERVICE_ID`, `RENDER_DEPLOY_HOOK_URL`, `RENDER_DEPLOY_CLEAR_CACHE`

## Exemples d'usage courants
### Déclencher un déploiement via l'API admin
```bash
curl -X POST http://localhost:5000/api/deploy_application \
  -H 'Content-Type: application/json' \
  -b '<session-authentifiée>'
```

### Vérifier la configuration Render côté Python
```bash
python - <<'PY'
from services.config_service import ConfigService
print(ConfigService().get_render_config())
PY
```

## Ressources
- Documentation Render.com pour les hooks et l'API REST
- `routes/api_admin.py` pour la logique de déploiement effective de ce projet

## Bonnes pratiques
- Toujours vérifier les variables `RENDER_*` avant un déploiement
- Préférer `/api/deploy_application` pour rester aligné avec la logique métier du dépôt
- Monitorer `/health` et les logs après déclenchement
- Garder l'historique des déploiements pour rollback si nécessaire
- Ne pas exposer les clés API ou secrets dans les logs
