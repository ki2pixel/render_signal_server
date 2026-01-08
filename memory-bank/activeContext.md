# Contexte Actif

## Objectif Actuel
Aucune tâche active.

## Dernière Tâche Terminée
Aucune tâche récente.

## Architecture Actuelle
- Backend Flask + services (ConfigService, RuntimeFlagsService, WebhookConfigService, AuthService, PollingConfigService, DeduplicationService, R2TransferService).
- Traitement e-mails via `email_processing/orchestrator.py`, poller IMAP singleton, offload R2 optionnel.
- Workers Cloudflare : `r2-fetch-worker` (fetch distant) et `r2-cleanup-worker` (auto-suppression 24h).
- Déploiement Render via image Docker (GHCR) déclenchée par GitHub Actions.

## Prochaines Étapes Potentielles
Aucune étape définie.

## Dernières Mises à Jour
Aucune mise à jour récente.
