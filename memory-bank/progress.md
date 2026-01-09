# Suivi de Progression

## Archives disponibles
Les périodes antérieures sont archivées dans `/memory-bank/archive/` :
- [progress_2025Q4.md](archive/progress_2025Q4.md) - Archives Q4 2025 (décembre 2025 et antérieur)

## Highlights 2025 Q4
- **Standardisation des environnements virtuels** (2025-12-21) : Documentation unifiée avec priorité à l'environnement partagé `/mnt/venv_ext4/venv_render_signal_server`.
- **Architecture orientée services** (2025-11-17) : 6 services déployés, 83/83 tests OK, couverture ~41.16%, statut Production Ready.
- **Absence Globale** (2025-11-21/24) : Refactoring terminologique et application stricte, 14/14 tests OK.
- **Stabilisation post-refactoring** (2025-11-18) : Correction 11 tests, consolidation logging/preferences, nettoyage app_render.py, refactoring email_processing.
- **Suppression fonctionnalité "Presence"** (2025-11-18) : Nettoyage complet UI + backend + tests.

---

## Politique d'archivage
Les périodes antérieures à 90 jours sont archivées dans `/memory-bank/archive/` par trimestre. Les entrées actuelles conservent uniquement le progrès récent. Voir les archives pour l'historique détaillé.

---

## Terminé
-   [2026-01-09 17:50] **Correction de la duplication dans webhook_links.json pour les liens R2**
    - Backend Python : mise à jour de `orchestrator.py` pour gérer le tuple `(r2_url, original_filename)` et propager `original_filename`
    - Filtrage des liens d'assets Dropbox (logos/avatars) dans `link_extraction.py`
    - PHP : suppression de la persistance de `email_id` et déduplication des entrées dans `JsonLogger.php`
    - Mise à jour des tests unitaires pour valider le nouveau schéma de données
    - Validation : 83/83 tests passants, couverture maintenue à ~41.16%
-   [2025-01-08 20:15] **Préservation du nom de fichier d'origine (Content-Disposition) pour les objets R2**
    - Worker `r2-fetch-worker` : extraction du nom source via `Content-Disposition`, sanitation, et écriture `httpMetadata.contentDisposition` + `customMetadata.originalFilename` lors de l'upload.
    - Objectif : télécharger le fichier offloadé avec son nom d'origine (ex: `61 Camille.zip`) au lieu d'un nom dérivé de la clé.
    - PHP backend: `JsonLogger` étendu pour persister `original_filename` dans `webhook_links.json`, pages de test mises à jour.
    - Commit: toutes les modifications commitées (commit 041cb4d).
-   [2026-01-08 19:05] **Worker R2 Fetch sécurisé (token) + tests PHP "vrai r2_url"**
    - Worker Cloudflare: authentification obligatoire via header `X-R2-FETCH-TOKEN`.
    - Backend Render: `R2TransferService` envoie le token (ENV `R2_FETCH_TOKEN`) et refuse l'offload si absent.
    - Tests: mise à jour `tests/test_r2_transfer_service.py` pour prendre en compte le token.
    - Pages PHP: ajout d'un mode "Offload via Worker" dans `test.php` et `test-direct.php`.
-   [2026-01-08 17:25] **Compatibilité R2 côté webhook PHP : persistance des paires `source_url`/`r2_url`**
    - `deployment/src/JsonLogger.php` étendu pour supporter l'écriture des paires R2 (en plus des entrées legacy `url`).
    - `deployment/src/WebhookHandler.php` mis à jour pour enregistrer les paires quand `delivery_links[*].r2_url` est présent.
    - `deployment/src/WebhookTestUtils.php` rendu compatible avec des fichiers `webhook_links.json` mixtes (legacy + R2).
-   [2026-01-08 14:10] **Correctif déploiement Render: NameError BASE_DIR**
    - Réordonnancement de `config/settings.py` pour définir `BASE_DIR` avant son usage dans `WEBHOOK_LINKS_FILE`
    - Validation locale: import `from config import settings` OK
-   [2026-01-08 13:47] **Amélioration des pages de test PHP pour compatibilité R2**
    - Audit et correction de `test-direct.php` et `test.php` pour faciliter les tests end-to-end d'offload R2
    - Ajout de diagnostics automatiques pour `webhook_links.json` (schéma, entrées legacy, comptage par provider)
    - Résolution de l'erreur de redéclaration de classe WebhookHandler par consolidation des helpers
    - Ajout de `getWebhookLinksSnapshot()` dans `WebhookHandler` pour snapshot des dernières entrées
    - Validation fonctionnelle des pages avec exemples utilisateur
-   [2026-01-08 12:45] **Correctif Dropbox `/scl/fo/` best-effort**
    - Suppression du skip backend (R2TransferService + orchestrator) pour laisser le Worker tenter l'offload
    - Timeout spécifique 120s pour dossiers Dropbox, normalisation stricte appliquée avant persistance `webhook_links.json`
    - Worker Cloudflare renforcé : User-Agent navigateur, fallback contrôlé vers `dl.dropboxusercontent.com` (hors `/scl/fo/`), validation ZIP (taille minimale + magic bytes `PK`) avant upload R2
    - Tests mis à jour (`tests/test_r2_transfer_service.py`) + documentation clarifiée (`docs/r2_dropbox_limitations.md`)
    - Curl manuel validé (265 MB ZIP téléchargé, logs Worker confirmés)
-   [2026-01-08 01:30] **Intégration Cloudflare R2 Offload terminée**
    - Service singleton `R2TransferService` avec normalisation Dropbox et persistance paires source/R2
    - Workers Cloudflare déployés : `r2-fetch-worker` (fetch + détection HTML) et `r2-cleanup-worker` (auto-suppression 24h)
    - Intégration orchestrator avec enrichissement payload webhook (`r2_url` optionnel)
    - Tests unitaires complets (422 lignes) et documentation (`docs/r2_offload.md`, `docs/r2_dropbox_limitations.md`)
    - Économie potentielle de ~$5/mois pour 50 GB transférés, limitation identifiée pour dossiers partagés Dropbox (fallback gracieux)
-   [2026-01-06 11:27] **Réduction de la dette historique des Memory Bank**
    - Mise en œuvre de la politique d'archivage pour decisionLog.md et progress.md
    - Création du dossier archive/ avec fichiers trimestriels
    - Consolidation des entrées redondantes en résumés thématiques
    - Réduction significative de la taille des fichiers principaux (>1000 lignes → <100 lignes)
    - Amélioration de la lisibilité et de la maintenabilité
-   [2026-01-07 11:10] **Pipeline Docker/Render industrialisé**
    - Ajout d'un `Dockerfile` standardisé (Gunicorn, variables GUNICORN\_*, logs stdout/stderr)
    - Nouveau workflow GitHub Actions `render-image.yml` (build+push GHCR, déclenchement Render via hook/API)
    - Documentation `docs/deploiement.md` enrichie (flux image-based, secrets requis, checklists)
    - Déploiement Render validé sur `render-signal-server-latest.onrender.com`, logs vérifiés

## En cours

Aucune tâche active.

## À faire

Aucune tâche active.
