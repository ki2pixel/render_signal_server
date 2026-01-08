# Journal des Décisions (Chronologie Inversée)
Ce document enregistre les décisions techniques et architecturales importantes prises au cours du projet.

## Archives disponibles
Les périodes antérieures sont archivées dans `/memory-bank/archive/` :
- [decisionLog_2025Q4.md](archive/decisionLog_2025Q4.md) - Archives Q4 2025 (décembre 2025 et antérieur)

## Highlights 2025 Q4
- **Standardisation des environnements virtuels** (2025-12-21) : Priorité à l'environnement partagé `/mnt/venv_ext4/venv_render_signal_server` avec alternative locale.
- **Architecture orientée services finalisée** (2025-11-17) : 6 services (ConfigService, RuntimeFlagsService, WebhookConfigService, AuthService, PollingConfigService, DeduplicationService) intégrés, 83/83 tests OK.
- **Absence Globale** (2025-11-21/24) : Refactoring terminologique "presence_pause" → "absence_pause" et application stricte avec garde de cycle.
- **Refactoring email_processing** (2025-11-18) : TypedDict, helpers extraits, types sécurisés, 282 tests OK.
- **Suppression fonctionnalité "Presence"** (2025-11-18) : Nettoyage complet du code obsolète.

---

## Politique d'archivage
Les périodes antérieures à 90 jours sont archivées dans `/memory-bank/archive/` par trimestre. Les entrées actuelles conservent uniquement les décisions récentes. Voir les archives pour l'historique détaillé.

---

## Entrées récentes (post-archives)

- **[2026-01-08 13:47:00] - Consolidation des helpers PHP pour les pages de test R2**
  - **Décision** : Résoudre l'erreur de redéclaration de classe WebhookHandler en consolidant la logique de diagnostic dans un seul fichier helper.
  - **Changements clés** :
    - Suppression des fichiers redondants (`webhook_test_utils.php` dans public_html et src).
    - Mise à jour de `deployment/src/WebhookTestUtils.php` pour contenir uniquement la fonction `loadWebhookLinksDiagnostics()`.
    - Ajout de diagnostics dans `test.php` et `test-direct.php` pour afficher l'état de `webhook_links.json`, y compris schéma, entrées legacy, et comptage par provider.
    - Ajout de `getWebhookLinksSnapshot()` dans `WebhookHandler` pour fournir les dernières entrées aux pages de test.
  - **Raisons** : Éviter les conflits d'inclusion PHP tout en permettant des tests end-to-end de l'offload R2.
  - **Impacts** : Pages de test fonctionnelles, diagnostics clairs pour valider la compatibilité R2, simplification de la maintenance.

- **[2026-01-08 12:45:00] - Passage en best-effort pour les dossiers Dropbox `/scl/fo/`**
  - **Décision** : Supprimer le skip backend des liens Dropbox `/scl/fo/` et renforcer le Worker Cloudflare pour tenter un offload best-effort avec garde-fous.
  - **Changements clés** :
    - `R2TransferService` et `email_processing/orchestrator.py` n’ignorent plus ces liens ; timeout augmenté à 120s, persistance toujours basée sur l’URL normalisée.
    - Worker `worker.js` : User-Agent navigateur, timeout 120s pour `/scl/fo/`, fallback `dl.dropboxusercontent.com` uniquement pour les liens non dossiers, validation ZIP stricte (Content-Length minimal + magic bytes `PK`) avant upload.
    - Documentation `docs/r2_dropbox_limitations.md` mise à jour pour expliquer l’approche best-effort et les raisons d’échec possibles.
  - **Raisons** : Les utilisateurs partagent majoritairement des dossiers Dropbox ; ignorer ces liens empêchait l’économie de bande passante et obligeait à télécharger depuis Render.
  - **Impacts** : Les liens `/scl/fo/` réussissent désormais quand Dropbox fournit un ZIP public (ex. test 265 MB validé). Les cas HTML/login échouent proprement sans stocker de prévisualisation, logs explicites et fallback vers le lien source toujours disponible.


- **[2026-01-08 01:30:00] - Intégration Cloudflare R2 Offload pour économiser la bande passante Render**
  - **Décision** : Implémenter un service R2TransferService et des Workers Cloudflare pour transférer automatiquement les fichiers volumineux (Dropbox, FromSmash, SwissTransfer) vers R2, supprimant la consommation de bande passante Render.
  - **Changements clés** :
    - Service singleton `services/r2_transfer_service.py` avec normalisation Dropbox, fetch distant, persistance paires source/R2 dans `webhook_links.json`.
    - Workers Cloudflare déployés : `worker.js` (fetch + détection HTML) et `cleanup.js` (auto-suppression 24h via métadonnées `expiresAt`).
    - Intégration orchestrator (`email_processing/orchestrator.py:645-698`) pour enrichir `delivery_links` avec `r2_url`.
    - Payload webhook enrichi avec champ optionnel `r2_url` (rétrocompatibilité maintenue).
    - Tests unitaires complets (`tests/test_r2_transfer_service.py`, 422 lignes) et documentation (`docs/r2_offload.md`, `docs/r2_dropbox_limitations.md`).
  - **Raisons** : Limiter la consommation de bande passante Render (100 GB gratuits) et réduire les coûts tout en maintenant la disponibilité des fichiers via CDN Cloudflare (bande passante sortante gratuite).
  - **Impacts** : Économie potentielle de ~$5/mois pour 50 GB transférés, auto-nettoyage R2 (économie 96% stockage), limitation identifiée pour dossiers partagés Dropbox (fallback gracieux).

- **[2026-01-07 16:45:00] - Authentification par magic link (usage unique + permanent)**
  - **Décision** : Introduire `MagicLinkService` et un flux d'authentification par liens pré-signés pour le dashboard, avec support des tokens one-shot (TTL configurable) et d'options permanentes révoquables.
  - **Changements clés** :
    - Nouveau service `services/magic_link_service.py`, stockage JSON (`MAGIC_LINK_TOKENS_FILE`) et signature HMAC (`FLASK_SECRET_KEY`).
    - Endpoint `/api/auth/magic-link`, intégration UI (`login.html`, `dashboard.html`, `static/dashboard.js`) avec génération/copie de lien et mode illimité.
    - Ajustements sécurité (single_use vs permanent, journaux, nettoyage auto) et documentation UI/sécurité.
  - **Raisons** : Simplifier l’accès admin récurrent tout en conservant une trace sécurisée des tokens et la possibilité d’expiration rapide.
  - **Impacts** : Amélioration UX login, nouveau besoin de surveiller les tokens permanents (révocation manuelle si fuite), couverture test à compléter.

- **[2026-01-06 11:27:00] - Réduction de la dette historique des Memory Bank**
  - **Décision** : Mettre en œuvre une politique d'archivage pour réduire la taille de `decisionLog.md` (>1000 lignes) et `progress.md` (~350 lignes) tout en conservant l'historique utile.
  - **Changements clés** :
    - Création du dossier `/memory-bank/archive/` avec fichiers trimestriels (`decisionLog_2025Q4.md`, `progress_2025Q4.md`)
    - Consolidation des entrées redondantes en résumés thématiques (Absence Globale, refactoring services)
    - Ajout de sections "Archives disponibles" et "Highlights 2025 Q4" dans les fichiers principaux
    - Déplacement des entrées antérieures à 2025-12-01 vers les archives
  - **Raisons** : Les fichiers devenaient difficiles à maintenir et contenaient beaucoup de redondances. L'archivage améliore la lisibilité tout en préservant l'historique.
  - **Impacts** : Fichiers principaux réduits à <100 lignes, historique préservé dans archives, politique de maintenance claire établie.

- **[2026-01-07 11:10:00] - Passage au déploiement par image Docker (GHCR → Render)**
  - **Décision** : Construire et publier l'application via un `Dockerfile` officiel et un workflow GitHub Actions poussant sur GHCR puis déclenchant Render (Deploy Hook ou API).
  - **Changements clés** :
    - Création d'un `Dockerfile` standardisé (Gunicorn, logs stdout/stderr, variables `GUNICORN_*`).
    - Nouveau workflow `.github/workflows/render-image.yml` (build/push, déclenchement Render, fallback API).
    - Mise à jour de `docs/deploiement.md` pour documenter le flux image-based.
  - **Raisons** : Réduire le temps de déploiement Render en réutilisant une image pré-buildée et fiabiliser la traçabilité des logs.
  - **Impacts** : Service Render migré vers `render-signal-server-latest.onrender.com`, pipeline reproductible, monitoring conservé.
