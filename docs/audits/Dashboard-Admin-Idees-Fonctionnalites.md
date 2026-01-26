Basé sur l'analyse approfondie de votre code (notamment `orchestrator.py`, `webhook_sender.py` et les services de configuration), voici des propositions de fonctionnalités pour enrichir votre dashboard Admin.

L'objectif est de passer d'un dashboard de **monitoring/configuration** à un véritable **panneau de pilotage opérationnel** (DataOps).

## 2026-01-26 — Audit volumétrie & complexité (workflow `/docs-updater`)

- **Volumétrie actuelle (`cloc`)** : 497 248 lignes de code (dont 387 939 Python, 61 736 JavaScript). Le backend représente désormais >78 % du code total, ce qui renforce la nécessité de tooling d'observabilité server-side (DLQ, explorateur Redis).
- **Complexité moyenne (`radon cc -a`)** : **D (24.98)**. Les hotspots sont :
  1. `email_processing/orchestrator.py::check_new_emails_and_trigger_webhook` (grade **F**) — nécessité d'un simulateur pour tester les branches sans relancer le poller.
  2. `routes/api_config.py::update_polling_config` (grade **F**) — justifie la création d'un panneau de visualisation/dry-run côté dashboard.
  3. `services/r2_transfer_service.py::normalize_source_url` (grade **E**) — rend critique un explorateur des liens R2 pour diagnostiquer les normalisations.
- **Priorisation dérivée** :
  1. **Sandbox simulateur** → permet de vérifier les conditions complexes de l'orchestrateur avant mise en production.
  2. **Dead Letter Queue (DLQ)** → isole les échecs issus des flux complexes `update_polling_config`/`webhook_config` et offre un replay ciblé.
  3. **Explorateur dedup/R2** → fournit une vue opératrice sur les caches Redis et les mappings R2, indispensables pour comprendre les fonctions les plus complexes.

> Ces métriques doivent être tenues à jour après chaque refactor majeur pour suivre la réduction de la complexité et optimiser la roadmap DataOps.

### 1. File d'Attente des Échecs & Rejeu (Dead Letter Queue & Replay)
Actuellement, si un webhook échoue après les retries (définis dans `processing_prefs`), l'email est marqué comme traité ou perdu (selon la logique d'erreur) et loggué en erreur.

*   **La fonctionnalité :** Créer une interface "DLQ" (Dead Letter Queue).
*   **Fonctionnement :**
    *   Lorsqu'un webhook échoue définitivement, stocker le payload JSON complet + context (email_id, target_url) dans une liste Redis ou un fichier JSON dédié (`failed_webhooks.json`).
    *   **UI Dashboard :** Un nouvel onglet "Échecs" affichant la liste des envois ratés.
    *   **Action :** Un bouton **"Rejouer"** à côté de chaque entrée qui tente de renvoyer le payload stocké vers le webhook sans relire l'email IMAP.
*   **Impact :** Résilience maximale. Permet de gérer les pannes de Make.com sans perte de données.

### 2. Moteur de Règles de Routage Dynamique (Routing Rules Engine) ✅ **TERMINÉ**
Actuellement, la logique de routage est "hardcodée" dans `orchestrator.py` (détection DESABO vs RECADRAGE vs CUSTOM).

*   **La fonctionnalité :** Configurer le routage via l'UI au lieu du code Python.
*   **Fonctionnement :**
    *   Créer une structure JSON `routing_rules` stockée via `ConfigService`.
    *   Exemple de règle : `IF sender CONTAINS "@client.com" AND subject MATCHES "Facture" THEN USE "Webhook_Compta"`.
    *   **UI Dashboard :** Un constructeur visuel simple :
        *   Condition (Sujet / Expéditeur / Corps)
        *   Opérateur (Contient / Regex / Est égal à)
        *   Action (URL Webhook spécifique / Priorité Haute)
*   **Impact :** Permet d'ajouter de nouveaux flux (ex: "Factures", "Support") sans redéployer le serveur.
*   **Statut** : **Implémenté et terminé (2026-01-26)**
    *   Service `RoutingRulesService` (singleton, Redis-first) avec validation et normalisation
    *   API REST `/api/routing_rules` (GET/POST) sécurisée
    *   Intégration dans l'orchestrateur avec évaluation avant envoi webhook par défaut
    *   UI Dashboard avec builder de règles, drag-drop reorder, autosave debounce
    *   Correction UI robuste : détection client-side des règles legacy + génération automatique des 3 règles fallback
    *   Cache-bust ES6 pour garantir la mise à jour immédiate de l'interface
    *   Tests exhaustifs : 12 tests couvrant service, API et orchestrator
    *   Fichiers : `services/routing_rules_service.py`, `routes/api_routing_rules.py`, `email_processing/orchestrator.py`, `dashboard.html`, `static/services/RoutingRulesService.js`, `static/dashboard.js`

### 3. "Sandbox" / Simulateur de Traitement
Pour tester une regex ou un comportement, il faut actuellement s'envoyer un email.

*   **La fonctionnalité :** Un simulateur de pipeline dans l'onglet "Outils".
*   **Fonctionnement :**
    *   **Input :** Un formulaire avec "Sujet", "Expéditeur", "Corps (Texte/HTML)".
    *   **Process :** Le backend exécute `email_processing.pattern_matching` et `link_extraction` sur ces données fictives sans toucher à IMAP.
    *   **Output :** Affiche le JSON exact qui *serait* envoyé au webhook, quels patterns ont matché, et si l'email aurait été exclu par les filtres.
*   **Impact :** Debugging immédiat des problèmes de parsing ou de regex (ex: tester pourquoi un lien Dropbox n'est pas détecté).

### 4. Explorateur et Nettoyage de Cache (Deduplication Manager)
La déduplication repose sur Redis (`PROCESSED_EMAIL_IDS_REDIS_KEY`). Si on veut retraiter un email, c'est compliqué.

*   **La fonctionnalité :** Gestionnaire de cache de déduplication.
*   **Fonctionnement :**
    *   **UI :** Un outil permettant de rechercher si un `email_id` ou un `subject_group` est présent dans le cache.
    *   **Action :** Bouton "Oublier cet email" (supprime la clé de Redis) pour permettre au poller de le traiter à nouveau au prochain cycle.
    *   **Visualisation :** Afficher les statistiques réelles de Redis (taille de la mémoire, nombre de clés).
*   **Impact :** Capacité à forcer le re-traitement d'un email spécifique en cas d'erreur logique, sans toucher à la base de données brute.

### 5. Visualisation des Liens R2 (File Explorer)
Vous utilisez `R2TransferService` pour offloader les fichiers.

*   **La fonctionnalité :** Historique des fichiers transférés.
*   **Fonctionnement :**
    *   Lire le fichier `webhook_links.json` (ou la base de données correspondante).
    *   **UI :** Tableau listant les derniers fichiers : `Source (Dropbox)` -> `Destination (R2)` | `Date` | `Email ID`.
    *   **Action :** Bouton pour copier le lien R2 ou tester si le lien est toujours valide.
*   **Impact :** Audit rapide pour vérifier si le transfert de fichiers fonctionne correctement et retrouver un lien R2 généré.

### 6. Notifications Slack/Discord natives
Actuellement, vous avez un `notifyOnFailure` qui semble limité.

*   **La fonctionnalité :** Webhook de monitoring système.
*   **Fonctionnement :**
    *   Ajouter un champ de configuration `SYSTEM_ALERT_WEBHOOK_URL`.
    *   Si le `background_email_poller` crash (exception non gérée) ou si le taux d'erreur dépasse X%, envoyer une alerte sur ce webhook (Slack/Discord/Teams).
*   **Impact :** Être prévenu proactivement si le serveur Render plante ou si le mot de passe IMAP a expiré, sans avoir à consulter le dashboard.

### Résumé technique pour l'implémentation

Si je devais prioriser par valeur ajoutée par rapport à votre code actuel :

1.  **Le Simulateur (Sandbox)** : Facile à implémenter (nouvelle route API utilisant les fonctions existantes dans `email_processing`) et très utile pour le debug.
2.  **La DLQ (Replay)** : Crucial pour la fiabilité en production. Nécessite un peu de stockage (Redis List).
3.  **L'Explorateur de Cache** : Simple interface sur `deduplication_service.py`.

### Fonctionnalités terminées

- ✅ **Moteur de Règles de Routage Dynamique** : Terminé (2026-01-26) - Voir section 2 pour les détails d'implémentation complète incluant la correction UI robuste et le cache-bust

Ces ajouts transformeraient l'outil en une véritable console d'administration backend.