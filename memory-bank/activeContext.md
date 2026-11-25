# Contexte Actif

## Tâche en cours
- Aucune tâche active (documentation resynchronisée le 25/11/2026 via le workflow `docs-updater`).

## Décisions récentes
- **Resynchronisation documentaire [2026-11-25]** :
  - Audit métrique : 57 fichiers Python cœur, 8 346 lignes de code ; `radon` moyenne C (16,85) sur 59 blocs, hotspot legacy `check_new_emails_and_trigger_webhook` F (43).
  - `README.md` : index documentaire réparé (suppression des chemins `docs/features/`, `docs/configuration/`, `docs/operations/`, `docs/quality/`, `docs/integrations/`) ; arborescence alignée sur le code réel ; services et état des tests actualisés.
  - `docs/core/architecture.md` : table de complexité recalculée, lien `magic-links.md` corrigé vers `magic-link-auth.md`, arbre frontend et tables de services mis à jour, section `delivery_time_resolver.py` ajoutée.
  - `docs/processing/pattern-matching.md` et `docs/ingestion/gmail-push.md` : chaîne de résolution hors fenêtre précisée (`_resolve_recadrage_delivery_time`), diagramme de séquence Mermaid ajouté, compteurs de tests corrigés (30 + 19, ingress 14).
  - `docs/access/dashboard-ui.md` : modules ES6 réels (ConfirmDialog, autosave, config_io, deploy, magic_link, panels, status_banner, debounce, listenerRegistry), API `TabManager` corrigée (`init`, `enhanceAccessibility`, deep-linking, sessionStorage). Les exemples inventés (`loadTabContent`, `LogTimeline`, services instanciés, Jest) ont été remplacés par le code réel et les 38 tests Vitest.
  - `docs/access/authentication.md` : réécriture sur l'API réelle (`generate_token`/`consume_token`, format `<id>.<expires>.<signature>`, `permanent`, route `/login/magic/<token>`, fallback mot de passe historique).
  - `docs/ops/monitoring.md` : réécriture sur `/health` minimal, `/api/diag/runtime`, `WebhookLoggerService`, timeouts réels et verrou in-flight de 15 min.
  - `docs/ops/backfill-recadrage.md` : nouvelle note d'exploitation pour `scripts/backfill_recadrage_emails.py` (garantie sans rejeu, options CLI, sorties, limites).
  - `services/README.md` et `tests/README.md` : inventaires et liens corrigés (12 services, suppression des références mortes).
  - `README.md` et `docs/README.md` : promesses fausses retirées (lazy loading, mobile-first, conditional logging), payload `/health` et format des magic links corrigés, statuts Gmail Push alignés (`queued`, verrou 15 min).
  - `AGENTS.md` et `.agents/rules/codingstandards.md` : liste réelle des singletons, propriété du config store, marqueurs pytest disponibles, portée Given/When/Then, logging, validation R2 (`_validate_remote_fetch_domain`), mécanisme de déduplication et exception `innerHTML` de `ConfirmDialog`.
  - Aucun fichier `debug/*.json` modifié ; aucune commande d'écriture hors documentation.
- **Audit frontend UX & accessibilité [2026-11-25]** :
  - Page Outils scindée en 3 groupes (Actions fréquentes / Configuration / Débogage repliable par défaut) ; Déploiement et Ingestion Gmail Push remontés et visuellement prioritaires.
  - Gmail Push sauvegardé immédiatement (auto-save + rollback visuel en cas d'échec) ; les flags debug restants demeurent dans le panneau replié.
  - Navigation onglets : `aria-current`, deep-linking `#sec-*`, restauration de l'onglet via sessionStorage, focus géré ; `tabindex` retiré des tabpanels.
  - Confirmation accessible (`static/components/ConfirmDialog.js`) remplace `confirm()` ; toasts unifiés (`MessageHelper.showToast`), `role=status`/`aria-busy`, anti double-soumis, erreurs serveur contextualisées (`describeError`).
  - Découplage `handleConfigVerification` → événement `configverification:routing` consommé par `RoutingRulesService._renderRedisInspect` ; utilitaires partagés `utils/debounce.js` et `utils/listenerRegistry.js`.
  - Détail complet : `memory-bank/progress.md` (entrée du 2026-11-25).
- **Backfill Rétro-Actif 30 Jours `email_proxy.php` [2026-11-22]** :
  - Extraction de 62 missions entrantes de recadrage depuis `debug/mails/a_exporter.mbox` couvrant la fenêtre 23/10/2026 -> 12/11/2026 (dont le Lot 115 du 09/11).
  - Déduplication par paire `(lot, mois calendaire)` pour préserver la distinction entre les lots recyclés d'un mois sur l'autre (ex: Lot 268 octobre et Lot 268 novembre).
  - Fusion avec les 42 missions live de `https://webhook.kidpixel.fr/email_proxy.php` pour un index total de 104 entrées triées par `received_at` décroissant.
  - Enrichissement R2 automatique (54/62 missions avec URL R2 et nom de zip).
  - Zéro rejeu vers `index.php` (aucun envoi d'email au client).
  - Création de `scripts/backfill_recadrage_emails.py`, `tests/test_backfill_recadrage.py` (37 tests) et des packages dans `deployment/dist/`.
- **Remédiation Antigravity (Règles & Indexation) [2026-11-16]** :
  - Création de `.antigravityignore` à la racine (exclusion `.venv/`, `node_modules/`, caches pytest/mypy, `static/dist/`, `htmlcov/`, `.env`).
  - Densification normative et condensation de 4 règles en dépassement de plafond Antigravity (~5,5 Ko / ~750 mots) :
    - `codingstandards.md` : 11,9 Ko $\rightarrow$ 4,2 Ko (511 mots), basculé en `trigger: model_decision`.
    - `v5.md` : 11,6 Ko $\rightarrow$ 2,5 Ko (331 mots), fusion §1/§3 et recentrage outils.
    - `prompt-injection-guard.md` : 9,6 Ko $\rightarrow$ 2,5 Ko (323 mots), consolidation de la règle "Avertir puis arrêter".
    - `test-strategy.md` : 5,8 Ko $\rightarrow$ 2,5 Ko (361 mots), allègement sans perte d'exigence.
  - Correction de coquille dans `skills-integration.md` (`workflow_mediapipe` $\rightarrow$ `render_signal_server`).
  - Mise à jour des workflows `.agents/workflows/enhance.md` et `enhance_complex.md` pour intégrer `.agents/rules/test-strategy.md`.
  - Résultat : 100 % des règles sous 4,9 Ko (< 610 mots), élimination totale des alertes de saturation IDE.
- Ajustement des livraisons « Missions Recadrage » hors fenêtre horaire (report au prochain matin ouvré).
- Résolution dédiée dans `email_processing/delivery_time_resolver.py`, branchée dans l'ingress Gmail Push et l'orchestrateur IMAP.

## Questions Ouvertes
- Aucune.

## Prochaine Étape
- Surveiller les prochains lots nocturnes (`00hxx`) et vérifier la valeur `delivery_time` dans les logs webhook.
- Vérifier visuellement en production le rendu du nouvel onglet Outils (hiérarchie des 3 groupes, mémorisation du repli du panneau Débogage) sur desktop et mobile.
