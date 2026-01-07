# Contexte Actif

## Objectif Actuel
En attente de nouvelles instructions.

## Dernière Tâche Terminée
- [2026-01-07 11:10] Pipeline Docker/Render industrialisé (image GHCR, workflow GitHub Actions, docs déploiement).

## Architecture Actuelle
- Backend Flask + services (ConfigService, RuntimeFlagsService, WebhookConfigService, AuthService, PollingConfigService, DeduplicationService).
- Traitement e-mails via `email_processing/orchestrator.py`, poller IMAP singleton.
- Déploiement Render via image Docker (GHCR) déclenchée par GitHub Actions.

## Prochaines Étapes Potentielles
- Mettre à jour les moniteurs externes vers la nouvelle URL Render.
- Vérifier/mettre à jour la clé MAKE.com (scénarios 401).
- Continuer la surveillance des logs BG_POLLER / webhook.

## Dernières Mises à Jour
- [2026-01-07 11:10] Migration déploiement Render vers image Docker + GHCR.
- [2025-12-21 14:36] Standardisation des environnements virtuels (venv partagé).
