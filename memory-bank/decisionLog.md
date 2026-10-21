# Journal des Décisions (Chronologie Inversée)
Ce document enregistre les décisions techniques et architecturales importantes prises au cours du projet.

## Archives disponibles
Les périodes antérieures sont archivées dans `/memory-bank/archive/` :
- [decisionLog_2026Q3.md](archive/decisionLog_2026Q3.md) - Archives Q3 2026 (juillet 2026 ; août-septembre encore actifs)
- [decisionLog_2026Q1.md](archive/decisionLog_2026Q1.md) - Archives Q1 2026 (janvier à février 2026)
- [decisionLog_2025Q4.md](archive/decisionLog_2025Q4.md) - Archives Q4 2025 (septembre à décembre 2025)

## Décisions récentes (90 jours)

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
