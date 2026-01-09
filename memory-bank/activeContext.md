# Contexte Actif

## Objectif Actuel
Aucune tâche active.

## Dernière Tâche Terminée
**Correction de la duplication dans webhook_links.json pour les liens R2** (2026-01-09)
- Suppression de la persistance de `email_id` dans les entrées R2
- Ajout de la déduplication côté PHP pour éviter les doublons
- Filtrage des liens d'assets Dropbox (logos/avatars)
- Mise à jour complète des tests unitaires
- 83/83 tests passants, couverture maintenue à ~41.16%

## Architecture Actuelle
- Backend Flask + services (ConfigService, RuntimeFlagsService, WebhookConfigService, AuthService, PollingConfigService, DeduplicationService, R2TransferService).
- Traitement e-mails via `email_processing/orchestrator.py`, poller IMAP singleton, offload R2 optionnel.
- Workers Cloudflare : `r2-fetch-worker` (fetch distant) et `r2-cleanup-worker` (auto-suppression 24h).
- Déploiement Render via image Docker (GHCR) déclenchée par GitHub Actions.
- Schéma de persistance des liens R2 mis à jour : `{source_url, r2_url, provider, original_filename, created_at}`

## Prochaines Étapes Potentielles
- Surveillance des performances de l'offload R2 en production
- Audit de sécurité des workers Cloudflare
- Optimisation des requêtes IMAP pour réduire la charge serveur

## Dernières Mises à Jour
- [2026-01-09] Correction de la duplication dans `webhook_links.json`
- [2026-01-08] Ajout de la préservation du nom de fichier d'origine
- [2026-01-08] Sécurisation du worker R2 avec token d'authentification
