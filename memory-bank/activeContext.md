# Contexte Actif

## Tâches Terminées
- [2026-05-27] Synchronisation et mise à jour globale de la documentation (`docs/`) via `/docs-updater` : suppression des références obsolètes à `webhook_sender.py`, intégration des spécifications du fallback 415, documentation des optimisations de performance frontend (`JsonViewer` lazy rendering/chunking, `DOMHelper` data-target, `beforeunload`, et Vite), et correction de tous les liens internes `docs/v2/`.
- [2026-05-27] Investigation et correction des tests backend (`test_app_render.py`, `tests/test_r2_resilience.py`) échouant suite à la suppression du module `webhook_sender.py`.
- [2026-05-27] Implémentation de la prévention des pertes de données (interception beforeunload) pour les panneaux auto-save et manuels.
- [2026-05-27] Optimisation des performances du frontend (JsonViewer) avec Lazy Rendering sur les branches repliées et Chunking (100 éléments par tranche) pour prévenir les gels d'UI avec de gros payloads.
- [2026-05-27] Intégration d'un outil de Build/Bundling (Vite) pour regrouper et minifier les assets frontend, avec fallback auto en dev (dashboard.html, app_render.py).
- [2026-05-27] Découplage du DOM et des CSS pour le frontend (création de `DOMHelper.js` et injection de `data-target`).
- [2026-02-25] Tests de non-régression pour l’idempotence Gmail Push (double POST) + validation ciblée (28 tests OK).

## Questions Ouvertes
- Aucune question en attente.

## Prochaine Étape
- Aucune tâche active (session finalisée).
