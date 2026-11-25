# Suivi de Progression

## Archives disponibles
Les périodes antérieures sont archivées dans `/memory-bank/archive/` :
- [progress_2026Q3.md](archive/progress_2026Q3.md) - Archives Q3 2026 (juillet 2026 ; août-septembre encore actifs)
- [progress_2026Q2.md](archive/progress_2026Q2.md) - Archives Q2 2026 (mai à juin 2026)
- [progress_2026Q1.md](archive/progress_2026Q1.md) - Archives Q1 2026 (janvier à février 2026)
- [progress_2025Q4.md](archive/progress_2025Q4.md) - Archives Q4 2025 (décembre 2025 et antérieur)

## Politique d'archivage
Les entrées de plus de 90 jours sont archivées par trimestre dans `/memory-bank/archive/` au format `<fichier>_YYYYQn.md`. Une archive trimestrielle peut être complétée lors des campagnes suivantes. Voir les archives pour l'historique détaillé.

## En cours
- Aucune tâche active.

## Terminé

[2026-11-25 22:18:00] - Vérification de AGENTS.md et .agents/rules/codingstandards.md
- **Objectif** : Aligner les deux documents de référence sur l'architecture et les pratiques réellement présentes dans le dépôt.
- **Corrections factuelles** :
  * Liste des singletons ramenée aux 10 services qui exposent réellement `get_instance()` ; `ConfigService` et `AuthService` reclassés comme services non-singleton du composition root.
  * Propriété du config store précisée : `RoutingRulesService`, `WebhookConfigService`, `preferences/processing_prefs.py` + `routes/api_processing.py`, `MagicLinkService`. `ConfigService` ne lit que les variables d'environnement.
  * Marqueurs pytest corrigés : `unit`, `integration`, `e2e`, `slow`, `redis`, `imap`. Les suites R2 et résilience n'ont pas de marqueur et se sélectionnent par fichier.
  * Règle Given/When/Then limitée aux tests nouveaux ou modifiés (9 fichiers sur 41 la respectent aujourd'hui).
  * Logging clarifié : webhooks via `app_logging/`, applications via `app.logger`.
  * R2 : `ALLOWED_REMOTE_FETCH_DOMAINS` + `_validate_remote_fetch_domain()` au lieu d'un `is_allowed_domain()` inexistant.
  * Déduplication décrite réellement : set Redis, clés TTL, verrou `SET NX EX`.
  * `innerHTML` interdit pour les données dynamiques, exception statique documentée pour `ConfirmDialog` ; préférence `data-target` avec repli ID legacy.
- **Corrections annexes** : `README.md` utilise désormais `TRIGGER_PAGE_USER`/`TRIGGER_PAGE_PASSWORD` (et non `DASHBOARD_*`) ; l'anti-pattern de `docs/access/authentication.md` référence le bon nom de setting.
- **Validation** : noms de services, fonctions R2, marqueurs pytest et chemins de tests vérifiés dans le code ; blocs Markdown équilibrés.
- **Statut** : Terminé.

[2026-11-25 22:01:13] - Resynchronisation complète de la documentation (workflow docs-updater)
- **Objectif** : Aligner la documentation sur l'état réel du code après les livraisons du backfill 30 jours et de l'audit frontend, et supprimer les références à des dossiers documentaires disparus.
- **Audit métrique** :
  * Périmètre cœur : 57 fichiers Python, 8 346 lignes de code (hors tests, docs, debug, deployment).
  * Complexité : moyenne C (16,85) sur 59 blocs ; hotspots `check_new_emails_and_trigger_webhook` F (43), `_parse_and_validate_webhook_payload` E (36), `check_media_solution_pattern` E (33), `validate_processing_prefs` E (32), `normalize_source_url` E (31).
  * Hotspots historiques résolus : `process_gmail_push` B (8), `send_custom_webhook_flow` B (7), `consume_token` A (5).
- **Actions réalisées** :
  * `README.md` : index documentaire réparé, arborescence alignée sur le code réel, liste des services complétée, références mortes (`docs/features/`, `docs/configuration/`, `docs/operations/`, `docs/quality/`, `docs/integrations/`, `docs/refactoring-*.md`) supprimées.
  * `docs/core/architecture.md` : table de complexité recalculée, lien Magic Links corrigé, tables de services (Ingress, Dedup, RateLimit, Metrics, Logger) actualisées, arbre frontend réel, section `delivery_time_resolver.py`.
  * `docs/ingestion/gmail-push.md` : diagramme de séquence Mermaid du flux complet, étape 5 bis de résolution du créneau, compteur de tests ingress porté à 14.
  * `docs/processing/pattern-matching.md` : interface du résolveur, appel réel `IngressService._resolve_recadrage_delivery_time`, compteurs 30 + 19 tests.
  * `docs/access/dashboard-ui.md` : modules ES6 réels, API `TabManager` corrigée, sections ConfirmDialog, toasts et auto-save/rollback. Les exemples inventés (`loadTabContent`, `LogTimeline`, services instanciés, suites Jest) ont été remplacés par le code réel (services statiques, panneaux déjà présents, polling 30 s, Vitest).
  * `docs/access/authentication.md` : réécriture sur l'API réelle (`generate_token`/`consume_token`, format `<id>.<expires>.<signature>`, `permanent`, route `/login/magic/<token>`, fallback mot de passe en clair à temps constant, 3 tests magic link).
  * `docs/ops/monitoring.md` : réécriture sur `/health` minimal, `/api/diag/runtime`, `WebhookLoggerService`, limites mémoire/timeouts réelles et verrou in-flight de 15 min.
  * `docs/ops/backfill-recadrage.md` : nouvelle note d'exploitation (garantie sans rejeu vers `index.php`, options CLI, sorties, limites, 37 tests).
  * `services/README.md` : 12 services, sections Ingress/Routing/RateLimit/Metrics/Logger, références mortes supprimées.
  * `tests/README.md` : arborescence réelle et lien mort `docs/testing.md` remplacé.
  * `README.md` et `docs/README.md` : suppression des promesses fausses (lazy loading, mobile-first, conditional logging), correction du payload `/health`, du format des magic links et des statuts Gmail Push (`queued`, verrou 15 min).
- **Validation** : liens Markdown contrôlés (hors documentation Cline importée et faux positifs de regex) ; blocs de code équilibrés ; 422 tests Python recensés, 38 tests Vitest ; aucune modification de `debug/*.json`, aucun code applicatif touché.
- **Statut** : Terminé avec succès.

[2026-11-25 21:09:22] - Audit frontend UX/accessibilité et refonte de la page Outils
- **Objectif** : Réduire la charge cognitive du dashboard (surtout « Outils ») et corriger les lacunes WCAG AA de façon transverse plutôt qu'au cas par cas.
- **Actions réalisées** :
  * `dashboard.html` : page Outils réorganisée en 3 groupes (Actions fréquentes : Déploiement + Ingestion Gmail Push ; Configuration : Import/Export + Magic Link ; Outils de Débogage repliable par défaut) ; toggles reliés via `aria-labelledby` ; `tabindex` retiré des tabpanels.
  * `static/components/ConfirmDialog.js` : modale accessible (`role=alertdialog`, focus trap, Échap, retour du focus) remplaçant `confirm()` (déploiement, migration Redis).
  * `static/components/TabManager.js` : `aria-current`, deep-linking par hash `#sec-*`, persistance sessionStorage de l'onglet, focus sur l'onglet activé, gestion `hashchange`.
  * `static/services/panels.js` : état replié/déplié mémorisé en localStorage ; garde anti double-soumis et état de chargement sur les sauvegardes de panneaux.
  * `static/services/config_io.js` : `saveRuntimeFlag()` pour l'auto-save immédiat de Gmail Push (rollback UI en cas d'échec) ; erreurs serveur remontées via `MessageHelper.describeError` ; `handleConfigVerification` découplé du DOM routage via l'événement `configverification:routing` consommé par `RoutingRulesService._renderRedisInspect`.
  * `static/utils/MessageHelper.js` : toast unifié (`showToast`, région `role=status`, pile max 3), `role=status` garanti, `aria-busy` dans `setButtonLoading`, garde anti double-soumis.
  * `static/utils/debounce.js` + `static/utils/listenerRegistry.js` : utilitaires partagés (déduplication panels/autosave) ; debounce 400 ms sur la validation d'URL et 200 ms sur la preview payload.
  * `static/services/status_banner.js` + CSS : icône de statut `role=img` + `aria-label` dynamique, couleurs en dur migrées vers variables CSS (`--json-*`, timeline), ancien toast `.copied-feedback` supprimé.
  * Bouton mort `buildPayloadPreviewBtn` rendu fonctionnel ; préférence « mode illimité » magic link persistée ; `restartServerBtn`/`restartMsg` renommés `deployApplicationBtn`/`deployMsg`.
- **Validation** : ESLint 0 erreur (22 warnings préexistants), vitest 38/38, `vite build` OK, rendu Jinja du dashboard validé (`tests/test_routes_dashboard_unit.py` 5/5).
- **Référence** : plan d'audit `~/.commandcode/plans/audit-frontend-ux-accessibilite.md`.

[2026-11-22 13:45:00] - Enrichissement rétro-actif 30 jours du proxy email (email_proxy.php)
- **Objectif** : Alimenter le proxy public `email_proxy.php` (sur `webhook.kidpixel.fr`) avec les missions des 30 derniers jours (dont le Lot 115 du 09/11/2026) à partir du mbox `debug/mails/a_exporter.mbox`.
- **Actions réalisées** :
  * Script d'extraction Python `scripts/backfill_recadrage_emails.py` : extraction mbox, parsing dates/deadlines, enrichissement liens R2 via `webhook_links.json`, déduplication par `(lot, mois calendaire)`.
  * Génération des 62 fichiers JSON individuels et fusion avec les 42 entrées live de production -> index de 104 entrées triées chronologiquement (`received_at` DESC).
  * Génération des packages de déploiement dans `deployment/dist/` (`backfill_recadrage_30d.tar.gz` 29 Ko, `backfill_recadrage_30d.zip` 75 Ko, `backfill_payloads_30d.json` 207 Ko).
  * Outil de migration serveur PHP `deployment/tools/import_retroactive_missions.php` sous `flock(LOCK_EX)` avec mode `--dry-run`.
  * Tests automatisés dédiés dans `tests/test_backfill_recadrage.py` : 37 tests (100 % passants), 0 régression sur `tests/test_services.py` (31 tests passants).
- **Statut** : Prêt pour déploiement serveur par l'utilisateur.

[2026-11-16 21:46:00] - Audit et remédiation de la saturation de tokens des règles Antigravity et indexation projet
- **Objectif** : Éliminer les alertes « You have exceeded the maximum token limit for this file » dans l'IDE Antigravity et empêcher l'indexation non désirée des dossiers lourds (`node_modules/`, `.venv/`, caches).
- **Actions réalisées** :
  * `.antigravityignore` : créé à la racine avec règles d'exclusion pour `.venv/`, `node_modules/`, caches python (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`), builds `static/dist/`, `htmlcov/`, `.env` et dumps de debug.
  * `.agents/rules/codingstandards.md` : densification normative ramenant la taille de 11,9 Ko (1 466 mots) à **4,2 Ko (511 mots)**, basculement en `trigger: model_decision`, élimination des redondances avec `AGENTS.md` et de la liste verbeuse de descriptions de skills.
  * `.agents/rules/v5.md` : fusion des sections §1 et §3, condensation de la politique d'outils, ramené de 11,6 Ko (1 587 mots) à **2,5 Ko (331 mots)**.
  * `.agents/rules/prompt-injection-guard.md` : condensation de la règle "Warning-Then-Stop" et du protocole destructif, ramené de 9,6 Ko (1 309 mots) à **2,5 Ko (323 mots)**.
  * `.agents/rules/test-strategy.md` : simplification des exemples et répétitions, ramené de 5,8 Ko (819 mots) à **2,5 Ko (361 mots)**.
  * `.agents/rules/skills-integration.md` : correction du nom du repo (`workflow_mediapipe` $\rightarrow$ `render_signal_server`).
  * `.agents/workflows/enhance.md` et `enhance_complex.md` : ajout de la référence contractuelle à `test-strategy.md`.
- **Validation** :
  * 100 % des règles du projet `.agents/rules/*.md` sont désormais sous **4,9 Ko (< 610 mots)**, éliminant totalement le risque de dépassement de plafond IDE (~5,5 Ko / ~750 mots).
  * Validation syntaxique des frontmatters YAML réussie (`yaml.safe_load`).
  * Suite de tests de non-régression au vert (31 passed).
- **Statut** : Terminé avec succès.

[2026-11-13 09:13:50] - Ajustement des livraisons « Missions Recadrage » hors fenêtre horaire
- **Objectif** : Éviter que l'auto-réponse confirme un créneau de livraison nocturne hors de la plage d'activité (lots 113 à 117 : `21h00`, `00h25`, `00h30`, `00h40`, `00h55`).
- **Analyse amont** : `check_media_solution_pattern` extrait la cible brute (`HHhMM` ou `le DD/MM/YYYY à HHhMM`) ; l'ingress et l'orchestrateur construisent `payload_for_webhook["delivery_time"]` sans contrôle de plage ; PHP concatène directement la valeur dans `"OK merci, je m'en occupe pour {$safeDelivery}."`.
- **Décision** : Résoudre le créneau au moment du payload, via un module pur, sans toucher au fenêtrage de réception ni au PHP. Report au prochain matin ouvré à `09h00`, samedi ouvré, dimanche exclu, fériés non gérés.
- **Actions réalisées** :
  * `email_processing/delivery_time_resolver.py` : parsing ISO 8601/RFC 2822 de la date de réception, détection `URGENCE`, résolution soirée/nuit, gestion du rollover et du dimanche.
  * `services/ingress_service.py` : helper `_resolve_recadrage_delivery_time` appelé avant la construction du payload Gmail Push.
  * `email_processing/orchestrator.py` : helper `_resolve_out_of_window_delivery_time` appelé avant `_build_webhook_payload` (flux IMAP legacy).
  * `tests/email_processing/test_recadrage_delivery_window.py` : 32 tests (cas réels 113-117 embarqués en inline, bornes, urgence, rollover, dimanche, fenêtres invalides, câblage).
  * `tests/routes/test_api_ingress.py` : test de bout en bout du payload ajusté.
  * `docs/processing/pattern-matching.md` : section « Ajustement des livraisons recadrage hors fenêtre ».
- **Validation** : suite complète **432 passed, 7 skipped** ; `delivery_time_resolver.py` couvert à 100 % ; aucun changement PHP requis.
- **Correctif CI** : les `.eml` de `debug/mails/` étant ignorés par Git, les tests utilisent désormais des extraits inline. Commande CI exacte validée (`--cov-fail-under=70`) : 432 passed, 7 skipped, couverture **72.21 %**.
- **Statut** : Terminé avec succès.

[2026-11-11 20:30:00] - Archive des emails « Missions Recadrage » (stockage hybride PHP + proxy)
- **Objectif** : Persister les corps complets des emails de recadrage et les exposer via une API HTTP légère, sans dégrader les performances ni la fiabilité du webhook.
- **Analyse amont** : `scripts/google_script.js` envoie déjà `body` (`getBody()`/`getPlainBody()`) ; `IngressService` transmet `email_content` sans troncature ; `_prepare_payload()` ne modifie pas le corps. Aucun changement Apps Script/Flask.
- **Décision** : Option B, un fichier JSON par lot (`deployment/data/emails/recadrage_*.json`) + index plafonné à 200 entrées (`deployment/data/emails_recadrage_index.json`).
- **Actions réalisées** :
  * `deployment/src/EmailStorageLogger.php` : extraction lot/date/sujet/corps/deadline/liens, masquage de l'expéditeur, écriture atomique temp+rename, index sous `flock`, cap configurable, garde-fou taille corps.
  * `deployment/src/WebhookHandler.php` : persistance avant les branches à retour précoce, erreurs loguées sans échec d'acquittement, validation `Subject` en fallback.
  * `deployment/public_html/email_proxy.php` : index/détail en lecture seule, alias `recadrage_lot_XXX`, validation stricte d'ID, `realpath`, token optionnel.
  * `deployment/verify-compatibility.php` : 31 assertions (2 lots, déduplication, cap 10, PII, deadline texte, détection `URGENT`/`URGENCE`, template samedi exclu).
  * `tests/routes/test_api_ingress.py` : assertion `email_content == body`.
- **Validation** : PHP 7.4/8.2 `php -l` OK ; `verify-compatibility.php` 31/31 ; email réel `Lot 80 - URGENT` reconnu et stocké (`urgent: true`) ; smoke test proxy (index 200, détail 200, alias 200, traversal 400, absent 404, POST 405, token 401/200) ; pytest ciblé 52 passed ; suite complète **399 passed, 7 skipped**.
- **Déploiement** : `deployment/` étant ignoré par Git, upload manuel requis (voir `UPLOAD_CHECKLIST.md`).
- **Statut** : Terminé avec succès.

[2026-10-21 17:45:16] - Campagne d'archivage memory-bank (Q2/Q3 2026)
- **Objectif** : Réduire `decisionLog.md` et `progress.md` aux entrées de moins de 90 jours (cutoff 2026-07-23) et vider `activeContext.md` de ses tâches terminées.
- **Actions réalisées** :
  * Création de `archive/progress_2026Q2.md` (13 entrées, mai-juin) et `archive/progress_2026Q3.md` (5 entrées, juillet).
  * Création de `archive/decisionLog_2026Q3.md` (2 entrées, juillet) et append de 18 décisions de janvier dans `archive/decisionLog_2026Q1.md`.
  * Déplacement de la synthèse Q4 2025 vers `archive/decisionLog_2025Q4.md`.
  * Purge des 14 tâches terminées de `activeContext.md` (contenu préservé dans `progress.md` et les archives).
- **Validation** : 22 décisions et 21 entrées de progression conservées à l'identique ; ordre décroissant, absence de doublons et liens d'index vérifiés.
- **Statut** : Terminé avec succès.

[2026-09-30 02:04:50] - Détection du template « vidéos du samedi » (Média Solution)
- **Objectif** : Reconnaître le template « Missions de recadrage » demandant la disponibilité pour les vidéos du samedi (envoyé parfois en semaine), jusqu'ici non couvert par la chaîne.
- **Analyse de la chaîne** : filtres Gmail (aucun ne matche ce template) → Apps Script → `/api/ingress/gmail` → pattern matching (aucun détecteur) → webhook PHP `deployment/src/WebhookHandler.php` (hors git) qui route selon `detector` (`desabonnement_journee_tarifs` → AUTOREPONDEUR, `recadrage` → RECADRAGE).
- **Actions réalisées** :
  * `email_processing/pattern_matching.py` : ajout de `check_media_solution_samedi_conditions` (sujet « media solution » + « recadrage », corps « videos du samedi », texte normalisé).
  * `services/ingress_service.py` et `email_processing/orchestrator.py` : classement dans la famille `desabonnement_journee_tarifs` (flux AUTOREPONDEUR, aucun changement PHP requis).
  * Tests : `TestCheckMediaSolutionSamediConditions` (5 tests) + `test_ingress_gmail_samedi_template_detected_as_autorepondeur` ; doc `docs/processing/pattern-matching.md` synchronisée.
- **Validation** : 399 passed / 7 skipped ; détection vérifiée sur les 4 emails bruts `debug/mails/*.eml` (29/09 → template samedi ; Lot-162/169 et 18/09 inchangés).
- **Déploiement** : filtre Gmail « vidéos du samedi » ajouté par l'utilisateur ; commit `8f288eb` poussé sur `main` (déploiement Render via GitHub Actions).
- **Statut** : Terminé avec succès.

[2026-09-18 17:28:00] - Diagnostic et fiabilisation de l'ingestor Gmail Apps Script
- **Objectif** : Résoudre l'incident de non-détection de certains emails de missions automatiques (Lot 162, Lot 169) par l'ingestor Google Apps Script.
- **Causes racines identifiées** :
  * Erreur de syntaxe dans le filtre Gmail utilisateur (`-{Lien de dépôt}` interprété par Gmail comme `-(Lien OU de OU dépôt)`, excluant tous les emails contenant le mot "Lien" ou "de").
  * Faille logique dans `google_script.js` : la variable `allMessagesHandled = true` provoquait la suppression silencieuse du libellé `A_TRANSFERER_WEBHOOK` sans aucun envoi vers Render dès qu'un email était marqué comme lu avant le déclencheur.
  * Absence de repli texte brut dans `google_script.js` (`message.getBody()` vide sur les emails en `text/plain` provoquant un rejet HTTP 400).
- **Actions réalisées** :
  * `scripts/google_script.js` : fiabilisation de la boucle pour traiter au minimum le dernier message reçu si aucun n'est unread (`messagesToProcess`), conditionnement de la suppression du libellé à `processedCount > 0 && !hasErrors`, et ajout du repli `message.getBody() || message.getPlainBody()`.
  * Analyse des filtres Gmail et recommandation de correction de syntaxe (`-"Lien de dépôt"` avec guillemets).
- **Validation** : Suite de tests `tests/routes/test_api_ingress.py` (12 tests passés), validation du pattern matching et de l'extraction de liens sur les fichiers bruts `debug/mails/*.eml`.
- **Statut** : Terminé avec succès.

[2026-08-11 17:10:00] - Protection contre les URLs webhook placeholder et fallback cible
- **Objectif** : Empêcher la récurrence de l'incident du 11/08 (2 emails Média Solution non livrés) causé par une URL webhook placeholder `https://example.com/hook` stockée en config (écrasant l'env var `WEBHOOK_URL=https://webhook.kidpixel.fr/index.php`).
- **Actions réalisées** :
  * `utils/validators.py` : ajout de `is_placeholder_webhook_url()` (blocage domaines RFC 2606 `example.com/net/org`, `test.com`, `localhost`, `127.0.0.1`, sous-domaines `.example.com/.example.net`).
  * `services/ingress_service.py` (`_send_ingress_webhook`) : chaîne de résolution défensive — config stockée → si vide/placeholder → env var `WEBHOOK_URL` → si vide/placeholder → défaut `https://webhook.kidpixel.fr/index.php`.
  * `routes/api_webhooks.py` et `routes/api_test.py` : rejet HTTP 400 des URLs placeholder à la sauvegarde (empêche la réintroduction).
  * Tests : `tests/test_placeholder_webhook_url.py` (9 tests : helper + fallbacks) ; mise à jour de `tests/test_routes_integration.py` et `test_app_render.py` (remplacement `example.com` par `webhook.kidpixel.fr`).
- **Validation** : Suite complète **384 passed, 7 skipped**, `ruff` propre sur les lignes ajoutées.
- **Statut** : Terminé avec succès. Suivi post-déploiement par l'utilisateur (surveillance des logs `CUSTOM_WEBHOOK_DEBUG`).

## À faire

Aucune tâche active.
