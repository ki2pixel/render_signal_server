# Journal des Décisions (Chronologie Inversée)
Ce document enregistre les décisions techniques et architecturales importantes prises au cours du projet.

## Archives disponibles
Les périodes antérieures sont archivées dans `/memory-bank/archive/` :
- [decisionLog_2026Q3.md](archive/decisionLog_2026Q3.md) - Archives Q3 2026 (juillet 2026 ; août-septembre encore actifs)
- [decisionLog_2026Q1.md](archive/decisionLog_2026Q1.md) - Archives Q1 2026 (janvier à février 2026)
- [decisionLog_2025Q4.md](archive/decisionLog_2025Q4.md) - Archives Q4 2025 (septembre à décembre 2025)

## Décisions récentes (90 jours)

- **[2026-11-13] Report automatique des livraisons recadrage hors fenêtre au prochain matin ouvré**
  - **Décision** : Résoudre `delivery_time` au moment de construire le payload. Une cible hors de `[window_start, window_end)` est reportée à `09h00` le jour ouvré suivant ; le samedi est ouvré, le dimanche est exclu, les jours fériés ne sont pas gérés. Les sujets `URGENCE`, les cibles en journée et les autres détecteurs restent inchangés.
  - **Raisons** : Les lots 113 à 117 demandaient des livraisons à `21h00` ou `00h25`-`00h55` pour une fenêtre `09h30-19h00`. L'auto-réponse promettait un créneau nocturne alors que l'email avait été reçu en journée. Le flux d'envoi est immédiat : seule la formule d'engagement devait être corrigée.
  - **Changements clés** :
    1. `email_processing/delivery_time_resolver.py` : resolver pur (parsing ISO 8601/RFC 2822, fenêtre, urgence, chronologie, dimanche), sans dépendance externe.
    2. `services/ingress_service.py` : branchement dans `_handle_allowed_email` avec la date de réception du payload Gmail.
    3. `email_processing/orchestrator.py` : branchement avant `_build_webhook_payload` avec le `Date` IMAP.
    4. Tests : fixtures `.eml` réelles 113-117, bornes `09h30`/`19h00`, urgence, rollover `31/12/2026 → 01/01/2027`, vendredi/samedi/dimanche, fenêtres absentes ou traversant minuit.
  - **Impacts** : Payload `delivery_time` ajusté avant l'envoi PHP ; aucun changement de `WebhookHandler.php` ni de `EmailStorageLogger.php` (la valeur stockée est déjà ajustée). Suite complète **432 passed, 7 skipped** ; resolver couvert à 100 %.
  - **Alternatives écartées** : Recalcul dans PHP (dupliquerait la fenêtre et le fuseau, déploiement manuel du dossier `deployment/`) ; ajustement dans `check_media_solution_pattern` (couplerait l'extraction à la configuration) ; report à `window_start` 09h30 (le brief impose 09h00) ; gestion des jours fériés (contredirait l'attendu `01/01/2027 à 09h00`).

- **[2026-11-11] Archive des emails « Missions Recadrage » : stockage hybride fichier-par-lot + index**
  - **Décision** : Stocker chaque email de recadrage dans un fichier JSON individuel (`deployment/data/emails/recadrage_lot_<num>_<date>.json`) et maintenir un index léger plafonné (`deployment/data/emails_recadrage_index.json`). Exposer le tout via un proxy read-only `public_html/email_proxy.php`.
  - **Raisons** : Un JSON unique atteindrait 10 à 30 Mo après quelques centaines de lots, avec un `json_decode()` complet à chaque lecture et un risque de corruption lors des réécritures concurrentes. Le stockage par fichier donne une lecture O(1), des écritures isolées et un index de quelques dizaines de Ko.
  - **Changements clés** :
    1. `EmailStorageLogger` : extraction lot/date/sujet/corps/deadline/liens, masquage de l'expéditeur uniquement, hash SHA-256 de l'ID Gmail, écriture atomique temp+rename, index sous `flock`, cap `EMAIL_INDEX_MAX_ENTRIES` (défaut 200), garde-fou `EMAIL_STORAGE_MAX_BODY_BYTES`.
    2. `WebhookHandler` : persistance déclenchée après validation/autorisation et avant les branches à retour précoce (`recadrage`, `desabonnement_journee_tarifs`) ; une erreur de stockage est loguée sans faire échouer l'acquittement.
    3. `email_proxy.php` : `GET` uniquement, index ou détail, alias `recadrage_lot_XXX`, validation stricte de l'ID, `realpath()` + préfixe `data/emails/`, token `EMAIL_PROXY_TOKEN` optionnel.
    4. `verify-compatibility.php` : 31 assertions couvrant deux lots, la déduplication, le plafond d'index, le masquage PII, la deadline en texte pur, la détection `URGENT`/`URGENCE` et l'exclusion du template samedi.
  - **Impacts** : Aucun changement Apps Script/Flask ; le corps est déjà transmis intégralement via `email_content`. La suite Python reste verte (399 passed, 7 skipped). Le dossier `deployment/` étant ignoré par Git, l'upload des fichiers PHP reste manuel.
  - **Alternatives écartées** : JSON unique (mémoire et réécritures), base MySQL (complexité opérationnelle), stockage R2 (latence et gestion des credentials), index non plafonné (croissance inutile).

- **[2026-09-30] Classification du template « vidéos du samedi » dans la famille DESABO (flux AUTOREPONDEUR)**
  - **Décision** : Détecter le template « Missions de recadrage » (vidéos du samedi) avec un pattern dédié (`check_media_solution_samedi_conditions`) et le classer sous le détecteur existant `desabonnement_journee_tarifs`, sans introduire de nouvelle valeur de détecteur.
  - **Raisons** : Le handler PHP (`deployment/src/WebhookHandler.php`, hors git) ne route que `desabonnement_journee_tarifs` (flux AUTOREPONDEUR) et `recadrage` (confirmation mission) ; le template est une demande de disponibilité, comme les emails « lots de vidéos / tarifs habituels ». Réutiliser le détecteur existant évite une modification PHP manuelle (dossier `deployment/` déployé hors CI).
  - **Changements clés** : pattern dédié (sujet « media solution » + « recadrage » ; corps « videos du samedi » normalisé) ; branchement dans `IngressService._get_detector_and_time` et `email_processing/orchestrator._infer_detectors` ; tests pattern + ingress ; doc `docs/processing/pattern-matching.md`.
  - **Impacts** : Payload enrichi (`detector=desabonnement_journee_tarifs`, envoi même hors fenêtre horaire avec `webhooks_time_start` = début de fenêtre) ; réponse auto « Acception : … » vers `AUTOREPONDEUR_TO`. Un filtre Gmail dédié reste requis pour l'acheminement (ajouté le 29/09).
  - **Alternatives écartées** : Étendre `check_desabo_conditions` (deux templates mélangés dans une même fonction) ; nouveau détecteur `recadrage_samedi` (modification PHP manuelle + contrat payload étendu) ; élargir le filtre Gmail n°2 (l'exclusion « Lien de dépôt » est voulue pour les emails de lot).

- **[2026-08-11] Protection défensive contre les URLs webhook placeholder (incident 2 emails non livrés)**
  - **Décision** : Ajouter un garde-fou empêchant l'envoi de payloads webhook vers des URLs placeholder (`example.com`, `test.com`, hôtes locaux) et garantir un fallback vers une cible valide.
  - **Raisons** : Incident du 11/08/2026 — la config webhook stockée contenait `https://example.com/hook` (placeholder), qui écrasait l'env var `WEBHOOK_URL=https://webhook.kidpixel.fr/index.php` (la config stockée a priorité sur l'env var dans `_send_ingress_webhook`). Les 2 emails Média Solution ont été POSTés vers `example.com` (405) et non livrés. Le champ vide du dashboard ne peut pas vider la config (le serveur ignore les URL vides), donc la valeur placeholder provenait d'une saisie antérieure.
  - **Changements clés** :
    1. `utils/validators.py` : `is_placeholder_webhook_url()` — détecte domaines RFC 2606 (`example.com/net/org`), `test.com`, `localhost`, `127.0.0.1`, et sous-domaines `.example.com/.example.net`.
    2. `services/ingress_service.py` (`_send_ingress_webhook`) : chaîne de résolution défensive `config stockée → env var WEBHOOK_URL → défaut https://webhook.kidpixel.fr/index.php`, en sautant les valeurs vides/placeholders.
    3. `routes/api_webhooks.py` et `routes/api_test.py` : rejet HTTP 400 à la sauvegarde d'une URL placeholder (empêche la réintroduction via le dashboard).
  - **Impacts** : Suite de tests complète 384 passed / 7 skipped ; 9 nouveaux tests (`tests/test_placeholder_webhook_url.py`) ; tests existants ajustés (`test_app_render.py`, `test_routes_integration.py`). À surveiller : le fallback silencieux pourrait masquer une config erronée — un log explicite à l'envoi serait un bonus futur.
  - **Alternatives écartées** : Ne pas étendre la protection au flux `send_custom_webhook_flow` (réservé pour plus tard si besoin) ; pas de priorité inversée env var > config (changerait la sémantique existante).

---

## Politique d'archivage
Les entrées de plus de 90 jours sont archivées par trimestre dans `/memory-bank/archive/` au format `<fichier>_YYYYQn.md`. Une archive trimestrielle peut être complétée lors des campagnes suivantes. Voir les archives pour l'historique détaillé.
