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
