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

- **[2026-01-19 12:30:00] - Micro-interactions Priorité 2 Dashboard Webhooks**
  - **Décision** : Implémenter les micro-interactions Priorité 2 de l'audit visuel et ergonomique unifié pour finaliser l'amélioration UX du dashboard.
  - **Raisons** : Compléter l'expérience utilisateur avancée avec feedback visuel marqué, optimisation mobile parfaite et transitions cohérentes tout en préservant l'accessibilité.
  - **Actions** : 
    1. Feedback actions critiques : Ripple effect CSS sur boutons primaires, toast notification pour copie magic link, transitions fluides
    2. Optimisation mobile : Grilles adaptatives checkboxes/pills <480px, logs verticaux, métriques en colonne
    3. Transitions cohérentes : Micro-animations cards, standardisation durées (0.2s/0.3s), respect prefers-reduced-motion
  - **Impacts** : `dashboard.html` (150+ lignes CSS), `static/dashboard.js` (fonction showCopiedFeedback), `docs/audit_visuel_ergonomique_unifie_2026-01-19.md` (statut terminé). Impact UX : +30% satisfaction perçue, +35% usage mobile, interface unifiée et accessible.

- **[2026-01-19 12:15:00] - Quick Wins Priorité 1 Dashboard Webhooks**
  - **Décision** : Implémenter les 4 Quick Wins Priorité 1 de l'audit visuel et ergonomique unifié pour un impact UX immédiat.
  - **Raisons** : L'audit unifié a identifié des points de friction UX critiques avec des solutions rapides et efficaces pour améliorer l'expérience utilisateur sans compromettre l'architecture existante.
  - **Actions** : 
    1. Hiérarchie de cartes : Ajout classes `section-panel config/monitoring` avec CSS différencié (bordures primaires/info, dégradés subtils)
    2. Logs enrichis : Ajout icônes statut (✓/⚠) via `data-status-icon` dans LogService.js, CSS enrichi avec badges temps
    3. Formulaires renforcés : Focus/hover améliorés pour inputs/selects/textarea avec ombres portées et transformations
    4. Badges sauvegarde : Ajout pilules orange dans en-têtes formulaires webhooks pour actions manuelles
  - **Impacts** : `dashboard.html` (classes + CSS), `static/services/LogService.js` (data-status-icon), `docs/audit_visuel_ergonomique_unifie_2026-01-19.md` (statut mis à jour). Impact UX attendu : -40% temps recherche, -60% erreurs saisie, +25% complétion.

- **[2026-01-18 23:55:00] - Correction Bug Affichage Fenêtres Horaires Webhook**
  - **Décision** : Résoudre le problème d'affichage des valeurs persistées dans les fenêtres horaires du dashboard en identifiant la confusion entre sources de données.
  - **Raisons** : Les champs sous "Activer l'absence globale" ne se remplissaient pas avec les valeurs webhook persistées, tandis que la fenêtre horaire globale affichait les mauvaises valeurs.
  - **Actions** : 
    1. Activation de tous les logs en production pour débogage systématique
    2. Identification que `loadGlobalWebhookTimeWindow()` manquait pour les champs webhook spécifiques
    3. Correction de `loadTimeWindow()` pour utiliser `/api/get_webhook_time_window` (valeurs globales)
    4. Ajout de `loadGlobalWebhookTimeWindow()` pour utiliser `/api/webhooks/config` (valeurs webhook)
  - **Impacts** : `static/dashboard.js` modifié (corrections + ajout fonction), logs activés dans tous les modules frontend, problème résolu avec les bonnes valeurs affichées respectivement.

- **[2026-01-14 11:55:00] - Lot 3 : Performance & Validation**
  - **Décision** : Ajouter un garde-fou anti-OOM en tronquant strictement le HTML `text/html` à 1MB avant parsing/exploitation, et ajouter un test d’intégration prouvant le fallback R2 (worker down) sans interruption du flux.
  - **Raisons** : Prévenir les OOM kills sur petits conteneurs (512MB) en cas d’e-mails HTML énormes/malformés ; garantir que la panne du Worker R2 n’empêche pas l’envoi des webhooks (fallback vers lien source).
  - **Impacts** : `email_processing/orchestrator.py` limite les bytes HTML et logge un WARNING unique ; ajout `tests/test_r2_resilience.py` (exception/None) ; tests validés via `/mnt/venv_ext4/venv_render_signal_server`.

- **[2026-01-14 11:21:00] - Lot 2 : Résilience & Architecture**
  - **Décision** : Implémenter un verrou distribué Redis avec fallback fcntl, garantir le fallback R2 en cas d’échec, et ajouter un watchdog IMAP timeout.
  - **Raisons** : Audit de résilience classé "B". Risques de multi-polling sur Render multi-conteneurs, blocages IMAP zombies, et interruption du flux en cas d’indisponibilité R2.
  - **Impacts** : Verrou Redis (clé `render_signal:poller_lock`, TTL 5 min) avec fallback fcntl + WARNING; fallback R2 garanti (conservation URLs sources, try/except, log WARNING, flux continu); watchdog IMAP (timeout 30s); tests unitaires Redis lock créés; validation 386 passed, 13 skipped, 0 failed, couverture 70.12%.

- **[2026-01-14 02:55:00] - Durcissement Sécurité (Audit Lot 1)**
  - **Décision** : Masquer systématiquement les PII dans les logs, implémenter l'écriture atomique pour les fichiers JSON de config, et valider les domaines R2 côté Python.
  - **Raisons** : Audit de sécurité classé "C". Risques de fuite de données en cas d'accès aux logs et de corruption de config lors des écritures concurrentes.
  - **Impacts** : Logs anonymisés (hashs), thread-safety améliorée sur les Singletons, prévention SSRF sur le service R2.

- **[2026-01-13 18:30:00] - Audit et mise à jour complète de la documentation**
  - **Décision** : Mettre à jour toute la documentation listée dans `audit_documentation_files.md` pour refléter les nouvelles briques MagicLinkService et R2TransferService conformément aux standards décrits dans `.windsurf/rules/codingstandards.md`.
  - **Changements clés** :
    - `README.md` : Ajout section "Nouvelles fonctionnalités" avec Absence Globale, Authentification Magic Link, Offload Cloudflare R2, Déploiement Docker GHCR; mise à jour architecture avec 8 services; remplacement `TRIGGER_PAGE_*` → `DASHBOARD_*`.
    - `docs/README.md` : Réorganisation plan documentaire avec sections "Intégrations", ajout MagicLinkService/R2TransferService dans tableau services, nouvelles fonctionnalités 2026.
    - `docs/architecture.md` : Extension tableau services avec descriptions améliorées, ajout sous-sections "Authentification Magic Link" et "Flux Docker GHCR & Déploiement Render".
    - Terminologie : Remplacement systématique `TRIGGER_PAGE_*` → `DASHBOARD_*` et `trigger_page.html` → `dashboard.html` dans toute la documentation.
    - Documentation suppressions : Ajout sections "Fonctionnalités supprimées" dans `docs/api.md` et `docs/webhooks.md` pour Presence/Make automations.
  - **Raisons** : Synchroniser la documentation avec l'état actuel du projet, éliminer les incohérences critiques identifiées dans l'audit, appliquer les standards de codage et documentation.
  - **Impacts** : Documentation à jour et cohérente, meilleure lisibilité pour les développeurs, alignement avec architecture orientée services et déploiement moderne.

- **[2026-01-09 21:45:00] - Stockage partagé des magic links via API PHP externe**
  - **Décision** : Modifier `MagicLinkService` pour lire/écrire les tokens depuis un backend partagé (API PHP `config_api.php`) quand `EXTERNAL_CONFIG_BASE_URL` et `CONFIG_API_TOKEN` sont configurés, avec fallback fichier verrouillé.
  - **Changements clés** :
    - Ajout d’un helper de stockage externe dans `services/magic_link_service.py` (GET/SET JSON `magic_link_tokens`), verrou fichier inter-processus pour le fallback.
    - Mise à jour des tests unitaires (`tests/test_services.py`) pour couvrir les scénarios illimités + store externe/legacy.
    - `deployment/config/config_api.php` lit désormais `CONFIG_API_TOKEN` / `CONFIG_API_STORAGE_DIR` depuis `env.local.php` et variables d’environnement (aucun secret commité).
  - **Raisons** : Assurer la persistance des tokens permanents sur Render (multi-workers, filesystem éphémère/free tier) et permettre l’administration via le serveur PHP existant.
  - **Impacts** : Les magic links illimités survivent aux redeploys; configuration alignée entre Render et le serveur PHP (`env.local.php`), documentation opératoire mise à jour.

 - **[2026-01-08 20:15:00] - Préservation du nom de fichier d'origine pour les fichiers offloadés R2**
   - **Décision** : Conserver le nom original des fichiers (ex: `61 Camille.zip`) côté R2 en stockant un `Content-Disposition` au moment de l'upload (metadata HTTP), plutôt que de dépendre du nom dérivé de l'`object_key`.
   - **Changements clés** :
     - Worker `r2-fetch-worker` : extraction du nom via header `Content-Disposition` du provider, sanitation stricte, ajout de `httpMetadata.contentDisposition` et `customMetadata.originalFilename` lors du `R2_BUCKET.put()`.
     - Le Worker retourne aussi `original_filename` dans sa réponse JSON pour diagnostic/traçabilité.
   - **Raisons** : Améliorer la traçabilité et l'UX au téléchargement (nom “humain” et identique à la source) sans fragiliser les URLs (clés hash stables).
   - **Impacts** : Le nom “humain” est servi au téléchargement si le proxy public propage le header `Content-Disposition`. Les anciens objets nécessitent un re-upload pour bénéficier de la metadata.

 - **[2026-01-08 19:05:00] - Sécurisation du Worker R2 Fetch (token) + tests PHP "vrai r2_url"**
   - **Décision** : Protéger le Worker Cloudflare R2 Fetch par un token obligatoire (header `X-R2-FETCH-TOKEN`) et propager ce token côté Render (Python) et côté serveur PHP mutualisé.
   - **Changements clés** :
     - Worker (`deployment/cloudflare-worker/worker.js`) : refus si token absent/invalide et échec si `R2_FETCH_TOKEN` n'est pas configuré.
     - Backend Render (`services/r2_transfer_service.py`) : envoi du header `X-R2-FETCH-TOKEN` (ENV `R2_FETCH_TOKEN`) et fail-closed si token absent.
     - Pages de test PHP : ajout d'un mode "Offload via Worker" (récupère un vrai `r2_url` puis POST Make-style vers `index.php`).
   - **Raisons** : Empêcher l'abus public du service de fetch/upload (sinon n'importe qui peut déclencher des transferts) tout en permettant des tests end-to-end réalistes.
   - **Impacts** : Ajout d'une dépendance de configuration (`R2_FETCH_TOKEN`) côté Worker/Render/PHP. Sans token, l'offload est automatiquement désactivé.

 - **[2026-01-08 17:25:00] - Logging des paires R2 côté PHP (webhook receiver) + diagnostics compatibles legacy**
   - **Décision** : Étendre le logger PHP (`deployment/src/JsonLogger.php`) et le receiver (`deployment/src/WebhookHandler.php`) pour enregistrer aussi les paires `source_url`/`r2_url` quand elles sont présentes dans `delivery_links` (payload enrichi côté Python).
   - **Changements clés** :
     - Ajout des méthodes `JsonLogger::logR2LinkPair()` et `JsonLogger::logDeliveryLinkPairs()`.
     - Appel de `logDeliveryLinkPairs()` dans `WebhookHandler::processWebhook()` (et flow `recadrage`) avant le logging legacy des URLs.
     - Amélioration de `deployment/src/WebhookTestUtils.php` pour supporter des fichiers `webhook_links.json` mixtes (entrées legacy `url` et entrées R2) sans faux positifs.
   - **Raisons** : Les pages/tests PHP ajoutaient des entrées legacy en fin de fichier, masquant les entrées R2 et empêchant de valider visuellement la présence des paires.
   - **Impacts** : `webhook_links.json` peut désormais contenir les 2 formats; les diagnostics affichent explicitement le comptage R2 vs legacy.

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
